<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# Q03 pre-analysis plan — Bayesian partial pooling of county poverty estimates: what the model adds, and what the prior adds

Written and committed **before any table is retrieved for this notebook**. The notebook binds to this file by its SHA-256 (`krl.pap`); a committed
plan is never edited, and a change is a new amendment file.

## 1. Question, estimand and what this is not

Q03 asks how much a hierarchical model changes a set of small-area estimates, and how much of the change is the data and how much is the prior. The
quantity is the **true 2019–2023 poverty rate of each Virginia county and independent city**, `theta_i`, for 133 places whose published ACS estimates
have margins of error of very different sizes. The notebook reports two estimates side by side for every place: the **unpooled** published estimate
with its margin of error, and the **pooled** posterior for `theta_i`. Pooled estimates are model outputs and inherit the prior; the unpooled
estimates are design-based and inherit nothing.

This is a descriptive, non-causal analysis. It makes no statement about why a county's rate is what it is, ranks no county, and tests no hypothesis.
There is no multiplicity correction because there is no family of tests. D04's rule applies: **do not rank places on a modelled small-area
estimate**; the notebook reports shrinkage, not an order.

## 2. Data: the same request as D04, cells already aggregated

ACS 2023 5-year estimates, table `B17001` (poverty status), `county:*` within `state:51`, variables `B17001_001E`, `B17001_001M` (poverty universe and
its margin of error) and `B17001_002E`, `B17001_002M` (persons below the poverty level and its margin of error). This is the request D04 makes
(`d04_acs_b17001_county.json`). The notebook compares the digest of the rows it receives with the digest stored in D04's provenance record
(`de80c3ee9645ba785908f977b3af141521462e848c9a04908bf26198714d11f9`). **If they differ, Census has changed the file and the notebook stops and asks the
owner.** No other table is retrieved. No person-level row exists at this level.

Each county gives `y_i = B17001_002E / B17001_001E`. Its standard error `s_i` follows the Census Bureau's published formula for a proportion whose
numerator is a subset of its denominator, from the 90% margins (`se = MOE / 1.645`): `s_i = sqrt(se_x^2 - y_i^2 * se_n^2) / n_i`, and where the
radicand is negative, the ratio formula `sqrt(se_x^2 + y_i^2 * se_n^2) / n_i`. A county whose `y_i`, `n_i` or `s_i` is missing, non-positive in `n_i` or
`s_i`, or a Census jam value is dropped and counted; if fewer than 120 of the 133 remain the notebook stops and asks. Margins are treated as the
sampling error of a normal estimate and **are taken as known**, as every hierarchical small-area model does; that is an assumption, not a fact (the ACS
margins are themselves estimated, and the survey design is summarised by them, not modelled).

## 3. Model, fixed before the data

On the rate scale, non-centred:

```
y_i  ~ Normal(theta_i, s_i)           s_i known
theta_i = mu + tau * z_i,  z_i ~ Normal(0, 1)
mu   ~ Normal(0.15, 0.10)
tau  ~ HalfNormal(0.05)
```

| Setting | Value |
|---|---|
| Library | `pymc`, imported only by the notebook; installed only through its own optional extra, never core |
| Sampler | NUTS, 4 chains, 2000 tuning and 2000 retained draws per chain, `target_accept` 0.95 |
| Seed | 20261030 for the sampler (each chain seeded from it by the library), 20261030 for every other random number |
| Posterior summaries | posterior mean and a 90% equal-tailed interval for each `theta_i`, for `mu` and for `tau`; the posterior mean of the shrinkage factor `B_i = s_i^2 / (s_i^2 + tau^2)` |

The prior on `mu` puts most of its mass on 0 to 0.35; the prior on `tau` has median about 0.034. Both are written here before the data are seen and are
the primary setting; nothing is changed after the first fit.

**Exact reference.** For this model `mu` integrates out in closed form and `p(tau | y)` is one-dimensional, so the posterior mean of every `theta_i` and
of `tau` can be computed by numerical integration over a fine `tau` grid with no sampling. That calculation is a library function (numpy and scipy
only) with known-answer tests, and the notebook uses it as an independent check on the sampler (section 6).

## 4. Convergence stop rule

After sampling the notebook prints, for `mu`, `tau` and every `theta_i`, the split R-hat, the bulk and tail effective sample size, the number of
divergent transitions and the worst energy-BFMI. **If the largest R-hat exceeds 1.01, the notebook stops, prints the table and asks the owner.** It also
stops, and does not interpret results, if any divergent transition remains or the smallest bulk or tail effective sample size is below 400. A run
that stops is reported as a stop, not as a finding.

## 5. What is reported and what is exploratory

**Reported (all descriptive, pre-specified):**

1. **Pooled and unpooled together.** For each county, the unpooled estimate with its 90% margin, the pooled posterior mean with its 90% interval, and
   the shift (pooled minus unpooled, in percentage points). Summary: the median and the largest absolute shift; the ratio of the pooled interval's
   width to the unpooled margin's width, by population tercile.
