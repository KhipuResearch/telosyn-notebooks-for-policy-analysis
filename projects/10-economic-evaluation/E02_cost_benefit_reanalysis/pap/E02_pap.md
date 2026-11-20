<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# E02 pre-analysis plan — a re-analysis of EPA's economic analysis of the Lead and Copper Rule Improvements: discounting, scenarios and the switching rate

Written and committed **before the source document is downloaded**. The notebook binds to this file by its SHA-256 (`krl.pap`); a committed plan is never
edited, and a change is a new amendment file. Written under the owner ruling of 2026-10-30.

## 1. What this is, and what it is not

E02 takes a federal regulatory impact analysis, the U.S. Environmental Protection Agency's *Economic Analysis for the Final Lead and Copper Rule
Improvements* (October 2024), and re-does its arithmetic: it rebuilds the headline present values and annualised values from the analysis's own
yearly streams, shows how they move with the discount rate, and reports the scenario bounds the analysis itself publishes.

**This is a re-analysis of EPA's assumptions, not an independent estimate.** Every cost, every benefit quantity, every dollar value per unit of
benefit, every schedule and every low and high bound is EPA's. The notebook estimates nothing about lead in water, about health or about what the rule
costs. If EPA's assumptions are wrong, so is everything here; the notebook can only show how much of EPA's headline depends on the discount rate and
on the scenario EPA chose to publish.

**Regulatory status, checked on 2026-10-30.** EPA published the final rule in the Federal Register on 2024-10-30 (document 2024-23549). EPA's program
page, last updated 2025-12-29 by its own date line, shows the rule as final and shows no stay, rescission or reconsideration; it requires water systems
to comply three years after promulgation, with a state or EPA extension of the compliance start for treatment-technique requirements possible for up to
five years. A search of EPA and Federal Register pages on the same date returned nothing on reconsideration or litigation; **court dockets were not
searched.** The notebook states this status and the date it was checked. **The re-analysis of a published analysis does not depend on the rule's status:**
the question is what EPA's published numbers imply, whether or not the rule is later changed, delayed or withdrawn.

## 2. The source: one file, pinned, never committed

Exactly one file is approved for download: `https://www.epa.gov/system/files/documents/2024-10/508_lcri_final_ea_10-21-2024.pdf`, **9,589,288 bytes**,
`Last-Modified` 24 Oct 2024. Before the body is fetched, the size reported by the server is compared with 9,589,288 bytes; **if it differs, the download
stops and the owner is asked.** Nothing else is fetched without asking. The file is cached **outside the repository**, pinned by its SHA-256
(recorded on first fetch), and never committed. The URL, size, `Last-Modified`, retrieval time and SHA-256 are recorded in a `SOURCES.md` beside the
extracted tables and in a provenance record bound to this plan by its digest, and the fetch is on the run ledger.

**What is committed:** only the tables extracted from the document, as CSV, each tied to its **page and table number in the PDF** (the table's own caption
and number as printed, and the PDF page index), together with checks of each extracted table against **EPA's printed totals** (the total printed in the
same table or in the summary table that repeats it). The tables are values EPA published, reproduced as data with provenance; no prose of the document is
committed.

## 3. Discount rates and the Circular A-4 in force

**OMB Circular A-4, version in force, verified on OMB's circulars page on 2026-10-30:** the page lists Circular A-4 dated 17 September 2003 (the file
`CircularA-4.pdf` of the page, 48 pages, which sets the 3 percent and 7 percent rates). The 2023 revision (which set a 2 percent default) is not listed
there. The page does not itself say the 2023 text was rescinded; secondary sources disagree on the date. The plan therefore fixes:

| Role | Rates | Why |
|---|---|---|
| **Primary** | **3% and 7%** | the 2003 text, the version OMB's site shows in force |
| **Reproduction and sensitivity** | **2%** | EPA's published headline was computed at 2% (owner ruling); the 2% rate is also the 2023 revision's default |
| **Sensitivity grid** | 0%, 1%, 2%, 3%, 4%, 5%, 7%, 10% | to locate the switching rate |

The notebook states, from the document, which rates EPA itself used and prints them; **if EPA's headline was not computed at 2% the notebook stops and
the owner is asked** before any figure is labelled a reproduction. Timing of cash flows (start, middle or end of year) and the year to which values are
discounted are **EPA's, as the document states them**; the notebook prints the passage's page and reproduces EPA's present values under that convention.
If the document does not state a convention, the notebook stops and asks the owner; it does not try conventions until one matches.

## 4. Headline quantities, fixed before the document is read

For EPA's central scenario, in EPA's dollars and base year (the notebook states them from the document; it does not re-inflate):

1. **Present value of total costs** and **annualised total costs** at the rate EPA used.
2. **Present value of total monetised benefits** and **annualised total monetised benefits**, in total and by the benefit categories EPA itemises.
3. **Net benefits** (benefits minus costs) in present value and annualised.
4. **The benefit-cost ratio.**
5. The same four at 3% and 7%, from EPA's yearly streams discounted by the library.

The unit of the streams is the year as EPA tabulates it. Benefits that EPA does not monetise stay unmonetised and are listed, never given a value.

## 5. Reproduction check against EPA's printed totals (tolerance fixed here)

