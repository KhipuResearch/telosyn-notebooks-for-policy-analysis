"""Small-area pooling helpers: the standard error of an ACS proportion, and an exact reference for a normal-normal model.

Pure numpy and scipy. **Nothing here imports ``pymc``** (or any sampler): the notebook fits the hierarchical model with a
sampler, and these functions build its inputs and compute, with no sampling at all, the same posterior to check the
sampler against (DECISIONS/0012).

The model is the one-level normal-normal hierarchy with known sampling errors::

    y_i ~ Normal(theta_i, s_i),   theta_i ~ Normal(mu, tau),   mu ~ Normal(m0, s0),   tau ~ HalfNormal(a) or HalfCauchy(a)

Given ``tau`` the model is Gaussian, so ``mu`` integrates out in closed form and ``theta`` is conditionally normal.
That leaves one dimension, ``tau``, which :func:`exact_posterior` integrates on a fine grid.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import stats

__all__ = ["ExactPosterior", "conditional_posterior", "exact_posterior", "moment_tau2", "proportion_se"]

Float = NDArray[np.float64]
#: The Census Bureau's margin of error is published at 90% confidence.
Z90 = 1.645


def proportion_se(x: ArrayLike, moe_x: ArrayLike, n: ArrayLike, moe_n: ArrayLike) -> Float:
    """Standard error of ``x / n`` when ``x`` is a subset of ``n``, from the two 90% margins of error.

    The Census Bureau's formula is ``sqrt(se_x^2 - p^2 se_n^2) / n``; where that radicand is negative the ratio
    formula ``sqrt(se_x^2 + p^2 se_n^2) / n`` is used instead. An empty universe (``n <= 0``) gives ``nan``.
    """
    a, ma, b, mb = (np.asarray(v, dtype=float) for v in (x, moe_x, n, moe_n))
    if not (a.shape == ma.shape == b.shape == mb.shape) or a.ndim != 1:
        raise ValueError("all inputs must be one-dimensional and of equal length")
    with np.errstate(divide="ignore", invalid="ignore"):
        p = a / b
        sx, sn = ma / Z90, mb / Z90
        radicand = sx**2 - p**2 * sn**2
        radicand = np.where(radicand < 0, sx**2 + p**2 * sn**2, radicand)
        se = np.sqrt(radicand) / b
    return np.where(b > 0, se, np.nan)


def moment_tau2(y: ArrayLike, se: ArrayLike) -> float:
    """Between-unit variance by the moment estimator: observed variance minus mean sampling variance, floored at zero."""
    est, s = np.asarray(y, dtype=float), np.asarray(se, dtype=float)
    if est.shape != s.shape or est.ndim != 1 or len(est) < 2:
        raise ValueError("y and se must be one-dimensional, of equal length, with at least two units")
    return max(float(np.var(est, ddof=1) - np.mean(s**2)), 0.0)


def _check(y: ArrayLike, s: ArrayLike, mu_prior: tuple[float, float]) -> tuple[Float, Float]:
    ya, sa = np.asarray(y, dtype=float), np.asarray(s, dtype=float)
    if ya.shape != sa.shape or ya.ndim != 1:
        raise ValueError("y and s must be one-dimensional and of equal length")
    if np.any(~np.isfinite(ya)) or np.any(~np.isfinite(sa)) or np.any(sa <= 0):
        raise ValueError("standard errors must be positive and finite")
    if not mu_prior[1] > 0:
        raise ValueError("the prior standard deviation of mu must be positive")
    return ya, sa


def conditional_posterior(y: ArrayLike, s: ArrayLike, tau: float, m0: float, s0: float) -> tuple[Float, Float, float]:
    """Posterior mean and variance of each ``theta_i`` given ``tau``, with ``mu`` integrated out; also the mean of ``mu``.

    ``E[theta_i | tau, y] = (1 - B_i) y_i + B_i m`` with ``B_i = s_i^2 / (s_i^2 + tau^2)`` and ``m`` the posterior
    mean of ``mu``; the variance adds the uncertainty of ``m``.
    """
    ya, sa = _check(y, s, (m0, s0))
    if not tau > 0:
        raise ValueError("tau must be positive")
    w = 1.0 / (sa**2 + tau**2)
    precision = 1.0 / s0**2 + w.sum()
    m = (m0 / s0**2 + (w * ya).sum()) / precision
    shrink = sa**2 / (sa**2 + tau**2)
    mean = (1.0 - shrink) * ya + shrink * m
    var = (1.0 - shrink) * sa**2 + shrink**2 / precision
    return mean, var, float(m)


@dataclass(frozen=True)
class ExactPosterior:
    """Exact posterior summaries on a ``tau`` grid; every array is per unit unless noted."""

    theta_mean: Float
    theta_sd: Float
    shrinkage_mean: Float          # posterior mean of B_i = s_i^2 / (s_i^2 + tau^2)
    mu_mean: float
    tau_mean: float
    tau_sd: float
    tau_grid: Float
    tau_density: Float             # posterior density of tau on tau_grid (integrates to one)


def _log_prior_tau(tau: Float, prior: tuple[str, float]) -> Float:
    kind, scale = prior
    if kind not in ("halfnormal", "halfcauchy") or not scale > 0:
        raise ValueError("tau prior must be ('halfnormal' | 'halfcauchy', positive scale)")
    if kind == "halfnormal":
        return np.asarray(stats.halfnorm.logpdf(tau, scale=scale))
    return np.asarray(stats.halfcauchy.logpdf(tau, scale=scale))


def exact_posterior(
    y: ArrayLike,
    s: ArrayLike,
    *,
    mu_prior: tuple[float, float],
    tau_prior: tuple[Literal["halfnormal", "halfcauchy"], float],
    n_grid: int = 4001,
) -> ExactPosterior:
    """Exact posterior of the normal-normal hierarchy by integrating ``tau`` on a grid; no sampling.

    ``mu_prior`` is ``(mean, sd)``; ``tau_prior`` is ``("halfnormal" | "halfcauchy", scale)``. The grid runs from near
    zero to a bound where the posterior of ``tau`` is negligible (a multiple of the larger of the prior scale and the
    spread of ``y``). Raises ``ValueError`` for unequal lengths, a non-positive standard error or an unknown prior.
    """
    m0, s0 = mu_prior
    ya, sa = _check(y, s, mu_prior)
    kind, scale = tau_prior
    _log_prior_tau(np.array([1.0]), (kind, scale))  # validates the prior name and scale before any work
    reach = max(scale, float(np.std(ya)), float(sa.max()))
    upper = (40.0 if kind == "halfcauchy" else 12.0) * reach
    tau = np.linspace(upper * 1e-6, upper, n_grid)
    n = len(ya)
    log_post = np.empty_like(tau)
    means = np.empty((len(tau), n))
    varis = np.empty((len(tau), n))
    shrinks = np.empty((len(tau), n))
    mus = np.empty(len(tau))
    for k, t in enumerate(tau):
        v = sa**2 + t**2
        w = 1.0 / v
        precision = 1.0 / s0**2 + w.sum()
        m = (m0 / s0**2 + (w * ya).sum()) / precision
        quad = (w * ya**2).sum() + m0**2 / s0**2 - precision * m**2
        log_post[k] = -0.5 * np.log(v).sum() - 0.5 * np.log(s0**2 * precision) - 0.5 * quad
        means[k], varis[k], _ = conditional_posterior(ya, sa, float(t), m0, s0)
        mus[k] = m
        shrinks[k] = sa**2 / v
    log_post = log_post + _log_prior_tau(tau, (kind, scale))
    dens = np.exp(log_post - log_post.max())
    dens = dens / np.trapezoid(dens, tau)
    wts = dens
    mean = np.trapezoid(wts[:, None] * means, tau, axis=0)
    second = np.trapezoid(wts[:, None] * (varis + means**2), tau, axis=0)
    tau_mean = float(np.trapezoid(wts * tau, tau))
    tau_var = float(np.trapezoid(wts * tau**2, tau)) - tau_mean**2
    return ExactPosterior(
        theta_mean=mean, theta_sd=np.sqrt(np.maximum(second - mean**2, 0.0)),
        shrinkage_mean=np.trapezoid(wts[:, None] * shrinks, tau, axis=0),
        mu_mean=float(np.trapezoid(wts * mus, tau)), tau_mean=tau_mean, tau_sd=float(np.sqrt(max(tau_var, 0.0))),
        tau_grid=tau, tau_density=dens,
    )
