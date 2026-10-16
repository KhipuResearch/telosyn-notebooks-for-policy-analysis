"""Known-answer tests for ``krl_tutorials_data.methods.meta``.

Hand arithmetic for the three-study case y = (0, 2, 4), unit variances:
fixed mean 2; Q = 4 + 0 + 4 = 8 on 2 df; C = sum(w) - sum(w^2)/sum(w) = 3 - 1 = 2;
tau^2 = (Q - df)/C = 3; random weights 1/(1+3) = 1/4, so the random mean is 2 and
its variance is 1/(3/4) = 4/3; I^2 = (Q - df)/Q = 0.75; P(chi2_2 > 8) = exp(-4).

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

from krl_tutorials_data.methods import meta

Y = np.array([0.0, 2.0, 4.0])
SE = np.array([1.0, 1.0, 1.0])


def test_dersimonian_laird_by_hand() -> None:
    """Dersimonian laird by hand."""
    r = meta.pool(Y, SE)
    assert r.fixed_effect == pytest.approx(2.0, abs=1e-12)
    assert r.fixed_se == pytest.approx(math.sqrt(1 / 3), abs=1e-12)
    assert r.q == pytest.approx(8.0, abs=1e-12)
    assert r.df == 2
    assert r.tau2 == pytest.approx(3.0, abs=1e-12)
    assert r.i2 == pytest.approx(0.75, abs=1e-12)
    assert r.random_effect == pytest.approx(2.0, abs=1e-12)
    assert r.random_se == pytest.approx(math.sqrt(4 / 3), abs=1e-12)
    assert r.p_heterogeneity == pytest.approx(math.exp(-4.0), abs=1e-12)
    np.testing.assert_allclose(r.weights_random, [0.25, 0.25, 0.25], atol=1e-12)


def test_homogeneous_studies_have_zero_tau2_and_equal_fixed_and_random() -> None:
    """Homogeneous studies have zero tau2 and equal fixed and random."""
    r = meta.pool([1.0, 1.1, 0.9], [1.0, 1.0, 1.0])
    assert r.tau2 == 0.0 and r.i2 == 0.0
    assert r.random_effect == pytest.approx(r.fixed_effect, abs=1e-12)
    assert r.random_se == pytest.approx(r.fixed_se, abs=1e-12)


def test_agrees_with_statsmodels_combine_effects() -> None:
    """Agrees with statsmodels combine effects."""
    mm = pytest.importorskip("statsmodels.stats.meta_analysis")
    rng = np.random.default_rng(12)
    se = rng.uniform(0.1, 0.8, size=9)
    y = rng.normal(0.4, 0.5, size=9) + rng.normal(0, se)
    ours = meta.pool(y, se)
    ref = mm.combine_effects(y, se**2, method_re="dl")
    assert ours.tau2 == pytest.approx(ref.tau2, rel=1e-9)
    assert ours.random_effect == pytest.approx(ref.mean_effect_re, rel=1e-9)
    assert ours.random_se == pytest.approx(ref.sd_eff_w_re, rel=1e-9)
    assert ours.fixed_effect == pytest.approx(ref.mean_effect_fe, rel=1e-9)


def test_egger_recovers_an_exact_small_study_intercept() -> None:
    """z = y/se is exactly 1.5 + 0.8 * precision, so the intercept is 1.5 with no error."""
    precision = np.array([1.0, 2.0, 3.0, 5.0, 8.0])
    se = 1.0 / precision
    y = (1.5 + 0.8 * precision) * se
    e = meta.egger_test(y, se)
    assert e.intercept == pytest.approx(1.5, abs=1e-10)
    assert e.slope == pytest.approx(0.8, abs=1e-10)
    assert e.df == 3


def test_egger_agrees_with_ols_on_noisy_data() -> None:
    """Egger agrees with ols on noisy data."""
    sm = pytest.importorskip("statsmodels.api")
    rng = np.random.default_rng(2)
    se = rng.uniform(0.1, 0.9, size=12)
    y = 0.3 + rng.normal(scale=se)
    e = meta.egger_test(y, se)
    fit = sm.OLS(y / se, sm.add_constant(1.0 / se)).fit()
    assert e.intercept == pytest.approx(fit.params[0], rel=1e-9)
    assert e.se == pytest.approx(fit.bse[0], rel=1e-9)
    assert e.p_value == pytest.approx(fit.pvalues[0], rel=1e-9)


def test_leave_one_out_drops_each_study_in_turn() -> None:
    """Leave one out drops each study in turn."""
    loo = meta.leave_one_out(Y, SE)
    assert [r.n_studies for r in loo] == [2, 2, 2]
    assert loo[0].fixed_effect == pytest.approx(3.0)  # drops 0 -> mean(2, 4)
    assert loo[2].fixed_effect == pytest.approx(1.0)  # drops 4 -> mean(0, 2)


@pytest.mark.parametrize(
    ("y", "se", "message"),
    [
        ([1.0], [1.0], "at least two"),
        ([1.0, 2.0], [1.0], "same length"),
        ([1.0, 2.0], [1.0, 0.0], "positive"),
        ([1.0, np.nan], [1.0, 1.0], "non-finite"),
    ],
)
def test_invalid_inputs_raise(y: list, se: list, message: str) -> None:
    """Invalid inputs raise."""
    with pytest.raises(ValueError, match=message):
        meta.pool(y, se)


def test_egger_and_leave_one_out_need_enough_studies() -> None:
    """Egger and leave one out need enough studies."""
    with pytest.raises(ValueError, match="at least three"):
        meta.egger_test([1.0, 2.0], [1.0, 1.0])
    with pytest.raises(ValueError, match="at least three"):
        meta.leave_one_out([1.0, 2.0], [1.0, 1.0])


@settings(max_examples=40, deadline=None)
@given(
    shift=st.floats(-50, 50, allow_nan=False),
    scale=st.floats(0.2, 10, allow_nan=False),
)
def test_property_location_shift_and_scale_equivariance(shift: float, scale: float) -> None:
    """Property location shift and scale equivariance."""
    base = meta.pool(Y, SE)
    moved = meta.pool(Y + shift, SE)
    assert moved.random_effect == pytest.approx(base.random_effect + shift, abs=1e-8)
    assert moved.tau2 == pytest.approx(base.tau2, abs=1e-9)
    scaled = meta.pool(Y * scale, SE * scale)
    assert scaled.random_effect == pytest.approx(base.random_effect * scale, rel=1e-9, abs=1e-9)
    assert scaled.i2 == pytest.approx(base.i2, abs=1e-9)
