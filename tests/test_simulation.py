"""The one synthetic generator in this corpus, and the guarantees it must keep.

``krl_tutorials_data.simulation`` exists for a single artifact, D30, whose
subject is not well-being but false discovery. That notebook scores a published
analysis against a truth known by construction, so this module has two
obligations no other module here has:

1.  **It must reproduce the archived D30 notebook exactly.** Every number that
    notebook published -- the OLS coefficients, the sample means, the k-means
    cluster profile, the regional winner -- has to come back out. If it does
    not, D30 is not scoring the archived artifact; it is scoring a paraphrase
    of it, and the whole exercise is worthless. This is why the generator uses
    the legacy ``RandomState`` in the archive's draw order, and why it keeps a
    draw the archive discarded.

2.  **Its declared coefficients must be the ones it actually uses.** The truth
    object is the yardstick every claim in D30 is measured against. A generator
    whose documentation and behaviour disagree would let the notebook confidently
    score findings against the wrong answer.

The module is also fenced: nothing in the retrieval path may import it.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import inspect
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from krl_tutorials_data import simulation, sources
from krl_tutorials_data.simulation import (
    SimulationSpec,
    WELLBEING_NULL_PREDICTORS,
    WELLBEING_PREDICTORS,
    WELLBEING_TRUTH,
    WellbeingTruth,
    simulate_wellbeing,
)

FORMULA = "life_satisfaction ~ " + " + ".join(WELLBEING_PREDICTORS)


def _ols(frame: pd.DataFrame):
    from statsmodels.formula.api import ols

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return ols(FORMULA, data=frame).fit()


# --------------------------------------------------------------------------
# 1. Fidelity to the archived artifact
# --------------------------------------------------------------------------

#: Verbatim from the stored outputs of
#: ``notebooks/09_planned/D30_subjective_wellbeing/D30_D30_subjective_wellbeing.ipynb``.
ARCHIVED_COEFFICIENTS = {
    "unemployment_rate": (0.0770, 0.0482),
    "health_coverage_pct": (0.0365, 0.0051),
    "median_income": (0.0000, 0.0000),
}
ARCHIVED_MEANS = {
    "life_satisfaction": 7.37,
    "happiness_score": 5.99,
    "poor_mental_health_days": 3.52,
}
#: The archive's "WELL-BEING CLUSTER PROFILES" table, k=3, random_state=42.
ARCHIVED_CLUSTERS = [
    (5, 7.96, 87_424.29),
    (24, 7.66, 69_003.89),
    (21, 6.90, 58_081.32),
]


@pytest.fixture(scope="module")
def archived() -> pd.DataFrame:
    frame, _ = simulate_wellbeing(seed=42)
    return frame


@pytest.mark.parametrize("name", sorted(ARCHIVED_COEFFICIENTS))
def test_the_archived_regression_block_is_reproduced(archived: pd.DataFrame, name: str) -> None:
    """The load-bearing test. Without it D30 scores a paraphrase, not the artifact."""
    model = _ols(archived)
    want_beta, want_p = ARCHIVED_COEFFICIENTS[name]
    assert round(float(model.params[name]), 4) == want_beta
    assert round(float(model.pvalues[name]), 4) == want_p


@pytest.mark.parametrize("column,expected", sorted(ARCHIVED_MEANS.items()))
def test_the_archived_sample_means_are_reproduced(
    archived: pd.DataFrame, column: str, expected: float
) -> None:
    assert round(float(archived[column].mean()), 2) == expected


def test_the_archived_cluster_profile_is_reproduced(archived: pd.DataFrame) -> None:
    """D30's sharpest comparison is against this exact table. Pin it."""
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    features = ["life_satisfaction", "poor_mental_health_days", "happiness_score", "median_income"]
    scaled = StandardScaler().fit_transform(archived[features])
    labels = KMeans(n_clusters=3, random_state=42, n_init=10).fit_predict(scaled)
    profile = archived.assign(_c=labels).groupby("_c")
    observed = [
        (int(len(g)), round(float(g["life_satisfaction"].mean()), 2),
         round(float(g["median_income"].mean()), 2))
        for _, g in profile
    ]
    assert observed == ARCHIVED_CLUSTERS


def test_the_archived_regional_winner_is_reproduced(archived: pd.DataFrame) -> None:
    """Region is an independent draw, so this winner is an artifact -- a pinned one."""
    means = archived.groupby("region")["life_satisfaction"].mean()
    assert means.idxmax() == "Northeast"
    assert round(float(means.max()), 2) == 7.55


