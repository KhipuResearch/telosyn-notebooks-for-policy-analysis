<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# Q03 plan — amendment 1 (2026-10-30)

Committed **after** the table was retrieved and **after** the first fit stopped under the plan's own rule, and **before** any rerun and before any
number from a fit is used. It amends `Q03_pap.md` (commit `a1f4e8a`), which is not edited. The notebook binds to both files by SHA-256.

## What happened

The retrieval returned rows with the digest D04 stored. The primary fit (plan section 3: 4 chains, 2000 tuning and 2000 retained draws each) stopped under
section 4: the largest R-hat was 1.0060 (the owner's limit is 1.01), there were no divergent transitions and the lowest energy-BFMI was 0.63, but the
smallest effective sample size was 305, below the plan's floor of 400. No posterior summary, shrinkage factor, check or figure from that fit was read or
used, and the stop is on the run ledger.

## What changes

| Setting | Plan | Amendment |
|---|---|---|
| Retained draws per chain, every fit in the notebook (primary, the four prior settings, the exploratory logit fit) | 2000 | **8000** |

Nothing else changes: the model, the priors, the tuning length (2000), the number of chains (4), `target_accept` (0.95), the seed, the data, the
checks and their thresholds, and the stop rule of section 4 (R-hat 1.01; no divergence; smallest effective sample size 400). The effective sample size
of a chain grows roughly in proportion to its length, so four times the draws is expected to give about four times the effective sample size. If the
stop rule fires again, the notebook stops again and the owner is asked; no setting is changed to get under it.

The amendment changes no estimand and no hypothesis. It is recorded as a departure from the plan in the notebook's Limitations.
