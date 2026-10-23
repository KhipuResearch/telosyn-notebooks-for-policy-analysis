"""Known-answer tests for the staggered-adoption estimators in ``methods.did``.

Panels are built noise-free from unit effects, period effects and a stated treatment
effect for each cohort and event time, so the answer is known before the estimator runs.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from krl_tutorials_data.methods import did

Effect = Callable[[int], float]


def make_panel(
    effects: dict[float, Effect],
    sizes: dict[float, int],
    periods: int,
    *,
    noise: float = 0.0,
    seed: int = 0,
) -> dict[str, np.ndarray]:
    """Long panel: unit effect + period effect + cohort effect; ``nan`` = never treated."""
    rng = np.random.default_rng(seed)
    rows = []
    uid = 0
    for cohort, n in sizes.items():
        for _ in range(n):
            for t in range(periods):
                lift = 0.0
                if np.isfinite(cohort) and t >= cohort:
                    lift = effects[cohort](int(t - cohort))
                y = 0.3 * uid + 0.5 * t + lift + (noise * rng.normal() if noise else 0.0)
                rows.append((uid, t, cohort, y))
            uid += 1
    arr = np.array(rows, dtype=float)
    return {"unit": arr[:, 0], "time": arr[:, 1], "cohort": arr[:, 2], "y": arr[:, 3]}


def treated_indicator(p: dict[str, np.ndarray]) -> np.ndarray:
    """Absorbing treatment dummy implied by the cohort column."""
    return (p["time"] >= np.where(np.isnan(p["cohort"]), np.inf, p["cohort"])).astype(float)


def test_two_groups_one_timing_is_the_hand_computed_two_by_two() -> None:
    """Treated y = 1,2,5,6; control y = 1,2,3,4: DiD = (5.5-1.5) - (3.5-1.5) = 2, weight 1."""
    unit = np.repeat([0, 1, 2, 3], 4)
    time = np.tile([0, 1, 2, 3], 4)
    y = np.array([1, 2, 5, 6, 1, 2, 5, 6, 1, 2, 3, 4, 1, 2, 3, 4], dtype=float)
    cohort = np.repeat([2, 2, np.nan, np.nan], 4)
    out = did.bacon_decomposition(y, unit, time, cohort)
    assert out.twfe == pytest.approx(2.0)
    assert len(out.comparisons) == 1
    only = out.comparisons[0]
    assert (only.kind, only.estimate, only.weight) == (
        "treated_vs_never",
        pytest.approx(2.0),
        pytest.approx(1.0),
    )


def test_weights_rebuild_the_pooled_estimate_with_all_three_kinds_present() -> None:
    """All four group types present: the weights sum to 1 and rebuild the TWFE coefficient."""
    p = make_panel(
        {0: lambda e: 2.0, 3: lambda e: 1 + e, 6: lambda e: 0.5},
        {np.nan: 4, 0: 3, 3: 4, 6: 5},
        10,
        noise=0.4,
        seed=5,
    )
    out = did.bacon_decomposition(p["y"], p["unit"], p["time"], p["cohort"])
    fit = did.twfe(p["y"], treated_indicator(p), p["unit"], p["time"])
    assert out.twfe == pytest.approx(float(fit.coef[0]), abs=1e-9)
    assert sum(c.weight for c in out.comparisons) == pytest.approx(1.0)
    kinds = out.by_kind()
    totals = [weight for weight, _ in kinds.values()]
    assert all(w > 0 for w in totals)
    assert sum(totals) == pytest.approx(1.0)


def test_the_sign_flips_when_effects_grow_and_the_decomposition_says_why() -> None:
    """Every true effect is at least 1, yet TWFE is negative: the treated serve as control."""
    p = make_panel({3: lambda e: 1 + 3 * e, 8: lambda e: 1.0}, {3: 5, 8: 5}, 12)
    out = did.bacon_decomposition(p["y"], p["unit"], p["time"], p["cohort"])
    assert out.twfe < 0
    weight, mean = out.by_kind()["later_vs_earlier"]
    assert weight > 0.2 and mean < 0
    assert min(1 + 3 * e for e in range(9)) >= 1.0  # every true effect is positive


@settings(max_examples=25, deadline=None)
@given(seed=st.integers(0, 10_000))
def test_property_the_decomposition_always_rebuilds_the_pooled_estimate(seed: int) -> None:
    """For any random staggered panel the weighted comparisons equal the TWFE coefficient."""
    rng = np.random.default_rng(seed)
    cohorts = [np.nan, 0.0, 2.0, 4.0, 7.0]
    picked = {c: int(rng.integers(1, 4)) for c in cohorts if rng.random() < 0.8}
    picked.setdefault(2.0, 2)
    p = make_panel(
        {c: (lambda e, s=rng.normal(): s + 0.3 * e) for c in picked},
        picked,
        9,
        noise=0.5,
        seed=seed,
    )
    out = did.bacon_decomposition(p["y"], p["unit"], p["time"], p["cohort"])
    fit = did.twfe(p["y"], treated_indicator(p), p["unit"], p["time"])
    assert out.twfe == pytest.approx(float(fit.coef[0]), abs=1e-8)
    assert sum(c.weight for c in out.comparisons) == pytest.approx(1.0)


def test_decomposition_input_guards() -> None:
    """Unbalanced panels, no variation and a unit whose cohort changes all raise."""
    p = make_panel({2: lambda e: 1.0}, {2: 2, np.nan: 2}, 5)
    with pytest.raises(ValueError, match="balanced"):
        did.bacon_decomposition(p["y"][1:], p["unit"][1:], p["time"][1:], p["cohort"][1:])
    with pytest.raises(ValueError, match="no variation"):
        did.bacon_decomposition(p["y"], p["unit"], p["time"], np.full_like(p["cohort"], np.nan))
    bad = p["cohort"].copy()
    bad[0] = 3.0
    with pytest.raises(ValueError, match="same in every period"):
        did.bacon_decomposition(p["y"], p["unit"], p["time"], bad)
    nan_y = p["y"].copy()
    nan_y[3] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        did.bacon_decomposition(nan_y, p["unit"], p["time"], p["cohort"])
    with pytest.raises(ValueError, match="one-dimensional"):
        did.bacon_decomposition(p["y"][:-1], p["unit"], p["time"], p["cohort"])


EFFECTS = {3: lambda e: 1.0 + 0.5 * e, 6: lambda e: 3.0 - 0.25 * e}
SIZES = {np.nan: 6, 3: 4, 6: 8}


def expected_att(e: int) -> float:
    """Cohort-size-weighted truth at event time ``e`` (cohort 3 has 4 units, cohort 6 has 8)."""
    parts = [(4, EFFECTS[3](e)) if 3 + e < 12 else None, (8, EFFECTS[6](e)) if 6 + e < 12 else None]
    live = [x for x in parts if x]
    return sum(n * v for n, v in live) / sum(n for n, _ in live)


def test_sun_abraham_recovers_the_known_effects_where_twfe_does_not() -> None:
    """Noise-free: ATT(e) matches the cohort-share-weighted truth; the TWFE dummy does not.

    ``lags`` is wide enough that no post-period cell is binned: a binned cell mixes
    different true effects and would leak into the fixed effects.
    """
    p = make_panel(EFFECTS, SIZES, 12)
    fit = did.sun_abraham(
        p["y"], p["unit"], p["time"], p["cohort"], leads=2, lags=9, cluster=p["unit"]
    )
    for e, a in zip(fit.event_times, fit.att):
        want = 0.0 if e < 0 else expected_att(e)
        assert a == pytest.approx(want, abs=1e-8), e
    assert fit.event_times[-1] == 8
    assert fit.cohorts == (3.0, 6.0)
    assert fit.n_clusters == 18
    truth = np.mean([expected_att(e) for e in range(0, 9)])
    assert fit.overall == pytest.approx(truth, abs=1e-8)
    naive = did.twfe(p["y"], treated_indicator(p), p["unit"], p["time"]).coef[0]
    assert abs(naive - truth) > 0.1
    assert np.all(fit.se >= 0) and fit.overall_se >= 0


def test_sun_abraham_guards() -> None:
    """It needs never-treated units, integer event time and a sensible window."""
    p = make_panel(EFFECTS, {3: 3, 6: 3}, 12)
    with pytest.raises(ValueError, match="never-treated"):
        did.sun_abraham(p["y"], p["unit"], p["time"], p["cohort"], leads=1, lags=2)
    q = make_panel(EFFECTS, SIZES, 12)
    with pytest.raises(ValueError, match="reference"):
        did.sun_abraham(q["y"], q["unit"], q["time"], q["cohort"], leads=1, lags=2, reference=5)
    with pytest.raises(ValueError, match="integer-valued"):
        did.sun_abraham(
            q["y"],
            q["unit"],
            q["time"] + 0.5,
            np.where(np.isnan(q["cohort"]), np.nan, q["cohort"]),
            leads=1,
            lags=2,
        )
    with pytest.raises(ValueError, match="same length"):
        did.sun_abraham(q["y"][:-1], q["unit"], q["time"], q["cohort"], leads=1, lags=2)
    with pytest.raises(ValueError, match="inside the event window"):
        beyond = np.where(
            np.isfinite(q["cohort"]), 40.0, np.nan
        )  # first treated after the panel ends
        did.sun_abraham(q["y"], q["unit"], q["time"], beyond, leads=1, lags=2)


@pytest.mark.parametrize("control", ["never", "not_yet"])
def test_group_time_att_recovers_the_known_effects(control: str) -> None:
    """With parallel trends in the untreated outcome both control groups give the truth."""
    p = make_panel(EFFECTS, SIZES, 12)
    fit = did.group_time_att(
        p["y"],
        p["unit"],
        p["time"],
        p["cohort"],
        leads=2,
        lags=3,
        control=control,
        n_boot=60,
        seed=7,
    )
    for e, a in zip(fit.event_times, fit.att):
        want = 0.0 if e < 0 else expected_att(e)
        assert a == pytest.approx(want, abs=1e-8), (control, e)
    assert fit.overall == pytest.approx(np.mean([expected_att(e) for e in range(0, 4)]), abs=1e-8)
    assert fit.overall_se >= 0 and fit.overall_ci[0] <= fit.overall <= fit.overall_ci[1] + 1e-9
    again = did.group_time_att(
        p["y"],
        p["unit"],
        p["time"],
        p["cohort"],
        leads=2,
        lags=3,
        control=control,
        n_boot=60,
        seed=7,
    )
    assert again.overall_se == fit.overall_se


def test_group_time_att_clusters_and_guards() -> None:
    """Clusters are resampled whole; a bad control, window or cluster raises."""
    p = make_panel(EFFECTS, SIZES, 12, noise=0.3, seed=2)
    clusters = (p["unit"] // 3).astype(int)
    fit = did.group_time_att(
        p["y"],
        p["unit"],
        p["time"],
        p["cohort"],
        leads=2,
        lags=3,
        n_boot=40,
        seed=1,
        cluster=clusters,
    )
    assert fit.n_boot == 40 and np.all(np.isfinite(fit.se))
    with pytest.raises(ValueError, match="control must be"):
        did.group_time_att(
            p["y"],
            p["unit"],
            p["time"],
            p["cohort"],
            leads=1,
            lags=1,
            control="x",
            n_boot=10,
            seed=1,
        )  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="n_boot"):
        did.group_time_att(
            p["y"], p["unit"], p["time"], p["cohort"], leads=1, lags=1, n_boot=1, seed=1
        )
    with pytest.raises(ValueError, match="one cluster"):
        did.group_time_att(
            p["y"],
            p["unit"],
            p["time"],
            p["cohort"],
            leads=1,
            lags=1,
            n_boot=10,
            seed=1,
            cluster=p["time"],
        )
    never_only = np.full_like(p["cohort"], np.nan)
    with pytest.raises(ValueError, match="no cohort"):
        did.group_time_att(
            p["y"], p["unit"], p["time"], never_only, leads=1, lags=1, n_boot=10, seed=1
        )


def test_sun_abraham_pooled_lead_bin_weights_cohorts_by_units_not_observations() -> None:
    """The binned lead cell averages cohorts by their unit counts.

    Cohort 4 has 2 units and a lead shift of 1.0 at every event time <= -2; cohort 8
    has 6 units and a shift of 5.0. Cohort 8 contributes 7 periods to the e <= -2 bin and
    cohort 4 contributes 3, so weighting by observations would give (6*1 + 42*5)/48 = 4.5.
    The units-weighted truth is (2*1 + 6*5)/8 = 4.0.
    """
    effects = {4: lambda e: 1.0 + 0.5 * e, 8: lambda e: 2.0}
    p = make_panel(effects, {np.nan: 6, 4: 2, 8: 6}, 12)
    shift = {4.0: 1.0, 8.0: 5.0}
    lead = np.isfinite(p["cohort"]) & (p["time"] - p["cohort"] <= -2)
    p["y"] = p["y"] + np.where(lead, [shift.get(c, 0.0) for c in p["cohort"]], 0.0)
    fit = did.sun_abraham(
        p["y"], p["unit"], p["time"], p["cohort"], leads=2, lags=8, cluster=p["unit"]
    )
    assert fit.att[fit.event_times.index(-2)] == pytest.approx(4.0, abs=1e-8)


def test_group_time_att_not_yet_controls_exclude_the_cohort_and_the_treated_at_base() -> None:
    """Pre-period effects are zero under parallel untreated trends, whatever the control set.

    For cohort 9 at e = -5 (period 4, base period 8) cohort 6 is already treated at the
    base period and cohort 9 is the cohort itself; neither is a valid control, so every
    pre-period effect is exactly zero. A control set that admits them returns a non-zero value.
    """
    effects = {3: lambda e: 4.0, 6: lambda e: 10.0, 9: lambda e: 3.0}
    p = make_panel(effects, {np.nan: 6, 3: 4, 6: 4, 9: 4}, 12)
    fit = did.group_time_att(
        p["y"], p["unit"], p["time"], p["cohort"],
        leads=5, lags=2, control="not_yet", n_boot=20, seed=3,
    )
    pre = [a for e, a in zip(fit.event_times, fit.att) if e < 0]
    assert pre and np.allclose(pre, 0.0, atol=1e-9)
