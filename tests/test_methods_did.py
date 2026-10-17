"""Known-answer and property tests for ``krl_tutorials_data.methods.did``.

Test-first: this file was written before the estimator. The arithmetic that
defines each answer is in the test, so a reader can check the estimator against
four cell means rather than against itself.

Cross-checks use ``statsmodels`` (the ``notebooks`` extra) fitted with full
dummy variables and cluster-robust covariance, which is the convention the
module documents and the second implementation ADR 0009 section 7 promised.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import math
import time as clock

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from scipy import stats

from krl_tutorials_data.methods import did

# ---------------------------------------------------------------------------
# The hand-computed 2x2 panel.
#
#   unit  treated  y(t=1)  y(t=2)  change
#   A     yes       9      14       +5
#   B     yes      11      18       +7
#   C     no        7       9       +2
#   D     no        9      13       +4
#
#   treated: pre mean 10, post mean 16   -> change 6
#   control: pre mean  8, post mean 11   -> change 3
#   DiD = 6 - 3 = 3
#
# First-difference regression of the change on a treated dummy has residuals
# -1, +1 (treated) and -1, +1 (control).  Its HC0 variance is
#   sum(xtilde^2 * u^2) / (sum xtilde^2)^2 = 1.0 / 1.0^2 = 1.0   -> SE 1.0
# and the two-way FE regression on the same panel has the identical point
# estimate and identical CR0 variance (worked in the module docstring).
# ---------------------------------------------------------------------------
UNIT = np.array([0, 0, 1, 1, 2, 2, 3, 3])
TIME = np.array([1, 2, 1, 2, 1, 2, 1, 2])
Y = np.array([9.0, 14.0, 11.0, 18.0, 7.0, 9.0, 9.0, 13.0])
D = np.array([0.0, 1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0])


def test_two_by_two_matches_the_cell_means_by_hand() -> None:
    """Two by two matches the cell means by hand."""
    att = did.did_two_by_two(
        pre_treated=[9.0, 11.0], post_treated=[14.0, 18.0],
        pre_control=[7.0, 9.0], post_control=[9.0, 13.0],
    )
    assert att == pytest.approx((16.0 - 10.0) - (11.0 - 8.0), abs=1e-12)
    assert att == pytest.approx(3.0, abs=1e-12)


def test_twfe_on_the_balanced_two_by_two_equals_the_cell_means() -> None:
    """Twfe on the balanced two by two equals the cell means."""
    fit = did.twfe(Y, D[:, None], UNIT, TIME, ssc=False)
    assert fit.coef[0] == pytest.approx(3.0, abs=1e-12)
    assert fit.n_obs == 8 and fit.n_clusters == 4


def test_cluster_robust_se_matches_the_hand_derivation() -> None:
    """CR0: score per unit is +-0.25, so var = 4 * 0.0625 / 0.5**2 = 1.0."""
    fit = did.twfe(Y, D[:, None], UNIT, TIME, ssc=False)
    assert fit.se[0] == pytest.approx(1.0, abs=1e-12)


def test_small_sample_correction_is_the_stated_convention() -> None:
    """G/(G-1) * (N-1)/(N-K), K = 1 + 4 units + 2 periods - 1 = 6 -> 14/3."""
    corrected = did.twfe(Y, D[:, None], UNIT, TIME)
    assert corrected.se[0] == pytest.approx(math.sqrt(14.0 / 3.0), abs=1e-12)
    assert corrected.df_resid == 8 - 6


def _lsdv_cluster(y, x, unit, time, cluster=None):
    """Second implementation: dummy variables, then statsmodels' cluster option."""
    sm = pytest.importorskip("statsmodels.api")
    units = np.unique(unit)
    times = np.unique(time)
    cols = [x]
    cols += [(unit == u).astype(float)[:, None] for u in units[1:]]
    cols += [(time == t).astype(float)[:, None] for t in times[1:]]
    design = sm.add_constant(np.hstack(cols), prepend=False)
    groups = unit if cluster is None else cluster
    return sm.OLS(y, design).fit(cov_type="cluster", cov_kwds={"groups": groups})


