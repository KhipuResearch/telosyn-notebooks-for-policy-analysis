<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# I01 plan — amendment 4 (DRAFT for owner review, 2026-10-29)

Committed **before any fiscal 2022 options association is computed**. It adds one test and changes nothing else. `I01_plan.md` and amendments 1, 2
and 3 are not edited; they are cited by file name and SHA-256 in `krl.pap`, not by commit id.

## What was wrong

Amendment 1 and the notebook said the 15th State Options Report (options as of 1 October 2022) has neither a certification-length nor an
online-application option, so no fiscal 2022 options test was possible. The Review 4 pass searched the 15th edition's text and found that this was
**wrong for certification length**: the edition carries certification periods under the heading "Certification Periods for Households With
Simplified Reporting Requirements" (58 matches). It still has no online-application option under any term searched. Fiscal 2022 pairs with the
15th edition by plan section 4 (options as of 1 October 2022, twelve months from the start of fiscal 2022, inside the 18-month limit).
The heading was **not** recoded and no fiscal 2022 association was computed before this amendment.

## Owner decision requested

Authorise (or decline) **one** additional test, in fiscal 2022 only:

- **Feature:** certification length, in months, coded from that heading for the 51 jurisdictions.
- **Statistic:** Spearman rank correlation between months and the fiscal 2022 SNAP gap, with a 95% state-bootstrap interval (9,999 draws, seed
  20261027) and its p-value, exactly as plan section 5 specifies for the primary year.
- **Expected direction, stated now:** a longer certification period goes with a **smaller** gap (plan section 6). No magnitude is predicted.
- **Status:** a single descriptive test, **not** in the Holm family and **not** a second primary result. It is labelled "not pre-specified (added
  after review, 2026-10-29)" in the cell and the report. The primary year, the Holm family and every fiscal 2019 result are unchanged.
- **Online application:** not tested in fiscal 2022; no usable feature exists.

## Coding rule (fixed before computing)

1. The value for a jurisdiction is the **largest whole number of months printed** in its value under that heading, the rule amendment 1,
   section B, sets for the 14th edition. The notebook prints, before any association, every distinct printed text, the number of states with it
   and the value assigned. If the heading is not printed once per jurisdiction in a form this rule can read, **the test stops and the owner is
   asked**.
2. Coverage rule: all 51 jurisdictions must yield a value. If more than three do not, **the test stops and the owner is asked**; up to three
   missing are named and excluded.
3. A jurisdiction with no value under this heading is **not** coded zero.

## Caveat the owner should weigh

The heading is the certification period for **households with simplified reporting requirements**, a subset of cases, not the all-household
certification length the 14th edition's profile gives. The two measures are not the same variable. The fiscal 2022 result is therefore **not a
replication** of the fiscal 2019 certification-length result and is labelled a different measure. If the owner declines, this amendment is reverted
and the test is not run.

## Unchanged

The question, the estimators, the Holm family, the primary year (fiscal 2019, amendment 3), the replications, the EITC pairing and every
stop-rule.
