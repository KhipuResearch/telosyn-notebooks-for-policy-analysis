<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# Q01 pre-analysis plan — subgroup effects and multiple comparisons

Written and committed **before any ACS table is retrieved for this notebook**. The notebook binds
to this file by its SHA-256; changing the file afterwards breaks the identification gate.

## 1. Question and estimand

C01 estimated one average effect of the 2014 Medicaid expansion on the uninsured rate of adults
aged 35–64. Q01 runs **the same design** separately in seven subgroups and asks how many of the
seven subgroup effects remain distinguishable from zero once the number of tests is accounted
for. The estimand for each subgroup is the **ATT in percentage points**, averaged over 2014–2019,
of expansion on that subgroup's state uninsured rate, for the states that expanded on 1 January
2014 against the states that never expanded.

C01's own result is the reference, not a member of the family: ATT −1.453 pp, wild-bootstrap
95% interval [−2.912, +0.006], p = 0.051. It is borderline, and it moves with the seed and the
number of bootstrap draws; Q01 prints that interval and status beside every use of it, and reads
it from C01's stored output rather than re-running C01.

## 2. Departure from the track specification

The track specification names the ACS subject table S2701 for the subgroups. S2701 cannot supply
a consistent series for the C01 window. It has no 2010 release through the API; the meaning of
its percentage columns differs between the early and later vintages (the 2014 vintage's
percentage column is labelled "Percent Insured"); and its age rows are re-cut in 2017. The notebook instead
uses the ACS 1-year **detail tables**, which are consistent and count people:

| Subgroup | Table | Rows used |
|---|---|---|
| Black or African American alone | B27001B | ages 35–44, 45–54, 55–64: total and no coverage |
| Asian alone | B27001D | same |
| White alone, not Hispanic or Latino | B27001H | same |
| Hispanic or Latino (any race) | B27001I | same |
| Age 35–44, 45–54, 55–64 (all races) | B27001 | each band, males plus females: total and no coverage |

The race iterations do not split by sex; the all-race table does, and the two sexes are summed.
The rows for ages 35–44, 45–54 and 55–64 carry the same label in every vintage 2010–2019 and
2021–2023 (checked by label on 2026-10-27, and re-checked by the notebook for each year it
retrieves). The subgroup family is therefore race and ethnicity and age band within the C01
age range, not the broader age bands of the specification. The departure is stated in the
notebook's Limitations and recorded for the owner.

## 3. The family of tests

Seven subgroups: the four race and ethnicity groups and the three age bands in the table above.
Not in the family, and why: American Indian and Alaska Native alone, Native Hawaiian and Pacific
Islander alone, some other race alone and two or more races (state samples too small to
estimate an effect); White alone including Hispanic (it overlaps two included groups); sex and
income (not in the specification).

The seven are not independent: a person belongs to one race group and one age band, and the
Black and Asian groups include Hispanic people. Holm's procedure holds under any dependence;
Benjamini–Hochberg assumes independence or positive dependence, and the notebook says so.

## 4. Sample and the rule for a thin subgroup

Treated and control states are exactly C01's: 25 states with expansion effective 2014-01-01,
10 states with status "Not Adopted", read from `data/policy/medicaid/expansion_dates.csv` with
C01's assignment rule. The 16 excluded states are excluded here.

A state enters a subgroup's panel only if its subgroup population aged 35–64 (the sum of the band
totals; the band total for an age subgroup) is at least **1,000 persons in every year 2010–2019**
and no cell it needs is missing. A subgroup is estimable only if at least **5 treated and at
least 5 control states** remain. A subgroup that is not estimable is reported as such and is
counted in the family with p = 1, which can only make the correction more conservative. The
number of states dropped is printed for every subgroup. No threshold is changed after the data
are seen.

## 5. Outcome, estimator and inference

Outcome: 100 × (persons with no health insurance coverage) / (total persons), by state and year,
2010–2019. Estimator: two-way fixed effects exactly as in C01 (`y_st = a_s + g_t + b·D_st + e_st`,
`D_st` = 1 for treated states from 2014; unweighted; no covariates), via
`krl_tutorials_data.methods.did`. Inference: the 95% wild-cluster bootstrap interval and p-value,
state clusters, 9,999 draws, seed 20261022 (C01's). The cluster-robust standard error is
reported beside it and is used for the power calculation.

## 6. Multiple comparisons

The seven two-sided bootstrap p-values form one family. The notebook applies
`uncertainty.holm_bonferroni` (family-wise error) and `uncertainty.benjamini_hochberg` (false
discovery rate), each at **alpha = 0.05**, and prints: the number of subgroup effects with an
uncorrected p below 0.05, the number remaining after Holm, the number remaining after BH, and
which subgroups they are. An effect is called distinguishable from zero after correction only
if it survives the stated procedure.

## 7. Power

For each estimable subgroup the notebook prints the **minimum detectable effect at 80% power**
(2.8016 × the cluster-robust standard error, for a two-sided 5% test) and the **power to detect
an effect equal to C01's all-adult ATT** (−1.453 pp). The Limitations section states these as
the achieved power of the test, in the units of the outcome.

## 8. Falsification tests (each stored as `FALSIFICATION:` lines)

1. **Reproduction.** The all-adult 35–64 series built from table B27001 (the three age bands,
   both sexes) gives the same ATT as C01's stored −1.453 pp. A difference larger than 0.001 pp
   is a failure: the subgroup pipeline would not be measuring C01's quantity.
2. **Pre-trends, per subgroup.** The event-study lead coefficients at relative years −4, −3 and −2
   are jointly zero (cluster-robust Wald test), pass at the 10% level, as in C01.
3. **Placebo outcome, per race group and for all races.** The ATT on the uninsured rate of
   people aged 65 and over (bands 65–74 and 75 and over), same specification; the 95%
   wild-bootstrap interval must contain zero. This applies to the race groups and the
   all-race series, not to the age-band subgroups, which lie inside 35–64.

## 9. What counts as what

- **Not distinguishable from zero:** a subgroup's 95% wild-bootstrap interval contains zero.
  The result is reported with the interval in percentage points, never as "no effect".
- **Credible:** a subgroup effect is read as identified only if its pre-trend test passes and
  (for a race group) its placebo interval contains zero. A failing subgroup is reported as
  descriptive, and still counts in the family.
- **Expected sign, stated before the data:** negative in every subgroup.
- **Not a test of differences between subgroups.** A subgroup that survives correction and one
  that does not are not thereby different from each other; the notebook says so and does not test
  equality across subgroups, which this plan does not pre-specify.

## 10. Limitations the notebook must carry

The departure from the S2701 specification (section 2); the borderline status of C01's own
estimate, which every subgroup inherits; thin state subgroups, the drop rule and the achieved
power (sections 4 and 7); overlapping subgroups and the dependence assumption of BH; state-level
ACS margins of error enter the outcome as noise and are not modelled; the 2014-cohort design and
its contaminated groups carry over from C01; 2020 is missing. If the analysis departs from this
plan, the Limitations section says how and why, and any added analysis is labelled "not
pre-specified (added after review, <date>)".
