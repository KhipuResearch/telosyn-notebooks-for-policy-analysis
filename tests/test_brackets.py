"""Tests for bracket interpolation and the open-bracket identification guard.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import numpy as np
import pytest

from krl_tutorials_data.brackets import (
    ACS_B25070_BRACKETS,
    BracketEdges,
    BracketError,
    UnidentifiedPercentileError,
    interpolated_percentile,
    median_from_brackets,
    percentile_is_identified,
)

CLOSED = BracketEdges(lower=(0.0, 10.0, 20.0), upper=(10.0, 20.0, 30.0), units="pct")
OPEN = BracketEdges(lower=(0.0, 10.0, 20.0), upper=(10.0, 20.0, float("inf")), units="pct")


# --------------------------------------------------------------------------
# Specification validation
# --------------------------------------------------------------------------

def test_non_ascending_lower_edges_rejected():
    with pytest.raises(BracketError, match="ascending"):
        BracketEdges(lower=(0.0, 20.0, 10.0), upper=(20.0, 30.0, 40.0), units="pct")


def test_upper_edge_must_exceed_lower():
    with pytest.raises(BracketError, match="exceed"):
        BracketEdges(lower=(0.0, 10.0), upper=(0.0, 20.0), units="pct")


def test_only_the_last_bracket_may_be_open():
    with pytest.raises(BracketError, match="final bracket"):
        BracketEdges(lower=(0.0, 10.0), upper=(float("inf"), 20.0), units="pct")


def test_edge_count_mismatch_rejected():
    with pytest.raises(BracketError, match="upper edges"):
        BracketEdges(lower=(0.0, 10.0), upper=(10.0,), units="pct")


def test_empty_specification_rejected():
    with pytest.raises(BracketError, match="At least one"):
        BracketEdges(lower=(), upper=(), units="pct")


def test_top_is_open_reports_the_specification():
    assert OPEN.top_is_open and not CLOSED.top_is_open


# --------------------------------------------------------------------------
# Interpolation
# --------------------------------------------------------------------------

def test_median_of_a_symmetric_distribution_sits_at_the_centre():
    assert median_from_brackets([1.0, 1.0, 1.0], CLOSED) == pytest.approx(15.0)


def test_median_interpolates_linearly_within_its_bracket():
    """Half the mass below 10, so the median sits at the very start of bracket 2."""
    assert median_from_brackets([50.0, 25.0, 25.0], CLOSED) == pytest.approx(10.0)


def test_quarter_way_through_the_containing_bracket():
    # 40% below 10; the 50% point is 10/60 of the way through a 40-wide bracket.
    got = interpolated_percentile([40.0, 60.0, 0.0], CLOSED, 0.5)
    assert got == pytest.approx(10.0 + (0.10 / 0.60) * 10.0)


def test_all_mass_in_one_bracket_gives_an_interior_point():
    got = median_from_brackets([0.0, 100.0, 0.0], CLOSED)
    assert 10.0 < got < 20.0
    assert got == pytest.approx(15.0)


def test_percentiles_are_monotonic_in_q():
    counts = [10.0, 30.0, 20.0]
    qs = [0.1, 0.25, 0.5, 0.75, 0.9]
    vals = [interpolated_percentile(counts, CLOSED, q) for q in qs]
    assert vals == sorted(vals)


def test_empty_leading_brackets_are_skipped():
    assert median_from_brackets([0.0, 0.0, 10.0], CLOSED) == pytest.approx(25.0)


@pytest.mark.parametrize("q", [0.0, 1.0, -0.1, 1.5])
def test_q_outside_the_open_unit_interval_rejected(q):
    with pytest.raises(BracketError, match="strictly between"):
        interpolated_percentile([1.0, 1.0, 1.0], CLOSED, q)


def test_count_length_must_match_the_specification():
    with pytest.raises(BracketError, match="counts for"):
        median_from_brackets([1.0, 1.0], CLOSED)


def test_negative_counts_rejected():
    with pytest.raises(BracketError, match="non-negative"):
        median_from_brackets([1.0, -1.0, 1.0], CLOSED)


def test_empty_distribution_rejected():
    with pytest.raises(BracketError, match="no percentile"):
        median_from_brackets([0.0, 0.0, 0.0], CLOSED)


# --------------------------------------------------------------------------
# The identification guard
# --------------------------------------------------------------------------

def test_median_inside_the_open_bracket_raises():
    with pytest.raises(UnidentifiedPercentileError, match="open-ended"):
        median_from_brackets([10.0, 10.0, 80.0], OPEN)


def test_the_same_counts_are_fine_when_the_top_is_closed():
    assert median_from_brackets([10.0, 10.0, 80.0], CLOSED) == pytest.approx(23.75)


def test_opt_in_returns_the_lower_bound_not_a_percentile():
    got = median_from_brackets([10.0, 10.0, 80.0], OPEN, allow_unidentified=True)
    assert got == pytest.approx(20.0)  # the bracket's lower edge, a bound


def test_identification_check_agrees_with_the_guard():
    assert not percentile_is_identified([10.0, 10.0, 80.0], OPEN, 0.5)
    assert percentile_is_identified([80.0, 10.0, 10.0], OPEN, 0.5)
    assert percentile_is_identified([10.0, 10.0, 80.0], CLOSED, 0.5)


def test_a_high_percentile_can_be_unidentified_while_the_median_is_not():
    counts = [40.0, 40.0, 20.0]
    assert percentile_is_identified(counts, OPEN, 0.5)
    assert not percentile_is_identified(counts, OPEN, 0.95)
    with pytest.raises(UnidentifiedPercentileError):
        interpolated_percentile(counts, OPEN, 0.95)


def test_identification_check_validates_q():
    with pytest.raises(BracketError, match="strictly between"):
        percentile_is_identified([1.0, 1.0, 1.0], OPEN, 1.0)


# --------------------------------------------------------------------------
# The shipped ACS specification
# --------------------------------------------------------------------------

def test_b25070_specification_matches_the_published_table():
    b = ACS_B25070_BRACKETS
    assert b.n == 9, "B25070 has nine rent-burden brackets; the tenth is 'Not computed'"
    assert b.lower[:6] == (0.0, 10.0, 15.0, 20.0, 25.0, 30.0)
    assert b.upper[4] == 30.0 and b.lower[5] == 30.0, "30% must be an exact edge"
    assert b.top_is_open


def test_thirty_percent_threshold_needs_no_interpolation():
    """The conventional burden threshold coincides with a bracket edge."""
    counts = np.array([5.0, 8.0, 12.0, 15.0, 14.0, 13.0, 9.0, 10.0, 14.0])
    burdened = counts[5:].sum()
    assert burdened == pytest.approx(46.0)
    share = burdened / counts.sum()
    assert 0.0 < share < 1.0


def test_b25070_median_is_unidentified_when_half_pay_over_fifty_percent():
    counts = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 40.0]
    assert not percentile_is_identified(counts, ACS_B25070_BRACKETS, 0.5)
    with pytest.raises(UnidentifiedPercentileError):
        median_from_brackets(counts, ACS_B25070_BRACKETS)
