<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# State minimum wages — U.S. Department of Labor, Wage and Hour Division

Captured **2026-10-16** (UTC) from the publisher's page in a browser. Nothing was typed from
memory: every cell in `state_schedule.csv` is read from the captured table by
`scripts/build_minimum_wage_schedule.py`, which parses strictly and raises on anything it does not
recognise.

## What was captured, and what it is not

| | |
|---|---|
| Publisher | U.S. Department of Labor, Wage and Hour Division |
| Title | *Changes in Basic Minimum Wages in Non-Farm Employment Under State Law: Selected Years 1968 to 2024* |
| URL | `https://www.dol.gov/agencies/whd/state/minimum-wage/history` |
| Access date | 2026-10-16, 04:10:41 UTC (the capture's own timestamp) |
| Revision date, in the page's words | "This document was last revised in January 2025." |
| Publisher's sources, in the page's words | rates 1968–1998: *Book of the States*, 1968–1999 edition, vol. 32 (Council of State Governments); rates 2000 to the present: the Department's own *Minimum Wage and Overtime Pay Standards Applicable to Nonsupervisory NONFARM Private Sector Employment Under State and Federal Laws* |

**This is not a download of the served file.** The publisher's CDN answers a scripted HTTP client
with `403 Access Denied` (the same happened at `medicaid.gov`), so no original byte stream could be
fetched and hashed. The page was instead loaded in the in-app browser and its content read from the
rendered page. Two things follow, and both are stated so nobody mistakes the digests for more than
they are:

- **The saved artifact is a capture, not the HTML.** `state_schedule.raw.json` holds the page's
  six tables (header and cell text, as `innerText`), the page's notes, and the capture metadata.
  Its SHA-256 identifies *that capture*. It was written from the browser's output and checked
  byte-for-byte against the digest the browser computed over the same string (after a
  transcription error in one note, a year, was found by that comparison and corrected).
- **The rendered DOM cannot be hashed stably.** The page's own scripts change the document
  between reads: the whole-document serialisation measured 141,600, 147,248 and 147,264
  characters in three reads within minutes. The `<main>` element is smaller and was hashed once
  at capture time: **58,181 characters, SHA-256
  `c24a5472ceb211872e0f6cf36fbdac3b5026d4009463cfeed0e55456b7358e82`**. That digest identifies the
  rendered `<main>` at that moment; the HTML itself is not committed and cannot be recovered from
  it. It is recorded as the rendered DOM's digest and as nothing stronger.

The raw capture also contains, verbatim, a block of the site's own CSS that the page places inside
`<main>`; it is kept rather than edited out.

## Files

| File | Bytes | SHA-256 | What it is |
|---|---|---|---|
| `state_schedule.raw.json` | 28,728 | `b19cef86e498e2b1015c99ad06ffe6bc173d0136243cd51908764932b5638fa6` | the captured tables and notes, all six tables, 1968–2024 |
| `state_schedule.csv` | 43,897 | `54ca943911dd5f75530f76d0598a21bae13f9bb0eeb8db4978e4089d01e95b1a` | long format, 2007–2024, 55 jurisdictions × 18 years = 990 rows |

## Transformation

`python scripts/build_minimum_wage_schedule.py` refuses a raw capture whose digest is not the one
above, checks the three tables it uses are contiguous in years with identical jurisdictions in the
same order, and writes the CSV; `--check` fails if the committed CSV is stale. Per row:

- `rate_as_published` — the cell text, unchanged;
- `status` — `rate`, or `not_applicable` for the page's `...` (its key: "not applicable");
- `rate_low`, `rate_high`, `rate_form` — `single`, `range` (`a-b`, `a – b`) or `alternatives`
  (`a/b`); a range means the rate differs by industry, occupation or the like, per the page;
- `footnote_markers` — the page's letters, e.g. `c`, `e`, `g,j`, `i2`; their meaning is in the notes
  of the raw capture.

Years before 2007 stay in the raw capture only: the earlier tables carry weekly and daily rates
and typographical errors (e.g. `4..65(g,,j)`) that this CSV has no use for.

## Hazards, each visible in the source

- **January 1 only.** The page says "Wage rates are for January 1 of each year". An increase that
  takes effect later in a year appears only in the next January's column, so the table can place a
  change up to eleven months late. Timing from this table is the timing of a January-1 snapshot.
- **A "basic" rate.** The title says so. Where a state sets different rates by employer size, the
  table carries one figure and a footnote marker, not the schedule. For California, the January-1
  figures read **10.00 (2016), 10.00 (2017), 11.00 (2018), 12.00 (2019)**. TRACKS §3 C04 describes
  the first step of the 2017 schedule as "to $10.50 for employers with 26 or more employees"; the
  table's 2017 figure is 10.00. Any analysis that defines treatment or donors from this table must
  say which employer-size definition the figure follows. Recorded in `QUESTIONS.md`.
- **A state rate below the federal rate is not the binding rate.** Several states show a statutory
  figure under the federal one (the raw table shows Georgia at 5.15 and Wyoming at 5.15 against a
  federal 7.25). The effective minimum is the greater of the two; this file does not compute it.
- **`...` means no state minimum in the table's sense, not "no minimum applies".** The federal rate
  still applies.
- **Increases are not marked.** The page says "Wage rates in bold indicate an increase over the
  previous year's rate"; bold is formatting and is not in the capture. Increases must be derived by
  comparing columns.
- **Ranges and alternatives are not scalars.** 80 cells are ranges and 2 are alternatives (Nevada
  2022 and 2023, `9.50/10.50` and `10.25/11.25`). `rate_low` and `rate_high` carry both ends.
- **Footnoted coverage differs by state**: `[c]` employers of four or more, `(d)` six or more, `(e)`
  two or more, `(g)` lower rates for small enterprises in several states, and so on, as the notes
  state. The marker is kept; the threshold is not applied.
- **Territories are in the table** (Guam, Puerto Rico, U.S. Virgin Islands) beside the federal row,
  the 50 states and the District of Columbia. A notebook filters; the file does not.
- **Coverage ends at 2024** and the page was last revised January 2025. Later years are not here.
- **Join key is the jurisdiction name.** No FIPS code is in the source and none is typed here.
