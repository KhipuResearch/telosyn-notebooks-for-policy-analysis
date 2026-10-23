"""Known-answer tests for ``krl_tutorials_data.methods.rdd``.

Written before the estimator. A step function with no noise has an exact answer
at every bandwidth; that is the known answer, and seeded noise is the tolerance
case. Test fixtures may use seeded randomness; the gates do not scan ``tests/``.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from scipy import stats

from krl_tutorials_data.methods import rdd


def test_hand_computed_step_with_a_uniform_kernel() -> None:
    """Left points (-3,-2,-1) on y = x + 3 and right points (0,1,2) on y = 2x + 5.

    Each side is an exact line, so the intercepts at the cutoff are 3 and 5 and
    the discontinuity is 5 - 3 = 2 with zero residual.
    """
    x = np.array([-3.0, -2.0, -1.0, 0.0, 1.0, 2.0])
    y = np.array([0.0, 1.0, 2.0, 5.0, 7.0, 9.0])
    fit = rdd.local_linear(x, y, cutoff=0.0, bandwidth=3.5, kernel="uniform")
    assert fit.estimate == pytest.approx(2.0, abs=1e-12)
    assert fit.se == pytest.approx(0.0, abs=1e-9)
    assert (fit.n_left, fit.n_right) == (3, 3)


@pytest.mark.parametrize("bandwidth", [2.5, 4.0, 7.0, 10.0])
@pytest.mark.parametrize("kernel", ["triangular", "uniform"])
def test_zero_noise_step_is_recovered_exactly_at_every_bandwidth(
    bandwidth: float, kernel: str
) -> None:
    """Different slopes either side: a local-linear fit is exact, so tau is exact."""
    x = np.arange(-12.0, 13.0)
    y = 4.0 + 0.5 * x + 3.25 * (x >= 0) + 0.2 * x * (x >= 0)
    fit = rdd.local_linear(x, y, cutoff=0.0, bandwidth=bandwidth, kernel=kernel)
    assert fit.estimate == pytest.approx(3.25, abs=1e-9)


def test_seeded_noise_is_within_a_few_standard_errors() -> None:
    """Seeded noise is within a few standard errors."""
    rng = np.random.default_rng(10)
    x = rng.uniform(-5, 5, 4000)
    y = 1.0 + 0.3 * x + 2.0 * (x >= 0) + rng.normal(scale=1.0, size=x.size)
    fit = rdd.local_linear(x, y, cutoff=0.0, bandwidth=2.0)
    assert abs(fit.estimate - 2.0) < 4 * fit.se
    assert fit.se > 0


def test_a_cutoff_shift_moves_the_estimate_with_it() -> None:
    """A cutoff shift moves the estimate with it."""
    x = np.arange(40.0, 71.0)
    y = 10.0 + 0.1 * (x - 55) + 6.0 * (x >= 55)
    fit = rdd.local_linear(x, y, cutoff=55.0, bandwidth=8.0)
    assert fit.estimate == pytest.approx(6.0, abs=1e-9)


def test_survey_weights_change_the_estimand_not_the_exact_answer() -> None:
    """Survey weights change the estimand not the exact answer."""
    x = np.arange(-10.0, 11.0)
    y = 2.0 + 1.0 * (x >= 0)
    w = np.linspace(1.0, 50.0, x.size)
    fit = rdd.local_linear(x, y, cutoff=0.0, bandwidth=6.0, weights=w)
    assert fit.estimate == pytest.approx(1.0, abs=1e-9)


def test_clustering_on_the_running_variable_gives_a_larger_or_equal_se_than_none() -> None:
    """Clustering on the running variable gives a larger or equal se than none."""
    rng = np.random.default_rng(3)
    ages = np.repeat(np.arange(-10.0, 11.0), 30)
    shock = np.repeat(rng.normal(size=21), 30)
    y = 1.0 + 0.2 * ages + shock + rng.normal(size=ages.size) * 0.1
    plain = rdd.local_linear(ages, y, cutoff=0.0, bandwidth=8.0)
    clustered = rdd.local_linear(ages, y, cutoff=0.0, bandwidth=8.0, cluster=ages)
    assert clustered.se > plain.se


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"bandwidth": 0.0}, "bandwidth"),
        ({"bandwidth": -1.0}, "bandwidth"),
        ({"kernel": "gaussian"}, "kernel"),
        ({"bandwidth": 0.4}, "at least"),
    ],
)
def test_invalid_specifications_raise(kwargs: dict, message: str) -> None:
    """Invalid specifications raise."""
    x = np.arange(-5.0, 6.0)
    y = x.copy()
    args = {"cutoff": 0.0, "bandwidth": 3.0}
    args.update(kwargs)
    with pytest.raises(ValueError, match=message):
        rdd.local_linear(x, y, **args)


def test_non_finite_and_mismatched_inputs_are_refused() -> None:
    """Non finite and mismatched inputs are refused."""
    x = np.arange(-5.0, 6.0)
    with pytest.raises(ValueError, match="same length"):
        rdd.local_linear(x, x[:-1], cutoff=0.0, bandwidth=3.0)
    bad = x.copy()
    bad[2] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        rdd.local_linear(x, bad, cutoff=0.0, bandwidth=3.0)
    with pytest.raises(ValueError, match="weights"):
        rdd.local_linear(x, x, cutoff=0.0, bandwidth=3.0, weights=-np.ones_like(x))


def test_bandwidth_grid_returns_one_fit_per_bandwidth_in_order() -> None:
    """Bandwidth grid returns one fit per bandwidth in order."""
    x = np.arange(-12.0, 13.0)
    y = 1.0 + 2.0 * (x >= 0)
    grid = rdd.bandwidth_grid(x, y, cutoff=0.0, bandwidths=[3.0, 6.0, 10.0])
    assert [g.bandwidth for g in grid] == [3.0, 6.0, 10.0]
    assert all(g.estimate == pytest.approx(2.0, abs=1e-9) for g in grid)


def test_placebo_cutoffs_use_only_one_side_of_the_true_cutoff() -> None:
    """A real step at 0 must not leak into a placebo at -4 or +4."""
    x = np.arange(-12.0, 13.0)
    y = 1.0 + 0.3 * x + 5.0 * (x >= 0)
    results = rdd.placebo_cutoffs(x, y, true_cutoff=0.0, placebo_cutoffs=[-4.0, 4.0], bandwidth=3.0)
    assert [r.cutoff for r in results] == [-4.0, 4.0]
    for r in results:
        assert r.fit.estimate == pytest.approx(0.0, abs=1e-9)


def test_placebo_on_the_wrong_side_of_the_cutoff_is_refused() -> None:
    """Placebo on the wrong side of the cutoff is refused."""
    x = np.arange(-12.0, 13.0)
    with pytest.raises(ValueError, match="not in"):
        rdd.placebo_cutoffs(x, x, true_cutoff=0.0, placebo_cutoffs=[-40.0], bandwidth=3.0)


def test_density_test_by_hand_and_for_a_balanced_window() -> None:
    """Window (-3, 3): 6 left, 6 right of 12 -> p = 1.0; 11 vs 1 rejects."""
    even = np.array([-2.5, -1.5, -0.5, -2.0, -1.0, -0.2, 0.5, 1.5, 2.5, 0.2, 1.0, 2.0])
    balanced = rdd.density_test(even, cutoff=0.0, bandwidth=3.0)
    assert (balanced.n_left, balanced.n_right) == (6, 6)
    assert balanced.p_value == pytest.approx(1.0, abs=1e-12)
    lopsided = np.array([-2.9] * 11 + [0.1])
    assert rdd.density_test(lopsided, cutoff=0.0, bandwidth=3.0).p_value < 0.01


def test_density_test_needs_observations_in_the_window() -> None:
    """Density test needs observations in the window."""
    with pytest.raises(ValueError, match="no observations"):
        rdd.density_test(np.array([10.0, 11.0]), cutoff=0.0, bandwidth=1.0)


@settings(max_examples=30, deadline=None)
@given(
    a=st.floats(-20, 20, allow_nan=False),
    b=st.floats(-3, 3, allow_nan=False),
    tau=st.floats(-10, 10, allow_nan=False),
    shift=st.floats(-100, 100, allow_nan=False),
)
def test_property_exact_for_any_piecewise_linear_truth_and_translation_invariant(
    a: float, b: float, tau: float, shift: float
) -> None:
    """Property exact for any piecewise linear truth and translation invariant."""
    x = np.arange(-9.0, 10.0)
    y = a + b * x + tau * (x >= 0)
    base = rdd.local_linear(x, y, cutoff=0.0, bandwidth=6.0)
    assert base.estimate == pytest.approx(tau, abs=1e-7)
    moved = rdd.local_linear(x + shift, y, cutoff=shift, bandwidth=6.0)
    assert moved.estimate == pytest.approx(base.estimate, abs=1e-6)


def test_remaining_input_guards() -> None:
    """Weight, cluster and cutoff-identity mismatches raise rather than coerce."""
    x = np.arange(-5.0, 6.0)
    with pytest.raises(ValueError, match="weights must have the same length"):
        rdd.local_linear(x, x, cutoff=0.0, bandwidth=3.0, weights=np.ones(3))
    with pytest.raises(ValueError, match="cluster must have the same length"):
        rdd.local_linear(x, x, cutoff=0.0, bandwidth=3.0, cluster=np.ones(3))
    with pytest.raises(ValueError, match="true cutoff"):
        rdd.placebo_cutoffs(x, x, true_cutoff=0.0, placebo_cutoffs=[0.0], bandwidth=3.0)
    with pytest.raises(ValueError, match="non-finite"):
        rdd.density_test(np.array([1.0, np.nan]), cutoff=0.0, bandwidth=3.0)


def test_placebo_weights_and_clusters_follow_their_observations() -> None:
    """Weights and clusters are restricted to the placebo's side, with x and y.

    Before this was fixed, a weighted placebo raised "weights must have the same length as x"
    because only x and y were narrowed to the side of the cutoff.
    """
    x = np.arange(-10.0, 11.0)
    y = 0.5 * x + (x >= 0) * 3.0
    w = np.linspace(1.0, 4.0, x.size)
    cl = np.arange(x.size)
    got = rdd.placebo_cutoffs(
        x,
        y,
        true_cutoff=0.0,
        placebo_cutoffs=[-4.5, 4.5],
        bandwidth=3.0,
        kernel="triangular",
        weights=w,
        cluster=cl,
    )
    for placebo in got:
        side = x < 0.0 if placebo.cutoff < 0.0 else x >= 0.0
        expect = rdd.local_linear(
            x[side],
            y[side],
            cutoff=placebo.cutoff,
            bandwidth=3.0,
            kernel="triangular",
            weights=w[side],
            cluster=cl[side],
        )
        assert placebo.fit.estimate == pytest.approx(expect.estimate, abs=1e-12)
        assert placebo.fit.se == pytest.approx(expect.se, abs=1e-12)
    with pytest.raises(ValueError, match="weights must have the same length"):
        rdd.placebo_cutoffs(
            x, y, true_cutoff=0.0, placebo_cutoffs=[-4.5], bandwidth=3.0, weights=np.ones(3)
        )


def _ages() -> tuple[np.ndarray, np.ndarray]:
    """Whole-year running variable around 64.5 with a weight per cell."""
    x = np.arange(60.0, 70.0)
    return x, np.linspace(1.0, 2.0, x.size)


def test_the_estimator_weights_reproduce_the_jump_and_satisfy_the_moment_conditions() -> None:
    """Sum of w y equals the fit; each side sums to -1 and +1 and is orthogonal to distance."""
    x, pop = _ages()
    y = (
        3.0
        + 0.2 * (x - 64.5)
        + 5.0 * (x >= 65)
        + np.array([0.3, -0.2, 0.1, 0.4, -0.3, 0.2, 0.0, -0.1, 0.3, -0.4])
    )
    w, dist = rdd.estimator_weights(x, cutoff=64.5, bandwidth=4.5, weights=pop)
    fit = rdd.local_linear(x, y, cutoff=64.5, bandwidth=4.5, weights=pop)
    assert float(w @ y) == pytest.approx(fit.estimate, abs=1e-10)
    right = dist > 0
    assert w[right].sum() == pytest.approx(1.0) and w[~right].sum() == pytest.approx(-1.0)
    assert float(w[right] @ dist[right]) == pytest.approx(0.0, abs=1e-10)
    assert float(w[~right] @ dist[~right]) == pytest.approx(0.0, abs=1e-10)


def test_the_worst_case_curvature_attains_the_bias_bound_exactly() -> None:
    """A baseline of sign(w) M/2 d^2 over a straight line has bias M/2 sum |w| d^2: the bound."""
    x, pop = _ages()
    smooth = 0.2
    w, dist = rdd.estimator_weights(x, cutoff=64.5, bandwidth=4.5, weights=pop)
    y = 7.0 - 0.4 * dist + 0.5 * smooth * np.sign(w) * dist**2
    jump = float(w @ y)
    out = rdd.honest_interval(
        x, y + 5.0 * (x >= 65), cutoff=64.5, bandwidth=4.5, smoothness=smooth, weights=pop
    )
    assert out.bias_bound == pytest.approx(0.5 * smooth * np.sum(np.abs(w) * dist**2))
    assert jump == pytest.approx(
        out.bias_bound
    )  # the jump of the curved baseline alone, no true jump


def test_the_honest_interval_widens_with_smoothness_and_reduces_to_the_usual_one_at_zero() -> None:
    """M = 0 gives estimate +- 1.96 se; larger M gives a wider interval."""
    x, pop = _ages()
    y = 3.0 + 5.0 * (x >= 65) + np.array([0.3, -0.2, 0.1, 0.4, -0.3, 0.2, 0.0, -0.1, 0.3, -0.4])
    base = rdd.honest_interval(x, y, cutoff=64.5, bandwidth=4.5, smoothness=0.0, weights=pop)
    assert base.critical_value == pytest.approx(1.959964, abs=1e-5)
    assert base.upper - base.lower == pytest.approx(2 * 1.959964 * base.se, rel=1e-5)
    wide = [
        rdd.honest_interval(x, y, cutoff=64.5, bandwidth=4.5, smoothness=m, weights=pop)
        for m in (0.05, 0.2, 1.0)
    ]
    assert all(a.upper - a.lower < b.upper - b.lower for a, b in zip([base, *wide], wide))
    direct = np.sqrt(stats.ncx2.ppf(0.95, 1, (wide[1].bias_bound / wide[1].se) ** 2))
    assert wide[1].critical_value == pytest.approx(direct)


def test_the_honest_interval_input_guards() -> None:
    """Negative smoothness and an alpha outside (0, 1) raise."""
    x, _ = _ages()
    y = np.arange(10.0)
    with pytest.raises(ValueError, match="smoothness"):
        rdd.honest_interval(x, y, cutoff=64.5, bandwidth=4.5, smoothness=-1.0)
    with pytest.raises(ValueError, match="alpha"):
        rdd.honest_interval(x, y, cutoff=64.5, bandwidth=4.5, smoothness=0.1, alpha=1.5)
