"""Tests for direct standardisation and the Kitagawa decomposition.

The decomposition is an algebraic identity, so it is tested as one: over
randomised inputs the two components must sum to the crude difference. A test
that only checked a hand-computed example would not catch a sign error in a
branch the example never reaches.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import numpy as np
import pytest

from krl_tutorials_data.standardization import (
    KitagawaSplit,
    StandardPopulation,
    StandardizationError,
    crude_rate,
    direct_standardized_rate,
    kitagawa_decomposition,
    standardized_rate_estimate,
    standardized_rate_bounds,
)
from krl_tutorials_data.uncertainty import Estimate

LABELS = ("young", "middle", "old")


def _std(counts) -> StandardPopulation:
    return StandardPopulation.from_counts("test standard", LABELS, counts)


# --------------------------------------------------------------------------
# StandardPopulation
# --------------------------------------------------------------------------

def test_from_counts_normalises_to_unit_sum():
    std = _std([100, 200, 700])
    assert std.weights.sum() == pytest.approx(1.0)
    assert std.weights.tolist() == pytest.approx([0.1, 0.2, 0.7])


def test_weights_not_summing_to_one_are_rejected():
    with pytest.raises(StandardizationError, match="sum to"):
        StandardPopulation("bad", LABELS, np.array([0.5, 0.2, 0.2]))


def test_negative_weight_rejected():
    with pytest.raises(StandardizationError, match=">= 0"):
        StandardPopulation("bad", LABELS, np.array([1.2, -0.1, -0.1]))


def test_label_weight_length_mismatch_rejected():
    with pytest.raises(StandardizationError, match="labels but"):
        StandardPopulation("bad", ("a", "b"), np.array([0.5, 0.3, 0.2]))


def test_zero_total_standard_rejected():
    with pytest.raises(StandardizationError, match="zero total"):
        StandardPopulation.from_counts("bad", LABELS, [0, 0, 0])


# --------------------------------------------------------------------------
# Structural guards
# --------------------------------------------------------------------------

def test_events_exceeding_population_is_a_universe_mismatch():
    with pytest.raises(StandardizationError, match="universe mismatch"):
        crude_rate([5, 1, 1], [4, 10, 10])


def test_shape_mismatch_rejected():
    with pytest.raises(StandardizationError, match="shape"):
        crude_rate([1, 2], [10, 20, 30])


def test_standard_group_count_must_match():
    std = _std([1, 1, 1])
    with pytest.raises(StandardizationError, match="groups but"):
        direct_standardized_rate([1, 2], [10, 20], std)


# --------------------------------------------------------------------------
# Direct standardisation
# --------------------------------------------------------------------------

def test_standardising_to_own_composition_reproduces_the_crude_rate():
    """The defining property: a population standardised to itself is unchanged."""
    events = [30.0, 50.0, 120.0]
    pop = [300.0, 1000.0, 600.0]
    own = _std(pop)
    assert direct_standardized_rate(events, pop, own) == pytest.approx(
        crude_rate(events, pop)
    )


def test_uniform_group_rates_are_invariant_to_the_standard():
    """If every group has the same rate, composition cannot matter."""
    pop = [400.0, 100.0, 1500.0]
    events = [p * 0.12 for p in pop]
    for counts in ([1, 1, 1], [90, 5, 5], [5, 5, 90]):
        assert direct_standardized_rate(events, pop, _std(counts)) == pytest.approx(0.12)


def test_standardisation_moves_the_rate_toward_the_standard_weighting():
    """An old-heavy standard raises the rate when old people have higher rates."""
    pop = [1000.0, 1000.0, 100.0]
    events = [10.0, 50.0, 40.0]  # rates 1%, 5%, 40%
    young_std = _std([90, 9, 1])
    old_std = _std([1, 9, 90])
    assert direct_standardized_rate(events, pop, old_std) > direct_standardized_rate(
        events, pop, young_std
    )


def test_empty_group_raises_by_default_and_names_the_group():
    std = _std([1, 1, 1])
    with pytest.raises(StandardizationError, match="old"):
        direct_standardized_rate([1.0, 2.0, 0.0], [10.0, 20.0, 0.0], std)


def test_empty_group_skip_renormalises_and_changes_the_standard():
    std = _std([1, 1, 2])
    got = direct_standardized_rate(
        [10.0, 40.0, 0.0], [100.0, 200.0, 0.0], std, empty_group_policy="skip"
    )
    # Remaining weights 1:1 over rates 0.10 and 0.20.
    assert got == pytest.approx(0.15)


def test_unknown_empty_group_policy_rejected():
    std = _std([1, 1, 1])
    with pytest.raises(StandardizationError, match="empty_group_policy"):
        direct_standardized_rate([1.0, 1.0, 0.0], [10.0, 10.0, 0.0], std, empty_group_policy="drop")


# --------------------------------------------------------------------------
# Kitagawa decomposition -- tested as an identity
# --------------------------------------------------------------------------

@pytest.mark.parametrize("seed", range(40))
def test_decomposition_is_exact_over_random_inputs(seed: int):
    rng = np.random.default_rng(seed)
    k = int(rng.integers(2, 9))
    na = rng.uniform(50, 5000, k)
    nb = rng.uniform(50, 5000, k)
    ea = na * rng.uniform(0, 1, k)
    eb = nb * rng.uniform(0, 1, k)
    split = kitagawa_decomposition(ea, na, eb, nb)
    assert split.rate_effect + split.composition_effect == pytest.approx(
        split.difference, abs=1e-12
    )
    assert abs(split.residual) < 1e-12


def test_identical_rates_leave_only_a_composition_effect():
    na, nb = [100.0, 900.0], [900.0, 100.0]
    ea = [n * r for n, r in zip(na, (0.05, 0.25))]
    eb = [n * r for n, r in zip(nb, (0.05, 0.25))]
    split = kitagawa_decomposition(ea, na, eb, nb)
    assert split.rate_effect == pytest.approx(0.0, abs=1e-12)
    assert split.composition_effect == pytest.approx(split.difference, abs=1e-12)


def test_identical_composition_leaves_only_a_rate_effect():
    na = nb = [500.0, 500.0]
    ea = [50.0, 150.0]
    eb = [25.0, 100.0]
    split = kitagawa_decomposition(ea, na, eb, nb)
    assert split.composition_effect == pytest.approx(0.0, abs=1e-12)
    assert split.rate_effect == pytest.approx(split.difference, abs=1e-12)


def test_reversal_shows_as_opposite_signed_components():
    """Simpson's paradox in decomposition form.

    A is worse in every group, yet has the lower crude rate, because A's
    population is concentrated in the low-rate group. The rate effect must then
    be positive while the crude difference is negative.
    """
    na = [9000.0, 1000.0]   # A: mostly low-rate group
    nb = [1000.0, 9000.0]   # B: mostly high-rate group
    ea = [9000 * 0.06, 1000 * 0.40]
    eb = [1000 * 0.05, 9000 * 0.35]
    split = kitagawa_decomposition(ea, na, eb, nb)
    assert split.crude_a < split.crude_b          # A looks better crude
    assert split.rate_effect > 0                  # A is worse in every group
    assert split.composition_effect < 0
    assert split.composition_share > 1.0          # composition more than explains it


def test_composition_share_is_nan_when_crude_rates_are_equal():
    na = nb = [100.0, 100.0]
    split = kitagawa_decomposition([10.0, 10.0], na, [10.0, 10.0], nb)
    assert np.isnan(split.composition_share)


def test_decomposition_rejects_empty_groups():
    with pytest.raises(StandardizationError, match="zero population"):
        kitagawa_decomposition([1.0, 0.0], [10.0, 0.0], [1.0, 1.0], [10.0, 10.0])


def test_decomposition_rejects_mismatched_group_counts():
    with pytest.raises(StandardizationError, match="same groups"):
        kitagawa_decomposition([1.0, 2.0], [10.0, 20.0], [1.0, 2.0, 3.0], [10.0, 20.0, 30.0])


# --------------------------------------------------------------------------
# Uncertainty propagation
# --------------------------------------------------------------------------

def test_standardised_estimate_matches_the_point_computation():
    std = _std([2, 3, 5])
    events = [Estimate(20.0, 5.0), Estimate(60.0, 9.0), Estimate(150.0, 20.0)]
    pop = [Estimate(400.0, 30.0), Estimate(800.0, 40.0), Estimate(1000.0, 50.0)]
    est = standardized_rate_estimate(events, pop, std)
    point = direct_standardized_rate(
        [e.value for e in events], [p.value for p in pop], std
    )
    assert est.value == pytest.approx(point)
    assert est.moe > 0


def test_zero_input_moes_give_zero_standardised_moe():
    std = _std([1, 1, 1])
    events = [Estimate(10.0, 0.0), Estimate(20.0, 0.0), Estimate(30.0, 0.0)]
    pop = [Estimate(100.0, 0.0), Estimate(100.0, 0.0), Estimate(100.0, 0.0)]
    assert standardized_rate_estimate(events, pop, std).moe == pytest.approx(0.0)


def test_standardised_moe_is_below_the_sum_of_weighted_group_moes():
    """Quadrature, not addition. Adding MOEs overstates the interval."""
    from krl_tutorials_data.uncertainty import proportion_moe

    std = _std([1, 1, 1])
    events = [Estimate(10.0, 4.0), Estimate(20.0, 6.0), Estimate(30.0, 8.0)]
    pop = [Estimate(100.0, 9.0), Estimate(100.0, 9.0), Estimate(100.0, 9.0)]
    est = standardized_rate_estimate(events, pop, std)
    linear = sum(
        w * proportion_moe(e, p) for w, e, p in zip(std.weights, events, pop)
    )
    assert 0 < est.moe < linear


def test_estimate_length_mismatch_rejected():
    std = _std([1, 1, 1])
    with pytest.raises(StandardizationError, match="same length"):
        standardized_rate_estimate(
            [Estimate(1.0, 0.1)], [Estimate(10.0, 1.0), Estimate(10.0, 1.0)], std
        )


def test_zero_population_makes_the_standardised_moe_undefined():
    std = _std([1, 1, 1])
    events = [Estimate(1.0, 0.1), Estimate(1.0, 0.1), Estimate(0.0, 0.0)]
    pop = [Estimate(10.0, 1.0), Estimate(10.0, 1.0), Estimate(0.0, 0.0)]
    with pytest.raises(StandardizationError, match="undefined"):
        standardized_rate_estimate(events, pop, std)


def test_split_is_frozen():
    split = kitagawa_decomposition([1.0], [10.0], [2.0], [10.0])
    assert isinstance(split, KitagawaSplit)
    with pytest.raises(Exception):
        split.difference = 0.0  # type: ignore[misc]


# --------------------------------------------------------------------------
# Correlation bounds
# --------------------------------------------------------------------------

def test_bounds_bracket_the_quadrature_estimate():
    std = _std([2, 3, 5])
    events = [Estimate(20.0, 5.0), Estimate(60.0, 9.0), Estimate(150.0, 20.0)]
    pop = [Estimate(400.0, 30.0), Estimate(800.0, 40.0), Estimate(1000.0, 50.0)]
    lo, hi = standardized_rate_bounds(events, pop, std)
    mid = standardized_rate_estimate(events, pop, std)
    assert lo.value == pytest.approx(mid.value) == pytest.approx(hi.value)
    assert lo.moe == pytest.approx(mid.moe)
    assert hi.moe > lo.moe


def test_bounds_coincide_for_a_single_group():
    std = StandardPopulation("one", ("all",), np.array([1.0]))
    lo, hi = standardized_rate_bounds(
        [Estimate(50.0, 7.0)], [Estimate(500.0, 20.0)], std
    )
    assert lo.moe == pytest.approx(hi.moe)


def test_bounds_reject_zero_population():
    std = _std([1, 1, 1])
    with pytest.raises(StandardizationError, match="undefined"):
        standardized_rate_bounds(
            [Estimate(1.0, 0.1), Estimate(1.0, 0.1), Estimate(0.0, 0.0)],
            [Estimate(10.0, 1.0), Estimate(10.0, 1.0), Estimate(0.0, 0.0)],
            std,
        )
