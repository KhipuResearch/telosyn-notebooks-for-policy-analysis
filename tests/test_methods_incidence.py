"""Known-answer tests for ``krl_tutorials_data.methods.incidence``.

Hand arithmetic.

* Kish: unit weights on n records give n_eff = n; weights (1, 3) give (1 + 3)^2 / (1 + 9) = 1.6.
* Share, unit weights, n = 100, 30 in the group: p = 0.3, se = sqrt(0.3 * 0.7 / 100) = 0.0458258,
  95% interval p +/- 1.959964 * se.
* Bin allocation, five equal-weight bins [0,10) ... [40,50), five groups: each bin is one group.
* Bin allocation, weights (3, 2), five groups of weight 1: bin 0 (weight 3) splits 1/3 each to
  groups 0, 1, 2; bin 1 (weight 2) splits 1/2 each to groups 3, 4; boundaries at 10/3, 20/3, 10, 15.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from krl_tutorials_data.methods import incidence

Z95 = 1.959963984540054


def test_kish_unit_weights_is_n() -> None:
    assert incidence.kish_effective_n(sum_w=100.0, sum_w2=100.0) == pytest.approx(100.0)


def test_kish_unequal_weights_by_hand() -> None:
    assert incidence.kish_effective_n(sum_w=4.0, sum_w2=10.0) == pytest.approx(1.6)


def test_kish_rejects_nonpositive() -> None:
    with pytest.raises(ValueError):
        incidence.kish_effective_n(sum_w=0.0, sum_w2=1.0)
    with pytest.raises(ValueError):
        incidence.kish_effective_n(sum_w=1.0, sum_w2=0.0)


def test_share_lower_bound_by_hand() -> None:
    r = incidence.share_with_lower_bound(
        group_w=30.0, total_w=100.0, total_w2=100.0
    )
    se = math.sqrt(0.3 * 0.7 / 100)
    assert r.share == pytest.approx(0.3, abs=1e-12)
    assert r.se == pytest.approx(se, abs=1e-12)
    assert r.low == pytest.approx(0.3 - Z95 * se, abs=1e-12)
    assert r.high == pytest.approx(0.3 + Z95 * se, abs=1e-12)
    assert r.n_effective == pytest.approx(100.0)


def test_share_interval_is_clipped_to_unit_interval() -> None:
    r = incidence.share_with_lower_bound(group_w=1.0, total_w=1000.0, total_w2=1000.0)
    assert r.low >= 0.0
    r = incidence.share_with_lower_bound(group_w=1000.0, total_w=1000.0, total_w2=1000.0)
    assert r.se == 0.0 and r.low == 1.0 and r.high == 1.0


def test_share_rejects_group_larger_than_total() -> None:
    with pytest.raises(ValueError):
        incidence.share_with_lower_bound(group_w=2.0, total_w=1.0, total_w2=1.0)


def test_equal_bins_map_one_to_one() -> None:
    bins = pd.DataFrame({"bin": [0, 10, 20, 30, 40], "weight": [1.0] * 5})
    fr, edges = incidence.bin_group_fractions(bins, width=10.0, groups=5)
    np.testing.assert_allclose(fr.to_numpy(), np.eye(5), atol=1e-12)
    np.testing.assert_allclose(edges["boundary"].to_numpy(), [10.0, 20.0, 30.0, 40.0], atol=1e-9)


def test_split_bins_by_hand() -> None:
    bins = pd.DataFrame({"bin": [0, 10], "weight": [3.0, 2.0]})
    fr, edges = incidence.bin_group_fractions(bins, width=10.0, groups=5)
    np.testing.assert_allclose(
        fr.to_numpy(),
        [[1 / 3, 1 / 3, 1 / 3, 0.0, 0.0], [0.0, 0.0, 0.0, 0.5, 0.5]],
        atol=1e-12,
    )
    np.testing.assert_allclose(
        edges["boundary"].to_numpy(), [10 / 3, 20 / 3, 10.0, 15.0], atol=1e-9
    )
    # the bin holding each boundary, as a share of the population
    np.testing.assert_allclose(edges["bin_share"].to_numpy(), [0.6, 0.6, 0.4, 0.4], atol=1e-12)


def test_rows_sum_to_one_and_columns_to_total() -> None:
    rng = np.random.default_rng(7)
    w = rng.uniform(0.5, 5.0, 40)
    bins = pd.DataFrame({"bin": np.arange(40) * 1000.0, "weight": w})
    fr, _ = incidence.bin_group_fractions(bins, width=1000.0, groups=5)
    np.testing.assert_allclose(fr.sum(axis=1).to_numpy(), 1.0, atol=1e-12)
    np.testing.assert_allclose((fr.mul(w, axis=0)).sum().to_numpy(), w.sum() / 5, atol=1e-9)


def test_unsorted_bins_are_sorted_not_trusted() -> None:
    a = pd.DataFrame({"bin": [10, 0], "weight": [2.0, 3.0]})
    fr, _ = incidence.bin_group_fractions(a, width=10.0, groups=5)
    assert fr.index.tolist() == [0, 10]


def test_rejects_duplicate_bins_and_bad_arguments() -> None:
    with pytest.raises(ValueError):
        incidence.bin_group_fractions(
            pd.DataFrame({"bin": [0, 0], "weight": [1.0, 1.0]}), width=10.0, groups=5
        )
    with pytest.raises(ValueError):
        incidence.bin_group_fractions(
            pd.DataFrame({"bin": [0], "weight": [-1.0]}), width=10.0, groups=5
        )
    with pytest.raises(ValueError):
        incidence.bin_group_fractions(
            pd.DataFrame({"bin": [0], "weight": [1.0]}), width=10.0, groups=1
        )
