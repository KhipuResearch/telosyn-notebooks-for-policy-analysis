"""Known-answer tests for ``krl_tutorials_data.methods.cea``.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from krl_tutorials_data.methods import cea


def test_icer_on_a_two_strategy_table() -> None:
    """A: cost 100, effect 1.0.  B: cost 300, effect 1.5.  ICER = 200 / 0.5 = 400."""
    r = cea.icer(cost=300.0, effect=1.5, ref_cost=100.0, ref_effect=1.0)
    assert r.status == "icer"
    assert r.ratio == pytest.approx(400.0, abs=1e-12)
    assert (r.delta_cost, r.delta_effect) == (200.0, 0.5)


@pytest.mark.parametrize(
    ("cost", "effect", "status"),
    [
        (50.0, 1.5, "dominant"),     # cheaper and better
        (300.0, 0.5, "dominated"),   # dearer and worse
        (50.0, 0.5, "icer_saving"),  # cheaper and worse: ratio is a saving per unit lost
        (300.0, 1.0, "no_difference_in_effect"),
    ],
)
def test_icer_status_covers_every_quadrant(cost: float, effect: float, status: str) -> None:
    """Icer status covers every quadrant."""
    r = cea.icer(cost=cost, effect=effect, ref_cost=100.0, ref_effect=1.0)
    assert r.status == status
    if status in ("dominant", "dominated", "no_difference_in_effect"):
        assert r.ratio is None
    else:
        assert r.ratio == pytest.approx(100.0)


def test_frontier_removes_strong_dominance() -> None:
    """Frontier removes strong dominance."""
    steps = cea.efficient_frontier(
        ["A", "B", "C", "D"], costs=[100, 300, 500, 400], effects=[1.0, 1.5, 1.6, 1.0]
    )
    assert [s.name for s in steps] == ["A", "B", "C"]
    assert steps[0].icer is None
    assert steps[1].icer == pytest.approx(400.0)
    assert steps[2].icer == pytest.approx(200.0 / 0.1)


def test_frontier_removes_extended_dominance() -> None:
    """B (300, 1) vs A (0, 0) is 300; C (400, 3) vs B is 100 < 300, so B is extended-dominated."""
    steps = cea.efficient_frontier(["A", "B", "C"], costs=[0, 300, 400], effects=[0, 1, 3])
    assert [s.name for s in steps] == ["A", "C"]
    assert steps[1].icer == pytest.approx(400.0 / 3.0)


def test_frontier_icers_are_increasing() -> None:
    """Frontier icers are increasing."""
    rng = np.random.default_rng(1)
    costs = rng.uniform(0, 1000, 12)
    effects = rng.uniform(0, 5, 12)
    steps = cea.efficient_frontier([str(i) for i in range(12)], costs, effects)
    icers = [s.icer for s in steps if s.icer is not None]
    assert icers == sorted(icers)


def test_net_monetary_benefit_and_ceac_by_hand() -> None:
    """Net monetary benefit and ceac by hand."""
    dc = np.array([10.0, 20.0, 30.0, 40.0])
    de = np.ones(4)
    assert cea.net_monetary_benefit(delta_cost=dc, delta_effect=de, threshold=15.0).tolist() == [
        5.0, -5.0, -15.0, -25.0,
    ]
    curve = cea.ceac(dc, de, thresholds=[15.0, 25.0, 100.0])
    np.testing.assert_allclose(curve.probability, [0.25, 0.5, 1.0])
    assert curve.thresholds.tolist() == [15.0, 25.0, 100.0]


def test_psa_draws_are_seeded_and_match_their_moments() -> None:
    """Psa draws are seeded and match their moments."""
    a = cea.psa_normal(mean_delta_cost=200.0, sd_delta_cost=50.0, mean_delta_effect=0.5,
                       sd_delta_effect=0.1, correlation=0.0, n=20_000, seed=3)
    b = cea.psa_normal(mean_delta_cost=200.0, sd_delta_cost=50.0, mean_delta_effect=0.5,
                       sd_delta_effect=0.1, correlation=0.0, n=20_000, seed=3)
    np.testing.assert_array_equal(a[0], b[0])
    assert a[0].mean() == pytest.approx(200.0, abs=2.0)
    assert a[1].std() == pytest.approx(0.1, abs=0.005)


def test_psa_correlation_is_induced() -> None:
    """Psa correlation is induced."""
    dc, de = cea.psa_normal(100.0, 10.0, 1.0, 0.2, correlation=0.8, n=20_000, seed=0)
    assert np.corrcoef(dc, de)[0, 1] == pytest.approx(0.8, abs=0.02)


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: cea.efficient_frontier(["A"], [1.0, 2.0], [1.0]), "same length"),
        (lambda: cea.efficient_frontier([], [], []), "at least one"),
        (lambda: cea.ceac([1.0], [1.0, 2.0], [1.0]), "same length"),
        (lambda: cea.ceac([1.0], [1.0], []), "threshold"),
        (lambda: cea.psa_normal(1, 1, 1, 1, correlation=1.5, n=5, seed=0), "correlation"),
        (lambda: cea.psa_normal(1, -1, 1, 1, correlation=0, n=5, seed=0), "non-negative"),
        (lambda: cea.psa_normal(1, 1, 1, 1, correlation=0, n=0, seed=0), "n must"),
        (lambda: cea.icer(float("nan"), 1.0, 1.0, 1.0), "finite"),
    ],
)
def test_invalid_inputs_raise(call, message: str) -> None:
    """Invalid inputs raise."""
    with pytest.raises(ValueError, match=message):
        call()


@settings(max_examples=40, deadline=None)
@given(
    dc=st.floats(1, 1e4, allow_nan=False),
    de=st.floats(0.01, 100, allow_nan=False),
    k=st.floats(0.1, 100, allow_nan=False),
)
def test_property_icer_is_scale_equivariant_in_cost_and_threshold_consistent(
    dc: float, de: float, k: float
) -> None:
    """Property icer is scale equivariant in cost and threshold consistent."""
    r = cea.icer(cost=dc, effect=de, ref_cost=0.0, ref_effect=0.0)
    scaled = cea.icer(cost=dc * k, effect=de, ref_cost=0.0, ref_effect=0.0)
    assert scaled.ratio == pytest.approx(r.ratio * k, rel=1e-9)
    # at a threshold equal to the ICER the net monetary benefit is zero
    nmb = cea.net_monetary_benefit(np.array([dc]), np.array([de]), threshold=r.ratio)
    assert nmb[0] == pytest.approx(0.0, abs=1e-6 * max(dc, 1.0))


def test_remaining_guards() -> None:
    """Non-finite frontier inputs and mismatched net-benefit arrays raise."""
    with pytest.raises(ValueError, match="finite"):
        cea.efficient_frontier(["A", "B"], [1.0, np.nan], [1.0, 2.0])
    with pytest.raises(ValueError, match="same length"):
        cea.net_monetary_benefit([1.0], [1.0, 2.0], threshold=1.0)
