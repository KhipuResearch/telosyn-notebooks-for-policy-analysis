"""Integrity of E02's committed EPA tables: complete, internally consistent, and the digests SOURCES.md records.

The source PDF is not committed and not needed here; the checks are on the extracted CSV.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd
import pytest

DATA = Path(__file__).resolve().parents[1] / "projects" / "10-economic-evaluation" / "E02_cost_benefit_reanalysis" / "data"


def _streams() -> pd.DataFrame:
    return pd.read_csv(DATA / "epa_lcri_yearly_streams.csv")


@pytest.mark.parametrize("name", ["epa_lcri_yearly_streams.csv", "epa_lcri_printed_annualized_2pct.csv"])
def test_each_table_has_the_digest_sources_md_records(name: str) -> None:
    recorded = re.search(re.escape(name) + r"`\s*\|\s*`([0-9a-f]{64})`", (DATA / "SOURCES.md").read_text(encoding="utf-8"))
    assert recorded, f"SOURCES.md records no digest for {name}"
    assert hashlib.sha256((DATA / name).read_bytes()).hexdigest() == recorded.group(1)


def test_both_scenarios_have_every_year_2024_to_2058_once() -> None:
    d = _streams()
    for scenario in ("low", "high"):
        assert sorted(d.loc[d["scenario"] == scenario, "year"]) == list(range(2024, 2059))


def test_net_benefits_are_benefits_minus_costs_within_rounding() -> None:
    d = _streams()
    assert ((d["incremental_benefits_musd"] - d["incremental_costs_musd"]) - d["net_benefits_musd"]).abs().max() <= 0.1001


def test_undiscounted_net_totals_match_the_text_epa_prints() -> None:
    d = _streams()
    totals = d.groupby("scenario")["net_benefits_musd"].sum() / 1000.0
    assert round(totals["low"]) == 479 and round(totals["high"]) == 918


def test_every_row_names_its_exhibit_and_pdf_page() -> None:
    d = _streams()
    assert set(d["source_exhibit"]) == {"Exhibit 6-4", "Exhibit 6-5"} and d["pdf_page"].between(709, 711).all()
    p = pd.read_csv(DATA / "epa_lcri_printed_annualized_2pct.csv")
    assert len(p) == 6 and set(p["source_exhibit"]) == {"Exhibit 6-6"} and (p["discount_rate"] == 0.02).all()
    for scenario in ("low", "high"):
        v = p[p["scenario"] == scenario].set_index("quantity")["value_musd"]
        assert abs(v["annualized_incremental_benefits"] - v["annualized_incremental_costs"] - v["annual_net_benefits"]) <= 0.11
