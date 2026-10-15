"""Measure how margins and rank identifiability degrade as geography shrinks.

§7 of the Data Source Handbook said county rankings "deserve far more scepticism
than state ones" and that tract margins are wider "by an unmeasured factor",
with §12 adding that §7's results at tract level "should be assumed worse, not
similar". Those are assumptions sitting inside the corpus's own guidance, which
is the thing this corpus exists to replace with numbers.

This script measures them on one quantity, at three levels, and prints the table
§7 quotes. It is a script rather than a notebook because it answers one question
and produces one table; the figures in the handbook cite this file, so they are
reproducible even though no notebook carries them.

    KRL_SECRETS_PATH=... python scripts/measure_geography_escalation.py

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from krl_tutorials_data.reliability import Estimate, rank_intervals
from krl_tutorials_data.sources import fetch_acs_wide

YEAR = 2023

#: Virginia is the geography D09, D15 and the CHAS notebook use, so its county row
#: is comparable with those. The others are chosen to vary the two things that
#: could explain the tract result away: how many tracts a state has, and how big
#: they are. Wyoming has the fewest; California the most; New Jersey has small
#: dense ones; Mississippi is rural with a low share, so a ceiling effect at high
#: shares cannot be doing the work.
STATES = {
    "51": "Virginia",
    "06": "California",
    "34": "New Jersey",
    "28": "Mississippi",
    "56": "Wyoming",
}
STATE = "51"

#: Broadband of any type as a share of households: the quantity D16 measured at
#: county level, so the county row here is comparable with that notebook.
VARIABLES = {
    "B28002_001E": "households",
    "B28002_001M": "households_moe",
    "B28002_004E": "broadband",
    "B28002_004M": "broadband_moe",
}

LEVELS = (
    ("state", "state:*", None),
    (f"county (FIPS {STATE})", "county:*", f"state:{STATE}"),
    (f"tract (FIPS {STATE})", "tract:*", f"state:{STATE}"),
)

#: A rank interval this wide means the ordering carries essentially no
#: information; used only to phrase the replication result, not to define it.
NO_INFORMATION_SHARE = 0.5


def shares(geography: str, within: str | None) -> pd.DataFrame:
    """Broadband share and its margin, by the ACS proportion formula.

    Where the radicand goes negative -- which happens when the numerator's margin
    is small relative to the denominator's -- the Bureau's instruction is to fall
    back to the ratio formula rather than to clip. Clipping would report a
    margin of zero for the units with the least information, which is backwards.
    """
    frame, _ = fetch_acs_wide(
        year=YEAR, variables=VARIABLES, geography=geography, within=within
    )
    frame = frame[frame["B28002_001E"] > 0].copy()
    proportion = frame["B28002_004E"] / frame["B28002_001E"]
    radicand = frame["B28002_004M"] ** 2 - (proportion**2) * (frame["B28002_001M"] ** 2)
    margin = np.where(
        radicand >= 0,
        np.sqrt(radicand.clip(lower=0)),
        np.sqrt(frame["B28002_004M"] ** 2 + (proportion**2) * (frame["B28002_001M"] ** 2)),
    )
    out = pd.DataFrame(
        {"estimate": 100 * proportion, "margin": 100 * margin / frame["B28002_001E"]}
    ).dropna()
    return out[out["margin"] > 0].reset_index(drop=True)


def summarise(data: pd.DataFrame) -> dict[str, float | int]:
    """Rank-identifiability summary for one set of estimates with margins."""
    intervals = rank_intervals(
        {str(i): Estimate(value=row.estimate, moe=row.margin) for i, row in data.iterrows()}
    )
    widths = np.array([interval.width for interval in intervals])
    units = len(data)
    return {
        "units": units,
        "median margin (pp)": round(data["margin"].median(), 2),
        "median rank interval": int(np.median(widths)),
        "as % of units": round(100 * float(np.median(widths)) / units, 1),
        "determined ranks": int(sum(i.is_determined for i in intervals)),
        "could be rank 1": int(sum(i.best == 1 for i in intervals)),
    }


def replicate_at_tract_level() -> pd.DataFrame:
    """Does the tract result hold outside Virginia, or is it a property of Virginia?"""
    rows = []
    for fips, name in STATES.items():
        data = shares("tract:*", f"state:{fips}")
        summary = summarise(data)
        summary["state"] = name
        summary["median share (%)"] = round(data["estimate"].median(), 1)
        summary["% could be rank 1"] = round(
            100 * summary["could be rank 1"] / summary["units"], 1
        )
        rows.append(summary)
    columns = [
        "state", "units", "median share (%)", "median margin (pp)",
        "as % of units", "determined ranks", "could be rank 1", "% could be rank 1",
    ]
    return pd.DataFrame(rows)[columns]


def main() -> None:
    rows = []
    for label, geography, within in LEVELS:
        summary = summarise(shares(geography, within))
        rows.append({"level": label, **summary})

    table = pd.DataFrame(rows)
    print(table.to_string(index=False))
    margins = table["median margin (pp)"]
    print(
        f"\nmargin escalation: state->county {margins[1] / margins[0]:.1f}x, "
        f"county->tract {margins[2] / margins[1]:.1f}x, "
        f"state->tract {margins[2] / margins[0]:.1f}x"
    )
    top = table["could be rank 1"].iloc[-1]
    print(
        f"\nAt tract level {top} of {table['units'].iloc[-1]} units "
        f"({100 * top / table['units'].iloc[-1]:.0f}%) could occupy rank 1. A ranking in "
        f"which two fifths of the units could be first is not a ranking."
    )

    print("\n" + "=" * 78)
    print("Does that hold outside Virginia?")
    print("=" * 78)
    replication = replicate_at_tract_level()
    print(replication.to_string(index=False))
    worst = replication["% could be rank 1"].max()
    best = replication["% could be rank 1"].min()
    print(
        f"\n  'could be rank 1' ranges from {best}% to {worst}% of tracts across "
        f"{len(replication)} states"
        f"\n  spanning {replication['units'].min():,} to {replication['units'].max():,} tracts and "
        f"median shares of {replication['median share (%)'].min()}% to "
        f"{replication['median share (%)'].max()}%."
    )
    print(
        f"  states with any determined tract rank: "
        f"{int((replication['determined ranks'] > 0).sum())} of {len(replication)}"
    )


if __name__ == "__main__":
    main()
