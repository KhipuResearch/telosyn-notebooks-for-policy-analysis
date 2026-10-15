"""Tests for the reliability screen and rank-interval bounds.

The central claim this module exists to support is that a CV screen and a rank
bound answer different questions. That claim is tested directly: a fixture of
high-share, modest-margin estimates must pass the CV screen while producing
rank intervals that span most of the field.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import numpy as np
import pytest

from krl_tutorials_data.reliability import (
    CVThresholds,
    RankInterval,
    ReliabilityClass,
    ReliabilityError,
    classify_reliability,
    coefficient_of_variation,
    proportion_moe_is_degenerate,
    rank_intervals,
)
from krl_tutorials_data.uncertainty import Estimate, Z90


# --------------------------------------------------------------------------
# Coefficient of variation
# --------------------------------------------------------------------------

def test_cv_is_standard_error_over_estimate():
    est = Estimate(0.80, 0.0658)  # SE = 0.04
    assert coefficient_of_variation(est) == pytest.approx(0.04 / 0.80, rel=1e-3)


def test_cv_uses_the_ninety_percent_z_not_ninety_five():
    est = Estimate(100.0, 16.45)
    assert coefficient_of_variation(est) == pytest.approx(10.0 / 100.0, rel=1e-6)
    assert coefficient_of_variation(est) != pytest.approx(16.45 / 1.96 / 100.0, rel=1e-6)


def test_cv_of_zero_estimate_raises_rather_than_returning_infinity():
    with pytest.raises(ReliabilityError, match="undefined"):
        coefficient_of_variation(Estimate(0.0, 5.0))


def test_zero_margin_gives_zero_cv():
    assert coefficient_of_variation(Estimate(10.0, 0.0)) == 0.0


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "cv_target,expected",
    [
        (0.05, ReliabilityClass.RELIABLE),
        (0.15, ReliabilityClass.RELIABLE),          # boundary is inclusive
        (0.20, ReliabilityClass.USE_WITH_CAUTION),
        (0.30, ReliabilityClass.USE_WITH_CAUTION),  # boundary is inclusive
        (0.45, ReliabilityClass.UNRELIABLE),
    ],
)
def test_classification_boundaries(cv_target, expected):
    est = Estimate(1.0, cv_target * Z90)
    assert classify_reliability(est) is expected


def test_custom_thresholds_are_honoured():
    strict = CVThresholds(caution=0.02, suppress=0.05)
    est = Estimate(1.0, 0.03 * Z90)
    assert classify_reliability(est) is ReliabilityClass.RELIABLE
    assert classify_reliability(est, strict) is ReliabilityClass.USE_WITH_CAUTION


def test_incoherent_thresholds_rejected():
    with pytest.raises(ReliabilityError, match="caution"):
        CVThresholds(caution=0.4, suppress=0.2)
    with pytest.raises(ReliabilityError):
        CVThresholds(caution=0.0, suppress=0.3)


def test_thresholds_carry_their_source():
    assert "convention" in CVThresholds().source.lower()


# --------------------------------------------------------------------------
# Rank intervals
# --------------------------------------------------------------------------

def _est(pairs) -> dict[str, Estimate]:
    return {k: Estimate(v, m) for k, v, m in pairs}


def test_disjoint_intervals_determine_every_rank():
    ri = {r.label: r for r in rank_intervals(
        _est([("a", 0.90, 0.01), ("b", 0.70, 0.01), ("c", 0.50, 0.01)]))}
    for label, rank in (("a", 1), ("b", 2), ("c", 3)):
        assert (ri[label].point, ri[label].best, ri[label].worst) == (rank, rank, rank)
        assert ri[label].is_determined


def test_fully_overlapping_intervals_determine_nothing():
    ri = rank_intervals(_est([("a", 0.80, 0.50), ("b", 0.60, 0.50), ("c", 0.55, 0.50)]))
    assert all(r.best == 1 and r.worst == 3 for r in ri)
    assert all(r.width == 3 for r in ri)


def test_point_rank_always_lies_inside_the_interval():
    rng = np.random.default_rng(7)
    data = _est([(f"u{i}", float(v), float(m))
                 for i, (v, m) in enumerate(zip(rng.uniform(0, 1, 60),
                                                rng.uniform(0, 0.3, 60)))])
    for r in rank_intervals(data):
        assert r.best <= r.point <= r.worst


def test_ascending_order_reverses_the_bounds():
    data = _est([("a", 0.90, 0.01), ("b", 0.70, 0.01), ("c", 0.50, 0.01)])
    asc = {r.label: r for r in rank_intervals(data, descending=False)}
    assert (asc["c"].point, asc["a"].point) == (1, 3)
    assert asc["c"].is_determined and asc["a"].is_determined


def test_zero_margins_reproduce_a_strict_ordering():
    ri = rank_intervals(_est([("a", 3.0, 0.0), ("b", 2.0, 0.0), ("c", 1.0, 0.0)]))
    assert [r.width for r in ri] == [1, 1, 1]


def test_a_single_unit_is_rank_one():
    (only,) = rank_intervals(_est([("solo", 0.5, 0.2)]))
    assert (only.point, only.best, only.worst, only.width) == (1, 1, 1, 1)


def test_bounds_are_conservative_relative_to_the_point_ordering():
    """A wide interval can only ever widen the attainable range, never narrow it."""
    tight = rank_intervals(_est([("a", 0.9, 0.001), ("b", 0.8, 0.001), ("c", 0.7, 0.001)]))
    loose = rank_intervals(_est([("a", 0.9, 0.06), ("b", 0.8, 0.06), ("c", 0.7, 0.06)]))
    for t, l in zip(tight, loose):
        assert l.best <= t.best and l.worst >= t.worst


def test_negative_margin_rejected():
    with pytest.raises(ReliabilityError, match="non-negative"):
        rank_intervals(_est([("a", 1.0, -0.1)]))


def test_empty_input_rejected():
    with pytest.raises(ReliabilityError, match="No estimates"):
        rank_intervals({})


def test_ties_receive_distinct_point_ranks_but_shared_bounds():
    ri = {r.label: r for r in rank_intervals(
        _est([("a", 0.5, 0.01), ("b", 0.5, 0.01), ("c", 0.1, 0.01)]))}
    assert {ri["a"].point, ri["b"].point} == {1, 2}
    assert ri["a"].best == ri["b"].best == 1
    assert ri["a"].worst == ri["b"].worst == 2


def test_interval_is_frozen():
    (r,) = rank_intervals(_est([("a", 1.0, 0.1)]))
    assert isinstance(r, RankInterval)
    with pytest.raises(Exception):
        r.best = 2  # type: ignore[misc]


# --------------------------------------------------------------------------
# The claim the module exists to support
# --------------------------------------------------------------------------

def test_cv_screen_passes_estimates_whose_ranks_are_undetermined():
    """High shares with modest margins: 'reliable' levels, meaningless ranks.

    This is the B28002 county situation in miniature. Every unit clears the CV
    screen comfortably, and no unit's rank is pinned down at all.
    """
    units = _est([(f"c{i}", 0.85 + 0.0005 * i, 0.023) for i in range(40)])
    assert all(
        classify_reliability(e) is ReliabilityClass.RELIABLE for e in units.values()
    )
    intervals = rank_intervals(units)
    assert all(r.width == len(units) for r in intervals)
    assert not any(r.is_determined for r in intervals)


# --------------------------------------------------------------------------
# The boundary artefact
# --------------------------------------------------------------------------

def test_proportion_margin_collapses_to_zero_at_a_share_of_one():
    from krl_tutorials_data.uncertainty import proportion_moe

    num = Estimate(90.0, 35.0)
    den = Estimate(90.0, 35.0)
    assert proportion_moe(num, den) == pytest.approx(0.0)
    assert proportion_moe_is_degenerate(num, den)


def test_an_ordinary_proportion_is_not_degenerate():
    assert not proportion_moe_is_degenerate(Estimate(40.0, 9.0), Estimate(100.0, 12.0))


def test_a_genuinely_zero_numerator_margin_is_not_flagged():
    """Degeneracy means the formula cancelled, not that the input margin was zero."""
    assert not proportion_moe_is_degenerate(Estimate(50.0, 0.0), Estimate(100.0, 0.0))


def test_degeneracy_check_rejects_a_zero_denominator():
    with pytest.raises(ReliabilityError, match="positive"):
        proportion_moe_is_degenerate(Estimate(0.0, 1.0), Estimate(0.0, 0.0))
