<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# I01 plan — amendment 2 (2026-10-27)

Committed **before any gap, feature coding, association, correlation or interval is computed**. It
amends `I01_plan_amendment_1.md` (commit `5da2eb1`), which is not edited, and does not touch
`I01_plan.md`.

## What happened

Amendment 1, section B, requires each of the 51 jurisdictions to have exactly one profile page in the
options report, found by a jurisdiction named in the page's first lines, or the notebook stops. A first
read of the 14th edition (options as of 1 October 2017) found 50: Virginia's profile page begins with
the printed footer "SNAP State Options Report • 82" and has no heading in the text layer. The table of
contents lists "Virginia 82", the footer of that page is 82, and the page sits between Vermont (81) and
Virgin Islands (83). The notebook stopped. No gap, feature coding or association had been computed; the
only figures seen from the retrieval were row and profile counts, the restated-year agreement, and
value counts of the two features across states.

## Owner ruling (2026-10-27)

A profile page with no heading is assigned to a jurisdiction by its page number:

- The **table of contents** gives each jurisdiction's printed page number (a line that is a
  jurisdiction's name followed by one whole number; leader dots are ignored).
- A page is *headingless* if it carries at least one of the profile labels, has no heading naming a
  jurisdiction, and has a printed footer number (`Options Report • <n>`).
- Such a page is assigned to a jurisdiction **only if** that jurisdiction otherwise has no profile,
  its table-of-contents number equals the page's footer number, and **exactly one** page has that footer
  number. Otherwise nothing is assigned and the notebook stops as before.
- Every assignment is printed with the page, the footer number and the table-of-contents entry.

## Unchanged

Everything else in `I01_plan.md` and `I01_plan_amendment_1.md`, including every stop-rule not named here.
