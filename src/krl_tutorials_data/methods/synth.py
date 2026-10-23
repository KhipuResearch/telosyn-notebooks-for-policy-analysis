"""Synthetic control: simplex-constrained weights, placebos, RMSPE ratio.

Estimand
    For one treated unit and a pool of untreated donors, the gap between the
    treated series and a weighted average of donor series after the
    intervention, where the weights make the weighted average track the treated
    unit before it.

Identifying assumption
    The donor combination that fits the *pre*-period would have continued to
    track the treated unit absent treatment, and no donor was itself affected.
    Neither is testable here. A good pre-period fit is necessary, not
    sufficient: it is reported (``pre_rmspe``) and never read as proof.

Estimator
    ``min_w sum_k v_k (x1_k - X0_k . w)^2`` subject to ``w >= 0, sum w = 1``,
    solved by SLSQP, from a uniform start and then from the best single donor,
    after scaling by the treated series' root mean square. Predictors are the
    pre-period outcomes, optionally with
    covariate rows weighted by ``covariate_weight``. Optimality is checked
    against the first-order conditions rather than the solver's own flag, and a
    vector that fails them is not returned.

Inference
    Permutation, not asymptotic. :func:`placebo_in_space` re-estimates the
    effect treating each donor as the treated unit and reports where the real
    unit's post/pre RMSPE ratio ranks; the p-value is ``rank / (n_placebos+1)``
    and is valid only for the donor pool as constructed. :func:`placebo_in_time`
    moves the intervention date into the pre-period.

Reference (recalled, not verified in this build): Abadie, Diamond &
Hainmueller (2010), JASA 105(490).

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

# Estimator signatures carry the series, the split and the options explicitly.
# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
# pylint: disable=too-many-instance-attributes
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import minimize  # type: ignore[import-untyped]

Float = NDArray[np.float64]


@dataclass(frozen=True)
class SynthFit:
    """A fitted synthetic control and its gap series."""

    weights: Float
    synthetic: Float
    gap: Float
    pre_rmspe: float
    post_rmspe: float
    rmspe_ratio: float
    n_pre: int
    objective: float


@dataclass(frozen=True)
class SpacePlacebo:
    """The permutation distribution over donors and where the treated unit ranks."""

    treated_ratio: float
    donor_ratios: Float
    rank: int
    p_value: float
    n_placebos: int


def rmspe_ratio(pre: float, post: float) -> float:
    """``post / pre``; ``inf`` when the pre-period fit is exact and the post gap is not."""
    if pre == 0.0:
        return float("inf") if post > 0.0 else 1.0
    return post / pre


def _series(values: ArrayLike, name: str, ndim: int) -> Float:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != ndim:
        raise ValueError(f"{name} must be {ndim}-dimensional")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} contains non-finite values; none are dropped silently")
    return arr


def fit_weights(
    x_treated: ArrayLike, x_donors: ArrayLike, *, v: ArrayLike | None = None
) -> tuple[Float, float]:
    """Simplex weights minimising the ``v``-weighted squared predictor distance.

    ``x_treated`` is ``(K,)`` and ``x_donors`` is ``(K, J)``. Returns the weight
    vector and the minimised objective on the *original* scale. Raises
    ``RuntimeError`` when no start reaches first-order optimality.
    """
    x1 = _series(x_treated, "x_treated", 1)
    x0 = _series(x_donors, "x_donors", 2)
    if x0.shape[0] != x1.shape[0] or x0.shape[1] < 1:
        raise ValueError("x_donors must be (K, J) with J >= 1 donor and K matching x_treated")
    k, j = x0.shape
    vv = np.ones(k) if v is None else _series(v, "v", 1)
    if vv.shape != (k,) or np.any(vv < 0):
        raise ValueError("v must be non-negative with one entry per predictor")
    scale = max(float(np.sqrt(np.mean(x1**2))), 1e-12)
    a, b = x0 / scale, x1 / scale
    sqrt_v = np.sqrt(vv)

    def objective(w: Float) -> float:
        diff = sqrt_v * (b - a @ w)
        return float(diff @ diff)

    def gradient(w: Float) -> Float:
        return -2.0 * (a.T @ (vv * (b - a @ w)))

    singles = np.argmin([objective(np.eye(j)[i]) for i in range(j)])
    starts = [np.full(j, 1.0 / j), np.eye(j)[singles]]
    best: Float | None = None
    for start in starts:
        result = minimize(
            objective, start, jac=gradient, method="SLSQP", bounds=[(0.0, 1.0)] * j,
            constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1.0,
                          "jac": lambda w: np.ones(j)}],
            options={"ftol": 1e-15, "maxiter": 2000},
        )
        candidate = np.clip(result.x, 0.0, 1.0)
        candidate = candidate / candidate.sum()
        if _kkt_gap(candidate, gradient(candidate)) <= 1e-6 * (1.0 + objective(candidate)):
            best = candidate
            break
    if best is None:
        raise RuntimeError(
            "synthetic-control weights did not reach first-order optimality from any start; "
            "the donor pool may be degenerate"
        )
    return best, float(objective(best) * scale**2)


def _kkt_gap(w: Float, grad: Float) -> float:
    """Violation of the simplex first-order conditions, independent of the solver's flag.

    At an optimum every donor with positive weight has the same (minimal)
    gradient component, and no donor with zero weight has a smaller one.
    """
    support = w > 1e-8
    low = float(grad.min())
    return float(grad[support].max() - low) if support.any() else float("inf")


def _rmspe(gap: Float) -> float:
    return float(np.sqrt(np.mean(gap**2))) if gap.size else float("nan")


def _check_split(treated: Float, donors: Float, n_pre: int) -> None:
    if donors.shape[0] != treated.shape[0]:
        raise ValueError("treated and donors must have the same number of periods")
    if donors.shape[1] < 1:
        raise ValueError("at least one donor is required")
    if not 2 <= n_pre < treated.shape[0]:
        raise ValueError(
            f"n_pre must leave at least two pre-period and one post-period observation; "
            f"got n_pre={n_pre} with {treated.shape[0]} periods"
        )


def synthetic_control(
    treated: ArrayLike,
    donors: ArrayLike,
    *,
    n_pre: int,
    covariates_treated: ArrayLike | None = None,
    covariates_donors: ArrayLike | None = None,
    covariate_weight: float = 1.0,
) -> SynthFit:
    """Fit weights on the first ``n_pre`` periods and extend the gap to all periods.

    ``treated`` is ``(T,)`` and ``donors`` is ``(T, J)``. Covariates, if given,
    are appended to the pre-period outcomes as extra predictors with relative
    weight ``covariate_weight`` per row.
    """
    y1 = _series(treated, "treated", 1)
    y0 = _series(donors, "donors", 2)
    _check_split(y1, y0, n_pre)
    x1, x0 = y1[:n_pre], y0[:n_pre]
    v = np.ones(n_pre)
    if (covariates_treated is None) != (covariates_donors is None):
        raise ValueError("covariates_treated and covariates_donors must be given together")
    if covariates_treated is not None and covariates_donors is not None:
        c1 = _series(covariates_treated, "covariates_treated", 1)
        c0 = _series(covariates_donors, "covariates_donors", 2)
        if c0.shape != (c1.shape[0], y0.shape[1]):
            raise ValueError("covariates_donors must be (K, J) matching the donors")
        x1 = np.concatenate([x1, c1])
        x0 = np.vstack([x0, c0])
        v = np.concatenate([v, np.full(c1.shape[0], float(covariate_weight))])
    weights, objective = fit_weights(x1, x0, v=v)
    synthetic = y0 @ weights
    gap = y1 - synthetic
    pre, post = _rmspe(gap[:n_pre]), _rmspe(gap[n_pre:])
    return SynthFit(
        weights=weights, synthetic=synthetic, gap=gap, pre_rmspe=pre, post_rmspe=post,
        rmspe_ratio=rmspe_ratio(pre, post), n_pre=n_pre, objective=objective,
    )


def placebo_in_space(
    treated: ArrayLike,
    donors: ArrayLike,
    *,
    n_pre: int,
    max_pre_ratio: float | None = None,
    covariates_treated: ArrayLike | None = None,
    covariates_donors: ArrayLike | None = None,
    covariate_weight: float = 1.0,
) -> SpacePlacebo:
    """Re-estimate the effect with each donor in the treated role.

    Each placebo's donor pool is the other donors (the real treated unit is
    excluded). ``max_pre_ratio`` drops placebos whose pre-period RMSPE exceeds
    that multiple of the treated unit's, the usual guard against comparing the
    treated unit's good fit with placebos that never fitted. ``rank`` is 1 for
    the largest ratio; ``p_value = rank / (n_placebos + 1)`` in the sense of
    ``(1 + #placebos with ratio >= treated) / (1 + n_placebos)``.

    If covariates are given, **every** fit, the real one and each placebo, uses them
    with the same ``covariate_weight``: a placebo distribution from a different
    specification than the estimate would not be a distribution for that estimate.
    A placebo donor's covariates are its own column of ``covariates_donors``.
    """
    y1 = _series(treated, "treated", 1)
    y0 = _series(donors, "donors", 2)
    _check_split(y1, y0, n_pre)
    if y0.shape[1] < 2:
        raise ValueError("an in-space placebo needs at least two donors")
    if (covariates_treated is None) != (covariates_donors is None):
        raise ValueError("covariates_treated and covariates_donors must be given together")
    c1 = c0 = None
    if covariates_treated is not None and covariates_donors is not None:
        c1 = _series(covariates_treated, "covariates_treated", 1)
        c0 = _series(covariates_donors, "covariates_donors", 2)
        if c0.shape != (c1.shape[0], y0.shape[1]):
            raise ValueError("covariates_donors must be (K, J) matching the donors")
    actual = synthetic_control(
        y1, y0, n_pre=n_pre, covariates_treated=c1, covariates_donors=c0,
        covariate_weight=covariate_weight,
    )
    ratios: list[float] = []
    for j in range(y0.shape[1]):
        rest = np.delete(y0, j, axis=1)
        fit = synthetic_control(
            y0[:, j], rest, n_pre=n_pre,
            covariates_treated=None if c0 is None else c0[:, j],
            covariates_donors=None if c0 is None else np.delete(c0, j, axis=1),
            covariate_weight=covariate_weight,
        )
        limit = None if max_pre_ratio is None else max_pre_ratio * max(actual.pre_rmspe, 1e-12)
        if limit is not None and fit.pre_rmspe > limit:
            continue
        ratios.append(fit.rmspe_ratio)
    donor_ratios = np.asarray(ratios, dtype=float)
    exceed = int(np.sum(donor_ratios >= actual.rmspe_ratio))
    return SpacePlacebo(
        treated_ratio=actual.rmspe_ratio, donor_ratios=donor_ratios, rank=exceed + 1,
        p_value=(exceed + 1) / (donor_ratios.size + 1), n_placebos=int(donor_ratios.size),
    )


def placebo_in_time(
    treated: ArrayLike,
    donors: ArrayLike,
    *,
    n_pre: int,
    placebo_pre: int,
    covariates_treated: ArrayLike | None = None,
    covariates_donors: ArrayLike | None = None,
    covariate_weight: float = 1.0,
) -> SynthFit:
    """Fit on the first ``placebo_pre`` periods and score the rest of the pre-period.

    The real post-period is discarded, so a gap here is a gap that appears
    where no intervention occurred. ``post_rmspe`` of the returned fit is the
    placebo effect size over ``[placebo_pre, n_pre)``. Covariates, if given, must
    be computed over the periods before ``placebo_pre`` only: a covariate that
    looks into the discarded periods would leak them into the weights.
    """
    y1 = _series(treated, "treated", 1)
    y0 = _series(donors, "donors", 2)
    _check_split(y1, y0, n_pre)
    if not 2 <= placebo_pre < n_pre:
        raise ValueError(f"placebo_pre must satisfy 2 <= placebo_pre < n_pre={n_pre}")
    return synthetic_control(
        y1[:n_pre], y0[:n_pre], n_pre=placebo_pre, covariates_treated=covariates_treated,
        covariates_donors=covariates_donors, covariate_weight=covariate_weight,
    )
