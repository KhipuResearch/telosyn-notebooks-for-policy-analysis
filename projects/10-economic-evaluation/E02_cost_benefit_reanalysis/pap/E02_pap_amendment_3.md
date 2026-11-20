<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# E02 plan — amendment 3 (2026-11-20)

Text only. Written under the owner ruling in the owner's re-review of 2026-11-01 (REVIEW-7), which corrects the owner's own earlier record. It amends
`E02_pap.md` (SHA-256 `91e02c694a3ba14f1e9fc184477c00384ae4a52479aceaff15d56510a6f01f74`) and follows `E02_pap_amendment_1.md` (SHA-256
`7db39861f47cc89ee3ce59d06a7f38efdb92e4bb53aa1281a2d5e8f7d0d5e78c`) and `E02_pap_amendment_2.md` (SHA-256
`cd0c4725f67f0cddb72b89c1caa7b39bbd10b5560e82f017a6f8694668f04f73`); none of the three is edited. Relation: **after_retrieval**. It is **not
pre-specified**: it is added after review. It is committed before the notebook's wording is changed to match it.

## What is withdrawn

Amendment 2 says, in its section "How it is applied", that if EPA computed the annualised values the way reading H does, "they are about 2 percent higher
than a consistent convention gives". **That phrase is withdrawn**, and so is the word "mismatch", which the owner's review of 2026-10-31 used for the same
point. The phrase was carried into the notebook's cells 17 and 18 and Takeaway 3. **The error was the reviewer's.** Neither
convention below is inconsistent, and neither is an error.

## What is true instead

Both conventions are internally consistent. Each gives an equal annual amount whose present value equals the present value of the stream. They differ only
in where in the year that amount is placed, with flows x_y for the years y = 2024 to 2058 (n = 35) and rate r:

- **Amendment 1's convention** places the equal annual amount at the **start** of each year. Its annualised value is the present value (year one
  undiscounted) divided by the sum over k = 0 to n − 1 of 1/(1+r)^k.
- **Reading H** (amendment 2) places the equal annual amount at the **end** of each year. Its annualised value is the same present value divided by the sum
  over k = 1 to n of 1/(1+r)^k.

Because the second sum equals the first divided by (1+r), **reading H's value is exactly (1+r) times amendment 1's value**: 1.02 at 2 percent. Neither is
an error of EPA's or of the notebook's. EPA's analysis states neither placement, so the notebook cannot say which one EPA used; reading H remains a likely
explanation of the gap, stated conditionally, and nothing more.

## What does not change

No computation, no tolerance, no check and no verdict. Check 3 of the plan stays **FAIL**; the primary result stays the failed reproduction under
amendment 1's convention; reading H stays labelled "not pre-specified" and reported as a likely explanation, not a reproduction pass; nothing is computed at 3
or 7 percent and no other convention is tried; the stop rules, the prohibition on a random draw over EPA's ranges, and the statement that this is a
reproduction attempt of EPA's own assumptions and not an independent estimate all stand. Amendment 2's other text is unchanged.
