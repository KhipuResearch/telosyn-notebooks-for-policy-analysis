"""Known-answer tests for ``krl_tutorials_data.methods.resample``.

Hand arithmetic. Group means of constants: every draw of (3, 3) minus (1, 1) is 2. For group one (0, 2) against
group zero (0, 0), a draw of two values from (0, 2) averages 0, 1 or 2 with probabilities 1/4, 1/2, 1/4, so the mean
of many draws is 1. A perfectly monotone pair has Spearman 1 in every resample that keeps two distinct x values.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import numpy as np
import pytest

from krl_tutorials_data.methods import resample


def test_difference_of_constants_is_constant() -> None:
    y = np.array([3.0, 3.0, 1.0, 1.0])
    g = np.array([1, 1, 0, 0])
    d = resample.bootstrap_mean_difference(y, g, draws=200, seed=1)
    assert d.shape == (200,) and np.all(d == 2.0)


def test_difference_takes_only_the_three_possible_values_and_centres_on_one() -> None:
    y = np.array([0.0, 2.0, 0.0, 0.0])
    g = np.array([1, 1, 0, 0])
    d = resample.bootstrap_mean_difference(y, g, draws=20_000, seed=7)
    assert set(np.unique(d)) <= {0.0, 1.0, 2.0}
    assert d.mean() == pytest.approx(1.0, abs=0.03)
    assert (d == 1.0).mean() == pytest.approx(0.5, abs=0.02)


def test_same_seed_same_draws_different_seed_different() -> None:
    y = np.arange(10.0)
    g = np.array([1] * 5 + [0] * 5)
    a = resample.bootstrap_mean_difference(y, g, draws=50, seed=3)
    b = resample.bootstrap_mean_difference(y, g, draws=50, seed=3)
    c = resample.bootstrap_mean_difference(y, g, draws=50, seed=4)
    assert np.array_equal(a, b) and not np.array_equal(a, c)


def test_difference_rejects_an_empty_group_and_bad_draws() -> None:
    with pytest.raises(ValueError):
        resample.bootstrap_mean_difference(np.array([1.0, 2.0]), np.array([1, 1]), draws=10, seed=1)
    with pytest.raises(ValueError):
        resample.bootstrap_mean_difference(np.array([1.0, 2.0]), np.array([1, 0]), draws=0, seed=1)
    with pytest.raises(ValueError):
        resample.bootstrap_mean_difference(np.array([1.0, 2.0]), np.array([1]), draws=5, seed=1)


def test_spearman_of_a_monotone_pair_is_one_in_every_valid_draw() -> None:
    x = np.arange(1.0, 11.0)
    r = resample.bootstrap_spearman(x, x, draws=300, seed=2)
    assert len(r) > 0 and np.allclose(r, 1.0)


def test_spearman_of_a_reversed_pair_is_minus_one() -> None:
    x = np.arange(1.0, 11.0)
    assert np.allclose(resample.bootstrap_spearman(x, -x, draws=100, seed=2), -1.0)


def test_spearman_drops_draws_with_no_variation_and_constants_give_none() -> None:
    assert resample.bootstrap_spearman(np.ones(5), np.arange(5.0), draws=50, seed=1).size == 0
    x = np.array([0.0, 0.0, 0.0, 0.0, 1.0])
    r = resample.bootstrap_spearman(x, x, draws=2000, seed=5)
    assert 0 < r.size < 2000 and np.allclose(r, 1.0)


def test_spearman_rejects_unequal_lengths() -> None:
    with pytest.raises(ValueError):
        resample.bootstrap_spearman(np.arange(3.0), np.arange(4.0), draws=5, seed=1)
