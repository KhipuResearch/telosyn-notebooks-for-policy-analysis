"""Tests for the partition check.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import pytest

from krl_tutorials_data.tabulation import (
    Coverage,
    PartitionError,
    check_partition,
)


def test_exact_partition():
    r = check_partition([30.0, 50.0, 20.0], 100.0, label="exclusive")
    assert r.coverage is Coverage.EXACT
    assert r.partitions
    assert r.residual == pytest.approx(0.0)
    assert r.ratio == pytest.approx(1.0)


def test_overlapping_categories_report_over_coverage():
    """The B28002 shape: children of one parent that are not mutually exclusive."""
    r = check_partition([85.0, 60.0, 64.0, 10.0], 88.0, label="overlapping")
    assert r.coverage is Coverage.OVER
    assert not r.partitions
    assert r.ratio > 2.0


def test_omitted_categories_report_under_coverage():
    r = check_partition([30.0, 40.0], 100.0)
    assert r.coverage is Coverage.UNDER
    assert r.residual == pytest.approx(-30.0)


def test_tolerance_is_opt_in_and_absolute():
    assert check_partition([99.0], 100.0).coverage is Coverage.UNDER
    assert check_partition([99.0], 100.0, tolerance=1.0).coverage is Coverage.EXACT
    assert check_partition([99.0], 100.0, tolerance=0.5).coverage is Coverage.UNDER
    assert check_partition([101.0], 100.0, tolerance=1.0).coverage is Coverage.EXACT


def test_negative_tolerance_rejected():
    with pytest.raises(PartitionError, match="non-negative"):
        check_partition([1.0], 1.0, tolerance=-1.0)


def test_empty_parts_rejected():
    with pytest.raises(PartitionError, match="No parts"):
        check_partition([], 10.0)


def test_non_positive_total_rejected():
    with pytest.raises(PartitionError, match="non-positive"):
        check_partition([1.0], 0.0)


def test_render_names_the_verdict():
    text = check_partition([85.0, 60.0], 88.0, label="subscriptions").render()
    assert "subscriptions" in text and "OVER" in text


def test_report_is_frozen():
    r = check_partition([1.0], 1.0)
    with pytest.raises(Exception):
        r.total = 2.0  # type: ignore[misc]