def test_the_discarded_draw_is_load_bearing() -> None:
    """Document why a dead line stays in the generator.

    Removing the archive's overwritten happiness draw advances the bit stream
    and changes every number after it. This test reproduces that deletion and
    asserts the output moves, so nobody tidies the line away.
    """
    rng = np.random.RandomState(42)
    rng.normal(7.2, 0.8, 50)
    rng.normal(3.5, 1.2, 50)
    rng.normal(6.8, 0.7, 50)  # the draw the generator keeps
    kept = rng.normal(65_000, 15_000, 50)

    rng2 = np.random.RandomState(42)
    rng2.normal(7.2, 0.8, 50)
    rng2.normal(3.5, 1.2, 50)
    tidied = rng2.normal(65_000, 15_000, 50)

    assert not np.allclose(kept, tidied), (
        "if these agreed the dead draw could be deleted; they do not, so it stays"
    )


# --------------------------------------------------------------------------
# 2. The declared truth is the truth actually used
# --------------------------------------------------------------------------

LARGE = 40_000


@pytest.fixture(scope="module")
def large_sample() -> pd.DataFrame:
    frame, _ = simulate_wellbeing(seed=7, n=LARGE)
    return frame


def test_the_declared_true_coefficients_are_recovered_at_large_n(
    large_sample: pd.DataFrame,
) -> None:
    """The yardstick has to be the thing being used, or every score in D30 is wrong."""
    model = _ols(large_sample)
    for name, declared in WELLBEING_TRUTH.as_dict().items():
        if declared == 0:
            continue
        estimate = float(model.params[name])
        assert estimate == pytest.approx(declared, rel=0.06), (
            f"{name}: declared {declared:g}, recovered {estimate:g} at n={LARGE:,}"
        )


@pytest.mark.parametrize("name", WELLBEING_NULL_PREDICTORS)
def test_a_declared_null_predictor_is_null_at_large_n(
    large_sample: pd.DataFrame, name: str
) -> None:
    model = _ols(large_sample)
    assert float(model.params[name]) == pytest.approx(0.0, abs=0.002), (
        f"{name} is declared to have no effect but a large sample disagrees"
    )


def test_region_enters_no_outcome(large_sample: pd.DataFrame) -> None:
    """Every regional finding in D30 is an artifact. Establish it rather than assert it."""
    spread = large_sample.groupby("region")["life_satisfaction"].mean()
    assert float(spread.max() - spread.min()) < 0.02, (
        "region must be inert; a real regional gradient would make D30's "
        "regional-artifact section false"
    )


def test_mental_health_days_enters_no_outcome(large_sample: pd.DataFrame) -> None:
    corr = large_sample["poor_mental_health_days"].corr(large_sample["life_satisfaction"])
    assert abs(float(corr)) < 0.02


def test_happiness_is_a_noisy_echo_at_the_declared_coefficient(
    large_sample: pd.DataFrame,
) -> None:
    from statsmodels.formula.api import ols

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = ols("happiness_score ~ life_satisfaction", data=large_sample).fit()
    assert float(model.params["life_satisfaction"]) == pytest.approx(
        WELLBEING_TRUTH.happiness_on_satisfaction, rel=0.03
    )


def test_the_income_coefficient_is_real_but_prints_as_zero_at_four_decimals() -> None:
    """The archive's most quotable defect, pinned as a property of the units."""
    declared = WELLBEING_TRUTH.income_per_dollar
    assert declared > 0
    assert f"{declared:.4f}" == "0.0000", (
        "D30 teaches that a true effect was displayed as nothing; if the units "
        "ever change so that it prints non-zero, that lesson needs rewriting"
    )


# --------------------------------------------------------------------------
# 3. signal severs the true effects, and only those
# --------------------------------------------------------------------------

def test_signal_zero_severs_every_true_effect() -> None:
    frame, spec = simulate_wellbeing(seed=7, n=LARGE, signal=0.0)
    model = _ols(frame)
    for name in WELLBEING_PREDICTORS:
        assert float(model.params[name]) == pytest.approx(0.0, abs=0.002), (
            f"{name} still moves the target at signal=0; D30's pure-noise "
            "sections would then be measuring a real effect"
        )
    assert all(value == 0 for value in spec.truth.values())


def test_signal_scales_the_true_effects_proportionally() -> None:
    frame, spec = simulate_wellbeing(seed=7, n=LARGE, signal=0.5)
    model = _ols(frame)
    assert float(model.params["health_coverage_pct"]) == pytest.approx(
        0.5 * WELLBEING_TRUTH.coverage_per_point, rel=0.08
    )
    assert spec.truth["health_coverage_pct"] == 0.5 * WELLBEING_TRUTH.coverage_per_point


