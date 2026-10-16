"""The state minimum-wage schedule: the parser, the committed files, and their record.

Fixture tables are built in the test (synthetic, labelled as such); the committed
CSV is held to the digests its ``SOURCES.md`` states.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[1]
FOLDER = REPO / "data" / "policy" / "minimum_wage"


def _script() -> ModuleType:
    """Script."""
    spec = importlib.util.spec_from_file_location(
        "build_mw", REPO / "scripts" / "build_minimum_wage_schedule.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = _script()


@pytest.mark.parametrize(
    ("text", "status", "low", "high", "form", "marks"),
    [
        ("7.25", "rate", 7.25, 7.25, "single", ""),
        ("$16.10", "rate", 16.10, 16.10, "single", ""),
        ("6.25[c]", "rate", 6.25, 6.25, "single", "c"),
        ("7.25(e)", "rate", 7.25, 7.25, "single", "e"),
        ("4.30-6.15(g,j)", "rate", 4.30, 6.15, "range", "g,j"),
        ("7.25-8.25", "rate", 7.25, 8.25, "range", ""),
        ("5.08 – 7.25 (i2)", "rate", 5.08, 7.25, "range", "i2"),
        ("9.50/10.50", "rate", 9.50, 10.50, "alternatives", ""),
        ("...", "not_applicable", None, None, "", ""),
    ],
)
def test_every_published_form_parses_to_the_value_read_by_hand(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    text: str, status: str, low: float | None, high: float | None, form: str, marks: str
) -> None:
    """Every published form parses to the value read by hand."""
    got = build.parse_value(text)
    assert (got["status"], got["rate_low"], got["rate_high"], got["rate_form"],
            got["footnote_markers"]) == (status, low, high, form, marks)


@pytest.mark.parametrize(
    "text", ["", "abc", "4..65(g,,j)", "1.25`", "12", "7.25 7.30", "7.25(", "NA"]
)
def test_an_unrecognised_value_raises_rather_than_being_guessed(text: str) -> None:
    """An unrecognised value raises rather than being guessed."""
    with pytest.raises(ValueError, match="unrecognised"):
        build.parse_value(text)


def _tables(years: list[list[int]], names: list[str]) -> list[dict]:
    """Synthetic tables: a federal row then the named jurisdictions, rate = year/1000."""
    out = []
    for ys in years:
        out.append({
            "caption": "c", "header": ["State or other\njurisdiction", *map(str, ys)],
            "rows": [[n, *[f"{y / 1000:.2f}" for y in ys]] for n in names],
        })
    return out


NAMES = ["Federal (FLSA)", "Alpha", "Beta"]


def test_the_long_table_has_one_row_per_jurisdiction_and_year() -> None:
    """The long table has one row per jurisdiction and year."""
    rows = build.build_rows(_tables([[2007, 2008], [2009]], NAMES), first_year=2007)
    assert len(rows) == 3 * 3
    assert rows[0] == {
        "jurisdiction": "Federal (FLSA)", "year": 2007, "rate_as_published": "2.01",
        "status": "rate", "rate_low": 2.01, "rate_high": 2.01,
        "rate_form": "single", "footnote_markers": "",
    }
    assert {r["year"] for r in rows} == {2007, 2008, 2009}


def test_years_before_the_first_year_are_not_in_the_csv_but_are_in_the_raw_table() -> None:
    """Years before the first year are not in the csv but are in the raw table."""
    rows = build.build_rows(_tables([[2005, 2006], [2007]], NAMES), first_year=2007)
    assert {r["year"] for r in rows} == {2007}


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda t: t[1]["rows"].__setitem__(0, ["Other", "1.00"]), "jurisdictions differ"),
        (lambda t: t[1]["header"].__setitem__(1, "2008"), "contiguous"),
        (lambda t: t[0]["header"].__setitem__(0, "State"), "header"),
        (lambda t: t[0]["rows"][1].__setitem__(1, "n/a"), "unrecognised"),
        (lambda t: t[0]["rows"][1].append("9.99"), "cells"),
    ],
)
def test_structural_changes_raise(mutate, message: str) -> None:
    """Structural changes raise."""
    tables = _tables([[2007, 2008], [2009]], NAMES)
    mutate(tables)
    with pytest.raises(ValueError, match=message):
        build.build_rows(tables, first_year=2007)


def test_the_raw_capture_matches_the_digest_the_script_and_sources_md_record() -> None:
    """The raw capture matches the digest the script and sources md record."""
    raw = (FOLDER / "state_schedule.raw.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == build.RAW_SHA256
    text = (FOLDER / "SOURCES.md").read_text(encoding="utf-8")
    assert build.RAW_SHA256 in text
    doc = json.loads(raw)
    assert doc["main_element_html_sha256"] in text, "the rendered-DOM digest must be recorded"


def test_a_raw_file_with_the_wrong_digest_is_refused(tmp_path: Path, monkeypatch, capsys) -> None:
    """A raw file with the wrong digest is refused."""
    fake = tmp_path / "raw.json"
    fake.write_bytes(b"{}")
    monkeypatch.setattr(build, "RAW", fake)
    monkeypatch.setattr(build, "CSV_PATH", tmp_path / "out.csv")
    assert build.main([]) == 2
    assert "not the recorded" in capsys.readouterr().err
    assert not (tmp_path / "out.csv").exists()


def test_the_committed_csv_is_what_the_committed_raw_capture_produces() -> None:
    """The committed csv is what the committed raw capture produces."""
    assert build.main(["--check"]) == 0


def test_the_files_match_the_digests_and_sizes_in_sources_md() -> None:
    """The files match the digests and sizes in sources md."""
    text = (FOLDER / "SOURCES.md").read_text(encoding="utf-8")
    for name in ("state_schedule.raw.json", "state_schedule.csv"):
        data = (FOLDER / name).read_bytes()
        pattern = rf"\|\s*`{re.escape(name)}`\s*\|\s*([\d,]+)\s*\|\s*`([0-9a-f]{{64}})`"
        row = re.search(pattern, text)
        assert row, f"{name} has no row in SOURCES.md"
        assert int(row.group(1).replace(",", "")) == len(data)
        assert row.group(2) == hashlib.sha256(data).hexdigest()


def test_the_committed_table_is_complete_and_the_known_cells_read_as_published() -> None:
    """The committed table is complete and the known cells read as published."""
    rows = list(csv.DictReader((FOLDER / "state_schedule.csv").open(encoding="utf-8")))
    names = {r["jurisdiction"] for r in rows}
    assert len(names) == 55 and "District of Columbia" in names and "Federal (FLSA)" in names
    assert len(rows) == 55 * 18
    assert {int(r["year"]) for r in rows} == set(range(2007, 2025))
    cell = {(r["jurisdiction"], int(r["year"])): r for r in rows}
    # read from the published table, see SOURCES.md: DOL's January-1 figure for California
    assert [cell[("California", y)]["rate_as_published"] for y in (2016, 2017, 2018, 2019)] == [
        "10.00", "10.00", "11.00", "12.00",
    ]
    assert cell[("Alabama", 2015)]["status"] == "not_applicable"
    assert cell[("Nevada", 2022)]["rate_form"] == "alternatives"
    assert cell[("Georgia", 2015)]["footnote_markers"] == "d"
    assert cell[("Georgia", 2015)]["rate_low"] == "5.15"
    nevada = cell[("Nevada", 2022)]
    assert (nevada["rate_low"], nevada["rate_high"]) == ("9.50", "10.50")


def test_raw_to_csv_end_to_end_and_the_staleness_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """A raw capture with the pinned digest is built; a doctored CSV fails --check."""
    doc = {"tables": _tables([[2005, 2006], [2007, 2008]], NAMES)}
    raw = tmp_path / "raw.json"
    raw.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(build, "RAW", raw)
    monkeypatch.setattr(build, "CSV_PATH", tmp_path / "out.csv")
    monkeypatch.setattr(build, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(build, "RAW_SHA256", hashlib.sha256(raw.read_bytes()).hexdigest())
    assert build.main([]) == 0
    assert "wrote out.csv: 6 rows" in capsys.readouterr().out
    assert build.main(["--check"]) == 0
    (tmp_path / "out.csv").write_text("jurisdiction\nTampered\n", encoding="utf-8")
    assert build.main(["--check"]) == 1


def test_a_header_that_does_not_end_in_a_year_is_refused() -> None:
    """Table selection reads the last header; one that is not a year raises."""
    with pytest.raises(ValueError, match="does not end in a year"):
        build._last_year(["State or other", "note"])  # pylint: disable=protected-access
