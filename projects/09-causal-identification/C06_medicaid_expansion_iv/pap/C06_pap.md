<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# C06 pre-analysis plan — Medicaid expansion as an instrument for coverage, and employment

Written and committed **before any PUMS table is retrieved for this notebook**. The notebook binds to
this file by its SHA-256; changing the file afterwards breaks the identification gate. The only look at
the data before this plan was a count of records and withheld cells for a candidate grouping on three
states in one year, with nothing tabulated by coverage or employment; it fixed the grouping below.

## 1. Question and estimand

For low-income adults, how much does Medicaid coverage change employment among the people whose coverage
changes because their state expanded Medicaid? The estimand is the **local average treatment effect (LATE)
on the employment rate of Medicaid coverage, for compliers**, in percentage points per percentage point of
coverage: the ratio of the reduced-form effect of expansion on employment to its first-stage effect on
coverage. It says nothing about people whose coverage does not respond to expansion.

## 2. Data and sample

ACS 1-year PUMS for 2012 to 2019 (eight vintages; the Census Bureau publishes no standard 2020 release),
through `fetch_acs_pums`, one state and one year per request, which returns **weighted cells and record
counts only**. No person row is read, printed or stored. Records are kept where `AGEP` is 19 to 64 and
`POVPIP` is 0 to 137 (income below 138% of the poverty level), and records with `ESR` 4 or 5 (armed
forces) are dropped and counted.

| Role | Variable | Definition |
|---|---|---|
| Endogenous treatment | `HINS4` | 1 = covered by Medicaid or a similar means-tested or disability programme |
| Outcome | `ESR` | employed = 1 or 2; not employed = 3 (unemployed) or 6 (not in labour force) |
| Cell demographics | `SEX`, `AGEP` | sex; age in three bands, 19–34, 35–49, 50–64 |

A cell is a **state × year × sex × age band**. Its coverage rate and employment rate are weighted shares
of its retained records, and its weight is its weighted population. A cell with fewer than **30 retained
records** (after the client's 10-record floor withholds small rows) is dropped and counted, with the share of
records it holds.

## 3. States, instrument and years

The states are those of C01's clean comparison, taken from `data/policy/medicaid/expansion_dates.csv`:
**treated** = expansion effective 1 January 2014 (25 states); **control** = status "Not Adopted" (10 states).
States that expanded at another time are excluded and counted. The instrument is
`Z = 1` for a treated state in a year from 2014 on, and 0 otherwise.

**Departure from the track specification, recorded before retrieval.** The track says "expansion state ×
post-expansion year", which for states with different dates would use staggered timing; C03 shows what that
does to a two-way fixed-effects regression. Restricting to the 2014 cohort and the never-adopters keeps the
timing single, so the instrument is a clean difference-in-differences contrast.

## 4. Estimators

1. **Grouped, weighted 2SLS (headline):** `methods.iv.tsls` of the cell employment rate on the cell coverage
   rate, instrumented by `Z`, with state, year and demographic-cell fixed effects as dummy controls, weights
   equal to the cell's weighted population, and standard errors clustered by state (35 clusters).
2. **First stage and reduced form,** stored beside the IV estimate: the coefficient of `Z` on coverage (its
   size is the **compliers' share**: the percentage-point rise in coverage that expansion causes) and on
   employment.
3. **OLS** of employment on coverage with the same controls, for contrast.
4. **Weights sensitivity:** the same IV with every cell weighted equally. Grouping and weighting change who
   the estimate is about; the notebook reports both estimates, their difference, and the share of the total
   weight carried by the five heaviest states.

Intervals use the t distribution with 34 degrees of freedom; with 35 clusters they are approximate, and the
notebook says so.

## 5. Checks (each stored as a `FALSIFICATION:` line)

1. **First-stage strength.** The cluster-robust F statistic for `Z` in the first stage.
   **PASS if F is at least 10.**
2. **Pre-period placebo on the reduced form.** The 2012 to 2013 cells only, with a placebo instrument that
   switches on in 2013 in the treated states, and the same fixed effects, weights and clustering. **PASS if the
   95% interval of the placebo reduced-form coefficient contains zero.**

## 6. What counts as no effect, and what counts as credible

- **No effect:** the 95% interval of the IV estimate contains zero.
- **Credible:** both checks pass. If either fails the notebook reports the IV number as descriptive. It does not
  change the sample, the cells or the controls to rescue it.
- **No sign is expected before the data.**

## 7. The exclusion restriction, stated as the argument it is

Identification needs expansion to affect employment only through Medicaid coverage. It cannot be tested, and
these routes threaten it: expansion may change employment by raising health (a route through coverage, which
the estimate is meant to include), by loosening "job lock" (also through coverage), by changing state labour
demand in health care, by coming with other state policy changes, by altering the reporting of coverage (people
who move from other coverage to Medicaid), or, in later years, through work requirements adopted by some states.
Only the first two are the effect of interest; the notebook names the others and says the estimate is an upper
bound on what the argument can support.

## 8. Limitations the notebook must carry

The LATE belongs to compliers in the treated states and to this window; the exclusion restriction is an
argument, not a test; the single timing excludes the 2015-and-later adopters; some treated states broadened
coverage before 2014; `HINS4` mixes Medicaid with other low-income and disability programmes and is
self-reported; withheld and dropped cells (their records are counted); cell grouping and population weights
change the estimand's weights, which the notebook measures; 35 clusters make the intervals approximate. If the
analysis departs from this plan, the Limitations section says how and why.
