"""Known-answer tests: frequency weights, stratification and Rosenbaum bounds.

A row that stands for ``n`` people must behave as ``n`` copies of itself, because that is how
PUMS cells enter the matching estimators. Each frequency-weighted result is checked against the
same computation on the expanded rows, and against figures worked by hand.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from krl_tutorials_data.methods import matching


def expand(frame: dict[str, np.ndarray], freq: np.ndarray) -> dict[str, np.ndarray]:
    """Repeat each row ``freq`` times."""
    return {k: np.repeat(v, freq.astype(int), axis=0) for k, v in frame.items()}


def cells(seed: int, n_rows: int = 12) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Random rows with both treatment groups, integer frequencies and a binary outcome."""
    rng = np.random.default_rng(seed)
    d = np.r_[np.ones(n_rows // 2), np.zeros(n_rows - n_rows // 2)]
    rng.shuffle(d)
    x = rng.normal(size=(n_rows, 2))
    p = np.clip(0.2 + 0.2 * x[:, 0] + 0.2 * d, 0.05, 0.95)
    y = (rng.random(n_rows) < p).astype(float)
    freq = rng.integers(1, 8, n_rows).astype(float)
    return {"x": x, "d": d, "y": y}, freq


def test_saturated_cells_with_frequencies_recover_the_cell_shares_by_hand() -> None:
    """Cell 0: 30 treated, 70 control; cell 1: 60 treated, 40 control, one binary covariate.

    The saturated logit returns logit(0.3) for the intercept and logit(0.6) - logit(0.3) for
    the slope, from four rows of counts and no person-level data.
    """
    x = np.array([0.0, 0.0, 1.0, 1.0])
    d = np.array([1.0, 0.0, 1.0, 0.0])
    fit = matching.logit_propensity(x, d, frequency=[30, 70, 60, 40])

    def logit(p: float) -> float:
        """Log-odds of a probability."""
        return float(np.log(p / (1 - p)))

    assert fit.coef[0] == pytest.approx(logit(0.3), abs=1e-8)
    assert fit.coef[1] == pytest.approx(logit(0.6) - logit(0.3), abs=1e-8)
    assert fit.propensity[[0, 1]] == pytest.approx([0.3, 0.3], abs=1e-8)
    assert fit.propensity[[2, 3]] == pytest.approx([0.6, 0.6], abs=1e-8)


@settings(max_examples=25, deadline=None)
@given(seed=st.integers(0, 10_000))
def test_property_a_frequency_weighted_logit_equals_the_fit_on_expanded_rows(seed: int) -> None:
    """The coefficients agree to numerical precision whatever the counts.

    Random small data can be separable; then the expanded fit raises and the frequency-weighted
    fit must raise too, which is the same equivalence.
    """
    frame, freq = cells(seed)
    big = expand(frame, freq)
    try:
        plain = matching.logit_propensity(big["x"], big["d"])
    except RuntimeError:
        with pytest.raises(RuntimeError):
            matching.logit_propensity(frame["x"], frame["d"], frequency=freq)
        return
    weighted = matching.logit_propensity(frame["x"], frame["d"], frequency=freq)
    np.testing.assert_allclose(weighted.coef, plain.coef, atol=1e-6)


def test_a_zero_frequency_row_has_no_influence_and_no_frequency_changes_nothing() -> None:
    """Dropping a zero-count row leaves the fit alone; omitting frequency is all ones."""
    frame, freq = cells(3)
    freq[0] = 0.0
    kept = slice(1, None)
    with_zero = matching.logit_propensity(frame["x"], frame["d"], frequency=freq)
    without = matching.logit_propensity(frame["x"][kept], frame["d"][kept], frequency=freq[kept])
    np.testing.assert_allclose(with_zero.coef, without.coef, atol=1e-8)
    base = matching.logit_propensity(frame["x"], frame["d"])
    ones = matching.logit_propensity(frame["x"], frame["d"], frequency=np.ones(frame["d"].size))
    np.testing.assert_allclose(base.coef, ones.coef)


@pytest.mark.parametrize(
    ("frequency", "message"),
    [
        (np.array([1.0, -1.0, 1.0, 1.0]), "non-negative"),
        (np.array([1.0, 2.0]), "same length"),
        (np.array([1.0, np.nan, 1.0, 1.0]), "same length"),
        (np.array([1.0, 1.0, 0.0, 0.0]), "no weight"),
    ],
)
def test_invalid_frequencies_raise(frequency: np.ndarray, message: str) -> None:
    """Negative, mis-sized, non-finite or group-erasing frequencies are refused."""
    x, d = np.array([0.0, 1.0, 0.0, 1.0]), np.array([1.0, 1.0, 0.0, 0.0])
    with pytest.raises(ValueError, match=message):
        matching.logit_propensity(x, d, frequency=frequency)


@pytest.mark.parametrize("estimand", ["ate", "att"])
def test_ipw_with_frequencies_equals_ipw_on_expanded_rows(estimand: str) -> None:
    """Estimate, standard error and counts all match, including with trimming."""
    frame, freq = cells(11, n_rows=16)
    score = matching.logit_propensity(frame["x"], frame["d"], frequency=freq).propensity
    kwargs = {"estimand": estimand, "trim": (0.15, 0.85)}
    cell_fit = matching.ipw_effect(frame["y"], frame["d"], score, frequency=freq, **kwargs)
    big = expand({**frame, "score": score}, freq)
    row_fit = matching.ipw_effect(big["y"], big["d"], big["score"], **kwargs)
    assert cell_fit.estimate == pytest.approx(row_fit.estimate, abs=1e-10)
    assert cell_fit.se == pytest.approx(row_fit.se, abs=1e-10)
    assert (cell_fit.n_used, cell_fit.n_trimmed) == (row_fit.n_used, row_fit.n_trimmed)


def test_smd_and_balance_table_with_frequencies_equal_the_expanded_rows() -> None:
    """Means and variances are taken as if each row were repeated; weights still adjust means."""
    frame, freq = cells(5, n_rows=14)
    x = frame["x"][:, 0]
    assert matching.standardized_mean_difference(x, frame["d"], frequency=freq) == pytest.approx(
        matching.standardized_mean_difference(
            *(expand({"x": x, "d": frame["d"]}, freq)[k] for k in ("x", "d"))
        )
    )
    rows = matching.balance_table(frame["x"], frame["d"], names=["a", "b"], frequency=freq)
    big = expand(frame, freq)
    expected = matching.balance_table(big["x"], big["d"], names=["a", "b"])
    assert [r.smd for r in rows] == pytest.approx([r.smd for r in expected])
    adjust = np.linspace(1.0, 2.0, x.size)
    got = matching.standardized_mean_difference(x, frame["d"], weights=adjust, frequency=freq)
    big_w = expand({"x": x, "d": frame["d"], "w": adjust}, freq)
    want = matching.standardized_mean_difference(big_w["x"], big_w["d"], weights=big_w["w"])
    assert got == pytest.approx(want)


def test_stratified_effect_by_hand() -> None:
    """Stratum 1: 6/10 against 4/20 = +0.4; stratum 2: 9/30 against 5/10 = -0.2; one unmatched.

    ATT = (10 * 0.4 + 30 * -0.2) / 40 = -0.05; the third stratum has no control and is dropped,
    so 40 of 45 treated units are used.
    """
    result = matching.stratified_effect([6, 9, 3], [10, 30, 5], [4, 5, 0], [20, 10, 0])
    assert result.estimate == pytest.approx(-0.05)
    assert (result.n_strata_used, result.n_strata_dropped) == (2, 1)
    assert result.share_treated_used == pytest.approx(40 / 45)


def test_stratified_effect_guards() -> None:
    """Shape, impossible counts and no comparable stratum raise."""
    with pytest.raises(ValueError, match="equal length"):
        matching.stratified_effect([1], [2], [1, 1], [2, 2])
    with pytest.raises(ValueError, match="between 0 and the group size"):
        matching.stratified_effect([3], [2], [1], [2])
    with pytest.raises(ValueError, match="no stratum"):
        matching.stratified_effect([1], [2], [0], [0])


def test_rosenbaum_with_no_hidden_bias_has_the_hypergeometric_moments() -> None:
    """Gamma = 1: mean n1 m / N and variance n1 n0 m (N - m) / (N^2 (N - 1)) in every stratum."""
    e1, n1, e0, n0 = (
        np.array([3, 6, 2]),
        np.array([8, 10, 5]),
        np.array([2, 1, 3]),
        np.array([9, 12, 7]),
    )
    out = matching.rosenbaum_bounds(e1, n1, e0, n0, gamma=1.0)
    m, n = e1 + e0, n1 + n0
    assert out.expected_upper == pytest.approx(np.sum(n1 * m / n))
    assert out.variance_upper == pytest.approx(np.sum(n1 * n0 * m * (n - m) / (n**2 * (n - 1))))
    assert (out.expected_upper, out.variance_upper) == pytest.approx(
        (out.expected_lower, out.variance_lower)
    )
    assert out.statistic == 11.0


def test_rosenbaum_single_table_with_gamma_two_by_hand() -> None:
    """n1 = n0 = 2, two events: P(k) = 1, 8, 4 over 13 at odds ratio 2; mean 16/13, var 56/169."""
    out = matching.rosenbaum_bounds([2], [2], [0], [2], gamma=2.0)
    assert out.expected_upper == pytest.approx(16 / 13)
    assert out.variance_upper == pytest.approx(56 / 169)
    # by symmetry the lower mean is 2 - 16/13 (odds ratio 1/2 mirrors odds ratio 2)
    assert out.expected_lower == pytest.approx(2 - 16 / 13)


def test_rosenbaum_p_values_move_the_right_way_with_gamma() -> None:
    """The upper bound rises and the lower bound falls as hidden bias is allowed to grow."""
    e1, n1, e0, n0 = np.full(30, 7), np.full(30, 10), np.full(30, 4), np.full(30, 10)
    ps = [matching.rosenbaum_bounds(e1, n1, e0, n0, gamma=g) for g in (1.0, 1.5, 2.0, 3.0)]
    assert all(a.p_upper < b.p_upper for a, b in zip(ps, ps[1:]))
    assert all(a.p_lower > b.p_lower for a, b in zip(ps, ps[1:]))
    assert ps[0].p_upper < 1e-6


def test_the_normal_approximation_tracks_the_exact_distribution() -> (
    None
):  # pylint: disable=too-many-locals
    """Twelve small strata: the normal p-value is within 0.03 of the exact convolution."""
    rng = np.random.default_rng(2)
    n1, n0 = np.full(12, 6), np.full(12, 8)
    events = rng.integers(3, 9, 12)
    e1 = np.minimum(rng.integers(1, 5, 12), events)
    e0 = events - e1
    gamma = 1.5
    pmf = np.array([1.0])
    for a, b, m in zip(n1, n0, events):
        k = np.arange(max(0, m - b), min(a, m) + 1)
        w = np.array(
            [math.comb(int(a), int(j)) * math.comb(int(b), int(m - j)) * gamma**j for j in k]
        )
        stratum = np.zeros(k.max() + 1)
        stratum[k] = w / w.sum()
        pmf = np.convolve(pmf, stratum)
    exact = float(pmf[int(e1.sum()) :].sum())
    approx = matching.rosenbaum_bounds(e1, n1, e0, n0, gamma=gamma).p_upper
    assert abs(exact - approx) < 0.03


def test_critical_gamma_is_where_the_worst_case_p_crosses_alpha() -> None:
    """Bisection returns a Gamma at which the bound is at alpha, and one just below stays under."""
    e1, n1, e0, n0 = np.full(40, 6), np.full(40, 10), np.full(40, 4), np.full(40, 10)
    g = matching.rosenbaum_critical_gamma(e1, n1, e0, n0, alpha=0.025, tol=1e-6)
    assert 1.0 < g < 100.0
    assert matching.rosenbaum_bounds(e1, n1, e0, n0, gamma=g * 1.001).p_upper > 0.025
    assert matching.rosenbaum_bounds(e1, n1, e0, n0, gamma=g * 0.999).p_upper < 0.025


def test_critical_gamma_edge_cases_and_negative_direction() -> None:
    """No effect gives 1.0, a huge one infinity; a negative effect uses the lower bound."""
    flat = matching.rosenbaum_critical_gamma(
        np.full(20, 5), np.full(20, 10), np.full(20, 5), np.full(20, 10)
    )
    assert flat == 1.0
    huge = matching.rosenbaum_critical_gamma(
        np.full(60, 9), np.full(60, 10), np.full(60, 1), np.full(60, 10), gamma_max=1.5
    )
    assert huge == float("inf")
    negative = matching.rosenbaum_critical_gamma(
        np.full(40, 4), np.full(40, 10), np.full(40, 6), np.full(40, 10)
    )
    mirror = matching.rosenbaum_critical_gamma(
        np.full(40, 6), np.full(40, 10), np.full(40, 4), np.full(40, 10)
    )
    assert negative == pytest.approx(mirror, rel=0.05)


@pytest.mark.parametrize(
    ("args", "kwargs", "message"),
    [
        (([1], [2], [1], [2]), {"gamma": 0.5}, "at least 1"),
        (([1], [2], [1, 1], [2, 2]), {"gamma": 1.0}, "equal length"),
        (([1.5], [2], [1], [2]), {"gamma": 1.0}, "whole counts"),
        (([3], [2], [1], [2]), {"gamma": 1.0}, "between 0 and the group size"),
        (([0], [2], [0], [2]), {"gamma": 1.0}, "mix of outcomes"),
    ],
)
def test_rosenbaum_guards(args: tuple, kwargs: dict, message: str) -> None:
    """Bad Gamma, shapes, counts and strata with nothing to compare raise."""
    with pytest.raises(ValueError, match=message):
        matching.rosenbaum_bounds(*args, **kwargs)


def test_critical_gamma_rejects_a_silly_alpha() -> None:
    """Alpha outside (0, 0.5) is refused."""
    with pytest.raises(ValueError, match="alpha"):
        matching.rosenbaum_critical_gamma([1], [2], [1], [2], alpha=0.7)
