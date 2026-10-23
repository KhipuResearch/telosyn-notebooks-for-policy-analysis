#!/usr/bin/env python3
"""Build ``data/policy/medicaid/expansion_expenditure.csv`` from the CMS-64 file.

The source is CMS's *Medicaid CMS-64 New Adult Group Expenditures* dataset on data.medicaid.gov, the
state-by-quarter summary of spending on the ACA expansion population (the "VIII Group") reported
through the Medicaid Budget and Expenditure System. The file is a plain CSV. This script has two
stages, and the second never needs the network:

``--file FILE``
    Read a saved copy of the CSV, **refuse it unless its SHA-256 is the one recorded in**
    ``data/policy/medicaid/SOURCES.md`` (``RAW_SHA256`` below), copy it unchanged to
    ``expansion_expenditure.raw.csv``, then build the tidy CSV.

(no arguments)
    Rebuild the tidy CSV from the committed raw file.

``--check``
    Rebuild in memory and exit non-zero if the committed tidy CSV differs.

Nothing is typed from memory: every amount is read from the file. The parser raises on a header it
does not recognise, a quarter that is not a calendar quarter end, an amount it cannot read, a
duplicate state-quarter or a state that is not one of the 50 states and the District of Columbia; no
row is dropped or repaired, except that the territories and the "National Totals" row are set aside
and counted.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FOLDER = REPO_ROOT / "data" / "policy" / "medicaid"
RAW = FOLDER / "expansion_expenditure.raw.csv"
CSV_PATH = FOLDER / "expansion_expenditure.csv"
DATES_CSV = FOLDER / "expansion_dates.csv"

#: SHA-256 of the downloaded file, recorded in SOURCES.md on the access date.
RAW_SHA256 = "1b9232bac8abcb92f74963962b0d31d9ea299176120d657b22eae680810377e5"

#: The publisher's header, after stripping the stray space and quotes it puts around one name.
EXPECTED_HEADER = [
    "State",
    "Total Computable All Medical Assistance Expenditures",
    "Total Federal Share All Medical Assistance Expenditures",
    "Total Computable VIII Group Expenditures",
    "Total Federal Share VIII Group Expenditures",
    "Total Computable VIII Group Newly Eligible Expenditures",
    "Total Federal Share VIII Group Newly Eligible Expenditures",
    "Total Computable VIII Group Not Newly Eligible Expenditures",
    "Total Federal Share VIII Group Not Newly Eligible Expenditures",
    "Quarter End Date",
    "Updated Year",
    "Updated Month",
    "Notes",
]
VALUE_COLUMNS = [
    "all_medical_assistance_computable",
    "all_medical_assistance_federal",
    "viii_computable",
    "viii_federal",
    "viii_newly_eligible_computable",
    "viii_newly_eligible_federal",
    "viii_not_newly_eligible_computable",
    "viii_not_newly_eligible_federal",
]
COLUMNS = ["state", "quarter_end", "year", "quarter", *VALUE_COLUMNS, "note"]
SET_ASIDE = {
    "Amer. Samoa",
    "Guam",
    "N. Mariana Islands",
    "Puerto Rico",
    "Virgin Islands",
    "National Totals",
}
NAME_FIX = {"Dist. Of Col.": "District of Columbia"}
QUARTER_ENDS = {(3, 31): 1, (6, 30): 2, (9, 30): 3, (12, 31): 4}
_AMOUNT = re.compile(r"^-?\d[\d,]*$")
_PARENTHESISED = re.compile(r"^\((\d[\d,]*)\)$")  # accounting notation for a negative amount
_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")


def parse_amount(token: str) -> str:
    """An integer dollar amount as text: blank and ``N/A`` give "", ``(n)`` gives ``-n``."""
    text = token.strip()
    if text == "" or text.upper() == "N/A":
        return ""
    negative = _PARENTHESISED.match(text)
    if negative:
        return str(-int(negative.group(1).replace(",", "")))
    if not _AMOUNT.match(text):
        raise ValueError(f"unrecognised amount {token!r}")
    return str(int(text.replace(",", "")))


def parse_quarter_end(token: str) -> tuple[date, int]:
    """The calendar quarter end a ``m/d/yyyy`` date names, and its quarter number."""
    found = _DATE.match(token.strip())
    if not found:
        raise ValueError(f"unrecognised date {token!r}")
    month, day, year = (int(g) for g in found.groups())
    if (month, day) not in QUARTER_ENDS:
        raise ValueError(f"{token!r} is not a calendar quarter end")
    return date(year, month, day), QUARTER_ENDS[(month, day)]


def jurisdictions() -> list[str]:
    """The 50 states and the District of Columbia, from the repository's expansion table."""
    with DATES_CSV.open(encoding="utf-8", newline="") as handle:
        return [row["state"] for row in csv.DictReader(handle)]