2. **Shrinkage against the corpus's reliability framework.** The posterior mean `B_i` against the reliability `lambda_i = tau2 / (tau2 + s_i^2)` used
   by D04 (`tau2` by the moment estimator, floored at zero); they are the same quantity under the model and differ in how `tau` is estimated, so the
   notebook reports `tau`'s posterior against the moment estimate and the share of counties with `lambda_i` below 0.7 under each. The correlation
   (Spearman) of the shrinkage weight with the log of the poverty universe is reported as an association, not a test.
3. **What the prior contributes.** The posterior of `tau` against its prior (contraction: posterior standard deviation divided by prior standard
   deviation) and the change in every county's pooled estimate under the sensitivity priors below.

**Prior sensitivity (pre-specified settings, the same sampler settings):**

| Label | `mu` prior | `tau` prior |
|---|---|---|
| primary | Normal(0.15, 0.10) | HalfNormal(0.05) |
| tight tau | Normal(0.15, 0.10) | HalfNormal(0.02) |
| loose tau | Normal(0.15, 0.10) | HalfNormal(0.15) |
| heavy-tailed tau | Normal(0.15, 0.10) | HalfCauchy(0.05) |
| vague mu | Normal(0.15, 0.30) | HalfNormal(0.05) |

Report, for each, the posterior mean of `tau`, the median `B_i`, and the largest and median absolute change in any county's pooled mean from the
primary. **A county is "prior-sensitive" if its pooled mean moves by more than 1 percentage point across the settings;** the notebook lists them and
states how many there are. No setting is promoted to primary after the fact.

**Exploratory (labelled in the cell, outside the report):** a refit on the logit scale (standard errors by the delta method) compared with the primary
pooled means, and any further description of which counties shrink most. Nothing exploratory is reported as a finding.

## 6. Falsification and checks (each stored as a `FALSIFICATION:` line)

1. **Data identity.** The digest of the rows equals D04's stored digest. PASS if equal.
2. **Sampler against the exact reference.** The largest absolute difference, over counties, between the sampler's posterior mean of `theta_i` and the
   exact grid-integrated posterior mean. PASS if below 0.1 percentage point.
3. **Convergence.** The largest R-hat. PASS if at most 1.01 (and the stop rule of section 4 has not fired).
4. **Posterior predictive coverage.** The share of counties whose unpooled estimate lies inside its own 90% posterior predictive interval
   (`theta_i` draws plus Normal noise with standard deviation `s_i`). PASS if between 0.85 and 0.95, the range two binomial standard errors
   around 0.90 for 133 counties.
5. **Pooling is not an artefact of the prior on `mu`.** The largest absolute change in any pooled mean between the primary and the vague-`mu`
   setting. PASS if below 0.5 percentage point.

A check that fails is reported and not explained away; the notebook then describes the pooled estimates as sensitive to the stated cause.

## 7. What counts as credible

- **Credible as estimates of the county rates:** the stop rule has not fired, checks 2 and 3 pass, and the pooled estimates are shown beside the
  unpooled ones with the prior stated.
- **The model's contribution is itself uncertain:** if more than a tenth of counties are prior-sensitive, or check 5 fails, the notebook says the
  pooled estimates for those counties are mostly the prior and reports them as such.
- **Expected direction, stated before the data:** small counties shrink most, so the association in section 5.2 should be negative. If it is not,
  the notebook says so.

## 8. What Q03 does not claim, and the software

- It does not claim the pooled estimate is closer to the truth for any single county; it reports the model's posterior under stated assumptions,
  and the coverage check of section 6 is a check on the model's calibration at the observed estimates, not an out-of-sample validation.
- It does not rank counties, and it does not treat the margins of error as anything but the published ones.
- `pymc` is installed only through its own optional extra, never as a core dependency; no library test requires it; the library keeps the
  proportion standard error, the moment estimator and the exact reference in functions that import neither `pymc` nor anything beyond the existing
  dependencies, and the notebook alone imports `pymc`. A decision record for the dependency (ADR) and a before-and-after measure of CI time accompany
  the notebook, and if the total CI increase would exceed 5 minutes the work stops and the owner is asked.
- Sampling is seeded; numbers in the notebook's text are those of its stored run. A different platform or library version can change the last digits
  of a draw-based number, which is why every check above is a threshold and not an equality.

## 9. Limitations the notebook must carry

The margins of error are taken as known and normal; the rate-scale model ignores that rates are bounded (the logit refit is the exploratory check);
the survey design is summarised by the published margins, and the model does not use covariates or spatial structure, so a county is shrunk toward
the state mean and not toward similar counties; the pooled estimate is a model output that depends on the prior, shown by section 5; 5-year estimates
pool 2019 to 2023 and describe none of those years in particular; independent cities and counties are treated as exchangeable; and the unpooled
estimates remain the design-based quantity. If the analysis departs from this plan, the Limitations section says how and why, and a departure that
moves the primary result is a new amendment, committed before the result it changes is computed.
