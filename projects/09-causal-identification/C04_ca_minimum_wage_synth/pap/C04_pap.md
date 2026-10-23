<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# C04 pre-analysis plan — California SB 3 and leisure-and-hospitality employment

Written and committed **before any observation of any outcome series is retrieved for this
notebook**. The notebook binds to this file by its SHA-256; changing the file afterwards breaks the
identification gate. Before this plan the only FRED requests were to the `series` endpoint, which
returns a series' title, units, seasonal adjustment and coverage, never its observations, to confirm the
identifiers below exist.

## 1. Question and estimand

Did California's leisure-and-hospitality employment, from the first scheduled increase under SB 3
(chaptered 4 April 2016; **intervention date 1 January 2017**, to $10.50 for employers with 26 or more
employees), diverge from what a weighted average of states with no scheduled increase would have shown?
The estimand is the **average gap between California and its synthetic control over 2017-01 to 2019-12**,
in thousands of jobs and as a percentage of the synthetic series. It is the effect of the schedule's start,
not of one wage level. The window stops before the pandemic discontinuity; that is a scope choice.

## 2. Series (identifiers verified against FRED's `series` endpoint on 2026-10-23)

- **Outcome:** `CALEIH`, *All Employees: Leisure and Hospitality in California*, thousands of persons,
  seasonally adjusted, monthly, coverage 1990-01 to 2026-09.
- **Donor outcomes:** `<ST>LEIH` for each donor state below, same units and adjustment; all 51 state
  series exist and carry the same coverage.
- **Covariates:** `<ST>UR` (unemployment rate, per cent, seasonally adjusted) and `<ST>NA` (total nonfarm
  employment, thousands, seasonally adjusted) for California and every donor, which exist.
- Window requested: 2010-01-01 to 2019-12-01. The current (revised) series is used; FRED revises, so
  the retrieval is the vintage and the notebook says so.

## 3. Donor pool, fixed here from the wage schedule

A state is a donor if its effective minimum wage (the larger of its schedule value `rate_low` and the
federal $7.25, with "no state minimum" treated as the federal rate) is the **same on 1 January of every
year from 2015 to 2020**. 2015 is included so that an increase on 1 January 2016 shows, and 2020 so that an
increase during 2019, which the January-1 schedule dates to the next 1 January, is excluded rather than
missed. The District of Columbia and the territories are not donors; California is the treated unit.
The rule applied to `data/policy/minimum_wage/state_schedule.csv` gives **21 donors**:

Alabama (AL), Georgia (GA), Idaho (ID), Indiana (IN), Iowa (IA), Kansas (KS), Kentucky (KY), Louisiana
(LA), Mississippi (MS), New Hampshire (NH), North Carolina (NC), North Dakota (ND), Oklahoma (OK),
Pennsylvania (PA), South Carolina (SC), Tennessee (TN), Texas (TX), Utah (UT), Virginia (VA), Wisconsin
(WI), Wyoming (WY).

The notebook recomputes the list from the table and stops if it differs from this one.

## 4. Periods and predictors

- **Pre-period:** 2010-01 to 2016-12 (84 months). **Post-period:** 2017-01 to 2019-12 (36 months).
- **Predictors:** the 84 pre-period monthly outcomes, plus two covariates, each the pre-period mean:
  the unemployment rate, and the leisure-and-hospitality share of total nonfarm employment
  (100 × `<ST>LEIH` / `<ST>NA`). Each covariate is standardised across California and the donors (z-score)
  and then multiplied by 5% of California's pre-period mean outcome, so a one-standard-deviation covariate
  gap counts like a 5% gap in employment; each covariate row has weight 10 against 1 for each monthly outcome.

## 5. Estimators

1. **Headline:** `methods.synth.synthetic_control` with the predictors above; the weights table; the
   gap series; the mean post-period gap in thousands and in per cent.
2. **Sensitivity, beside the headline:** the same with pre-period outcomes only (no covariates); and
   the gap range when each donor with non-zero weight is dropped in turn (leave-one-out).

