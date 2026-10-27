"""Parse state-by-state tables from text a PDF reader has already extracted.

Estimand
    None. This reads rows, it does not estimate.

Assumptions
    A table row starts with a jurisdiction's name and is followed by numbers. Names are matched
    longest first and only at the start of a line and at a word boundary, so ``Virginia`` does not
    claim a line that begins ``West Virginia``. A line that begins with a name and whose remainder
    does not parse is **reported**, never repaired or dropped silently. Lines that do not begin
    with a name (headings, prose, notes) are not rows and are not reported.

Numbers
    Thousands separators, ``%``, ``$``, ``±``, parentheses and footnote marks are removed; ``n/a``,
    ``na``, ``--`` and the dashes become NaN. A value that is still not a number is a rejection.

The package does not read PDFs; a notebook does that with the library named in DECISIONS/0010 and
hands the text lines here. Nothing here performs I/O.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

_MISSING: Final[frozenset[str]] = frozenset({"n/a", "na", "--", "-", "–", "—", "−"})
_STRIP: Final[str] = "%$,*†‡±()"


@dataclass(frozen=True)
class Row:
    """One accepted row: the canonical jurisdiction, its numbers and its 1-based line."""

    name: str
    values: tuple[float, ...]
    line_no: int


@dataclass(frozen=True)
class Rejected:
    """A line that began with a jurisdiction name but could not be read as a row."""

    line_no: int
    line: str
    reason: str


@dataclass(frozen=True)
class ParsedTable:
    """The rows read and the lines that began with a name and failed."""

    rows: list[Row] = field(default_factory=list)
    rejected: list[Rejected] = field(default_factory=list)


@dataclass(frozen=True)
class Coverage:
    """Which expected jurisdictions are absent or occur more than once."""

    missing: list[str]
    repeated: list[str]

    @property
    def complete(self) -> bool:
        """True when every expected jurisdiction occurs exactly once."""
        return not self.missing and not self.repeated


def _number(token: str) -> float:
    cleaned = token.strip(_STRIP).replace(",", "")
    if token.lower() in _MISSING or cleaned.lower() in _MISSING:
        return float("nan")
    return float(cleaned.strip(_STRIP))


def parse_jurisdiction_rows(
    lines: Iterable[str], names: Sequence[str], aliases: Mapping[str, str] | None = None
) -> ParsedTable:
    """Read rows that begin with one of ``names`` (or an alias, mapped to its canonical name)."""
    lookup = {n: n for n in names}
    lookup.update(aliases or {})
    ordered = sorted(lookup, key=len, reverse=True)
    rows: list[Row] = []
    rejected: list[Rejected] = []
    for line_no, raw in enumerate(lines, start=1):
        line = raw.strip()
        label = next((n for n in ordered if line.startswith(n) and _boundary(line, len(n))), None)
        if label is None:
            continue
        rest = line[len(label):].split()
        if not rest:
            rejected.append(Rejected(line_no, line, "no values after the name"))
            continue
        if not any(t.strip(_STRIP) for t in rest):
            rejected.append(Rejected(line_no, line, "no values after the name"))
            continue
        try:
            values = tuple(_number(t) for t in rest if t.strip(_STRIP))
        except ValueError:
            bad = next(t for t in rest if t.strip(_STRIP) and not _parses(t))
            rejected.append(Rejected(line_no, line, f"unparseable value {bad!r}"))
            continue
        rows.append(Row(lookup[label], values, line_no))
    return ParsedTable(rows, rejected)


def _boundary(line: str, end: int) -> bool:
    """True when the name ends at a word boundary: the next character is not a letter or an apostrophe."""
    return end >= len(line) or not (line[end].isalpha() or line[end] in "'’")


def _parses(token: str) -> bool:
    try:
        _number(token)
    except ValueError:
        return False
    return True


def find_pages(pages: Sequence[str], heading: str) -> list[int]:
    """Zero-based indices of pages whose text contains ``heading``, ignoring case and all whitespace.

    Whitespace is ignored entirely because PDF text extraction often splits a word at a kerning gap
    (``T able``) or joins two words.
    """
    target = "".join(heading.lower().split())
    return [i for i, text in enumerate(pages) if target in "".join(text.lower().split())]


def check_coverage(rows: Sequence[Row], expected: Sequence[str]) -> Coverage:
    """Which ``expected`` jurisdictions are missing, and which occur more than once."""
    seen = Counter(r.name for r in rows)
    return Coverage(
        missing=[n for n in expected if seen[n] == 0],
        repeated=[n for n in expected if seen[n] > 1],
    )
