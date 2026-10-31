<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# E02 plan — amendment 2 (2026-10-31)

Written under the owner ruling of 2026-10-31 that followed the owner's review of PR 20. It amends `E02_pap.md` (SHA-256
`91e02c694a3ba14f1e9fc184477c00384ae4a52479aceaff15d56510a6f01f74`) and follows `E02_pap_amendment_1.md` (SHA-256
`7db39861f47cc89ee3ce59d06a7f38efdb92e4bb53aa1281a2d5e8f7d0d5e78c`); neither is edited. Relation: **after_retrieval**. **Not pre-specified: added after review,
2026-10-31.** It is committed before the computation it describes is added to the notebook.

## What had been computed when this was written

- The reproduction of record under amendment 1's convention (year one undiscounted; the annualised value is the present value divided by the sum of the same
  factors) missed EPA's printed 2% annualised values in all six comparisons, by 1.77 to 1.98 percent. That result stands.
- The notebook already printed the ratio of EPA's value to the rebuilt value (1.018 to 1.020, near the one-year factor 1.020). Because the annualised
  value divided by the sum of the same factors does not depend on a uniform shift of the timing, that ratio cannot be explained by a uniform shift in
  timing; the notebook's earlier wording that named a base-year or flow-timing difference as a possible cause is withdrawn.
- **The hypothesis below was suggested by the owner's review, which had already computed it** and reported that it brings the six values within the
  tolerance. It is written here before the notebook computes it, but it was not formed from a blind reading of the document, and it is labelled so.

## The one hypothesis

**H: EPA's annualised value is a present value in which year one is undiscounted, divided by an end-of-year annuity factor.** With flows x_y for the
years y = 2024 to 2058 (n = 35) and rate r:

    PV   = sum over y of x_y / (1+r)^(y - 2024)           (year one undiscounted)
    A_H  = PV / sum over k = 1..n of 1/(1+r)^k            (the end-of-year annuity factor, (1 - (1+r)^-n) / r)

This differs from amendment 1's annualised value, which divides the same PV by the sum over k = 0..n-1 of 1/(1+r)^k. A_H equals amendment 1's value
multiplied by exactly (1+r). That the ratio of EPA's printed value to amendment 1's value is near (1+r) = 1.020 is the fact the hypothesis would explain.

## How it is applied

- **Once, at 2 percent, on the six comparisons of amendment 1** (EPA's low and high scenarios; costs, benefits, net benefits), against EPA's printed
  Exhibit 6-6 values and the tolerance of plan section 5. **Nothing is computed at 3 or 7 percent, no net present value is shown, and no other convention
  is tried.**
- It is reported as a **likely explanation, not a reproduction pass.** Check 3 of the plan stays **FAIL**, and the primary result stays the failed
  reproduction under amendment 1's convention. The cell is labelled "not pre-specified (added after review, 2026-10-31)".
- It is worded conditionally: if EPA computed the annualised values this way, they are about 2 percent higher than a consistent convention gives. The
  notebook does not say that EPA erred, and does not say which convention EPA used, because EPA's analysis states none.

## What does not change

The plan and amendment 1, the tolerance, the stop rules (a stop rule that holds for the downstream results holds still), the checks, the prohibition on a
random draw over EPA's ranges, and the statement that this is a reproduction attempt of EPA's own assumptions and not an independent estimate.
