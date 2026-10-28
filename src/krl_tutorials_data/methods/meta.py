"""Meta-analytic pooling: fixed effect, DerSimonian-Laird random effects, Egger.

Estimand
    The weighted mean of study effects: under the fixed-effect model, the one
    common effect; under random effects, the *mean of a distribution* of study
    effects whose between-study variance is ``tau^2``.

Assumptions
    Studies are independent. **When the "studies" are re-estimates against a
    shared control pool they are not**, and every interval here is too narrow;
    the notebook that does that says so. Normality of study estimates with
    known variances is taken as given (the standard errors are plug-ins).

Estimators
    ``tau^2`` by the DerSimonian-Laird moment estimator,
    ``max(0, (Q - df) / C)``, ``C = sum w - sum w^2 / sum w``. ``I^2`` is
    ``max(0, (Q - df) / Q)``. The random-effects interval uses the normal
    quantile and no Hartung-Knapp adjustment: with few studies it is narrow,
    and that is stated rather than corrected. Egger's test regresses
    ``y/se`` on ``1/se`` and tests the intercept; it has low power with fewer
    than about ten studies and the notebook reports the count.

References (author, year, venue and pages checked against the publishers' records on 2026-10-28):
DerSimonian & Laird (1986) Controlled Clinical Trials 7(3):177-188; Egger, Davey Smith, Schneider &
Minder (1997) BMJ 315:629-634; Higgins, Thompson & Spiegelhalter (2009) J R Stat Soc A 172(1):137-159.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

# pylint: disable=too-many-instance-attributes
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import stats  # type: ignore[import-untyped]

Float = NDArray[np.float64]


@dataclass(frozen=True)
class MetaResult:
    """A pooled estimate under fixed and random effects, with heterogeneity."""

    fixed_effect: float
    fixed_se: float
    random_effect: float
    random_se: float
    tau2: float
    q: float
    df: int
    i2: float
    p_heterogeneity: float
    n_studies: int
    weights_fixed: Float
    weights_random: Float


@dataclass(frozen=True)
class EggerResult:
    """Egger's regression test for small-study effects."""

    intercept: float
    slope: float
    se: float
    t_stat: float
    p_value: float
    df: int


def _inputs(y: ArrayLike, se: ArrayLike, minimum: int, word: str) -> tuple[Float, Float]:
    yy = np.asarray(y, dtype=float)
    ss = np.asarray(se, dtype=float)
    if yy.ndim != 1 or yy.shape != ss.shape:
        raise ValueError("y and se must be one-dimensional and of the same length")
    if not (np.all(np.isfinite(yy)) and np.all(np.isfinite(ss))):
        raise ValueError("y and se contain non-finite values; none are dropped silently")
    if np.any(ss <= 0):
        raise ValueError("standard errors must be positive")
    if yy.size < minimum:
        raise ValueError(f"at least {word} studies are required; got {yy.size}")
    return yy, ss


def pool(y: ArrayLike, se: ArrayLike) -> MetaResult:
    """Fixed-effect and DerSimonian-Laird random-effects pooling of ``y`` with ``se``."""
    yy, ss = _inputs(y, se, 2, "two")
    w = 1.0 / ss**2
    fixed = float(np.sum(w * yy) / w.sum())
    q = float(np.sum(w * (yy - fixed) ** 2))
    df = yy.size - 1
    c = float(w.sum() - np.sum(w**2) / w.sum())
    tau2 = max(0.0, (q - df) / c) if c > 0 else 0.0
    w_re = 1.0 / (ss**2 + tau2)
    random = float(np.sum(w_re * yy) / w_re.sum())
    return MetaResult(
        fixed_effect=fixed, fixed_se=float(np.sqrt(1.0 / w.sum())),
        random_effect=random, random_se=float(np.sqrt(1.0 / w_re.sum())),
        tau2=tau2, q=q, df=df, i2=max(0.0, (q - df) / q) if q > 0 else 0.0,
        p_heterogeneity=float(stats.chi2.sf(q, df)), n_studies=int(yy.size),
        weights_fixed=w, weights_random=w_re,
    )


def prediction_interval(result: MetaResult, level: float = 0.95) -> tuple[float, float]:
    """Interval for the effect in a *new* study under the random-effects model.

    ``mean +/- t(k - 2) * sqrt(tau^2 + SE^2)`` with ``k = result.n_studies`` studies
    (Higgins, Thompson & Spiegelhalter 2009, J R Stat Soc A 172(1):137-159; the t(k - 2) form was
    checked against a published description of it, not against the paper's text).
    It is wider than the confidence interval for the mean whenever ``tau^2 > 0``.
    Needs at least three studies: with two there are no degrees of freedom.

    It is approximate: it treats ``tau^2`` as known (it is the DerSimonian-Laird estimate), assumes the
    studies are independent and the new study is exchangeable with them, and covers poorly when ``k`` is
    small or the weights are unequal.
    """
    if not 0.0 < level < 1.0:
        raise ValueError(f"level must be strictly between 0 and 1, got {level!r}.")
    if result.n_studies < 3:
        raise ValueError("A prediction interval needs at least three studies.")
    t_crit = float(stats.t.ppf(0.5 + level / 2.0, result.n_studies - 2))
    half = t_crit * float(np.sqrt(result.tau2 + result.random_se**2))
    return result.random_effect - half, result.random_effect + half


def egger_test(y: ArrayLike, se: ArrayLike) -> EggerResult:
    """Regress ``y/se`` on ``1/se``; the intercept is the small-study asymmetry."""
    yy, ss = _inputs(y, se, 3, "three")
    z, precision = yy / ss, 1.0 / ss
    design = np.column_stack([np.ones_like(precision), precision])
    beta, *_ = np.linalg.lstsq(design, z, rcond=None)
    resid = z - design @ beta
    df = yy.size - 2
    sigma2 = float(resid @ resid) / df
    cov = sigma2 * np.linalg.inv(design.T @ design)
    se_int = float(np.sqrt(max(cov[0, 0], 0.0)))
    t = float(beta[0] / se_int) if se_int > 0 else float("inf") * np.sign(beta[0])
    p = float(2 * stats.t.sf(abs(t), df)) if np.isfinite(t) else 0.0
    return EggerResult(
        intercept=float(beta[0]), slope=float(beta[1]), se=se_int, t_stat=t, p_value=p, df=df
    )


def leave_one_out(y: ArrayLike, se: ArrayLike) -> list[MetaResult]:
    """:func:`pool` with each study omitted in turn, in input order."""
    yy, ss = _inputs(y, se, 3, "three")
    return [pool(np.delete(yy, i), np.delete(ss, i)) for i in range(yy.size)]
