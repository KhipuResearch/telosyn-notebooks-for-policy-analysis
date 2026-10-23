"""Instrumental variables: one endogenous regressor, one instrument, weights, clusters.

Estimand
    With a binary instrument and no controls, the IV estimate is the Wald ratio of the
    reduced form to the first stage, the average effect for **compliers**: those whose
    treatment is moved by the instrument. With weights the estimand is the weighted
    version of the same, a different object from the unweighted one.

Identifying assumptions
    **Relevance** (the first stage is not zero; reported with a cluster-robust F), and
    **exclusion and independence** (the instrument moves the outcome only through the
    treatment, and is as good as randomly assigned given the controls). Exclusion is an
    argument and cannot be tested here; a design with more instruments than regressors
    could test overidentification, and this one is exactly identified.

Estimator
    ``beta = (Z'WX)^-1 Z'Wy`` with ``X = [endogenous, 1, controls]`` and
    ``Z = [instrument, 1, controls]``, which is two-stage least squares when exactly
    identified. The variance is the cluster-robust sandwich
    ``(Z'WX)^-1 (sum_g s_g s_g') (Z'WX)^-T`` with ``s_g`` the within-cluster sum of
    ``z_i w_i e_i``, and the CR1 factor ``G/(G-1) (N-1)/(N-K)`` unless ``small_sample``
    is false (``N`` counts rows, not weight). Cluster-robust inference is unreliable
    with few clusters; this module does not bootstrap.

Weights
    ``weights`` are analytic weights (cell populations), applied as a weighted least
    squares. Replicating a row ``n`` times gives the same coefficients as giving it
    weight ``n``, which the tests check; the standard errors agree with
    ``small_sample=False``.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""

from __future__ import annotations

# Estimator signatures carry the outcome, the regressor, the instrument and the options.
# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
# pylint: disable=too-many-instance-attributes
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

Float = NDArray[np.float64]


@dataclass(frozen=True)
class IvFit:
    """An IV estimate with its first stage and reduced form."""

    coef: float
    se: float
    first_stage_coef: float
    first_stage_se: float
    first_stage_f: float
    reduced_form_coef: float
    reduced_form_se: float
    n_obs: int
    n_clusters: int
    n_params: int


def _vector(values: ArrayLike, name: str, n: int | None = None) -> Float:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1 or (n is not None and arr.shape[0] != n):
        raise ValueError(f"{name} must be one-dimensional and of the same length as y")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} contains non-finite values; none are dropped silently")
    return arr


def _sandwich(
    z: Float, resid: Float, bread: Float, codes: NDArray[np.intp], n_clusters: int, factor: float
) -> Float:
    """Cluster-robust covariance ``factor * bread @ meat @ bread.T`` from instrument scores."""
    scores = np.empty((n_clusters, z.shape[1]))
    for j in range(z.shape[1]):
        scores[:, j] = np.bincount(codes, weights=z[:, j] * resid, minlength=n_clusters)
    return factor * bread @ (scores.T @ scores) @ bread.T


def _fit(
    outcome: Float,
    regressors: Float,
    instruments: Float,
    codes: NDArray[np.intp],
    n_clusters: int,
    small_sample: bool,
) -> tuple[Float, Float]:
    """IV coefficients and cluster-robust covariance for already weighted data."""
    n, k = regressors.shape
    gram = instruments.T @ regressors
    if np.linalg.matrix_rank(gram) < k:
        raise ValueError("the instrument is irrelevant or collinear with the controls")
    bread = np.linalg.inv(gram)
    beta = bread @ (instruments.T @ outcome)
    resid = outcome - regressors @ beta
    factor = 1.0
    if small_sample:
        if n - k <= 0:
            raise ValueError(f"{n} observations cannot support {k} parameters")
        factor = (n_clusters / (n_clusters - 1)) * ((n - 1) / (n - k))
    return beta, _sandwich(instruments, resid, bread, codes, n_clusters, factor)


def tsls(
    y: ArrayLike,
    endog: ArrayLike,
    instrument: ArrayLike,
    *,
    cluster: ArrayLike,
    controls: ArrayLike | None = None,
    weights: ArrayLike | None = None,
    small_sample: bool = True,
) -> IvFit:
    """Exactly identified 2SLS of ``y`` on ``endog`` with one ``instrument``.

    ``controls`` is an optional ``(n, k)`` matrix of exogenous regressors (a constant is
    always included; fixed effects are passed as dummy columns). ``cluster`` labels the
    clusters. Returns the IV coefficient, the first stage and reduced form of the same
    specification, and ``first_stage_f``, the square of the instrument's cluster-robust
    t-statistic in the first stage. Raises ``ValueError`` for mismatched or non-finite
    inputs, negative weights, fewer than two clusters, or an instrument that does not
    move the regressor.
    """
    yy = _vector(y, "y")
    n = yy.shape[0]
    d, z = _vector(endog, "endog", n), _vector(instrument, "instrument", n)
    w = np.ones(n) if weights is None else _vector(weights, "weights", n)
    if np.any(w < 0) or w.sum() <= 0:
        raise ValueError("weights must be non-negative with a positive sum")
    ctrl = np.empty((n, 0)) if controls is None else np.asarray(controls, dtype=float)
    if ctrl.ndim != 2 or ctrl.shape[0] != n or not np.all(np.isfinite(ctrl)):
        raise ValueError("controls must be a finite (n, k) matrix")
    labels = np.asarray(cluster)
    if labels.shape != (n,):
        raise ValueError("cluster must have one label per row")
    codes = np.unique(labels, return_inverse=True)[1].astype(np.intp)
    n_clusters = int(codes.max()) + 1
    if n_clusters < 2:
        raise ValueError("cluster-robust inference needs at least two clusters")

    root = np.sqrt(w)[:, None]
    base = np.column_stack([np.ones(n), ctrl])
    x_full = root * np.column_stack([d, base])
    z_full = root * np.column_stack([z, base])
    ys = root[:, 0] * yy
    beta, cov = _fit(ys, x_full, z_full, codes, n_clusters, small_sample)

    # first stage and reduced form: OLS of each on the instrument and the controls
    ols = root * np.column_stack([z, base])
    fs_beta, fs_cov = _fit(root[:, 0] * d, ols, ols, codes, n_clusters, small_sample)
    rf_beta, rf_cov = _fit(ys, ols, ols, codes, n_clusters, small_sample)
    fs_se = float(np.sqrt(fs_cov[0, 0]))
    return IvFit(
        coef=float(beta[0]),
        se=float(np.sqrt(cov[0, 0])),
        first_stage_coef=float(fs_beta[0]),
        first_stage_se=fs_se,
        first_stage_f=float((fs_beta[0] / fs_se) ** 2) if fs_se > 0 else float("inf"),
        reduced_form_coef=float(rf_beta[0]),
        reduced_form_se=float(np.sqrt(rf_cov[0, 0])),
        n_obs=int(n),
        n_clusters=n_clusters,
        n_params=int(x_full.shape[1]),
    )