def test_twfe_agrees_with_dummy_variable_ols_on_a_balanced_panel() -> None:
    """Twfe agrees with dummy variable ols on a balanced panel."""
    rng = np.random.default_rng(20261015)
    n_units, n_time = 12, 5
    unit = np.repeat(np.arange(n_units), n_time)
    time = np.tile(np.arange(n_time), n_units)
    treated = (unit % 3 == 0) & (time >= 3)
    x = np.column_stack([treated.astype(float), rng.normal(size=unit.size)])
    y = 2.0 * x[:, 0] - 0.5 * x[:, 1] + unit * 0.3 + time * 0.2 + rng.normal(size=unit.size)
    ours = did.twfe(y, x, unit, time)
    ref = _lsdv_cluster(y, x, unit, time)
    np.testing.assert_allclose(ours.coef, ref.params[:2], rtol=1e-10, atol=1e-10)
    np.testing.assert_allclose(ours.se, ref.bse[:2], rtol=1e-10, atol=1e-10)


def test_twfe_agrees_with_dummy_variable_ols_on_an_unbalanced_panel() -> None:
    """Twfe agrees with dummy variable ols on an unbalanced panel."""
    rng = np.random.default_rng(7)
    n_units, n_time = 15, 6
    unit = np.repeat(np.arange(n_units), n_time)
    time = np.tile(np.arange(n_time), n_units)
    keep = rng.random(unit.size) > 0.2
    unit, time = unit[keep], time[keep]
    x = ((unit % 2 == 0) & (time >= 3)).astype(float)[:, None]
    y = 1.5 * x[:, 0] + 0.1 * unit + 0.4 * time + rng.normal(size=unit.size)
    ours = did.twfe(y, x, unit, time)
    ref = _lsdv_cluster(y, x, unit, time)
    np.testing.assert_allclose(ours.coef, ref.params[:1], rtol=1e-8, atol=1e-8)
    np.testing.assert_allclose(ours.se, ref.bse[:1], rtol=1e-8, atol=1e-8)


def test_clustering_above_the_unit_level_is_supported() -> None:
    """Clustering above the unit level is supported."""
    rng = np.random.default_rng(3)
    n_units, n_time = 20, 4
    unit = np.repeat(np.arange(n_units), n_time)
    time = np.tile(np.arange(n_time), n_units)
    cluster = unit // 4
    x = ((unit % 2 == 0) & (time >= 2)).astype(float)[:, None]
    y = x[:, 0] + rng.normal(size=unit.size)
    ours = did.twfe(y, x, unit, time, cluster=cluster)
    ref = _lsdv_cluster(y, x, unit, time, cluster=cluster)
    assert ours.n_clusters == 5
    np.testing.assert_allclose(ours.se, ref.bse[:1], rtol=1e-9)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"y": Y[:-1]}, "same length"),
        ({"y": np.where(np.arange(8) == 3, np.nan, Y)}, "non-finite"),
        ({"x": np.zeros((8, 1))}, "no variation"),
        ({"cluster": np.zeros(8, dtype=int)}, "at least two clusters"),
    ],
)
def test_bad_inputs_raise_rather_than_coerce(kwargs: dict, message: str) -> None:
    """Bad inputs raise rather than coerce."""
    args = {"y": Y, "x": D[:, None], "unit": UNIT, "time": TIME, "cluster": None}
    args.update(kwargs)
    with pytest.raises(ValueError, match=message):
        did.twfe(args["y"], args["x"], args["unit"], args["time"], cluster=args["cluster"])


def test_a_regressor_collinear_with_the_fixed_effects_is_refused() -> None:
    """A treatment dummy that is constant within unit is absorbed by the unit effect."""
    always_treated_unit = (UNIT == 0).astype(float)[:, None]
    with pytest.raises(ValueError, match="no variation"):
        did.twfe(Y, always_treated_unit, UNIT, TIME)


def test_the_estimate_is_invariant_to_a_constant_shift_of_the_outcome() -> None:
    """The estimate is invariant to a constant shift of the outcome."""
    base = did.twfe(Y, D[:, None], UNIT, TIME).coef[0]
    shifted = did.twfe(Y + 1000.0, D[:, None], UNIT, TIME).coef[0]
    assert shifted == pytest.approx(base, abs=1e-9)


