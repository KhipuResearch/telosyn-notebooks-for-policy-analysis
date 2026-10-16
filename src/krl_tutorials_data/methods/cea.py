"""Cost-effectiveness: ICER, efficient frontier, net benefit, acceptability curve.

Estimand
    Incremental cost per unit of incremental effect between two strategies, and
    the probability that one is cost-effective at a stated willingness to pay.

What this is not
    The ratio is a **ratio of two estimates** and its sampling distribution is
    not normal; a confidence interval on it is not offered. Uncertainty is
    carried by draws (:func:`psa_normal`) and summarised by
    :func:`ceac`, which is the probability that net monetary benefit is
    positive. The draws are independent-normal inputs the caller supplies the
    moments of; they are inference randomness, seeded at the call, and are not
    data.

Conventions
    Effect is "more is better". An ICER in the south-west quadrant (cheaper
    and worse) is reported as ``icer_saving`` with a positive ratio that means
    *money saved per unit of effect given up*; it is read against the threshold
    in the opposite direction and the status says so. ``efficient_frontier``
    removes strong dominance (costlier and no better) and then extended
    dominance (an ICER that does not exceed its predecessor's).

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

Float = NDArray[np.float64]


@dataclass(frozen=True)
class Icer:
    """An incremental comparison of one strategy against a reference."""

    delta_cost: float
    delta_effect: float
    ratio: float | None
    status: str


@dataclass(frozen=True)
class FrontierStep:
    """One strategy on the efficient frontier and its ICER against the previous step."""

    name: str
    cost: float
    effect: float
    icer: float | None


@dataclass(frozen=True)
class Ceac:
    """Probability of cost-effectiveness at each willingness-to-pay threshold."""

    thresholds: Float
    probability: Float


def icer(cost: float, effect: float, ref_cost: float, ref_effect: float) -> Icer:
    """Incremental cost-effectiveness ratio of a strategy against a reference."""
    values = (cost, effect, ref_cost, ref_effect)
    if not all(np.isfinite(v) for v in values):
        raise ValueError("cost and effect inputs must be finite")
    dc, de = cost - ref_cost, effect - ref_effect
    if de == 0:
        return Icer(dc, de, None, "no_difference_in_effect")
    if de > 0 >= dc:
        return Icer(dc, de, None, "dominant")
    if de < 0 <= dc:
        return Icer(dc, de, None, "dominated")
    return Icer(dc, de, dc / de, "icer" if de > 0 else "icer_saving")


def efficient_frontier(
    names: Sequence[str], costs: ArrayLike, effects: ArrayLike
) -> list[FrontierStep]:
    """Strategies surviving strong and extended dominance, ordered by cost."""
    c = np.asarray(costs, dtype=float)
    e = np.asarray(effects, dtype=float)
    if c.ndim != 1 or c.shape != e.shape or len(names) != c.shape[0]:
        raise ValueError("names, costs and effects must be one-dimensional and of the same length")
    if c.size == 0:
        raise ValueError("at least one strategy is required")
    if not (np.all(np.isfinite(c)) and np.all(np.isfinite(e))):
        raise ValueError("costs and effects must be finite")
    order = np.lexsort((-e, c))
    kept: list[int] = []
    best = -np.inf
    for i in order:  # strong dominance: costlier and no more effective than a kept one
        if e[i] > best:
            kept.append(int(i))
            best = e[i]
    changed = True
    while changed and len(kept) > 2:  # extended dominance: ICERs must increase
        changed = False
        slopes = [
            (c[kept[k]] - c[kept[k - 1]]) / (e[kept[k]] - e[kept[k - 1]])
            for k in range(1, len(kept))
        ]
        for k in range(1, len(slopes)):
            if slopes[k] <= slopes[k - 1]:
                del kept[k]
                changed = True
                break
    steps: list[FrontierStep] = []
    for pos, i in enumerate(kept):
        ratio = None
        if pos:
            prev = kept[pos - 1]
            ratio = float((c[i] - c[prev]) / (e[i] - e[prev]))
        steps.append(FrontierStep(str(names[i]), float(c[i]), float(e[i]), ratio))
    return steps


def net_monetary_benefit(
    delta_cost: ArrayLike, delta_effect: ArrayLike, threshold: float
) -> Float:
    """``threshold * delta_effect - delta_cost``, elementwise."""
    dc = np.asarray(delta_cost, dtype=float)
    de = np.asarray(delta_effect, dtype=float)
    if dc.shape != de.shape:
        raise ValueError("delta_cost and delta_effect must have the same length")
    return np.asarray(threshold * de - dc, dtype=float)


def ceac(delta_cost: ArrayLike, delta_effect: ArrayLike, thresholds: ArrayLike) -> Ceac:
    """Share of draws with positive net monetary benefit, at each threshold."""
    dc = np.asarray(delta_cost, dtype=float)
    de = np.asarray(delta_effect, dtype=float)
    lam = np.asarray(thresholds, dtype=float)
    if dc.shape != de.shape or dc.ndim != 1:
        raise ValueError("delta_cost and delta_effect must be one-dimensional and the same length")
    if lam.ndim != 1 or lam.size == 0:
        raise ValueError("at least one threshold is required")
    prob = np.array([float(np.mean(t * de - dc > 0)) for t in lam])
    return Ceac(thresholds=lam, probability=prob)


def psa_normal(
    mean_delta_cost: float,
    sd_delta_cost: float,
    mean_delta_effect: float,
    sd_delta_effect: float,
    *,
    correlation: float,
    n: int,
    seed: int,
) -> tuple[Float, Float]:
    """Correlated normal draws of ``(delta_cost, delta_effect)``; ``seed`` is required.

    This is a stated input distribution for probabilistic sensitivity analysis,
    not a model of the data.
    """
    if not -1.0 <= correlation <= 1.0:
        raise ValueError("correlation must lie in [-1, 1]")
    if sd_delta_cost < 0 or sd_delta_effect < 0:
        raise ValueError("standard deviations must be non-negative")
    if n < 1:
        raise ValueError("n must be at least 1")
    rng = np.random.default_rng(seed)
    z1, z2 = rng.standard_normal(n), rng.standard_normal(n)
    dc = mean_delta_cost + sd_delta_cost * z1
    de = mean_delta_effect + sd_delta_effect * (
        correlation * z1 + np.sqrt(1.0 - correlation**2) * z2
    )
    return dc, de