def build_rows(text: str, names: list[str]) -> tuple[list[dict[str, str]], int]:
    """Tidy rows for the named jurisdictions, and the count of rows set aside."""
    reader = csv.reader(io.StringIO(text, newline=""))
    header = [cell.strip().strip('"').strip() for cell in next(reader)]
    if header != EXPECTED_HEADER:
        raise ValueError(f"unexpected header {header!r}")
    rows: dict[tuple[str, str], dict[str, str]] = {}
    set_aside = 0
    for raw in reader:
        if not raw:
            continue
        if len(raw) != len(EXPECTED_HEADER):
            raise ValueError(
                f"a row has {len(raw)} cells, expected {len(EXPECTED_HEADER)}: {raw[:2]!r}"
            )
        state = NAME_FIX.get(raw[0].strip(), raw[0].strip())
        if raw[0].strip() in SET_ASIDE:
            set_aside += 1
            continue
        if state not in names:
            raise ValueError(f"unrecognised jurisdiction {state!r}")
        when, quarter = parse_quarter_end(raw[9])
        key = (state, when.isoformat())
        if key in rows:
            raise ValueError(f"duplicate row for {state} at {when.isoformat()}")
        rows[key] = {
            "state": state,
            "quarter_end": when.isoformat(),
            "year": str(when.year),
            "quarter": str(quarter),
            **{name: parse_amount(raw[1 + i]) for i, name in enumerate(VALUE_COLUMNS)},
            "note": " ".join(raw[12].split()),
        }
    present = {s for s, _ in rows}
    if present != set(names):
        raise ValueError(f"jurisdictions differ: missing {sorted(set(names) - present)}")
    quarters = {s: {q for t, q in rows if t == s} for s in present}
    if len({frozenset(q) for q in quarters.values()}) != 1:
        raise ValueError("the states do not all report the same quarters")
    return [rows[key] for key in sorted(rows)], set_aside


def render_csv(rows: list[dict[str, str]]) -> str:
    """Deterministic CSV: fixed columns, LF endings."""
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    ap.add_argument("--file", type=Path, help="a saved copy of the CMS CSV")
    ap.add_argument("--check", action="store_true", help="fail if the committed CSV is stale")
    args = ap.parse_args(argv)
    if args.file is not None:
        data = args.file.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != RAW_SHA256:
            print(
                f"{args.file.name} has SHA-256 {digest}, not the recorded {RAW_SHA256}. "
                "Nothing was written.",
                file=sys.stderr,
            )
            return 2
        RAW.write_bytes(data)
    raw_bytes = RAW.read_bytes()
    if hashlib.sha256(raw_bytes).hexdigest() != RAW_SHA256:
        print(f"{RAW.name} is not the recorded file. Nothing was written.", file=sys.stderr)
        return 2
    rows, set_aside = build_rows(raw_bytes.decode("utf-8-sig"), jurisdictions())
    text = render_csv(rows)
    if args.check:
        if CSV_PATH.read_text(encoding="utf-8") != text:
            print(f"{CSV_PATH} is not what {RAW.name} produces.", file=sys.stderr)
            return 1
        print("expansion_expenditure.csv is current")
        return 0
    CSV_PATH.write_text(text, encoding="utf-8")
    shown = CSV_PATH.relative_to(REPO_ROOT) if CSV_PATH.is_relative_to(REPO_ROOT) else CSV_PATH.name
    print(f"wrote {shown}: {len(rows)} rows ({set_aside} territory and total rows set aside)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
