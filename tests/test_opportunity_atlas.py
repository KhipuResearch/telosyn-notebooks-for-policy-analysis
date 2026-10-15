"""The Opportunity Atlas fetcher's contract.

This source's traps are not about parsing. They are about what the number means
and how it joins:

- `state` and `county` ship UNPADDED, so Accomack County is `state=51,
  county=1`. Concatenating them without zero-padding produces `511`, which
  matches no Census FIPS and fails by returning an empty join rather than an
  error.
- The three geographies are not resolutions of one thing. Suppression at tract
  level removes cells with fewer than 20 children; at county level the same
  threshold applies per race and gender. Defaulting silently between them would
  change what is measurable.
- The vintage is a COHORT, not a year, and the provenance has to say so.

No network: these drive the argument contract and the FIPS construction.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import pandas as pd
import pytest

from krl_tutorials_data import sources
from krl_tutorials_data.sources import (
    OPPORTUNITY_ATLAS_COHORT,
    OPPORTUNITY_ATLAS_FILES,
)


def test_geography_must_be_named_and_known() -> None:
    with pytest.raises(ValueError, match="geography must be one of"):
        sources.fetch_opportunity_atlas(geography="zip")
    with pytest.raises(ValueError, match="geography must be one of"):
        sources.fetch_opportunity_atlas(geography="")


def test_every_geography_maps_to_a_distinct_file() -> None:
    """A duplicated path would serve county data under a tract label."""
    paths = list(OPPORTUNITY_ATLAS_FILES.values())
    assert len(paths) == len(set(paths)), OPPORTUNITY_ATLAS_FILES


def test_the_vintage_is_a_cohort_not_a_year() -> None:
    """Recording '2018' as the vintage would be the central misreading of this
    source: the release year is not the period the data describes."""
    assert "1978" in OPPORTUNITY_ATLAS_COHORT
    assert "1983" in OPPORTUNITY_ATLAS_COHORT
    assert not OPPORTUNITY_ATLAS_COHORT.strip().isdigit()


def test_fips_construction_zero_pads_both_parts() -> None:
    """The join trap, pinned.

    Unpadded concatenation of state=51, county=1 gives '511' -- which is a valid
    FIPS *prefix* for a different state's county, so the failure is a silent
    mismatch rather than an obvious one.
    """
    frame = pd.DataFrame({"state": [51, 51, 6], "county": [1, 830, 37]})
    built = (
        frame["state"].astype("Int64").astype(str).str.zfill(2)
        + frame["county"].astype("Int64").astype(str).str.zfill(3)
    )
    assert built.tolist() == ["51001", "51830", "06037"]
    naive = frame["state"].astype(str) + frame["county"].astype(str)
    assert naive.tolist() == ["511", "51830", "637"]
    assert naive.tolist() != built.tolist(), "the padding must actually change something"


def test_the_atlas_needs_no_credential() -> None:
    """These are public bulk files. A notebook using only this source must not
    demand a key it never needs."""
    assert "OPPORTUNITY_API_KEY" not in sources.ALLOWED_KEYS
    assert "OI_API_KEY" not in sources.ALLOWED_KEYS


def test_files_are_not_committed_to_the_repository() -> None:
    """The corpus has no verified redistribution licence for these files, so they
    are fetched at runtime. If someone later commits one, this fails and the
    licence question gets asked before the file ships."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    stray = [
        p.relative_to(root).as_posix()
        for name in OPPORTUNITY_ATLAS_FILES.values()
        for p in root.rglob(Path(name).name)
    ]
    assert not stray, (
        "Opportunity Atlas bulk files found in the repository: "
        + ", ".join(stray)
        + ". They are fetched at runtime because no redistribution licence has "
        "been verified for them."
    )
