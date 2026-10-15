"""The corpus's only synthetic data generator, and the reason it exists.

Every other module in this package retrieves real data and fails closed rather
than substitute a value. This one does the opposite on purpose, and it is
confined to a single job: **giving D30 a dataset whose truth is known by
construction**, so that a published analysis of it can be scored rather than
believed.

The generator is not invented here. It is a faithful re-implementation of the
data-generating process embedded in the archived D30 notebook
(``notebooks/09_planned/D30_subjective_wellbeing/``), which drew seven
independent normal variates, built a target from three of them, assigned a
region at random, and then reported regression coefficients, random-forest
feature importances, cluster profiles and a regional ranking as findings about
subjective well-being.

Restating that process as a declared object with named true coefficients is what
turns the archived artifact from an embarrassment into a teaching instrument. A
reader can ask, of every number that notebook published, whether it was true --
and here, uniquely in this corpus, the question has an exact answer.

**This module may only be imported by an artifact declaring**
``krl.data_mode = "illustrative"``. ``tests/test_gate_no_synthetic.py`` enforces
that at the notebook level; ``tests/test_simulation.py`` enforces that this
module never leaks into the fetcher path.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Final

import numpy as np
import pandas as pd

__all__ = [
    "WELLBEING_TRUTH",
    "WELLBEING_NULL_PREDICTORS",
    "WELLBEING_PREDICTORS",
    "SimulationSpec",
    "WellbeingTruth",
    "simulate_wellbeing",
]


@dataclass(frozen=True)
class WellbeingTruth:
    """The exact coefficients the generator uses. Not estimates -- definitions.

    Units matter and are the source of the archived notebook's most quotable
    defect. ``income_per_dollar`` is 2e-05: a real, precisely-known effect that
    prints as ``0.0000`` under the four-decimal format the archive used, so the
    one coefficient it estimated with the right sign and a vanishing p-value was
    displayed as nothing at all.
    """

    #: life-satisfaction points per dollar of median income. 0.2 per $10,000.
    income_per_dollar: float = 0.2 / 10_000
    #: life-satisfaction points per percentage point of health coverage. 0.2 per 10 pp.
    coverage_per_point: float = 0.2 / 10
    #: unemployment rate enters the target not at all.
    unemployment: float = 0.0
    #: bachelor's-degree share enters the target not at all.
    education: float = 0.0
    #: poor-mental-health days enter the target not at all.
    mental_health_days: float = 0.0
    #: region enters the target not at all; it is an independent categorical draw.
    region: float = 0.0
    #: happiness is a noisy echo of life satisfaction, at this coefficient.
    happiness_on_satisfaction: float = 0.8
    #: the residual standard deviation carried into life satisfaction.
    satisfaction_residual_sd: float = 0.6 * 0.8

    def as_dict(self) -> dict[str, float]:
        return {
            "median_income": self.income_per_dollar,
            "health_coverage_pct": self.coverage_per_point,
            "unemployment_rate": self.unemployment,
            "education_bachelors_pct": self.education,
        }


WELLBEING_TRUTH: Final[WellbeingTruth] = WellbeingTruth()

#: The predictors the archived notebook regressed life satisfaction on.
WELLBEING_PREDICTORS: Final[tuple[str, ...]] = (
    "median_income",
    "unemployment_rate",
    "health_coverage_pct",
    "education_bachelors_pct",
)

#: Of those, the ones with a true coefficient of exactly zero. Any p < 0.05 on
#: one of these is a false positive, with certainty rather than with suspicion.
WELLBEING_NULL_PREDICTORS: Final[tuple[str, ...]] = (
    "unemployment_rate",
    "education_bachelors_pct",
)

_REGIONS: Final[tuple[str, ...]] = ("Northeast", "South", "Midwest", "West")


@dataclass(frozen=True)
class SimulationSpec:
    """What produced a frame, recorded in the same spirit as ``DataProvenance``.

    A simulated frame carries a spec rather than a provenance record, and the two
    are deliberately different types so that no code path can mistake one for the
    other. A spec has no endpoint, no vintage and no publisher, because there is
    nothing upstream of it.
    """

    generator: str
    seed: int
    n: int
    signal: float
    truth: dict[str, float]
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def digest(self) -> str:
        """A stable hash of the spec, so a notebook can pin what it simulated."""
        payload = json.dumps(
            {
                "generator": self.generator,
                "seed": self.seed,
                "n": self.n,
                "signal": self.signal,
                "truth": self.truth,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def __str__(self) -> str:
        return (
            f"SIMULATED -- {self.generator}, seed={self.seed}, n={self.n}, "
            f"signal={self.signal:g}, spec {self.digest[:12]}"
        )


def simulate_wellbeing(
    *,
    seed: int,
    n: int = 50,
    signal: float = 1.0,
    truth: WellbeingTruth = WELLBEING_TRUTH,
) -> tuple[pd.DataFrame, SimulationSpec]:
    """Generate one well-being dataset with known coefficients.

    Parameters
    ----------
    seed
        Required. There is no default, because a default seed is how a
        simulation quietly becomes a single dataset that everyone cites.
    n
        Number of units. The archived notebook used 50 -- one per state -- and
        that number is the origin of most of what D30 demonstrates.
    signal
        Multiplier on the **true** coefficients only. ``1.0`` reproduces the
        archived process exactly. ``0.0`` severs every real effect, leaving the
        predictors independent of the target, so that any finding recovered from
        the result is a false one by construction.
    truth
        The coefficient set. Overridable so a reader can vary effect size, but
        the default is the archived process and the tests pin it.

    Returns
    -------
    A frame and a :class:`SimulationSpec`. The spec is not a
    ``DataProvenance``; nothing here was retrieved from anywhere.

    Notes
    -----
    The clipping is reproduced from the archive rather than cleaned up. It is
    mild at these parameters but it is not nothing -- it makes the true
    relationship slightly non-linear at the boundaries, which is one more reason
    an estimated coefficient will not land exactly on the declared one even in a
    very large sample.
    """
    if n < 3:
        raise ValueError(f"n must be at least 3 to fit anything; got {n}.")
    if signal < 0:
        raise ValueError(f"signal must be non-negative; got {signal}.")

    # RandomState, not default_rng, and in this draw order on purpose. The point
    # of this generator is that `seed=42, signal=1.0` reproduces the archived
    # notebook's published numbers exactly, so that its claims can be scored
    # rather than paraphrased. A modern bit generator would be better practice
    # and would make that impossible.
    rng = np.random.RandomState(seed)
    satisfaction_residual = rng.normal(7.2, 0.8, n).clip(1, 10)
    mental_health_days = rng.normal(3.5, 1.2, n).clip(0, 30)
    # The archive drew happiness here and then overwrote it two statements later.
    # The draw is discarded and deliberately kept: removing it advances the
    # stream and changes every number after it, including the ones being scored.
    _discarded_happiness_draw = rng.normal(6.8, 0.7, n)
    frame = pd.DataFrame(
        {
            "unit": [f"Unit_{i + 1}" for i in range(n)],
            "poor_mental_health_days": mental_health_days,
            "median_income": rng.normal(65_000, 15_000, n),
            "unemployment_rate": rng.normal(4.5, 1.5, n).clip(0, 15),
            "health_coverage_pct": rng.normal(92, 5, n).clip(70, 100),
            "education_bachelors_pct": rng.normal(32, 8, n).clip(15, 60),
        }
    )
    frame["_satisfaction_residual"] = satisfaction_residual

    frame["life_satisfaction"] = (
        0.6 * frame["_satisfaction_residual"]
        + signal * truth.income_per_dollar * frame["median_income"]
        + signal * truth.coverage_per_point * frame["health_coverage_pct"]
    ).clip(1, 10)

    frame["happiness_score"] = (
        truth.happiness_on_satisfaction * frame["life_satisfaction"]
        + rng.normal(0, 0.5, n)
    ).clip(1, 10)

    frame["region"] = rng.choice(list(_REGIONS), n)
    frame = frame.drop(columns="_satisfaction_residual")

    effective = {k: signal * v for k, v in truth.as_dict().items()}
    notes = (
        "SIMULATED. Nothing here was measured. This frame exists so that a "
        "published analysis of it can be scored against a truth that is known "
        "rather than estimated.",
        "True coefficients on life_satisfaction: "
        + ", ".join(f"{k}={v:g}" for k, v in effective.items())
        + f". The two at exactly zero are {', '.join(WELLBEING_NULL_PREDICTORS)}.",
        "region is an independent categorical draw and enters no outcome. Any "
        "regional difference recovered from this frame is an artifact.",
        "poor_mental_health_days is an independent draw and enters no outcome.",
        f"happiness_score = {truth.happiness_on_satisfaction:g} * life_satisfaction "
        "+ N(0, 0.5), so it carries no information the target does not already have.",
        "Values are clipped as in the archived process, which makes the true "
        "relationship slightly non-linear near the boundaries.",
    )
    spec = SimulationSpec(
        generator="archived D30 well-being process",
        seed=int(seed),
        n=int(n),
        signal=float(signal),
        truth=effective,
        notes=notes,
    )
    return frame, spec
