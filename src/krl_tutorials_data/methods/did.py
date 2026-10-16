"""Difference-in-differences: two-way fixed effects, event-study design, wild bootstrap.

Estimand
    With a binary treatment ``D_it`` and unit and period effects, the
    coefficient on ``D`` in ``y_it = a_i + l_t + b D_it + e_it``. On a balanced
    2x2 panel this equals the difference of the four cell means exactly.

Identifying assumption
    Parallel trends in the absence of treatment. **This module cannot test it**;
    it supplies the machinery (event-study leads, bootstrap inference) a
    notebook uses to examine it. With staggered adoption and heterogeneous
    effects the two-way coefficient is a weighted average with weights that can
    be negative (Goodman-Bacon 2021); the heterogeneity-robust estimators and
    the decomposition belong to the notebook that needs them (C03), not here.

Computation
    Fixed effects are absorbed by alternating projections on the unit and period
    means, never by a dummy-variable matrix, so a 3,000-unit by 48-period panel
    costs a few ``bincount`` passes per iteration. On a balanced panel one pass
    is exact; on an unbalanced panel the iteration converges geometrically and
    raises if it does not.

Standard errors
    Cluster-robust (CR1): ``V = c * (X'X)^-1 (sum_g s_g s_g') (X'X)^-1`` with
    ``s_g`` the within-cluster sum of ``x_i * e_i`` on the demeaned data and
    ``c = G/(G-1) * (N-1)/(N-K)``. ``K`` counts the regressors **and every
    absorbed effect**: ``K = k + n_units + n_periods - 1``. That is the
    convention of a regression on full dummy variables with a cluster-robust
    covariance, which is what the tests cross-check against. It is the more
    conservative of the conventions in use (it does not exempt unit effects
    nested in clusters), and a notebook that quotes another convention must say
    so. Cluster-robust inference is unreliable with few clusters; the wild
    cluster bootstrap below is the check, and Webb weights are the usual advice
    when there are fewer than about a dozen.

References (author, year, venue as recalled; **not verified against the
published record in this build**): Bertrand, Duflo & Mullainathan (2004) QJE;
Cameron, Gelbach & Miller (2008) REStat 90(3); Webb (2014) Queen's Economics
Department Working Paper 1315; Goodman-Bacon (2021) J. Econometrics.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

# Numerical estimators take the full design (outcome, regressors, unit, time,
# cluster, options) and keep intermediate arrays named; the design-complexity
# limits are relaxed for this package only, not silenced elsewhere.
# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
# pylint: disable=too-many-instance-attributes

from dataclasses import dataclass
from typing import Literal, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

Float = NDArray[np.float64]

_MAX_ITER = 10_000
_TOL = 1e-12


@dataclass(frozen=True)
class TwfeFit:
    """A two-way fixed-effects fit with cluster-robust inference."""

    coef: Float
    se: Float
    vcov: Float
    n_obs: int
    n_clusters: int
    n_units: int
    n_periods: int
    df_resid: int


@dataclass(frozen=True)
class WildBootstrap:
    """A null-imposed wild cluster bootstrap-t test of one coefficient."""

    t_stat: float
    p_value: float
    t_boot: Float
    n_boot: int
    weights: str


@dataclass(frozen=True)
class EventStudyDesign:
    """Event-time dummies, one column per entry of ``labels``."""

    matrix: Float
    labels: tuple[int, ...]


def did_two_by_two(
    pre_treated: ArrayLike,
    post_treated: ArrayLike,
    pre_control: ArrayLike,
    post_control: ArrayLike,
) -> float:
    """Difference of changes in group means: ``(T_post - T_pre) - (C_post - C_pre)``.

    Complexity O(n). Each group must be non-empty and finite; nothing is dropped.
    """
    means = []
    for name, values in (
        ("pre_treated", pre_treated), ("post_treated", post_treated),
        ("pre_control", pre_control), ("post_control", post_control),
    ):
        arr = np.asarray(values, dtype=float)
        if arr.size == 0 or not np.all(np.isfinite(arr)):
            raise ValueError(f"{name} must be non-empty and finite")
        means.append(float(arr.mean()))
    return (means[1] - means[0]) - (means[3] - means[2])


def _codes(values: ArrayLike, name: str) -> tuple[NDArray[np.intp], int]:
    arr = np.asarray(values)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    uniq, inverse = np.unique(arr, return_inverse=True)
    return inverse.astype(np.intp), int(uniq.size)


def _group_mean_subtract(
    v: Float, codes: NDArray[np.intp], n: int, counts: Float
) -> Float:
    sums = np.bincount(codes, weights=v, minlength=n)
    return v - (sums / counts)[codes]


def demean_two_way(
    values: Float,
    unit_codes: NDArray[np.intp],
    time_codes: NDArray[np.intp],
    n_units: int,
    n_periods: int,
) -> Float:
    """Project out unit and period effects by alternating projections.

    Accepts a vector or an ``(n, k)`` matrix. Exact in one pass on a balanced
    panel. Raises ``RuntimeError`` if the iteration has not converged in
    ``10,000`` passes, rather than returning a partly demeaned column.
    """
    unit_counts = np.bincount(unit_codes, minlength=n_units).astype(float)
    time_counts = np.bincount(time_codes, minlength=n_periods).astype(float)
    cols = values.reshape(values.shape[0], -1)
    out = np.empty_like(cols, dtype=float)
    for j in range(cols.shape[1]):
        v = cols[:, j].astype(float).copy()
        scale = max(float(np.abs(v).max()), 1.0)
        for _ in range(_MAX_ITER):
            before = v
            v = _group_mean_subtract(v, unit_codes, n_units, unit_counts)
            v = _group_mean_subtract(v, time_codes, n_periods, time_counts)
            if float(np.abs(v - before).max()) <= _TOL * scale:
                break
        else:
            raise RuntimeError("two-way demeaning did not converge")
        out[:, j] = v
    return out.reshape(values.shape)


def _prepare(
    y: ArrayLike, x: ArrayLike, unit: ArrayLike, time: ArrayLike, cluster: ArrayLike | None
) -> tuple[Float, Float, NDArray[np.intp], NDArray[np.intp], NDArray[np.intp], int, int, int]:
    yy = np.asarray(y, dtype=float)
    xx = np.asarray(x, dtype=float)
    if xx.ndim == 1:
        xx = xx[:, None]
    n = yy.shape[0]
    arrays = {"unit": np.asarray(unit), "time": np.asarray(time)}
    if cluster is not None:
        arrays["cluster"] = np.asarray(cluster)
    if yy.ndim != 1 or xx.shape[0] != n or any(a.shape[0] != n for a in arrays.values()):
        raise ValueError("y, x, unit, time and cluster must all have the same length")
    if not (np.all(np.isfinite(yy)) and np.all(np.isfinite(xx))):
        raise ValueError("y and x contain non-finite values; none are dropped silently")
    u_codes, n_units = _codes(unit, "unit")
    t_codes, n_periods = _codes(time, "time")
    c_codes, n_clusters = _codes(cluster if cluster is not None else unit, "cluster")
    if n_clusters < 2:
        raise ValueError("cluster-robust inference needs at least two clusters")
    return yy, xx, u_codes, t_codes, c_codes, n_units, n_periods, n_clusters


def _absorb(
    yy: Float, xx: Float, u: NDArray[np.intp], t: NDArray[np.intp], n_units: int, n_periods: int
) -> tuple[Float, Float]:
    x_before = (xx**2).sum(axis=0)
    y_t = demean_two_way(yy, u, t, n_units, n_periods)
    x_t = demean_two_way(xx, u, t, n_units, n_periods)
    x_after = (x_t**2).sum(axis=0)
    dead = np.where((x_after <= 1e-12 * np.maximum(x_before, 1e-300)) | (x_before == 0))[0]
    if dead.size:
        raise ValueError(
            f"regressor column(s) {dead.tolist()} have no variation after absorbing the unit "
            "and period effects; they are collinear with the fixed effects"
        )
    return y_t, x_t


def _cluster_vcov(
    x_t: Float, resid: Float, c: NDArray[np.intp], n_clusters: int, bread: Float, factor: float
) -> Float:
    k = x_t.shape[1]
    scores = np.empty((n_clusters, k))
    for j in range(k):
        scores[:, j] = np.bincount(c, weights=x_t[:, j] * resid, minlength=n_clusters)
    return factor * bread @ (scores.T @ scores) @ bread


def _factor(n: int, n_clusters: int, n_params: int, ssc: bool) -> float:
    if not ssc:
        return 1.0
    if n - n_params <= 0:
        raise ValueError(
            f"{n} observations cannot support {n_params} parameters (regressors plus "
            "absorbed unit and period effects)"
        )
    return (n_clusters / (n_clusters - 1)) * ((n - 1) / (n - n_params))


def twfe(
    y: ArrayLike,
    x: ArrayLike,
    unit: ArrayLike,
    time: ArrayLike,
    *,
    cluster: ArrayLike | None = None,
    ssc: bool = True,
) -> TwfeFit:
    """Two-way fixed-effects OLS of ``y`` on the columns of ``x``.

    ``unit`` and ``time`` label the effects to absorb; ``cluster`` defaults to
    ``unit``. ``ssc=False`` returns the uncorrected (CR0) variance. Complexity
    ``O(iterations * n * k)``. A regressor with no variation after absorbing the
    effects, a non-finite value or fewer than two clusters raises ``ValueError``;
    nothing is dropped or coerced.
    """
    yy, xx, u, t, c, n_units, n_periods, n_clusters = _prepare(y, x, unit, time, cluster)
    y_t, x_t = _absorb(yy, xx, u, t, n_units, n_periods)
    gram = x_t.T @ x_t
    if np.linalg.matrix_rank(gram) < gram.shape[0]:
        raise ValueError("regressors are collinear after absorbing the fixed effects")
    bread = np.linalg.inv(gram)
    coef = bread @ (x_t.T @ y_t)
    resid = y_t - x_t @ coef
    n_params = xx.shape[1] + n_units + n_periods - 1
    factor = _factor(yy.shape[0], n_clusters, n_params, ssc)
    vcov = _cluster_vcov(x_t, resid, c, n_clusters, bread, factor)
    return TwfeFit(
        coef=coef, se=np.sqrt(np.diag(vcov)), vcov=vcov, n_obs=yy.shape[0],
        n_clusters=n_clusters, n_units=n_units, n_periods=n_periods,
        df_resid=yy.shape[0] - n_params,
    )


_WEBB = np.array([-np.sqrt(1.5), -1.0, -np.sqrt(0.5), np.sqrt(0.5), 1.0, np.sqrt(1.5)])


def bootstrap_weights(
    kind: Literal["rademacher", "webb"], *, size: tuple[int, ...], seed: int
) -> Float:
    """Mean-zero, unit-variance multipliers for the wild bootstrap.

    ``rademacher`` is +-1 with probability 1/2. ``webb`` is the six-point
    distribution on +-sqrt(3/2), +-1, +-sqrt(1/2), each with probability 1/6,
    which has more support points and is the usual advice when there are few
    clusters. The generator is built here from ``seed``: this is inference
    randomness and is declared at the call.
    """
    rng = np.random.default_rng(seed)
    if kind == "rademacher":
        return rng.choice(np.array([-1.0, 1.0]), size=size)
    if kind == "webb":
        return rng.choice(_WEBB, size=size)
    raise ValueError(f"weights must be 'rademacher' or 'webb', not {kind!r}")


def wild_cluster_bootstrap(
    y: ArrayLike,
    x: ArrayLike,
    unit: ArrayLike,
    time: ArrayLike,
    *,
    test_column: int,
    n_boot: int,
    seed: int,
    cluster: ArrayLike | None = None,
    weights: Literal["rademacher", "webb"] = "rademacher",
) -> WildBootstrap:
    """Null-imposed wild cluster bootstrap-t test that ``coef[test_column] == 0``.

    The restricted model drops the tested column, its residuals are multiplied
    by one cluster-level weight, and the studentised statistic is recomputed on
    each pseudo-sample with the same cluster-robust formula as :func:`twfe`.
    Two-sided p-value: the share of ``|t*|`` at least ``|t|``. ``seed`` is
    required. Complexity ``O(n_boot * iterations * n * k)``.
    """
    yy, xx, u, t, c, n_units, n_periods, n_clusters = _prepare(y, x, unit, time, cluster)
    k = xx.shape[1]
    if not 0 <= test_column < k:
        raise ValueError(f"test_column {test_column} is outside the {k} regressor columns")
    if n_boot < 1:
        raise ValueError("n_boot must be at least 1")
    y_t, x_t = _absorb(yy, xx, u, t, n_units, n_periods)
    n = yy.shape[0]
    factor = _factor(n, n_clusters, k + n_units + n_periods - 1, True)
    bread = np.linalg.inv(x_t.T @ x_t)

    def statistic(y_demeaned: Float) -> float:
        coef = bread @ (x_t.T @ y_demeaned)
        resid = y_demeaned - x_t @ coef
        vcov = _cluster_vcov(x_t, resid, c, n_clusters, bread, factor)
        return float(coef[test_column] / np.sqrt(vcov[test_column, test_column]))

    observed = statistic(y_t)
    keep = [j for j in range(k) if j != test_column]
    if keep:
        xr = x_t[:, keep]
        beta_r = np.linalg.lstsq(xr, y_t, rcond=None)[0]
        fitted_r = xr @ beta_r
    else:
        fitted_r = np.zeros(n)
    resid_r = y_t - fitted_r
    draws = bootstrap_weights(weights, size=(n_boot, n_clusters), seed=seed)
    t_boot = np.empty(n_boot)
    for b in range(n_boot):
        shocked = draws[b][c] * resid_r
        y_star = fitted_r + demean_two_way(shocked, u, t, n_units, n_periods)
        t_boot[b] = statistic(y_star)
    p_value = float(np.mean(np.abs(t_boot) >= abs(observed)))
    return WildBootstrap(
        t_stat=observed, p_value=p_value, t_boot=t_boot, n_boot=n_boot, weights=weights
    )


def event_study_design(
    time: ArrayLike,
    adoption_time: ArrayLike,
    *,
    leads: int,
    lags: int,
    reference: int = -1,
    bin_endpoints: bool = True,
) -> EventStudyDesign:
    """Dummies for event time ``k = time - adoption_time`` over ``[-leads, +lags]``.

    ``adoption_time`` is ``NaN`` for never-treated observations, whose rows are
    all zero. The ``reference`` period is omitted (its coefficient is zero by
    construction). With ``bin_endpoints`` the end periods absorb everything
    beyond them; without it those observations are all-zero rows, which treats
    them as belonging to the reference group and is rarely what is intended, so
    binning is the default. Event time must be integer-valued.
    """
    t = np.asarray(time, dtype=float)
    a = np.asarray(adoption_time, dtype=float)
    if t.shape != a.shape or t.ndim != 1:
        raise ValueError("time and adoption_time must be one-dimensional and of equal length")
    if leads < 0 or lags < 0:
        raise ValueError("leads and lags must be non-negative")
    if not -leads <= reference <= lags:
        raise ValueError(
            f"reference {reference} must lie inside the event window [{-leads}, {lags}]"
        )
    rel = t - a
    treated = np.isfinite(rel)
    if not np.all(rel[treated] == np.round(rel[treated])):
        raise ValueError("event time must be integer-valued")
    if bin_endpoints:
        rel = np.clip(rel, -leads, lags)
    labels: Sequence[int] = [k for k in range(-leads, lags + 1) if k != reference]
    matrix = np.zeros((t.shape[0], len(labels)))
    for col, k in enumerate(labels):
        matrix[:, col] = (treated & (rel == k)).astype(float)
    return EventStudyDesign(matrix=matrix, labels=tuple(labels))