## 6. Inference

Permutation, not asymptotic: `methods.synth.placebo_in_space` treats each donor as the treated unit in
turn with the same predictors and covariate settings, and reports the rank of California's post/pre RMSPE
ratio (rank 1 is the largest) and `p = rank / (placebos + 1)`. With 21 donors the smallest possible p is
1/22. A second distribution drops placebos whose pre-period RMSPE exceeds 5 times California's. The
p-value is valid only for this donor pool.

## 7. Falsification and fit checks (each stored as a `FALSIFICATION:` line)

1. **Pre-period fit.** California's pre-period RMSPE as a percentage of its pre-period mean employment.
   **PASS if at most 3.0%.**
2. **In-time placebo at 2014-01.** Weights fitted on 2010-01 to 2013-12 only, covariates recomputed over
   those 48 months, and the gap scored over 2014-01 to 2016-12, where no increase took effect. The statistic
   is that placebo's post/pre RMSPE ratio. **PASS if it is at most the 90th percentile of the in-space
   placebo ratios.**
3. **Permutation test.** The in-space p-value. **PASS if p is at most 0.10**; a FAIL here means no
   effect distinguishable from the placebo distribution, which is a finding about the effect, not about
   the design.

## 8. What counts as no effect, and what counts as credible

- **Effect detected:** the permutation p-value is at most 0.10. Otherwise the notebook says no effect was
  detected and does not describe the gap as an effect.
- **Credible design:** checks 1 and 2 pass. If either fails the notebook reports the gap as descriptive. It
  does not change the pool, the predictors or the window after seeing the result.
- **No sign is expected before the data.**

## 9. Limitations the notebook must carry

Permutation inference depends on the donor pool and has coarse resolution with 21 donors; California is
large and may lie outside the convex hull of the donors; SB 3 was chaptered in April 2016, so anticipation
in the last months of the pre-period is possible and the pre-period fit does not test for it; the 2017 step is
the first of several scheduled increases; the series are revised and seasonally adjusted; donors may have
had other policy changes (local minimum wages) that the state-level schedule does not show. If the analysis
departs from this plan, the Limitations section says how and why.

## Amendment of 2026-10-23 — fit on indexed series (made before any gap or effect was computed)

**What went wrong.** Section 4 fits the pre-period monthly outcomes in levels. A check of the pre-period
months alone, run when the first execution of the notebook stopped, showed that California's
leisure-and-hospitality employment is larger than that of **every** donor in **all 84** pre-period months
(California's pre-period mean is about 1,685 thousand; the largest donor's is about 1,142 thousand). A weighted
average with non-negative weights summing to one can never exceed its largest component, so no synthetic control
in levels can match California, and the placebo fits for small donors were degenerate with covariates scaled to
California's level. The 84 pre-period months of the 22 outcome series had been read for that check and for
debugging; no post-period value had been used, and no gap, effect or placebo ratio had been computed or seen.

**What changes.** In every fit, the real one and each placebo:
- each outcome series is expressed as an index, 100 × value ÷ the unit's own mean over 2010-01 to 2016-12;
- each covariate is standardised across California and the donors and then multiplied by **5 index points**
  (the same one-standard-deviation-counts-like-a-5%-gap rule, now in the units of the index), with weight 10
  per covariate row against 1 per monthly row;
- California's gap is reported in index points and converted to thousands of jobs with California's
  pre-period mean; the percentage gap is the gap over the synthetic index.

For the in-time placebo, the index base is the mean over 2010-01 to 2013-12 (the months used in that fit), so
that no later month enters the weights.

**What does not change.** The outcome, the donor pool, the windows, the covariates, the estimators, the
placebo designs, the checks, the thresholds (pre-period fit as a percentage of the pre-period mean is the
RMSPE in index points; the limit stays 3.0) and the decision rule. The notebook states this amendment in its
Limitations.
