<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# E03 plan — distributional incidence

Written and committed **before any CBO file or CPS table is retrieved for this notebook**. The
notebook binds to this file by its SHA-256; changing the file afterwards breaks the gate. A change
is made only by a new, dated amendment file committed on its own before the numbers it concerns
are computed.

## 1. Question and estimand

Who bears the federal tax system and who receives federal transfers, by income group, and who
would receive a stylised transfer? Three descriptive estimands, all for **income year 2023**:

1. **Incidence of taxes and transfers (CBO).** For each quintile of household income, CBO's
   average market income, transfers received, federal taxes paid, and income after transfers and
   taxes, and each quintile's share of the totals, read from CBO's supplemental table file.
2. **Incidence of a stylised transfer (CPS ASEC).** A transfer of **$1,000 per person aged under
   18, paid to that person's household**, costing the same wherever the child lives. Its incidence
   is the share of its total cost going to each (a) quintile of people ranked by household income
   adjusted for household size, (b) race and ethnicity group, (c) age group of the *recipient
   household's reference person*; and the transfer per person in each group. The transfer is
   defined for illustration; it is not a proposal and no take-up or behavioural response is
   modelled.
3. **Reconciliation.** How far the CPS income measure sits from CBO's, group by group.

Nothing here is causal and no policy effect is estimated.

## 2. Sources, by file (owner approval 2026-10-27)

| Source | File or endpoint | Size when listed |
|---|---|---|
| CBO, *The Distribution of Household Income, 2023* (publication 62761) | `https://www.cbo.gov/system/files/2026-09/62761-supp-data.xlsx` | 263,423 bytes |
| Census Bureau, CPS ASEC 2024 (income year 2023) | `https://api.census.gov/data/2024/cps/asec/mar` | API, existing key |

The owner also approved the CBO file `62761-data.xlsx`, the researcher zip, the table builder and
the report PDF. **They are not used**: the supplemental tables carry what the three estimands
need. A file is retrieved only if the notebook uses it.

## 3. Departures from the track specification

- **Replicate weights are not available.** The track specification says to carry sampling error
  with replicate weights where available. The CPS ASEC API serves no replicate weights (its 1,051
  variables include only `MARSUPWT`, `A_FNLWGT`, `HSUP_WGT`, `FSUP_WGT`, `SPM_WEIGHT` and
  `A_ERNLWT`; checked 2026-10-27). Sampling error is therefore reported as a **lower bound**: the
  standard error of a weighted share computed as if the sample were a simple random sample with
  Kish's effective sample size. The notebook labels every such interval a lower bound and does
  not describe any CPS difference as established on its basis.
- **Cells, not person rows.** Like PUMS (`fetch_acs_pums`), the new `fetch_cps_asec` returns
  weighted cells and no code path returns person rows. Because quintiles need a continuous income,
  household income adjusted for size is cut into **$1,000 bins** and the cell key is
  (income bin, race and ethnicity group, age group of the reference person, under-18 indicator).
  A person is assigned to a quintile by interpolating linearly inside the bin that holds the
  quintile boundary; the notebook prints, for each boundary, the share of the population in that
  bin, which bounds the misallocation. A library test with a known answer comes first.

## 4. Definitions

- **CBO income group:** CBO's quintiles of people ranked by household income adjusted for
  household size, as the supplemental table defines them. Which table and sheet is read is
  recorded by its title in the provenance record; if the file does not hold average market
  income, transfers and federal taxes by quintile for 2023, the notebook stops and the owner is
  asked, and no other table is substituted.
- **CPS household income adjusted for size:** `HTOTVAL` / sqrt(`H_NUMPER`), CBO's own
  adjustment. Quintiles rank people by this, weighted by `MARSUPWT`. Negative values are kept.
- **Race and ethnicity:** Hispanic (any race) from `PEHSPNON`; non-Hispanic by `PRDTRACE`:
  White alone, Black alone, Asian alone, all other non-Hispanic (including American Indian and
  Alaska Native alone, Pacific Islander alone and two or more races), combined because the
  separate groups are too small for the CPS to estimate. Five groups, mutually exclusive.
- **Age groups of the reference person:** under 35, 35–64, 65 and over.
- **Child:** `A_AGE` below 18. The transfer is paid per child; recipients are the children, and
  group shares are shares of children.

## 5. Estimators

- CBO: each quintile's value as printed in the file; shares are the quintile's value divided by
  the sum across the five quintiles, computed in the notebook. No smoothing, no interpolation.
- CPS: weighted means and shares with `MARSUPWT`; share of the stylised transfer to a group =
  weighted children in the group / weighted children in all groups, each with the Kish lower-bound
  95% interval. Transfer per person in a group = $1,000 × (weighted children / weighted people).
- Expected direction, stated before the data: the bottom quintile's share of the stylised transfer
  exceeds 20% and the top quintile's is below 20%; CBO's average transfers fall and average federal
  taxes rise with income.

## 6. Reconciliation of the two income concepts

CBO's measure is market income plus social insurance and employer contributions, retained
earnings and in-kind transfers valued at government cost; the CPS ASEC `HTOTVAL` is pre-tax
money income. The notebook prints a table of the differences in coverage and, for each quintile,
the ratio of CPS mean income-adjusted-for-size to CBO's average income before transfers and
taxes where the CBO file gives an equivalent. The quintile means are compared as printed, in
dollars, and the ratio is described, not corrected. The notebook does not rescale either source.

## 7. Falsification and known-answer checks (stored as `FALSIFICATION:` lines)

1. **Shares add up.** The five quintile shares of the stylised transfer sum to 100% within
   0.001 percentage points; the five race shares and three age shares likewise.
2. **Weighted population.** The sum of `MARSUPWT` over the cells equals the sum over the raw
   response held in the client before binning (the client raises if not). The notebook prints the
   weighted resident population and the weighted number of children; no external benchmark is
   retrieved for this notebook.
3. **Bin error bound.** For each quintile boundary, the bin's population share is below 1%; if
   not, the bin width is halved and the run repeated, and the notebook says so.
4. **Direction.** The expected direction in section 5 holds; if it does not, the notebook
   reports it as an unexpected finding and does not reinterpret the transfer.

## 8. What counts as what

- A difference between two CPS groups is **not distinguishable from zero** when the Kish
  lower-bound interval of the difference contains zero; because that interval is a lower bound on
  the true interval, a difference that is distinguishable under it is called "suggested by the
  sample", never "established". Nulls are stated with the interval in dollars per person.
- Any added analysis is labelled "not pre-specified (added after review, <date>)" in the cell and
  in Limitations.

## 9. Limitations the notebook must carry

CBO and CPS income concepts differ and are reconciled but not harmonised (section 6); the CPS
sampling error is a lower bound without replicate weights; CPS reports money income with known
under-reporting at both ends of the distribution; the stylised transfer ignores take-up,
phase-outs, taxation and behaviour; the five race groups pool small populations; income year
2023 only; the $1,000 binning (section 3). If the analysis departs from this plan, the
Limitations section says how and why, and the pre-analysis plan's digest is bound into every
provenance record.