def test_signal_does_not_change_the_predictors_themselves() -> None:
    """Only the target's construction may respond to signal."""
    full, _ = simulate_wellbeing(seed=11, n=400, signal=1.0)
    none, _ = simulate_wellbeing(seed=11, n=400, signal=0.0)
    for name in WELLBEING_PREDICTORS:
        pd.testing.assert_series_equal(full[name], none[name])
    assert not np.allclose(full["life_satisfaction"], none["life_satisfaction"])


# --------------------------------------------------------------------------
# 4. Determinism and the argument contract
# --------------------------------------------------------------------------

def test_the_same_seed_gives_the_same_frame() -> None:
    a, spec_a = simulate_wellbeing(seed=3)
    b, spec_b = simulate_wellbeing(seed=3)
    pd.testing.assert_frame_equal(a, b)
    assert spec_a.digest == spec_b.digest


def test_different_seeds_give_different_frames() -> None:
    a, _ = simulate_wellbeing(seed=3)
    b, _ = simulate_wellbeing(seed=4)
    assert not np.allclose(a["life_satisfaction"], b["life_satisfaction"])


def test_the_seed_has_no_default() -> None:
    """A default seed is how a simulation becomes one dataset everybody cites."""
    parameters = inspect.signature(simulate_wellbeing).parameters
    assert parameters["seed"].default is inspect.Parameter.empty
    assert parameters["seed"].kind is inspect.Parameter.KEYWORD_ONLY


@pytest.mark.parametrize("bad_n", [2, 1, 0, -5])
def test_an_unfittable_n_is_refused(bad_n: int) -> None:
    with pytest.raises(ValueError, match="at least 3"):
        simulate_wellbeing(seed=1, n=bad_n)


def test_a_negative_signal_is_refused() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        simulate_wellbeing(seed=1, signal=-1.0)


# --------------------------------------------------------------------------
# 5. A spec is not a provenance record
# --------------------------------------------------------------------------

def test_a_simulation_spec_is_not_a_provenance_record() -> None:
    _, spec = simulate_wellbeing(seed=1)
    assert isinstance(spec, SimulationSpec)
    assert not isinstance(spec, sources.DataProvenance)
    for absent in ("endpoint", "vintage", "source_name", "content_sha256"):
        assert not hasattr(spec, absent), (
            f"SimulationSpec exposes {absent!r}; nothing is upstream of a "
            "simulation and a reader must not be able to ask it for one"
        )


def test_the_spec_announces_itself_as_simulated() -> None:
    _, spec = simulate_wellbeing(seed=1)
    assert "SIMULATED" in str(spec)
    assert "SIMULATED" in spec.notes[0] and "Nothing here was measured" in spec.notes[0]
    joined = " ".join(spec.notes)
    assert "artifact" in joined
    for name in WELLBEING_NULL_PREDICTORS:
        assert name in joined


def test_the_spec_digest_changes_with_every_parameter() -> None:
    base = simulate_wellbeing(seed=1)[1].digest
    assert simulate_wellbeing(seed=2)[1].digest != base
    assert simulate_wellbeing(seed=1, n=60)[1].digest != base
    assert simulate_wellbeing(seed=1, signal=0.0)[1].digest != base


def test_a_custom_truth_is_reflected_in_the_spec() -> None:
    truth = WellbeingTruth(coverage_per_point=0.05)
    _, spec = simulate_wellbeing(seed=1, truth=truth)
    assert spec.truth["health_coverage_pct"] == 0.05


# --------------------------------------------------------------------------
# 6. The fence
# --------------------------------------------------------------------------

def test_the_retrieval_path_never_imports_the_simulator() -> None:
    """Real-data-only is a property of the package, not just of the notebooks.

    Matched on the import statement, not on the word. A first draft of this test
    grepped every module for "simulation" and failed on a docstring in
    ``reliability.py`` explaining that a bound is exact rather than
    simulation-based -- a check that looked right and measured the wrong thing,
    which is the defect class this whole corpus exists to catch.
    """
    package = Path(sources.__file__).parent
    imports = re.compile(
        r"^\s*(?:from\s+[\w.]*\bsimulation\b|import\s+[\w.]*\bsimulation\b)", re.M
    )
    offenders = [
        path.name
        for path in sorted(package.glob("*.py"))
        if path.name not in {"simulation.py", "__init__.py"}
        and imports.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        "the synthetic generator is imported by the retrieval path: "
        + ", ".join(offenders)
    )


def test_the_simulator_does_not_reach_the_network() -> None:
    source = inspect.getsource(simulation)
    for forbidden in ("requests", "urllib", "http", "fetch_"):
        assert forbidden not in source, (
            f"simulation.py mentions {forbidden!r}; it must generate, never retrieve"
        )
