"""Cell units for a heterogeneous-effects forest, and the calibration regression that checks it.

Both functions are pure numpy and pandas. **Nothing here imports ``econml``** (or any forest library): the forest
is fitted in the notebook, and these functions build its units and test its forecast, so the library tests run
without the optional dependency (DECISIONS/0011).

Units
    The PUMS client returns weighted cells and no person rows. :func:`cell_units` turns the covariate-cell table
    (treated and untreated record counts and employed counts per covariate cell) into **one row per covariate cell
    and treatment arm**: the arm's outcome rate and its record count, which a forest uses as the outcome and the
    sample weight. A forest fitted on these rows is honest and resampled over *cells and arms*, not over people,
    so its intervals are cell-level; they are not person-level intervals.

Calibration
    :func:`blp_calibration` is the best-linear-predictor test of Chernozhukov, Demirer, Duflo and
    Fernandez-Val: regress the outcome minus its predicted value on ``(T - e)`` times the mean predicted effect
    and on ``(T - e)`` times the predicted effect minus its mean, by weighted least squares with cluster-robust
    errors. The second coefficient is one when the forecast of heterogeneity is right and zero when the forest
    has found none.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike
from scipy import stats

__all__ = ["BlpResult", "CellUnits", "blp_calibration", "cell_units", "detectable_coefficient"]

_COUNTS = ("n1", "e1", "n0", "e0")


@dataclass(frozen=True)
class CellUnits:
    """Units for a forest, and what building them dropped."""

    units: pd.DataFrame            # key columns, ``cell`` (id), ``treated`` (0/1), ``n`` (records), ``rate`` (events / records)
    cells_total: int
    cells_kept: int
    treated_records_total: float
    treated_records_kept: float

    @property
    def cells_dropped(self) -> int:
        """Covariate cells without both arms."""
        return self.cells_total - self.cells_kept

    @property
    def treated_share_kept(self) -> float:
        """Share of treated records that sit in covariate cells with both arms."""
        return self.treated_records_kept / self.treated_records_total


def cell_units(wide: pd.DataFrame, key: Sequence[str]) -> CellUnits:
    """One row per covariate cell and treatment arm, from a table with one row per covariate cell.

    ``wide`` holds the ``key`` columns and four counts per covariate cell: ``n1``/``e1`` (records and events among the
    treated) and ``n0``/``e0`` (among the untreated). A cell without records in both arms has no comparison and is
    dropped; the share of treated records that survives is reported. Raises ``ValueError`` for a missing column,
    a negative count, more events than records, or no cell with both arms.
    """
    missing = [c for c in (*key, *_COUNTS) if c not in wide.columns]
    if missing:
        raise ValueError(f"the table needs the key and count columns; missing {missing}")
    counts = wide[list(_COUNTS)].to_numpy(dtype=float)
    if np.any(counts < 0):
        raise ValueError("counts must not be negative")
    if np.any(wide["e1"] > wide["n1"]) or np.any(wide["e0"] > wide["n0"]):
        raise ValueError("events cannot exceed records in an arm")
    both = (wide["n1"] > 0) & (wide["n0"] > 0)
    if not both.any():
        raise ValueError("no covariate cell holds both arms")
    kept = wide.loc[both].reset_index(drop=True)
    kept = kept.assign(cell=np.arange(len(kept)))
    parts = []
    for flag in (1, 0):
        part = kept[[*key, "cell"]].copy()
        part["treated"] = flag
        part["n"] = kept[f"n{flag}"].to_numpy(dtype=float)
        part["rate"] = kept[f"e{flag}"].to_numpy(dtype=float) / part["n"]
        parts.append(part)
    units = pd.concat(parts, ignore_index=True)
    return CellUnits(units=units, cells_total=len(wide), cells_kept=int(both.sum()),
                     treated_records_total=float(wide["n1"].sum()), treated_records_kept=float(kept["n1"].sum()))


@dataclass(frozen=True)
class BlpResult:
    """Coefficients of the calibration regression: ``[mean forecast, heterogeneity forecast]``."""

    coef: np.ndarray
    se: np.ndarray
    lo: np.ndarray
    hi: np.ndarray
    n_units: int
    n_clusters: int


def blp_calibration(
    y_resid: ArrayLike,
    t_resid: ArrayLike,
    tau_hat: ArrayLike,
    *,
    weights: ArrayLike,
    clusters: ArrayLike,
    alpha: float = 0.05,
) -> BlpResult:
    """Best-linear-predictor calibration of a forecast of heterogeneous effects.

    Regress ``y_resid`` (the outcome minus its cross-fitted prediction) on
    ``t_resid * mean(tau_hat)`` and ``t_resid * (tau_hat - mean(tau_hat))`` with no intercept, weighted least
    squares, ``weights`` the record counts, and the mean of ``tau_hat`` weighted the same way. ``t_resid`` is the
    treatment minus its cross-fitted propensity. The standard error is the cluster-robust sandwich over
    ``clusters`` with the small-sample factor ``G/(G-1) * (N-1)/(N-k)``, and the interval uses the normal quantile.
    Raises ``ValueError`` for unequal lengths, a non-positive weight, fewer than two clusters, or a forecast that
    does not vary (its heterogeneity regressor is then zero).
    """
    y, t, tau = (np.asarray(a, dtype=float) for a in (y_resid, t_resid, tau_hat))
    w, g = np.asarray(weights, dtype=float), np.asarray(clusters)
    if not (y.shape == t.shape == tau.shape == w.shape == g.shape) or y.ndim != 1:
        raise ValueError("all inputs must be one-dimensional and of equal length")
    if np.any(w <= 0):
        raise ValueError("weights must be positive")
    labels = np.unique(g)
    if len(labels) < 2:
        raise ValueError("cluster-robust errors need at least two clusters")
    wbar = float(np.average(tau, weights=w))
    x = np.column_stack([t * wbar, t * (tau - wbar)])
    if not np.any(x[:, 1] != 0):
        raise ValueError("the forecast must vary: the heterogeneity regressor is zero")
    n, k = x.shape
    xtwx = x.T @ (x * w[:, None])
    try:
        bread = np.linalg.inv(xtwx)
    except np.linalg.LinAlgError as exc:
        raise ValueError("the regressors are collinear") from exc
    coef = bread @ (x.T @ (w * y))
    score = x * (w * (y - x @ coef))[:, None]
    meat = np.zeros((k, k))
    for label in labels:
        s = score[g == label].sum(axis=0)
        meat += np.outer(s, s)
    n_g = len(labels)
    cov = (n_g / (n_g - 1)) * ((n - 1) / (n - k)) * bread @ meat @ bread
    se = np.sqrt(np.diag(cov))
    z = float(stats.norm.ppf(1 - alpha / 2))
    return BlpResult(coef=coef, se=se, lo=coef - z * se, hi=coef + z * se, n_units=n, n_clusters=n_g)


def detectable_coefficient(se: float, *, alpha: float = 0.05, power: float = 0.8) -> float:
    """Smallest true coefficient a two-sided test at ``alpha`` detects with probability ``power``: ``(z_{1-a/2} + z_power) * se``."""
    if not se >= 0:
        raise ValueError("the standard error must be non-negative")
    return float((stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)) * se)
