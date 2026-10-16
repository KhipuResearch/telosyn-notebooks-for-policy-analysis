"""Discounting: present value of a stream, annuity factors, rate sensitivity.

No discount rate lives in this module. A rate is an argument, and a notebook
that uses a published one (an OMB Circular A-4 rate, for instance) pins it from
the publication with provenance and passes it in. Embedding a rate here would
make it a code constant that drifts from its source.

Convention
    ``timing="end"`` (default) places the first flow one period from now, so its
    factor is ``1/(1+r)``; ``timing="start"`` places it now (factor 1), which is
    an annuity-due. Rates are per period and must exceed -1.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

from typing import Literal, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

Float = NDArray[np.float64]
Timing = Literal["end", "start"]


def _rate(rate: float) -> float:
    if not np.isfinite(rate) or rate <= -1.0:
        raise ValueError(f"rate must be finite and greater than -1, not {rate!r}")
    return float(rate)


def _timing_offset(timing: str) -> int:
    if timing == "end":
        return 1
    if timing == "start":
        return 0
    raise ValueError(f"timing must be 'end' or 'start', not {timing!r}")


def discount_factors(rate: float, periods: int, *, timing: Timing = "end") -> Float:
    """``1/(1+rate)^t`` for each of ``periods`` flows."""
    r = _rate(rate)
    if periods < 1:
        raise ValueError("periods must be at least 1")
    t = np.arange(periods) + _timing_offset(timing)
    return (1.0 + r) ** (-t.astype(float))


def present_value(cashflows: ArrayLike, rate: float, *, timing: Timing = "end") -> float:
    """Present value of a stream of flows at a constant per-period rate."""
    flows = np.asarray(cashflows, dtype=float)
    if flows.ndim != 1 or flows.size == 0:
        raise ValueError("cashflows must be a one-dimensional sequence with at least one flow")
    if not np.all(np.isfinite(flows)):
        raise ValueError("cashflows must be finite")
    return float(flows @ discount_factors(rate, flows.size, timing=timing))


def annuity_factor(rate: float, n: int, *, timing: Timing = "end") -> float:
    """Present value of 1 a period for ``n`` periods, in closed form."""
    r = _rate(rate)
    if n < 1:
        raise ValueError("n must be at least 1")
    base = float(n) if r == 0.0 else (1.0 - (1.0 + r) ** (-n)) / r
    return base * (1.0 + r) if _timing_offset(timing) == 0 else base


def net_present_value(
    benefits: ArrayLike, costs: ArrayLike, rate: float, *, timing: Timing = "end"
) -> float:
    """Present value of benefits minus present value of costs."""
    b = np.asarray(benefits, dtype=float)
    c = np.asarray(costs, dtype=float)
    if b.shape != c.shape:
        raise ValueError("benefits and costs must have the same length")
    return present_value(b, rate, timing=timing) - present_value(c, rate, timing=timing)


def rate_sensitivity(
    cashflows: ArrayLike, rates: Sequence[float], *, timing: Timing = "end"
) -> list[tuple[float, float]]:
    """``(rate, present value)`` for each rate, in the order given."""
    if len(rates) == 0:
        raise ValueError("at least one rate is required")
    return [(float(r), present_value(cashflows, r, timing=timing)) for r in rates]
