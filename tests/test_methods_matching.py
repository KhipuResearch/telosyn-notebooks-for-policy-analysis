"""Known-answer tests for ``krl_tutorials_data.methods.matching``.

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


def test_intercept_only_logit_is_the_log_odds_of_the_sample_share() -> None:
    """Intercept only logit is the log odds of the sample share."""
    d = np.array([1] * 3 + [0] * 7, dtype=float)
    fit = matching.logit_propensity(np.empty((10, 0)), d)
    assert fit.coef[0] == pytest.approx(math.log(3 / 7), abs=1e-8)
    np.testing.assert_allclose(fit.propensity, 0.3, atol=1e-9)


def test_saturated_binary_covariate_logit_matches_cell_proportions() -> None:
    """x=1: 6 treated of 10 -> 0.6.  x=0: 2 treated of 10 -> 0.2."""
    x = np.array([1] * 10 + [0] * 10, dtype=float)[:, None]
    d = np.array([1] * 6 + [0] * 4 + [1] * 2 + [0] * 8, dtype=float)
    fit = matching.logit_propensity(x, d)
    def logit(p: float) -> float:
        """Log-odds."""
        return math.log(p / (1 - p))

    assert fit.coef[0] == pytest.approx(logit(0.2), abs=1e-7)
    assert fit.coef[1] == pytest.approx(logit(0.6) - logit(0.2), abs=1e-7)
    np.testing.assert_allclose(fit.propensity[:10], 0.6, atol=1e-8)


def test_logit_agrees_with_statsmodels() -> None:
    """Logit agrees with statsmodels."""
    sm = pytest.importorskip("statsmodels.api")
    rng = np.random.default_rng(4)
    x = rng.normal(size=(400, 3))
    d = (rng.random(400) < 1 / (1 + np.exp(-(0.3 + x @ [0.8, -0.5, 0.2])))).astype(float)
    ours = matching.logit_propensity(x, d)
    ref = sm.Logit(d, sm.add_constant(x)).fit(disp=0)
    np.testing.assert_allclose(ours.coef, ref.params, atol=1e-6)


def test_perfect_separation_raises_instead_of_returning_a_degenerate_score() -> None:
    """Perfect separation raises instead of returning a degenerate score."""
    x = np.array([[0.0], [1.0], [2.0], [3.0]])
    d = np.array([0.0, 0.0, 1.0, 1.0])
    with pytest.raises(RuntimeError, match="separation"):
        matching.logit_propensity(x, d)


def test_nearest_neighbour_by_hand_with_replacement() -> None:
    """Treated 0.30 -> control 0.28 ; treated 0.80 -> control 0.79."""
    score = np.array([0.30, 0.80, 0.28, 0.50, 0.79, 0.10])
    d = np.array([1, 1, 0, 0, 0, 0])
    m = matching.nearest_neighbour_match(score, d, scale="raw")
    assert m.treated.tolist() == [0, 1]
    assert m.control.tolist() == [2, 4]
    assert m.n_dropped == 0


def test_caliper_drops_a_treated_unit_with_no_close_control() -> None:
    """Caliper drops a treated unit with no close control."""
    score = np.array([0.30, 0.95, 0.28, 0.29])
    d = np.array([1, 1, 0, 0])
    m = matching.nearest_neighbour_match(score, d, caliper=0.05, scale="raw")
    assert m.treated.tolist() == [0]
    assert m.control.tolist() == [3]
    assert m.n_dropped == 1


def test_without_replacement_a_control_is_used_once() -> None:
    """Without replacement a control is used once."""
    score = np.array([0.50, 0.51, 0.49, 0.10])
    d = np.array([1, 1, 0, 0])
    m = matching.nearest_neighbour_match(score, d, replace=False, scale="raw")
    assert len(set(m.control.tolist())) == len(m.control)
    assert sorted(m.control.tolist()) == [2, 3]


def test_att_from_matches_by_hand() -> None:
    """Treated y 10, 8 matched to controls 4, 6 -> (6 + 2) / 2 = 4."""
    y = np.array([10.0, 8.0, 4.0, 6.0])
    d = np.array([1, 1, 0, 0])
    m = matching.MatchResult(
        treated=np.array([0, 1]), control=np.array([2, 3]), distance=np.zeros(2), n_dropped=0
    )
    att = matching.att_from_matches(y, d, m)
    assert att.estimate == pytest.approx(4.0, abs=1e-12)
    assert att.n_pairs == 2
    # pair differences 6 and 2 have sample sd sqrt(8); se = sqrt(8)/sqrt(2) = 2
    assert att.se == pytest.approx(2.0, abs=1e-12)


def test_ipw_ate_and_att_by_hand() -> None:
    """ATE (Hajek): treated mean 9, control mean 5 -> 4, influence-function SE 1.0.
    ATT with control propensities 0.2 and 0.5: weights 0.25 and 1.0 -> (4*.25+6)/1.25 = 5.6."""
    y = np.array([10.0, 8.0, 4.0, 6.0])
    d = np.array([1, 1, 0, 0])
    ate = matching.ipw_effect(y, d, np.array([0.5, 0.5, 0.5, 0.5]), estimand="ate")
    assert ate.estimate == pytest.approx(4.0, abs=1e-12)
    assert ate.se == pytest.approx(1.0, abs=1e-12)
    att = matching.ipw_effect(y, d, np.array([0.5, 0.5, 0.2, 0.5]), estimand="att")
    assert att.estimate == pytest.approx(9.0 - 5.6, abs=1e-12)


def test_constant_propensity_reduces_ipw_to_the_difference_in_means() -> None:
    """Constant propensity reduces ipw to the difference in means."""
    rng = np.random.default_rng(8)
    d = (rng.random(200) < 0.4).astype(float)
    y = rng.normal(size=200) + d
    got = matching.ipw_effect(y, d, np.full(200, 0.4), estimand="ate").estimate
    assert got == pytest.approx(y[d == 1].mean() - y[d == 0].mean(), abs=1e-10)


def test_trimming_reports_how_many_units_were_dropped() -> None:
    """Trimming reports how many units were dropped."""
    y = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    d = np.array([1, 0, 1, 0, 1, 0])
    ps = np.array([0.5, 0.5, 0.005, 0.5, 0.995, 0.5])
    r = matching.ipw_effect(y, d, ps, estimand="ate", trim=(0.01, 0.99))
    assert r.n_trimmed == 2


def test_standardised_mean_difference_by_hand() -> None:
    """Treated 1,2,3 (var 1); control 2,3,4 (var 1): (2 - 3) / sqrt(1) = -1."""
    smd = matching.standardized_mean_difference(
        np.array([1.0, 2.0, 3.0, 2.0, 3.0, 4.0]), np.array([1, 1, 1, 0, 0, 0])
    )
    assert smd == pytest.approx(-1.0, abs=1e-12)


def test_weights_can_restore_balance() -> None:
    """Weights can restore balance."""
    x = np.array([0.0, 1.0, 0.0, 1.0, 1.0, 1.0])
    d = np.array([1, 1, 0, 0, 0, 0])
    before = matching.standardized_mean_difference(x, d)
    w = np.array([1.0, 1.0, 1.0, 1.0, 0.0, 0.0])  # drop the two extra controls
    after = matching.standardized_mean_difference(x, d, weights=w)
    assert abs(after) < abs(before)
    assert after == pytest.approx(0.0, abs=1e-12)


def test_balance_table_has_one_row_per_covariate() -> None:
    """Balance table has one row per covariate."""
    x = np.column_stack([np.arange(6.0), np.ones(6)])
    d = np.array([1, 1, 1, 0, 0, 0])
    rows = matching.balance_table(x, d, names=["a", "const"])
    assert [r.name for r in rows] == ["a", "const"]
    assert rows[1].smd == 0.0


def test_overlap_data_counts_and_common_support() -> None:
    """Overlap data counts and common support."""
    ps = np.array([0.1, 0.2, 0.3, 0.6, 0.7, 0.8])
    d = np.array([0, 0, 1, 0, 1, 1])
    o = matching.overlap_data(ps, d, bins=4)
    assert o.counts_treated.sum() == 3 and o.counts_control.sum() == 3
    # treated scores 0.3, 0.7, 0.8; control 0.1, 0.2, 0.6 -> overlap is [0.3, 0.6]
    assert o.common_support == (0.3, 0.6)
    assert len(o.edges) == 5


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: matching.logit_propensity(np.ones((4, 1)), np.array([0, 1, 2, 0])), "binary"),
        (lambda: matching.logit_propensity(np.ones((4, 1)), np.array([1, 1, 1, 1])), "both"),
        (lambda: matching.nearest_neighbour_match(np.ones(3), np.array([1, 1, 1])), "both"),
        (lambda: matching.nearest_neighbour_match(
            np.array([0.2, 0.3]), np.array([1, 0]), scale="logit", caliper=-1.0), "caliper"),
        (lambda: matching.nearest_neighbour_match(
            np.array([0.2, 0.3]), np.array([1, 0]), scale="other"), "scale"),
        (lambda: matching.ipw_effect(np.ones(2), np.array([1, 0]), np.array([0.5, 1.5])), "(0, 1)"),
        (lambda: matching.ipw_effect(
            np.ones(2), np.array([1, 0]), np.array([0.5, 0.5]), estimand="other"), "estimand"),
        (lambda: matching.standardized_mean_difference(np.ones(3), np.array([1, 1, 1])), "both"),
        (lambda: matching.overlap_data(np.array([0.2, 0.3]), np.array([1, 0]), bins=0), "bins"),
    ],
)
def test_invalid_inputs_raise(call, message: str) -> None:
    """Invalid inputs raise."""
    with pytest.raises(ValueError, match=message):
        call()


@settings(max_examples=30, deadline=None)
@given(shift=st.floats(-20, 20, allow_nan=False), scale=st.floats(0.1, 10, allow_nan=False))
def test_property_smd_is_invariant_to_location_and_positive_scale(
    shift: float, scale: float
) -> None:
    """Property smd is invariant to location and positive scale."""
    x = np.array([1.0, 4.0, 2.0, 7.0, 3.0, 5.0, 9.0, 2.0])
    d = np.array([1, 1, 1, 1, 0, 0, 0, 0])
    base = matching.standardized_mean_difference(x, d)
    assert matching.standardized_mean_difference(x * scale + shift, d) == pytest.approx(
        base, abs=1e-9
    )


def test_remaining_guards_and_the_logit_scale_caliper() -> None:
    """Shape, finiteness and convergence guards; caliper in logit standard deviations."""
    d = np.array([1.0, 0.0, 1.0, 0.0, 0.0, 1.0])
    flat = matching.logit_propensity(np.array([0.1, 0.4, 0.3, 0.9, 0.2, 0.8]), d)
    assert flat.coef.shape == (2,)
    with pytest.raises(ValueError, match="same number of rows"):
        matching.logit_propensity(np.ones((3, 1)), d)
    with pytest.raises(ValueError, match="non-finite"):
        matching.logit_propensity(np.array([np.nan, 1, 2, 3, 4, 5.0]), d)
    with pytest.raises(RuntimeError, match="did not converge"):
        matching.logit_propensity(np.array([0.1, 0.4, 0.3, 0.9, 0.2, 0.8]), d, max_iter=1)
    with pytest.raises(ValueError, match="finite and the same length"):
        matching.nearest_neighbour_match(np.array([0.1, np.nan]), np.array([1, 0]))
    scores = np.array([0.50, 0.99, 0.49, 0.30, 0.52])
    treat = np.array([1, 1, 0, 0, 0])
    tight = matching.nearest_neighbour_match(scores, treat, caliper=0.2, scale="logit")
    assert tight.treated.tolist() == [0]
    assert tight.n_dropped == 1


def test_att_and_ipw_input_guards() -> None:
    """Mismatched lengths, empty matches and a trim that empties a group raise."""
    m = matching.MatchResult(
        treated=np.array([], dtype=np.intp), control=np.array([], dtype=np.intp),
        distance=np.array([]), n_dropped=2,
    )
    with pytest.raises(ValueError, match="no matched pairs"):
        matching.att_from_matches(np.ones(2), np.array([1, 0]), m)
    with pytest.raises(ValueError, match="finite and the same length"):
        matching.att_from_matches(np.ones(3), np.array([1, 0]), m)
    with pytest.raises(ValueError, match="same length"):
        matching.ipw_effect(np.ones(3), np.array([1, 0]), np.array([0.5, 0.5]))
    with pytest.raises(ValueError, match="finite"):
        matching.ipw_effect(np.array([1.0, np.nan]), np.array([1, 0]), np.array([0.5, 0.5]))
    with pytest.raises(ValueError, match="only one treatment group"):
        matching.ipw_effect(
            np.ones(3), np.array([1, 0, 0]), np.array([0.5, 0.01, 0.02]), trim=(0.4, 0.6)
        )


def test_smd_balance_and_overlap_guards() -> None:
    """Weights of the wrong length, bad names and non-finite scores raise."""
    d = np.array([1, 1, 0, 0])
    with pytest.raises(ValueError, match="same length"):
        matching.standardized_mean_difference(np.ones(4), d, weights=np.ones(3))
    with pytest.raises(ValueError, match="one name per column"):
        matching.balance_table(np.ones((4, 2)), d, names=["only"])
    with pytest.raises(ValueError, match="finite and the same length"):
        matching.overlap_data(np.array([0.1, np.nan, 0.2, 0.3]), d)
    # constant but unequal groups: the standardised difference is infinite, with sign
    x = np.array([5.0, 5.0, 3.0, 3.0])
    assert matching.standardized_mean_difference(x, d) == float("inf")
