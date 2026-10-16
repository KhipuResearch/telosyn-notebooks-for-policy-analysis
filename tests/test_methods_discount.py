"""Known-answer tests for ``krl_tutorials_data.methods.discount``.

No discount rate is hardcoded in the module; every test passes the rate it uses.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from krl_tutorials_data.methods import discount


def test_level_annuity_matches_the_closed_form() -> None:
    """100 a period for 10 periods at 3%, paid at period ends."""
    r, n, payment = 0.03, 10, 100.0
    closed = payment * (1.0 - (1.0 + r) ** -n) / r
    by_sum = sum(payment / (1.0 + r) ** t for t in range(1, n + 1))
    pv = discount.present_value([payment] * n, r)
    assert pv == pytest.approx(closed, rel=1e-12)
    assert pv == pytest.approx(by_sum, rel=1e-12)
    assert discount.annuity_factor(r, n) * payment == pytest.approx(closed, rel=1e-12)


def test_annuity_due_is_the_ordinary_annuity_grown_one_period() -> None:
    """Annuity due is the ordinary annuity grown one period."""
    r, n = 0.05, 8
    ordinary = discount.present_value([1.0] * n, r, timing="end")
    due = discount.present_value([1.0] * n, r, timing="start")
    assert due == pytest.approx(ordinary * (1 + r), rel=1e-12)
    assert discount.annuity_factor(r, n, timing="start") == pytest.approx(due, rel=1e-12)


def test_zero_rate_is_the_undiscounted_sum() -> None:
    """Zero rate is the undiscounted sum."""
    assert discount.present_value([5.0, 5.0, 5.0], 0.0) == pytest.approx(15.0)
    assert discount.annuity_factor(0.0, 7) == 7.0


def test_discount_factors_by_hand() -> None:
    """Discount factors by hand."""
    np.testing.assert_allclose(discount.discount_factors(0.10, 3), [1 / 1.1, 1 / 1.21, 1 / 1.331])
    np.testing.assert_allclose(
        discount.discount_factors(0.10, 3, timing="start"), [1.0, 1 / 1.1, 1 / 1.21]
    )


def test_net_present_value_subtracts_discounted_costs() -> None:
    """Net present value subtracts discounted costs."""
    npv = discount.net_present_value(benefits=[0, 110, 121], costs=[100, 0, 0], rate=0.10,
                                     timing="start")
    assert npv == pytest.approx(-100 + 110 / 1.1 + 121 / 1.21, abs=1e-12)
    assert npv == pytest.approx(100.0, abs=1e-9)


def test_rate_sensitivity_is_monotone_for_positive_flows() -> None:
    """Rate sensitivity is monotone for positive flows."""
    table = discount.rate_sensitivity([10.0] * 20, rates=[0.0, 0.01, 0.03, 0.07])
    assert [r for r, _ in table] == [0.0, 0.01, 0.03, 0.07]
    values = [v for _, v in table]
    assert values == sorted(values, reverse=True)
    assert values[0] == pytest.approx(200.0)


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: discount.present_value([1.0], -1.0), "greater than -1"),
        (lambda: discount.present_value([], 0.03), "at least one"),
        (lambda: discount.present_value([1.0, np.nan], 0.03), "finite"),
        (lambda: discount.present_value([1.0], 0.03, timing="mid"), "timing"),
        (lambda: discount.annuity_factor(0.03, 0), "n must"),
        (lambda: discount.net_present_value([1.0], [1.0, 2.0], 0.03), "same length"),
        (lambda: discount.rate_sensitivity([1.0], rates=[]), "rate"),
    ],
)
def test_invalid_inputs_raise(call, message: str) -> None:
    """Invalid inputs raise."""
    with pytest.raises(ValueError, match=message):
        call()


@settings(max_examples=50, deadline=None)
@given(
    flows=st.lists(st.floats(-1e4, 1e4, allow_nan=False), min_size=1, max_size=20),
    rate=st.floats(0.0, 0.5),
)
def test_property_linearity_and_start_end_relation(flows: list[float], rate: float) -> None:
    """Property linearity and start end relation."""
    f = np.array(flows)
    end = discount.present_value(f, rate)
    assert discount.present_value(2.0 * f, rate) == pytest.approx(2.0 * end, abs=1e-6)
    assert discount.present_value(f, rate, timing="start") == pytest.approx(
        end * (1.0 + rate), abs=1e-6 * (1 + abs(end))
    )


def test_zero_periods_is_refused() -> None:
    """A stream with no periods has no factors."""
    with pytest.raises(ValueError, match="periods must"):
        discount.discount_factors(0.03, 0)
