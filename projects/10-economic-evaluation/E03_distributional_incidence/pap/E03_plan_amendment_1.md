<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# E03 plan — amendment 1 (2026-10-27)

Committed **before any CBO file or CPS table is retrieved**, after `fetch_cps_asec` was built and
tested on constructed fixtures. It amends `E03_plan.md` (commit `f44a811`), which is not edited.
The notebook binds to **both** files by SHA-256.

## What changes

`E03_plan.md` section 3 fixed $1,000 income bins and section 7, check 3, a 1% bound on the
population share of the bin that holds each quintile boundary. Crossing income bins with race,
the reference person's age group and a child indicator at $1,000 would push many cells under the
small-cell floor (10 records, the repository's rule for any weighted cell), and withheld cells
leave the population, which biases every share. Written down now, before the data are seen:

| Setting | Plan | Amendment |
|---|---|---|
| Income bin width | $1,000 | **$2,500** |
| Bin at or above | (none) | **$150,000** (one bin; exact weighted income kept) |
| Bin below | (none) | **$0** (one bin labelled −$2,500; exact weighted income kept) |
| Small-cell floor | (not stated) | **10 records** |
| Boundary-bin population share, check 3 | below 1% | **below 5%**, printed per boundary |
| Withheld weight | (not stated) | **at most 1% of the weighted population**; if more, the notebook stops and the owner is asked, and no setting is changed to get under it |

The amendment does not change the estimands, the sources, the reconciliation or the other
checks. If check 3 fails (a boundary bin holds 5% or more), the notebook reports it and does not
rerun with other widths.

## What is unchanged

Everything in `E03_plan.md` not listed above, including the departure on replicate weights and
the lower-bound intervals.
