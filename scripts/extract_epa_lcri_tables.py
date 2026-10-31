"""Extract the yearly streams (Exhibits 6-4 and 6-5) and EPA's printed 2% annualised totals (Exhibit 6-6) from the cached EPA PDF.

E02 (DECISIONS/0009; projects/10-economic-evaluation/E02_cost_benefit_reanalysis/pap). Usage::

    python -I scripts/extract_epa_lcri_tables.py <pdf> <out_dir>

The PDF is the one file approved for E02 and is never committed; its SHA-256 must equal ``EXPECTED_SHA256``. Only the extracted
tables are written, each row tied to its exhibit and PDF page. The script stops (non-zero exit) when a table is ambiguous: a
missing year, a net that is not benefits minus costs, or a printed total that does not match.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import csv
import hashlib
import re
import sys
from pathlib import Path

from pypdf import PdfReader

EXPECTED_SHA256 = "057c531f5bf14910f321a653bcdf341317676325b0d3dafeef4e874054bca350"
YEARS = range(2024, 2059)
#: (scenario, exhibit, 1-based PDF pages that hold its rows). Exhibit 6-4 starts on page 709 and runs to 710; 6-5 starts on 710.
EXHIBITS = (("low", "Exhibit 6-4", (709, 710)), ("high", "Exhibit 6-5", (710, 711)))
ROW = re.compile(r"^(20\d\d) (-?\$[\d,]+\.\d) (-?\$[\d,]+\.\d) (-?\$[\d,]+\.\d)\s*$")
MONEY = r"(-?\$[\d,]+\.\d)"


def _num(token: str) -> float:
    return float(token.replace("$", "").replace(",", ""))


def _fail(message: str) -> None:
    sys.exit(f"STOP: {message}")


def main(pdf: Path, out: Path) -> None:
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        _fail(f"the PDF's SHA-256 is {digest}, not the recorded {EXPECTED_SHA256}")
    pages = {n: (PdfReader(str(pdf)).pages[n - 1].extract_text() or "") for n in (709, 710, 711)}
    rows: list[dict[str, object]] = []
    seen: dict[str, set[int]] = {}
    for scenario, exhibit, page_numbers in EXHIBITS:
        started = False
        for n in page_numbers:
            for line in pages[n].split("\n"):
                text = line.strip()
                if text.startswith(f"{exhibit}:"):
                    started = True
                if scenario == "low" and text.startswith("Exhibit 6-5:"):
                    started = False
                if not started:
                    continue
                m = ROW.match(text)
                if m:
                    year = int(m.group(1))
                    cost, benefit, net = (_num(g) for g in m.groups()[1:])
                    rows.append({"scenario": scenario, "year": year, "incremental_costs_musd": cost, "incremental_benefits_musd": benefit,
                                 "net_benefits_musd": net, "source_exhibit": exhibit, "pdf_page": n})
                    seen.setdefault(scenario, set()).add(year)
    for scenario in ("low", "high"):
        if seen.get(scenario) != set(YEARS):
            _fail(f"{scenario}: rows for {sorted(set(YEARS) - seen.get(scenario, set()))} missing or years extra")
    for r in rows:
        if abs(float(r["incremental_benefits_musd"]) - float(r["incremental_costs_musd"]) - float(r["net_benefits_musd"])) > 0.1001:
            _fail(f"{r['scenario']} {r['year']}: net is not benefits minus costs within 0.1")
    # EPA's text (page 708): "Total undiscounted net benefits range from $479 billion to $918 billion."
    for scenario, lo, hi in (("low", 478.5, 479.5), ("high", 917.5, 918.5)):
        total = sum(float(r["net_benefits_musd"]) for r in rows if r["scenario"] == scenario) / 1000.0
        if not lo <= total <= hi:
            _fail(f"{scenario}: undiscounted net benefits {total:.1f} billion do not match the printed {round(total)} billion")
    # Exhibit 6-6 (page 711): annualised incremental costs, benefits and net benefits at 2 percent.
    text = " ".join(pages[711].split())
    m = re.search(r"Exhibit 6-6:.*?Annualized Incremental Costs " + MONEY + r"\s+" + MONEY + r" Annualized Incremental Benefits " + MONEY + r"\s+" + MONEY
                  + r" Annual Net Benefits " + MONEY + r"\s+" + MONEY, text)
    if not m:
        _fail("Exhibit 6-6 could not be read")
    c_lo, c_hi, b_lo, b_hi, n_lo, n_hi = (_num(g) for g in m.groups())
    printed = [
        {"scenario": "low", "quantity": "annualized_incremental_costs", "value_musd": c_lo},
        {"scenario": "high", "quantity": "annualized_incremental_costs", "value_musd": c_hi},
        {"scenario": "low", "quantity": "annualized_incremental_benefits", "value_musd": b_lo},
        {"scenario": "high", "quantity": "annualized_incremental_benefits", "value_musd": b_hi},
        {"scenario": "low", "quantity": "annual_net_benefits", "value_musd": n_lo},
        {"scenario": "high", "quantity": "annual_net_benefits", "value_musd": n_hi},
    ]
    for r in printed:
        r.update(discount_rate=0.02, source_exhibit="Exhibit 6-6", pdf_page=711)
    if abs(b_lo - c_lo - n_lo) > 0.11 or abs(b_hi - c_hi - n_hi) > 0.11:
        _fail("Exhibit 6-6: net is not benefits minus costs")
    out.mkdir(parents=True, exist_ok=True)
    for name, data in (("epa_lcri_yearly_streams.csv", rows), ("epa_lcri_printed_annualized_2pct.csv", printed)):
        with (out / name).open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(data)
    print(f"wrote {len(rows)} yearly rows and {len(printed)} printed totals to {out}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
