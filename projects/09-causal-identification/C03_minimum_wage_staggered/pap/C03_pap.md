<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# C03 pre-analysis plan — state minimum-wage increases and food-service employment

Written and committed **before any QCEW table is retrieved for this notebook**. The notebook
binds to this file by its SHA-256; changing the file afterwards breaks the identification gate.

## 1. Question and estimand

What did the first move of a state's minimum wage above the federal minimum do to employment in
food services and drinking places (NAICS 722)? The estimand is the **average treatment effect on
the treated** over the first twelve quarters after adoption, as a log-point change in county
private-sector employment, averaged across adopting cohorts (weighted by the cohorts' county
counts). It is estimated three ways, side by side: the naive two-way fixed-effects regression, the
Goodman-Bacon decomposition of what that regression averages, and a heterogeneity-robust estimator.

## 2. Data, and two departures from the track specification

- **Outcome:** natural log of the mean of the three monthly employment levels in a quarter
  (`month1_emplvl`, `month2_emplvl`, `month3_emplvl`), private ownership (`own_code` 5), NAICS 722,
  county level (`agglvl_code` 75), from the QCEW industry slice through `fetch_qcew(industry="722")`,
  one request per quarter.
- **Window: 2014 Q1 to 2023 Q4 (40 quarters), not 2012 to 2023.** The BLS QCEW slice API serves
  2014 Q1 onward and returns HTTP 404 for earlier quarters (checked 2026-10-22). The bulk annual files
  that reach earlier would need a new fetcher; the plan does not build one.
- **Policy:** `data/policy/minimum_wage/state_schedule.csv` (DOL; January-1 values). The federal
  rate is 7.25 in every year of the window.
- **Both departures, and the county sample rule below, are recorded in `QUESTIONS.md` for the
  owner and stated in the notebook's Limitations.**

## 3. Treatment, groups and sample

- **Above federal:** a state's schedule value `rate_low` exceeds 7.25 on 1 January of a year.
  Territories are excluded; the unit set is the 50 states and the District of Columbia.
- **Treatment time:** the first quarter of the first year in which the state is above federal.
  The schedule records January-1 values only, so an increase made part-way through a year is dated
  to the following 1 January; the plan accepts that misclassification of up to two quarters and says
  so as a limitation.
- **Groups:** *treated throughout* (above federal in 2014; they have no pre-period); *adopters*
  (first above federal in 2015 to 2023); *never treated* (not above federal in any year to 2023).
  Group sizes are printed and must match the table.
- **County sample:** counties with a disclosed, positive employment value in all 40 quarters (a
  balanced panel, which the decomposition requires). Counties dropped for suppression or zeros are
  counted, and their share of the retained states' employment is printed. Suppression is not random
  (it is applied where few establishments make a cell identifying), so this is a limitation, not a
  nuisance.

## 4. Estimators

1. **Naive TWFE:** `ln(emp)_ct = a_c + g_t + b · D_ct`, `D` = 1 from the state's treatment quarter
   onward, all three groups, county and quarter fixed effects, standard errors clustered by state.
2. **Goodman-Bacon decomposition** of estimator 1 (`methods.did.bacon_decomposition`): the weights
   and estimates of the treated-versus-never, earlier-versus-later and later-versus-earlier
   comparisons. The "sign flip" statement is computed: whether the naive estimate and the
   robust estimate differ in sign, and how much weight falls on later-versus-earlier comparisons.
3. **Heterogeneity-robust (primary): Sun-Abraham** interaction-weighted estimator
   (`methods.did.sun_abraham`) on adopters and never-treated counties only (the treated-throughout
   states have no pre-period and are dropped), four leads (event times −4 and earlier binned), no
   binned post-period cells, cohort-by-event-time dummies, clustered by state.
   Callaway-Sant'Anna was considered; a package (`csdid`) exists on PyPI, but adopting it needs an
   architecture-record decision on a new dependency, so the estimator is implemented in the
   repository instead, as the track specification allows.
4. **The headline number** is the mean of the Sun-Abraham `ATT(e)` over event times 0 to 11
   (the first twelve quarters), with its standard error from the coefficient covariance.

## 5. Inference

State-clustered throughout (there are about 50 clusters). Sun-Abraham errors are the clustered
analytic ones. The group-time estimator used in the falsification below takes a cluster bootstrap
(999 draws, seed fixed in the notebook and printed).

## 6. Falsification tests (each stored as a `FALSIFICATION:` line)

1. **Pre-period coefficients.** The Sun-Abraham coefficients at event times −4, −3 and −2 are
   jointly zero (cluster-robust Wald, referred to F with the number of restrictions and states − 1
   degrees of freedom). **PASS if p ≥ 0.10.**
2. **Never-treated versus not-yet-treated.** The group-time estimator (`methods.did.group_time_att`,
   no covariates) run twice, with never-treated counties as the control and with never-treated plus
   not-yet-treated counties as the control, over event times 0 to 11. **PASS if the two overall
   estimates differ by no more than the larger of their two bootstrap standard errors.**

## 7. What counts as no effect, and what counts as credible

- **No effect:** the 95% interval for the headline Sun-Abraham estimate contains zero.
- **Credible:** both falsifications pass. If either fails, the notebook says so and reports the
  estimates as descriptive. It does not change the window, the sample or the outcome to rescue them.
- **No sign is expected before the data.** The plan states none; the notebook reports whichever
  sign the data show.

## 8. Limitations the notebook must carry

Suppressed county cells and the balanced-panel rule (coverage printed); the 2014 start (no pre-period
for states already above federal, and none before 2014 for anyone); January-1 dating of increases;
a binary treatment that ignores the size of the increase; spillovers across state borders at the
county level; the always-treated states are dropped from the robust estimate, so it speaks only to
adopters 2015 to 2023. If the analysis departs from this plan, the Limitations section says how and why.
