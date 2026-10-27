<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# M01 pre-analysis plan — internal replication and random-effects pooling

Written and committed **before any ACS table is retrieved for this notebook**. The notebook binds
to this file by its SHA-256; changing the file afterwards breaks the identification gate.

## 1. Question and estimand

C01 estimated one average effect of the 2014 Medicaid expansion on the uninsured rate of adults
aged 35–64. M01 asks whether that average is a stable feature of the expansion states or the
sum of very different state results. It re-estimates C01's design **one expansion state at a
time** against the pool of never-expanded states, pools the 25 state estimates, and reports how
much they differ from one another beyond sampling error.

Estimand for each expansion state *s*: the change in its uninsured rate (ages 35–64, mean of
2014–2019 minus mean of 2010–2013) minus the mean change in the never-expanded states, in
percentage points. This is C01's 2×2 for a treated group of one state. The pooled estimand is the
**mean of the distribution of state effects** (random effects); the fixed-effect estimate is also
reported.

C01's own result is the reference: ATT −1.453 pp, wild-bootstrap 95% interval [−2.912, +0.006],
p = 0.051. It is borderline, and it moves with the seed and the number of draws. M01 reads it
from C01's stored output (no re-run) and prints the interval and status beside every use of the
estimate.

## 2. Data and sample

ACS 1-year detail table **B27010**, state × year, 2010–2019 (no 2020 release): the same table,
variables and age band as C01 — `B27010_034E` (total, ages 35–64), `B27010_050E` (no coverage,
35–64), `B27010_051E` (total, 65 and over), `B27010_066E` (no coverage, 65 and over) — and the
margin of error published for each (`…M`), which C01 did not retrieve. Treated and control states
are exactly C01's: 25 states with expansion effective 2014-01-01 and 10 with status "Not
Adopted", from `data/policy/medicaid/expansion_dates.csv` by C01's assignment rule; the 16
excluded states are excluded here. The 2021–2023 extension is not used.

## 3. State estimates and their standard errors

Each state-year rate is 100 × no coverage / total. Its standard error is derived from the
published margins of error (90% level, divided by 1.645) with the proportion formula in
`krl_tutorials_data.uncertainty`, and the years are treated as independent samples. The standard
error of a state estimate is the square root of the sum of: the variance of the state's
post-period mean (sum of yearly variances over 6², for 2014–2019), the variance of its
pre-period mean (over 4², for 2010–2013), and the variance of the control pool's mean change
(the same quantities for the 10 control states, divided by 10²). The control-pool term is **common
to every state estimate**, so the 25 estimates are positively correlated; the pooling treats them
as independent, and the pooled interval is too narrow for that reason (section 8).

The standard error is a **sampling** error. Differences between states that sampling error does
not explain appear as between-state variance (τ²), which is the finding of interest.

## 4. Pooling

`krl_tutorials_data.methods.meta`: inverse-variance fixed effect; DerSimonian–Laird random
effects; τ², Cochran's Q with its p-value, and I². Additionally, the 95% **prediction interval**
for the effect in a new state, mean ± t(k−2) × √(τ² + SE²), with k = 25. Egger's regression test
for small-study asymmetry (k = 25), a funnel plot, a forest plot of the 25 state estimates, and
the leave-one-out series (the pooled random effect with each state omitted), naming the state
whose omission moves the pooled estimate most.

Identity the notebook checks: the **unweighted mean of the 25 state estimates equals C01's
ATT** (−1.453 pp), because C01's panel is balanced with a single treatment date. A difference
larger than 0.001 pp is a failure, and the notebook says so.

## 5. Falsification tests (each stored as `FALSIFICATION:` lines)

1. **Placebo timing.** The same 25 state estimates, built on 2010–2011 against 2012–2013 (a
   post-period that predates the expansion), are pooled by random effects; the 95% interval of
   the pooled placebo effect must contain zero.
2. **Placebo outcome.** The same 25 state estimates for the uninsured rate of people aged 65
   and over, pooled by random effects; the 95% interval must contain zero.

Both use the same standard-error construction as the main estimates. A failure is a finding and
is reported, not repaired.

## 6. What counts as what

- **Pooled effect not distinguishable from zero:** the 95% random-effects interval contains
  zero. It is reported with the interval in percentage points, never as "no effect".
- **Heterogeneity is a finding** if Cochran's Q rejects at the 10% level (as C01's pre-trend
  threshold). The notebook then reports τ², I² and the prediction interval as the result, and
  does not treat the average as the effect in any particular state. If Q does not reject,
  it says the heterogeneity is not distinguishable from zero with 25 estimates, and gives τ²
  with the caveat that Q has low power.
- **Credible:** the pooled effect is read as identified only if both placebo intervals contain
  zero. Otherwise it is descriptive.
- **Expected sign, stated before the data:** negative.

## 7. Added analyses

None are pre-specified beyond sections 3–6. Any addition is labelled "not pre-specified (added
after review, <date>)" in its cell and in Limitations.

## 8. Limitations the notebook must carry

The state estimates share one control pool and are not independent; the pooled interval
understates uncertainty for that reason, and the notebook says by how much it cannot say. The
standard errors are sampling errors only. The DerSimonian–Laird τ² is imprecise with 25
estimates and the interval uses the normal quantile without a Hartung–Knapp adjustment. Several
treated states had broader adult coverage before 2014 and are contaminated comparisons
(listed in C01). Single-state estimates compare one state with ten controls and are noisy by
design. C01's own estimate is borderline. 2020 is missing. If the analysis departs from this
plan, the Limitations section says how and why.
