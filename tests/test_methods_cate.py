"""Known-answer tests for ``krl_tutorials_data.methods.cate``.

Written before the module. The functions are pure numpy/pandas; nothing here imports ``econml``.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from krl_tutorials_data.methods import cate

KEY = ["a", "b"]


def _wide() -> pd.DataFrame:
    """Three covariate cells: one with both arms, one with only treated records, one with both."""
    return pd.DataFrame({"a": [1, 1, 2], "b": [0, 1, 0], "n1": [10.0, 5.0, 2.0], "e1": [4.0, 5.0, 1.0],
                         "n0": [20.0, 0.0, 8.0], "e0": [5.0, 0.0, 2.0]})


# ------------------------------------------------------------------------------------------------ cell units
def test_cell_units_makes_one_row_per_cell_and_arm_with_the_arm_rate_and_record_count() -> None:
    out = cate.cell_units(_wide(), KEY)
    f = out.units.sort_values(["cell", "treated"]).reset_index(drop=True)
    assert len(f) == 4 and list(f["treated"]) == [0, 1, 0, 1]
    np.testing.assert_allclose(f["rate"], [5 / 20, 4 / 10, 2 / 8, 1 / 2])
    np.testing.assert_allclose(f["n"], [20, 10, 8, 2])
    # the two arms of a covariate cell share its id, and different cells have different ids
    assert f["cell"].iloc[0] == f["cell"].iloc[1] and f["cell"].iloc[2] == f["cell"].iloc[3] and f["cell"].iloc[0] != f["cell"].iloc[2]


def test_cell_units_drops_cells_without_both_arms_and_reports_what_it_dropped() -> None:
    out = cate.cell_units(_wide(), KEY)
    assert out.cells_total == 3 and out.cells_kept == 2 and out.cells_dropped == 1
    assert out.treated_records_total == 17.0 and out.treated_records_kept == 12.0
    assert out.treated_share_kept == pytest.approx(12 / 17)


def test_cell_units_carries_the_key_columns_so_the_forest_can_use_them() -> None:
    out = cate.cell_units(_wide(), KEY)
    assert set(KEY) <= set(out.units.columns)
    assert sorted(out.units.loc[out.units["treated"] == 1, "a"].tolist()) == [1, 2]


@pytest.mark.parametrize("mutate", [
    lambda d: d.assign(e1=d["n1"] + 1),                 # more events than records
    lambda d: d.assign(e0=-d["e0"] - 1),                # negative events
    lambda d: d.drop(columns=["n0"]),                   # a count column missing
])
def test_cell_units_rejects_impossible_or_missing_counts(mutate) -> None:
    with pytest.raises(ValueError):
        cate.cell_units(mutate(_wide()), KEY)


def test_cell_units_rejects_a_missing_key_column_and_an_empty_overlap() -> None:
    with pytest.raises(ValueError, match="key"):
        cate.cell_units(_wide(), ["a", "zzz"])
    only_treated = _wide().assign(n0=0.0, e0=0.0)
    with pytest.raises(ValueError, match="both arms"):
        cate.cell_units(only_treated, KEY)


# ---------------------------------------------------------------------------------------------- calibration
def _design(n: int = 60, groups: int = 12, seed: int = 3):
    rng = np.random.default_rng(seed)
    tau = rng.normal(size=n)
    t_res = rng.normal(size=n)
    w = rng.integers(1, 9, size=n).astype(float)
    cl = np.repeat(np.arange(groups), n // groups)
    return tau, t_res, w, cl


def test_calibration_recovers_exact_coefficients_when_the_outcome_is_built_from_them() -> None:
    tau, t_res, w, cl = _design()
    wbar = np.average(tau, weights=w)
    y = t_res * (1.5 * wbar + 0.25 * (tau - wbar))       # noise-free: beta1 = 1.5, beta2 = 0.25
    r = cate.blp_calibration(y, t_res, tau, weights=w, clusters=cl)
    np.testing.assert_allclose(r.coef, [1.5, 0.25], atol=1e-10)
    np.testing.assert_allclose(r.se, 0.0, atol=1e-8)


def test_calibration_matches_statsmodels_weighted_least_squares_with_clustered_errors() -> None:
    tau, t_res, w, cl = _design()
    rng = np.random.default_rng(11)
    wbar = np.average(tau, weights=w)
    y = t_res * (0.8 * wbar + 0.4 * (tau - wbar)) + rng.normal(scale=0.7, size=len(tau))
    r = cate.blp_calibration(y, t_res, tau, weights=w, clusters=cl)
    X = np.column_stack([t_res * wbar, t_res * (tau - wbar)])
    ref = sm.WLS(y, X, weights=w).fit(cov_type="cluster", cov_kwds={"groups": cl})
    np.testing.assert_allclose(r.coef, ref.params, rtol=1e-10)
    np.testing.assert_allclose(r.se, ref.bse, rtol=1e-8)
    np.testing.assert_allclose(r.lo, ref.params - 1.959963984540054 * ref.bse, rtol=1e-8)
    np.testing.assert_allclose(r.hi, ref.params + 1.959963984540054 * ref.bse, rtol=1e-8)
    assert r.n_units == len(tau) and r.n_clusters == 12


def test_calibration_point_estimates_do_not_change_when_a_row_is_repeated_as_a_weight() -> None:
    tau, t_res, w, cl = _design(n=24, groups=6)
    rng = np.random.default_rng(5)
    y = rng.normal(size=len(tau))
    a = cate.blp_calibration(y, t_res, tau, weights=np.full(len(tau), 2.0), clusters=cl)
    b = cate.blp_calibration(y, t_res, tau, weights=np.full(len(tau), 1.0), clusters=cl)
    np.testing.assert_allclose(a.coef, b.coef, rtol=1e-12)


def test_calibration_rejects_bad_input() -> None:
    tau, t_res, w, cl = _design()
    y = np.zeros(len(tau))
    with pytest.raises(ValueError, match="length"):
        cate.blp_calibration(y[:-1], t_res, tau, weights=w, clusters=cl)
    with pytest.raises(ValueError, match="positive"):
        cate.blp_calibration(y, t_res, tau, weights=np.where(np.arange(len(w)) == 0, 0.0, w), clusters=cl)
    with pytest.raises(ValueError, match="two clusters"):
        cate.blp_calibration(y, t_res, tau, weights=w, clusters=np.zeros(len(tau), dtype=int))
    with pytest.raises(ValueError, match="vary"):
        cate.blp_calibration(y, t_res, np.full(len(tau), 0.3), weights=w, clusters=cl)       # a constant forecast has no heterogeneity part


def test_detectable_coefficient_is_the_standard_error_times_the_two_normal_quantiles() -> None:
    assert cate.detectable_coefficient(0.1) == pytest.approx((1.959963984540054 + 0.8416212335729143) * 0.1)
    assert cate.detectable_coefficient(0.1, alpha=0.10, power=0.9) == pytest.approx((1.6448536269514722 + 1.2815515655446004) * 0.1)
    with pytest.raises(ValueError):
        cate.detectable_coefficient(-1.0)
