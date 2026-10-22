<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# C01 pre-analysis plan — Medicaid expansion and the uninsured rate

Written and committed **before any ACS table is retrieved for this notebook**. The notebook
binds to this file by its SHA-256; changing the file afterwards breaks the identification gate.

## 1. Question and estimand

What did the 2014 Medicaid expansion do to the share of adults aged 35–64 without health
insurance, in the states that expanded on 1 January 2014, compared with the states that never
expanded? The estimand is the **average treatment effect on the treated (ATT)** of expansion
on the state uninsured rate, averaged over 2014–2019, in percentage points.

## 2. Outcome and the departure from the track specification

**Primary outcome:** the uninsured rate of the civilian non-institutionalised population aged
35–64, from the ACS 1-year detail table **B27010**, as 100 × `B27010_050E` / `B27010_034E`,
state × year, 2010–2019 for the primary window and 2021–2023 for the extension.

The track specification names ages 19–64. That series does not exist on a consistent basis:
the ACS changed its age bands in 2017 (B27010 reads "18 to 34" through 2016 and "19 to 34" from
2017), and the S2701 row "19 to 64" exists only from 2018 (before that it reads "18 to 64").
The 35–64 band is the one adult band whose definition does not change in 2010–2023. It also
sits clear of the 2010 extension of dependent coverage to age 26, which moves the younger
adult band for reasons unrelated to Medicaid. The departure is recorded in `QUESTIONS.md` for
the owner and stated in the notebook's Limitations.

**Placebo outcome:** the uninsured rate aged 65 and over, 100 × `B27010_066E` / `B27010_051E`.
Medicare covers this group in every state, so expansion should not move it.

**Missing year:** the Census Bureau publishes no standard 2020 ACS 1-year release (the API
returns HTTP 404 for it; checked 2026-10-22). 2020 is absent from every series and is not
imputed.

## 3. Treatment, sample and exclusions

Treatment timing comes from `data/policy/medicaid/expansion_dates.csv` (KFF, digest in its
`SOURCES.md`). Units are the 50 states and the District of Columbia.

| Group | Rule | Count |
|---|---|---|
| Treated | `expansion_effective` = 2014-01-01 | 25 |
| Control | status "Not Adopted" at the table's date | 10 |
| Excluded, partial first year | effective dates inside 2014 but not 1 January | 2 |
| Excluded, later adopters | effective 2015 or later (handled in C03) | 14 |

The 2014 cohort is the only cohort with a full pre-period and a clean comparison against
never-adopters; it makes the design a single-timing difference-in-differences, so the
two-way fixed-effects regression has no staggered-timing problem. This is the choice the
Limitations section must name.

## 4. Estimators

1. **The 2×2.** Mean uninsured rate in 2010–2013 and in 2014–2019, for treated and control
   states, each state one observation; ATT = (treated post − treated pre) − (control post −
   control pre). This is also computed by hand on the group means in the notebook, and the
   regression result must agree with it within rounding.
2. **Two-way fixed effects:** `y_st = a_s + g_t + b · D_st + e_st`, 2010–2019, `D_st` = 1 for
   treated states from 2014. `b` is the ATT.
3. **Event study:** relative-year indicators −4 to +5 (2010–2019), reference year −1 (2013),
   state and year fixed effects.

No covariates. The identifying assumption is unconditional parallel trends. Sensitivity: the
same estimates weighted by each state's 2013 population aged 35–64 (`B27010_034E`); reported
beside the unweighted results, never in place of them.

## 5. Inference

Standard errors are clustered at the state (35 clusters). With fewer than 50 clusters the
notebook also reports the **wild-cluster bootstrap** confidence interval and p-value
(`krl_tutorials_data.methods.did.wild_cluster_bootstrap`; 9,999 draws; seed fixed in the
notebook and printed). The bootstrap interval is the one the decision rule reads.

## 6. Falsification tests (both must be stored in the notebook as `FALSIFICATION:` lines)

1. **Pre-trends.** The lead coefficients at relative years −4, −3 and −2 are jointly zero
   (cluster-robust Wald test; wild-bootstrap p-value reported beside it).
2. **Placebo outcome.** The ATT on the 65-and-over uninsured rate, same specification.

## 7. What counts as no effect, and what counts as credible

- **No effect:** the 95% wild-cluster bootstrap interval for the ATT contains zero.
- **Credible:** the joint lead test does not reject at the 10% level **and** the 95% interval
  for the placebo ATT contains zero. If either fails, the notebook says the design is not
  credibly identified for this outcome and reports the ATT as descriptive. It does not drop
  the failing test or change the window to rescue the result.
- **Expected sign, stated before the data:** negative (expansion lowers the uninsured rate).

## 8. Limitations the notebook must carry

The 2014-cohort choice and the exclusion of 16 states (two partial-year, fourteen later);
ACS 1-year margins of error enter as measurement error in the outcome and are not modelled;
some treated states broadened adult coverage before 2014, which would show in the lead
coefficients; the 35–64 band is not the track's 19–64; 2020 is missing. If the analysis departs
from this plan, the Limitations section says how and why.
