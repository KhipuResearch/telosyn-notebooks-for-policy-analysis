"""``scripts/extract_epa_lcri_tables.py`` refuses a table in which a year appears twice, instead of keeping both rows or the last.

The real PDF is not committed, so the script's PDF reader is replaced by a stand-in whose pages hold rows built here.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from policy_support import load_script

SCRIPT = load_script("extract_epa_lcri_tables_under_test", "extract_epa_lcri_tables.py")


def _row(year: int) -> str:
    return f"{year} $10.0 $20.0 $10.0"


class _Page:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


def _reader_for(pages: dict[int, str]):
    class _Reader:
        def __init__(self, _path: str) -> None:
            self.pages = [_Page(pages.get(n, "")) for n in range(1, 712)]
    return _Reader


def _run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, pages: dict[int, str]) -> None:
    pdf = tmp_path / "stand_in.pdf"
    pdf.write_bytes(b"%PDF-1.7 stand-in")
    monkeypatch.setattr(SCRIPT, "EXPECTED_SHA256", hashlib.sha256(pdf.read_bytes()).hexdigest())
    monkeypatch.setattr(SCRIPT, "PdfReader", _reader_for(pages))
    SCRIPT.main(pdf, tmp_path / "out")


def test_a_year_repeated_on_the_same_page_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rows = [_row(y) for y in range(2024, 2059)] + [_row(2030)]
    pages = {709: "Exhibit 6-4: low\n" + "\n".join(rows)}
    with pytest.raises(SystemExit, match="the year 2030 appears twice"):
        _run(monkeypatch, tmp_path, pages)
    assert not (tmp_path / "out").exists()


def test_a_year_repeated_across_the_page_break_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pages = {709: "Exhibit 6-4: low\n" + "\n".join(_row(y) for y in range(2024, 2040)),
             710: "\n".join(_row(y) for y in range(2039, 2059))}              # 2039 closes page 709 and opens page 710
    with pytest.raises(SystemExit, match="the year 2039 appears twice"):
        _run(monkeypatch, tmp_path, pages)
    assert not (tmp_path / "out").exists()


def test_a_missing_year_is_a_different_refusal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pages = {709: "Exhibit 6-4: low\n" + "\n".join(_row(y) for y in range(2024, 2058))}
    with pytest.raises(SystemExit, match="missing or years extra"):
        _run(monkeypatch, tmp_path, pages)
