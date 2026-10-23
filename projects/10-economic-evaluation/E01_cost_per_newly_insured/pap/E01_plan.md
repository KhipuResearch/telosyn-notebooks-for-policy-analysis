<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# E01 plan — the cost of Medicaid expansion per newly insured person

Written and committed **before the expenditure table is built or any expenditure amount is read**. The
notebook binds to this file by its SHA-256. The only look at the cost file before this plan was its
structure: its columns, its row count, the states and quarters it covers and the form of its values, with
no amount read.

## 1. Question and estimand

What did the 2014 Medicaid expansion cost, in gross public spending, for each additional adult it insured?
The quantity is the **cost per newly insured person-year** for the 25 states whose expansion took effect on
1 January 2014 (C01's treated states), over 2014 to 2019: total expansion spending divided by the
person-years of coverage the expansion added. It is a cost-effectiveness ratio against no expansion, not a
benefit-cost result and not a net cost.

## 2. Cost side

**Source.** CMS, *Medicaid CMS-64 New Adult Group Expenditures*, data.medicaid.gov, the summary of
expenditures for the "VIII Group" (the ACA expansion population) reported by states through the Medicaid
Budget and Expenditure System. File `medicaid-cms-64-new-adult-group-expenditures-dataset-02172026.csv` at
`https://download.medicaid.gov/data/`, 374,311 bytes, SHA-256
`1b9232bac8abcb92f74963962b0d31d9ea299176120d657b22eae680810377e5`, a US-government work. It is committed
unchanged beside the other Medicaid policy tables, as a raw file named `expansion_expenditure.raw.csv`
with a tidy `expansion_expenditure.csv` built from it by a digest-checked script, as those tables are. (The
commit that adds them comes after this plan, so this sentence names them without a path.)

**Headline cost:** *Total Computable VIII Group Expenditures* (federal and state together), summed over the
quarters ending 2014-03-31 to 2019-12-31 and over the 25 treated states, in nominal dollars.
**Cost range**, used in the uncertainty analysis: from *Total Computable VIII Group Newly Eligible
Expenditures* (lower) to *Total Computable VIII Group Expenditures* (upper). The federal share is reported
beside the headline.

**Rules, fixed here.** A treated state-quarter that is blank, "N/A" or zero for the VIII Group is counted as
unreported and listed; nothing is imputed, so the cost is then a lower bound. Negative quarters that states
report as prior-period adjustments are kept as reported. The notebook checks that the newly-eligible and
not-newly-eligible columns add to the VIII Group total within one dollar per state-quarter and reports every
state-quarter where they do not; it does not correct them. The "Updated Year" and "Updated Month" columns are
not used.

## 3. Effect side, and a departure from "use C01's ATT"

The expenditure covers adults aged 19 to 64. C01's ATT is for ages 35 to 64 only, because the ACS tabulation
C01 uses changes its age bands in 2017 and has no consistent 19–64 series. Dividing a 19–64 cost by a 35–64
effect would overstate the cost per person. The plan therefore does the following.

- **Headline effect: C01's design applied to ages 19 to 64**, from ACS PUMS cells (the cells-only client;
  `AGEP` is in single years, so there is no band change). The 25 treated states against the 10 never-adopters,
  2012 to 2019 (pre-period 2012–2013, post-period 2014–2019; 2020 is not published), outcome = the share of
  adults 19–64 with no health insurance (`HICOV` = 2), state and year dummies, **weighted by the state-year
  population aged 19–64**, standard errors clustered by state, t distribution with 34 degrees of freedom
  (`methods.iv.tsls`, with the regressor as its own instrument, which is weighted least squares with clustered
  errors).
- **Newly insured persons in year t** = −τ ÷ 100 × the treated states' population aged 19–64 in year t, where
  τ is that estimate in percentage points. **Person-years** are the sum over 2014–2019.
- **Cross-check: C01's own ATT** (ages 35–64, as stored in C01's notebook output) is shown beside. A second
  ratio is also shown: the 19–64 cost divided by only the 35–64 effect counted on the 35–64 population, an
  upper bound on the cost per person that is labelled as one.

## 4. Ratio and uncertainty

- **Point estimate:** headline cost ÷ person-years, in dollars per newly insured person-year, with the same
  ratio on the federal share and on the lower and upper ends of the cost range.
- **Probabilistic sensitivity** (`methods.cea.psa_normal`, 20,000 draws, seed fixed in the notebook and
  printed): the effect is a normal distribution with the estimate as its mean and its standard error as its
  standard deviation; the cost is a normal distribution centred on the midpoint of the cost range with the range
  treated as its 95% interval; the two are independent. This is a stated input distribution, not a model of the
  data.
- **CEAC** (`methods.cea.ceac`): the probability that the net monetary benefit is positive at each willingness
  to pay from $1,000 to $30,000 per newly insured person-year in steps of $1,000.
- **Rule for reporting the ratio:** the ratio is reported as an interval only if the 95% interval of the effect
  excludes zero; otherwise the notebook says the cost per person is not bounded because the effect cannot be
  distinguished from zero, and reports the probability that the effect is not positive.

## 5. Checks (each stored as a `CHECK:` line)

1. The newly-eligible plus not-newly-eligible reconciliation described above.
2. The sign of the 19–64 effect agrees with the sign of C01's ATT.
3. No treated state's annual VIII Group total is negative.

A failed check is reported and does not change the headline or the rules.

## 6. Limitations the notebook must carry

- **Gross, not net.** The cost is gross spending. It omits offsets that would lower the net cost: reduced
  uncompensated care, state savings on programmes the newly covered would otherwise have used, and any tax or
  employment effects. It also omits what would raise it: administrative costs, and the spending on people who
  would have been insured anyway is *included* (it is part of the gross cost, which is what makes the ratio
  cost per newly insured rather than per enrollee). The direction of bias for net cost is that the gross figure
  overstates the net cost per newly insured person; the omission of administrative cost pushes the other way.
- **Nominal dollars, no discounting** (discounting is E02).
- **Unreported quarters** make the cost a lower bound.
- **Effect mean, constant over years:** one average effect is applied to every year, although coverage grew
  over 2014 to 2015.
- **The effect is an average over states weighted by population**; it relies on C01's parallel-trends argument
  and is not re-tested here beyond the placebo-style check C01 stores.
- **Different populations:** the expenditure is for the expansion group as defined by CMS, and the effect is for
  all adults 19–64; they overlap but are not identical.
