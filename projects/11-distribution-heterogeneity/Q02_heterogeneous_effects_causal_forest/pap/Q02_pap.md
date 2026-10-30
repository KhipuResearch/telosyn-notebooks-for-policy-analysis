<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# Q02 pre-analysis plan — does the association of public coverage with employment vary across people? A causal forest on weighted cells

Written and committed **before any PUMS table is retrieved for this notebook**. The notebook binds to this file by its SHA-256 (`krl.pap`); a
committed plan is never edited, and a change is a new amendment file.

## 1. Question, estimand and what this is built on

Q02 asks how the adjusted difference in employment between adults with and without public coverage varies with the measured characteristics C05
conditions on. It uses **the same population, treatment, outcome and covariates as C05** (ACS 2023 1-year PUMS, adults aged 19 to 64 below 200% of the
poverty level, pooled across states; `PUBCOV`; `ESR`; age band, sex, education band, disability, household size band, state Medicaid expansion
status). The estimand is the **conditional average effect on employment, in percentage points, given the covariate cell**, `CATE(x)`, and its
average over the treated records (the same weights as C05's headline), which Q02 compares with C05's stratified ATT.

**This inherits C05's identification and C05's result for it.** C05's stratified ATT is about −21.7 pp, and its negative-control check (the same
adjustment applied to the share foreign born) did not pass, so C05 reports its estimate as a descriptive association. Q02 states this before it
looks at the data: whatever `CATE(x)` the forest returns is a description of how the adjusted association varies across cells, and is a
heterogeneous *causal* effect only if the negative control in section 6 passes in Q02's own estimate, which C05's did not. Any heterogeneity found
is **exploratory** except the contrasts declared in section 5.

## 2. Data: cells only, the same request as C05

`fetch_acs_pums` returns weighted cells and record counts only. **No person row is read, printed, stored or reconstructed anywhere in Q02**, and no
step expands a cell into repeated rows. The request is C05's, unchanged: year 2023, `AGEP` 19 to 64 and `POVPIP` 0 to 199, the same 49 states in
the same two groups (39 expanded, 10 not expanded; two states that expanded during 2023 excluded and counted), the same bands (`AGEP`
19-24, 25-29, ..., 60-64; `SCHL` four bands; `NP` five bands; `ESR` banded to the employment codes), the same small-cell floor of 10 records
applied after pooling, and the same grouping columns. The notebook compares the digest of the rows it receives with the digest stored in
C05's provenance record for the same request (`c05_pums2023_expanded.json`, `c05_pums2023_not_expanded.json`). **If they differ, Census has changed
the file and the notebook stops and asks the owner.** Withheld cells (fewer than 10 records) are reported as C05 reports them and are not imputed.

## 3. The unit is the covariate cell and treatment arm (owner decision, 2026-10-30)

Because the data are cells, the forest's unit cannot be a person. The unit is **one row per covariate cell and treatment arm**: the covariate cell is
the key (age band, sex, education band, disability, household size band, expansion status), the arm is `treated = (PUBCOV == 1)`, the outcome is
the arm's **employment rate** in that cell, and the weight is the arm's **record count** (the construction C05 uses in its cell table). Cells with
only one arm present are dropped and the share of treated records they hold is printed, as in C05.

What this changes, stated plainly:

- The forest's honest splitting, subsampling and bootstrap of little bags operate over these units, which hold from a handful to thousands of
  records each. They do not operate over people. **Honesty and the intervals are therefore at the cell level**: they say how stable the estimate is
  to resampling cells, not to resampling people, and they are not the person-level intervals the causal-forest literature reports.
- Both arms of a covariate cell are kept together when the nuisance models are cross-fitted (the `groups` argument of `fit`, which governs the
  cross-fitting folds), so a cell's own outcome never trains the nuisance prediction used for that cell.
- Inference ignores the survey design, as C05's does (the client returns no replicate weights), and treats the records as the sample.

## 4. Estimator

`econml` `CausalForestDML` (verified for the version used: the constructor takes `honest`, `n_estimators`, `min_samples_leaf`, `max_samples`,
`subforest_size`, `inference` and `random_state`; `fit(Y, T, X=..., sample_weight=..., groups=...)` is supported; `effect`, `effect_interval`
and `ate_interval` exist). Fixed before the data:

| Setting | Value |
|---|---|
| Treatment | binary (`discrete_treatment=True`) |
| Nuisance models | scikit-learn random forests (outcome: regressor; treatment: classifier), 200 trees, `min_samples_leaf` 10, fitted with the record counts as sample weights, cross-fitted over 5 group folds (`GroupKFold`) that keep a covariate cell's two arms together |
| Forest | `n_estimators` 2000, `subforest_size` 4, `honest=True`, `min_samples_leaf` 5, `max_samples` 0.45 (the library defaults for those two), inference on |
| Covariates `X` | the six cell columns, entered as numeric codes of their bands (age band, education band, household size band, sex, disability, expansion), so no covariate is split into dummies |
| Seed | 20261030 for the forest, the nuisance models and the fold assignment; every printed number reproduces under it |

