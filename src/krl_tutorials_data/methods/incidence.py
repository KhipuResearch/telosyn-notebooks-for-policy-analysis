"""Distributional incidence on weighted cells: group boundaries inside bins, Kish intervals.

Estimand
    The share of a weighted total that falls in each of ``k`` equal-population groups of a
    continuous variable (quintiles of income), and the interval a *simple random sample with
    the same weights* would put around a weighted share.

Assumptions
    The variable is known only to its bin, so people inside a bin are taken to be spread
    **uniformly across it**; the bin that holds each group boundary is reported so the reader
    can see how much population that assumption governs. The Kish interval **likely understates**
    the uncertainty and is not a guaranteed bound: it treats the sample as a simple random sample
    whose weights only change the effective sample size, and ignores clustering (which widens it) and
    stratification (which narrows it). It is not a substitute for replicate weights and is never called one.

Estimators
    ``n_eff = (sum w)^2 / sum w^2``; ``se = sqrt(p (1 - p) / n_eff)`` for a weighted share
    ``p``; the 95% interval is ``p +/- 1.959964 se`` clipped to [0, 1]. A group's fraction of a
    bin is the overlap of the bin's cumulative-weight interval with the group's.

Nothing here performs I/O.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd

#: Standard normal 97.5th percentile.
Z95: Final[float] = 1.959963984540054


@dataclass(frozen=True)
class ShareResult:
    """A weighted share with its simple-random-sample (lower-bound) interval."""

    share: float
    se: float
    low: float
    high: float
    n_effective: float


#: ASEC successive-difference replication: 160 replicates and the factor 4/160 (Census Bureau, "Estimating ASEC
#: Variances with Replicate Weights", formula 1: var(theta_0) = (4 / 160) * sum_{i=1..160} (theta_i - theta_0)^2).
ASEC_REPLICATES: Final[int] = 160
ASEC_FACTOR: Final[float] = 4.0 / ASEC_REPLICATES


def replicate_variance(estimate: float, replicates: "np.ndarray | list[float]") -> float:
    """Variance of ``estimate`` from its 160 replicate estimates: (4/160) * sum (replicate - estimate)^2.

    The deviations are taken about the full-sample estimate, not the replicate mean, as the Bureau's
    formula has it. Raises unless exactly 160 replicates are given.
    """
    reps = np.asarray(replicates, dtype=float)
    if reps.shape != (ASEC_REPLICATES,):
        raise ValueError(f"the ASEC formula needs exactly {ASEC_REPLICATES} replicate estimates; got {reps.shape}.")
    return float(ASEC_FACTOR * np.sum((reps - estimate) ** 2))


def replicate_se(estimate: float, replicates: "np.ndarray | list[float]") -> float:
    """Standard error: the square root of :func:`replicate_variance`."""
    return float(np.sqrt(replicate_variance(estimate, replicates)))


def replicate_interval(estimate: float, replicates: "np.ndarray | list[float]") -> tuple[float, float]:
    """95% interval ``estimate +/- 1.96 * SE`` (normal; the instructions give no degrees of freedom)."""
    se = replicate_se(estimate, replicates)
    return estimate - Z95 * se, estimate + Z95 * se


def kish_effective_n(*, sum_w: float, sum_w2: float) -> float:
    """Kish's effective sample size, ``(sum w)^2 / sum w^2``."""
    if not (sum_w > 0.0 and sum_w2 > 0.0):
        raise ValueError("sum_w and sum_w2 must be positive.")
    return sum_w * sum_w / sum_w2


def share_with_lower_bound(*, group_w: float, total_w: float, total_w2: float) -> ShareResult:
    """Weighted share of ``group_w`` in ``total_w``, with its lower-bound 95% interval."""
    if not 0.0 <= group_w <= total_w:
        raise ValueError("group_w must lie between 0 and total_w.")
    n_eff = kish_effective_n(sum_w=total_w, sum_w2=total_w2)
    p = group_w / total_w
    se = float(np.sqrt(p * (1.0 - p) / n_eff))
    return ShareResult(
        share=p,
        se=se,
        low=max(0.0, p - Z95 * se),
        high=min(1.0, p + Z95 * se),
        n_effective=n_eff,
    )


def bin_group_fractions(
    bins: pd.DataFrame, *, width: float, groups: int = 5
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split each bin of a weighted distribution across ``groups`` equal-weight groups.

    ``bins`` has ``bin`` (the lower edge) and ``weight`` (total weight in the bin), one row
    per bin. Returns ``(fractions, boundaries)``: ``fractions`` is indexed by bin with one
    column per group, each row summing to 1, so a cell's weight in group ``g`` is its
    weight times ``fractions.loc[bin, g]``; ``boundaries`` has, for each of the
    ``groups - 1`` cut points, its ``boundary`` value (linear inside its bin) and the
    ``bin_share`` of the population in the bin that holds it.
    """
    if groups < 2:
        raise ValueError("groups must be at least 2.")
    if width <= 0.0:
        raise ValueError("width must be positive.")
    if bins["bin"].duplicated().any():
        raise ValueError("bins must be unique.")
    if (bins["weight"] <= 0.0).any():
        raise ValueError("every bin weight must be positive.")
    ordered = bins.sort_values("bin").reset_index(drop=True)
    w = ordered["weight"].to_numpy(dtype=float)
    cum = np.cumsum(w)
    total = float(cum[-1])
    lower = cum - w
    cuts = np.linspace(0.0, total, groups + 1)
    fractions = np.zeros((len(w), groups))
    for g in range(groups):
        overlap = np.minimum(cum, cuts[g + 1]) - np.maximum(lower, cuts[g])
        fractions[:, g] = np.clip(overlap, 0.0, None) / w
    out = pd.DataFrame(fractions, index=pd.Index(ordered["bin"].to_numpy(), name="bin"))
    targets = cuts[1:-1]
    idx = np.minimum(np.searchsorted(cum, targets, side="right"), len(w) - 1)
    boundary = ordered["bin"].to_numpy(dtype=float)[idx] + width * (targets - lower[idx]) / w[idx]
    edges = pd.DataFrame(
        {"boundary": boundary, "bin_share": w[idx] / total},
        index=pd.RangeIndex(1, groups, name="cut"),
    )
    return out, edges
