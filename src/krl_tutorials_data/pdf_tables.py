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

import math
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
    tokens: tuple[str, ...] = ()


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
        tokens = tuple(t.strip(_STRIP).replace(",", "") for t in rest if t.strip(_STRIP))
        rows.append(Row(lookup[label], values, line_no, tokens))
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


def repair_split_names(
    lines: Sequence[str], names: Sequence[str]
) -> tuple[list[str], list[tuple[int, str, str]]]:
    """Join a line that is one capital letter to the next line when that makes a jurisdiction's name.

    Text extraction sometimes breaks a word after its first letter (``L`` / ``ouisiana 82 86``). This is
    the only repair of a name: the next line must start with lower-case letters and the joined line must
    begin with one of ``names`` at a word boundary. Returns the new lines and, for every join, the
    1-based number of the lone letter's line in ``lines`` and the two pieces.
    """
    out: list[str] = []
    joins: list[tuple[int, str, str]] = []
    i = 0
    while i < len(lines):
        cur = lines[i].strip()
        if len(cur) == 1 and cur.isupper() and i + 1 < len(lines) and lines[i + 1].strip()[:1].islower():
            joined = cur + lines[i + 1].strip()
            if any(joined.startswith(n) and _boundary(joined, len(n)) for n in names):
                out.append(joined)
                joins.append((i + 1, cur, lines[i + 1].strip()))
                i += 2
                continue
        out.append(lines[i])
        i += 1
    return out, joins


def reconcile_row(row: Row, *, expected: int, max_value: float) -> tuple[float, ...] | None:
    """The row's values if they number ``expected``; one extra value is merged only if exactly one fit exists.

    A printed number can be split in two (``7 6`` for 76). With one value too many, adjacent pairs of
    whole-number tokens **from the fourth token on** are tried; the row is accepted only if exactly
    one merge gives ``expected`` values all at most ``max_value``. A split among the first three tokens
    is never repaired. Any other length returns ``None``.
    """
    if len(row.values) == expected:
        return row.values
    if len(row.values) != expected + 1 or len(row.tokens) != len(row.values):
        return None
    if any(math.isnan(v) for v in row.values):
        return None
    fits: list[tuple[float, ...]] = []
    for k in range(3, len(row.tokens) - 1):
        a, b = row.tokens[k], row.tokens[k + 1]
        if not (a.isdigit() and b.isdigit()):
            continue
        merged = [*row.values[:k], float(a + b), *row.values[k + 2:]]
        if all(v <= max_value for v in merged):
            fits.append(tuple(merged))
    return fits[0] if len(fits) == 1 else None


@dataclass(frozen=True)
class Profile:
    """One state's profile page: its 0-based page index and the labelled values found on it."""

    name: str
    page: int
    fields: dict[str, str | None]


def _heading(lines: Sequence[str], names: Mapping[str, str]) -> str | None:
    for line in lines[:6]:
        text = line.strip()
        for n in sorted(names, key=len, reverse=True):
            if text == n or re.match(re.escape(n) + r"\s*[\u2014\u2013-]", text):
                return names[n]
    return None


def parse_profiles(
    pages: Sequence[str],
    names: Sequence[str],
    labels: Mapping[str, str],
    aliases: Mapping[str, str] | None = None,
) -> list[Profile]:
    """State profile pages: a jurisdiction named in the first lines and at least one labelled value.

    ``labels`` maps a key to a regular expression for the label text. A value is the rest of the line
    after the label (optionally preceded by ``... -`` or ``...—`` on the same line, as in
    ``Simplified Reporting - Certification Length``). A label that is absent gives ``None``. A page
    with a heading but none of the labels is not a profile.
    """
    lookup = {n: n for n in names}
    lookup.update(aliases or {})
    found: list[Profile] = []
    for index, text in enumerate(pages):
        who = _heading(text.splitlines(), lookup)
        if who is None:
            continue
        fields: dict[str, str | None] = {}
        for key, label in labels.items():
            m = re.search(r"(?m)^(?:[^\n]*?[\u2014\u2013-]\s*)?" + label + r"\s+(\S[^\n]*?)\s*$", text)
            fields[key] = m.group(1) if m else None
        if any(v is not None for v in fields.values()):
            found.append(Profile(who, index, fields))
    return found


def online_offered(value: str) -> int:
    """1 if the printed value says states can apply online (the word "apply"), else 0."""
    return 1 if re.search(r"\bapply\b", value, re.IGNORECASE) else 0


def longest_months(value: str | None) -> float | None:
    """The largest whole number in a certification-length value, or ``None`` if it has none."""
    if value is None:
        return None
    numbers = re.findall(r"\d+", value)
    return float(max(int(n) for n in numbers)) if numbers else None