The notebook rebuilds quantities 1 to 3 at EPA's rate from the **yearly streams** with `methods.discount` and compares them with EPA's printed present
values and annualised values. **Tolerance: the larger of 0.5 percent of EPA's printed value and one unit in the last printed digit of that value.**
PASS if every compared quantity is within it. A quantity outside the tolerance is reported as a failure, the reproduction is declared not achieved, and the
notebook does **not** go on to present re-discounted figures as comparable with EPA's headline; it stops and asks the owner. Where EPA also prints totals
at other rates, the same check is made at those rates.

## 6. Low and high estimates

EPA's low and high estimates are **scenario bounds, not distributions.** The notebook reports them as scenarios: the central scenario, and the low and
high scenarios exactly as EPA labels and defines them (stated from the document, each with the assumption EPA says it varies). It then reports a
**scenario grid**: every scenario EPA publishes streams for, crossed with the sensitivity rates of section 3. Where EPA publishes only bounds on a total
and not yearly streams for them, the bound is shown as EPA's printed number at EPA's rate and is **not re-discounted**.

**No Monte Carlo, no random draw over EPA's ranges, and no probability statement about any quantity.** Random draws over bounds would assign a
distribution EPA did not assert and would be a model of the world, the reserved `model` data mode. The notebook contains no random-number call. If a
probabilistic analysis seems necessary, the work stops and the owner is asked.

## 7. The switching discount rate

For each scenario whose yearly net benefit stream is available, the notebook finds the discount rate at which the present value of net benefits changes
sign (the internal rate of return of the net stream), searched over 0% to 20%, by root-finding on the library's present value, and prints the bracket
used. Possible results: **none in the range** (net benefits keep one sign at every rate in the range) or one rate or more than one rate (a stream that
changes sign more than once can have several). The notebook reports what it finds and says which of the 3% and 7% primary rates, and of the 2%
reproduction rate, fall on each side. A switching rate is a property of EPA's streams, not a forecast.

## 8. Falsification and checks (each stored as a `FALSIFICATION:` line)

1. **Source identity.** The cached file's size equals 9,589,288 bytes and its SHA-256 equals the one recorded in the provenance record and in `SOURCES.md`.
2. **Extracted tables against EPA's printed totals.** For each extracted table, the sum of its rows equals EPA's printed total within the larger of
   0.5 percent and one unit in the last printed digit. PASS if all tables are.
3. **Reproduction at EPA's rate** (section 5). PASS if every compared quantity is within tolerance.
4. **Monotone in the rate.** The present value of any non-negative stream falls as the rate rises; the library's present values on EPA's cost and
   benefit streams are non-increasing over the sensitivity grid. A violation means a stream is mis-signed or mis-ordered.
5. **Discount-factor identity.** The library's present value of a constant stream equals the closed-form annuity value at every grid rate (a check of
   the library on a case with a known answer, not of EPA).

A check that fails is reported and not explained away.

## 9. Stop rules

- **(a)** If the analysis does not publish **benefit and cost streams by year** (only annualised values or present values), the work **stops and asks the
  owner before re-discounting anything.** The notebook does not reconstruct streams from totals.
- **(b)** No Monte Carlo over EPA's low and high ranges (section 6). If a probabilistic analysis seems necessary, stop and ask.
- **(c)** The server's size differs from 9,589,288 bytes: stop before the body is fetched, and ask.
- **(d)** EPA's headline was not computed at 2%, or the document states no timing convention: stop and ask.
- **(e)** The reproduction check (section 5) is not met: stop and ask.
- **(f)** A table cannot be extracted without ambiguity (merged cells, footnotes that change a value, rows that do not sum): stop and ask rather than choose a reading.

## 10. What counts as a finding

- **Reproduced:** checks 1 to 3 pass. Then the sensitivity of EPA's net benefits and benefit-cost ratio to the rate (3% and 7% primary, 2% reproduction, the
  grid) is a description of EPA's streams.
- **Not reproduced:** reported as not reproduced, with the quantities and the gaps; nothing downstream is presented as comparable.
- **Direction expected, stated before the document is read:** none. Costs fall earlier than benefits in most such analyses, so a higher rate would be
  expected to lower the benefit-cost ratio; if the streams show otherwise, the notebook says so.

## 11. Software and what is committed

No new dependency. The yearly streams are discounted by `krl_tutorials_data.methods.discount`; the switching-rate search and the annualisation are
added there as pure functions with known-answer tests written first. Table extraction reuses the repository's PDF tools (`pypdf`, declared) and is a
documented, repeatable step whose output is the committed CSV. The notebook reads the committed CSVs, verifies their digests against `SOURCES.md`, and
does not require the PDF. The notebook contains no random-number call.

## 12. Limitations the notebook must carry

It is a re-analysis of EPA's assumptions and not an independent estimate; every dollar value is EPA's; the low and high estimates are scenario bounds and
carry no probability; unmonetised benefits stay unmonetised; the discount rates are a choice (the 2003 text's 3 and 7 percent as primary, 2 percent
because EPA used it) and the choice of Circular A-4 version was verified on one date; EPA's streams are in EPA's dollars and base year and are not
re-inflated; the rule's status was checked on one date and court dockets were not searched; the extraction takes values from a PDF and is checked
against EPA's printed totals only. If the analysis departs from this plan, the Limitations section says how and why, and a departure that moves the
primary result is a new amendment, committed before the result it changes is computed.
