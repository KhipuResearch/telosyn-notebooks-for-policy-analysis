<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# Medicaid expansion dates — KFF State Health Facts

Retrieved **2026-10-16** (UTC) from the publisher's own page, by an HTTP GET with a plain
client (`curl -L`, `User-Agent: Mozilla/5.0 (research)`). Nothing was typed from memory: every
state, status and date in `expansion_dates.csv` is read from the downloaded table by
`scripts/build_medicaid_expansion_dates.py`.

## The download

| | |
|---|---|
| Publisher | KFF (Kaiser Family Foundation), State Health Facts |
| Title | *Status of State Action on the Medicaid Expansion Decision* |
| URL | `https://www.kff.org/affordable-care-act/state-indicator/state-activity-around-expanding-medicaid-under-the-affordable-care-act/` |
| Access date | 2026-10-16 |
| Response | HTTP 200, `text/html; charset=UTF-8` |
| Size | 118,038 bytes |
| SHA-256 of the original | `2498611e10665db07205ed8912a4522c16acd2947d72b1d996d6f934029cf3ba` |
| Data as of (the page's own words) | "States' decisions about adopting the Medicaid expansion are as of October 2026." |
| Publisher's stated source | "Current status for each state is based on KFF tracking and analysis of state executive activity." |

The page is revised in place and serves no prior version, so the digest identifies this
retrieval and nothing a later visit will return. The original page is **not committed**; the
table it embeds is, unchanged, as `expansion_dates.raw.json`.

## Files

| File | Bytes | SHA-256 | What it is |
|---|---|---|---|
| `expansion_dates.raw.json` | 3,768 | `3fd9325549635bbc4b34180bf39f658a8c2c268cddcf2ef85e207e53953fbc66` | the embedded table, extracted verbatim (header, type row, summary row, 51 state rows) |
| `expansion_dates.csv` | 1,857 | `cf7734a78b72416f02212bf68aa23bb208dd48e8afa12a2c4bab97a3fc5a018f` | the transformation below |

## Transformation

`python scripts/build_medicaid_expansion_dates.py --page <saved page>` verifies the page's
digest, writes the raw table, then builds the CSV; with no arguments it rebuilds the CSV from the
committed raw table, and `--check` fails if the CSV is stale. The only changes are:

- the summary row ("United States") is dropped, and the type row is dropped;
- dates `m/d/yyyy` become ISO `yyyy-mm-dd`;
- for a state not adopted, KFF's `N/A` becomes an empty field;
- columns are renamed: `state`, `status`, `expansion_effective`, `ballot_initiative`,
  `trigger_law`.

No row is dropped, repaired or added. The parser raises on an unknown status, a date it cannot
read, a row of the wrong length, a duplicate state, or a count other than 51 jurisdictions.

## What the file says, as read from it

51 jurisdictions (50 states and the District of Columbia): 41 adopted, 10 not adopted, matching
the page's own summary row.

## Hazards, each visible in the source

- **One date per state.** The table gives a single "Expansion Implementation Date". It has no
  column for partial or early expansions before that date, and none for coverage that was made
  retroactive. A study that dates treatment from this column inherits that definition.
- **Implementation is not always effective coverage.** The page's own footnotes say Maine began
  implementing on 10 January 2019 "with coverage retroactive to July 2018", and that Missouri's
  coverage began on processing in October 2021 "with coverage retroactive to July 1, 2021". The
  table carries the implementation dates, 2019-01-10 and 2021-10-01.
- **The page disagrees with itself for Nebraska.** The table gives 2020-10-01; the footnote says
  the state terminated its waiver in August 2021 and "began offering all expansion adults full
  benefits starting October 1, 2021". Both are the publisher's words; the file keeps the table's
  date and this note records the conflict.
- **Idaho and Utah** read 2020-01-01 in the table although voters approved expansion in November
  2018; the footnotes describe state-level changes to the program. Dates are implementation, not
  adoption.
- **Mid-year dates** exist (Michigan 2014-04-01, New Hampshire 2014-08-15, Alaska 2015-09-01,
  Louisiana 2016-07-01, among others). A year-level treatment indicator must say how it treats
  them.
- **The trigger-law and ballot-initiative columns are the publisher's text**, kept verbatim
  (`Yes (November 2018)`), not coded to booleans.
- **Join key is the state name.** The table carries no FIPS code, and adding one here would mean
  typing a mapping from memory. A notebook joins on the ACS `NAME` column, which uses the same
  names, and checks that all 51 match.

---

# Medicaid expansion expenditure — CMS-64 New Adult Group

Retrieved **2026-10-23** (UTC) by an HTTP GET with a plain client (`curl -L`, `User-Agent: Mozilla/5.0 (research)`),
after the dataset's own metadata record on data.medicaid.gov was read to find the file. Nothing was typed from
memory: every state, quarter and amount in `expansion_expenditure.csv` is read from the downloaded file by
`scripts/build_medicaid_expansion_expenditure.py`.

## The download

| | |
|---|---|
| Publisher | Centers for Medicare & Medicaid Services (CMS), through data.medicaid.gov |
| Title | *Medicaid CMS-64 New Adult Group Expenditures* |
| Dataset identifier | `00505e90-f8ac-5921-b12f-5e23ba7ffcf3`; the record was last modified 2026-02-17 |
| URL | `https://download.medicaid.gov/data/medicaid-cms-64-new-adult-group-expenditures-dataset-02172026.csv` |
| Access date | 2026-10-23 |
| Response | HTTP 200, `application/octet-stream`; the portal reports no length, so the size is that of the bytes received |
| Size | 374,311 bytes |
| SHA-256 of the original | `1b9232bac8abcb92f74963962b0d31d9ea299176120d657b22eae680810377e5` |
| Licence | the dataset record points to <https://www.usa.gov/government-works> (a US-government work) |
| Publisher's description | the new adult group's summary-level expenditures, reported by states through the Medicaid Budget and Expenditure System (MBES). "VIII GROUP" is the new adult group; its figures are "N/A" for states that have not adopted it; "0" means no expenditures or not yet reported; MCHIP expenditures are not included in All Medical Assistance Expenditures |

The original is committed unchanged as `expansion_expenditure.raw.csv`.

## Files

| File | Bytes | SHA-256 | What it is |
|---|---|---|---|
| `expansion_expenditure.raw.csv` | 374,311 | `1b9232bac8abcb92f74963962b0d31d9ea299176120d657b22eae680810377e5` | the downloaded file, unchanged |
| `expansion_expenditure.csv` | 266,707 | `20ebd2560030dc10d1bfc186c8e1d00e6bcd8e70f09a0cbded4204caa241a35a` | the transformation below |

## Transformation

`python scripts/build_medicaid_expansion_expenditure.py --file <saved download>` verifies the digest, copies the
file unchanged, then builds the tidy CSV; with no arguments it rebuilds the tidy CSV from the committed raw file, and
`--check` fails if the tidy CSV is stale. The only changes are:

- rows for the territories (American Samoa, Guam, the Northern Mariana Islands, Puerto Rico, the Virgin Islands) and
  the "National Totals" row are set aside (276 rows) and counted, not kept;
- the publisher's `Dist. Of Col.` becomes `District of Columbia`, to match the expansion-dates table;
- quarter-end dates `m/d/yyyy` become ISO `yyyy-mm-dd`, with `year` and `quarter` columns; a date that is not a
  calendar quarter end is an error;
- amounts lose their thousands commas; `N/A` and blank become an empty field; a figure in parentheses, which is
  accounting notation for a negative amount (for example `(72,227)`), becomes a negative number;
- the `Updated Year` and `Updated Month` columns are dropped (they are inconsistent, for example swapped in some rows);
- columns are renamed: `all_medical_assistance_*`, `viii_*`, `viii_newly_eligible_*`, `viii_not_newly_eligible_*`
  (each as `_computable` and `_federal`), and `note` holds the publisher's footnote text.

No other row is dropped, repaired or added. The parser raises on a header it does not recognise, an amount it cannot
read, a duplicate state-quarter, a jurisdiction that is not one of the 50 states and the District of Columbia, or states
that do not report the same quarters.

## What the file says, as read from it

51 jurisdictions by 46 quarters (quarter ends 2014-03-31 to 2025-06-30) = 2,346 rows. 744 rows have no VIII Group total:
the states that have not adopted the group, and the quarters before an adopting state began.
Where all three are present, `viii_newly_eligible_computable` plus `viii_not_newly_eligible_computable` equals
`viii_computable` to within a dollar in every row.

## Hazards, each visible in the source

- **Negative amounts.** 65 cells in the VIII Group total and its two components are negative. The publisher's notes
  attribute them to prior-period adjustments reported in that quarter. They are kept as reported; a quarterly series
  can fall.
- **Zero is ambiguous.** The publisher says a state that reports "0" has either no expenditures for the category or has
  not yet reported. A zero for an expanded state in a quarter after expansion is therefore not evidence of no spending.
- **Reporting errors the publisher flags.** Some notes say a state's newly eligible federal share exceeds its total
  computable, or that CMS "is working with the state to correct this claiming issue". The figures are kept as published.
- **Notes carry dates.** Many notes state a state's adoption date. These are the publisher's words and are not used to
  date treatment here; the KFF table is the source of treatment dates (see above) and the two can differ.
- **Totals include only the VIII Group's medical assistance.** Administrative spending is not in this file.
- **Join key is the state name,** as for the expansion-dates table.
