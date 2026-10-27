<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# E03 plan — amendment 2 (2026-10-27)

Committed **before any incidence, share, quintile or group result is computed**. It amends
`E03_plan_amendment_1.md` (commit `dbf5ce3`), which is not edited, and does not touch `E03_plan.md`.

## What happened

Amendment 1 fixed a stop-rule: if the small-cell floor withholds more than 1% of the weighted
population, the notebook stops and the owner is asked, and no setting is changed to get under it.
The first and only CPS ASEC 2024 retrieval (144,265 person records, 1,242 cells kept) withheld 444
cells holding 1,909 records and 4,531,099 weighted people: **1.36%** of the weighted population. The
notebook stopped; no setting was changed. Before this amendment the only figures seen from the
retrieval were the total weighted population (327.9 million), the weighted number of children
(69.5 million) and the five race-group population shares. No quintile, share, transfer or
incidence figure had been computed.

## Owner ruling (2026-10-27)

Accept the 1.36% withheld weight. The bound in amendment 1 moves from 1% to **2%**; every other
setting in amendments 1 stays: $2,500 bins, $150,000 and $0 tails, a floor of 10 records, the
5% bound on a boundary bin's population share.

## What the notebook must do with it

- Print the withheld cells, records and weighted people, and the withheld share of the weighted
  population (withheld / (kept + withheld)), from the retrieval's own record.
- **Bound every CPS share by the withheld weight.** For a share *p* of a total *T* with withheld
  weight *W* that could belong to any group, the share lies between *p_kept × T / (T + W)* and
  *(p_kept × T + W) / (T + W)*. Print this interval beside each CPS share, as a separate column
  from the sampling interval, and say that it is a bound that assumes nothing about where the
  withheld people are.
- State in Limitations that withheld cells are thin cells (few records), so they are concentrated
  in the tails of the income distribution and in small race and age groups, and that the shares are
  therefore least certain exactly there.
- A difference between two groups is called "suggested by the sample" only if the sampling lower
  bound excludes zero **and** the difference between the two groups' bounds under the withheld
  weight keeps its sign at both ends; otherwise "not distinguishable from zero at the precision of
  this data", with the bounds in percentage points.

## Unchanged

Everything else in `E03_plan.md` and `E03_plan_amendment_1.md`.
