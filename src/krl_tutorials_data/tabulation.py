"""Checking whether a set of published categories actually partitions a total.

Published tables indent their categories, and indentation reads like a
partition. It frequently is not one. In ACS table B28002, "Broadband of any
type", "Cellular data plan", "Broadband such as cable, fiber optic or DSL" and
"Satellite Internet service" are all children of "With an Internet
subscription", and a household with cable and a phone plan is counted under
several of them. Summing those rows overstates the total by a factor of roughly
2.7 across every US county, and nothing in the response signals it.

The mutually exclusive categories in the same table are the ones whose labels
end "with no other type of Internet subscription". Reading the labels is what
distinguishes them; this module makes the reading testable.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

import numpy as np

__all__ = ["Coverage", "PartitionReport", "PartitionError", "check_partition"]


class PartitionError(ValueError):
    """Raised when a partition check cannot be performed."""


class Coverage(str, Enum):
    EXACT = "exact"
    OVER = "over"      # categories overlap, or a component is double-counted
    UNDER = "under"    # categories omit part of the universe


@dataclass(frozen=True)
class PartitionReport:
    """Result of testing ``sum(parts) == total``."""

    label: str
    part_sum: float
    total: float
    residual: float
    ratio: float
    coverage: Coverage
    tolerance: float

    @property
    def partitions(self) -> bool:
        return self.coverage is Coverage.EXACT

    def render(self) -> str:
        return (
            f"{self.label}: sum of parts {self.part_sum:,.0f} vs published total "
            f"{self.total:,.0f}  (ratio {self.ratio:.4f}, residual "
            f"{self.residual:,.0f}) -> {self.coverage.value.upper()}"
        )


def check_partition(
    parts: Sequence[float],
    total: float,
    *,
    label: str = "partition",
    tolerance: float = 0.0,
) -> PartitionReport:
    """Test whether ``parts`` sum to ``total`` within ``tolerance``.

    ``tolerance`` is an absolute count, defaulting to zero. Published Census
    counts are integers that are supposed to add exactly; a tolerance is
    something the analyst opts into and therefore has to write down.
    """
    if len(parts) == 0:
        raise PartitionError("No parts supplied.")
    if tolerance < 0:
        raise PartitionError("Tolerance must be non-negative.")
    if total <= 0:
        raise PartitionError(
            "A non-positive total has no meaningful partition; handle the "
            "empty-universe case explicitly."
        )
    part_sum = float(np.sum(np.asarray(parts, dtype=float)))
    residual = part_sum - total
    if abs(residual) <= tolerance:
        coverage = Coverage.EXACT
    else:
        coverage = Coverage.OVER if residual > 0 else Coverage.UNDER
    return PartitionReport(
        label=label,
        part_sum=part_sum,
        total=float(total),
        residual=residual,
        ratio=part_sum / float(total),
        coverage=coverage,
        tolerance=tolerance,
    )
