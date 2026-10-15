"""Unit tests for the inequality measures.

These use constructed inputs with analytically known answers. That is unit
testing, not synthetic analysis: no number produced here is ever reported as a
finding about the world.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import numpy as np
import pytest

from krl_tutorials_data.inequality import (
    BracketScheme, lorenz_curve, gini_from_lorenz, gini_from_brackets,
)

FLAT = BracketScheme(edges=(0, 100, 200, 300), top_mean=350.0, top_mean_basis="test")


def test_perfect_equality_gives_gini_zero() -> None:
    """Everyone in one income level -> Lorenz curve is the diagonal -> G = 0."""
    pop, inc = lorenz_curve([100], [50_000])
    assert gini_from_lorenz(pop, inc) == pytest.approx(0.0, abs=1e-12)


def test_equal_counts_equal_incomes_gives_gini_zero() -> None:
    pop, inc = lorenz_curve([10, 10, 10, 10], [7, 7, 7, 7])
    assert gini_from_lorenz(pop, inc) == pytest.approx(0.0, abs=1e-12)


def test_maximal_inequality_approaches_one() -> None:
    """One household holds all income; G -> 1 - 1/n for n households."""
    n = 1000
    counts = [n - 1, 1]
    incomes = [0.0, 1.0]
    pop, inc = lorenz_curve(counts, incomes)
    g = gini_from_lorenz(pop, inc)
    assert g == pytest.approx(1.0 - 1.0 / n, abs=1e-9)


def test_two_equal_groups_double_income_known_value() -> None:
    """Half earn 1, half earn 2. Analytic Gini for this discrete case is 1/6."""
    pop, inc = lorenz_curve([50, 50], [1.0, 2.0])
    assert gini_from_lorenz(pop, inc) == pytest.approx(1.0 / 6.0, abs=1e-12)


def test_gini_is_scale_invariant() -> None:
    """Multiplying every income by a constant must not change inequality."""
    counts = [12, 30, 25, 9]
    base = gini_from_lorenz(*lorenz_curve(counts, [10, 20, 45, 90]))
    scaled = gini_from_lorenz(*lorenz_curve(counts, [1000, 2000, 4500, 9000]))
    assert base == pytest.approx(scaled, abs=1e-12)


def test_lorenz_curve_is_monotone_and_bounded() -> None:
    pop, inc = lorenz_curve([5, 20, 40, 20, 15], [8_000, 25_000, 55_000, 90_000, 300_000])
    assert pop[0] == 0.0 and inc[0] == 0.0
    assert pop[-1] == pytest.approx(1.0) and inc[-1] == pytest.approx(1.0)
    assert np.all(np.diff(pop) >= 0) and np.all(np.diff(inc) >= 0)
    assert np.all(inc <= pop + 1e-12), "Lorenz curve may never rise above the diagonal"


def test_negative_values_raise_rather_than_silently_compute() -> None:
    """An unremoved ACS jam value must stop the computation, not skew it."""
    with pytest.raises(ValueError, match="sentinel"):
        lorenz_curve([10, -666666666], [20_000, 50_000])


def test_mismatched_shapes_raise() -> None:
    with pytest.raises(ValueError, match="shape"):
        lorenz_curve([1, 2, 3], [10, 20])


def test_zero_households_raise() -> None:
    with pytest.raises(ValueError, match="zero"):
        lorenz_curve([0, 0], [10, 20])


def test_bracket_scheme_midpoints_use_stated_top_mean() -> None:
    mids = FLAT.midpoints()
    assert mids[:-1].tolist() == [50.0, 150.0, 250.0]
    assert mids[-1] == 350.0, "the open-ended top bracket must use the stated assumption"


# --------------------------------------------------------------------------- #
# Alternative measures: tested against their known analytic properties.
# --------------------------------------------------------------------------- #

from krl_tutorials_data.inequality import (  # noqa: E402
    theil_t, atkinson, percentile_from_brackets, percentile_ratio, top_share,
)

EQUAL_COUNTS = [25, 25, 25, 25]
EQUAL_INCOMES = [50_000.0] * 4
SPREAD_COUNTS = [10, 30, 40, 20]
SPREAD_INCOMES = [12_000.0, 35_000.0, 68_000.0, 190_000.0]


def test_theil_is_zero_under_perfect_equality() -> None:
    assert theil_t(EQUAL_COUNTS, EQUAL_INCOMES) == pytest.approx(0.0, abs=1e-12)


def test_theil_is_positive_under_inequality() -> None:
    assert theil_t(SPREAD_COUNTS, SPREAD_INCOMES) > 0


def test_theil_is_scale_invariant() -> None:
    base = theil_t(SPREAD_COUNTS, SPREAD_INCOMES)
    scaled = theil_t(SPREAD_COUNTS, [v * 7.3 for v in SPREAD_INCOMES])
    assert base == pytest.approx(scaled, abs=1e-12)


def test_atkinson_is_zero_under_perfect_equality_at_every_epsilon() -> None:
    for eps in (0.25, 0.5, 1.0, 2.0):
        assert atkinson(EQUAL_COUNTS, EQUAL_INCOMES, epsilon=eps) == pytest.approx(0.0, abs=1e-12)


def test_atkinson_is_bounded_in_unit_interval() -> None:
    for eps in (0.5, 1.0, 2.0):
        a = atkinson(SPREAD_COUNTS, SPREAD_INCOMES, epsilon=eps)
        assert 0.0 <= a <= 1.0


def test_atkinson_increases_with_inequality_aversion() -> None:
    """Higher epsilon weights the bottom more heavily, so the index rises."""
    a_low = atkinson(SPREAD_COUNTS, SPREAD_INCOMES, epsilon=0.5)
    a_mid = atkinson(SPREAD_COUNTS, SPREAD_INCOMES, epsilon=1.0)
    a_high = atkinson(SPREAD_COUNTS, SPREAD_INCOMES, epsilon=2.0)
    assert a_low < a_mid < a_high


def test_atkinson_epsilon_one_uses_the_geometric_mean_limit() -> None:
    """At epsilon = 1, A = 1 - (geometric mean / arithmetic mean)."""
    c = np.array(SPREAD_COUNTS, dtype=float)
    y = np.array(SPREAD_INCOMES, dtype=float)
    share = c / c.sum()
    arith = (c * y).sum() / c.sum()
    geo = np.exp((share * np.log(y)).sum())
    assert atkinson(SPREAD_COUNTS, SPREAD_INCOMES, epsilon=1.0) == pytest.approx(1 - geo / arith)


def test_atkinson_rejects_negative_aversion() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        atkinson(SPREAD_COUNTS, SPREAD_INCOMES, epsilon=-0.5)


def test_percentile_is_monotone_in_q() -> None:
    vals = [percentile_from_brackets(SPREAD_COUNTS, SPREAD_INCOMES, q)
            for q in (0.1, 0.25, 0.5, 0.75, 0.9)]
    assert all(a <= b for a, b in zip(vals, vals[1:]))


def test_percentile_rejects_out_of_range_q() -> None:
    for bad in (0.0, 1.0, -0.2, 1.5):
        with pytest.raises(ValueError, match="strictly between"):
            percentile_from_brackets(SPREAD_COUNTS, SPREAD_INCOMES, bad)


def test_percentile_ratio_is_one_under_perfect_equality() -> None:
    assert percentile_ratio(EQUAL_COUNTS, EQUAL_INCOMES) == pytest.approx(1.0)


def test_percentile_ratio_exceeds_one_under_inequality() -> None:
    assert percentile_ratio(SPREAD_COUNTS, SPREAD_INCOMES) > 1.0


def test_top_share_equals_the_population_share_under_equality() -> None:
    """If everyone earns the same, the top 10% hold 10% of income.

    The fixture puts 25% of units in the final bracket, which trips the
    identification guard. That is incidental to the mathematical property under
    test here, so it is acknowledged explicitly rather than worked around.
    """
    assert top_share(EQUAL_COUNTS, EQUAL_INCOMES, top=0.10,
                     allow_unidentified=True) == pytest.approx(0.10, abs=1e-9)


def test_top_share_exceeds_population_share_under_inequality() -> None:
    assert top_share(SPREAD_COUNTS, SPREAD_INCOMES, top=0.10,
                     allow_unidentified=True) > 0.10


def test_top_share_rejects_out_of_range() -> None:
    with pytest.raises(ValueError, match="strictly between"):
        top_share(SPREAD_COUNTS, SPREAD_INCOMES, top=1.0)


def test_measures_reject_unremoved_sentinels() -> None:
    for fn in (theil_t, atkinson, percentile_ratio):
        with pytest.raises(ValueError, match="sentinel"):
            fn([10, -666666666], [20_000.0, 50_000.0])
    # top_share validates counts before the identification check, so a sentinel
    # surfaces as a sentinel rather than as an identification failure.
    with pytest.raises(ValueError, match="sentinel"):
        top_share([10, -666666666], [20_000.0, 50_000.0], allow_unidentified=True)


# --------------------------------------------------------------------------- #
# Top-share identification. The unguarded statistic correlates at about -0.95
# with the open-bracket share across US states: it measures the bracket cap.
# --------------------------------------------------------------------------- #

from krl_tutorials_data.inequality import (  # noqa: E402
    open_bracket_share, top_share_is_identified, UnidentifiedTopShareError,
)


def test_open_bracket_share_is_the_final_bracket_fraction() -> None:
    assert open_bracket_share([10, 20, 70]) == pytest.approx(0.70)


def test_top_share_is_identified_only_when_open_bracket_is_smaller() -> None:
    assert top_share_is_identified([90, 5], top=0.10)          # 5% < 10%
    assert not top_share_is_identified([80, 20], top=0.10)     # 20% >= 10%
    assert top_share_is_identified([80, 20], top=0.25)         # 20% < 25%


def test_top_share_raises_when_the_top_decile_is_inside_the_open_bracket() -> None:
    counts = [40, 30, 30]          # 30% in the open bracket
    incomes = [10_000.0, 60_000.0, 350_000.0]
    with pytest.raises(UnidentifiedTopShareError, match="bracket cap"):
        top_share(counts, incomes, top=0.10)


def test_top_share_proceeds_when_the_caller_acknowledges_the_limitation() -> None:
    counts = [40, 30, 30]
    incomes = [10_000.0, 60_000.0, 350_000.0]
    v = top_share(counts, incomes, top=0.10, allow_unidentified=True)
    assert 0.0 < v < 1.0


def test_identified_case_still_computes_normally() -> None:
    counts = [90, 5, 5]
    incomes = [20_000.0, 90_000.0, 350_000.0]
    assert top_share(counts, incomes, top=0.10) > 0.10


def test_the_artifact_direction_is_reproducible() -> None:
    """More units in the open bracket -> LOWER measured top share, holding the
    cap fixed. This is the mechanism behind the -0.95 correlation."""
    incomes = [20_000.0, 80_000.0, 350_000.0]
    few = top_share([90, 8, 2], incomes, top=0.10, allow_unidentified=True)
    many = top_share([50, 20, 30], incomes, top=0.10, allow_unidentified=True)
    assert many < few
