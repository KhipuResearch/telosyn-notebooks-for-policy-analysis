<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# I01 plan — benefit take-up and administrative burden

Written and committed **before any FNS, IRS or other file is retrieved for this notebook**. The
notebook binds to this file by its SHA-256; changing the file afterwards breaks the gate. A change is
made only by a new, dated amendment file committed on its own before the numbers it concerns are
computed.

## 1. Question and estimand

Across states, how large is the share of eligible people who do not take up a benefit, and is the gap
associated with how burdensome a state's administration is? Three descriptive estimands:

1. **The SNAP take-up gap by state.** For each state and fiscal year, `gap = 100 − participation rate`,
   in percentage points of eligible people who did not receive SNAP, from USDA FNS's *Reaching Those
   in Need* series.
2. **The association between that gap and two administrative features,** taken from the same state's
   entry in FNS's *State Options Report*: whether the state offered an **online application**, and the
   **length of the certification period** it uses (months). These are the two features the track
   specification names (online application, recertification interval).
3. **The EITC take-up gap by state,** `100 − participation rate` for the tax year, from the IRS table
   of participation rates by state, and its rank correlation with the SNAP gap.

This is association across states. **It is not an effect of any administrative feature.** The
notebook refuses the causal reading in its text and names the design project 09 would need: a
staggered adoption of a feature across states, with an event-study and pre-trend test (C03's
design), on state-year data this notebook does not have.

## 2. Sources, by file (owner approval 2026-10-27)

| Source | File | Size when listed |
|---|---|---|
| FNS, *Reaching Those in Need*, FY 2014 | `ops/Reaching2014.pdf` | 1,106,307 bytes |
| FY 2015 | `ops/Reaching2015.pdf` | 563,270 |
| FY 2016 | `resource-files/Reaching2016.pdf` | 647,644 |
| FY 2017 | `resource-files/Reaching2017-1.pdf` | 1,134,902 |
| FY 2018 | `resource-files/Reaching2018.pdf` | 1,428,103 |
| FY 2019 | `resource-files/snap2019reaching.pdf` | 980,952 |
| FY 2022 | `resource-files/ear-snap-Reaching-Those-in-Need-2022.pdf` | 900,600 |
| FNS, *State Options Report*, 12th (April 2016) | `snap/12-State_Options.pdf` | 5,613,866 |
| 14th (May 2018) | `snap/14-State-Options.pdf` | 6,879,323 |
| 15th (October 2023) | `resource-files/snap-15th-state-options-report-october23.pdf` | 1,951,320 |
| 17th (August 2025) | `resource-files/snap-stateOptionsReport-17edition-120925.pdf` | 5,872,573 |
| IRS, EITC participation rate by state | the HTML table at `irs.gov/tax-professionals/eitc-central/eitc-participation-rate-by-state` (tax years 2014–2022) | about 18 KB |

All FNS paths are under `https://www.fna.usda.gov/sites/default/files/`. No ACS denominator is
retrieved: the participation rates are already participants over eligible people, and no ACS
retrieval is approved for this card. Other files the owner approved (the FY 2010–2013 and FY 2020
reports, the technical reports, the 9th–11th, 13th and 16th editions, the IRS methodology PDF) are not
used unless an amendment, committed first, says why.

## 3. How a PDF is read

The state tables exist only inside PDFs. `pypdf` (DECISIONS/0010) extracts each page's text; a pure
function parses the lines of the table into rows of `(state, value[, interval])` and is tested against
known answers on constructed text before any file is read. Nothing is read by eye and typed in.

- The table is located by its heading text in the extracted pages, not by page number.
- A row is accepted only if its leading name matches exactly one of the 51 jurisdictions (50 states
  and the District of Columbia) from the repository's FIPS table, and its values parse as numbers; any
  other line is reported with its page and dropped, never repaired.
- **Stop rules.** If a report's table yields fewer than 51 jurisdictions, or a jurisdiction twice, or
  a value outside 0 to 150, or the heading is not found, the notebook stops and the owner is asked. If
  a feature named in section 1 is not in an edition, the notebook stops and the owner is asked; no
  proxy is substituted.
- If the reports print a confidence interval or standard error for each state, it is carried and the
  gap is reported with it. If they print none, the gap is reported **without an interval** and the
  notebook says so; no interval is invented.

## 4. Joining take-up years to editions

A fiscal year's participation rate is joined to the State Options Report edition whose stated
"as of" date is nearest the start of that fiscal year (1 October of the previous calendar year). The
date is read from the edition's text and printed. A pairing whose distance exceeds **18 months** is
not made and the year is not used in the association. The notebook prints each pairing and its
distance. The **primary year** is the latest fiscal year with a pairing; other paired years are
reported as replications, not pooled.

## 5. Estimators

- **Gap:** `100 − rate` per state; the distribution (mean, median, minimum and maximum with states
  named) is descriptive and unweighted by population, because the unit is the state.
- **Online application (binary):** the difference in mean gap between states with and without the
  feature, with a 95% interval from a bootstrap over states (9,999 draws, seed 20261027, resampling
  states within each group), and the Mann–Whitney p-value. The difference is reported in percentage
  points of eligible people.
- **Certification period (months):** Spearman rank correlation with the gap, with a 95% state
  bootstrap interval (same draws and seed) and its p-value.
- **EITC:** Spearman correlation between the SNAP gap and the EITC gap in the same year where both
  exist, with the same interval; tax year and fiscal year are matched by the calendar year in which
  the fiscal year ends, and the notebook says that the periods overlap and do not coincide.
- **Multiplicity.** The two administrative-feature tests in the primary year are one family, corrected
  by `uncertainty.holm_bonferroni` at alpha = 0.05. The EITC correlation is a separate, single
  descriptive test and is not in the family. Replication years are not corrected and are labelled as
  replications.

## 6. Expected direction, stated before the data

States that offered an online application have a **smaller** gap (higher take-up); a longer
certification period goes with a **smaller** gap; the SNAP and EITC gaps are **positively**
correlated. No magnitude is predicted.

## 7. Checks (stored as `FALSIFICATION:` lines)

1. **Coverage.** Every retrieved table yields exactly the 51 jurisdictions once (section 3).
2. **Range.** Every rate lies between 0 and 150, and the number of rates above 100 is printed
   (the FNS estimates can exceed 100 for a state; they are shown, not clipped).
3. **Re-read.** Each PDF is read twice, page by page and as a whole, and the two parsed tables must
   be identical.
4. **Known-answer parser tests** on constructed text, in the library test suite, passed before any
   file was read.

## 8. What counts as what

- An association is **not distinguishable from zero** when its 95% state-bootstrap interval contains
  zero. It is stated with the interval in percentage points (binary) or as a correlation (ordinal);
  a null is never read as "no association".
- An association that survives Holm correction in the primary year is called **suggested by the
  data** and, because it is across 51 states in one year, is never called an effect.
- Any added analysis is labelled "not pre-specified (added after review, <date>)" in the cell and in
  Limitations.

## 9. Limitations the notebook must carry

Association only, across at most 51 states; states differ in many things the administrative features
travel with (income, population, politics, caseload), none modelled; the participation estimates are
FNS's and rest on survey and administrative data with their own error, which this notebook does not
re-derive; the fiscal year of the rate and the date of the options report do not coincide (section 4);
the EITC rate is a tax-year, individually linked estimate for a different benefit and population; the
gap is not population-weighted; the reports can estimate a rate above 100; the two features are the
two the track names, not a complete measure of burden; PDF text extraction is a parse of typeset
tables and is checked, not proven (section 7). If the analysis departs from this plan, the Limitations
section says how and why.
