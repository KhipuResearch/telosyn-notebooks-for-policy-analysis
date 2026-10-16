"""The handbook stubs and the source map for the expansion say only what is true yet.

The stubs state what a section will contain and which card fills it; they carry no
figure, because no expansion notebook has produced one. The source map marks a
source ``VERIFIED`` only where this repository's own build reached it.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parents[1] / "docs"
METHOD = (DOCS / "methodology.md").read_text(encoding="utf-8")
SOURCE_MAP = (DOCS / "source-map.md").read_text(encoding="utf-8")

STUBS = {
    18: ("Identification", ("C01", "C06")),
    19: ("Appraisal and distribution", ("E01", "Q01")),
    20: ("Models and scenarios", ("project 12",)),
}


def _section(number: int) -> str:
    """Section."""
    match = re.search(rf"^## {number}\. .*?(?=^## |\Z)", METHOD, re.M | re.S)
    assert match, f"section {number} is missing from docs/methodology.md"
    return match.group(0)


@pytest.mark.parametrize("number", sorted(STUBS))
def test_each_stub_exists_once_names_its_cards_and_is_marked_a_stub(number: int) -> None:
    """Each stub exists once names its cards and is marked a stub."""
    name, cards = STUBS[number]
    assert len(re.findall(rf"^## {number}\. ", METHOD, re.M)) == 1
    body = _section(number)
    assert body.splitlines()[0] == f"## {number}. {name}"
    assert "Stub" in body and "filled by" in body
    for card in cards:
        assert card in body


@pytest.mark.parametrize("number", sorted(STUBS))
def test_a_stub_asserts_no_figure(number: int) -> None:
    """A stub asserts no figure."""
    body = _section(number)
    # Bare integers here are identifiers (project numbers, an ADR number); a figure is a
    # percentage, a decimal or a number with thousands separators.
    figures = re.findall(r"\d+\s?%|\d+\.\d+|\d{1,3}(?:,\d{3})+", body.split("\n", 1)[1])
    assert not figures, f"stub {number} contains figures that no notebook has produced: {figures}"


def test_the_stubs_do_not_reuse_numbers_that_were_already_taken() -> None:
    """The stubs do not reuse numbers that were already taken."""
    numbers = [int(n) for n in re.findall(r"^## (\d+)\. ", METHOD, re.M)]
    assert len(numbers) == len(set(numbers)), "a section number is used twice"
    assert {18, 19, 20} <= set(numbers)


NEW_SOURCES = (
    "ACS PUMS", "CPS ASEC", "CMS MBES", "DOL", "KFF", "USDA FNS", "IRS SOI", "CBO",
)


def test_the_source_map_lists_every_expansion_source_with_a_status() -> None:
    """The source map lists every expansion source with a status."""
    block = SOURCE_MAP.split("## Expansion", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in block.splitlines() if line.startswith("| **")]
    for source in NEW_SOURCES:
        row = next((r for r in rows if source in r), None)
        assert row, f"{source} has no row in the expansion block of docs/source-map.md"
        assert re.search(r"\b(BUILT|VERIFIED|UNVERIFIED)\b", row), f"{source} row has no status"


def test_nothing_is_verified_that_the_build_did_not_reach() -> None:
    """Nothing is verified that the build did not reach."""
    block = SOURCE_MAP.split("## Expansion", 1)[1].split("\n## ", 1)[0]
    for source in ("CPS ASEC", "CMS MBES", "USDA FNS", "IRS SOI", "CBO"):
        row = next(r for r in block.splitlines() if r.startswith("| **") and source in r)
        assert "UNVERIFIED" in row and "VERIFIED" not in row.replace("UNVERIFIED", "")
