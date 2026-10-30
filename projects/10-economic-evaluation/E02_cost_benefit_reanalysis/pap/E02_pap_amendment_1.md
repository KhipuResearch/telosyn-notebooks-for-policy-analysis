<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# E02 plan — amendment 1 (2026-10-30)

Written under the owner ruling of 2026-10-30 on the timing convention and the scenarios. Committed **after** the source document was downloaded and read,
and **before** the reproduction check is run as a computation of record. It amends `E02_pap.md` (commit `d5799ce`), which is not edited. The notebook
binds to both files by SHA-256. Relation: **after_retrieval**.

## What had been computed when this rule was set

- The document was downloaded once (9,589,288 bytes, as approved; SHA-256 `057c531f5bf14910f321a653bcdf341317676325b0d3dafeef4e874054bca350`) and read.
- The yearly streams were located: Exhibit 6-4 (low scenario) and Exhibit 6-5 (high scenario), 2024 to 2058, 35 years, millions of 2022 dollars,
  undiscounted. Stop rule (a) of the plan therefore does not fire. The streams were parsed in a scratch file and their undiscounted totals compared
  with the text (net benefits $479,206 million and $918,482 million; the text says "$479 billion to $918 billion"). No table is committed yet.
- **One reproduction had already been computed**, under the reading the plan fixed in section 3 (discount to year one; annualise by the same factors),
  before this convention was set. It gave annualised values at 2% below EPA's printed values by **1.8 to 2.0 percent**: costs 1,442.3 (low) and 1,919.3
  (high) against EPA's 1,468.8 and 1,953.8; benefits 13,228.9 and 24,649.7 against 13,493.5 and 25,142.6; net benefits 11,786.6 and 22,730.4 against
  12,024.7 and 23,188.8. The tolerance of plan section 5 (the larger of 0.5 percent and one unit in the last printed digit) is not met, so the plan's
  stop rule (e) fired and the owner was asked.
- **The gap was seen to be about a factor of 1.02**, that is, one year of discounting: the benefit figure multiplied by 1.02 equals EPA's printed
  value (13,228.9 x 1.02 = 13,493.5), and the cost and net figures are within a few tenths of a percent of the same factor. This observation did not
  select any convention, and **no other convention was computed.** The owner then ruled as follows.

## The timing convention (applied once)

The rule: use the convention EPA's analysis itself states; where it states none, use Circular A-4 (2003) and say so. Do not try alternatives.

**What EPA states** (Economic Analysis for the Final LCRI, October 2024):

- Base year of present values: Section 5.6.2, "Monetized National Annual Benefits", document page 5-58 (PDF page 662): "Benefits are discounted back to
  year one of the analysis and annualized within the SafeWater LCR model." Year one of the analysis is 2024, the first row of Exhibits 6-4 and 6-5.
- The rate: Section 4.2.3.3, "Discounting and Cost of Capital", document page 4-13 (PDF page 255): "the EPA discounted future costs (and benefits) at a 2 percent
  discount rate."
- The period and symmetry: Executive Summary, document page ES-2 (PDF page 29): EPA "annualized the estimated future streams of costs and benefits ...
  over this same period of analysis symmetrically", and the period of analysis is 35 years.
- Section 4.2.3.3 also says that, "when evaluating the economic impacts on PWSs and households, the EPA uses the estimated PWS cost of capital to
  discount future costs" (document page 4-14). The national annualised costs in Exhibits ES-1 and 4-1 are headed "2 Percent Discount Rate". This
  notebook takes the 2 percent figure for the national costs, as the exhibits are headed, and records the cost-of-capital statement as a possible source of
  difference that it does not model.

**What EPA does not state:** whether flows fall at the start or the end of each year, or the annuity form used to annualise. A search of the whole
document for those terms found no statement.

**What Circular A-4 (2003) provides** (the file on OMB's circulars page, 48 pages, SHA-256 `cb57542f6598541785a60f7c735f92421ec39ae1f960ee379751ddd8d8b5d2a0`):

- Section "Discount Rates", page 32: the discount factor "is 1/(1+ the discount rate)^t where t measures the number of years in the future that
  the benefits or costs are expected to occur." The Circular states no start-of-year or end-of-year convention.
- Page 45: the "stream of annualized estimates should begin in the year in which the final rule will begin to have effects."

**The convention, then:** the base year is year one (2024); a flow in calendar year *y* is discounted by 1/(1+r)^(y - 2024), so that year one is
undiscounted and *t* counts the years after the base year (A-4's *t*); the **annualised value is the constant yearly amount over the same 35 years that
has the same present value under the same factors**, A = sum(f_t x_t) / sum(f_t). Because annualisation divides a present value by the sum of the same
factors, **the annualised value does not depend on whether flows are placed at the start or the end of a year** (a common shift of every *t* cancels);
the choice matters only for the level of a present value, which is reported as of year one. The unstated annuity form is thereby fixed by A-4's formula and
EPA's word "symmetrically", and not by a search for a match. This is the reading the first computation had used; stating it now does not change it.

The reproduction at 2% is therefore the one already computed and gives the gaps listed above. **The plan's stop rule (e) stands and fires.** The gap is a
finding with its size, not something to adjust: nothing in the convention, the tolerance or the rate is changed to close it.

## The scenarios

The plan's "central scenario" (sections 4 and 6) does not exist in the document: EPA publishes two scenarios, **low and high**, in which the low
costs go with the low benefits and the high costs with the high benefits (the same three cost drivers and the same likelihood of exceeding the action
level define both). The two published scenarios **replace** the central scenario. Costs and benefits stay paired within each scenario, exactly as EPA publishes them.
**No midpoint, average or other constructed scenario is made.** Primary results are reported for both scenarios at **3% and 7%**; 2% is the
sensitivity and the reproduction check; the sensitivity grid and the switching-rate search of the plan stand, per scenario.

## What does not change

The tolerance (section 5), the stop rules (section 9), the checks (section 8), the prohibition on a Monte Carlo or any random draw over EPA's ranges, the
statement that this is a re-analysis of EPA's assumptions and not an independent estimate, and the Limitations of section 12. The notebook records this
amendment as a departure from the plan's wording on the central scenario and as the fixing of the timing convention after retrieval.
