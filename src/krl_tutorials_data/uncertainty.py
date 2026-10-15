"""Margin-of-error propagation for ACS estimates.

Every ACS figure is a survey estimate with a published 90% margin of error. A
table that ranks geographies without carrying those margins invents distinctions
that the data does not support. This module implements the formulas the Census
Bureau publishes for exactly this purpose.

Reference
---------
U.S. Census Bureau, *Understanding and Using American Community Survey Data:
What All Data Users Need to Know*, Appendix: "Measures of Error" — derived
proportions, derived ratios, and testing the statistical significance of a
difference between two estimates.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

__all__ = ["Z90", "Estimate", "aggregate_moe", "aggregate_moe_bounds", "proportion_moe",
           "ratio_moe", "proportion_moe_fallback_triggered", "difference_is_significant",
           "p_value_from_z",
           "holm_bonferroni", "benjamini_hochberg", "significance_matrix",
           "CorrectionResult"]

#: ACS margins of error are published at the 90% confidence level.
Z90: float = 1.645


@dataclass(frozen=True)
class Estimate:
    """An ACS estimate with its published 90% margin of error."""

    value: float
    moe: float

    @property
    def standard_error(self) -> float:
        return self.moe / Z90

    @property
    def ci90(self) -> tuple[float, float]:
        return (self.value - self.moe, self.value + self.moe)

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"{self.value:,.2f} ± {self.moe:,.2f}"


def aggregate_moe(parts: list[Estimate]) -> Estimate:
    """Combine several count estimates into their sum, with the Census MOE formula.

    Census formula for an aggregated count::

        MOE(sum) = sqrt( sum of MOE_i^2 )

    This assumes the component estimates are independent. The Census notes that
    the approximation degrades when many components are summed, and that
    components which are themselves zero-estimates should be handled carefully;
    for the four attainment categories combined here the approximation is the
    Bureau's own recommended practice.
    """
    if not parts:
        raise ValueError("Cannot aggregate an empty list of estimates.")
    total = float(sum(p.value for p in parts))
    moe = float(np.sqrt(sum(p.moe ** 2 for p in parts)))
    return Estimate(value=total, moe=moe)


def proportion_moe(num: Estimate, den: Estimate) -> float:
    """MOE of a proportion ``num/den`` where the numerator is a SUBSET of the denominator.

    Census formula::

        MOE(p) = (1/Y) * sqrt( MOE(X)^2 - p^2 * MOE(Y)^2 )

    When the radicand is negative the proportion formula is undefined, and the
    Census instructs the analyst to fall back to the **ratio** formula, which
    adds instead of subtracting. That fallback is applied here and is not
    silent: it is the documented behaviour, not an exception swallow.
    """
    if den.value <= 0:
        raise ValueError("Denominator estimate must be positive to form a proportion.")
    p = num.value / den.value
    radicand = num.moe ** 2 - (p ** 2) * (den.moe ** 2)
    if radicand < 0:
        return ratio_moe(num, den)
    return float(np.sqrt(radicand) / den.value)


def proportion_moe_fallback_triggered(num: Estimate, den: Estimate) -> bool:
    """Whether :func:`proportion_moe` would fall back to the ratio formula.

    Exposed so a notebook can report **how often** the documented fallback fires
    on its actual data, rather than leaving the reader to assume it never does.
    """
    if den.value <= 0:
        raise ValueError("Denominator estimate must be positive.")
    p = num.value / den.value
    return bool(num.moe ** 2 - (p ** 2) * (den.moe ** 2) < 0)


def ratio_moe(num: Estimate, den: Estimate) -> float:
    """MOE of a ratio ``num/den`` where the numerator is NOT a subset of the denominator.

    Census formula::

        MOE(r) = (1/Y) * sqrt( MOE(X)^2 + r^2 * MOE(Y)^2 )
    """
    if den.value <= 0:
        raise ValueError("Denominator estimate must be positive to form a ratio.")
    r = num.value / den.value
    return float(np.sqrt(num.moe ** 2 + (r ** 2) * (den.moe ** 2)) / den.value)


def difference_is_significant(a: Estimate, b: Estimate, *, z: float = Z90) -> tuple[bool, float]:
    """Test whether two ACS estimates are statistically distinguishable.

    Census formula::

        Z = (X1 - X2) / sqrt( SE1^2 + SE2^2 )    with SE = MOE / 1.645

    Returns ``(significant, z_statistic)``. ``significant`` is True when
    ``|Z| > z``.

    .. warning::
       This is a pairwise test. Applying it across many pairs without a
       multiple-comparison correction inflates the false-positive rate; see
       :func:`significance_matrix`, which reports how many tests were run.
    """
    se = np.sqrt(a.standard_error ** 2 + b.standard_error ** 2)
    if se == 0:
        return (False, 0.0)
    z_stat = (a.value - b.value) / se
    return (bool(abs(z_stat) > z), float(z_stat))


def significance_matrix(estimates: dict[str, Estimate]) -> tuple[np.ndarray, list[str], int]:
    """Pairwise significance for every pair of geographies.

    Returns ``(matrix, labels, n_tests)`` where ``matrix[i, j]`` is True when
    geography *i* differs significantly from *j*. ``n_tests`` is returned so
    that the caller can state the multiple-comparison burden rather than
    ignoring it.
    """
    labels = list(estimates)
    n = len(labels)
    m = np.zeros((n, n), dtype=bool)
    for i in range(n):
        for j in range(i + 1, n):
            sig, _ = difference_is_significant(estimates[labels[i]], estimates[labels[j]])
            m[i, j] = m[j, i] = sig
    return m, labels, n * (n - 1) // 2


def aggregate_moe_bounds(parts: list[Estimate]) -> tuple[Estimate, Estimate]:
    """Bound the aggregate margin under the two extreme correlation assumptions.

    The Census aggregation formula assumes the component estimates are
    **independent**. They are not: the four attainment categories are derived
    from the same survey respondents. Rather than assert that the approximation
    is adequate, this returns both extremes so the analyst can check whether any
    conclusion depends on the assumption:

    * **lower bound** — perfect independence, margins combine in quadrature
      (``sqrt(sum of squares)``). This is the Census formula.
    * **upper bound** — perfect positive correlation, margins add linearly
      (``sum``). No real dataset is worse than this.

    The truth lies between. If a conclusion holds at the upper bound, the
    independence assumption is not load-bearing for it.
    """
    if not parts:
        raise ValueError("Cannot aggregate an empty list of estimates.")
    total = float(sum(p.value for p in parts))
    return (
        Estimate(total, float(np.sqrt(sum(p.moe ** 2 for p in parts)))),
        Estimate(total, float(sum(p.moe for p in parts))),
    )


def p_value_from_z(z: float) -> float:
    """Two-sided p-value for a z statistic under the standard normal."""
    return float(2.0 * stats.norm.sf(abs(z)))


@dataclass(frozen=True)
class CorrectionResult:
    """Outcome of a multiple-comparison procedure."""

    method: str
    alpha: float
    n_tests: int
    n_significant_raw: int
    n_significant_corrected: int
    rejected: np.ndarray

    @property
    def n_withdrawn(self) -> int:
        return self.n_significant_raw - self.n_significant_corrected

    def render(self) -> str:  # pragma: no cover - display helper
        return (
            f"{self.method} at alpha = {self.alpha:.2f} over {self.n_tests:,} tests: "
            f"{self.n_significant_raw:,} significant uncorrected -> "
            f"{self.n_significant_corrected:,} after correction "
            f"({self.n_withdrawn:,} withdrawn)."
        )


def holm_bonferroni(pvalues: np.ndarray, alpha: float = 0.10) -> CorrectionResult:
    """Holm's step-down procedure. Controls the family-wise error rate.

    Strictly more powerful than Bonferroni and makes no independence assumption.
    Use when a false positive anywhere in the family is costly.
    """
    p = np.asarray(pvalues, dtype=float)
    n = p.size
    order = np.argsort(p)
    rejected = np.zeros(n, dtype=bool)
    for rank, idx in enumerate(order):
        if p[idx] <= alpha / (n - rank):
            rejected[idx] = True
        else:
            break  # step-down: once one fails, all larger p-values fail
    return CorrectionResult("Holm-Bonferroni (FWER)", alpha, n,
                            int((p <= alpha).sum()), int(rejected.sum()), rejected)


def benjamini_hochberg(pvalues: np.ndarray, alpha: float = 0.10) -> CorrectionResult:
    """Benjamini-Hochberg step-up procedure. Controls the false discovery rate.

    Less conservative than Holm. Appropriate when the family is large and a
    bounded *proportion* of false positives is tolerable, which is the usual
    situation for an exploratory table of many geographies.
    """
    p = np.asarray(pvalues, dtype=float)
    n = p.size
    order = np.argsort(p)
    thresholds = alpha * (np.arange(1, n + 1) / n)
    passing = p[order] <= thresholds
    rejected = np.zeros(n, dtype=bool)
    if passing.any():
        cutoff = np.max(np.flatnonzero(passing))
        rejected[order[: cutoff + 1]] = True
    return CorrectionResult("Benjamini-Hochberg (FDR)", alpha, n,
                            int((p <= alpha).sum()), int(rejected.sum()), rejected)