@settings(max_examples=40, deadline=None)
@given(
    shift_unit=st.floats(-50, 50, allow_nan=False),
    shift_time=st.floats(-50, 50, allow_nan=False),
    scale=st.floats(0.1, 20, allow_nan=False),
)
def test_property_unit_and_time_effects_do_not_move_the_estimate(
    shift_unit: float, shift_time: float, scale: float
) -> None:
    """Adding any unit effect and any time effect to y leaves the TWFE estimate alone;
    rescaling y rescales the estimate and its standard error by the same factor."""
    base = did.twfe(Y, D[:, None], UNIT, TIME)
    moved_y = Y + shift_unit * (UNIT == 1) + shift_time * (TIME == 2)
    moved = did.twfe(moved_y, D[:, None], UNIT, TIME)
    assert moved.coef[0] == pytest.approx(base.coef[0], abs=1e-8)
    assert moved.se[0] == pytest.approx(base.se[0], abs=1e-8)
    scaled = did.twfe(scale * Y, D[:, None], UNIT, TIME)
    assert scaled.coef[0] == pytest.approx(scale * base.coef[0], rel=1e-9, abs=1e-9)
    assert scaled.se[0] == pytest.approx(scale * base.se[0], rel=1e-9, abs=1e-9)


def test_a_dense_unbalanced_panel_converges_and_is_fast() -> None:
    """The scale C03 needs: ~3,000 units x 48 periods in well under 30 s."""
    rng = np.random.default_rng(1)
    n_units, n_time = 3000, 48
    unit = np.repeat(np.arange(n_units), n_time)
    period = np.tile(np.arange(n_time), n_units)
    keep = rng.random(unit.size) > 0.05
    unit, period = unit[keep], period[keep]
    adopt = rng.integers(10, 60, size=n_units)
    x = (period >= adopt[unit]).astype(float)[:, None]
    y = 0.7 * x[:, 0] + rng.normal(size=unit.size)
    t0 = clock.perf_counter()
    fit = did.twfe(y, x, unit, period)
    assert clock.perf_counter() - t0 < 30.0
    assert abs(fit.coef[0] - 0.7) < 0.1


# ---------------------------------------------------------------------------
# Wild cluster bootstrap
# ---------------------------------------------------------------------------
def _null_panel(seed: int, n_units: int = 40, n_time: int = 4):
    """Null panel."""
    rng = np.random.default_rng(seed)
    unit = np.repeat(np.arange(n_units), n_time)
    time = np.tile(np.arange(n_time), n_units)
    x = ((unit % 2 == 0) & (time >= 2)).astype(float)[:, None]
    y = rng.normal(size=unit.size) + 0.2 * time
    return y, x, unit, time


def test_wild_bootstrap_is_deterministic_for_a_seed_and_a_valid_probability() -> None:
    """Wild bootstrap is deterministic for a seed and a valid probability."""
    y, x, unit, time = _null_panel(11)
    a = did.wild_cluster_bootstrap(y, x, unit, time, test_column=0, n_boot=299, seed=5)
    b = did.wild_cluster_bootstrap(y, x, unit, time, test_column=0, n_boot=299, seed=5)
    c = did.wild_cluster_bootstrap(y, x, unit, time, test_column=0, n_boot=299, seed=6)
    assert a.p_value == b.p_value
    assert 0.0 <= a.p_value <= 1.0
    assert a.p_value != c.p_value or a.t_boot.tolist() != c.t_boot.tolist()
    assert a.t_boot.shape == (299,)


def test_wild_bootstrap_p_approximates_the_analytic_p_with_many_clusters() -> None:
    """Wild bootstrap p approximates the analytic p with many clusters."""
    y, x, unit, time = _null_panel(21, n_units=60)
    fit = did.twfe(y, x, unit, time)
    analytic = 2 * stats.t.sf(abs(fit.coef[0] / fit.se[0]), df=fit.n_clusters - 1)
    boot = did.wild_cluster_bootstrap(y, x, unit, time, test_column=0, n_boot=1999, seed=1)
    assert boot.t_stat == pytest.approx(fit.coef[0] / fit.se[0], abs=1e-9)
    assert abs(boot.p_value - analytic) < 0.08


def test_wild_bootstrap_rejects_a_large_true_effect() -> None:
    """Wild bootstrap rejects a large true effect."""
    rng = np.random.default_rng(2)
    n_units, n_time = 30, 4
    unit = np.repeat(np.arange(n_units), n_time)
    time = np.tile(np.arange(n_time), n_units)
    x = ((unit % 2 == 0) & (time >= 2)).astype(float)[:, None]
    y = 3.0 * x[:, 0] + rng.normal(size=unit.size) * 0.5
    boot = did.wild_cluster_bootstrap(y, x, unit, time, test_column=0, n_boot=499, seed=3)
    assert boot.p_value < 0.01


