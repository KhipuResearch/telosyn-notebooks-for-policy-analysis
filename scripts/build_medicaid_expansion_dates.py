#!/usr/bin/env python3
"""Build ``data/policy/medicaid/expansion_dates.csv`` from KFF's published table.

The source is the KFF State Health Facts page "Status of State Action on the
Medicaid Expansion Decision". The page embeds its table as a JSON array. This
script has two stages, and the second never needs the network:

``--page FILE``
    Read a saved copy of the page, **refuse it unless its SHA-256 is the one
    recorded in** ``data/policy/medicaid/SOURCES.md`` (``PAGE_SHA256`` below),
    extract the embedded table and write it unchanged to
    ``expansion_dates.raw.json``, then build the CSV.

(no arguments)
    Rebuild the CSV from the committed ``expansion_dates.raw.json``.

``--check``
    Rebuild in memory and exit non-zero if the committed CSV differs.

Nothing is typed from memory: every state, status and date in the CSV is read
from the downloaded table. Anything the parser does not recognise raises; no row
is dropped or repaired.

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
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FOLDER = REPO_ROOT / "data" / "policy" / "medicaid"
RAW = FOLDER / "expansion_dates.raw.json"
CSV_PATH = FOLDER / "expansion_dates.csv"

#: SHA-256 of the downloaded page, recorded in SOURCES.md on the access date.
PAGE_SHA256 = "2498611e10665db07205ed8912a4522c16acd2947d72b1d996d6f934029cf3ba"

EXPECTED_HEADER = [
    "",
    "Status of Medicaid Expansion Decision",
    "Expansion Implementation Date",
    "Expansion Adopted Through Ballot Initiative",
    "Trigger Law In Place",
]
COLUMNS = ["state", "status", "expansion_effective", "ballot_initiative", "trigger_law"]
STATUSES = ("Adopted", "Not Adopted")
N_JURISDICTIONS = 51  # 50 states and the District of Columbia


def extract_table(page: bytes) -> list[list[str]]:
    """Return the embedded table (header, type row, summary row, then one row per state)."""
    text = page.decode("utf-8", "replace")
    anchor = text.find('["Alabama"')
    if anchor < 0:
        raise ValueError("the page does not contain the expected state table")
    start = text.rfind("[[", 0, anchor + 1)
    if start < 0:
        raise ValueError("the page does not contain the expected state table")
    depth = 0
    for end in range(start, len(text)):
        depth += (text[end] == "[") - (text[end] == "]")
        if depth == 0:
            break
    else:
        raise ValueError("the embedded table is not balanced")
    table = json.loads(text[start : end + 1])
    if table[0] != EXPECTED_HEADER:
        raise ValueError(f"the table header changed: {table[0]!r}")
    return table  # type: ignore[no-any-return]


def parse_date(value: str) -> str:
    """``m/d/yyyy`` to ISO ``yyyy-mm-dd``; raises on anything else."""
    parts = value.split("/")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"unrecognised date {value!r}")
    month, day, year = (int(p) for p in parts)
    return date(year, month, day).isoformat()


def build_rows(table: list[list[str]]) -> list[dict[str, str]]:
    """One record per jurisdiction. A state not adopted has no date and no flags."""
    body = table[3:]  # skip header, the type row and the "United States" summary row
    if len(body) != N_JURISDICTIONS:
        raise ValueError(f"expected {N_JURISDICTIONS} jurisdictions, found {len(body)}")
    rows: list[dict[str, str]] = []
    for raw in body:
        name, status = raw[0], raw[1]
        if status not in STATUSES:
            raise ValueError(f"{name}: unrecognised status {status!r}")
        if status == "Adopted":
            if len(raw) != 5:
                raise ValueError(f"{name}: an adopted state should have 5 fields, has {len(raw)}")
            rows.append({
                "state": name, "status": status, "expansion_effective": parse_date(raw[2]),
                "ballot_initiative": raw[3], "trigger_law": raw[4],
            })
        else:
            if len(raw) != 4 or raw[2] != "N/A" or raw[3] != "N/A":
                raise ValueError(f"{name}: a state not adopted should read N/A, N/A; got {raw}")
            rows.append({
                "state": name, "status": status, "expansion_effective": "",
                "ballot_initiative": "", "trigger_law": "",
            })
    names = [r["state"] for r in rows]
    if len(set(names)) != len(names):
        raise ValueError("duplicate jurisdiction in the table")
    return rows


def render_csv(rows: list[dict[str, str]]) -> str:
    """Deterministic CSV text: fixed column order, LF line endings, source row order."""
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    ap.add_argument("--page", type=Path, help="saved copy of the KFF page (verifies its digest)")
    ap.add_argument("--check", action="store_true", help="fail if the committed CSV is stale")
    args = ap.parse_args(argv)
    if args.page:
        page = args.page.read_bytes()
        digest = hashlib.sha256(page).hexdigest()
        if digest != PAGE_SHA256:
            print(f"{args.page} has SHA-256 {digest}, not the recorded {PAGE_SHA256}. The page was "
                  "revised or is a different file; read what changed, then update SOURCES.md and "
                  "PAGE_SHA256 together. Nothing was written.", file=sys.stderr)
            return 2
        RAW.write_text(json.dumps(extract_table(page), indent=1, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    table: list[list[str]] = json.loads(RAW.read_text(encoding="utf-8"))
    text = render_csv(build_rows(table))
    if args.check:
        if CSV_PATH.read_text(encoding="utf-8") != text:
            print(f"{CSV_PATH} is not what {RAW.name} produces.", file=sys.stderr)
            return 1
        print("expansion_dates.csv is current")
        return 0
    CSV_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {CSV_PATH.relative_to(REPO_ROOT)}: {len(text.splitlines()) - 1} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
