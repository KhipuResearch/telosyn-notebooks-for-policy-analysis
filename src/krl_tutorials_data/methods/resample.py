"""Resampling states: bootstrap draws for a group mean difference and for a rank correlation.

Estimand
    The sampling distribution of (a) the difference in mean of a quantity between two groups of
    units and (b) Spearman's rank correlation between two quantities across units, when the units are
    resampled with replacement.

Assumptions
    Units are independent and exchangeable within a group; the bootstrap is the percentile
    bootstrap, so intervals are the percentiles of the returned draws. With few units in a group
    (a handful) the percentile interval is unreliable and the notebook that uses it says so.

Estimators
    (a) each draw resamples each group with replacement, at the group's own size, and subtracts the group
    means (group 1 minus group 0). (b) each draw resamples unit pairs; a draw in which either variable does
    not vary is dropped, and the number kept is the length of the result.

Randomness is declared at the call: a required integer ``seed`` builds a private generator. Nothing performs I/O.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import stats  # type: ignore[import-untyped]

Float = NDArray[np.float64]


def bootstrap_mean_difference(y: ArrayLike, group: ArrayLike, *, draws: int, seed: int) -> Float:
    """Bootstrap draws of mean(y | group == 1) - mean(y | group == 0), resampling within each group."""
    values = np.asarray(y, dtype=float)
    flag = np.asarray(group)
    if draws < 1:
        raise ValueError("draws must be at least 1.")
    if values.shape != flag.shape:
        raise ValueError("y and group must have the same length.")
    a, b = values[flag == 1], values[flag == 0]
    if a.size == 0 or b.size == 0:
        raise ValueError("both groups must contain at least one unit.")
    rng = np.random.default_rng(seed)
    ia = rng.integers(0, a.size, size=(draws, a.size))
    ib = rng.integers(0, b.size, size=(draws, b.size))
    return np.asarray(a[ia].mean(axis=1) - b[ib].mean(axis=1), dtype=float)


def bootstrap_spearman(x: ArrayLike, y: ArrayLike, *, draws: int, seed: int) -> Float:
    """Bootstrap draws of Spearman's rho over resampled (x, y) pairs; draws without variation are dropped."""
    xs, ys = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if draws < 1:
        raise ValueError("draws must be at least 1.")
    if xs.shape != ys.shape or xs.ndim != 1:
        raise ValueError("x and y must be one-dimensional and of the same length.")
    rng = np.random.default_rng(seed)
    n = xs.size
    out = []
    for _ in range(draws):
        idx = rng.integers(0, n, n)
        a, b = xs[idx], ys[idx]
        if np.ptp(a) == 0 or np.ptp(b) == 0:
            continue
        out.append(float(stats.spearmanr(a, b)[0]))
    return np.asarray(out, dtype=float)