@pytest.mark.parametrize("weights", ["rademacher", "webb"])
def test_bootstrap_weights_have_mean_zero_and_unit_variance(weights: str) -> None:
    """Bootstrap weights have mean zero and unit variance."""
    draws = did.bootstrap_weights(weights, size=(200_000,), seed=0)
    assert abs(draws.mean()) < 0.01
    assert abs(draws.var() - 1.0) < 0.01


def test_unknown_weights_and_a_missing_seed_are_refused() -> None:
    """Unknown weights and a missing seed are refused."""
    with pytest.raises(ValueError, match="weights"):
        did.bootstrap_weights("gaussian", size=(3,), seed=0)
    y, x, unit, time = _null_panel(1)
    with pytest.raises(TypeError):
        did.wild_cluster_bootstrap(  # type: ignore[call-arg]  # pylint: disable=missing-kwoa
            y, x, unit, time, test_column=0, n_boot=9
        )
    with pytest.raises(ValueError, match="test_column"):
        did.wild_cluster_bootstrap(y, x, unit, time, test_column=3, n_boot=9, seed=0)
    with pytest.raises(ValueError, match="n_boot"):
        did.wild_cluster_bootstrap(y, x, unit, time, test_column=0, n_boot=0, seed=0)


# ---------------------------------------------------------------------------
# Event-study design matrix
# ---------------------------------------------------------------------------
def test_event_study_design_by_hand() -> None:
    """Adopt at t=3.  Reference period -1 is omitted; endpoints are binned."""
    time = np.array([1, 2, 3, 4, 5, 1, 2, 3, 4, 5])
    unit = np.array([0] * 5 + [1] * 5)
    adoption = np.array([3.0] * 5 + [np.nan] * 5)  # unit 1 is never treated
    design = did.event_study_design(time, adoption, leads=2, lags=1)
    # relative time of unit 0: -2, -1, 0, +1, +2 ; lags binned at +1 (so +2 -> +1)
    assert design.labels == (-2, 0, 1)
    expected = np.array(
        [
            [1, 0, 0],  # rel -2
            [0, 0, 0],  # rel -1 : the reference period, all zeros
            [0, 1, 0],  # rel  0
            [0, 0, 1],  # rel +1
            [0, 0, 1],  # rel +2 binned into +1
        ],
        dtype=float,
    )
    np.testing.assert_array_equal(design.matrix[:5], expected)
    assert not design.matrix[5:].any(), "never-treated units carry no event-time dummies"
    assert unit.size == design.matrix.shape[0]


def test_event_study_without_binning_drops_the_far_periods() -> None:
    """Window -1..+1 with reference -1 leaves labels (0, +1); -2 and +2 are all-zero rows."""
    time = np.arange(1, 6)
    adoption = np.full(5, 3.0)
    design = did.event_study_design(time, adoption, leads=1, lags=1, bin_endpoints=False)
    assert design.labels == (0, 1)
    expected = np.array([[0, 0], [0, 0], [1, 0], [0, 1], [0, 0]], dtype=float)
    np.testing.assert_array_equal(design.matrix, expected)


def test_event_study_rejects_a_reference_outside_the_window() -> None:
    """Event study rejects a reference outside the window."""
    with pytest.raises(ValueError, match="reference"):
        did.event_study_design(np.arange(4), np.full(4, 2.0), leads=1, lags=1, reference=-5)


def test_event_study_coefficients_recover_a_known_dynamic_effect() -> None:
    """Zero effect before adoption, +2 on impact, +4 afterwards, no noise."""
    n_units, n_time = 20, 8
    unit = np.repeat(np.arange(n_units), n_time)
    time = np.tile(np.arange(n_time), n_units)
    adopt_by_unit = np.where(np.arange(n_units) < 10, 4.0, np.nan)
    adoption = adopt_by_unit[unit]
    rel = time - adoption
    y = np.where(rel == 0, 2.0, np.where(rel >= 1, 4.0, 0.0)) + 0.5 * unit + 0.1 * time
    design = did.event_study_design(time, adoption, leads=3, lags=3)
    fit = did.twfe(y, design.matrix, unit, time, ssc=False)
    got = dict(zip(design.labels, fit.coef))
    for k in (-3, -2):
        assert got[k] == pytest.approx(0.0, abs=1e-8)
    assert got[0] == pytest.approx(2.0, abs=1e-8)
    for k in (1, 2, 3):
        assert got[k] == pytest.approx(4.0, abs=1e-8)


