"""Known-answer tests for ``krl_tutorials_data.methods.synth``.

The treated unit is built as an exact convex combination of two donors, so the
weights the estimator must return are known before it runs.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from krl_tutorials_data.methods import synth

T0, T, J = 12, 18, 4


def _donors(seed: int = 5, periods: int = T, units: int = J) -> np.ndarray:
    """Non-collinear donor series with distinct trends and noise (fixture randomness)."""
    rng = np.random.default_rng(seed)
    t = np.arange(periods)[:, None]
    return 10 + rng.normal(size=(1, units)) * 3 + t * rng.normal(size=(1, units)) \
        + rng.normal(size=(periods, units))


def test_exact_convex_combination_is_recovered() -> None:
    """Exact convex combination is recovered."""
    donors = _donors()
    treated = 0.3 * donors[:, 0] + 0.7 * donors[:, 1]
    fit = synth.synthetic_control(treated, donors, n_pre=T0)
    np.testing.assert_allclose(fit.weights, [0.3, 0.7, 0.0, 0.0], atol=1e-5)
    assert fit.weights.sum() == pytest.approx(1.0, abs=1e-9)
    assert (fit.weights >= -1e-12).all()
    assert fit.pre_rmspe == pytest.approx(0.0, abs=1e-5)


def test_a_known_post_period_effect_is_the_gap() -> None:
    """A known post period effect is the gap."""
    donors = _donors()
    treated = 0.3 * donors[:, 0] + 0.7 * donors[:, 1]
    treated[T0:] += 5.0
    fit = synth.synthetic_control(treated, donors, n_pre=T0)
    np.testing.assert_allclose(fit.gap[T0:], 5.0, atol=1e-4)
    assert fit.post_rmspe == pytest.approx(5.0, abs=1e-4)
    assert fit.rmspe_ratio > 1e3


def test_ratio_is_infinite_when_the_pre_fit_is_exact_and_the_post_gap_is_not() -> None:
    """Ratio is infinite when the pre fit is exact and the post gap is not."""
    assert synth.rmspe_ratio(0.0, 2.0) == float("inf")
    assert synth.rmspe_ratio(0.0, 0.0) == 1.0
    assert synth.rmspe_ratio(2.0, 6.0) == pytest.approx(3.0)


def test_in_space_placebo_ranks_a_real_effect_first() -> None:
    """In space placebo ranks a real effect first."""
    donors = _donors(units=9)
    treated = 0.5 * donors[:, 0] + 0.5 * donors[:, 1] + 0.05 * _donors(seed=99, units=1)[:, 0]
    treated[T0:] += 6.0
    result = synth.placebo_in_space(treated, donors, n_pre=T0)
    assert result.rank == 1
    assert result.p_value == pytest.approx(1.0 / 10.0)
    assert result.donor_ratios.shape == (9,)


def test_in_space_placebo_with_no_effect_does_not_rank_the_treated_unit_special() -> None:
    """In space placebo with no effect does not rank the treated unit special."""
    donors = _donors(units=9)
    treated = 0.5 * donors[:, 0] + 0.5 * donors[:, 1] + 0.3 * _donors(seed=7, units=1)[:, 0]
    result = synth.placebo_in_space(treated, donors, n_pre=T0)
    assert result.p_value > 0.1


def test_pre_fit_filter_drops_poorly_fitting_placebos() -> None:
    """Pre fit filter drops poorly fitting placebos."""
    donors = _donors(units=9)
    donors[:, 8] += np.linspace(0, 80, T)  # an outlier no convex combination can match
    treated = 0.5 * donors[:, 0] + 0.5 * donors[:, 1]
    full = synth.placebo_in_space(treated, donors, n_pre=T0)
    trimmed = synth.placebo_in_space(treated, donors, n_pre=T0, max_pre_ratio=5.0)
    assert trimmed.n_placebos <= full.n_placebos
    assert full.n_placebos == 9


def test_in_time_placebo_finds_no_effect_where_there_is_none() -> None:
    """In time placebo finds no effect where there is none."""
    donors = _donors()
    treated = 0.3 * donors[:, 0] + 0.7 * donors[:, 1]
    treated[T0:] += 5.0
    fit = synth.placebo_in_time(treated, donors, n_pre=T0, placebo_pre=8)
    np.testing.assert_allclose(fit.gap[8:T0], 0.0, atol=1e-4)
    assert fit.post_rmspe == pytest.approx(0.0, abs=1e-4)


def test_covariates_enter_the_fit_and_do_not_break_an_exact_solution() -> None:
    """Covariates enter the fit and do not break an exact solution."""
    donors = _donors()
    treated = 0.3 * donors[:, 0] + 0.7 * donors[:, 1]
    cov_donors = np.array([[1.0, 2.0, 4.0, 8.0], [5.0, 3.0, 9.0, 1.0]])
    cov_treated = cov_donors @ np.array([0.3, 0.7, 0.0, 0.0])
    fit = synth.synthetic_control(
        treated, donors, n_pre=T0, covariates_treated=cov_treated,
        covariates_donors=cov_donors, covariate_weight=2.0,
    )
    np.testing.assert_allclose(fit.weights, [0.3, 0.7, 0.0, 0.0], atol=1e-4)


def test_fit_weights_hand_case_two_donors_one_period() -> None:
    """Treated 5 between donors 4 and 8: any weight with 4a + 8(1-a) = 5 -> a = 0.75."""
    w, objective = synth.fit_weights(np.array([5.0]), np.array([[4.0, 8.0]]))
    np.testing.assert_allclose(w, [0.75, 0.25], atol=1e-6)
    assert objective == pytest.approx(0.0, abs=1e-8)


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: synth.synthetic_control(np.ones(5), np.ones((6, 2)), n_pre=3), "same number"),
        (lambda: synth.synthetic_control(np.ones(5), np.ones((5, 2)), n_pre=1), "n_pre"),
        (lambda: synth.synthetic_control(np.ones(5), np.ones((5, 2)), n_pre=5), "n_pre"),
        (lambda: synth.synthetic_control(np.ones(5), np.ones((5, 0)), n_pre=3), "donor"),
        (lambda: synth.synthetic_control(
            np.array([1.0, np.nan, 1.0, 1.0, 1.0]), np.ones((5, 2)), n_pre=3), "non-finite"),
        (lambda: synth.placebo_in_space(np.ones(6), np.ones((6, 1)), n_pre=3), "at least two"),
        (lambda: synth.placebo_in_time(
            np.ones(6), np.ones((6, 2)), n_pre=3, placebo_pre=3), "placebo_pre"),
    ],
)
def test_invalid_inputs_raise(call, message: str) -> None:
    """Invalid inputs raise."""
    with pytest.raises(ValueError, match=message):
        call()


@settings(max_examples=25, deadline=None)
@given(seed=st.integers(0, 10_000), n_units=st.integers(2, 6))
def test_property_weights_are_a_distribution_and_fit_no_worse_than_uniform(
    seed: int, n_units: int
) -> None:
    """Property weights are a distribution and fit no worse than uniform."""
    donors = _donors(seed=seed, units=n_units)
    rng = np.random.default_rng(seed + 1)
    treated = donors @ rng.dirichlet(np.ones(n_units)) + rng.normal(scale=0.5, size=T)
    fit = synth.synthetic_control(treated, donors, n_pre=T0)
    assert fit.weights.sum() == pytest.approx(1.0, abs=1e-7)
    assert (fit.weights >= -1e-9).all()
    uniform_rmspe = float(
        np.sqrt(np.mean((treated[:T0] - donors[:T0].mean(axis=1)) ** 2))
    )
    assert fit.pre_rmspe <= uniform_rmspe + 1e-6


def test_fit_weights_input_guards() -> None:
    """Shape and sign violations raise instead of being coerced."""
    with pytest.raises(ValueError, match="2-dimensional"):
        synth.fit_weights(np.ones(3), np.ones(3))
    with pytest.raises(ValueError, match="x_donors must be"):
        synth.fit_weights(np.ones(3), np.ones((4, 2)))
    with pytest.raises(ValueError, match="v must be"):
        synth.fit_weights(np.ones(3), np.ones((3, 2)), v=-np.ones(3))


def test_covariate_arguments_must_come_as_a_pair_and_match() -> None:
    """Half a covariate specification, or one that misses the donors, is an error."""
    y, d = np.ones(6), np.ones((6, 2))
    with pytest.raises(ValueError, match="together"):
        synth.synthetic_control(y, d, n_pre=4, covariates_treated=np.ones(2))
    with pytest.raises(ValueError, match="matching the donors"):
        synth.synthetic_control(
            y, d, n_pre=4, covariates_treated=np.ones(2), covariates_donors=np.ones((2, 5))
        )


def test_a_solution_that_fails_first_order_conditions_is_never_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If no start satisfies the KKT check the function raises, whatever the solver says."""
    monkeypatch.setattr(synth, "_kkt_gap", lambda w, g: float("inf"))
    with pytest.raises(RuntimeError, match="first-order optimality"):
        synth.fit_weights(np.array([5.0]), np.array([[4.0, 8.0]]))


def test_the_second_start_is_used_when_the_first_fails_the_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first candidate is rejected, the second is accepted and returned."""
    real = synth._kkt_gap  # pylint: disable=protected-access
    calls = {"n": 0}

    def flaky(w: np.ndarray, g: np.ndarray) -> float:
        """Reject the first candidate only."""
        calls["n"] += 1
        return float("inf") if calls["n"] == 1 else real(w, g)

    monkeypatch.setattr(synth, "_kkt_gap", flaky)
    w, _ = synth.fit_weights(np.array([5.0]), np.array([[4.0, 8.0]]))
    assert calls["n"] == 2
    np.testing.assert_allclose(w, [0.75, 0.25], atol=1e-5)
