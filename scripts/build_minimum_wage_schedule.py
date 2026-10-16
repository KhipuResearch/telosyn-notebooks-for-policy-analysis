#!/usr/bin/env python3
"""Build ``data/policy/minimum_wage/state_schedule.csv`` from the DOL capture.

The source is the U.S. Department of Labor Wage and Hour Division page "Changes in
Basic Minimum Wages in Non-Farm Employment Under State Law: Selected Years 1968 to
2024". The page's host refuses scripted HTTP clients, so the committed
``state_schedule.raw.json`` is a **capture of the rendered page read in a browser**
(its six tables, cell text, and the page's notes); ``SOURCES.md`` says exactly what
that is and what it is not.

This script never touches the network. It

1. refuses a raw capture whose SHA-256 is not ``RAW_SHA256``;
2. checks the three tables it uses are structurally what it expects (header,
   contiguous years, identical jurisdictions in the same order, equal row widths);
3. parses every cell strictly -- an unrecognised value raises, nothing is guessed --
   and writes one row per jurisdiction and year.

``--check`` rebuilds in memory and fails if the committed CSV differs.

Years before ``FIRST_YEAR`` stay in the raw capture only: the earlier tables carry
weekly and daily rates and typographical errors that this CSV does not need.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FOLDER = REPO_ROOT / "data" / "policy" / "minimum_wage"
RAW = FOLDER / "state_schedule.raw.json"
CSV_PATH = FOLDER / "state_schedule.csv"

#: SHA-256 of the committed raw capture, recorded in SOURCES.md.
RAW_SHA256 = "b19cef86e498e2b1015c99ad06ffe6bc173d0136243cd51908764932b5638fa6"
FIRST_YEAR = 2007

COLUMNS = [
    "jurisdiction", "year", "rate_as_published", "status", "rate_low", "rate_high",
    "rate_form", "footnote_markers",
]
HEADER_START = "State or other"
_VALUE = re.compile(
    r"^\$?(?P<a>\d+\.\d{2})(?:\s*(?P<sep>[-–/])\s*\$?(?P<b>\d+\.\d{2}))?"
    r"\s*(?:[(\[](?P<marks>[a-z0-9, ]+)[)\]])?$"
)


def parse_value(text: str) -> dict[str, Any]:
    """Parse one published cell. ``...`` is DOL's "not applicable"; anything else must match."""
    if text == "...":
        return {"status": "not_applicable", "rate_low": None, "rate_high": None,
                "rate_form": "", "footnote_markers": ""}
    m = _VALUE.match(text)
    if not m:
        raise ValueError(f"unrecognised wage value {text!r}")
    first = float(m["a"])
    second = float(m["b"]) if m["b"] else first
    form = "single" if m["b"] is None else ("alternatives" if m["sep"] == "/" else "range")
    marks = (m["marks"] or "").replace(" ", "")
    return {"status": "rate", "rate_low": min(first, second), "rate_high": max(first, second),
            "rate_form": form, "footnote_markers": marks}


def _years(header: list[str]) -> list[int]:
    if not header[0].startswith(HEADER_START):
        raise ValueError(f"unexpected table header {header[0]!r}")
    return [int(h) for h in header[1:]]


def _last_year(header: list[str]) -> int:
    """Final year of a table whose headers may carry footnote markers, e.g. ``1968 (a)``."""
    found = re.match(r"\d{4}", header[-1])
    if not found:
        raise ValueError(f"table header does not end in a year: {header[-1]!r}")
    return int(found.group(0))


def build_rows(
    tables: list[dict[str, Any]], *, first_year: int = FIRST_YEAR
) -> list[dict[str, Any]]:
    """Long-format rows for every table year at or after ``first_year``."""
    rows: list[dict[str, Any]] = []
    names: list[str] | None = None
    last_year: int | None = None
    for table in tables:
        years = _years(table["header"])
        if years != list(range(years[0], years[0] + len(years))):
            raise ValueError(f"table years are not contiguous: {years}")
        if last_year is not None and years[0] != last_year + 1:
            raise ValueError(f"tables are not contiguous: {last_year} then {years[0]}")
        last_year = years[-1]
        these = [r[0] for r in table["rows"]]
        if names is None:
            names = these
        elif these != names:
            raise ValueError("the jurisdictions differ between tables")
        for raw in table["rows"]:
            if len(raw) != len(years) + 1:
                raise ValueError(f"{raw[0]}: {len(raw) - 1} cells for {len(years)} years")
            for year, cell in zip(years, raw[1:]):
                if year < first_year:
                    continue
                rows.append({"jurisdiction": raw[0], "year": year, "rate_as_published": cell,
                             **parse_value(cell)})
    return rows


def render_csv(rows: list[dict[str, Any]]) -> str:
    """Deterministic CSV: fixed columns, LF endings, empty field for a missing number."""
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow({
            k: ("" if r[k] is None else (f"{r[k]:.2f}" if isinstance(r[k], float) else r[k]))
            for k in COLUMNS
        })
    return out.getvalue()


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    ap.add_argument("--check", action="store_true", help="fail if the committed CSV is stale")
    args = ap.parse_args(argv)
    raw_bytes = RAW.read_bytes()
    digest = hashlib.sha256(raw_bytes).hexdigest()
    if digest != RAW_SHA256:
        print(f"{RAW.name} has SHA-256 {digest}, not the recorded {RAW_SHA256}. Nothing was "
              "written.", file=sys.stderr)
        return 2
    doc = json.loads(raw_bytes)
    used = [t for t in doc["tables"] if _last_year(t["header"]) >= FIRST_YEAR]
    text = render_csv(build_rows(used))
    if args.check:
        if CSV_PATH.read_text(encoding="utf-8") != text:
            print(f"{CSV_PATH} is not what {RAW.name} produces.", file=sys.stderr)
            return 1
        print("state_schedule.csv is current")
        return 0
    CSV_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {CSV_PATH.relative_to(REPO_ROOT)}: {len(text.splitlines()) - 1} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