The record counts act as `sample_weight` throughout. Sensitivity to the forest's size is reported by refitting with `min_samples_leaf` 20 and 50;
the primary setting does not change.

## 5. What is pre-specified and what is exploratory

**Pre-specified (the whole family of four tests, Holm-corrected at 0.05):**

1. **Heterogeneity exists in the cross-fitted forecast.** The calibration regression below, coefficient on the heterogeneity forecast.
2. **Three subgroup contrasts**, declared in advance because they are the splits C05's plan names as the state differences and health conditions
   most likely to matter: expansion status (expanded versus not), sex (male versus female) and disability (with versus without). For each, Q02
   reports the difference between the subgroups' stratified ATTs (`methods.matching.stratified_effect`, record counts, with its standard error)
   beside the forest's treated-record-weighted mean `CATE` for each subgroup. The stratified difference is the pre-specified test; the forest
   mean is the description.

**Exploratory (labelled in the cell, outside the family):** `CATE` by every other covariate and by pairs of covariates, the forest's variable
importances, the most and least favourable cells, and the sensitivity refits. Nothing exploratory is reported as a finding, and no covariate is
added, no band changed and no cell dropped after the first fit.

**Calibration test (Chernozhukov, Demirer, Duflo and Fernandez-Val's best linear predictor).** Each unit's `CATE` is predicted by the forest
trained on the other four folds (folds over covariate cells). The notebook regresses the outcome minus its cross-fitted prediction on
`(T - e)` times the mean predicted `CATE` and on `(T - e)` times the predicted `CATE` minus its mean (weighted least squares, record-count
weights, standard errors clustered by covariate cell), where `e` is the cross-fitted treatment propensity. The first coefficient says whether the
mean is calibrated; **the second says whether the forest has found real heterogeneity: it is "found" if its 95% interval lies above zero.** Both
are printed with the intervals, and the second is the first member of the family above.

## 6. Falsification and checks (each stored as a `FALSIFICATION:` line)

1. **Data identity.** The digest of the cells equals C05's stored digest for the same request. PASS if equal.
2. **Negative-control outcome.** The forest's average effect on the share foreign born (same covariates, same weights) with its cell-level 95%
   interval. PASS if the interval contains zero. C05's stratified version did not pass (about −5.0 pp); Q02 expects the same and says so, and
   reports the heterogeneity as descriptive if it fails.
3. **Agreement with C05.** The treated-record-weighted mean `CATE` against C05's stratified ATT (−21.67 pp). Reported as a difference; PASS if
   within 3 percentage points. A larger gap is reported and not explained away.
4. **Overlap.** The share of treated records in cells with both arms, and the range of the cross-fitted propensity. Stop and ask if the share
   of treated records kept is below 90% (C05: 95.7%) or the cross-fitted propensity has no variation within 0.05 of a constant.

## 7. What counts as no heterogeneity, and what counts as credible

- **No heterogeneity found:** the calibration coefficient on the heterogeneity forecast has a 95% interval that contains zero. The notebook then
  states that the forest found no heterogeneity it could calibrate **with the power it had**, prints the smallest heterogeneity coefficient the
  design could detect with 80% power, and does not read the null as "no variation".
- **Credible as heterogeneous effects:** the negative control passes, the calibration coefficient interval is above zero, and the pre-specified
  contrasts survive Holm. If the negative control fails, as C05's did, everything is reported as a description of how an adjusted association
  varies, and the title and Takeaways say so.
- **Expected direction, stated before the data:** none. Disability and programme rules could push the association either way.

## 8. What Q02 does not claim, and the software

- It does not estimate a person-level `CATE`, a person-level interval, or any effect for an individual. The unit is a cell and an arm.
- Discovered heterogeneity is exploratory unless it is in section 5. The most favourable cell in a forest is selected by the forest.
- `econml` is installed only through its own optional extra, never as a core dependency; no library test requires it; the library keeps the
  calibration regression and the cell-table construction in functions that import neither `econml` nor anything else beyond the existing
  dependencies, and the notebook alone imports `econml`. A decision record for the dependency (ADR) and a before-and-after measure of CI time
  accompany the notebook, and if the total CI increase would exceed 5 minutes the work stops and the owner is asked.

## 9. Limitations the notebook must carry

C05's identification assumption (no unmeasured confounding within a covariate cell) and its failed negative control; cell-level, not person-level,
honesty and intervals; inference that ignores the survey design; `PUBCOV` mixing programmes with different rules; coverage and employment measured
at the same date; small cells withheld and their records reported; the forest's discovered heterogeneity being exploratory beyond section 5; and
the dependence of any single cell's `CATE` on the forest's settings (the sensitivity refits). If the analysis departs from this plan, the
Limitations section says how and why, and a departure that moves the primary result is a new amendment, committed before the result it changes is
computed.