def test_two_by_two_refuses_an_empty_or_non_finite_group() -> None:
    """A group with no observations or a NaN is an error, not a dropped cell."""
    with pytest.raises(ValueError, match="pre_control"):
        did.did_two_by_two([1.0], [2.0], [], [3.0])
    with pytest.raises(ValueError, match="post_treated"):
        did.did_two_by_two([1.0], [float("nan")], [1.0], [3.0])


def test_labels_must_be_one_dimensional() -> None:
    """A two-dimensional unit label array is refused."""
    with pytest.raises(ValueError, match="one-dimensional"):
        did.twfe(Y, D[:, None], np.column_stack([UNIT, UNIT]), TIME)


def test_two_identical_regressors_are_collinear() -> None:
    """Two copies of one column leave the Gram matrix singular."""
    two = np.column_stack([D, D])
    with pytest.raises(ValueError, match="collinear"):
        did.twfe(Y, two, UNIT, TIME)


def test_too_few_observations_for_the_parameters_is_refused() -> None:
    """N must exceed regressors plus absorbed effects when a correction is requested."""
    with pytest.raises(ValueError, match="cannot support"):
        pick = [0, 1, 4, 5]
        did.twfe(Y[pick], D[pick, None], UNIT[pick], TIME[pick])


def test_non_convergence_raises_instead_of_returning_partial_demeaning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With one pass allowed on an unbalanced panel the iteration cannot finish."""
    rng = np.random.default_rng(0)
    unit = np.repeat(np.arange(10), 6)
    period = np.tile(np.arange(6), 10)
    keep = rng.random(unit.size) > 0.4
    values = rng.normal(size=unit.size)[keep]
    monkeypatch.setattr(did, "_MAX_ITER", 1)
    codes_u = np.unique(unit[keep], return_inverse=True)[1]
    codes_t = np.unique(period[keep], return_inverse=True)[1]
    with pytest.raises(RuntimeError, match="did not converge"):
        did.demean_two_way(values, codes_u, codes_t, 10, 6)


def test_bootstrap_with_a_control_regressor_imposes_the_null_on_the_tested_column() -> None:
    """Two regressors: the restricted model keeps the control and drops the tested column."""
    rng = np.random.default_rng(4)
    n_units, n_time = 25, 4
    unit = np.repeat(np.arange(n_units), n_time)
    time = np.tile(np.arange(n_time), n_units)
    treated = ((unit % 2 == 0) & (time >= 2)).astype(float)
    control = rng.normal(size=unit.size)
    y = 0.8 * control + rng.normal(size=unit.size)
    result = did.wild_cluster_bootstrap(
        y, np.column_stack([treated, control]), unit, time,
        test_column=0, n_boot=199, seed=9, weights="webb",
    )
    assert result.weights == "webb" and 0.0 <= result.p_value <= 1.0
    strong = did.wild_cluster_bootstrap(
        y, np.column_stack([treated, control]), unit, time, test_column=1, n_boot=199, seed=9
    )
    assert strong.p_value < 0.05


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"leads": -1, "lags": 1}, "non-negative"),
        ({"leads": 1, "lags": 1, "time": np.arange(3)}, "equal length"),
        ({"leads": 1, "lags": 1, "adoption": np.array([2.5, 2.5, 2.5, 2.5])}, "integer"),
    ],
)
def test_event_study_input_validation(kwargs: dict, message: str) -> None:
    """Negative windows, ragged inputs and fractional event time are refused."""
    time = kwargs.pop("time", np.arange(4))
    adoption = kwargs.pop("adoption", np.full(4, 2.0))
    with pytest.raises(ValueError, match=message):
        did.event_study_design(time, adoption, **kwargs)


def test_a_one_dimensional_regressor_is_accepted_as_a_single_column() -> None:
    """A vector x is treated as one column."""
    flat = did.twfe(Y, D, UNIT, TIME, ssc=False)
    assert flat.coef.shape == (1,)
    assert flat.coef[0] == pytest.approx(3.0, abs=1e-12)
