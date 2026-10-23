"""Regression discontinuity: local linear estimation, bandwidth grid, falsification.

Estimand
    The jump in the conditional mean of the outcome at the cutoff,
    ``lim_{x->c+} E[y|x] - lim_{x->c-} E[y|x]``, local to ``c``. With survey
    weights the estimand is the jump in the *weighted* mean, which is a
    different object from the population one.

Identifying assumption
    Potential outcomes are continuous in the running variable at the cutoff:
    nobody sorts across it. The estimator cannot test this. The falsifications
    here are the **density test** (counts either side of the cutoff within the
    window) and **placebo cutoffs** (estimates at points where no policy
    changes), plus covariate continuity, which a notebook runs by passing a
    covariate as ``y``.

Estimator
    Weighted least squares of ``y`` on ``[1, D, (x-c), D*(x-c)]`` within
    ``|x - c| <= h``, with triangular (``1 - |x-c|/h``) or uniform kernel
    weights, optionally multiplied by survey weights. The coefficient on ``D``
    is the estimate. Variance is the HC1 sandwich, or cluster-robust (CR1) when
    ``cluster`` is given. With a *discrete* running variable that takes few values
    inside the window, neither is reliable and clustering on the values of the
    running variable is not a remedy: with a handful of clusters and as many
    parameters, the variance is close to zero by construction. :func:`honest_interval`
    adds a bound on the bias from curvature, which is the other half of the problem.
    No data-driven bandwidth: the notebook shows a grid and says so.

Limits
    The density test is a binomial test of window counts. It is **not** the
    McCrary (2008) smoothness test and does not estimate a density; with a
    whole-year running variable it asks only whether the two sides are equally
    populated.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""

from __future__ import annotations

# Estimator signatures carry the data, the cutoff and the options explicitly.
# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
from dataclasses import dataclass
from typing import Literal, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import stats  # type: ignore[import-untyped]

Float = NDArray[np.float64]
_MIN_PER_SIDE = 2


@dataclass(frozen=True)
class RddFit:
    """A local-linear discontinuity estimate."""

    estimate: float
    se: float
    bandwidth: float
    n_left: int
    n_right: int
    cutoff: float


@dataclass(frozen=True)
class PlaceboFit:
    """An estimate at a placebo cutoff, with the cutoff it was run at."""

    cutoff: float
    fit: RddFit


@dataclass(frozen=True)
class DensityTest:
    """Counts either side of the cutoff within the window, and a binomial p-value."""

    n_left: int
    n_right: int
    p_value: float
    bandwidth: float


def _arrays(x: ArrayLike, y: ArrayLike, weights: ArrayLike | None) -> tuple[Float, Float, Float]:
    xx = np.asarray(x, dtype=float)
    yy = np.asarray(y, dtype=float)
    if xx.ndim != 1 or xx.shape != yy.shape:
        raise ValueError("x and y must be one-dimensional and of the same length")
    ww = np.ones_like(xx) if weights is None else np.asarray(weights, dtype=float)
    if ww.shape != xx.shape:
        raise ValueError("weights must have the same length as x")
    if not (np.all(np.isfinite(xx)) and np.all(np.isfinite(yy)) and np.all(np.isfinite(ww))):
        raise ValueError("x, y and weights contain non-finite values; none are dropped silently")
    if np.any(ww < 0):
        raise ValueError("weights must be non-negative")
    return xx, yy, ww


def local_linear(
    x: ArrayLike,
    y: ArrayLike,
    *,
    cutoff: float,
    bandwidth: float,
    kernel: Literal["triangular", "uniform"] = "triangular",
    weights: ArrayLike | None = None,
    cluster: ArrayLike | None = None,
) -> RddFit:
    """Local-linear estimate of the jump at ``cutoff`` within ``bandwidth``.

    Complexity O(n). Raises ``ValueError`` for a non-positive bandwidth, an
    unknown kernel, non-finite inputs, or fewer than two observations with
    positive weight on a side (a line cannot be fitted to fewer).
    """
    if not bandwidth > 0:
        raise ValueError(f"bandwidth must be positive, not {bandwidth!r}")
    if kernel not in ("triangular", "uniform"):
        raise ValueError(f"kernel must be 'triangular' or 'uniform', not {kernel!r}")
    xx, yy, ww = _arrays(x, y, weights)
    cl = None if cluster is None else np.asarray(cluster)
    if cl is not None and cl.shape != xx.shape:
        raise ValueError("cluster must have the same length as x")
    dist = xx - cutoff
    inside = np.abs(dist) <= bandwidth
    k = 1.0 - np.abs(dist) / bandwidth if kernel == "triangular" else np.ones_like(dist)
    w = np.where(inside, k * ww, 0.0)
    live = w > 0
    right = dist >= 0
    n_left, n_right = int((live & ~right).sum()), int((live & right).sum())
    if min(n_left, n_right) < _MIN_PER_SIDE:
        raise ValueError(
            f"at least {_MIN_PER_SIDE} weighted observations are needed on each side of the "
            f"cutoff within the bandwidth; found {n_left} left and {n_right} right"
        )
    design = np.column_stack([np.ones_like(dist), right.astype(float), dist, right * dist])[live]
    wl, yl = w[live], yy[live]
    gram = design.T @ (design * wl[:, None])
    bread = np.linalg.inv(gram)
    beta = bread @ (design.T @ (wl * yl))
    resid = yl - design @ beta
    scores = design * (wl * resid)[:, None]
    n, p = design.shape
    if cl is None:
        meat = scores.T @ scores
        factor = n / (n - p) if n > p else 1.0
    else:
        groups = np.unique(cl[live], return_inverse=True)[1]
        g = int(groups.max()) + 1
        summed = np.zeros((g, p))
        np.add.at(summed, groups, scores)
        meat = summed.T @ summed
        factor = (g / (g - 1)) * ((n - 1) / (n - p)) if g > 1 and n > p else 1.0
    var = factor * bread @ meat @ bread
    return RddFit(
        estimate=float(beta[1]),
        se=float(np.sqrt(max(var[1, 1], 0.0))),
        bandwidth=float(bandwidth),
        n_left=n_left,
        n_right=n_right,
        cutoff=float(cutoff),
    )


def bandwidth_grid(
    x: ArrayLike,
    y: ArrayLike,
    *,
    cutoff: float,
    bandwidths: Sequence[float],
    **options: object,
) -> list[RddFit]:
    """One :func:`local_linear` fit per bandwidth, in the order given."""
    return [
        local_linear(x, y, cutoff=cutoff, bandwidth=h, **options)  # type: ignore[arg-type]
        for h in bandwidths
    ]


def placebo_cutoffs(
    x: ArrayLike,
    y: ArrayLike,
    *,
    true_cutoff: float,
    placebo_cutoffs: Sequence[float],  # pylint: disable=redefined-outer-name
    bandwidth: float,
    **options: object,
) -> list[PlaceboFit]:
    """Estimates at cutoffs where no policy changes.

    A placebo below the true cutoff uses only observations below it, and a
    placebo above uses only observations at or above it, so the real
    discontinuity cannot leak into the placebo window. A placebo at or beyond
    the true cutoff's side but outside the data raises.
    """
    xx = np.asarray(x, dtype=float)
    yy = np.asarray(y, dtype=float)
    # Per-observation options travel with the observations: restricting x and y to one
    # side of the cutoff without restricting these would misalign them.
    per_obs = {
        name: np.asarray(options.pop(name))
        for name in ("weights", "cluster")
        if options.get(name) is not None
    }
    for name in ("weights", "cluster"):
        options.pop(name, None)
    for name, values in per_obs.items():
        if values.shape != xx.shape:
            raise ValueError(f"{name} must have the same length as x")
    out: list[PlaceboFit] = []
    for c in placebo_cutoffs:
        if c == true_cutoff:
            raise ValueError("a placebo cutoff equal to the true cutoff is not in a placebo set")
        side = xx < true_cutoff if c < true_cutoff else xx >= true_cutoff
        if not xx[side].min() < c < xx[side].max():
            raise ValueError(f"placebo cutoff {c} is not in the data on its side of the cutoff")
        out.append(
            PlaceboFit(
                cutoff=float(c),
                fit=local_linear(
                    xx[side],
                    yy[side],
                    cutoff=c,
                    bandwidth=bandwidth,
                    **{name: values[side] for name, values in per_obs.items()},
                    **options,  # type: ignore[arg-type]
                ),
            )
        )
    return out


def density_test(x: ArrayLike, *, cutoff: float, bandwidth: float) -> DensityTest:
    """Binomial test that the window holds equal counts either side of the cutoff."""
    xx = np.asarray(x, dtype=float)
    if not np.all(np.isfinite(xx)):
        raise ValueError("x contains non-finite values; none are dropped silently")
    window = xx[np.abs(xx - cutoff) <= bandwidth]
    if window.size == 0:
        raise ValueError("no observations fall inside the window")
    right = int((window >= cutoff).sum())
    left = int(window.size - right)
    p = float(stats.binomtest(right, window.size, 0.5).pvalue)
    return DensityTest(n_left=left, n_right=right, p_value=p, bandwidth=float(bandwidth))


@dataclass(frozen=True)
class HonestInterval:
    """A confidence interval that allows for curvature of bounded size."""

    estimate: float
    se: float
    smoothness: float
    bias_bound: float
    critical_value: float
    lower: float
    upper: float


def estimator_weights(
    x: ArrayLike,
    *,
    cutoff: float,
    bandwidth: float,
    kernel: Literal["triangular", "uniform"] = "triangular",
    weights: ArrayLike | None = None,
) -> tuple[Float, Float]:
    """The weights ``w_i`` with which :func:`local_linear`'s jump is ``sum_i w_i y_i``.

    Returns ``(w, distance)`` over all observations (zero outside the window). The jump is a
    linear estimator, so its weights depend on ``x`` only: ``e' (X'WX)^-1 X'W`` for the
    coefficient on the treatment indicator. On each side they sum to plus or minus one and are
    orthogonal to the distance from the cutoff.
    """
    xx = np.asarray(x, dtype=float)
    ww = np.ones_like(xx) if weights is None else np.asarray(weights, dtype=float)
    dist = xx - cutoff
    k = 1.0 - np.abs(dist) / bandwidth if kernel == "triangular" else np.ones_like(dist)
    w = np.where(np.abs(dist) <= bandwidth, k * ww, 0.0)
    live = w > 0
    right = dist >= 0
    design = np.column_stack([np.ones_like(dist), right.astype(float), dist, right * dist])[live]
    wl = w[live]
    bread = np.linalg.inv(design.T @ (design * wl[:, None]))
    out = np.zeros_like(xx)
    out[live] = wl * (design @ bread[:, 1])
    return out, dist


def honest_interval(
    x: ArrayLike,
    y: ArrayLike,
    *,
    cutoff: float,
    bandwidth: float,
    smoothness: float,
    kernel: Literal["triangular", "uniform"] = "triangular",
    weights: ArrayLike | None = None,
    alpha: float = 0.05,
) -> HonestInterval:
    """Bias-aware confidence interval for the jump, for a bound ``smoothness`` on curvature.

    The regression function on each side is allowed to depart from its straight line at the
    cutoff by at most ``smoothness / 2 * distance**2`` (the Taylor class of Armstrong and
    Kolesar, 2018, as recalled, not verified in this build). A linear estimator ``sum w_i y_i``
    that is exact for straight lines then has worst-case bias ``smoothness / 2 * sum |w_i|
    d_i**2``; the interval is the estimate plus or minus the ``1 - alpha`` quantile of
    ``|N(b/se, 1)|`` times ``se``, with ``b`` the bias bound and ``se`` the HC1 standard error
    of :func:`local_linear`. With ``smoothness = 0`` it is the conventional interval. The
    choice of ``smoothness`` is the analyst's, and it should be reported for several values.
    """
    if not smoothness >= 0:
        raise ValueError("smoothness must be non-negative")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must lie in (0, 1)")
    fit = local_linear(x, y, cutoff=cutoff, bandwidth=bandwidth, kernel=kernel, weights=weights)
    w, dist = estimator_weights(
        x, cutoff=cutoff, bandwidth=bandwidth, kernel=kernel, weights=weights
    )
    bias = 0.5 * smoothness * float(np.sum(np.abs(w) * dist**2))
    ratio = bias / fit.se if fit.se > 0 else float("inf")
    cv = float(np.sqrt(stats.ncx2.ppf(1.0 - alpha, 1, ratio**2)))
    return HonestInterval(
        estimate=fit.estimate,
        se=fit.se,
        smoothness=float(smoothness),
        bias_bound=bias,
        critical_value=cv,
        lower=fit.estimate - cv * fit.se,
        upper=fit.estimate + cv * fit.se,
    )
