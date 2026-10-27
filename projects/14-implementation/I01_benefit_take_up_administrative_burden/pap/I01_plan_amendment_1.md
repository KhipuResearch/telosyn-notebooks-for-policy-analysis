<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# I01 plan — amendment 1 (2026-10-27)

Committed **before any take-up gap, feature coding, association, correlation or interval is
computed**. It amends `I01_plan.md` (commit `fc7a0ab`), which is not edited. The notebook binds its
provenance to the plan's digest and prints this file's digest beside it.

## What happened

After the plan, the approved files were retrieved once to a scratch folder and read **for layout only**
(page structure, row counts, the set of printed feature values). Three of the plan's stop-rules fired:

1. The FY 2018 and FY 2019 *Reaching* reports parse to 49 of 51 jurisdictions because text
   extraction splits a name across two lines ("L" / "ouisiana", "O" / "regon"), and the FY 2018 row for
   Oklahoma has a printed number split in two ("7 6").
2. The edition nearest FY 2022 within 18 months (the 15th, options as of 1 October 2022) has no online
   application option and no certification-length option; the 17th (as of 1 October 2024) is 36 months
   away.
3. The rates tables print no confidence interval; intervals exist only on chart pages whose text layer is
   scrambled.

The owner ruled on 2026-10-27 to approve the amendments below.

## Amendments

**A. Reading the rates tables.**
- A line that is a single capital letter, followed by a line that begins with lower-case letters and
  whose concatenation begins with a jurisdiction's name, is joined before parsing. This is the only
  repair of a name. It is tested on constructed text before any file is read by the notebook, and the
  notebook prints every join it makes.
- Only the **first three values** of a row are read for a report of FY 2014 to FY 2019 (the
  "all eligible people" columns for the report's three years) and the **first two** for the FY 2022
  report (columns headed 2020 and 2022). The value for the report's own fiscal year is the **last** of
  those. The header line is printed and must end with the report's own year or the notebook stops.
- A row whose number of values differs from the table's most common count is reported. A row with
  exactly one extra value is accepted only if merging **exactly one** adjacent pair of values from the
  fourth value on yields the common count with every value at most 100; the merge is printed. Any other
  mismatched row is excluded and named.
- Coverage: for the two association years (FY 2018, FY 2016) every one of the 51 jurisdictions must be
  present exactly once after these steps, or the notebook stops and the owner is asked. For years used
  only descriptively (FY 2022) up to three jurisdictions may be excluded and are named.
- No interval is printed for any rate (the tables carry none). The gap is reported without one and the
  notebook says so. Rates are as the reports print them: whole percent, capped at 100 in the later reports.

**B. Reading the options.** The features are read from each state's profile page in the State Options
Report, by label, not from the maps:
- A profile page is a page whose first lines name a jurisdiction (the name alone, or the name followed
  by a dash and the programme's name) and which carries the label `Online Application`.
- *Online application offered* = 1 if the printed value contains the word "apply" (for example
  "Apply & recertify", "Apply only", "Apply"), 0 otherwise ("No online application", "Recertify"). The
  value counts are printed.
- *Certification length (months)* = the largest whole number printed in the value of
  `Certification Length` (for example "12 & 24 months only" is 24; "4, 6, & 12 months" is 12). A value with
  no number (for example "Change reporting only") is missing and the state is left out of that
  correlation; the count is printed.
- Every one of the 51 jurisdictions must have exactly one profile with both labels, or the notebook
  stops and the owner is asked. Guam and the Virgin Islands are not in the rates and are left out.

**C. Which years.** Plan section 4's rule (nearest edition, within 18 months) is applied to the two
editions in which both features exist:
- **Primary year: FY 2018** with the 14th edition (options as of 1 October 2017; 0 months from the
  start of FY 2018).
- **Replication: FY 2016** with the 12th edition (options as of 1 October 2015; 0 months from the start of
  FY 2016).
- **FY 2022** is reported for the SNAP gap and, with the EITC, for the SNAP–EITC correlation. The
  options test for FY 2022 is **not possible** with the approved files and the notebook says so. Other
  years (FY 2014, 2015, 2017, 2019) are not paired and not used for the options test.

**D. The EITC.** Pairing by calendar year in plan section 5 is unchanged: FY 2018 with tax year 2018, FY 2016
with tax year 2016, FY 2022 with tax year 2022.

## Unchanged

The question, the estimands, the estimators (state-bootstrap interval, Mann–Whitney, Spearman, Holm over
the two feature tests in the primary year), the expected directions, the checks in plan section 7 (with
section 3's coverage rule as amended here) and every limitation in plan section 9, to which this
amendment adds: the choice of the longest period as the length, the coding of "Recertify" as no online
application, and the reduced number of years in which the features can be tested.
