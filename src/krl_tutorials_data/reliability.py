"""Reliability screening and rank stability for small-area estimates.

Two distinct questions are conflated constantly in published small-area work:

1. *Is this estimate precise enough to report?* — conventionally answered with a
   coefficient of variation and a threshold.
2. *Is this estimate precise enough to **rank**?* — a different question with a
   different answer, because ranking is a comparison against every other unit
   and a level screen says nothing about it.

A proportion near 1 makes the point concrete: a share of 0.85 with a margin of
2.3 percentage points has a coefficient of variation near 1.6 per cent, which
every conventional screen calls highly reliable, while its position in a ranking
of three thousand counties is almost entirely undetermined. Certifying the level
and then publishing the rank is a category error.

This module supplies both screens and keeps them separate.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

import numpy as np

from .uncertainty import Estimate, Z90

__all__ = [
    "ReliabilityClass",
    "ReliabilityError",
    "CVThresholds",
    "NCHS_THRESHOLDS",
    "coefficient_of_variation",
    "classify_reliability",
    "RankInterval",
    "rank_intervals",
    "proportion_moe_is_degenerate",
]


class ReliabilityError(ValueError):
    """Raised when a reliability input is structurally unusable."""


class ReliabilityClass(str, Enum):
    """Conventional three-way screen on the coefficient of variation."""

    RELIABLE = "reliable"
    USE_WITH_CAUTION = "use_with_caution"
    UNRELIABLE = "unreliable"


@dataclass(frozen=True)
class CVThresholds:
    """Cut points on the coefficient of variation.

    The defaults follow the widely used National Center for Health Statistics
    convention (30 per cent for suppression, 15 per cent for a caution flag).
    They are a **convention**, not a property of the data, and different
    agencies use different cuts. They are therefore a parameter carried on an
    object that can be printed, not a pair of constants buried in a function.
    """

    caution: float = 0.15
    suppress: float = 0.30
    source: str = "NCHS Data Presentation Standards for Proportions (convention)"

    def __post_init__(self) -> None:
        if not 0 < self.caution < self.suppress:
            raise ReliabilityError(
                f"Thresholds must satisfy 0 < caution ({self.caution}) < "
                f"suppress ({self.suppress})."
            )


NCHS_THRESHOLDS = CVThresholds()


def coefficient_of_variation(est: Estimate, *, z: float = Z90) -> float:
    """Standard error as a fraction of the estimate.

    Undefined at a zero estimate; raises rather than returning infinity, because
    an infinite CV silently sorts to one end of a table.
    """
    if est.value == 0:
        raise ReliabilityError(
            "Coefficient of variation is undefined for a zero estimate. Decide "
            "explicitly whether the unit is suppressed or excluded."
        )
    return abs((est.moe / z) / est.value)


def classify_reliability(
    est: Estimate, thresholds: CVThresholds = NCHS_THRESHOLDS, *, z: float = Z90
) -> ReliabilityClass:
    """Apply the CV screen. This certifies the **level**, and nothing else."""
    cv = coefficient_of_variation(est, z=z)
    if cv > thresholds.suppress:
        return ReliabilityClass.UNRELIABLE
    if cv > thresholds.caution:
        return ReliabilityClass.USE_WITH_CAUTION
    return ReliabilityClass.RELIABLE


@dataclass(frozen=True)
class RankInterval:
    """The range of ranks a unit could occupy, given overlapping intervals.

    ``point`` is the rank by point estimate. ``best`` and ``worst`` bound the
    ranks consistent with the published confidence intervals: a unit can be
    beaten only by units whose interval lies entirely above its own.

    ``width`` is the count of ranks in the interval. A width of 1 means the
    unit's position is determined; a width approaching the number of units means
    the published rank carries no information.
    """

    label: str
    point: int
    best: int
    worst: int

    @property
    def width(self) -> int:
        return self.worst - self.best + 1

    @property
    def is_determined(self) -> bool:
        return self.width == 1


def rank_intervals(
    estimates: dict[str, Estimate], *, descending: bool = True
) -> list[RankInterval]:
    """Bound every unit's attainable rank from its confidence interval.

    The bound is the exact interval-overlap one, not a simulation: unit *i* can
    be outranked only by units whose interval lies wholly on the better side of
    *i*'s interval, so

        best_i  = 1 + #{ j : j's interval lies entirely above i's }
        worst_i = n - #{ j : j's interval lies entirely below i's }

    This is deliberately **conservative**. It makes no distributional assumption
    and no independence assumption, so it cannot understate the ambiguity. A
    simulation-based interval would be narrower and would rest on assumptions
    that a published ACS table does not licence.

    Ties in the point estimate are ranked by the ordinal position of the sorted
    array, so ``point`` is a strict ordering; ``best``/``worst`` are unaffected.
    """
    if not estimates:
        raise ReliabilityError("No estimates supplied.")
    labels = list(estimates)
    values = np.array([estimates[k].value for k in labels], dtype=float)
    moes = np.array([estimates[k].moe for k in labels], dtype=float)
    if np.any(moes < 0):
        raise ReliabilityError("Margins of error must be non-negative.")
    low, high = values - moes, values + moes
    n = len(labels)

    sign = -1.0 if descending else 1.0
    order = np.argsort(sign * values, kind="stable")
    point_rank = np.empty(n, dtype=int)
    point_rank[order] = np.arange(1, n + 1)

    out: list[RankInterval] = []
    for i in range(n):
        if descending:
            better = int(np.sum(low > high[i]))
            worse = int(np.sum(high < low[i]))
        else:
            better = int(np.sum(high < low[i]))
            worse = int(np.sum(low > high[i]))
        out.append(
            RankInterval(
                label=labels[i],
                point=int(point_rank[i]),
                best=1 + better,
                worst=n - worse,
            )
        )
    return out


def proportion_moe_is_degenerate(num: Estimate, den: Estimate) -> bool:
    """Whether the Census proportion formula collapses to a zero margin.

    At a proportion of exactly 1 the numerator and denominator are the same
    count, so ``MOE(X)^2 - p^2 * MOE(Y)^2`` is exactly zero and the formula
    returns a margin of zero — for an estimate that may rest on a handful of
    sampled households.

    **A zero margin here is an artefact of the boundary, not a measurement of
    certainty.** Reported unguarded it puts the unit at the top of a ranking
    with apparently no uncertainty at all. Detect it and say so.
    """
    if den.value <= 0:
        raise ReliabilityError("Denominator estimate must be positive.")
    p = num.value / den.value
    radicand = num.moe ** 2 - (p ** 2) * (den.moe ** 2)
    return bool(radicand == 0 and num.moe > 0)
