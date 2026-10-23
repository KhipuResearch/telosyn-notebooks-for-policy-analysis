<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# C05 pre-analysis plan — public coverage and employment, adjusting for what was measured

Written and committed **before any PUMS table is retrieved for this notebook**. The notebook binds
to this file by its SHA-256; changing the file afterwards breaks the identification gate. The only
look at the data before this plan was a count of records and withheld cells for a grouping on twelve
states, with nothing tabulated by treatment or outcome; it fixed the grouping below.

## 1. Question and estimand

Among adults aged 19 to 64 living below 200% of the federal poverty level, is having public health
coverage associated with a different probability of being employed, once people are compared with
others who share the same measured characteristics? The estimand is the **average effect on the
treated (ATT)** in percentage points: the difference between the employment rate of people with
public coverage and the rate their covariate cells would have had without it. It is identified only
if, within a covariate cell, whether someone has public coverage is unrelated to their employment
potential. That assumption cannot be tested; the plan measures how much hidden bias it could
survive.

## 2. Data, sample and what the client returns

ACS 2023 1-year PUMS through `fetch_acs_pums`, which returns **weighted cells and record counts
only**. No person row is read, printed or stored. The client is asked for records with `AGEP` 19 to
64 and `POVPIP` 0 to 199 (income below 200% of the poverty level), pooled across states before the
small-cell floor of 10 records is applied.

| Role | Variable | Definition |
|---|---|---|
| Treatment | `PUBCOV` | 1 = with public health coverage (Medicaid, Medicare, military health care and similar) |
| Outcome | `ESR` | employed = 1 (at work) or 2 (with a job, not at work); not employed = 3 (unemployed) or 6 (not in labour force). `ESR` 4 and 5 (armed forces) are dropped and counted |
| Negative-control outcome | `NATIVITY` | 2 = foreign born |
| Covariates | `AGEP` | nine bands of age: 19–24, 25–29, 30–34, ..., 60–64 |
| | `SEX` | as published |
| | `SCHL` | four bands: below high school (≤ 15), high school or equivalent (16–17), some college or associate (18–20), bachelor's or higher (21–24) |
| | `DIS` | disability recode as published |
| | `NP` | household size, five bands: 1, 2, 3, 4–5, 6 or more |
| | state's Medicaid expansion | expanded (effective on or before 2022-12-31), not expanded (status "Not Adopted"), from `data/policy/medicaid/expansion_dates.csv`; two states that expanded during 2023 are excluded and counted |

**Departure from the track specification, recorded before retrieval.** The track names the state
as a covariate. State is not in the cells: a grouping fine enough to hold age, sex, education,
disability and household size would leave most cells under the small-cell floor within a single
state (a probe on one mid-sized state withheld 60% of its records, and a small state lost all of
them). The pooled design instead carries the state's Medicaid expansion status, the state
difference most likely to separate public coverage from employment. State-level differences beyond
that are an unmeasured confounder, which the sensitivity analysis addresses. This is recorded in
`QUESTIONS.md` for the owner.

## 3. Estimators (each reported; the stratified estimate is the headline)

1. **Naive difference:** employment rate of the treated minus that of the untreated, unadjusted.
2. **Stratified ATT (headline):** within each full covariate cell, the treated employment rate minus
   the untreated rate, averaged with weights equal to the cell's treated count
   (`methods.matching.stratified_effect`), using **record counts**. Cells with no treated or no
   untreated record are dropped and the share of treated records that survives is printed. The
   standard error treats the cell weights as fixed.
3. **Inverse-probability weighting (ATT):** a main-effects logistic model of treatment on the
   covariate dummies, fitted on cell rows with the record count as the frequency weight
   (`methods.matching.logit_propensity`); untreated cells weighted by `p / (1 - p)`
   (`methods.matching.ipw_effect`, `estimand="att"`). Reported without trimming and, beside it,
   with propensities trimmed to [0.05, 0.95].
4. **Balance:** standardised mean differences of every covariate dummy before and after the IPW
   weights (`methods.matching.balance_table`), and the overlap of the propensity score (counts of
   records by score bin, treated and untreated).
5. **Population-weighted sensitivity:** the stratified and IPW estimates with each cell's weighted
   population in place of its record count. This changes the estimand to the population-weighted
   one and is shown beside, not in place of, the headline.

All inference counts **records**, not weighted people, and ignores the survey's complex design (the
client has no replicate weights); intervals are therefore narrower than a design-based analysis
would give, and the notebook says so.

## 4. Sensitivity to hidden bias

Rosenbaum bounds for a stratified binary outcome (`methods.matching.rosenbaum_bounds` and
`rosenbaum_critical_gamma`), strata = the full covariate cells, counts = records. The headline
sensitivity number is **Gamma, the smallest ratio by which an unmeasured factor would have to
multiply the odds of public coverage between two people in the same cell for the worst-case
one-sided p-value to exceed 0.025** (a two-sided 0.05). A table of the worst-case p-value at
Gamma = 1, 1.1, 1.2, 1.5, 2 and 3 is stored. The sentence "the estimate survives hidden bias up to
Gamma = x" is produced from the computed value, and if the estimate is not significant at
Gamma = 1 the notebook says it does not survive even that.

## 5. Falsification and balance checks (each stored as a `FALSIFICATION:` line)

1. **Negative-control outcome.** The stratified ATT on the share foreign born. Public coverage
   cannot change where a person was born; a non-zero adjusted difference measures confounding the
   covariates did not remove. **PASS if the 95% interval contains zero.**
2. **Balance after weighting.** The largest absolute standardised mean difference over the
   covariate dummies after IPW weighting. **PASS if it is at most 0.10.**

## 6. What counts as no effect, and what counts as credible

- **No effect:** the 95% interval of the stratified ATT on employment contains zero.
- **Credible:** both checks pass. If either fails, the notebook says so and reports the estimates as
  descriptive associations. It does not add covariates, change bands or drop cells to rescue them.
- Even when both pass, the claim is conditional on no unmeasured confounding; the Gamma above says how
  much of that assumption the conclusion can lose.
- **Expected sign, stated before the data:** none. Public coverage may raise or lower employment
  depending on the programme (work requirements, eligibility rules, disability coverage).

## 7. Limitations the notebook must carry

The assumption of no unmeasured confounding is untestable, and public coverage is plausibly chosen
and conferred on grounds that also bear on work (disability, caregiving, health, state rules); state
differences beyond expansion status are omitted; `PUBCOV` mixes programmes with different rules and
includes Medicare and military coverage; coverage and employment are measured at the same date, so
direction is not established; small cells are withheld and their records are reported; inference
ignores the survey design. If the analysis departs from this plan, the Limitations section says how
and why.
