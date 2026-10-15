"""Income inequality measures computed from published income brackets.

Why this module exists
----------------------
The Census publishes both a household income *distribution* (table B19001, 16
brackets) and its own Gini index (B19083). Computing the Gini from the brackets
and comparing it to the published value gives a tutorial an **external
validation target**: if the computed figure does not land near the published
one, the pipeline is wrong and the notebook should say so.

Every function here is deterministic and has no data dependency, so it is unit
tested against cases whose answers are known analytically.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

__all__ = ["BracketScheme", "ACS_B19001_BRACKETS", "lorenz_curve", "gini_from_lorenz",
           "gini_from_brackets", "theil_t", "atkinson", "percentile_from_brackets",
           "percentile_ratio", "top_share", "open_bracket_share",
           "top_share_is_identified", "UnidentifiedTopShareError"]


@dataclass(frozen=True)
class BracketScheme:
    """An income bracket scheme with an explicit top-code assumption.

    Attributes
    ----------
    edges:
        Lower bounds of each bracket, ascending. ``len(edges)`` equals the
        number of brackets; the final bracket is open-ended.
    top_mean:
        Assumed mean of the open-ended top bracket. This is a **modelling
        choice, not a measurement**, and it materially affects the Gini. It is
        stored here so that it is stated rather than buried.
    top_mean_basis:
        Prose justification for ``top_mean``, surfaced in the notebook.
    """

    edges: tuple[float, ...]
    top_mean: float
    top_mean_basis: str

    def midpoints(self) -> np.ndarray:
        """Representative income for each bracket.

        Closed brackets use the arithmetic midpoint, which assumes households
        are uniformly distributed within the bracket. That assumption biases
        the Gini slightly downward because income is right-skewed inside
        brackets as well as between them.
        """
        mids = [(self.edges[i] + self.edges[i + 1]) / 2 for i in range(len(self.edges) - 1)]
        mids.append(self.top_mean)
        return np.asarray(mids, dtype=float)


# B19001 lower bounds, in dollars. The final bracket is "$200,000 or more".
ACS_B19001_BRACKETS = BracketScheme(
    edges=(0, 10_000, 15_000, 20_000, 25_000, 30_000, 35_000, 40_000, 45_000,
           50_000, 60_000, 75_000, 100_000, 125_000, 150_000, 200_000),
    top_mean=350_000.0,
    top_mean_basis=(
        "The top bracket ($200,000+) is open-ended, so its mean must be assumed. "
        "350,000 is used as a documented placeholder; the notebook reports the "
        "sensitivity of the Gini to this choice rather than hiding it."
    ),
)


def lorenz_curve(
    counts: Sequence[float], incomes: Sequence[float]
) -> tuple[np.ndarray, np.ndarray]:
    """Return cumulative population and income shares, both starting at zero.

    Parameters
    ----------
    counts:
        Number of households in each bracket.
    incomes:
        Representative income for each bracket, same length and order.

    Raises
    ------
    ValueError
        If the inputs disagree in length, contain negatives, or sum to zero —
        all of which indicate a data defect rather than a degenerate economy.
    """
    c = np.asarray(counts, dtype=float)
    y = np.asarray(incomes, dtype=float)
    if c.shape != y.shape:
        raise ValueError(f"counts and incomes differ in shape: {c.shape} vs {y.shape}")
    if np.any(c < 0) or np.any(y < 0):
        raise ValueError("Negative counts or incomes indicate unremoved sentinel values.")
    if c.sum() <= 0:
        raise ValueError("Total household count is zero; nothing to describe.")

    order = np.argsort(y)
    c, y = c[order], y[order]
    total_income = (c * y).sum()
    if total_income <= 0:
        raise ValueError("Total income is zero; cannot form a Lorenz curve.")

    pop = np.concatenate([[0.0], np.cumsum(c) / c.sum()])
    inc = np.concatenate([[0.0], np.cumsum(c * y) / total_income])
    return pop, inc


def gini_from_lorenz(pop_share: np.ndarray, income_share: np.ndarray) -> float:
    """Gini coefficient as twice the area between the diagonal and the curve.

    Uses the trapezoidal rule over the supplied points. With bracketed data the
    curve is piecewise linear between bracket boundaries, so this is exact for
    the bracket representation and an approximation of the underlying
    continuous distribution.
    """
    area_under = np.trapezoid(income_share, pop_share)
    return float(1.0 - 2.0 * area_under)


def gini_from_brackets(counts: Sequence[float], scheme: BracketScheme = ACS_B19001_BRACKETS) -> float:
    pop, inc = lorenz_curve(counts, scheme.midpoints())
    return gini_from_lorenz(pop, inc)


# --------------------------------------------------------------------------- #
# Alternative inequality measures.
#
# The Gini is one summary of a distribution, not the summary. These measures
# weight different regions of the distribution, so they can and do disagree
# about which places are most unequal. A notebook that reports only one is
# making a choice it has not disclosed.
# --------------------------------------------------------------------------- #


def _grouped(counts: Sequence[float], incomes: Sequence[float]) -> tuple[np.ndarray, np.ndarray, float]:
    """Validate grouped data and return (counts, incomes, mean income)."""
    c = np.asarray(counts, dtype=float)
    y = np.asarray(incomes, dtype=float)
    if c.shape != y.shape:
        raise ValueError(f"counts and incomes differ in shape: {c.shape} vs {y.shape}")
    if np.any(c < 0) or np.any(y < 0):
        raise ValueError("Negative counts or incomes indicate unremoved sentinel values.")
    if c.sum() <= 0:
        raise ValueError("Total household count is zero; nothing to describe.")
    mu = float((c * y).sum() / c.sum())
    if mu <= 0:
        raise ValueError("Mean income is zero or negative; measures are undefined.")
    return c, y, mu


def theil_t(counts: Sequence[float], incomes: Sequence[float]) -> float:
    """Theil's T index for grouped data.

    ``T = sum_i (n_i/N) * (y_i/mu) * ln(y_i/mu)``

    Theil is **top-sensitive**: it responds more to changes at the top of the
    distribution than the Gini does, which is why it and the Gini can rank the
    same places differently. It is also additively decomposable into
    within-group and between-group components, which the Gini is not.

    Zero indicates perfect equality. There is no fixed upper bound; the maximum
    is ``ln(N)`` when one unit holds everything.
    """
    c, y, mu = _grouped(counts, incomes)
    mask = (y > 0) & (c > 0)
    share = c[mask] / c.sum()
    rel = y[mask] / mu
    return float((share * rel * np.log(rel)).sum())


def atkinson(counts: Sequence[float], incomes: Sequence[float], epsilon: float = 0.5) -> float:
    """Atkinson index with explicit inequality aversion ``epsilon``.

    ``epsilon`` is a **normative parameter**, not a statistical one: it states
    how much weight the analyst places on transfers at the bottom of the
    distribution. Larger values are more bottom-sensitive. Reporting an Atkinson
    index without stating epsilon is meaningless, which is why it is required
    here rather than hidden behind a default that readers ignore.

    Interpretation: ``A = 0.20`` means the same welfare could be achieved with
    80% of current total income if it were distributed equally.

    Bounded in [0, 1]. Zero indicates perfect equality.
    """
    if epsilon < 0:
        raise ValueError("Inequality aversion epsilon must be non-negative.")
    c, y, mu = _grouped(counts, incomes)
    mask = (c > 0) & (y > 0)
    share = c[mask] / c.sum()
    rel = y[mask] / mu
    if np.isclose(epsilon, 1.0):
        # Limiting case: 1 - (geometric mean / arithmetic mean)
        return float(1.0 - np.exp((share * np.log(rel)).sum()))
    ede = float((share * rel ** (1.0 - epsilon)).sum() ** (1.0 / (1.0 - epsilon)))
    return float(1.0 - ede)


def percentile_from_brackets(
    counts: Sequence[float], incomes: Sequence[float], q: float
) -> float:
    """Income at cumulative population share ``q``, by linear interpolation.

    With bracketed data the percentile is not observed; it is interpolated
    within whichever bracket contains it. The result inherits the
    within-bracket-uniformity assumption and is less reliable in the tails,
    where brackets are widest.
    """
    if not 0.0 < q < 1.0:
        raise ValueError("q must lie strictly between 0 and 1.")
    c, y, _ = _grouped(counts, incomes)
    order = np.argsort(y)
    c, y = c[order], y[order]
    cum = np.cumsum(c) / c.sum()
    idx = int(np.searchsorted(cum, q))
    if idx == 0:
        return float(y[0])
    if idx >= len(y):
        return float(y[-1])
    lo_cum, hi_cum = cum[idx - 1], cum[idx]
    if np.isclose(hi_cum, lo_cum):
        return float(y[idx])
    frac = (q - lo_cum) / (hi_cum - lo_cum)
    return float(y[idx - 1] + frac * (y[idx] - y[idx - 1]))


def percentile_ratio(
    counts: Sequence[float], incomes: Sequence[float], high: float = 0.90, low: float = 0.10
) -> float:
    """Ratio of the ``high`` percentile to the ``low`` percentile, e.g. p90/p10.

    Unlike the Gini this ignores the distribution between the two points
    entirely — which is both its weakness and, when the question is about the
    gap between rich and poor specifically, its point.
    """
    lo = percentile_from_brackets(counts, incomes, low)
    if lo <= 0:
        raise ValueError(f"Income at the {low:.0%} percentile is zero; ratio undefined.")
    return float(percentile_from_brackets(counts, incomes, high) / lo)


class UnidentifiedTopShareError(ValueError):
    """The requested top share is not identified by the bracket scheme.

    Raised when the open top bracket contains a larger share of units than the
    share being requested. In that case the whole of the requested top group
    lies inside a single bracket whose members are all assigned the same assumed
    income, so the statistic measures the **bracket cap**, not the distribution.

    This is not a nuisance warning. Measured across US states from ACS B19001,
    the correlation between the open-bracket share and the naively computed
    top-decile share is about **-0.95**: the more households a state has above
    the top threshold, the *lower* its apparent top-decile share. Any ranking
    built on the unguarded statistic is substantially an artifact.
    """


def open_bracket_share(counts: Sequence[float]) -> float:
    """Fraction of units falling in the final, open-ended bracket."""
    c = np.asarray(counts, dtype=float)
    if np.any(c < 0):
        raise ValueError("Negative counts indicate unremoved sentinel values.")
    if c.sum() <= 0:
        raise ValueError("Total count is zero.")
    return float(c[-1] / c.sum())


def top_share_is_identified(counts: Sequence[float], top: float = 0.10) -> bool:
    """Whether a ``top`` share can be resolved given the open top bracket.

    Identified only when the open bracket holds *less* than ``top`` of the
    units, so that the boundary of the top group falls inside a bracket with a
    known upper edge.
    """
    return open_bracket_share(counts) < top


def top_share(
    counts: Sequence[float],
    incomes: Sequence[float],
    top: float = 0.10,
    *,
    allow_unidentified: bool = False,
) -> float:
    """Share of total income held by the richest ``top`` fraction of units.

    Computed from the Lorenz curve, so it inherits the bracket assumptions and
    is highly sensitive to the assumed mean of the open top bracket.

    Raises
    ------
    UnidentifiedTopShareError
        When the open top bracket holds at least ``top`` of the units, unless
        ``allow_unidentified=True`` is passed to acknowledge the limitation
        explicitly. Failing closed here is deliberate: the unguarded statistic
        is silently wrong rather than obviously wrong.
    """
    if not 0.0 < top < 1.0:
        raise ValueError("top must lie strictly between 0 and 1.")
    if not allow_unidentified and not top_share_is_identified(counts, top):
        raise UnidentifiedTopShareError(
            f"The open top bracket holds {open_bracket_share(counts):.1%} of units, "
            f"which is not less than the requested top {top:.0%}. The whole of the "
            f"top group lies inside one flat bracket, so this statistic would "
            f"measure the bracket cap rather than the distribution. Use a smaller "
            f"`top`, a scheme with a higher top edge, or pass "
            f"allow_unidentified=True to proceed knowingly."
        )
    pop, inc = lorenz_curve(counts, incomes)
    return float(1.0 - np.interp(1.0 - top, pop, inc))
