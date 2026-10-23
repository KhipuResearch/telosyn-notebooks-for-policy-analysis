<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# C02 pre-analysis plan — health insurance coverage at age 65

Written and committed **before any PUMS table is retrieved for this notebook**. The notebook
binds to this file by its SHA-256; changing the file afterwards breaks the identification gate.

## 1. Question and estimand

How much does the share of people with health insurance jump at age 65, the age at which
Medicare eligibility begins for most people? The estimand is the **jump in the survey-weighted
mean of the outcome at the age-65 threshold**, local to age 65, in percentage points:
`lim E[y | age → 65+] − lim E[y | age → 65−]`. Because the means are weighted, this is the
jump in the weighted mean, which is a different object from the unweighted one.

## 2. Data

ACS 2023 1-year PUMS, through `krl_tutorials_data.sources.fetch_acs_pums`, one call per state
for the 50 states and the District of Columbia (Puerto Rico excluded), person weight `PWGTP`.
The client returns **weighted cells only**; no person row is read, printed or stored, and the
notebook uses no other path to PUMS. Three aggregations are requested, chosen so that few cells
fall under the client's small-cell floor:

| Aggregation | Used for |
|---|---|
| `AGEP` × `HICOV` × `PRIVCOV` × `PUBCOV` | outcomes and the density check |
| `AGEP` × `SEX` | covariate continuity (share female) |
| `AGEP` × `SCHL` | covariate continuity (share with a bachelor's degree or higher, `SCHL` ≥ 21) |

Records in withheld small cells are reported in the notebook; the plan does not recode or
impute them. The sample is single years of age 55 to 75.

## 3. Running variable, treatment and outcomes

- **Running variable:** `AGEP`, age in completed years at the survey. The cutoff lies between 64
  and 65 (c = 64.5 on the `AGEP` scale); the treated side is `AGEP` ≥ 65. Because age is
  reported in whole years the running variable is **discrete**: the unit of observation is the
  single-year-of-age cell, weighted by that cell's weighted population.
- **Primary outcome:** `HICOV` = 1 (any health insurance coverage), as a percentage of the cell's
  weighted population.
- **Decomposition, reported in full beside the primary:** `PUBCOV` = 1 (public coverage) and
  `PRIVCOV` = 1 (private coverage). Both are shown whatever they show.
- **Expected signs, stated before the data:** any coverage up; public coverage up by much more;
  private coverage down.

## 4. Estimator

Local-linear weighted least squares of the cell outcome on a constant, the treated indicator,
the distance from the cutoff and their interaction, within a bandwidth, with a **triangular
kernel** multiplied by the cell weights (`krl_tutorials_data.methods.rdd.local_linear`).
Standard errors are HC1 over the age-cell observations. There is no data-driven bandwidth and
no bias correction (`rdrobust` is not adopted); the notebook says so.

A bandwidth of k whole years means ages 65−k to 64 and 65 to 64+k, which is `bandwidth` =
k − 0.5 on the `AGEP` scale around c = 64.5. **Headline: k = 5 (ages 60 to 69).** The sensitivity
grid is k = 3 to 10, reported for all three outcomes.

## 5. Falsification tests (each stored as a `FALSIFICATION:` line)

1. **Density.** The binomial test of equal counts either side of the cutoff within the headline
   window, on **unweighted record counts** by age. Age cannot be chosen, so manipulation is not
   the live threat, and with tens of thousands of records the p-value will be small whenever
   neighbouring birth cohorts differ in size. The stored statistic is therefore the right-hand
   share of record counts, and the verdict is **PASS if that share is within 0.03 of 0.5**; the
   binomial p-value is printed beside it.
2. **Placebo cutoffs.** The same estimator and bandwidth on the primary outcome at cutoffs
   between 59 and 60 and between 69 and 70, each using only the data on its side of 65. **PASS
   if the 95% interval (estimate ± 1.96 standard errors) contains zero.**
3. **Covariate continuity.** The same estimator at the headline bandwidth on the share female and
   the share with a bachelor's degree or higher. **PASS if each 95% interval contains zero.**

## 6. What counts as no effect, and what counts as credible

- **No effect:** the 95% interval for the primary outcome at the headline bandwidth contains zero.
- **Credible:** all three falsifications pass. If any fails, the notebook says so and reports the
  jump as descriptive; it does not drop the failing test or change the window to rescue it.

## 7. Limitations the notebook must carry

The effect is local to 65 and says nothing about other ages. Age is in whole years, so the
running variable is discrete and the data cannot be closer to the cutoff than one year; the
estimate pools people up to a year either side of their birthday. Survey weights change the
estimand to the weighted mean's jump. Coverage is measured at the survey date, and many people
at 65 already have coverage, so the jump in *any* coverage is smaller than the jump in public
coverage. Small cells are withheld by the client and their records are reported. If the analysis
departs from this plan, the Limitations section says how and why.
