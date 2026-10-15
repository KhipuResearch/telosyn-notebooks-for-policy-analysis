"""Direct age standardisation and exact decomposition of crude-rate differences.

A crude rate is a weighted average of group-specific rates, weighted by the
population's own composition. Two populations can therefore differ in crude rate
while every group-specific rate is identical, or differ in *opposite* directions
from every group-specific rate. Comparing crude rates across populations with
different age structures is the canonical confounding error in demography.

This module supplies two primitives:

``direct_standardized_rate``
    Re-weights group-specific rates by a *shared* standard composition, so the
    comparison isolates rate differences from composition differences.

``kitagawa_decomposition``
    Splits the difference between two crude rates into a rate component and a
    composition component. The split is algebraically exact -- the two
    components sum to the crude difference to floating-point precision -- which
    makes it testable rather than merely plausible.

Weights from the standard population are treated as **fixed constants** when
propagating uncertainty. This is the conventional treatment (the standard
population defines the comparison; it is not being estimated) and it is stated
here because it understates total variance if the standard is itself a sample.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .uncertainty import Z90, Estimate

__all__ = [
    "StandardPopulation",
    "KitagawaSplit",
    "direct_standardized_rate",
    "standardized_rate_estimate",
    "standardized_rate_bounds",
    "kitagawa_decomposition",
    "crude_rate",
]


class StandardizationError(ValueError):
    """Raised when a standardisation input is structurally unusable."""


@dataclass(frozen=True)
class StandardPopulation:
    """A named set of group weights that sum to 1.

    Attributes
    ----------
    name:
        What the standard is, in words, so it appears in output rather than
        living only in the analyst's head. The choice of standard changes the
        numbers and must therefore be disclosed.
    labels:
        Group labels, in the same order as ``weights``.
    weights:
        Non-negative shares summing to 1.
    """

    name: str
    labels: tuple[str, ...]
    weights: np.ndarray

    def __post_init__(self) -> None:
        w = np.asarray(self.weights, dtype=float)
        if w.ndim != 1:
            raise StandardizationError("Standard population weights must be 1-D.")
        if len(w) != len(self.labels):
            raise StandardizationError(
                f"{len(self.labels)} labels but {len(w)} weights."
            )
        if np.any(w < 0):
            raise StandardizationError("Standard population weights must be >= 0.")
        total = float(w.sum())
        if not np.isclose(total, 1.0, atol=1e-9):
            raise StandardizationError(
                f"Standard population weights sum to {total!r}, not 1."
            )

    @classmethod
    def from_counts(
        cls, name: str, labels: Sequence[str], counts: Sequence[float]
    ) -> "StandardPopulation":
        c = np.asarray(counts, dtype=float)
        if np.any(c < 0):
            raise StandardizationError("Standard population counts must be >= 0.")
        total = float(c.sum())
        if total <= 0:
            raise StandardizationError("Standard population has zero total.")
        return cls(name=name, labels=tuple(labels), weights=c / total)


def _check_group_inputs(events: np.ndarray, population: np.ndarray) -> None:
    if events.shape != population.shape:
        raise StandardizationError(
            f"events shape {events.shape} != population shape {population.shape}."
        )
    if np.any(population < 0) or np.any(events < 0):
        raise StandardizationError("Counts must be non-negative.")
    over = events > population
    if np.any(over):
        idx = int(np.argmax(over))
        raise StandardizationError(
            f"Group {idx}: {events[idx]} events exceed {population[idx]} at risk. "
            "This is a universe mismatch, not a rate."
        )


def crude_rate(events: Sequence[float], population: Sequence[float]) -> float:
    """Total events divided by total population at risk."""
    e = np.asarray(events, dtype=float)
    n = np.asarray(population, dtype=float)
    _check_group_inputs(e, n)
    denom = float(n.sum())
    if denom <= 0:
        raise StandardizationError("Total population at risk is zero.")
    return float(e.sum() / denom)


def direct_standardized_rate(
    events: Sequence[float],
    population: Sequence[float],
    standard: StandardPopulation,
    *,
    empty_group_policy: str = "raise",
) -> float:
    """Re-weight group-specific rates by the standard population's composition.

    ``empty_group_policy`` controls the treatment of a group with zero
    population at risk, whose rate is undefined:

    ``"raise"``
        Refuse to produce a number. The default, because silently dropping a
        group changes the effective standard and the result is then not
        comparable with other geographies.
    ``"skip"``
        Drop the group and renormalise the remaining weights, which produces a
        rate standardised to a *different* population. Only defensible when the
        caller reports which groups were dropped.
    """
    e = np.asarray(events, dtype=float)
    n = np.asarray(population, dtype=float)
    _check_group_inputs(e, n)
    w = standard.weights
    if len(w) != len(e):
        raise StandardizationError(
            f"Standard has {len(w)} groups but {len(e)} were supplied."
        )
    empty = n <= 0
    if np.any(empty):
        if empty_group_policy == "raise":
            missing = [standard.labels[i] for i in np.flatnonzero(empty)]
            raise StandardizationError(
                "Zero population at risk in group(s): "
                + ", ".join(missing)
                + ". Their rates are undefined; pass empty_group_policy='skip' "
                "to standardise to the remaining groups instead, and report it."
            )
        if empty_group_policy != "skip":
            raise StandardizationError(
                f"Unknown empty_group_policy {empty_group_policy!r}."
            )
        keep = ~empty
        if not keep.any():
            raise StandardizationError("Every group is empty.")
        w = w[keep] / w[keep].sum()
        e, n = e[keep], n[keep]
    rates = e / n
    return float(np.dot(w, rates))


def standardized_rate_estimate(
    events: Sequence[Estimate],
    population: Sequence[Estimate],
    standard: StandardPopulation,
    *,
    z: float = Z90,
) -> Estimate:
    """Age-standardised rate with a margin of error at the same confidence as inputs.

    Each group rate is a proportion ``p_a = e_a / n_a``. Its standard error is
    taken from the published margins of error via the Census proportion formula
    in :mod:`krl_tutorials_data.uncertainty`; the standardised rate is a fixed
    linear combination of those proportions, so variances add in quadrature with
    squared weights.

    Group rates are treated as independent. They are not: numerator and
    denominator are drawn from the same sample, and the published MOEs already
    reflect that within a group. Across groups the independence assumption is
    the standard one and is stated rather than hidden.
    """
    from .uncertainty import proportion_moe  # local import: avoids cycle at import time

    if len(events) != len(population):
        raise StandardizationError("events and population must be the same length.")
    if len(events) != len(standard.weights):
        raise StandardizationError(
            f"Standard has {len(standard.weights)} groups but "
            f"{len(events)} were supplied."
        )
    e_vals = np.array([x.value for x in events], dtype=float)
    n_vals = np.array([x.value for x in population], dtype=float)
    _check_group_inputs(e_vals, n_vals)
    if np.any(n_vals <= 0):
        raise StandardizationError(
            "Zero population at risk; the standardised MOE is undefined."
        )
    w = standard.weights
    rate = float(np.dot(w, e_vals / n_vals))
    group_moes = np.array(
        [proportion_moe(num, den) for num, den in zip(events, population)],
        dtype=float,
    )
    group_se = group_moes / z
    se = float(np.sqrt(np.sum((w * group_se) ** 2)))
    return Estimate(value=rate, moe=se * z)


@dataclass(frozen=True)
class KitagawaSplit:
    """Exact decomposition of a crude-rate difference.

    ``rate_effect + composition_effect == crude_a - crude_b`` to floating-point
    precision. ``residual`` records the realised deviation so the identity is
    reported rather than asserted.
    """

    crude_a: float
    crude_b: float
    difference: float
    rate_effect: float
    composition_effect: float
    residual: float

    @property
    def composition_share(self) -> float:
        """Fraction of the crude gap attributable to composition.

        Undefined when the crude rates are equal; returns ``nan`` rather than
        dividing by zero. The share can exceed 1 or fall below 0 when the two
        effects have opposite signs, which is the signature of a comparison the
        crude rate reverses.
        """
        if self.difference == 0:
            return float("nan")
        return self.composition_effect / self.difference


def kitagawa_decomposition(
    events_a: Sequence[float],
    population_a: Sequence[float],
    events_b: Sequence[float],
    population_b: Sequence[float],
) -> KitagawaSplit:
    """Split ``crude_a - crude_b`` into rate and composition components.

    Uses the symmetric (average-weight) form, which is exact:

    ``D = sum_g mean(w_ag, w_bg) * (r_ag - r_bg)  +  sum_g mean(r_ag, r_bg) * (w_ag - w_bg)``

    The asymmetric forms -- weighting by A's composition or B's -- are not exact
    and leave an interaction term. That term is where a misleading summary hides,
    so it is eliminated by construction here.
    """
    ea = np.asarray(events_a, dtype=float)
    na = np.asarray(population_a, dtype=float)
    eb = np.asarray(events_b, dtype=float)
    nb = np.asarray(population_b, dtype=float)
    _check_group_inputs(ea, na)
    _check_group_inputs(eb, nb)
    if ea.shape != eb.shape:
        raise StandardizationError("Both populations must use the same groups.")
    if np.any(na <= 0) or np.any(nb <= 0):
        raise StandardizationError(
            "A group with zero population at risk has no rate to decompose."
        )
    ra, rb = ea / na, eb / nb
    wa, wb = na / na.sum(), nb / nb.sum()
    rate_effect = float(np.dot((wa + wb) / 2.0, ra - rb))
    comp_effect = float(np.dot((ra + rb) / 2.0, wa - wb))
    crude_a = float(ea.sum() / na.sum())
    crude_b = float(eb.sum() / nb.sum())
    diff = crude_a - crude_b
    return KitagawaSplit(
        crude_a=crude_a,
        crude_b=crude_b,
        difference=diff,
        rate_effect=rate_effect,
        composition_effect=comp_effect,
        residual=diff - (rate_effect + comp_effect),
    )


def standardized_rate_bounds(
    events: Sequence[Estimate],
    population: Sequence[Estimate],
    standard: StandardPopulation,
    *,
    z: float = Z90,
) -> tuple[Estimate, Estimate]:
    """Bound the standardised rate's margin under the two extreme correlation cases.

    :func:`standardized_rate_estimate` combines group margins in quadrature,
    which assumes the age groups are independent. They are not -- they come from
    the same survey respondents in the same geography. Rather than assert that
    the approximation is adequate, this returns both extremes:

    * **lower bound** -- independence; weighted margins combine in quadrature.
    * **upper bound** -- perfect positive correlation; weighted margins add
      linearly. No real dependence structure is worse than this.

    A comparison that still holds at the upper bound does not rest on the
    independence assumption. One that holds only at the lower bound does, and
    should say so.
    """
    from .uncertainty import proportion_moe

    if len(events) != len(population):
        raise StandardizationError("events and population must be the same length.")
    if len(events) != len(standard.weights):
        raise StandardizationError(
            f"Standard has {len(standard.weights)} groups but {len(events)} were supplied."
        )
    e_vals = np.array([x.value for x in events], dtype=float)
    n_vals = np.array([x.value for x in population], dtype=float)
    _check_group_inputs(e_vals, n_vals)
    if np.any(n_vals <= 0):
        raise StandardizationError(
            "Zero population at risk; the standardised MOE is undefined."
        )
    w = standard.weights
    rate = float(np.dot(w, e_vals / n_vals))
    weighted = np.array(
        [wi * proportion_moe(num, den) for wi, num, den in zip(w, events, population)],
        dtype=float,
    )
    return (
        Estimate(rate, float(np.sqrt(np.sum(weighted ** 2)))),
        Estimate(rate, float(weighted.sum())),
    )
