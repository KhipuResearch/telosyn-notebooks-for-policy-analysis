"""The Medicaid expansion expenditure table: the transform, the committed files, and their record.

Fixture files are built in the test (synthetic, labelled as such); the committed tidy CSV is held to
the digests its ``SOURCES.md`` states, so the file and the record cannot drift apart.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from policy_support import REPO, assert_file_matches_sources, load_script

FOLDER = REPO / "data" / "policy" / "medicaid"


build = load_script("build_expenditure", "build_medicaid_expansion_expenditure.py")
HEADER = ",".join(
    [
        "State",
        "Total Computable All Medical Assistance Expenditures",
        "Total Federal Share All Medical Assistance Expenditures",
        "Total Computable VIII Group Expenditures",
        "Total Federal Share VIII Group Expenditures",
        "Total Computable VIII Group Newly Eligible Expenditures",
        "Total Federal Share VIII Group Newly Eligible Expenditures",
        ' "Total Computable VIII Group Not Newly Eligible Expenditures"',
        "Total Federal Share VIII Group Not Newly Eligible Expenditures",
        "Quarter End Date",
        "Updated Year",
        "Updated Month",
        "Notes",
    ]
)


def _line(
    state: str, when: str, total: str = "N/A", newly: str = "N/A", not_newly: str = "N/A"
) -> str:
    """One synthetic row; the amounts are made up and the others are blank."""
    return f'{state},"1,000 ","500 ","{total} ",,"{newly} ",,"{not_newly} ",,{when},2026,1,\n'


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("1,234,567 ", "1234567"),
        ("0", "0"),
        ("-5,000", "-5000"),
        ("(72,227)", "-72227"),
        ("N/A", ""),
        (" n/a ", ""),
        ("", ""),
    ],
)
def test_every_published_form_of_an_amount_parses_to_the_value_read_by_hand(
    token: str, expected: str
) -> None:
    """Commas, parentheses for a negative, blanks and N/A are the forms the file uses."""
    assert build.parse_amount(token) == expected


@pytest.mark.parametrize("token", ["$5", "1.5", "12-", "abc", "(5", "1 000"])
def test_an_unrecognised_amount_raises_rather_than_being_guessed(token: str) -> None:
    """Anything else is refused."""
    with pytest.raises(ValueError, match="unrecognised amount"):
        build.parse_amount(token)


def test_quarter_ends_parse_to_iso_with_their_quarter_number() -> None:
    """3/31 is the first quarter and 12/31 the fourth, in either date padding."""
    assert build.parse_quarter_end("3/31/2014") == (build.date(2014, 3, 31), 1)
    assert build.parse_quarter_end("12/31/2019") == (build.date(2019, 12, 31), 4)
    for token in ("2/28/2014", "3/30/2014", "March", "2014-03-31"):
        with pytest.raises(ValueError):
            build.parse_quarter_end(token)


def test_a_small_file_builds_the_rows_worked_by_hand() -> None:
    """Two synthetic jurisdictions over two quarters; the territory row is set aside and counted."""
    text = HEADER + "\n"
    for state in ("Alpha", "Beta"):
        text += _line(state, "3/31/2014") + _line(state, "6/30/2014", "200", "250", "(50)")
    text += _line("Guam", "3/31/2014") + _line("National Totals", "3/31/2014")
    rows, aside = build.build_rows(text, ["Alpha", "Beta"])
    assert aside == 2 and len(rows) == 4
    cell = next(r for r in rows if r["state"] == "Beta" and r["quarter_end"] == "2014-06-30")
    assert (cell["year"], cell["quarter"], cell["viii_computable"]) == ("2014", "2", "200")
    assert (cell["viii_newly_eligible_computable"], cell["viii_not_newly_eligible_computable"]) == (
        "250",
        "-50",
    )
    assert int(cell["viii_computable"]) == int(cell["viii_newly_eligible_computable"]) + int(
        cell["viii_not_newly_eligible_computable"]
    )
    empty = next(r for r in rows if r["state"] == "Alpha" and r["quarter_end"] == "2014-03-31")
    assert empty["viii_computable"] == ""


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda t: t.replace("Quarter End Date", "Quarter"), "unexpected header"),
        (lambda t: t + _line("Gamma", "3/31/2014"), "unrecognised jurisdiction"),
        (lambda t: t + _line("Alpha", "3/31/2014"), "duplicate row"),
        (lambda t: t.replace("6/30/2014", "6/29/2014", 1), "calendar quarter end"),
        (lambda t: t.replace('"1,000 "', '"$1"', 1), "unrecognised amount"),
        (lambda t: t + "Alpha,1,2\n", "cells"),
        (lambda t: t.replace(_line("Beta", "6/30/2014"), ""), "same quarters"),
    ],
)
def test_the_parser_raises_rather_than_repairing(mutate, message: str) -> None:
    """A bad header, state, duplicate, date, amount, row length or set of quarters is refused."""
    text = (
        HEADER
        + "\n"
        + "".join(_line(s, q) for s in ("Alpha", "Beta") for q in ("3/31/2014", "6/30/2014"))
    )
    with pytest.raises(ValueError, match=message):
        build.build_rows(mutate(text), ["Alpha", "Beta"])


def test_a_missing_jurisdiction_is_refused() -> None:
    """Asking for a jurisdiction the file does not hold stops the build."""
    text = HEADER + "\n" + _line("Alpha", "3/31/2014")
    with pytest.raises(ValueError, match="jurisdictions differ"):
        build.build_rows(text, ["Alpha", "Beta"])


def test_a_file_with_the_wrong_digest_writes_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    """A file whose digest is not the recorded one is refused before anything is written."""
    fake = tmp_path / "other.csv"
    fake.write_bytes(b"State\n")
    monkeypatch.setattr(build, "RAW", tmp_path / "raw.csv")
    monkeypatch.setattr(build, "CSV_PATH", tmp_path / "out.csv")
    assert build.main(["--file", str(fake)]) == 2
    assert "not the recorded" in capsys.readouterr().err
    assert not (tmp_path / "raw.csv").exists() and not (tmp_path / "out.csv").exists()


def test_the_committed_csv_is_what_the_committed_raw_file_produces() -> None:
    """The tidy table is current."""
    assert build.main(["--check"]) == 0


def test_the_files_match_the_digests_and_sizes_in_sources_md() -> None:
    """Each committed file has a row in SOURCES.md with its size and SHA-256."""
    for name in ("expansion_expenditure.raw.csv", "expansion_expenditure.csv"):
        assert_file_matches_sources(FOLDER, name)
    assert build.RAW_SHA256 in (FOLDER / "SOURCES.md").read_text(encoding="utf-8")


def test_the_committed_table_is_complete_and_the_known_cells_read_as_published() -> None:
    """51 jurisdictions by 46 quarters, and two cells read by hand from the downloaded file."""
    rows = list(csv.DictReader((FOLDER / "expansion_expenditure.csv").open(encoding="utf-8")))
    assert len(rows) == 51 * 46 and len({r["state"] for r in rows}) == 51
    assert {r["quarter_end"] for r in rows} >= {"2014-03-31", "2019-12-31", "2025-06-30"}
    cell = {(r["state"], r["quarter_end"]): r for r in rows}
    dc = cell[("District of Columbia", "2014-12-31")]
    # read from the file: 77,540,290 = 73,873,412 newly eligible + 3,666,878 not newly eligible
    assert (
        dc["viii_computable"],
        dc["viii_newly_eligible_computable"],
        dc["viii_not_newly_eligible_computable"],
    ) == ("77540290", "73873412", "3666878")
    arkansas = cell[("Arkansas", "2022-09-30")]
    # the file prints the not-newly-eligible component as (72,227): a negative adjustment
    assert arkansas["viii_not_newly_eligible_computable"] == "-72227"
    assert (
        int(arkansas["viii_computable"]) == int(arkansas["viii_newly_eligible_computable"]) - 72227
    )
    assert cell[("Alabama", "2014-12-31")]["viii_computable"] == ""


def test_the_components_add_to_the_total_in_every_row_that_has_all_three() -> None:
    """Newly plus not-newly eligible equals the VIII Group total, within a dollar."""
    rows = list(csv.DictReader((FOLDER / "expansion_expenditure.csv").open(encoding="utf-8")))
    checked = 0
    for r in rows:
        parts = [
            r["viii_computable"],
            r["viii_newly_eligible_computable"],
            r["viii_not_newly_eligible_computable"],
        ]
        if all(parts):
            checked += 1
            assert abs(int(parts[0]) - int(parts[1]) - int(parts[2])) <= 1, (
                r["state"],
                r["quarter_end"],
            )
    assert checked > 1000


def test_main_builds_from_a_saved_download_and_rebuilds_from_the_raw_file(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """End to end on the real file with outputs redirected, then the staleness check."""
    raw = (FOLDER / "expansion_expenditure.raw.csv").read_bytes()
    saved = tmp_path / "download.csv"
    saved.write_bytes(raw)
    monkeypatch.setattr(build, "RAW", tmp_path / "raw.csv")
    monkeypatch.setattr(build, "CSV_PATH", tmp_path / "out.csv")
    assert build.main(["--file", str(saved)]) == 0
    assert "2346 rows" in capsys.readouterr().out
    assert build.main(["--check"]) == 0
    (tmp_path / "out.csv").write_text("state\nTampered\n", encoding="utf-8")
    assert build.main(["--check"]) == 1
    (tmp_path / "raw.csv").write_bytes(b"State\n")
    assert build.main([]) == 2
