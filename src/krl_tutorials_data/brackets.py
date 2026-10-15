"""Percentiles from published bracket tables, with an identification guard.

Census publishes many distributions only as bracket counts: households by rent
burden, by income, by year built. A percentile of such a distribution is never
observed. It is *interpolated* inside whichever bracket contains it, and it
therefore inherits an assumption — normally that the bracket is uniformly
filled — which is stated here rather than buried.

The failure this module exists to prevent is the open top bracket. When the
requested percentile falls in "50.0 percent or more", the bracket has no upper
edge, and no interpolation is possible. Every finite answer produced at that
point is an artefact of whatever upper bound the code silently assumed. The
guard refuses by default, in the same spirit as the top-share guard in
:mod:`krl_tutorials_data.inequality`, which was added after an unguarded
statistic ranked the District of Columbia both 1st and 52nd on the same data.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

__all__ = [
    "BracketEdges",
    "BracketError",
    "UnidentifiedPercentileError",
    "interpolated_percentile",
    "median_from_brackets",
    "percentile_is_identified",
    "ACS_B25070_BRACKETS",
]


class BracketError(ValueError):
    """Raised when a bracket specification or its counts are unusable."""


class UnidentifiedPercentileError(BracketError):
    """The requested percentile falls in an open-ended bracket."""


@dataclass(frozen=True)
class BracketEdges:
    """Bracket boundaries for a grouped distribution.

    Attributes
    ----------
    lower:
        Lower edge of each bracket, strictly ascending.
    upper:
        Upper edge of each bracket. The final entry may be ``inf``, which
        declares the top bracket open-ended and makes any percentile falling
        inside it unidentified.
    units:
        What the edges are measured in, carried so that output can name it.
    """

    lower: tuple[float, ...]
    upper: tuple[float, ...]
    units: str

    def __post_init__(self) -> None:
        lo = np.asarray(self.lower, dtype=float)
        up = np.asarray(self.upper, dtype=float)
        if lo.size == 0:
            raise BracketError("At least one bracket is required.")
        if lo.size != up.size:
            raise BracketError(f"{lo.size} lower edges but {up.size} upper edges.")
        if np.any(np.diff(lo) <= 0):
            raise BracketError("Lower edges must be strictly ascending.")
        if np.any(up <= lo):
            raise BracketError("Every upper edge must exceed its lower edge.")
        if np.any(np.isinf(up[:-1])):
            raise BracketError("Only the final bracket may be open-ended.")

    @property
    def n(self) -> int:
        return len(self.lower)

    @property
    def top_is_open(self) -> bool:
        return bool(np.isinf(self.upper[-1]))


#: ACS table B25070, gross rent as a percentage of household income. The nine
#: brackets exclude "Not computed" (`B25070_011E`), which is NOT a bracket of
#: the distribution but a separate category of the universe.
ACS_B25070_BRACKETS = BracketEdges(
    lower=(0.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 50.0),
    upper=(10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 50.0, float("inf")),
    units="percent of household income",
)


def _validated(counts: Sequence[float], edges: BracketEdges) -> np.ndarray:
    c = np.asarray(counts, dtype=float)
    if c.ndim != 1:
        raise BracketError("Counts must be one-dimensional.")
    if c.size != edges.n:
        raise BracketError(f"{c.size} counts for {edges.n} brackets.")
    if np.any(c < 0):
        raise BracketError("Counts must be non-negative.")
    if c.sum() <= 0:
        raise BracketError(
            "Total count is zero; the distribution is empty and has no percentile."
        )
    return c


def _containing_bracket(counts: np.ndarray, q: float) -> tuple[int, float, float]:
    cum = np.cumsum(counts) / counts.sum()
    idx = int(np.searchsorted(cum, q, side="left"))
    idx = min(idx, len(counts) - 1)
    below = float(cum[idx - 1]) if idx > 0 else 0.0
    return idx, below, float(cum[idx])


def percentile_is_identified(
    counts: Sequence[float], edges: BracketEdges, q: float = 0.5
) -> bool:
    """Whether ``q`` falls somewhere with a finite upper edge."""
    if not 0.0 < q < 1.0:
        raise BracketError("q must lie strictly between 0 and 1.")
    c = _validated(counts, edges)
    idx, _, _ = _containing_bracket(c, q)
    return bool(np.isfinite(edges.upper[idx]))


def interpolated_percentile(
    counts: Sequence[float],
    edges: BracketEdges,
    q: float = 0.5,
    *,
    allow_unidentified: bool = False,
) -> float:
    """Percentile ``q`` by linear interpolation inside the containing bracket.

    Within the bracket holding the percentile, the cumulative distribution is
    assumed to rise linearly from its lower edge to its upper edge. This is the
    standard treatment for grouped data and is what makes the result an
    estimate rather than a measurement.

    Raises :class:`UnidentifiedPercentileError` when the percentile falls in an
    open-ended bracket, unless ``allow_unidentified`` is set — in which case the
    bracket's lower edge is returned, which is a **lower bound and not the
    percentile**, and callers must report it as such.
    """
    if not 0.0 < q < 1.0:
        raise BracketError("q must lie strictly between 0 and 1.")
    c = _validated(counts, edges)
    idx, below, at = _containing_bracket(c, q)
    lo, hi = float(edges.lower[idx]), float(edges.upper[idx])

    if not np.isfinite(hi):
        if not allow_unidentified:
            raise UnidentifiedPercentileError(
                f"The {q:.0%} percentile falls in the open-ended bracket starting "
                f"at {lo:g} {edges.units}, which has no upper edge. Any finite "
                f"value reported here would come from an assumed bound, not from "
                f"the data. Pass allow_unidentified=True to receive the lower "
                f"bound {lo:g} and report it as a bound."
            )
        return lo

    if at <= below:  # an empty bracket cannot be interpolated through
        return lo
    return lo + (q - below) / (at - below) * (hi - lo)


def median_from_brackets(
    counts: Sequence[float], edges: BracketEdges, *, allow_unidentified: bool = False
) -> float:
    """The 50th percentile of a grouped distribution."""
    return interpolated_percentile(
        counts, edges, 0.5, allow_unidentified=allow_unidentified
    )
