"""Parse tests on text extracted from the real FNS PDFs (fixtures saved from the retrieved files).

The expected values are read off the printed tables in the PDFs themselves: the fixtures hold the table pages'
extracted text (``reaching_table_pages.json``) and the 14th edition's profile pages (``options14_pages.json``).

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from krl_tutorials_data import pdf_tables

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / "fixtures" / "fns"
STATES = [r["state"] for r in csv.DictReader(open(ROOT / "data/policy/medicaid/expansion_dates.csv"))]
TABLES = json.loads((FIX / "reaching_table_pages.json").read_text())
OPTIONS = json.loads((FIX / "options14_pages.json").read_text())


def _parse(key: str) -> tuple[dict[str, tuple[float, ...]], list]:
    fixed, joins = pdf_tables.repair_split_names(TABLES[key]["text"].splitlines(), STATES)
    table = pdf_tables.parse_jurisdiction_rows(fixed, STATES)
    return {r.name: r.values for r in table.rows}, joins


@pytest.mark.parametrize("key", ["reaching2016", "reaching2017", "reaching2018", "reaching2019", "reaching2022"])
def test_every_year_yields_all_51_jurisdictions_once(key: str) -> None:
    rows, _ = _parse(key)
    assert sorted(rows) == sorted(STATES) and len(rows) == 51


@pytest.mark.parametrize(
    ("key", "name", "values"),
    [
        ("reaching2018", "Louisiana", (82, 86, 83, 74, 74, 73)),
        ("reaching2018", "Oregon", (100, 100, 100, 91, 96, 88)),
        ("reaching2018", "Alabama", (82, 80, 79, 78, 80, 77)),
        ("reaching2019", "Louisiana", (86, 84, 85, 75, 73, 77)),
        ("reaching2019", "Oregon", (100, 100, 100, 97, 90, 89)),
        ("reaching2019", "Alabama", (80, 78, 80, 79, 77, 75)),
        ("reaching2016", "Louisiana", (74, 78, 84, 62, 70, 76)),
        ("reaching2022", "Louisiana", (87, 99)),
    ],
)
def test_values_read_off_the_printed_tables(key: str, name: str, values: tuple[float, ...]) -> None:
    rows, _ = _parse(key)
    assert rows[name] == tuple(float(v) for v in values)


def test_the_name_joins_are_the_ones_recorded() -> None:
    assert [j[1:] for j in _parse("reaching2019")[1]] == [("L", "ouisiana 86 84 85 75 73 77"), ("Or", "egon 100 100 100 97 90 89")]
    assert [j[1] for j in _parse("reaching2018")[1]] == ["L", "O"]


def test_oklahoma_fy2018_split_number_is_merged_to_76() -> None:
    fixed, _ = pdf_tables.repair_split_names(TABLES["reaching2018"]["text"].splitlines(), STATES)
    row = next(r for r in pdf_tables.parse_jurisdiction_rows(fixed, STATES).rows if r.name == "Oklahoma")
    assert len(row.values) == 7
    assert pdf_tables.reconcile_row(row, expected=6, max_value=100.0) == (80.0, 83.0, 85.0, 71.0, 76.0, 78.0)


def test_options_14th_edition_profiles() -> None:
    pages = [OPTIONS["pages"].get(str(i), "") for i in range(93)]
    labels = {"online": r"Online\s+Application", "length": r"Certification\s+Length"}
    profiles, assigned = pdf_tables.parse_profiles_with_contents(pages, STATES, labels, {"DC": "District of Columbia"})
    got = {p.name: p.fields for p in profiles}
    assert len(got) == 51
    assert got["Louisiana"] == {"online": "Apply & recertify", "length": "12 & 24 months"}
    assert got["Oregon"]["length"] == "4, 6, 12, & 24 months"
    assert got["Oklahoma"]["length"] == "12 & 24 months"
    assert got["Virginia"]["length"] == "5, 6, 12, & 24 months"
    assert [(a.name, a.page, a.footer, a.contents) for a in assigned] == [("Virginia", 87, 82, 82)]


def test_options_14th_summary_lists_on_the_real_pages() -> None:
    online = pdf_tables.parse_summary_groups(OPTIONS["pages"]["35"])
    assert [(h, n, len(names)) for h, n, names in online] == [
        ("No online application", 7, 7), ("Apply only", 13, 13), ("Apply & recertify", 33, 33)]
    assert online[0][2] == ["Alaska", "DC", "Georgia", "Guam", "Hawaii", "Virgin Islands", "Wyoming"]
    length = pdf_tables.parse_summary_groups(OPTIONS["pages"]["16"])
    assert [(h, n, len(names)) for h, n, names in length] == [
        ("6 Months only", 4, 4), ("6 & 12 Months", 6, 6), ("12 Months only", 13, 13),
        ("12 & 24 Months", 16, 16), ("Various combinations", 13, 13), ("Change reporting only", 1, 1)]
