"""The Medicaid expansion table: the transform, the committed files, and their record.

Fixture pages are built in the test; the committed CSV is held to the digests its
``SOURCES.md`` states, so the file and the record cannot drift apart.

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
FOLDER = REPO / "data" / "policy" / "medicaid"


def _script() -> ModuleType:
    """Script."""
    spec = importlib.util.spec_from_file_location(
        "build_medicaid", REPO / "scripts" / "build_medicaid_expansion_dates.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = _script()


def _table(adopted: list[list[str]] | None = None, n: int = 51) -> list[list[str]]:
    """A table with the real header and ``n`` synthetic state rows (fixture, not data)."""
    rows = adopted or []
    pad = [["Alabama" if i == 0 else f"State{i}", "Not Adopted", "N/A", "N/A"]
           for i in range(n - len(rows))]
    return [build.EXPECTED_HEADER, ["", "Text", "Text", "Text", "Text"],
            ["United States", "Adopted: 1", "", "", ""], *rows, *pad]


def _page(table: list[list[str]]) -> bytes:
    """Page."""
    return ("<html><script>var d=" + json.dumps(table) + ";</script></html>").encode()


def test_extract_and_build_a_known_row_by_hand() -> None:
    """Extract and build a known row by hand."""
    rows = [["Alpha", "Adopted", "1/1/2014", "No", "Yes"],
            ["Beta", "Adopted", "8/15/2014", "Yes (November 2018)", "No"]]
    table = build.extract_table(_page(_table(rows)))
    built = build.build_rows(table)
    assert built[0] == {"state": "Alpha", "status": "Adopted", "expansion_effective": "2014-01-01",
                        "ballot_initiative": "No", "trigger_law": "Yes"}
    assert built[1]["expansion_effective"] == "2014-08-15"
    assert built[2] == {"state": "Alabama", "status": "Not Adopted", "expansion_effective": "",
                        "ballot_initiative": "", "trigger_law": ""}


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda t: t[3].__setitem__(1, "Pending"), "unrecognised status"),
        (lambda t: t.__setitem__(3, ["Alpha", "Adopted", "13/45/2014", "No", "No"]), "month"),
        (lambda t: t.__setitem__(3, ["Alpha", "Adopted", "soon", "No", "No"]), "unrecognised date"),
        (lambda t: t.__setitem__(3, ["Alpha", "Adopted", "1/1/2014", "No"]), "5 fields"),
        (lambda t: t.__setitem__(3, ["Alpha", "Not Adopted", "1/1/2014", "N/A"]), "N/A, N/A"),
        (lambda t: t.append(["Extra", "Not Adopted", "N/A", "N/A"]), "expected 51"),
        (lambda t: t.__setitem__(4, list(t[3])), "duplicate"),
    ],
)
def test_the_parser_raises_rather_than_repairing(mutate, message: str) -> None:
    """The parser raises rather than repairing."""
    table = _table([["Alpha", "Adopted", "1/1/2014", "No", "No"]])
    mutate(table)
    with pytest.raises(ValueError, match=message):
        build.build_rows(table)


def test_a_changed_header_or_missing_table_is_refused() -> None:
    """A changed header or missing table is refused."""
    bad = _table()
    bad[0] = ["", "Status", "Date", "Ballot", "Trigger"]
    with pytest.raises(ValueError, match="header changed"):
        build.extract_table(_page(bad))
    with pytest.raises(ValueError, match="does not contain"):
        build.extract_table(b"<html>nothing here</html>")
    with pytest.raises(ValueError, match="not balanced"):
        build.extract_table(b'<html>[["Alabama", "x"</html>')


def test_a_page_with_the_wrong_digest_writes_nothing(tmp_path: Path, capsys) -> None:
    """A page with the wrong digest writes nothing."""
    page = tmp_path / "page.html"
    page.write_bytes(_page(_table()))
    before = (FOLDER / "expansion_dates.csv").read_bytes()
    assert build.main(["--page", str(page)]) == 2
    assert "not the recorded" in capsys.readouterr().err
    assert (FOLDER / "expansion_dates.csv").read_bytes() == before


def test_the_committed_csv_is_what_the_committed_raw_table_produces() -> None:
    """The committed csv is what the committed raw table produces."""
    assert build.main(["--check"]) == 0


def test_the_files_match_the_digests_and_sizes_in_sources_md() -> None:
    """The files match the digests and sizes in sources md."""
    text = (FOLDER / "SOURCES.md").read_text(encoding="utf-8")
    for name in ("expansion_dates.raw.json", "expansion_dates.csv"):
        data = (FOLDER / name).read_bytes()
        pattern = rf"\|\s*`{re.escape(name)}`\s*\|\s*([\d,]+)\s*\|\s*`([0-9a-f]{{64}})`"
        row = re.search(pattern, text)
        assert row, f"{name} has no row in SOURCES.md"
        assert int(row.group(1).replace(",", "")) == len(data)
        assert row.group(2) == hashlib.sha256(data).hexdigest()
    assert build.PAGE_SHA256 in text, "the script and SOURCES.md name different page digests"
    assert "118,038 bytes" in text


def test_the_committed_table_is_complete_and_self_consistent() -> None:
    """The committed table is complete and self consistent."""
    rows = list(csv.DictReader((FOLDER / "expansion_dates.csv").open(encoding="utf-8")))
    assert len(rows) == 51 and len({r["state"] for r in rows}) == 51
    adopted = [r for r in rows if r["status"] == "Adopted"]
    assert all(r["expansion_effective"] for r in adopted)
    assert all(not r["expansion_effective"] for r in rows if r["status"] == "Not Adopted")
    assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["expansion_effective"]) for r in adopted)
    assert "District of Columbia" in {r["state"] for r in rows}
    assert "41 adopted, 10 not adopted" in (FOLDER / "SOURCES.md").read_text(encoding="utf-8")
    assert (len(adopted), len(rows) - len(adopted)) == (41, 10)


def test_page_to_csv_end_to_end_and_the_staleness_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """A page with the pinned digest is extracted and built; a doctored CSV fails --check."""
    page = tmp_path / "page.html"
    page.write_bytes(_page(_table([["Alpha", "Adopted", "1/1/2014", "No", "Yes"]])))
    monkeypatch.setattr(build, "PAGE_SHA256", hashlib.sha256(page.read_bytes()).hexdigest())
    monkeypatch.setattr(build, "RAW", tmp_path / "raw.json")
    monkeypatch.setattr(build, "CSV_PATH", tmp_path / "out.csv")
    monkeypatch.setattr(build, "REPO_ROOT", tmp_path)
    assert build.main(["--page", str(page)]) == 0
    assert "wrote out.csv: 51 rows" in capsys.readouterr().out
    assert build.main(["--check"]) == 0
    (tmp_path / "out.csv").write_text("state\nTampered\n", encoding="utf-8")
    assert build.main(["--check"]) == 1
    assert build.main([]) == 0 and build.main(["--check"]) == 0
