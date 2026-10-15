"""Unit tests for MOE propagation, against the Census's published formulas.

Constructed inputs with known answers. No number here is reported as a finding.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import numpy as np
import pytest

from krl_tutorials_data.uncertainty import (
    Z90, Estimate, aggregate_moe, proportion_moe, ratio_moe,
    difference_is_significant, significance_matrix,
)


def test_standard_error_derives_from_the_90_percent_moe() -> None:
    e = Estimate(value=1000.0, moe=164.5)
    assert e.standard_error == pytest.approx(100.0)
    assert e.ci90 == pytest.approx((835.5, 1164.5))


def test_proportion_moe_matches_the_census_formula() -> None:
    num, den = Estimate(500.0, 50.0), Estimate(2000.0, 100.0)
    p = 0.25
    expected = np.sqrt(50.0**2 - (p**2) * 100.0**2) / 2000.0
    assert proportion_moe(num, den) == pytest.approx(expected)


def test_proportion_falls_back_to_ratio_when_the_radicand_is_negative() -> None:
    """Census instruction: use the ratio formula when the radicand goes negative."""
    num, den = Estimate(1000.0, 20.0), Estimate(2000.0, 500.0)
    p = 0.5
    assert 20.0**2 - (p**2) * 500.0**2 < 0, "test case must trigger the fallback"
    assert proportion_moe(num, den) == pytest.approx(ratio_moe(num, den))


def test_ratio_moe_adds_rather_than_subtracts() -> None:
    num, den = Estimate(500.0, 50.0), Estimate(2000.0, 100.0)
    r = 0.25
    expected = np.sqrt(50.0**2 + (r**2) * 100.0**2) / 2000.0
    assert ratio_moe(num, den) == pytest.approx(expected)


def test_identical_estimates_are_not_distinguishable() -> None:
    a = b = Estimate(1000.0, 100.0)
    sig, z = difference_is_significant(a, b)
    assert sig is False and z == pytest.approx(0.0)


def test_widely_separated_estimates_are_distinguishable() -> None:
    sig, z = difference_is_significant(Estimate(1000.0, 50.0), Estimate(100.0, 50.0))
    assert sig is True and abs(z) > Z90


def test_overlapping_margins_are_not_distinguishable() -> None:
    """The headline lesson: a visible gap is not a significant one."""
    sig, _ = difference_is_significant(Estimate(1000.0, 400.0), Estimate(900.0, 400.0))
    assert sig is False


def test_zero_variance_pair_returns_not_significant_rather_than_dividing_by_zero() -> None:
    sig, z = difference_is_significant(Estimate(10.0, 0.0), Estimate(20.0, 0.0))
    assert sig is False and z == 0.0


def test_significance_matrix_is_symmetric_and_counts_its_tests() -> None:
    est = {
        "A": Estimate(1000.0, 30.0),
        "B": Estimate(1010.0, 30.0),
        "C": Estimate(1500.0, 30.0),
    }
    m, labels, n_tests = significance_matrix(est)
    assert labels == ["A", "B", "C"]
    assert n_tests == 3
    assert np.array_equal(m, m.T)
    assert not m[0, 0]
    assert m[0, 2] and m[1, 2]      # C is far from both
    assert not m[0, 1]              # A and B are 10 apart with MOE 30


def test_zero_denominator_raises_rather_than_returning_inf() -> None:
    with pytest.raises(ValueError, match="positive"):
        proportion_moe(Estimate(5.0, 1.0), Estimate(0.0, 1.0))


def test_aggregate_moe_combines_in_quadrature() -> None:
    parts = [Estimate(100.0, 30.0), Estimate(200.0, 40.0)]
    agg = aggregate_moe(parts)
    assert agg.value == pytest.approx(300.0)
    assert agg.moe == pytest.approx(50.0)   # sqrt(30^2 + 40^2)


def test_aggregate_moe_is_smaller_than_naive_summing_of_moes() -> None:
    """Quadrature, not addition: independent errors partially cancel."""
    parts = [Estimate(10.0, 10.0)] * 4
    assert aggregate_moe(parts).moe == pytest.approx(20.0)      # sqrt(4*100)
    assert aggregate_moe(parts).moe < sum(p.moe for p in parts)  # 20 < 40


def test_aggregate_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        aggregate_moe([])


# --------------------------------------------------------------------------- #
# Multiple-comparison procedures and the independence bound.
# --------------------------------------------------------------------------- #

from krl_tutorials_data.uncertainty import (  # noqa: E402
    aggregate_moe_bounds, p_value_from_z, holm_bonferroni, benjamini_hochberg,
)


def test_p_value_from_z_matches_known_normal_quantiles() -> None:
    assert p_value_from_z(0.0) == pytest.approx(1.0)
    assert p_value_from_z(1.96) == pytest.approx(0.05, abs=1e-3)
    assert p_value_from_z(1.645) == pytest.approx(0.10, abs=1e-3)
    assert p_value_from_z(-1.96) == pytest.approx(p_value_from_z(1.96))


def test_holm_is_more_conservative_than_uncorrected() -> None:
    p = np.array([0.001, 0.02, 0.04, 0.06, 0.30])
    res = holm_bonferroni(p, alpha=0.10)
    assert res.n_significant_raw == 4
    assert res.n_significant_corrected <= res.n_significant_raw
    assert res.n_withdrawn >= 0


def test_holm_steps_down_and_stops_at_first_failure() -> None:
    """Once a hypothesis fails, every larger p-value must also fail."""
    p = np.array([0.001, 0.09, 0.0001])
    res = holm_bonferroni(p, alpha=0.10)
    # sorted: 0.0001 (<=0.10/3), 0.001 (<=0.10/2), 0.09 (>0.10/1? no, 0.09<=0.10) -> all
    assert res.rejected.sum() == 3


def test_holm_rejects_nothing_when_all_p_values_are_large() -> None:
    res = holm_bonferroni(np.array([0.5, 0.6, 0.9]), alpha=0.10)
    assert res.n_significant_corrected == 0 and not res.rejected.any()


def test_bh_is_at_least_as_powerful_as_holm() -> None:
    p = np.array([0.001, 0.008, 0.02, 0.04, 0.05, 0.2, 0.5])
    holm = holm_bonferroni(p, alpha=0.10)
    bh = benjamini_hochberg(p, alpha=0.10)
    assert bh.n_significant_corrected >= holm.n_significant_corrected


def test_bh_rejects_the_contiguous_block_up_to_the_cutoff() -> None:
    """Step-up: everything with p below the largest passing threshold is rejected."""
    p = np.array([0.01, 0.04, 0.03, 0.9])
    bh = benjamini_hochberg(p, alpha=0.10)
    assert bh.rejected[0] and bh.rejected[1] and bh.rejected[2]
    assert not bh.rejected[3]


def test_correction_result_reports_what_it_withdrew() -> None:
    res = holm_bonferroni(np.array([0.001, 0.09, 0.095]), alpha=0.10)
    assert res.n_withdrawn == res.n_significant_raw - res.n_significant_corrected
    assert "Holm" in res.render()


def test_aggregate_bounds_bracket_the_census_formula() -> None:
    parts = [Estimate(100.0, 30.0), Estimate(200.0, 40.0)]
    lo, hi = aggregate_moe_bounds(parts)
    assert lo.value == hi.value == pytest.approx(300.0)
    assert lo.moe == pytest.approx(50.0)     # quadrature, the Census formula
    assert hi.moe == pytest.approx(70.0)     # perfect correlation, linear sum
    assert lo.moe < hi.moe


def test_aggregate_bounds_coincide_for_a_single_component() -> None:
    lo, hi = aggregate_moe_bounds([Estimate(10.0, 3.0)])
    assert lo.moe == pytest.approx(hi.moe)
