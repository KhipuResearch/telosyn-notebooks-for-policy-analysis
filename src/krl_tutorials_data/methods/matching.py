"""Propensity scores, matching, inverse-probability weighting, balance.

Estimand
    ``att_from_matches`` estimates the average effect on the treated (ATT);
    ``ipw_effect`` estimates the ATE or ATT by Hajek-normalised weights.

Identifying assumption
    **Selection on observables**: conditional on the covariates, treatment is
    independent of potential outcomes, and every unit has a propensity strictly
    inside (0, 1). **Neither can be tested here.** Balance on what was measured
    says nothing about what was not; the sensitivity analysis a notebook needs
    for that (Rosenbaum bounds) is a separate card and is not in this module.

Estimators and their limits
    * The score is a logit fitted by Newton-Raphson. Perfect separation raises
      ``RuntimeError``; a degenerate score is never returned.
    * Matching is 1:1 nearest neighbour on the score (or its logit), with a
      caliper in score units or, on the logit scale, in standard deviations of
      the logit. With replacement is the default; without replacement is greedy
      in input order and therefore order-dependent, which is documented rather
      than hidden.
    * The ATT standard error from matches is the sample standard error of the
      pair differences. With replacement a control can appear in several pairs,
      so that is **not** the Abadie-Imbens variance and ignores both the reuse
      and the estimation of the score; it is an approximation and is labelled
      as one.
    * The IPW standard error is the influence-function variance treating the
      propensity as known, so it ignores score estimation.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
from dataclasses import dataclass
from typing import Literal, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

Float = NDArray[np.float64]
Int = NDArray[np.intp]
_EPS = 1e-10


@dataclass(frozen=True)
class LogitFit:
    """A fitted logistic propensity model; ``coef[0]`` is the intercept."""

    coef: Float
    propensity: Float
    n_iter: int


@dataclass(frozen=True)
class MatchResult:
    """Matched index pairs; ``treated[i]`` is matched to ``control[i]``."""

    treated: Int
    control: Int
    distance: Float
    n_dropped: int


@dataclass(frozen=True)
class AttResult:
    """An ATT from matched pairs."""

    estimate: float
    se: float
    n_pairs: int


@dataclass(frozen=True)
class IpwResult:
    """An inverse-probability-weighted effect."""

    estimate: float
    se: float
    n_used: int
    n_trimmed: int


@dataclass(frozen=True)
class BalanceRow:
    """Standardised mean difference of one covariate."""

    name: str
    smd: float


@dataclass(frozen=True)
class OverlapData:
    """Histogram data for an overlap figure, and the common-support interval."""

    edges: Float
    counts_treated: Int
    counts_control: Int
    common_support: tuple[float, float]


def _binary(d: ArrayLike) -> Float:
    dd = np.asarray(d, dtype=float)
    if dd.ndim != 1 or not np.all(np.isin(dd, (0.0, 1.0))):
        raise ValueError("treatment must be a one-dimensional binary (0/1) array")
    if dd.min() == dd.max():
        raise ValueError("treatment must contain both treated and control units")
    return dd


def logit_propensity(
    x: ArrayLike, d: ArrayLike, *, max_iter: int = 100, tol: float = 1e-10
) -> LogitFit:
    """Logistic regression of ``d`` on ``x`` with an intercept (Newton-Raphson)."""
    dd = _binary(d)
    xx = np.asarray(x, dtype=float)
    if xx.ndim == 1:
        xx = xx[:, None]
    if xx.shape[0] != dd.shape[0]:
        raise ValueError("x and d must have the same number of rows")
    if not np.all(np.isfinite(xx)):
        raise ValueError("x contains non-finite values; none are dropped silently")
    design = np.column_stack([np.ones(dd.shape[0]), xx])
    beta = np.zeros(design.shape[1])
    for it in range(1, max_iter + 1):
        p = 1.0 / (1.0 + np.exp(-(design @ beta)))
        w = p * (1.0 - p)
        if w.max() < _EPS:
            raise RuntimeError("perfect separation: fitted probabilities collapsed to 0 or 1")
        step = np.linalg.solve(design.T @ (design * w[:, None]), design.T @ (dd - p))
        beta = beta + step
        if np.abs(step).max() < tol:
            break
    else:
        raise RuntimeError("logit did not converge; the score may be separable (separation)")
    p = 1.0 / (1.0 + np.exp(-(design @ beta)))
    return LogitFit(coef=beta, propensity=p, n_iter=it)


def nearest_neighbour_match(
    score: ArrayLike,
    d: ArrayLike,
    *,
    caliper: float | None = None,
    replace: bool = True,
    scale: Literal["logit", "raw"] = "logit",
) -> MatchResult:
    """1:1 nearest-neighbour matching of treated units to controls on ``score``.

    ``scale="logit"`` matches on ``logit(score)`` and interprets ``caliper`` in
    standard deviations of the logit; ``scale="raw"`` matches on the score and
    interprets ``caliper`` in score units. Treated units with no control inside
    the caliper are dropped and counted. Without replacement the match is
    greedy in input order.
    """
    dd = _binary(d)
    s = np.asarray(score, dtype=float)
    if s.shape != dd.shape or not np.all(np.isfinite(s)):
        raise ValueError("score must be finite and the same length as d")
    if scale not in ("logit", "raw"):
        raise ValueError(f"scale must be 'logit' or 'raw', not {scale!r}")
    if caliper is not None and caliper <= 0:
        raise ValueError("caliper must be positive")
    metric = s
    limit = caliper
    if scale == "logit":
        clipped = np.clip(s, _EPS, 1 - _EPS)
        metric = np.log(clipped / (1 - clipped))
        if caliper is not None:
            limit = caliper * float(np.std(metric))
    t_idx = np.flatnonzero(dd == 1)
    c_idx = np.flatnonzero(dd == 0)
    available = np.ones(c_idx.size, dtype=bool)
    pairs_t: list[int] = []
    pairs_c: list[int] = []
    dist: list[float] = []
    for i in t_idx:
        gaps = np.abs(metric[c_idx] - metric[i])
        if not replace:
            gaps = np.where(available, gaps, np.inf)
        j = int(np.argmin(gaps))
        if not np.isfinite(gaps[j]) or (limit is not None and gaps[j] > limit):
            continue
        if not replace:
            available[j] = False
        pairs_t.append(int(i))
        pairs_c.append(int(c_idx[j]))
        dist.append(float(gaps[j]))
    return MatchResult(
        treated=np.asarray(pairs_t, dtype=np.intp), control=np.asarray(pairs_c, dtype=np.intp),
        distance=np.asarray(dist), n_dropped=int(t_idx.size - len(pairs_t)),
    )


def att_from_matches(y: ArrayLike, d: ArrayLike, match: MatchResult) -> AttResult:
    """Mean of matched-pair differences ``y_treated - y_control`` and its approximate SE."""
    yy = np.asarray(y, dtype=float)
    dd = _binary(d)
    if yy.shape != dd.shape or not np.all(np.isfinite(yy)):
        raise ValueError("y must be finite and the same length as d")
    if match.treated.size == 0:
        raise ValueError("no matched pairs: nothing to average")
    diff = yy[match.treated] - yy[match.control]
    n = diff.size
    se = float(np.std(diff, ddof=1) / np.sqrt(n)) if n > 1 else float("nan")
    return AttResult(estimate=float(diff.mean()), se=se, n_pairs=int(n))


def ipw_effect(
    y: ArrayLike,
    d: ArrayLike,
    propensity: ArrayLike,
    *,
    estimand: Literal["ate", "att"] = "ate",
    trim: tuple[float, float] | None = None,
) -> IpwResult:
    """Hajek-normalised IPW estimate of the ATE or ATT with an influence-function SE.

    ``trim`` drops units whose propensity lies outside ``[low, high]`` and
    reports how many; nothing is dropped otherwise.
    """
    if estimand not in ("ate", "att"):
        raise ValueError(f"estimand must be 'ate' or 'att', not {estimand!r}")
    yy = np.asarray(y, dtype=float)
    dd = _binary(d)
    p = np.asarray(propensity, dtype=float)
    if yy.shape != dd.shape or p.shape != dd.shape:
        raise ValueError("y, d and propensity must have the same length")
    if not (np.all(np.isfinite(yy)) and np.all(np.isfinite(p))):
        raise ValueError("y and propensity must be finite")
    if np.any(p <= 0) or np.any(p >= 1):
        raise ValueError("propensity must lie strictly inside (0, 1)")
    keep = np.ones(yy.shape, dtype=bool) if trim is None else (p >= trim[0]) & (p <= trim[1])
    n_trimmed = int((~keep).sum())
    yy, dd, p = yy[keep], dd[keep], p[keep]
    if dd.min() == dd.max():
        raise ValueError("trimming left only one treatment group")
    n = yy.size
    if estimand == "ate":
        w1, w0 = dd / p, (1 - dd) / (1 - p)
    else:
        w1, w0 = dd, (1 - dd) * p / (1 - p)
    mu1 = float(np.sum(w1 * yy) / w1.sum())
    mu0 = float(np.sum(w0 * yy) / w0.sum())
    psi = n * (w1 * (yy - mu1) / w1.sum() - w0 * (yy - mu0) / w0.sum())
    return IpwResult(
        estimate=mu1 - mu0, se=float(np.sqrt(np.mean(psi**2) / n)), n_used=int(n),
        n_trimmed=n_trimmed,
    )


def standardized_mean_difference(
    x: ArrayLike, d: ArrayLike, *, weights: ArrayLike | None = None
) -> float:
    """``(mean_treated - mean_control) / sqrt((var_treated + var_control) / 2)``.

    With ``weights`` the means and variances are weighted; the pooled
    denominator uses the **unweighted** variances, the convention that keeps the
    scale fixed so before and after are comparable. Returns 0 when both groups
    are constant and equal; raises when only one group is present.
    """
    xx = np.asarray(x, dtype=float)
    dd = _binary(d)
    ww = np.ones_like(xx) if weights is None else np.asarray(weights, dtype=float)
    if xx.shape != dd.shape or ww.shape != xx.shape or not np.all(np.isfinite(xx)):
        raise ValueError("x, d and weights must be finite and the same length")
    t, c = dd == 1, dd == 0
    m1 = float(np.average(xx[t], weights=ww[t]))
    m0 = float(np.average(xx[c], weights=ww[c]))
    pooled = np.sqrt((np.var(xx[t], ddof=1) + np.var(xx[c], ddof=1)) / 2.0) \
        if t.sum() > 1 and c.sum() > 1 else 0.0
    if pooled == 0.0:
        return 0.0 if m1 == m0 else float("inf") * np.sign(m1 - m0)
    return (m1 - m0) / float(pooled)


def balance_table(
    x: ArrayLike, d: ArrayLike, *, names: Sequence[str], weights: ArrayLike | None = None
) -> list[BalanceRow]:
    """One :func:`standardized_mean_difference` per column of ``x``."""
    xx = np.asarray(x, dtype=float)
    if xx.ndim != 2 or xx.shape[1] != len(names):
        raise ValueError("names must give one name per column of x")
    return [
        BalanceRow(str(nm), standardized_mean_difference(xx[:, j], d, weights=weights))
        for j, nm in enumerate(names)
    ]


def overlap_data(score: ArrayLike, d: ArrayLike, *, bins: int = 20) -> OverlapData:
    """Counts per bin for treated and control scores, and the common-support interval."""
    if bins < 1:
        raise ValueError("bins must be at least 1")
    dd = _binary(d)
    s = np.asarray(score, dtype=float)
    if s.shape != dd.shape or not np.all(np.isfinite(s)):
        raise ValueError("score must be finite and the same length as d")
    edges = np.linspace(float(s.min()), float(s.max()), bins + 1)
    ct, _ = np.histogram(s[dd == 1], bins=edges)
    cc, _ = np.histogram(s[dd == 0], bins=edges)
    support = (
        float(max(s[dd == 1].min(), s[dd == 0].min())),
        float(min(s[dd == 1].max(), s[dd == 0].max())),
    )
    return OverlapData(edges=edges, counts_treated=ct.astype(np.intp),
                       counts_control=cc.astype(np.intp), common_support=support)
