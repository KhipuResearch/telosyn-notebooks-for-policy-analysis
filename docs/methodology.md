# Data Source Handbook

Corpus-level rules distilled from the 23 executed notebooks in `projects/`.

**Status: normative for this corpus.** Every quantitative claim below is traceable to a
notebook in this tree and to a number that notebook computed from live data. Where a
claim is a rule rather than a measurement, it is marked **[rule]** and the notebook that
motivates it is cited. Where something is not established, it says so.

Two of the corpus's own exercises ask for this document: D08 exercise 6 ("write the rule
this corpus should adopt" for vintages) and D15 exercise 6 ("draft the paragraph this
corpus should use to choose between CBP and QCEW"). §4 and §5 answer them directly.

**Traceability convention.** `[D09 F2]` means finding 2 of the FINDINGS block in
`projects/04-economy-industry/D09_industry_structure/`. Findings are regenerated on every
execution; if a number here disagrees with the notebook, the notebook is right and this
file is stale.

---

## 1. The fourteen data regimes

The single most important fact about these sources is that they do not fail in the same
way, and the handling that makes one safe makes another silently wrong.

| Source | What is published | What is withheld | What that disables |
|---|---|---|---|
| **Census ACS** | Estimate **and** margin of error, 90% confidence | Nothing systematic; small cells get wide margins | Nothing — but an analysis that drops the MOE column has thrown away the only published statement of how much the estimate knows |
| **BLS LAUS** | Estimates only | **All uncertainty** | Any significance test, any ranking claim, any "changed by more than noise" statement. There is no published quantity to test against |
| **FRED / ALFRED** | Current series by default; every past vintage on request | Nothing, but the default is a moving target | Reproducibility. The same call returns different numbers next month |
| **BLS QCEW** | Disclosed cells; a suppression flag on the rest | Values for cells failing disclosure rules | Per-cell statistics, industry counts, share denominators. **Sums survive** |
| **Census CBP** | A value in every published cell, noise-infused | The **existence** of unpublished cells | Roster completeness, industry coverage, any claim that a place has no employment in an industry |
| **HUD FMR** | A single binding figure per administrative area | Uncertainty, the revision history, and which schedule a machine-readable copy holds | Comparison to a contemporaneous survey, sub-area variation, and any assumption that the published copy is current |
| **HUD CHAS** | Counts retabulated from ACS microdata to a third party's specification | **The source's margins**, the current vintage, and any record of which categories were retired | Every significance and ranking claim, comparison against the current ACS, and trust in the published dictionary |
| **CDC PLACES** | A modelled prediction per county with a credible interval | That the interval is not a sampling margin, and that local evidence may be absent entirely | Reading interval width as local sample size; any claim that a county's value was measured there |
| **Opportunity Atlas** | Linked administrative outcomes for a fixed birth cohort, noise added, small cells withheld | The cohort's present, the withheld subgroups, and the size of the injected noise | Any statement about the place today, and any subgroup gap computed over the surviving counties |
| **Census BDS** | Exact counts, noise-infused flows, a flag column you must ask for | Statewide records at county level, and which firms are counted twice | Summing firms over any partition, reconciling counties to their state, and every rate built on `DENOM` |
| **BEA ACPSA** | A fully populated, perfectly additive accounting re-partition of value added | Nothing — and no uncertainty either, because nothing was sampled | Every precision claim. The error is entirely in the boundary, and the boundary is not a number |
| **Social Capital Atlas** | Estimates and standard errors, under formal differential privacy at a published ε | Units below the cell-size threshold, and the split between sampling and privacy error | Any claim about the units that were removed, and any attempt to treat the published error as purely statistical |
| **FBI CDE (NIBRS)** | Offences, coverage-normalised rates, and the covered population | Which agencies chose not to report, and whether a reporting agency filed usable counts | Any comparison across the participation transition, and any correction built from the coverage figure |
| **EPA TRI** | A self-reported quantity per record **and a code saying how that number was produced** | Any quantification of what each code costs in accuracy, and every facility below the reporting thresholds | Converting the provenance mix into a bound on a total, treating absence as zero release, and any magnitude-weighted quality statistic that has not been checked against its largest observation |
| **MIT election returns** | Counted ballots -- no estimator, no sample, and so **no sampling error to state** | Which of at least two things `totalvotes` counts in a given state, and the identity of 207 parties inside `OTHER` | Aggregating `totalvotes` across states, cleaning the file before testing its accounting identity, and any third-party analysis built on `party_simplified` |
| **USDA Food Environment Atlas** | 3,143 county rows with a FIPS column, on every sheet | **Which columns are county measurements.** 49 of 280 hold one value per state, replicated down; nothing marks them | Every county-level statistic on a replicated column, and every standard error taken at the county count rather than the distinct-value count |

### 1.1 ACS — margins of error

The ACS convention is **90% confidence**, so `SE = MOE / 1.645`. Using 1.96 silently
narrows every interval [D03 takeaways]. Margins combine **in quadrature**, not by
addition. They widen sharply as geography shrinks: on the identical quantity, county
margins run a median 2.34 pp against 0.27 pp at state level — **8.7× wider** [D16 F3].

Do not judge significance by whether intervals overlap; use the Bureau's Z-test. The
overlap heuristic is conservative and gets the answer wrong [D03 takeaways, Schenker &
Gentleman 2001].

Two failure modes of the margin machinery itself, both observed:

- **The proportion formula degenerates.** At a share of 1.00 the radicand under the
  standard proportion-MOE formula collapses and the published margin is zero. This
  occurred in 1 county on a base of 90 households [D16 F6]. `reliability.py`
  exposes `proportion_moe_is_degenerate` for this; it is not a rare-enough case to
  leave undetected.
- **MOE correlation is unpublished.** Aggregating margins in quadrature assumes
  independence. That assumption is not available from the Bureau. Where a conclusion
  depends on it, `standardization.py` computes both the independent and the
  perfect-correlation bound and the notebook reports which survive. In D07, of 24
  rank reversals under age standardisation, 1 was distinguishable at 90% under
  independence and **0 survived the worst-case correlation assumption** [D07 F3].

**[rule]** A finding that holds only under the independence assumption is reported as
conditional on it, in the finding itself, not in a footnote.

### 1.2 BLS LAUS — model output with no published uncertainty

LAUS is a state-space model benchmarked to state controls, not a survey with a sampling
error. Two consequences are measurable in this corpus:

- The published components reconcile **exactly**: unemployed + employed = labour force in
  306 of 306 state-years, largest deviation 0.0 persons [D02 F1]. This is a property of a
  constrained model, not agreement between independent measurements.
- Sub-state figures are controlled to the state. Virginia's 133 counties sum to the state
  employment total to within **7 persons (0.00016%)** [D02 F4]. County figures are
  therefore **not independent observations** and must not be treated as a sample of 133.

**[rule]** No LAUS ranking, significance claim, or "statistically different" statement.
The published series carries no quantity against which to test one.

### 1.3 FRED / ALFRED — revision

The same observation differs by vintage. Over one 51-month window, the **sign** of
month-over-month growth reversed between vintages in 3 months for nominal PCE and 7
for real PCE [D08 F4]. For those months the two vintages support opposite conclusions
about whether spending rose or fell.

**Rebasing and revision are distinct and the data cannot tell them apart.** D08 tried and
failed to build a diagnostic: ratio standard deviation is 0.007199 for nominal PCE against
0.006083 for real — no threshold separates them, and residual variation is similar (0.711%
vs 0.566%) [D08 F1]. What differs is the *shift*: +1.30% nominal against +7.54% real
[D08 F2]. Real PCE is chained, so most of its shift is a base-year change and its **levels
may not be compared across vintages at all**; nominal PCE cannot be rebased, so its shift
is revision. **That classification comes from the series definition, not from the data.**

Growth rates largely survive rebasing: cross-vintage correlation of month-over-month
growth is 0.9932 (real) and 0.9933 (nominal), with mean absolute revision of 0.229 pp and
0.242 pp [D08 F3]. Levels do not.

Revisability is itself heterogeneous and unpublished: across 50 states the median level
revision ranges from −2.62% to +4.10%, a **6.72 pp spread** [D08 F6].

### 1.4 BLS QCEW — suppression with a flag

Withheld cells are published as the literal value **`0`** with a suppression flag. This
leaves sums untouched — adding zeros changes a total by zero — and corrupts every
per-cell statistic. In Fairfax County at 6-digit NAICS, mean employment per industry reads
697 naively against 1,201 corrected, an error of **−42%**, and **308 industries appear to
have no employment at all** [D09 F2].

Suppression rises monotonically with detail: **0% at 2-digit sector, 41.9% at 6-digit**
[D09 F1]. The same suppression is 41.9% of *cells* and 9.6% of *employment*, so shares
built from disclosed cells sum to **90.4%, not 100%** [D09 F3].

**Missingness is informative.** Suppression runs 95% for cells with 1–3 establishments and
2% for cells with 50 or more (Spearman −0.667; Pearson −0.221 understates a step relation)
[D09 F4]. The flag therefore identifies *concentrated* industries, which is exactly the
population a concentration analysis is about. And because establishment counts are
disclosed even when employment is withheld — for all 294 suppressed cells in that county —
**the rule is partly recoverable** [D09 F4].

Small economies lose the most: across 5 areas spanning 2,522 to 540,812 private jobs,
suppression runs **41.9% to 88.9%** [D09 F5]. Detailed industry data is least available in
the economies most exposed to a single employer.

**[rule]** `fetch_qcew` converts suppressed numerics to `NaN` and returns a `suppressed`
boolean column. Never `fillna(0)` on a QCEW frame — that reconstructs the defect the
fetcher exists to remove.

### 1.5 Census CBP — noise infusion and silent omission

CBP publishes a value in every cell it publishes, and simply omits the rest. There is no
flag, no zero, no row. On the surface it looks like the cleaner source: 469 of 469 6-digit
cells populated in Fairfax County, against QCEW withholding 297 of 692 (42.9%) [D15 F1].

The rosters disagree about what exists. QCEW lists 692 industries, CBP lists 469, **365
appear in both**; 327 are QCEW-only and 104 CBP-only [D15 F2]. Of the 327 CBP omits,
QCEW openly reports employment for 120, totalling **59,834 jobs**. In CBP they are not
withheld, not zero, and not present — **a reader working from CBP alone cannot learn that
they exist** [D15 F3].

The noise flag is not usable as published: uniform across all 782 cells retrieved, with no
enumeration of its values in the API [D15 F5]. `fetch_cbp` preserves the flag columns as
**text** so they cannot be silently summed.

> **The source with visible gaps is the more usable one.** QCEW tells you an industry
> exists, how many establishments it has, and that its employment is withheld. CBP tells
> you nothing about what it did not publish. [D15, closing]


### 1.6 HUD FMR — the administratively determined number

The first five regimes describe measurements that are imperfect in different ways. This one
is not a measurement. A Fair Market Rent is **defined** as an estimate — 24 CFR 888.113 calls
it a 40th-percentile gross rent — and **used** as a rule: it sets Housing Choice Voucher
payment standards, Section 8 renewal rents, HOME and ESG ceilings, and Public Housing flat
rents. Four properties follow from the rule half, and each moves the number away from the
measurement it is named after.

**The definition describes the input, not the output.** The published FMR runs a median
**1.286×** the ACS 2023 median gross rent for the same unit size and county, and falls below
that median in only **35 of 3,102** counties [D05 F1] — the opposite of what "40th percentile"
implies, because the figure is trended forward to the fiscal year in which it binds. The gap's
p90/p10 is **1.42×**, so the step is local and is published as no field.

**The geography is statutory.** **281 of 2,606** FMR areas span more than one county row,
covering **2,439 of 4,764** rows; 114 rows share Boston-Cambridge-Quincy's single 2-bedroom
FMR of $3,008 [D05 F2]. Measured against each other so the projection cancels, county median
rents inside one FMR area span a median **29.2%** (p90 88.7%, max 213.2%), and **599 of 830**
such rows sit in an area whose internal spread exceeds 25%. This is MAUP that no analytical
choice can fix.

**Revision without a revision series.** FY2026 changed after it took effect in **9 county rows
across 7 FMR areas, +6.3% to +19.5%, every one an increase** [D05 F4]. There is no vintage
parameter: the revision exists only as the difference between two similarly-named files. The
uniform direction is a property of the appeals process — an authority requests reevaluation
when the standard is too low to lease — not of the rental market, so FMR revisions must never
be read as new information about rents.

**Two machine-readable copies that disagree.** HUD publishes both a keyed REST API and an
ArcGIS feature layer. The API is current and post-revision — on a 20-county sample it matches
the pinned FY2027 files in **16 of 16** that return a county figure, and on the nine revised
rows it serves the **revised** value in 8 of 8 comparable ones. The feature layer serves the
**pre-revision FY2026** schedule. Neither surface states which schedule it holds [D05 F7].
Which answer a developer gets depends on which surface they found.

**No published uncertainty**, as with LAUS (§1.2): no significance test, no ranking claim.

**[rule]** An administratively determined number may be compared to a survey estimate only
with the reference periods stated, and the comparison reports the gap rather than attributing
it. Any notebook using one records **which publication** it used, because more than one exists
for the same fiscal year.



### 1.7 HUD CHAS — the custom tabulation

The Census Bureau retabulates ACS microdata to HUD's specification each year, and local
governments plan HUD spending against the result. Everything in it descends from the ACS. The
ACS's defining feature is a published margin on every estimate.

**CHAS serves 129 count columns and no margin on any of them** [D05-chas F1].

That is not a disagreement. On the one quantity both publish — renter households paying over
30% of income — CHAS falls inside the ACS's own 90% margin in **130 of 133** counties, median
difference **−3.5%**. It is the same estimate with the interval removed. And the interval was
not small: the ACS margin runs a median **24.6%** of the estimate, p90 **46.0%**, max
**101.7%**. Someone allocating funds on a CHAS count in the median county is working from a
figure the survey underneath could not pin down to better than a quarter of its own size.

**It runs a full release behind, and the default moves.** The current tabulation is ACS
2018–2022 while ACS 2023 is published; `2019-2023` returns HTTP 200 and no rows. Over that gap
the same quantity moved more than 10% either way in **53 of 133** counties [D05-chas F2] — a
comparison against the current ACS would charge the calendar to the tabulation. The API's
`year` defaults to "latest", and HUD's own documentation lists ranges only to 2014-2018 while
later ones are served: *the documentation is not the authority on which vintages exist.*

**An empty column is a schema claim, not a data gap.** 2,660 of 17,157 cells are empty, all
accounted for by **20 columns empty in every one of 133 counties, with 0 varying between them**
[D05-chas F3]. Disclosure suppression responds to cell size and must therefore vary; this does
not. All 20 are the "cost burden not available, no other problems" family, which HUD's release
note says was **combined** into the neighbouring category. The measure was retired; the column,
the dictionary entry and the empty field all remain.

**[rule]** Before calling an absence suppression, check whether it *varies across geographies*.
If it does not, it is not responding to the data, and the explanation is in the publisher's
release notes rather than in its cells.

**[rule]** Where a derived product drops its source's uncertainty, recover the source's interval
for the same quantity and report it alongside. **A missing margin is not a small margin.**

**[rule]** Never adopt a custom tabulation without establishing four things: what it is derived
from, how far it lags, what its suppression and category changes are, and whether its published
dictionary matches its data. §4 of D05-chas found three documentation defects by reading the
dictionary beside one response.


### 1.8 CDC PLACES — the modelled small-area estimate

Regimes 1 through 7 publish something that was, at some point, counted. PLACES does not. A
county value is a **multilevel-regression-and-poststratification prediction** built from BRFSS
respondents who may not include anyone in that county, and its published interval is a
credible interval on that prediction rather than a margin on a sample.

The distinction is measurable and it is the reason the source needs its own regime. An ACS
margin shrinks with the square root of population; a PLACES interval is **essentially flat in
population** [D04 F1]. So the reflex that serves an analyst well everywhere else — read a wide
interval as thin local evidence, a narrow one as thick — inverts here. A narrow PLACES interval
can sit over a county that contributed no respondents at all.

**[rule]** Never read a modelled interval as a statement about local sample size. It is a
statement about how confidently the model predicts, which is a different quantity and is
largest exactly where the model is most strongly pooling toward its covariates.

PLACES also supplies this corpus's cleanest case that **reliability and rank identifiability
are different questions** (§7.1, §7.2). Diabetes reaches a pooled reliability of **0.853** with
every Virginia county clearing the **0.7** publishing convention, and still yields **0**
determined ranks, with a median rank span of **97** of **133** counties [D04 F2]. And
reliability is a property of a measure *and its comparison set*: asthma's pooled reliability is
**0.43** across US counties and **0.07** within Virginia, on identical interval widths [D04 F6].

One trap specific to the source: crude and age-adjusted prevalence ship under near-identical
column names and are not a calibration choice. For asthma and obesity they move the level and
leave the order (rank correlation above **0.95**); for diabetes they reorder the state, rank
correlation **0.68** [D04 F5]. Nothing raises an error if the wrong one is used.


### 1.9 Opportunity Atlas — the linked longitudinal cohort

A vintage is normally a date. Here it is a **cohort**: children born **1978**–**1983**, measured
at age **35**, located by where they *grew up*. The last outcomes were observed around **2018**,
which is also the publication year — a coincidence that makes 2018 look like a defensible
reference period. It is not. What a county value characterises is that place during the
cohort's childhood, and the number does not move when the county does [D10 F1].

**[rule]** When a source's reference period is a cohort, write the cohort into every caption.
"2018" is not a vintage here; it is the year the last member turned 35.

Two further properties earn the separate regime.

**Disclosure protection applied evenly removes unevenly.** In Virginia the pooled estimate is
present for all **133** counties, the Black estimate is missing for **14**, the Hispanic
estimate for **43**, and only **119** counties support a Black/White comparison at all [D10 F2].
A statewide gap computed from what survives is computed over a non-random subset and is not the
state's gap. The rule generalises: a uniform suppression threshold applied to unequal
populations is a *patterned* deletion, and the pattern runs along the dimension the analysis
usually cares about most.

**The noise is visible in the counts.** Every published count of children carries a fractional
part — **133** of **133** [D10 F3]. A count cannot be fractional, so the decimals are the
injected privacy noise made legible, and small counts are proportionally more perturbed.

This is also the source that settled §7.2's open objection, because it is *measured* rather than
modelled: reliability **0.916**, **98%** of counties above **0.7**, interval narrower than the
between-county spread (ratio **0.89**) — and still **0** determined ranks [D10 F4]. Rank failure
is neither a modelling artifact nor a precision problem.


### 1.10 Census BDS — exact values, unusable sums, and a protection regime with an issue date

BDS is the only source here whose published values are exact to the unit and whose *aggregations*
are almost never what a reader expects. Three unrelated mechanisms break "the parts sum to the
whole", they act in opposite directions, and the one analysts are trained to watch is the
smallest by a factor of several hundred.

**Noise infusion is real, documented, small, and undetectable by the obvious test.** The method
is *hybrid balanced multiplicative* — the multiplier is applied to each establishment record
before tabulation — so any sum of the same perturbed records is internally consistent. Across
**19** NAICS sectors in one state the count variables sum **exactly**, while the job-flow
variables Census names miss by at most **0.0302%** [D29 F2]. Nation against the sum of **51**
states: establishment gap **0.000%**, employment gap **0.000%** [D29 F3]. **Additivity therefore
cannot detect perturbation.** Nor can repetition: three identical requests returned **1** distinct
response, because the noise is fixed at tabulation rather than drawn per query [D29 F4].

**The firm count is not additive over any dimension, by construction.** Geography and industry
are defined at the establishment level, so a firm with establishments in several counties is
counted in each. The sum of states exceeds the national firm count by **3.73%**; summing counties
overstates firms in **50** of **50** states, median **10.44%** [D29 F5]. The error scales with how
finely the partition cuts: Spearman **0.746** against the number of counties, **-0.691** against
establishments per county, median gap **13.03%** in states with **90** or more counties against
**4.84%** in states with **20** or fewer [D29 F6].

**[rule]** Aggregate geography with `ESTAB`. Quote `FIRM` only at the geography it was published
for. There is no correction available from public data, because recovering it requires knowing
which establishments share a firm.

**County rows do not reconcile to their state, and the shortfall is not noise.** Counties fall
short in **50** of **50** states (sign test p=**1.8e-15**), median **-0.71%** of establishments
and **-3.43%** of employment [D29 F7]. The cause is documented: statewide (**999**) county codes
hold "establishments without a fixed location such as employee leasing establishments", and the
API does not serve them. The signature is decisive — NAICS **56** loses **36.23%** of its
employment against **2.08%** of its establishments, a ratio of **17.4**, and accounts for
**70.6%** of the national deficit [D29 F8].

**[rule]** When sub-geography sums fall short of a parent, the ratio of the employment gap to the
establishment gap separates **coverage exclusion** from **cell suppression**. Near one means whole
rows were removed; far above one means a few very large records were held out. Measured across
nineteen sectors the rank correlation between suppressed-cell count and that ratio is **-0.711**
(p=**0.001**) [D29 F8b]. This generalises past BDS and is offered as a diagnostic, not a
decomposition: each sector's gap still contains both mechanisms.

**A withheld cell is published as the number zero.** BDS carries QCEW's trap under CBP's regime:
**7,568** of **59,736** county-by-sector cells are flagged `D` (**12.67%**), against **1** of
**969** at state level, and every one of them arrives as `0` unless the `_F` column is requested
[D29 F9]. The totals are unaffected — a zero and a skipped NaN contribute the same nothing. What
changes is whether the frame supports a sentence about economic structure or a sentence about
data availability.

**`DENOM` is not the denominator.** It is the DHS *employment* denominator. Used for an
establishment entry rate it misses the published figure by a median of **9.34** percentage
points; the in-vintage DHS average reproduces **133** of **133** exactly [D29 F10]. The
prior-year count must be derived inside the current vintage as `estabs + exits − entries`:
reading it from the previous published file disagrees for **27** of **133** Virginia counties
(**20.3%**), by up to **6** establishments [D29 F11]. That particular error is negligible at this
geography and free to avoid, which is the only reason to state both facts together.

#### The regime is a dated policy variable

Every figure above was protected by a method that is now prohibited. Department of Commerce
**Administrative Order 216-26**, *"Disclosure Avoidance for Statistical Products"*, effective
**4 June 2026**, §5.01(c): *"Noise infusion shall not be used for any statistical product."*
§5.02 makes **coarsening** the preferred replacement and permits **suppression** "as a last
resort". Census's methodology page now carries a standing notice that its description is no
longer current, and the Bureau's own transition guidance names ACS (full transition by 2029) and
the 2030 Census (demonstration product mid-2027) without giving BDS a date.

This is the tenth regime and it is not a property of a source at all. **The protection method
has an issue date, a successor, and different error structure on each side of it**, and nothing
in the values announces the change. A time series that spans it is not homogeneous.

**[rule]** Record the disclosure-avoidance regime in provenance alongside the vintage.
`fetch_bds` does. Without it the information is unrecoverable from a stored artifact, because
the published numbers look identical either way.

**[rule]** The digit distribution is a cheap detector and belongs in any pipeline reading a
post-2026 federal release. Noise infusion leaves last digits flat; coarsening concentrates them
on 0, or on 0 and 5. Measured on this vintage: **3,142** county employment values, chi-square
**7.47** on 9 df, p=**0.589**, **10.9%** ending in zero against **10.0%** expected [D29 F1]. The
limit is explicit — the test sees rounding, not withholding, and would pass unchanged on a file
protected entirely by suppression.



### 1.11 BEA ACPSA — the satellite account, where the definition is the error bar

Every regime so far publishes something that was, at some point, observed — counted,
surveyed, linked, or predicted. A **satellite account** does not. The Bureau of Economic
Analysis takes value added that is already in the national accounts and re-sorts it under a
published decision about which industries, and which *shares* of which industries, constitute
arts and cultural production. Nothing is sampled, nothing is withheld, nothing is perturbed.

The consequence is a source that passes every structural check in this handbook and is still
capable of being read catastrophically wrongly.

**Its consistency is guaranteed and therefore uninformative.** Subtotals reconcile to their
total within **0.0000000%**, the leaf industries plus the residual line within **0.0000003%**,
and the **51** state rows to the US row within **0.0000003%** [D11 F5]. In a survey or a
register, ragged totals are a warning sign; here exactness is a property of double-entry
accounting and says nothing about whether the boundary is right. The account would balance
just as perfectly under a completely different definition.

**[rule]** Do not read reconciliation as validation. Ask first whether the product is a
measurement or an allocation; if it is an allocation, the totals were going to add up whatever
the definition was.

**The boundary is doing nearly all of the work.** ACPSA value added is **$1,169.8B**,
**4.24%** of US value added in 2023. Performing arts companies, promoters, agents, independent
artists, museums and fine-arts education together supply **9.6%** of that [D11 F1]. The three
largest lines that no lay reader would call arts — other information services, broadcasting
and government — supply **39.8%**, and the single largest industry in the account is *other
information services* at **15.5%** [D11 F2]. Core arts is **22.7%** of the account against
**74.7%** for supporting production [D11 F3].

**When there is no uncertainty to propagate, vary the definition instead.** This is the
handbook's answer to a whole class of sources and D11 is its worked case. The published
statistic is a location quotient, reconstructible from the value-added table to a median
**0.00380** [D11 F6], so it can be rebuilt under alternative boundaries. Against a core-arts
definition the published ranking has Spearman **0.852**, median move **4** places, max **31**,
with **7** of **51** states moving more than ten [D11 F7]. And it tracks a
supporting-industries measure (**0.978**) more closely than a core-arts one — the headline arts
statistic is very nearly a supporting-industries statistic wearing an arts label [D11 F8].

The single case that makes it concrete: the state ranked **1** on the published measure ranks
**32** on a core-arts one, and it has the **lowest** core-arts content of any state, **5.8%**
of its own ACPSA value added against a national **22.7%** and a maximum of **31.7%** [D11 F9].
Only **6** of the published top **8** survive the change of boundary [D11 F10].

**[rule]** A statistic with no published uncertainty is not precise; it is unquantified.
Report the sensitivity of the conclusion to the definition, and treat that as the error bar,
because it is the only one available.

**Three mechanical traps, all of which look like data.**

- **The line codes are not a flat list.** A grand total, a subject total, three subtotals and
  thirty-four leaves arrive as sibling rows with no depth column. Summing the value column of
  the 39-row national response gives **26.54x** the true total, because line 1 is total value
  added of the **whole economy** rather than an arts line [D11 F4]. `fetch_bea_regional` adds
  a `LineRole` column for exactly this.
- **The named industries are not a partition.** The leaves sum to **2.5801%** less than the
  total, because *all other industries* is a residual subtotal with no leaf lines beneath it
  [D11 F5b]. A reader who adds the industry rows to check their work finds a shortfall that is
  not an error.
- **An error arrives as HTTP 200.** A rejected request returns status 200 with `BEAAPI.Error`
  and no `Results`. Code that branches on the status line reads it as an empty result set —
  and BEA also answers an unrecognised geography (`GeoFIPS=US`) with a zero-row *success*.

**No vintage is selectable.** The Regional endpoint exposes four parameters and none of them
chooses a published vintage, while `Year` is optional and defaults to `LAST5`, a window that
moves with each annual release. Any revision is invisible from this interface [D11 F11]. This
extends §5.5: FRED remains the only source in the corpus that serves a past vintage, and BEA
is the clearest case of a source whose *default* silently moves.

#### The credential the source hands back

BEA is the only source here that echoes the submitted key inside the response body, at
`BEAAPI.Request.RequestParam[i].ParameterValue`. `redact` cannot reach it: that function
scrubs strings on their way into an error message, and a parsed payload is not a string — it
becomes a DataFrame, a `print`, and a stored notebook output as structured data no display
filter sees. The block is therefore removed from the document before anything else reads it,
and the provenance hash is taken over the **stripped** payload [D11 F12].

**[rule]** Hash what you would show another analyst, not what the wire returned. Hashing a
body that contains your own credential gives every analyst a different digest for identical
data, so nobody can ever verify anybody's provenance record. `tests/test_bea.py` pins this by
running the same payload under two different keys and asserting one hash.



### 1.12 Social Capital Atlas — when part of the uncertainty is a policy choice

Every published uncertainty in the preceding eleven regimes is a statistical property: it says
how much of the world went unobserved. This source is the first here where part of it says how
much the publisher **chose not to reveal**, and the first to state the choice as a number.

The mechanism is documented completely — Laplace noise at **ε = 8**, a smoothed sensitivity
term, and minimum cell sizes of 100 below-median-SES and 100 above-median-SES users. So is the
consequence, in the release's own definition of the standard-error columns: *"the standard
error of economic connectedness, incorporating both sampling error and error from the addition
of noise to protect privacy."* Epsilon is a dial. A different setting would have produced a
different published standard error for the same underlying network.

**And the two components cannot be separated from what was released.** The obvious test —
regress log standard error on log unit size, since sampling error falls as N^-0.5 and Laplace
noise scaling as 1/N falls as N^-1.0 — returns slopes of **-0.308**, **-0.292**, **-0.155** and
**-0.342** across the four geographies, none near either hypothesis. The reason is in the
regressor, not the mechanism: the noise depends on the within-unit degree distribution of
below-median-SES users, which is not published and could not be without defeating the noise,
and no size column in the files is the count the formula uses. The two county proxies correlate
**0.961** in logs and still give slopes **0.036** apart [D21 F4].

**[rule]** When a publisher combines statistical and disclosure error in one figure, record
that it did, and stop. Do not estimate the split from published size variables unless the
publisher says the noise is a function of one of them. The regression is available, looks
reasonable, and answers a different question.

**Two absences, and a file can only show one.** The cell-size rule removes whole units before
publication and separately blanks statistics for units that survive. Removal rates span a
factor of **92** in one release — **0.2%** of counties, **3.3%** of colleges, **18.4%** of high
schools, **20.8%** of ZIP codes — and leave no row, no flag and no gap behind them [D21 F1].
Blank estimates inside the file add **17.6%** of published ZIP rows and **19.7%** of
high-school rows, taking usable coverage of the stated universe down to **65.3%** for ZIPs
against **97.5%** for counties [D21 F2].

**[rule]** Carry the publisher's universe count into the code. A file that lost a fifth of its
units looks exactly like a file that never had them, and the suppression rate silently becomes
zero.

One cheaper trap sits alongside: the four size columns are four different quantities —
`mean_students_per_cohort` counts one year, every other column counts the whole unit — and no
units are recorded anywhere in the files. A cross-geography comparison of unit size is
available, looks reasonable, and is wrong by a factor of about four for colleges.

**The universe is a platform, not a population.** Facebook users aged 25–44, active in the
previous 30 days, with at least 100 US friends and a valid residential ZIP on one day. No user
count is published at any geography, so platform coverage cannot be checked against population
anywhere, and every representativeness claim rests on the publisher's caveat rather than on
measurement.



### 1.13 FBI Crime Data Explorer — when the coverage is the variable

Twelve regimes describe sources that measure something and report, with varying honesty, how
well. This one reports whatever agencies volunteered to report, and **the set of volunteers is
itself a time series** that moves for administrative reasons and moves differently in
different places.

Give the publisher its due first, because all three of these are more than most sources do,
and all three were verified rather than assumed.

**Participation is published per agency.** Every agency carries `is_nibrs` and, if it reports,
`nibrs_start_date` — the date it entered the measurement, which nothing else in this corpus
publishes. Across four states and **3,552** agencies the share reporting runs from **17.0%**
(Pennsylvania) to **100.0%** (Virginia), and the largest single adoption year in 2016–2023 is
**2021**, with **515** agencies joining [D13 F1].

**Coverage is published per month** — as `participated_population`, and as a percentage. And it
is filed under `tooltips` → `Percent of Population Coverage`, a key a charting library uses for
hover text. The variable that decides whether a crime series is comparable across years is
presented as chart furniture [D13 F2].

**Rates are normalised by the covered population, not the resident population.** Reconstructing
the published rate both ways across ten states gives a mean absolute error of **0.0024** against
the covered denominator and **1.6534** against the resident one [D13 F3]. The obvious
recomputation — offences over the `population` column sitting in the same response — disagrees
with the publisher by more than the year-on-year variation in crime.

**[rule]** When a response carries two plausible denominators, reconstruct the published figure
before using either. A column's name is not evidence of what was divided by what.

And none of it is sufficient.

**A coverage figure certifies the denominator, never the numerator.** It counts population
served by agencies in *some* reporting arrangement. It does not say those agencies filed usable
counts. In Florida, **54** of **60** months across 2016–2020 carry fewer than 200 offences, with
a median month of **4**, while mean reported population coverage over the same window is
**99.82%** [D13 F4]. An analyst who checks the coverage field — the correct instinct — is waved
straight through.

**[rule]** Before trusting a series, look at the counts for the period you intend to use. A
median month near zero beside a maximum month in the tens of thousands is a reporting artifact
whatever the coverage column says.

**The coverage figure supports refusing a comparison, not repairing one.** Across ten states the
correlation between the change in coverage and the change in the published rate is **+0.293**
(p=**0.411**); after dropping the state that fails the data-quality screen above it is
**+0.199** on nine. Among the screened states losing more than twenty points of coverage the
rate fell in **4** and rose in **1** — a tendency, with a sign reversal in it: New York
**-78.6%** against Pennsylvania **+35.5%** [D13 F5]. Whether losing an agency raises or lowers a
measured rate depends on whether its jurisdiction sat above or below the state average, and one
number cannot encode that.

**[rule]** If an analysis needs the transition years, fix the agency set and compare only
agencies reporting throughout, accepting a smaller named universe. Do not reweight by coverage.

#### An outage is not a zero

The FBI backend behind api.usa.gov returns HTTP 503 intermittently and recovers within seconds.
During this build the same endpoint failed and then answered on the next call, while a different
endpoint that had worked fifty-one times consecutively failed. A client that treats that as an
empty result publishes a table in which a state has no violent crime — and it passes every
structural gate in this corpus, because the schema is right, the types are right and the number
is a number. `fetch_fbi_cde_summarized` retries **5** times and then raises a distinct error
naming the outage [D13 F6].

**[rule]** Give an intermittent upstream its own exception type. "Unavailable" and "absent" must
not be representable by the same value, and a 404 is neither — on this API it means the path
shape is wrong, so retrying it only spends the budget the real outage needs.


### 1.14 EPA TRI — epistemic provenance, one record at a time

Thirteen regimes qualify a dataset, a cell, or a series. This one qualifies **every individual
observation**: each TRI release record carries a basis-of-estimate code saying how that number
was produced — continuous monitoring, periodic monitoring, mass balance, published emission
factors, site-specific emission factors, or best engineering judgment. No other source in this
corpus attaches an uncertainty statement at the row.

It is also a **regulatory self-report**. Facilities above statutory thresholds report their own
releases; EPA neither measures nor verifies them. The universe is a threshold, not a sample, so
a facility's absence is not evidence that it released nothing.

**Most published quantities are not measurements.** In Virginia reporting year 2022, of **2,100**
applicable release records, **263** — **12.52%** — rest on monitoring of any kind, and just
**16** (**0.76%**) on continuous monitoring. The single largest category is `O`, "other
approaches such as engineering calculations or best engineering judgment", at **32.00%** of
records [D12 F1].

**The code encodes the reporting situation as well as the method.** Among records carrying a
numeric quantity, `O` returns exactly zero **53.6%** of the time against a median of 0.00 lb,
while site-specific emission factors (`E2`) return zero **4.5%** of the time against a median of
258.54 lb [D12 F2]. `O` is substantially the code a filer uses to say *we judge this to be none*,
which is a caution against reading the codes as an ordered quality scale.

**[rule]** A per-record provenance flag is data about the observation, not metadata about the
file. Report the distribution of the flag before reporting anything computed over the values.

#### The weighting is a claim, and a weighted quality statistic needs a stability check

The same question — what share of this series rests on measurement? — has two defensible
answers. Counting records gives **12.52%**; weighting by pounds released gives **39.88%**, the
more reassuring figure and the one a reader interested in total mass would reach for [D12 F3].

The second is one facility. The largest single release, **8,096,003** lb, is **31.51%** of every
pound in the slice and is coded `M2`; removing that one row of **2,016** takes the mass-weighted
share to **12.22%** — within a third of a point of the record-weighted figure. Leave-one-out over
the twenty-five largest records spans **12.22%** to **42.22%** [D12 F3].

The obvious defence of the mass weighting — that large releases are the ones facilities actually
monitor — is testable and fails. Across size deciles the monitored share runs **4.2%** to
**20.3%** with no trend, and Spearman's ρ between release size and the monitored flag is
**+0.0280** (p=**0.288**, n=**1,439**) [D12 F4]. The mass-weighted excess is not a tendency to
measure large releases; it is one facility that monitors periodically and happens to account for
a third of the state's mass.

**[rule]** Before quoting a magnitude-weighted quality statistic, drop the largest observation
and quote the difference. Over a concentrated distribution, a statistic that moves tens of points
on one observation is describing that observation, not the population.

#### Directional does not imply material

Small releases may be reported as a **range code** rather than a number. EPA's Data Dictionary
states the stored amount is the range midpoint — code `1` is 1–10 lb, code `3` is 11–499 lb,
code `4` is 500–999 lb. The API does not honour it: every range-coded row returns
`total_release` as null while `release_na` marks the release **applicable**. A naive `sum()`
drops them, and drops them from the small end.

Bounded in both currencies, the hole is **84** of **2,100** records — **4.00%** — and **8,437**
lb against **25,690,634** reported, or **0.0328%**. Even placing every range-coded release at its
band maximum gives **0.0605%** [D12 F5]. The loss is real and one-directional and negligible in
mass; it is a genuine bias for anything that counts or ranks records.

**[rule]** When documentation and API disagree, implement the documentation in a **separate**
column and never merge it into the reported value. A reconstruction of what should be stored is
not a reported quantity.

**[rule]** Bound a known gap in records *and* in magnitude before describing it. "Directional"
predicts the sign and says nothing about the size.

#### A documented vocabulary change is not a clean cut

The basis-code scheme changed at reporting year 2007: `M` split into `M1`/`M2` and `E` into
`E1`/`E2`. The documented year invites filtering old codes before it and new codes after. Both
schemes appear on both sides. Virginia's 2006 filings already carry **5** new-scheme records, and
its 2008 filings still carry **10** retired-scheme ones. Over 2006–2008 the state filed **1,154**
monitoring-based records, of which a filter written as `code == "M"` catches **443** and silently
drops **711** [D12 F6].

**[rule]** Treat a changed vocabulary as a set union (`{M, M1, M2}`), never as a function of the
year. The change date tells you when the new codes were introduced, not when the old ones stopped
being used.

#### A full page is not a full answer

Envirofacts caps a response at **10,000** rows and signals truncation in no way — no flag, no
next-page link, no partial-content status, no error. The Virginia 2022 query matches **12,069**
rows, so a single unpaged call returns a well-formed, complete-looking array missing **17.1%** of
the answer [D12 F7]. The only signal available is the service's own `count` endpoint.

The same service degrades sharply near its cap: 2,000 rows returned in 11.4 seconds and 5,000 in
21.0, while a 10,000-row request did not return inside 175 seconds. The client therefore pages at
**2,000**, well below the ceiling, and reconciles the assembled length against the declared count.

**[rule]** For any paged API, ask for the count before asking for rows, and refuse to return a
frame whose length disagrees with it. A response that fills the page is the one case where
success and truncation are indistinguishable from the response alone.

#### Is it the regime or the state?

Across Virginia, Delaware, Rhode Island and West Virginia in reporting year 2022, the
record-weighted monitored share runs **4.55%** to **18.47%** while the mass-weighted share runs
**7.69%** to **62.92%**. The direction of the single-record effect is not even stable: dropping
the largest record moves the mass-weighted share down in Virginia and Rhode Island and up in
Delaware and West Virginia. One figure holds everywhere — continuous monitoring is **0.60%** to
**1.14%** of records in all four states [D12 F8].

**Under one percent of published TRI release quantities rest on continuous measurement. That is a
property of the programme.**

#### Why this source cannot join §7.3

TRI publishes no interval: no margin of error, no confidence bound, no suppression threshold, no
privacy parameter. §7.3 tracks how much precision is needed before a ranking is determined, and
the quantity that series needs does not exist here.

The absence of a stated uncertainty is not the absence of uncertainty. What TRI offers instead is
better in one respect — the statement is per record, so it can be aggregated however the question
requires, which no interval-based source in this corpus permits — and worse in another: it is
categorical. "Best engineering judgment" carries no error bar. You can say **32.00%** of Virginia
records rest on judgment [D12 F1]; you cannot say what that does to a total, because nothing
published relates a judgment-based estimate to a measured one.

**[rule]** Record which sources publish no uncertainty *statement* separately from which publish
no uncertainty. The first is a documented gap you can describe; the second does not exist.


---

## 2. The sentinel catalogue

Everything in this table returns **success** and is wrong.

| Source | Trap | Detection |
|---|---|---|
| Census (all datasets) | Rejected key returns **HTTP 200** with an HTML "Missing Key" page | Check the body and content type, never `status_code == 200` alone [D01] |
| Census ACS | **Jam values** in numeric fields: `-666666666`, `-999999999`, `-888888888`, `-777777777`, `-555555555`, `-333333333`, `-222222222`, `-111111111` | `ACS_SENTINELS` in `sources.py`; coerced to `NaN` on read |
| Census ACS | `get` accepts at most **50** comma-separated names; 51 returns a bare HTTP 400 with no body, indistinguishable from a malformed geography | `CENSUS_GET_CEILING`; `fetch_acs_wide` batches and **verifies every batch returned an identical geography key set** before joining |
| BLS (all) | Failure signalled with **HTTP 200** and `status: REQUEST_NOT_PROCESSED` | `fetch_bls` checks `payload["status"]`, and fails closed if any requested series is absent from the response |
| BLS (all) | At most **50** series per request | `BLS_SERIES_CEILING` |
| BLS QCEW | Suppressed cells published as literal `0` | `QCEW_SUPPRESSED = "N"`; suppressed numerics → `NaN`, `suppressed` column added |
| FRED | Missing observations encoded as the string `"."` | `FRED_MISSING` |
| FRED | An open-ended date range makes every derived number change on re-run | `fetch_fred` requires **both** `start` and `end` |
| BLS QCEW (and any server that ignores unknown query parameters) | An **invented query parameter accepted and silently ignored**: `?vintage=1970-01` returns byte-identical current data with HTTP 200. The caller believes they retrieved a past vintage | Send a nonsense value and compare digests. `scripts/measure_vintage_retrievability.py` does exactly this |
| HUD CHAS | An unrecognised id returns **HTTP 200 and `[]`** rather than 404. A zero-padded county code — the spelling the same publisher's FMR API *requires* — silently yields nothing | `fetch_chas` strips the padding and raises `EmptyResultError` on an empty body. An empty frame is not an empty population |
| HUD CHAS | A **county index that repeats itself**: 267 rows for 134 counties. Iterating it as served double-counts every household in the state | `fetch_chas_county_list` deduplicates and reports how many rows it removed |
| Any publisher behind a firewall | A **bot challenge returned as HTTP 202 with a zero-length body** and `x-amzn-waf-action: challenge` (AWS) or `cf-mitigated` (Cloudflare). 202 is a success code, so every `status_code < 400` check accepts it and parses nothing | `reject_bot_challenge` runs after every request in `sources.py` and raises `WafChallengeError`, naming the cause. HUD challenges `/portal/` (the bulk files) and not `/hudapi/` (the API) |
| Census CBP | Unpublished cells are **absent**, not flagged | No automatic detection is possible. Cross-source roster comparison is the only method [D15] |
| HUD FMR | A publisher's **machine-readable distribution is not the operative schedule**, and says so nowhere | No sentinel exists. HUD's ArcGIS layer matches FY2027 in **0 of 2,606** areas, FY2026-as-published in **2,604**, carries the revised values for **0** of the 7 revised areas, matches neither publication in **2**, and has no fiscal-year field [D05 F3]. The only detection is to hold it against the authoritative publication and count |

### 2.1 What the sweep found

Every fetcher in `sources.py` was run against a firewall challenge and an empty body with an
injected session (`tests/test_fetcher_response_contract.py`, no network). Two things came out
of it, and the difference between them is the useful part:

**Failing was never the problem.** All five original fetchers already tested
`status_code != 200` rather than `< 400`, so no challenge was ever accepted as data. That is
the discipline in §2 paying off before anyone knew this trap existed.

**Failing with the wrong cause was.** Only the HUD path named a challenge as a challenge; the
others raised "returned HTML rather than JSON" or a transport error, which sends the reader to
debug a parser or a proxy. That is exactly the afternoon §11 records. `reject_bot_challenge`
now runs in all six.

And one genuine defect the sweep turned up: `fetch_qcew` surfaced an empty body as pandas's
`EmptyDataError` — **outside the `DataAccessError` hierarchy**, so a caller following the
documented contract would not catch it. Now a `ResponseShapeError`.

**[rule]** An error must name the cause, not just refuse the data. A gate or a fetcher that
fails for the wrong stated reason costs more than one that fails silently, because it is
believed.

**[rule]** A misaligned batch join would corrupt every derived rate in the notebook
without raising. The geography-key verification in `fetch_acs_wide` is not defensive
padding; it is the check that makes multi-batch ACS retrieval safe at all.

---

## 3. Denominators, universes and partitions

Four of the eleven notebooks found their largest error in a denominator. This is the
corpus's most frequently confirmed failure mode.

**Published totals are often not the right base.** In the ACS rent-burden table, the nine
burden brackets plus "Not computed" sum to the published universe in 3,222 of 3,222
counties; **the brackets alone fall short in 3,218** [D27-rent F1]. "Not computed" is a
median 13.4% of the renter universe and reaches 100%. Correcting the denominator raises
the burdened share by a median **+5.48 pp** (90th percentile 13.2 pp, max 61.1 pp) and
moves **2,485 of 3,220 counties by 100 ranks or more** [D27-rent F2].

That correction was settled externally, not by argument: the corrected base reproduces the
Bureau's own DP04 percentage in **3,220 of 3,220 counties** (max difference 0.099 pp,
DP04 rounding to 0.1), while the published-total base matches in **14** [D27-rent F0].

**[rule]** Where the Bureau publishes a derived percentage for the same quantity, reproduce
it. Internal consistency is not validation [D01 takeaways].

**Test that a set of rows is a partition before summing it.** Four ACS
internet-subscription rows exceed their parent total in **3,222 of 3,222 counties, by a
mean factor of 2.74×**, because households report multiple subscription types; the three
mutually exclusive rows sum to the universe exactly in 3,222 of 3,222 [D16 F1].
`tabulation.check_partition` exists for this and returns `EXACT`/`OVER`/`UNDER`.

**Name the universe.** `B15003` is a 25-and-over universe; dividing it by total population
is simply wrong [D01 takeaways]. The ACS publishes 195 income tables and **zero** wealth
tables — establishing that took one request, and assuming otherwise would have produced a
notebook about a quantity the data never contained [D06 takeaways].

**Ratio of medians is not the median of ratios.** Using renter income sits +0.52 pp from
the true median rent burden and correlates 0.761 with it, still moving 2,420 of 3,181
counties by 100+ ranks. Using **all-household** income — the version in common use — sits
**−10.18 pp** away and drops the correlation to 0.545 [D27-rent F3–F4].

**Open top brackets are not identified.** Where a percentile falls in an open bracket it is
bounded below but has no value. `brackets.py` raises `UnidentifiedPercentileError` rather
than interpolating; opt-in returns the lower **bound**, not a point estimate. The median
rent burden falls in the open "50 percent or more" bracket in 6 counties [D27-rent F5].

**Weight before aggregating.** A simple average of county median rents misses the published
state median by a median of **−181 USD**; population weighting cuts that to +10 USD but
still errs by more than 25 USD in 10 of 51 states, peaking at 84 USD [D27-rent F6].

---

## 4. Source selection

*This section answers D15 exercise 6.*

### 4.1 CBP or QCEW

**Use QCEW when the question is about which industries exist, how concentrated they are,
or what is missing.** QCEW's suppression is visible: it names the industry, publishes the
establishment count even when withholding employment, and flags the withholding. That
makes the missingness measurable — and in this corpus the missingness was repeatedly the
finding [D09 F4, F5].

**Use CBP when the question needs a value in every cell of a fixed roster and the roster
is known to be adequate**, and only then. CBP's completeness is an artifact of what it
chose to publish, not of what exists.

**Use both when the question is about coverage itself.** The comparison is the only
available detector of silent omission [D15 F2–F3].

**Never treat the two as interchangeable measurements of the same quantity.** Where both
disclose, they correlate but do not agree: log-employment correlation 0.875 over 275
shared industries, yet only **17% within 10%** of each other, **28% differing by more than
2×**, and CBP running **+30% higher in total** [D15 F4]. The universes genuinely differ.
It follows that the 327-industry non-overlap **cannot** be attributed to disclosure policy
alone — which is itself the cost of silent omission: *disclosure and universe are
indistinguishable from the data.*

**Never substitute one for the other mid-analysis** — not across years, not across
geographies, not for a few missing cells. A CBP value dropped into a QCEW frame imports a
+30% level difference and a different universe with no visible seam.

### 4.2 ACS or an administrative source

ACS when you need uncertainty quantified, small-area detail, or household characteristics
no administrative file carries. Administrative (LAUS, QCEW) when you need the population
rather than a sample, and can accept that the uncertainty is unpublished.

They will disagree, and the disagreement is usually about definition. See §6.

### 4.3 A note on source choice as a finding

In three of the eleven notebooks the source-comparison *was* the result — the point was not
which number is right but that the choice of source is a substantive decision that moves
the answer [D02 F5, D15 F4, D27-gent F4]. Where a corpus notebook makes a source choice
that another reasonable analyst would make differently, the notebook reports both.

---

## 5. The vintage policy

*This section answers D08 exercise 6.*

### 5.1 Which analyses must pin a vintage

**Must pin** — a vintage is required, and an unpinned run is a defect:

1. Any analysis whose output is **reported, cited, or compared against a prior run**. If
   the number will be read twice, it must be the same number twice.
2. Any analysis of **levels** from a chained series. Real PCE's levels are not comparable
   across vintages at all [D08 F2]; without a pinned vintage the comparison is undefined
   rather than merely noisy.
3. Any **as-of** or back-test analysis. The series available at a past date is shorter as
   well as different — on 2023-06-01 the nominal series ran a month shorter than it does
   now [D08 F5]. Using today's series to simulate a past decision is look-ahead bias.
4. Any **bulk file** (Zillow, HUD, Eviction Lab). These carry no vintage parameter at all,
   so the vintage is the retrieval, and the file must be hash-pinned. See §5.3.

**May use the current series**:

5. **Growth rates and other differences**, where cross-vintage correlation is 0.9932 (real) and 0.9933 (nominal) and
   mean absolute revision is 0.229 pp (real) and 0.242 pp (nominal) [D08 F3] — provided the notebook says so and the
   magnitude is large relative to that revision. This exemption does **not** extend to the
   *sign* of a single month's growth, which reversed between vintages in 3 of 51 months
   (nominal) and 7 of 51 (real) [D08 F4].
6. **Deflators used as deflators**, where the analysis is a ratio and a uniform rebasing
   cancels. D27-gentrification depends on this and tested it: the CPI choice moved 20
   counties across zero but **reordered none** — largest rank move 0 [D27-gent F3].

### 5.2 What the artifact must record, either way

Every notebook records, in `metadata.krl`, the flag `vintage_pinned` and, in its
provenance block, for each series: the series ID, the **explicit start and end dates**,
the vintage date if pinned, and the payload hash. `fetch_fred` requires both `start` and
`end` precisely so that an unpinned *range* cannot slip through alongside a pinned vintage.

`vintage_pinned` takes `true`, `"digest"`, `false`, or `not_applicable`.

- **`true`** -- the publisher will serve these numbers again: prior vintages on request, or each
  vintage a separately addressed immutable asset.
- **`"digest"`** -- the publisher will not, and the notebook holds the retrieval to a digest it
  recorded, so an upstream change **raises** instead of quietly reporting different figures under
  unchanged prose. This is a weaker guarantee and a different kind of one: it does not restore a
  vintage, it removes the silence. `verify_digest` in `src/krl_tutorials_data/sources.py` is the whole
  mechanism, and the pin is written at the call site where a reader meets it.
- **`false`** -- neither, with a note saying why a pin was not taken.
- **`not_applicable`** -- the artifact retrieves no external source, where a boolean would be
  false in both directions.

**What `true` asserts.** Not that the call names a year. That a **re-run returns the same
numbers, guaranteed by the publisher's own contract**: either prior vintages are served on
request, or each vintage is a separately addressed immutable asset. A source that revises and
serves only "now" cannot be pinned by naming a reference period, however explicit the argument
(§5.5, and §5.4 for what that reclassified).

**[rule]** `vintage_pinned: false` is permitted only with a one-sentence justification naming
which exemption or condition applies. It is not a default. The justification goes in
`metadata.krl.vintage_note`, where a gate can read it, **and** in the notebook's prose, where the
reader meets it -- both, or neither counts. `tests/test_gate_vintage.py` enforces all of it,
including that a notebook claiming `true` calls no fetcher that cannot pin.

The provenance block says which it is too: `DataProvenance.render()` prints `(pinned)` or
`(NOT pinned - the source serves no prior vintage; this retrieval is the only one)` from the
record's own `pinned` field, rather than asserting the first unconditionally as it used to.

### 5.3 Bulk files

A bulk file has no vintage parameter, so the pin is a **SHA-256 of the retrieved file plus
the retrieval date**. `connectors.BulkFileSource` makes `vintage` a required field — there
is no "latest" — and `verify_bulk_file` streams the digest and raises `BulkFilePinError` on
mismatch. Zillow ZHVI and ZORI for 2026-08 are pinned in `data/zillow/2026-08/SOURCES.md`.

### 5.4 Checking the existing notebooks against this policy

Run against all **33** notebooks, after the corpus was complete. The previous revision of this
section ran against eleven and concluded *"No notebook currently violates the policy."* Both
halves of that had stopped being true.

#### What the flag means, corrected

§5.2 requires `vintage_pinned` on every notebook. It was being read as *the call names a year* --
and by that reading QCEW, CBP, BDS, BEA and HUD CHAS all pass, which §5.5 then measured as
serving no prior vintage at all. **Naming a reference period is not pinning a vintage.**

The flag now means what §5.1 clause 1 needs it to mean: **a re-run returns the same numbers, and
the publisher's own contract is what guarantees it.** That is true in exactly two situations:

- the publisher serves prior vintages on request -- FRED/ALFRED, and only FRED; or
- each vintage is a separately addressed immutable asset -- an ACS release year, a named PLACES
  release, a dated bulk file with a recorded hash, a Dataverse file fetched against a pinned MD5.

Everything else revises and serves only *now*.

#### The result

| | Notebooks | |
|---|---|---|
| `vintage_pinned: true` | 19 | ACS release years, FRED with explicit start/end, PLACES 2025, the Opportunity Atlas and Social Capital Atlas static releases, Zillow 2026-08 hash-pinned, MIT/Dataverse against a pinned MD5 |
| `vintage_pinned: "digest"` | 8 | D02 (LAUS), D09 (QCEW), D11 (BEA), D12 (TRI), D15 (CBP + QCEW), D17 (Atlas bulk `.xls`), D28 (Socrata), D29 (BDS) |
| `vintage_pinned: false` | 5 | D05-fmr, D05-chas, D13, D26, D22 |
| `vintage_pinned: not_applicable` | 1 | D30 retrieves no external source |

**The thirteen were worked through one at a time, and eight took a pin.** Each of those was first
checked for digest *stability* -- a pin against a payload the publisher does not serialise the same
way twice fires on the serialisation and gets switched off within a week. D09 and D15 pin **every**
area they fetch rather than a sample, as a dict keyed by FIPS.

The five that did not are declined for stated reasons rather than left unexamined:

| Notebook | Why no pin |
|---|---|
| D13, D26 | The FBI CDE notebooks' **subject is coverage as published at fetch time**. Pinning the payload would contradict what they teach: the agency roster is meant to move, and a notebook that raised when it did would assert the opposite |
| D05-chas | The county sweep is paced at HUD's 60 requests a minute and the retrieval is an assembly of hundreds of responses, so validating a pin means re-running the whole sweep |
| D05-fmr | The ArcGIS layer is queried live **on purpose** -- establishing what vintage it holds is the finding -- and the four bulk files it is compared against are already hash-pinned under §5.3 |
| D22 | ~341 MB across four regional extracts replaced in place monthly. Every validation run would re-download the Business Master File; the cost is real and the pin is not worth it |

Each `false` carries a `vintage_note` naming the condition, and says it in prose as well, because
§5.2 requires the justification to reach the reader and not only the gate.

**Five of those thirteen were previously marked `true`** -- D02, D05-fmr, D05-chas, D09 and D15 --
and **twenty of the thirty-three had no flag at all**, every one of them built after this section
was written. §5.2 was prose, so nothing enforced it.

#### It is now a gate

`tests/test_gate_vintage.py` requires the flag, requires a justification naming a recognised
condition when it is not `true`, requires that justification to appear in the notebook's prose,
and **fails any notebook claiming `true` while calling a fetcher that cannot pin** -- which is the
check the old reading of the flag would itself have failed. `tests/test_provenance_pinning.py`
holds the per-source judgement and fails any new fetcher that takes the convenient default without
deciding.

#### And the provenance block was asserting it

`DataProvenance.render()` printed `(pinned)` after every vintage unconditionally. That line was in
the stored output of sixteen notebooks, three of them built on QCEW, CBP or LAUS. It now prints
which it is, and D02, D09 and D15 have been re-executed so their stored output says so.

**A correction, retained.** An earlier revision of this section said D05's files had to be pinned
because "the publisher's host is not reachable." That was wrong -- see §11. HUD's API on the same
host works with a key, and D05 uses it. The files are pinned for reasons about the source rather
than the network: the API serves one entity per request under a 60/minute limit, and it serves
**only the current value**, so FY2026-as-first-published -- the file the revision is measured
against -- has no API equivalent at all. *A source that only ever serves "now" cannot answer a
question about what it said before.* That sentence is now the general rule and the reason D05-fmr
reads `false`.

#### The outstanding QCEW/CBP question, resolved as far as it can be

The previous revision closed: *"QCEW and CBP are revised, and this corpus has not measured by how
much... That is a gap, not a finding."*

It cannot be measured, and that is the finding. Re-checked 2026-09-15:

- QCEW answers **four** invented vintage parameters -- `?vintage=1970-01`, `?asof=2024-09-01`,
  `?version=1`, `?release=first` -- with HTTP 200 and a **byte-identical 265,757-byte** response,
  the same bytes as no parameter at all. §5.5 had measured one; all four behave the same way.
- The archived quarterly singlefile path returns **404**, and the download page answers **403** to
  this client.
- CBP's 2022 variable catalogue contains **no** variable naming a vintage, date, release or
  update.

Neither publisher ships an interface to its own history, so the revision magnitude is not
measurable from the publisher by any route a caller has. The pinned-period treatment therefore
rests on a documented property of the sources rather than on an unverified assumption, which is
a different and better position than the gap this section used to record -- and it is *why* those
notebooks read `false`.

#### What the corpus can do instead, and now does

`scripts/verify_provenance_reproducibility.py` re-issues every recorded request and compares the
digest against the one stored at build time. Running it is what turned up the next three findings,
each of which had been invisible because nothing had ever re-fetched anything.

**The digest was over unstable bytes at two of the corpus's sources.**

- **Census does not hold row order.** 25 identical requests to CBP 2022 county 51720 returned
  **3 distinct byte digests**, **1** distinct row multiset and **89** rows every time. The data is
  stable; the serialisation is not. A SHA-256 of the response body fails on roughly one request in
  twelve for reasons that have nothing to do with the data, so the recorded hash on every ACS and
  CBP record could not verify anything.
- **BLS puts the request's own latency inside the payload.** Three identical POSTs returned three
  byte digests and one identical `Results` object; the only difference was `responseTime`. Every
  BLS digest was unmatchable by construction.

Two bases now exist for this. `canonical-rows` hashes the header plus the **sorted** rows, and
`canonical-stable-json` drops declared volatile envelope fields before hashing. Both are lossy on
purpose and chosen **per fetcher**, never globally: sorting rows is correct for an unordered set of
geographies and wrong for a time series, where the order is the data, so FRED keeps
`response-bytes`.

**[rule]** Before trusting a content hash, fetch the same thing twice and compare. A digest over a
representation the publisher does not hold stable is not a content identifier -- it is a
false-alarm generator, and the corpus will learn to ignore it.

**A batched retrieval cannot record one batch as the request.** `fetch_acs_wide` and `fetch_bls`
split at their APIs' ceilings and join. Recording the loop's last body described a request
returning a fraction of the frame; both now record the batch count instead, and the sweep reports
them as what they are.

**And the record must not name the machine that wrote it.** The committed Zillow record carried an
absolute `file:///sessions/...` path from the sandbox that executed the notebook -- a path that
tells a later reader nothing and does not exist for them. Local sources now record a repo-relative
location.

**The result.** All **40** records now carry the fields, and the sweep accounts for every one with
a stated reason: **35 reproduced**, **1** pinned locally as a bulk file verified against its own
digest, **4** assembled from batched requests and therefore not reissuable as one. **Zero
unexplained differences.**

**Where provenance is written is also a claim, and it had drifted.** Eight notebooks resolved their
output directory as `Path.cwd() / "provenance"` and five as a repo-root-relative path. The two
conventions cannot both hold for one working directory: a run from the repository root wrote
**16** records into a stray folder at the top of the tree while the committed copies beside those
notebooks went stale, and nothing failed. Every notebook now anchors to the repository root found
by walking up from wherever it runs, and `tests/test_provenance_location.py` fails on a stray
folder, on a cwd-derived path, and on a machine-specific path in a committed record.

**[rule]** Provenance that cannot reissue the request is not provenance. Record the parameters,
redact the credentials, and re-run the sweep rather than trusting that a number is still there.

---

---

## 5.5 Retrievability of the past — a second axis

This corpus treated revision as one property. It is two, and the distinction decides whether an
analysis can ever be reproduced.

**Does the source revise?** and **can it be asked what it previously said?** are independent.
FRED does both: it revises heavily and ALFRED serves any vintage, which is why §1.3 could
measure revision at all. BEA revises and serves nothing.

| Source | Revises | Can you retrieve a past vintage? |
|---|---|---|
| FRED / ALFRED | Heavily | **Yes** — any vintage, by date |
| Census ACS 5-year | No; each release is a distinct product | **Yes** — prior releases stay published |
| **BEA** | Yes — four prior years in one release | **No** — 0 of 13 datasets offer any vintage, as-of or archive parameter |
| HUD CHAS | Yes — new tabulations supersede | **No** — the API serves only "the latest range" |
| HUD FMR | Yes — mid-year reevaluations | **Only if you kept both files.** There is no series; the revision is the difference between two similarly-named downloads |
| BLS LAUS | Yes — annual benchmarking | **No.** The v2 API has no as-of argument; `aspects` returns `[]` and the series catalog carries no publication date |
| BLS QCEW | Yes | **No** — and worse, see below |
| Census CBP / ACS | Yes | **No vintage selector.** 38 CBP endpoints span reference years 1986–2023, but `c_vintage` is the *reference* year, not the publication date |

BEA is the clearest case and the one measured here
(`scripts/measure_vintage_retrievability.py`). Every `Year` parameter across all thirteen
datasets selects the *reference period*, not the publication vintage. Meanwhile a Regional
response carries this note:

> "Last updated: February 5, 2026 — new statistics for 2024; **revised statistics for
> 2020-2023**."

Four prior years revised, announced in free text on the response, with no way to ask what the
series said the day before.

**What this disables.** Any as-of analysis, any back-test, and the reproduction of any prior
result — including your own from last quarter. D08 exercise 2 back-tests a rule on the
as-published series against the current one; that exercise is **impossible on BEA**, and the
reason is not that BEA is worse data but that it ships no interface to its own history.

**[rule]** Before using a source for anything that will be re-run or cited, establish both
properties. If it revises and serves no vintage, **your retrieval is the only vintage that will
ever exist**, so pin it — hash the payload, record the date, and keep the copy. §5.3's bulk-file
rule is the special case of this; the general rule is about sources, not files.

**QCEW does something worse than refusing.** A caller looking for a vintage will try
something, and QCEW answers every invented parameter with HTTP 200 and **byte-identical current
data** — `?vintage=1970-01` on a 2024Q1 request returns the same 356,635 bytes as no parameter
at all. The parameter is ignored, not honoured, and nothing in the response says so. The caller
believes they hold a 1970 vintage and they hold today's. An error would have been kinder.

**[rule]** Before trusting any parameter a source's documentation does not explicitly define,
send a nonsense value and compare the bytes. If the response does not change, the parameter is
decoration.

**[rule]** A revision announced only in prose is still a revision. Read the notes a response
carries; BEA's arrive in a `Notes` array that a client selecting `Data` never sees.

---

## 6. Documented cross-source disagreements

Both of these were tested rather than reported, and both tests are reproducible in the
notebooks.

### 6.1 ACS vs LAUS unemployment: +1.49 pp

ACS and LAUS disagree by a **median +1.49 pp**, and **51 of 51 states differ by more than
the ACS margin** — so the gap is not sampling noise [D02 F5]. ACS publishes a median margin
of 0.133 pp on this quantity; LAUS publishes none [D02 F6].

**Tested explanation:** the ACS figure is a 5-year window, LAUS an annual average. Matching
the reference period **closes 72% of the gap**. The residual still exceeds the margin in
40 of 51 states, and the notebook reports that rather than declaring the matter closed.

**[rule]** The two are not substitutes. An analysis that switches between them mid-series
introduces a ~1.5 pp step that will be read as a change in unemployment.

### 6.2 CBP vs QCEW employment: +30%

Covered in §4.1. The short form: CBP runs 30% higher in total, only 17% of shared
industries are within 10%, and the difference is universe, not disclosure [D15 F4].

### 6.3 A disagreement that is not a disagreement

The unemployment *rate* and the *level of employment* are different questions, and the
rate is close to uninformative about the level. Over 2019–2024 the correlation between a
state's change in unemployment rate and its change in employment was **+0.053**. The rate
fell in 19 states; in 2 of those, employment fell too — the rate improved because people
left the labour force [D02 F2–F3].

---

## 7. Rankings, and what a ranking is allowed to claim

The corpus's most consistent negative result: **published orderings of small geographies
are mostly not orderings.**

- Of 3,222 counties passing a CV screen on broadband access, **2,379 have a rank interval
  wider than 1,000 places and 0 have a determined rank**. The median county's interval
  spans **1,481 of 3,222 ranks**; 9 counties could occupy rank 1; of the published top 10,
  **7 have intervals reaching past rank 50** [D16 F4–F5].
- The coefficient of variation does not substitute for this. CV correlates **+0.27** with
  rank-interval width [D16 F4] — it screens estimate reliability, not rank identifiability,
  and `reliability.CVThresholds` carries a `source` string because the thresholds are an
  NCHS reporting convention, not a property of the data.
- Under age standardisation, 24 of 1,326 state pairs reverse order; **1** is distinguishable
  at 90% under independence and **0** under worst-case MOE correlation [D07 F3].
- Definitional choices reorder more than estimation error does. Two internet-access
  definitions correlate 0.765 and move **2,567 counties by 100+ ranks** [D16 F2].
  Correcting one denominator moved 2,485 of 3,220 counties by 100+ ranks [D27-rent F2].

**[rule]** A ranked table of counties is published with rank intervals or with an explicit
statement that ranks are not identified. `reliability.rank_intervals` computes the exact
interval-overlap bound.

### 7.1 How far down you can go, measured

§7 used to say county rankings "deserve far more scepticism than state ones", and §12 that at
tract level these results "should be assumed worse, not similar". Both were assumptions. One
quantity — broadband share, the same measure D16 ranks at county level — at three levels
(`scripts/measure_geography_escalation.py`, ACS 2023, Virginia below the state row):

| Level | Units | Median margin | Median rank interval | As % of units | Determined ranks | **Could be rank 1** |
|---|---|---|---|---|---|---|
| State | 52 | 0.27 pp | 8 | 15.4% | 3 | 3 |
| County | 133 | 2.65 pp | 54 | 40.6% | 0 | 9 |
| Tract | 2,074 | 5.85 pp | 1,481 | 71.4% | 0 | **810** |

The margin escalates **9.8×** from state to county and **21.7×** from state to tract. But the
margin is the least of it: **810 of 2,074 tracts — 39% — could occupy rank 1.** A ranking in
which two fifths of the units could be first is not a ranking, and no amount of care in
presenting it changes that.

Note also that the state level is not safe, only safer: the median state's rank interval spans
**8 of 52** places, and only **3** states have a determined rank.

**And it is not a property of Virginia.** The same measurement at tract level in five states
chosen to vary the two things that could explain it away — how many tracts a state has, and how
high the share is:

| State | Tracts | Median share | Median margin | Determined ranks | Could be rank 1 |
|---|---|---|---|---|---|
| California | 8,771 | 93.4% | 5.51 pp | 0 | 4,173 (47.6%) |
| New Jersey | 2,115 | 93.4% | 5.48 pp | 0 | 986 (46.6%) |
| Virginia | 2,074 | 91.2% | 5.85 pp | 0 | 810 (39.1%) |
| Mississippi | 864 | 82.1% | 8.53 pp | 0 | 187 (21.6%) |
| Wyoming | 157 | 89.1% | 5.87 pp | 0 | 50 (31.8%) |

"Could be rank 1" runs from **21.6% to 47.6%** across a 56-fold range in tract count and an
11-point range in median share. And the column that does not vary at all is the decisive one:
**across all 13,981 tracts in five states, not one has a determined rank.** Zero. The
ordering is unidentified everywhere, for every tract, in every state tested.

Mississippi is the useful control. It has the lowest share, so it is furthest from the ceiling
that compresses differences at the top — and it has the *widest* margins (8.53 pp) and still the
lowest "could be rank 1", because with 864 tracts there are simply fewer units to be confused
with. That is the shape to expect: the *share* that could be first scales with how many
neighbours a unit has, while the *failure to identify any rank at all* is universal.

**A coverage note, because this section is the exception.** These six figures come from a
script, not a notebook, so they carry no `[Dxx Fn]` tag and
`tests/test_handbook_traceability.py` does **not** check them — the gate verifies figures
against stored notebook output, and there is none here. They are reproducible by running the
script against live ACS with a Census key, and that is a weaker guarantee than every other
number in this document. Stated rather than left to be discovered.

**[rule]** Below county, do not rank — this is now a measured rule, not a cautious one. Report
the estimate with its margin, or aggregate up until the ordering is identified. "Assume worse"
was the right instinct and understated the result by a wide margin, which is the argument for
measuring rather than warning.

**Levels travel worse than orderings.** Changing the standard population moves the
standardised rate by a median 1.337 pp — more than standardising moved it from crude
(max 1.17 pp) — while the rank correlation between standards stays above 0.986 [D07 F5].

**Decompose before attributing.** Kitagawa splits a gap into rate and composition
components exactly. DC vs Oklahoma: a crude gap of −0.803 pp decomposes into +0.005 pp of
rate and −0.808 pp of composition — age structure accounts for **100.6%**, and the rate
component carries the *opposite* sign [D07 F4]. The crude ordering is not what it appears
to be. (That reversal does not survive the worst-case correlation assumption and is
reported as conditional.)

---

### 7.2 Modelled small-area estimates: what to report when a ranking is impossible

§7.1 measured tracts and found no determined rank among 13,981. That could have been a
story about geography — go small enough and the margins swamp the differences. CDC PLACES
tests it at **county** level, two steps coarser, on a different *kind* of estimate: a
model-based prediction with a credible interval rather than a design-based estimate with a
sampling margin.

Every figure below: `scripts/measure_modelled_estimate_ranking.py`, PLACES county release
`i46a-9kgh` (2025), crude prevalence, 2,956 counties with parseable intervals. Deterministic.

#### The result, and why it is not about geography

| measure | between-county SD | median CI width | ratio | reliability λ | share λ ≥ 0.7 | determined ranks |
|---|---|---|---|---|---|---|
| asthma | 0.90 | 2.70 | 3.01 | 0.43 | 0.4% | **0 / 2,956** |
| obesity | 4.75 | 15.30 | 3.22 | 0.37 | 1.6% | **0 / 2,956** |
| depression | 3.28 | 7.00 | 2.13 | 0.71 | 52.2% | **0 / 2,956** |
| diabetes | 2.78 | 3.90 | 1.40 | **0.87** | **100%** | **0 / 2,956** |

For every measure the interval around a single county is wider than the spread across all
of them. But the decisive row is **diabetes**: reliability 0.87, every county clearing the
0.7 floor conventionally required before publishing unit-level comparisons — and still not
one determined rank.

**[rule]** Reliability and rank identifiability are different questions, and clearing the
first does not touch the second. λ asks *can this unit be told apart from the average*;
rank asks *can it be told apart from every other unit*. At N ≈ 3,000 the second fails on
multiplicity alone, at any precision a real survey will ever reach. No amount of sample
rescues it, because it is not a precision problem.

λ here is `τ² / (τ² + se²)` with τ² by the DerSimonian–Laird moment estimator — the same
quantity as the shrinkage weight in a hierarchical model.

#### Why ranking point estimates is a category error, not merely imprecise

Shen & Louis (1998) [JRSS-B 60(2):455–471] show that one set of estimates cannot serve
three inferential goals at once — estimating each unit's value, estimating the *ensemble*
distribution, and estimating *ranks*. Their abstract states it directly: posterior means
"perform poorly in estimating the histogram of the parameters or in ranking them." The
estimator that is optimal for a unit's value is **not** optimal for its rank, so
`rank(estimate)` is the wrong functional, not a noisy version of the right one.

Related: Louis (1984, *JASA* 79) on ensemble vs. individual estimation; Lin, Louis, Paddock
& Ridgeway (2006, *Bayesian Analysis*) on loss-function-based ranking; Goldstein &
Spiegelhalter (1996, *JRSS-A* 159) on league tables; Gelman & Price (1999, *Statistics in
Medicine*) on maps of parameter estimates; Spiegelhalter (2005, *Statistics in Medicine*,
doi:10.1002/sim.1970) on funnel plots. *Shen & Louis was verified against the published
record; Spiegelhalter to journal, year and DOI. The remaining page ranges are from standing
knowledge and were **not** verified — treat them as leads, not citations.*

#### Four estimands that survive, with what each yields here

**1 — Detection, not ordering (funnel).** Compare each unit to a precision-weighted
benchmark; limits widen for imprecise units by construction, so small units are not
mechanically thrown into the tails. Outside the 95% limits: 13.3% (asthma), 15.0%
(obesity), 28.0% (depression), 44.1% (diabetes). Outside 99.8%: 2.6% to 25.0%. **Ranking
identifies zero counties; this identifies hundreds**, because it answers a question the
data can support.

**2 — Tiers, not ranks.** Under a Bonferroni-controlled sequential partition the data
support **2 tiers** (asthma), **3** (obesity, depression), **5** (diabetes) across 2,956
counties. That is the true resolution of the measurement, and it is a publishable answer.

**3 — Interval-valued ranks, where a rank is genuinely required.** Monte Carlo rank
distributions give median 95% widths of 44% (diabetes) to 72% (obesity) of the list. The
top-ranked county's own interval runs [1, 11] for diabetes but [1, 314] for obesity. Report
the interval; never the integer. Note this approximation is *optimistic* — independent
normal draws ignore the shared model structure that would correlate units, so true
posterior ranks are no sharper.

**4 — Exceedance, exploiting an asymmetry.** For P(θ > 90th percentile), only 0.6–3.5% of
counties can be confidently placed above — but **38.2–78.0% can be confidently placed
below**. The negative statement is far better supported than the positive one. You can
reliably *exclude* counties from a high-burden list long before you can confirm inclusion,
which is the opposite of how such lists are usually built.

#### Two diagnostics that must be run per measure, never assumed

This is the part that surprised the build, and it corrects a generalisation made here from
a single measure before the full run existed.

**Size artifact** (Gelman & Price). The signature is *more* spread among small units. It
appears in **diabetes only** — SD 3.01 → 2.11 from smallest to largest quartile,
Spearman(log pop, se) = −0.468. In obesity (4.46 → 5.06) and depression (3.01 → 3.41) the
spread is *higher* among large counties, the opposite pattern; asthma is flat. A mean
gradient is not evidence of the artifact and may be substantive — rural diabetes prevalence
plausibly is higher.

**Circularity.** Regress the PLACES estimate on four ACS covariates (median age, log median
income, poverty rate, share 65+) and ask how much of the *ranking* survives without PLACES
at all:

| measure | R² | Spearman(ranks) | top-100 counties shared |
|---|---|---|---|
| depression | 0.047 | +0.207 | **3 / 100** |
| asthma | 0.173 | +0.401 | 18 / 100 |
| obesity | 0.385 | +0.567 | 46 / 100 |
| diabetes | 0.694 | +0.821 | **66 / 100** |

Two-thirds of a "highest-diabetes counties" list is reproducible from four ACS variables
without touching PLACES; for depression, three counties. This **bounds the new information
in the ranking** — it is not evidence about which covariates the model used, and poverty
genuinely does predict diabetes, so it is an upper bound on circularity rather than a
demonstration of it. The practical reading: if you already hold ACS, a diabetes ranking
tells you comparatively little you did not have.

**[rule]** Rank is the wrong estimand for a modelled small-area estimate. Replace it with
detection, tiers, an interval-valued rank, or an exceedance probability — and measure
covariate-recoverability before publishing any ordering. Every diagnostic in this section
varies by an order of magnitude across four measures from *one dataset*; none may be
inherited from the source, the geography, or a neighbouring measure.

### 7.3 The series that closes the precision objection

§7.2's claim — that rank failure at fine geography is multiplicity rather than precision — had
an objection available to it twice: the measurements were not very precise. Three notebooks now
test it at increasing precision, and the objection does not survive.

| notebook | estimand | reliability λ | interval ÷ spread | units | ranks determined |
|---|---|---|---|---|---|
| modelled (PLACES diabetes) [D04 F2] | | 0.853 | — | 133 | 0 |
| measured (Opportunity Atlas) [D10 F4] | | 0.916 | 0.89 | 133 | 0 |
| measured (economic connectedness) [D21 F5] | | 0.995 | 0.0438 | 3,018 | 0 |
| published ratio of two medians (gender earnings) [D33 F4] | | 0.9745 | 0.1078 | 51 | 0 |

D21 is the decisive case. Its 95% interval width is **0.0438** of the between-county spread —
about twenty times tighter than D10 — its reliability clears the **0.7** convention in
**100.0%** of counties, and it carries roughly twenty-three times as many units [D21 F5]. It
yields **0** determined ranks out of **3,018**, with a median attainable span of **500**,
or **16.6%** of the table [D21 F6].

**More units makes ranking worse and more precision does not rescue it.** The number of
comparisons a rank must win grows with the table; the evidence per comparison does not.

**But precision buys the extremes, and the earlier notebooks were too imprecise to show it.**
**8** counties have an attainable rank span under **10**, the tightest being **2**, and **80**
(**2.65%**) have a span under **100** [D21 F7]. The top and the bottom of the table resolve
even though the order does not.

**[rule]** This is the operational form to hand a decision-maker: **you may name the extremes;
you may not publish the list.** It is more useful than a flat refusal to rank, and it is what
the evidence actually supports.

Detection continues to work where ranking does not, and scales with precision as expected:
**88.7%** of counties separate from the precision-weighted benchmark at 95% and **82.1%** at
99.8% [D21 F8], against D10's 56.4% and 42.1% on the same construction.

**The fourth case answers one of those questions and adds a mechanism.** D33's estimand is a
ratio of two published medians, and its between-state spread is **0.1928** against a mean level
of about 0.81 — a relative spread of **0.2383**, the narrow-spread case the paragraph above asks
for. It is also the most favourable case in the series on every other axis: **51** units rather
than 133 or 3,018, so the least multiplicity pressure yet tested; reliability λ of **0.9745**
median and **0.8310** minimum, clearing the 0.7 convention in **100.0%** of states; and a 95%
interval **10.78%** of the spread, about eight times tighter than D10's [D33 F4]. It yields
**0** determined ranks out of **51**, with a median attainable span of **19** — **37.3%** of the
table [D33 F5].

**Fewer units does not rescue ranking either.** The series now spans 51 to 3,018 units and every
case returns zero.

And D33 shows *why*, which the earlier cases could not because they reported determined ranks
without the pairwise rate beside them. **1,015 of 1,275 state pairs — 79.6% — are separated at
90%**, and 76.1% at 95% [D33 F6]. On a pairwise question the measurement performs well. A
determined rank is a different object: it must win all **50** comparisons, not one. Treating them
as independent gives 0.796⁵⁰ ≈ **1.12 × 10⁻⁵**, so about **0.0006** determined ranks are expected
across the table — against **0** observed [D33 F6]. The independence assumption is wrong in the
direction that matters (the comparisons share estimates and are positively dependent, which makes
determined ranks *more* likely, not less), so this is an order of magnitude and not a proof. It
is enough to show the zero is arithmetic rather than imprecision, and the exponent is the unit
count, which is the same fact §7.2 states from the other end.

**[rule]** Report the pairwise separation rate beside the count of determined ranks. One without
the other reads as a failed measurement instead of a structural result.

The extremes behave as D21's rule predicts at this scale too: **9** states have an attainable
span under 10, the tightest being **3** (Utah and Wyoming, both at the bottom), while the state
ranked third by point estimate can occupy any of ranks **1** through **17** [D33 F5]. Detection
continues to work: **82.4%** of states separate from the precision-weighted national ratio at 95%
and **56.9%** at 99.8% [D33 F7].

**What is still not established.** All three cases are counties or county-equivalents. The
tract-level question §7.1 leaves open is not answered here, and no case in the series has an
estimand whose between-unit spread is small relative to its own scale — where the result
should, if anything, be worse.

**What is not established.** That covariate-recoverability check is, as far as this build
is aware, not standard practice in the small-area literature, and that assessment rests on
no systematic review — it may well exist under a name not searched for. The four measures
here were chosen for contrast, not sampled; the other 36 in the release are unmeasured. And
§7.1's open question — whether the tract result holds for a quantity with more spread than
broadband share — is *not* answered by this section, which measures counties.

---

## 8. Scale, coverage and construct

### 8.1 Deflate, and say which deflator

County median home value rose **185.6% nominally and 54.4% in real terms** over 2000–2026:
**71% of the headline is the general price level**. In real terms 37 counties (3.6%) are
worth *less* than in 2000 [D27-gent F2]. A nominal long-run change is not a finding about
the thing being measured.

The deflator choice moves 20 counties across zero and reorders none [D27-gent F3]. **It
governs the sign, not the ranking** — which means it must be named wherever a sign is
reported and may be treated as immaterial wherever only an ordering is.

### 8.2 Coverage is two numbers, and they support different sentences

The D27-gentrification analysis set is **1,026 of 3,222 counties (31.8%) but 72.4% of
occupied housing units** [D27-gent F1]. Both are true. A notebook that quotes only the
second is overstating its reach; one that quotes only the first is understating it.

The same hazard is recorded for Zillow ZORI at **43.0% ACS-county coverage** in
`data/zillow/2026-08/SOURCES.md`, which is why D27-gentrification is built on home values
rather than on a rent-led measure.

**[rule]** Report coverage as both a unit count and a share of the quantity being analysed,
whenever the two differ materially.

### 8.3 Construct validity is not precision

D27-gentrification computes county-level home-value appreciation conditioned on baseline
median income. That is **not a measure of gentrification**, and the difference is one of
construct rather than precision — no amount of extra data closes it. The notebook says so
in its own scope note, after reporting the result.

Two findings force the point. Holding thresholds identical and varying **only** the
reference population, two defensible definitions name 124 and 161 counties, agree on 66,
and overlap at **Jaccard 0.301** — roughly 70% of the combined membership depends on that
one choice [D27-gent F4]. And within states, county real outcomes span a median of **91
percentage points**, with 12 of 34 states holding counties that moved in opposite
directions [D27-gent F5]: the phenomenon is defined below the scale at which it is being
measured. This is MAUP, and it is not mitigable by better estimation.

**[rule]** Where the computed statistic is a proxy for the named concept, the notebook
names the gap explicitly and does not let the title do the arguing.

### 8.4 Measures are choices

Five measures of the same distributions produce different rankings; Theil responds to the
top, Atkinson at high ε to the bottom, p90/p10 to neither. Lorenz curves cross, and when
they do no scalar summary can order the distributions without embedding a value judgement.
An Atkinson index quoted without its ε is not interpretable [D06 takeaways].

**Check identification before ranking.** The top-decile share returns a plausible number
for every state and is meaningless for half of them, because the top bracket is open. The
check costs one line; omitting it produces a confident, inverted ranking [D06 takeaways].

---

## 9. Credentials

Six keys, and no others: `CENSUS_API_KEY`, `FRED_API_KEY`, `BLS_API_KEY`, `BEA_API_KEY`,
`HUD_API_KEY`, `DATA_GOV_API_KEY` (`ALLOWED_KEYS` in `sources.py`). Each addition is a
decision, and `test_hud.py::test_hud_key_is_allowed_and_the_allowlist_is_still_closed`
asserts the exact set so that widening it stays deliberate. A request for any other name
raises `DisallowedCredentialError` **before the secrets file is opened**, so a disallowed
name is never matched against its contents.

`DATA_GOV_API_KEY` is named for its issuer rather than for an agency on purpose:
api.data.gov issues one key that authenticates across every participating agency, so the
same name covers the FBI Crime Data Explorer and anything else fronted by api.data.gov
without a further entry. That was verified rather than assumed — a request to
`api.usa.gov/crime/fbi/cde/arrest/national/all` returned HTTP 400 with *"From year and month
date is not valid, expected format MM-YYYY"*, which is the application validating query
parameters **after** accepting the credential. An invalid key returns 403 `API_KEY_INVALID`,
not a date-format complaint.

Resolution order is environment variable, then `KRL_SECRETS_PATH`, then
`~/.krl/secrets.env`. The file is streamed and reading stops at the first match; no
non-matching line is retained.

### 9.1 Point it at a scoped file, not at the operator's

The allowlist is a **code-level** guard: it stops a tutorial asking for `DATABASE_URL`. It
does nothing about a stray script in the same kernel, or a notebook a reader modifies, both
of which can open the configured file directly. So the file itself should carry only what
the corpus is allowed to ask for.

    umask 077
    { awk -F= '/^(CENSUS|FRED|BLS|BEA|HUD)_API_KEY=/' ~/.krl/secrets.env
      awk -F= '/^GOVINFO_API_KEY=/{print "DATA_GOV_API_KEY=" substr($0, index($0,"=")+1); exit}' \
          ~/.krl/secrets.env
    } > ~/.krl/tutorials.env
    chmod 600 ~/.krl/tutorials.env

Then `KRL_SECRETS_PATH=~/.krl/tutorials.env`. Six names, matching `ALLOWED_KEYS` exactly, and
the operator's database URLs are out of range structurally rather than by convention — which
is the difference between a guard and a policy.

**[rule]** Two independent barriers, not one. `ALLOWED_KEYS` bounds what the corpus *asks
for*; a scoped secrets file bounds what the kernel can *reach*. Either alone fails to a
mistake the other catches.

### 9.2 A mounted file can be stale in content while fresh in metadata

Encountered on the desktop bridge and worth recording, because the failure is silent and
reads like a missing key. After a new line was appended to `~/.krl/secrets.env` on the host,
the mounted copy inside the container kept the old content: `grep` on the host found the
line, `load_key` in the VM raised `MissingCredentialError`.

The diagnostic that separated the causes: `touch` on the host **did** propagate — the mount's
mtime moved from 04:04:30 to 04:16:10 — while the size stayed at 2,099 bytes and the content
did not change. So the mount was live and the cache was on content alone. Writing a *new*
file in the same directory was visible immediately, which places the cache per-file rather
than per-directory.

**[rule]** When a credential that exists on the host is missing inside a container, compare the
mount's size and mtime before concluding anything about the key. Matching mtime with stale
size is a cache, not a missing entry, and re-saving the same path will not clear it — write a
new path instead.

**Key material is never printed, logged, echoed, or written into a notebook output.**

HUD is the one source whose credential rides in a **header** (`Authorization: Bearer`) rather
than a query parameter, so its URL is safe to print and its request headers are not. `redact()`
covers it regardless, because `load_key` records every value it returns in `_SEEN_SECRETS` and
`redact()` removes those wherever they appear.

This rule was added after it was broken. Every fetcher interpolated the upstream exception
into its error text, and `requests` exceptions carry the request URL — which carries the
key as a query parameter. A FRED key reached a traceback. `redact()` now runs two passes:
recognised credential query parameters by regex, then any literal secret value this process
has loaded, wherever it appears. It is applied at every interpolation site, and
`tests/test_redaction.py::test_every_fetcher_redacts_its_upstream_exception` reads the
module source to prove no new site is added without it.

**[rule]** A fetcher may not interpolate an upstream exception into raised text without
`redact()`. The test is structural, not behavioural, because the behavioural version only
fails when a key is actually present.

---

## 10. Upstream connectors

`krl-data-connectors` is a declared dependency of this repository and is **upstream and
read-only**. This corpus adapts from above and never edits it; ADR 0004 records the ruling
and `tests/test_connectors.py::test_this_package_never_writes_to_the_upstream_connector`
enforces it.

`connectors.py` is the adapter: `load_connector` imports by string so that upstream is
never imported at module scope, `BulkFileSource` adds the vintage and hash pinning the
upstream layer does not carry, and `frame_from_bulk_file` applies this corpus's
`DataMode` discipline to the result.

**What the adapter adds, and why it exists** — from the comparison in ADR 0004: the
upstream `CensusACSPublicConnector` has no margin-of-error concept, no jam-value handling,
no HTTP-200-plus-HTML check, and a bare `except Exception`. Those are precisely the four
failure modes §1 and §2 are about. The adapter does not duplicate acquisition; it adds the
epistemic layer above it.

---

## 11. Self-audit: defects introduced and caught during this build

Recorded because it is the most transferable content in this document, and because a
corpus built to catch this class of error should not conceal its own instances. All were
found by reading executed output, none by a gate.

| # | Notebook | Defect | Detected by | Resolution |
|---|---|---|---|---|
| 1 | D07 | Within-state spread computed on **nominal** values while the prose said "in real terms" | Reading the finding against the code that produced it | Recomputed on real; the finding **strengthened** from 1 state to 12 |
| 2 | D16 | A test containing `assert ... or True` — structurally incapable of failing | Reading the test | Removed; swept every test file added in this build for the pattern |
| 3 | D08 | Rebasing classifier labelled nominal PCE "REBASING" while adjacent prose said nominal series are never rebased | Internal contradiction between two outputs | Root cause: **ratio variability does not discriminate** (sd 0.007199 vs 0.006083). Rewrote around the failure; the failed diagnostic is now the notebook's finding [D08 F1] |
| 4 | D09 | "Naive sum" demonstration showed identical numbers | The demo did not demonstrate anything | Root cause: adding zeros does not change a sum. Rewrote around **per-cell** statistics, where the defect is visible [D09 F2] |
| 5 | D09 | Pearson −0.221 reported beside a 95%→2% gradient | The coefficient contradicted the table above it | Switched to Spearman −0.667 with Pearson alongside and an explanation of why the linear coefficient understates a step relation [D09 F4] |
| 6 | D12 | The first TRI fetcher returned a full 10,000-row page as a complete result; the query matches 12,069 | Comparing the frame length against the service's own `count` endpoint | Client now counts before it fetches and refuses a frame that disagrees. **17.1% of the answer** was silently missing [D12 F7] |
| 7 | D12 | Prose called the range-code hole material because the loss is one-directional | Computing the bound instead of asserting the sign | It is **4.00%** of records and **0.0328%** of pounds [D12 F5]. Directional does not imply material |
| 8 | D30 | A fence test grepped every module for the word "simulation" and failed on a docstring in `reliability.py` explaining a bound is *not* simulation-based | The failure named a file with no such import | Matched on the import statement instead. A check that looked right and measured the wrong thing — this corpus's own subject |
| 9 | D30 | Two prose claims (`5.8` and `2.9` standard errors) were arithmetic on displayed values that the notebook never printed | Auditing every bolded figure against stored output | Added a `t` column to the scoring cell; the claims now read **5.78** and **2.95** from the table |
| 10 | gate 8 | The traceability gate's stated sensitivity (7 of 8) was measured once and never re-measured | Running two further mutation rounds while writing §1.14 and §13 | Now **25 of 28**, with all three misses and their causes recorded in the gate's own docstring |
| 11 | register | `MIGRATION.md` retired three notebooks on the stated ground that they were "SHA-256 identical to D01". They are not: four different file digests and four different byte counts | Hashing the files instead of trusting the register | The true claim is about the **code** (SHA-1 `9a5a5afdf75b`, byte-identical across all four). Corrected in place, evidenced, and pinned by `tests/test_retirement_basis.py` so it cannot go stale again |
| 12 | gate 8 | The traceability gate read notebook references in prose (`D10`, `D33's`) as numeric claims. It had been passing only by coincidence — "twenty times tighter than D10" was checked by looking for "10" in the cited notebook, which any notebook contains | D33's own tag failing against D33 | Notebook references are now stripped before a claim is read for figures, as section references already were |
| 13 | register | `SOURCE_MAP.md` listed D19 as needing registration and D20/D26 as unbuilt-because-blocked. Re-deriving the obstacle list found D19 unrestricted (Dataverse, `restricted: false`, no terms), D20 reachable on ACS `B28001`, and D26 reachable on the CDE key D13 already uses | Probing each claimed obstacle instead of reading the register | Three entries corrected; EJScreen (404) and CDC WONDER (403) re-confirmed as genuine. **Three of eight obstacle claims were false** |
| 14 | D20 | Prose claimed a minimum per-county overcount of 111.0%. The measured minimum is 49.0% — a figure invented inside a sentence that was itself a botched self-correction | Auditing every bolded figure against stored output | Rewritten from the output. The audit sweep is what caught it, which is the argument for running it on every notebook rather than on the ones that feel risky |
| 15 | contract | The fetcher-response contract followed guard delegation **one hop**, so `fetch_mit_president` → `fetch_dataverse_file` → `_dataverse_get` reported as unguarded | The new fetcher failing a gate that was right to fail it | Discovery is now a transitive closure. Third widening of this test (allowlist → name prefix → single hop), so it is now closed rather than narrowed again |
| 16 | D17 | A first draft of the grain-fence test grepped module sources for the word "simulation"; the same class of error appeared again here as a test that would have flagged any column constant in ANY state rather than in all of them | Mutation-testing the classifier | Both are now strict-by-construction and mutation-covered. The recurrence is the point: a check that is nearly right passes review twice as easily as one that is wrong |
| 17 | D22 | The BMF client raised `SchemaError` on any NTEE first character outside A-Z. On the live file that is 25 rows of 1,964,958 — three lowercase (`c030`) and 22 digits (`052`, `0000`) — so a correct guard made the fetcher unusable over 0.0013% of the data | Executing the notebook against the real file | Uppercase first (rescues the lowercase), then record a non-letter as MALFORMED and count it as unclassified. Raising is wrong at this rate; accepting would put a digit in a sector table |
| 18 | D22 | Prose carried 574,184 unclassified and a 58.6% non-charity rate, both measured before the malformed-code change moved 22 rows; the MAR estimate said $125.7B against a computed $125.4B | The figure sweep, after re-execution | Eleven figures corrected from the executed output. The lesson is narrow and keeps recurring: **a client change invalidates prose written against the previous run**, and only re-running the sweep catches it |
| 19 | D28 | Prose said "twelve columns" (the table has 13), described the 1950-2018 span as "sixty-eight years" when the table carries 42 year-points, and printed "the actual total rate" from a two-row frame by `.iloc[0]` without saying which of the two it was | Auditing every bolded figure against stored output, then measuring the year axis and the `unit` column | All three corrected. The third became the notebook's main finding: `unit` crosses all twelve classification schemes, so a correct filter on `stub_name` still leaves two incompatible rows per year |
| 20 | gate 8 | **Every figure in every table in the handbook was unchecked.** `\|` was a claim boundary and the claim fragment is read backwards from the citation, while the handbook's table convention puts the citation in the row's first cell -- so every figure in a row sat on the unread side of both rules. Mutating `0.853` in §7.3's precision-and-rank series, this document's central quantitative claim, tripped nothing | Mutation-testing the §17 table while registering it, then testing §7.3 to see how far it reached | `_claim_row` reads the whole row in both directions. Checks 529 -> 551; 16 citations that vouched for nothing now vouch for their row; 18 of 18 table mutations caught. Two rules that were each defensible produced an unguarded region where they met |
| 21 | §5.2 / 20 notebooks | The policy said every notebook records `vintage_pinned`. **Twenty of thirty-three had no such flag**, every one built after the policy was written, while §5.4 went on stating that no notebook violated the policy | Reading §5.2 against the notebooks during the §5.4 pass, instead of against §5.4 | `tests/test_gate_vintage.py`. A rule with no gate is a preference, and this one had been a preference for the entire second half of the build |
| 22 | §5.2 definition | `vintage_pinned` was read as *the call names a year*. By that reading QCEW, CBP, BDS, BEA and HUD CHAS all pass -- and §5.5, written later, measures every one of them as serving no prior vintage. **Five notebooks were marked `true` that cannot be** | The new gate's consistency check failing D02, D05-fmr, D05-chas, D09 and D15 | The flag now means a re-run returns the same numbers *by the publisher's contract*. Two sections of this handbook disagreed with each other for months; the later one was right |
| 23 | `DataProvenance.render()` | Printed `(pinned)` after every vintage **unconditionally**, in the stored output of sixteen notebooks, three of them built on sources that serve no vintage at all | Reading the renderer while adding the `pinned` field | Prints which it is, from the record. D02, D09 and D15 re-executed. A hand-written `(pinned)` in D09's own print statement had to be fixed separately -- the library was not the only place the claim was made |
| 24 | provenance | Six of twenty-two fetchers hash a **canonicalised JSON re-serialisation** rather than the response bytes, and none of them said so. A verifier assuming one basis reports a revision that did not happen -- which is what the first reproducibility sweep did to D04, reporting DIFF on a payload with an identical row count and an identical byte length | Writing the sweep, disbelieving its first result, and fetching the same URL twice | `hash_basis` is recorded and validated. My own hand-count of the affected fetchers was two; the gate found six. **The gate found four defects its author had missed in the same file he had just edited** |
| 25 | provenance | **29 of 40 provenance records cannot be replayed at all.** The endpoint is a base URL and the query was never stored, so a record cannot say which geography or variables it fetched | Running the sweep and counting what it had to skip | `request_params` added, credentials stripped inside `build` rather than at the call site, because several of these sources take the key as a query parameter and these records are committed |
| 26 | D30 | The notebook printed its own reproduced R² under the label *"test R2 as the archive reported it"*. The archive reported 0.6136; this pipeline reproduces 0.6144. In the one notebook whose entire purpose is scoring reproduction against an archived claim, the output asserted an exact match that does not hold | The corpus-wide bolded-figure sweep, run for the first time on notebooks built before the sweep existed | The archived figure is now a named constant transcribed from the forensic corpus, and the cell prints claim, reproduction and difference |
| 27 | D02, D10, D12, D27-gent | A first corpus-wide figure sweep found four more prose figures the notebook never printed: a correlation rounded to `+0.05` against a measured `+0.053`, a reliability of `0.92` against `0.916`, three TRI totals that were column sums of a printed table, and a ZORI coverage figure measured in a different file | Sweeping all 33 notebooks rather than only the ones built this week | All corrected or made computable. The sweep had been run on every notebook built after it was introduced and on none built before, which is how a corpus acquires two standards |
| 28 | provenance location | Eight notebooks wrote provenance to `Path.cwd() / "provenance"` and five to a repo-root-relative path. **The two conventions cannot both be satisfied by one working directory.** A run from the repo root put 16 records in a stray folder at the top of the tree and left the committed copies beside those notebooks stale; nothing failed | Noticing an untracked `provenance/` at the repo root days later, and reading what was in it | All 13 anchor to the repository root found by walking **up**. `tests/test_provenance_location.py` fails on a stray folder, a cwd-derived path, or a machine-specific path in a record. The defect needed two conventions to exist at once, which is the kind a single-notebook review never sees |
| 29 | Census records | **A digest over the response body cannot identify a Census payload.** 25 identical requests to CBP 2022 county 51720 returned 3 distinct byte digests, 1 distinct row multiset, 89 rows every time — the API does not hold row order | The reproducibility sweep reporting DIFF on four CBP records written minutes earlier, then 25 repeat fetches to decide whether the source or the sweep was wrong | `canonical-rows`: header plus sorted rows. Every ACS and CBP hash in the corpus had been unverifiable, and nothing had noticed because nothing had ever re-fetched |
| 30 | BLS records | **BLS returns the request's own latency inside the payload** (`responseTime`), so every response body differs and every BLS digest was unmatchable by construction | Diagnosing the last two DIFFs after the Census fix | `canonical-stable-json` drops declared volatile envelope fields. Two sources, two unrelated reasons, the same consequence: a hash that looks like evidence and is not |
| 31 | `redact_params` | Called `str(value)` on every parameter, turning the BLS body's `seriesid` **list** into `"['LAUCN...', ...]"`. Replaying posted a string where the API expects an array, and two different requests returned the same generic response — a DIFF that said nothing | The two D02 records replaying to an identical digest, which two different requests should not | Structure is preserved; only credential values are replaced. A parameter that cannot be replayed is not recorded, it is only described |
| 32 | `fetch_bls` | After the basis was corrected, the fetcher still hashed `b"\|".join(raw_contents)` — **the declared basis and the actual computation disagreed**, which is worse than claiming nothing | The sweep still reporting DIFF after a fix that should have resolved it | Canonicalise per batch, then join. The lesson is narrow: changing a `hash_basis` argument is not changing what gets hashed |
| 33 | BDS, BEA | Working through the thirteen unpinned notebooks found **two more sources whose bytes are not stable**: Census BDS (row order, like ACS and CBP) and BEA, which stamps each response with `UTCProductionTime` **nested inside `BEAAPI.Results`** rather than at the top level | Setting a digest pin on BEA, which fired within minutes of being set | The pin was right and the basis was wrong. Stripping volatile fields is now recursive. Four of eleven sources embed request-specific metadata or unstable ordering in the payload, so a naive content hash is the exception here, not the rule |
| 34 | `fetch_bea_regional` | Declared `canonical-stable-json` while still hashing `json.dumps(document)` — **the same defect as `fetch_bls` two hours earlier**, in a fetcher that builds its payload from something other than `resp.content` and so slipped past a check that only looked for that string | The BEA pin still firing after the basis was corrected | The check now asserts the payload routes through the declared basis's helper. A guard written against one spelling of a defect catches one spelling of it |
| 35 | `fetch_acs_wide` | Declared `canonical-rows` while hashing a **digest of per-batch digests** — not that basis, nor any other | The strengthened check above failing it immediately | Given its own basis, `composed-digests`, so a verifier does not try to reproduce it from a single response |
| 36 | 16 notebooks | Imported `krl_tutorials_data` with **no path discovery**, so they ran only from the repository root. Invisible for as long as every run happened to start there — and they started failing the moment provenance was re-anchored and they were executed in place | D28 raising `ModuleNotFoundError` on the first in-place run | All 16 walk up to find the package. Two defects of the same shape, found the same afternoon: a thing that works only because of where you happen to be standing |
| 6 | D15 | Asserted "where both disclose, they agree" when only 17% were within 10% and 28% differed by >2× — **and a conclusion rested on it** | Checking an asserted claim against the numbers on the same screen | Rewrote: the universes genuinely differ, so the non-overlap cannot be attributed to disclosure policy alone [D15 F4] |

**The figures those last two rows corrected**, stated here rather than in the table because a
citation inside a table row vouches for the whole row, including its index:

The archived D30 pipeline published a test R-squared of **0.6136**, and this corpus's
reproduction of it returns **0.6144** [D30 F6]. D02's correlation between a state's change in
unemployment rate and its change in employment is **+0.053** [D02 F5]; its prose had rounded that
to two decimals and then bolded it, which is how a figure the notebook never printed became a
published one. D10's pooled reliability is **0.916** [D10 F5]. And over reporting years 2006 to 2008
Virginia filed **1,154** monitoring-based TRI release records, of which a `code == "M"` filter
catches **443** and silently drops **711** [D12 F8].

**And one misdiagnosis that reached three documents before it was caught.** While building
D05, `https://www.huduser.gov/portal/...` returned HTTP 202 with a zero-length body from both
shells while `hud.gov` returned 200. I concluded the egress allowlist refused the host, wrote
that into the data provenance record, the handbook and `SOURCE_MAP.md`, and committed it. It
was wrong. The response carries `x-amzn-waf-action: challenge` — it is **HUD's own bot
defence**, not the network — and the FMR **API** on the same host answers normally with a key,
which D05 §4b now uses to re-fetch the same values from HUD directly.

Two failures, not one. The first is that **202 is a success code**, so the response never
looked like an error; the corpus already knew this shape (Census 200 + HTML, BLS 200 +
`REQUEST_NOT_PROCESSED`) and §2 now carries it as a row. The second is that I asserted a
*cause* — "the egress allowlist refuses it" — from an observation that only supported "this
path returns 202 with no body." **The observation was right and the diagnosis was invented**,
which is the same error as attributing the CBP/QCEW non-overlap to disclosure policy (row 6),
committed at the level of infrastructure rather than analysis.

*Read the headers before naming a cause. A status code is not an explanation.*

**And one gate that failed correct code.** `test_no_hardcoded_performance_claims` detected
string literals with a regex that excluded f-strings via a `(?<!f)` lookbehind on the opening
quote. An **apostrophe inside an f-string** defeats it — in `f"...whose area's spread exceeds
{t}%..."` the apostrophe closes the match and the remainder reads as a fresh plain literal — so
D05 was reported as printing a hardcoded percentage when every figure in the line was computed.
The detection now parses the cell and excludes `ast.JoinedStr` content exactly; three regression
tests pin both directions, and the repaired gate still fires on **80** checks against the
forensic archive.

*A gate that fails correct code is not a stricter gate. It is a gate that gets switched off* —
which is how the CI step behind F-15 came to carry `continue-on-error: true` in the first place.

**And one defect in this document's own machinery.** The traceability gate written to
keep this handbook honest (`tests/test_handbook_traceability.py`) shipped in a first
revision that matched numbers as **substrings**, so a figure corrupted from 95% to 94%
passed — 94 occurs inside 294, which appears in the notebook. A second revision fixed the
matching but scoped each claim to the last sentence break, silently checking 124 figures
while never seeing roughly 30 others. Both were found by mutation-testing the gate rather
than by running it. The gate now matches whole tokens, spans the whole claim, and carries
its own true-positive test; its measured sensitivity — 7 of 8 corruptions caught, and why
the eighth is not catchable — is stated in its docstring rather than implied.

*A gate that cannot fail is worse than no gate, because it is counted as coverage.* That is
the same sentence as row 2 above, one layer up.

**And one recurrence of the defect the corpus exists to prevent.** D01, D03 and D06 were
committed with **zero stored outputs and null execution counts** while `README.md` stated
they were executed — the F-1/F-2 signature from the original audit, reproduced inside the
tree built to eliminate it. Both halves were fixed: the three notebooks were re-executed,
and three evidence gates were added (`tests/test_gate_evidence.py`) requiring an execution
count on every code cell, a single ordered run, and stored output in any notebook that
reports results. The gates are proven true positives: they fail **83 of 159 checks** when
run against the forensic archive.

**The general lesson**, stated once: *every one of these survived the gates and was caught
by reading the executed output against the prose.* Gates catch structural defects. They do
not catch a true number attached to a false sentence. Nothing in this corpus replaces
reading the notebook after it runs.

---

## 12. What this handbook does not cover

- **Revision magnitudes for QCEW and CBP** — see §5.4. Unmeasured in this corpus.
- ~~**BEA.**~~ **Classified, §5.5.** BEA does not introduce a new regime — it is LAUS-like in
  publishing no uncertainty and FRED-like in revising — but establishing that surfaced the axis
  §5.5 now documents: it revises four prior years per release and offers no vintage retrieval in
  any of its thirteen datasets. No notebook uses it yet, and one is not needed to state the
  rule.
- ~~**Sub-county geography.**~~ **Measured and replicated, §7.1.** The margin escalates 2.2×
  from county to tract, and the rank consequence is far worse than the margin suggests: across
  13,981 tracts in five states, **zero** have a determined rank. What remains unmeasured is
  whether this holds for quantities other than broadband share — the expectation is that a
  measure with more spread between units would identify more ranks, and that is testable.
- **The remaining connector-backed sources.** HUD FMR is now classified (§1.6). The other
  three are not, and two are not merely unexercised but **unreachable as of 2026-09-14**:
  - **EPA EJSCREEN** — `gaftp.epa.gov` responds, but the `EJSCREEN/` directory it was
    published under no longer exists. Not a network problem; the distribution is gone.
  - **Eviction Lab** — `evictionlab.org` returns HTTP 403 from datacenter addresses (its CDN
    blocks them), so programmatic retrieval fails from any cloud execution environment.
  - ~~**HUD CHAS**~~ — **now classified, §1.7.** An earlier revision of this section said
    "there is no CHAS API". There is, at `/hudapi/public/chas`, and the same `HUD_API_KEY`
    reaches it. The bulk `.zip` under `/portal/` is WAF-challenged, but nothing needed it.
    *Two wrong claims about this one host in two days, both from not checking.*

  A source being unreachable is a finding about the source, not a gap in this corpus, and is
  recorded here so the next reader does not spend the same afternoon establishing it.

  **Correction, 2026-09-14.** An earlier revision of this section said `huduser.gov` was
  "refused by the egress allowlist." It is not. The `/portal/` paths return a WAF challenge
  as HTTP 202 with an empty body; the `/hudapi/` API on the same host works with a key and is
  what D05 §4b uses. The mistake was reading a status code instead of a header, and it is
  recorded in §11 rather than silently rewritten.
- ~~**Vintage retrievability for BLS and Census sources.**~~ **Settled, §5.5.** Every source
  this corpus uses has now been checked, and **FRED is the only one that serves a past
  vintage.** What remains genuinely unknown is narrower: whether Census ever republishes a
  corrected copy *under an existing endpoint*, which the API has no way to express and which
  therefore cannot be detected from the API at all.
- **Any source not listed in §1.** The regimes documented here are not a taxonomy of all
  public data; they are the ones this corpus has met.

---

## 17. The non-aggregable statistic -- a median has no parts

Every regime above concerns a number's provenance. This one concerns an operation, and it is the
most common defect in this document because the operation is one line and it never raises.

ACS `B25077` publishes a median home value for **3,222** county rows. Three things an analyst
plausibly does with that column, against the published national median of **303,400**
[D05-value F1]:

| what was done | result | error |
|---|---|---|
| mean of county medians [D05-value F1] | **209,224** | **31.0%** low |
| median of county medians [D05-value F1] | **172,300** | **43.2%** low |
| owner-unit-weighted mean of county medians [D05-value F1] | **349,878** | **15.3%** high |

The first two fail for an obvious reason: a county is one observation whether it holds four
owner-occupied units or four hundred thousand. The third is the dangerous one, because it looks
like the correction. It is wrong by **15.3%** and it is wrong **high in 44 of 52** states, median
error **+2.03%**, worst **+16.73%** [D05-value F2].

A one-signed error is worse than a large random one. It survives averaging across geographies, it
is stable between vintages, and it looks like a finding.

**[rule]** Counts and totals aggregate. Medians, percentiles, ratios of medians and indices built
from them do not, under any weighting. If the published statistic is not additive, no weighting
scheme recovers the aggregate from the parts -- because the parts do not contain it.

#### What to do instead

Pool the **distribution**, not the summary. `B25075` publishes **26** value brackets per county.
Summing the bracket counts across a state's counties and interpolating the 50th percentile
reproduces the Bureau's own published state median to within **0.0260%** in **52 of 52** states
[D05-value F3].

That agreement is the point. Linear interpolation inside the containing bracket is what the
Bureau does to the same grouped distribution, so the reconstruction is not an approximation of the
published figure -- it is the published figure, recomputed. Having checked it against an authority
at a geography where the answer is published, the method can be used where it is not.

**[rule]** Validate a reconstruction against a published figure before using it where nothing is
published. A reconstruction never compared against a known answer is an assumption with arithmetic
in it.

#### And the same method fails nationally, for a different reason

Pooling every county in the country gives **300,394** -- **0.99%** low. The method did not fail.
`check_partition` reports **OVER** by **844,228** owner-occupied units, and that residual is
exactly Puerto Rico: **`county:*` returns 78 municipios and `us:*` excludes them** [D05-value F4].
Two geography levels of one table in one API, covering different universes, with no exception
raised at either.

Excluding them, the partition is **EXACT** and the pooled median is **303,438** -- **0.01%** from
the published figure, and identical to what interpolating the Bureau's own national brackets
gives.

**[rule]** Before comparing an aggregate of sub-geographies against a published total, run the
partition check. Two levels of one API are not guaranteed to cover one universe, and a
sub-percent discrepancy is exactly the size that gets attributed to rounding.

#### Two deficiencies that do not substitute for each other

The county medians carry margins and the reconstruction does not. Median relative margin on the
county medians is **5.88%**; **775** of **3,216** counties carry a margin above **10%** of their
own estimate, the worst **66.87%**, against **0.119%** on the national median [D05-value F5]. The
pooled-bracket estimate has no margin at all -- bracket MOEs do not combine into the MOE of an
interpolated percentile, which needs the replicate weights.

So one object is imprecise and quantified, the other is accurate and unquantified. A reader
cannot tell them apart from the number.

**[rule]** State which of the two you are publishing. "Validated against the Bureau" and "carries
a confidence interval" are different claims and neither implies the other.

#### Where the statistic does not exist

**6** counties publish no median. One -- Kalawao County, Hawaii -- has **zero** owner-occupied
units, so none could exist; the other five hold between **4** and **772** and are suppressed.
Together they are **0.001622%** of national owner-occupied units [D05-value F6]. Here dropping
them costs nothing, which is the reason to count the cost rather than assume it: the identical
`dropna()` on a table whose suppressed geographies were the substantive ones would have removed
those just as quietly.

---

## 16. The replicated grain -- a county row that is a state value

Fifteen regimes concern what a number knows. This one concerns **where** it was measured, and it
is the cheapest defect in the corpus to detect and among the most expensive to miss.

The USDA Food Environment Atlas is one `.xls` with **3,143** county rows, a FIPS column and
**280** numeric variables across nine county sheets. **49** of those variables -- **17.5%** --
hold a single value per state, copied into every county row in that state [D17 F2].

The distribution is what makes it dangerous. `INSECURITY` and `TAXES` are **100%** replicated;
`ASSISTANCE` is **33** of **53**; and `ACCESS`, `STORES`, `LOCAL` and `SOCIOECONOMIC` are
**0%** -- genuinely county-level throughout [D17 F2]. One workbook, one merge key, and the rule
changes between adjacent sheets.

#### The test

Group by the coarser geography and count distinct values per group. A column taking one value in
**every** group does not vary at the geography its rows claim. `classify_geographic_grain` in
`src/krl_tutorials_data/sources.py` is four lines of pandas and it is the whole defence.

The strictness matters: a column constant in *some* groups is ordinary, and only a column
constant in *all* of them is evidence about how the file was assembled rather than about the
world.

And per-column is not a stylistic preference here -- the rule changes **inside a sheet**. On
`HEALTH`, `PCT_OBESE_ADULTS12` and `PCT_OBESE_ADULTS17` are state values copied into every county
row while `PCT_DIABETES_ADULTS08` and `PCT_DIABETES_ADULTS13` -- same sheet, same FIPS key, same
units -- vary by county [D17 F2]. A county obesity-against-diabetes scatter drawn from that one
sheet has real variation on one axis and 51 repeated values on the other. `RESTAURANTS` shows the
same thing across vintages of one variable: `PC_FFRSALES12` is replicated and `PC_FFRSALES07` is
not [D17 F2].

**[rule]** Before using a column at the geography its rows are labelled with, group by the
coarser geography and count distinct values. Classify per **column**, never per file -- a
dataset's geography is a property of its columns.

#### What it costs

Correlating county food insecurity against county low-access population, as the file invites:
**r = -0.0657**, **p = 0.000237**, **n = 3,124**. At the grain the data actually varies at:
**r = -0.1211**, **p = 0.397**, **n = 51** [D17 F3]. The county version is not a conservative
reading of the state one -- its point estimate is roughly half the size and its p-value is three
orders of magnitude smaller.

The mechanism is effective sample size. There are **44** distinct insecurity values across those
**3,124** rows, so a standard error taken at the row count is too small by about
**sqrt(3,124/44) = 8.4** [D17 F3].

**[rule]** Effective sample size is bounded by **distinct values**, not row count. A variable
with 44 distinct values supports no test with more than 44 observations, however many rows it was
merged onto.

#### Two ways to get a county number that was not measured at county level

This regime and §1.8 (CDC PLACES) produce the same symptom by different routes, and the defences
differ:

- **Replicated** (here): the county value *is* the state value. Detected by a groupby; the
  county grain is fictional and no analysis at that grain is available.
- **Modelled** (PLACES): the county value is a prediction from a model whose covariates are
  themselves county data. A groupby finds nothing, because the values genuinely differ; the
  hazard is circularity, not fiction.

**[rule]** Run the grain check first because it is free, and then ask how the values that *do*
vary were produced. Passing the first test says nothing about the second.

#### And the weakest pin in the corpus

The Atlas has no API, no version number and no release date in the file. Two URLs recorded in
earlier surveys now return **404**, and the live location was found by reading the data-access
page. The payload hash the client computes is the only vintage identifier that exists, and unlike
D19's Dataverse MD5 there is no publisher checksum to compare it against.

**[rule]** When a bulk file carries no vintage, record your own hash and say in provenance that
it is yours. A self-computed hash proves two downloads differ; it cannot say which is current.

---

## 15. The administrative enumeration -- zero sampling error, and the arithmetic still does not close

Fourteen regimes describe sources that estimate something. This one counts it. Presidential
election returns are certified ballots: no estimator was applied, no sample was drawn, and no
column in the file could carry a margin of error. **It is the first source in this corpus whose
sampling error is exactly zero**, and that is a real property, not a rhetorical one -- the
absence here is unlike BLS LAUS's (§1.2), where the uncertainty exists and is withheld, and
unlike BEA ACPSA's (§1.11), where nothing was sampled but the accounting identity holds by
construction.

What is left when sampling error is zero is definitional, and it is not small.

#### Test the identity before cleaning, and after

The file publishes both parts and whole, which most sources do not. As published, the sum of
`candidatevotes` equals `totalvotes` in **661** of **663** state-years, with the whole file
adrift by **3,409** votes [D19 F1].

Then you notice `candidate` is not always a person: **48** rows name a ballot disposition --
`OVERVOTES`, `UNDERVOTES`, `VOID`, `SCATTERING`, `NONE OF THESE CANDIDATES` -- carrying
**473,830** votes. Removing them is what a careful analyst does first. Do it and the identity
holds in **625** of 663, with the discrepancy at **472,169** votes: **139** times larger
[D19 F2].

`totalvotes` counts those rows. Dropping them removes them from the numerator and leaves them in
the denominator, so the cleaning step is the defect.

**[rule]** When a source publishes both parts and a whole, test the identity **before** you
clean and **after**. A worsening is evidence that your assumption about what the whole counts is
wrong, not evidence about the data.

#### A column whose meaning is not constant

Both 2024 failures involve disposition rows and they fail differently. In the District of
Columbia the gap is **exactly** the disposition rows -- `OVERVOTES` plus `UNDERVOTES` is
**2,535** and the sum exceeds the published total by 2,535, to the vote. In New York it is not:
removing its disposition rows leaves the state **118,929** short rather than balanced [D19 F3].

So `totalvotes` carries at least two definitions in the same year, in adjacent rows, with
nothing marking which is which.

**[rule]** A column whose meaning varies by unit cannot be aggregated across units, however
exact each value is. Precision is not a defence against a definition that moves.

#### One download is not one vintage

The `version` column holds **`20210113`** on **4,287** rows and **`2025-11-20`** on **535**,
split exactly by election year: everything through 2020 at the older vintage, 2024 at the newer
[D19 F4]. A single file hash and a single dataset version pin the file, not the data.

The two values are also in **different date formats** in one column, so anything that sorts or
compares that column without parsing it is relying on luck.

**[rule]** Check whether a vintage column is constant before treating a download as a vintage.
If it is not, the file is a concatenation and should be described as one.

#### Bound a lossy recode as precisely as you criticise it

`party_simplified` collapses everything outside Democrat, Republican and Libertarian into
`OTHER`: **2,909** of **4,822** rows, **207** distinct parties, **57,099,629** votes -- 3.826% of
the file. The largest single thing in the bucket is Ross Perot's **19,722,042** votes in 1992,
**19.755%** of that year's national total [D19 F5].

And **0** of **663** state-years were led by a candidate labelled `OTHER` [D19 F6]. For
identifying state winners the recode costs nothing; for any analysis of the third-party field it
destroys the subject.

**[rule]** State the bound on a defect as precisely as the defect. "This recode is lossy" and
"this recode changes no state winner in thirteen elections" are both true, and only the pair is
useful.

#### Pin against the publisher's checksum, not only your own

Harvard Dataverse serves a manifest carrying a dataset version, a release time and a per-file
MD5 **the publisher computed**. A self-computed hash (the Zillow pin, §5.3) proves your copy has
not changed; a publisher checksum proves the file has not been swapped. `fetch_dataverse_file`
verifies against the publisher's value on every call and accepts an `expected_md5` that pins a
vintage, so a deliberate upstream revision raises rather than silently rewriting every downstream
number.

Two client behaviours, both measured rather than assumed: **file ids change between dataset
versions and filenames do not**, so the file is resolved by name -- an id-addressed client pins a
vintage and then 404s. And this host answers **HTTP 403** to the default `python-requests` user
agent and 200 to a named one, so every request identifies the client.

**[rule]** Prefer a publisher-supplied checksum to a self-computed one, and keep both. They
detect different failures.

---

## 14. The stacked publication table -- twelve partitions and two rate definitions in one column

The regimes above concern what a number knows. This one concerns the **shape of the file it
arrives in**, and it is the regime most likely to be mistaken for a tidy dataset, because it has
one row per observation, no missing key, and nothing anomalous in its dtypes.

The NCHS *Health, United States* suicide death-rate table on `data.cdc.gov` is **6,390** rows and
**13** columns. Its `stub_name` column holds **12** values, and they are not twelve strata of one
breakdown -- they are **twelve separate classification schemes of the same deaths**: `Total`,
`Sex`, `Age`, `Sex and age`, `Sex, age and race and Hispanic origin`, and so on, published side
by side [D28 F1].

**Only 84 rows -- 1.3% -- are the whole population.** The other **98.7%** are subgroup estimates
of the same deaths, re-partitioned eleven ways [D28 F2]. In **2018** alone, **276** rows describe
the same twelve months; **2** of them are the population [D28 F3].

#### The second column nobody filters on

A reader who notices the stacking will filter to `Total`. That is still wrong, because `unit`
crosses all twelve schemes with **two incompatible rate definitions** -- **5,578** crude rows and
**812** age-adjusted ones. Filtering `stub_name == "Total"` returns **2** rows per year, every
year: for 2018, **14.20** age-adjusted and **14.80** crude [D28 F4]. Taking `.iloc[0]` returns
the age-adjusted figure here, and that is position, not selection.

**[rule]** A classification column is rarely the only one. After filtering one partition, check
whether the key is now unique. If it is not, a second column crosses the first and the filter is
half done.

#### What the default costs

`df.estimate.mean()` over this table returns **13.71**, against **14.20** age-adjusted and
**14.80** crude for 2018 -- **3.5%** and **7.4%** low [D28 F4]. That size is the hazard. A figure
that came out at 300 would be caught by anyone; one that comes out three and a half percent low
looks like a result, and it averages a national population against
sex-by-age-by-race-by-Hispanic-origin cells and two rate definitions, weighting each equally.

#### A standard change, visible in the value rather than absent

Two of the twelve schemes carry the marker `(Single race)`. **114** rows use the single-race
standard and all of them are in **2018**; **6,276** use the legacy one. **2018 is the only year
both are published** -- **162** legacy rows beside **114** new ones, describing the same deaths
[D28 F5].

This is the structure of §1.7 (HUD CHAS) with better manners: there a category was retired and
the column name did not change, here the standard is named in the value. That only helps a reader
who reads it. A series running `Sex and race` to 2017 and then taking whichever 2018 rows exist
has changed definition mid-series, and the discontinuity will look like an event.

**[rule]** An overlap year is where two standards can be compared and is not where they can be
combined. Pick one, state it, and end the series where it ends.

#### And the axis

The table spans **68** years and carries **42** year-points: 1950, 1960, 1970, 1980, then annual.
Three intervals are ten years wide and thirty-eight are one [D28 F6]. Plotted against a
positional index, the first four points occupy a tenth of the axis and stand for four decades --
a defect that survives every row filter above it, because it is in the axis rather than the rows.

**[rule]** When a span and a point count disagree, the series is not annual. Plot against the
date column, never against the index.

#### Access

CDC WONDER is the canonical route to this material and it **refuses automated query -- HTTP 403**,
re-confirmed 2026-09-15. The Socrata route reaches published NCHS tables and not WONDER's query
engine, so it is not a substitute: custom cross-tabulations, sub-national geography and
suppression-controlled small cells remain WONDER features. Socrata's own default page is
**1,000** rows, so the client passes `$limit` explicitly and **raises when a response exactly
fills it** -- the one case where a complete result and a truncated one are indistinguishable.

**[rule]** A paginated client that does not raise on an exactly-full page is not a client, it is
a truncation with a nice interface.

---

## 13. Simulation, and the one artifact permitted to use it

This corpus is real-data-only and fails closed rather than substitute a value. **D30 is the
single exception**, and the exception is narrow enough to state as a rule: simulation is
permitted only where the thing being taught *is* the relationship between an analysis and a
truth, because that relationship cannot be shown on real data — on real data you do not know
which findings are false.

D30's subject is not well-being. It is the archived D30 notebook, which generated seven
independent normal variates, built a target from three of them, assigned a region at random,
and published regression coefficients, feature importances, cluster profiles and a regional
ranking as findings about human happiness. `krl_tutorials_data.simulation` re-implements that
process as a declared object with named true coefficients, so every number the archive
published can be scored rather than argued about.

#### Reproduce before you audit

All **10** of the archived notebook's published numbers come back from the re-implementation:
three coefficients, three p-values to four decimals, three sample means, and the regional
winner [D30 F1]. That fidelity is not a nicety — without it the exercise audits a lookalike.
It cost keeping the legacy `RandomState` in the archive's draw order and retaining a draw the
archive computed and discarded, because deleting the dead line advances the bit stream and
changes every number after it.

**[rule]** An audit of a published artifact must first reproduce it. If your reimplementation
disagrees anywhere, you are scoring your paraphrase.

#### What the archive published, against what was true

Of **3** determinants reported, **1** — `unemployment_rate`, at p = 0.0482, with a positive
sign — has a true coefficient of exactly zero. A second, `health_coverage_pct`, is real and
was overstated **1.82x**. The third, `median_income`, was estimated well and **displayed as
`0.0000`**, because its true value is 2e-05 and the print format carried four decimals: the
one coefficient the analysis got right is the one a reader cannot see [D30 F1].

**[rule]** Choose the display precision from the coefficient's units, not from a house style.
A fixed-decimal format silently deletes any effect whose scale it cannot reach.

#### Measure the design before condemning the result

Across **2,000** independently drawn datasets from the same declared process, at least one
zero-effect predictor is reported at p<0.05 in **8.60%** of runs, against a nominal
**9.75%** [D30 F2]. Nothing was done wrong. A conventional regression, a conventional
threshold, one dataset, and roughly a one-in-twelve chance of publishing a determinant that
does not exist.

The same design's other error is larger and invisible: `health_coverage_pct` is real and is
detected in only **25.6%** of runs [D30 F2]. Three times in four the design misses a genuine
effect. A single notebook's output shows neither error.

**[rule]** "Is this finding real?" has no answer inside one run. "How often does a design like
this produce a finding like this when nothing is there?" does, and it is the question to ask.

#### The standard error separates reliable from unreliable, not true from false

Two real effects, same 50 rows, same model. `median_income` is recovered with a 5th-95th
range of **0.61x to 1.41x** of truth and is never wrong-signed in 2,000 runs.
`health_coverage_pct` is unbiased in the median and ranges **-0.21x to 2.21x**, coming out
**wrong-signed 8.55%** of the time [D30 F3].

What separates them is the standard error, which the archive did not print. And its limit is
equally instructive: in the archive's own fit the false positive sits at **t = 2.03** and the
real-but-fragile effect at **t = 2.95**, while the trustworthy one is at **t = 5.78** [D30 F3].
The t-column identifies the estimate worth believing. It does not identify which of the other
two is fictional.

**[rule]** Publish the standard error beside every coefficient, and do not read the result as
a truth detector.

#### Sample size, stated as a requirement rather than a lament

At n = 50 the coverage estimate is wrong-signed **9.33%** of the time and lands within ±25% of
truth in **25.0%** of runs. That reaches **70.7%** at n = 500 and **87.3%** at n = 1,000
[D30 F4]. Fifty units is not a sample size chosen for a question; it is the number of states.

#### Procedures that cannot return nothing, will not

Three of the archive's four analytical steps are structurally incapable of reporting an
absence, and D30 measures what each produces when handed data containing no signal at all:

- **Feature importance.** The random forest assigns **39.90%** of total importance to the two
  predictors whose true effect is exactly zero [D30 F5]. Importances are normalised to sum to
  one whether or not anything matters.
- **k-means and the silhouette criterion.** On pure noise a three-tier ranking is available in
  **100%** of runs, and the silhouette criterion selects a *k* in **100%** of them — **224** of
  **600** at k = 2, the rest spread to 7, with a best score whose median is **0.264** and whose
  maximum reaches **0.351** [D30 F7, D30 F8]. There is no value it can return meaning *no
  structure here*. The archive's named clusters are separated by **1.06** points, the **94th**
  percentile of what the identical procedure produces on data with every true effect severed.
- **The regional comparison.** A highest-satisfaction region exists in **100%** of pure-noise
  runs. The archive's own regional gap of **0.34** points sits at the **69th** percentile of
  noise — not merely explainable by chance but almost exactly the size chance produces
  [D30 F8].

Run end to end on data where every predictor is independent of the target, the archived
pipeline still reports a determinant in **19.3%** of runs [D30 F8].

**[rule]** Before quoting the output of a procedure that always returns something, run it on
data you know contains nothing and quote that too.

#### A performance figure can be a property of the split

The archive reported a random-forest test R2 of 0.6136 on a ten-row test set. Holding the same
fifty rows and the same model and varying only `random_state`, the median R2 across **300**
splits is **0.202**, the 5th-95th range is **-0.570 to 0.536**, and the minimum is **-1.421** —
worse than predicting the test mean. The reproduced **0.6144** is the **98th** percentile of
that distribution [D30 F6].

**[rule]** A test set of ten rows reports which ten rows it got. Quote a resampled spread or
quote nothing.

#### Report the rate that answers the reader's question

Across 2,000 runs, **1,971** reported at least one determinant — this design almost always
finds something. Within those published lists the mean false share is **4.1%**, and **8.7%**
contain at least one determinant that does not exist [D30 F9]. The archived notebook's list
was one of the 8.7%.

**[rule]** "Our threshold is 5%" describes the procedure. "About one published finding list in
twelve contains something that is not there" describes what the reader is holding. Report the
second.

#### The fence around the generator

`src/krl_tutorials_data/simulation.py` returns a `SimulationSpec`, never a `DataProvenance`. The
types are deliberately different and the spec exposes no endpoint, vintage, publisher or
content hash, because nothing is upstream of a simulation and no code path should be able to
ask it for one. `tests/test_simulation.py` pins the archived numbers, asserts that the declared
coefficients are the ones the generator actually uses, and fails if any module in the retrieval
path imports it. `simulate_wellbeing` has **no default seed**, because a default seed is how a
simulation quietly becomes one dataset that everybody cites.

**[rule]** A simulated frame and a retrieved frame must not be the same type. Make the
difference structural, so that mistaking one for the other is a `TypeError` rather than a
reading error.

---

## 18. Identification

*Stub. This section is filled by the cards that deliver projects 09 and 13 (C01 to C06 and
M01); until a card lands, it says only what it will contain. The expansion plan numbered this
section 12; that number, and 13 and 14, were already in use, so the expansion sections follow
the last existing one.*

It will state, for each design the corpus uses to estimate an effect: the estimand; the
identifying assumption written as an assumption; the falsification that was run and where its
output is stored; the inference method and what it assumes about the number of clusters; and
the specific conclusion the design is not entitled to. It will describe the identification
contract each causal notebook declares in its metadata, the pre-analysis plan that precedes
its data, and how that precedence is proven by a digest recorded in the provenance record
rather than by commit time (DECISIONS/0009). Every figure in it will be traced to a notebook's
stored output in the way the sections above are.

---

## 19. Appraisal and distribution

*Stub. This section is filled by the cards that deliver projects 10 and 11 (E01, E03, Q01, and
E02, Q02, Q03 if they are released).*

It will state what a cost-effectiveness ratio is a ratio of and why no interval is offered for
it; how discounting is applied and that no discount rate is stored in the code; what a
distributional incidence table can and cannot say when two income concepts are reconciled; and
what survives multiple-comparison correction in subgroup estimates, with the achieved power.

---

## 20. Models and scenarios

*Stub. Project 12 is designed and held to the next release; nothing in this corpus is a model
of that kind yet.*

It will describe the `model` data mode, which is reserved and not accepted (DECISIONS/0009),
the disclosure every such notebook must carry as its first cell, and the rule that a scenario
is not an estimate of what a policy did. It will be filled by the first card that releases
project 12.

---

## Provenance

Compiled from the FINDINGS blocks and key-takeaway cells of the 23 executed notebooks
in this tree, extracted programmatically from the stored outputs rather than from
recollection. Regenerate the extraction after any re-execution: a number here that
disagrees with a notebook means this file is stale.

`tests/test_handbook_traceability.py` enforces that automatically. Every figure in a
claim tagged `[D09 F2]` must appear in D09; the gate fails if it does not, so a
re-executed notebook forces this file to be corrected rather than quietly left behind.
Read its docstring before trusting it: it proves presence, not correspondence.

Notebooks: D01, D02, D03, D04, D05, D05-chas, D06, D07, D08, D09, D10, D11, D13, D15,
D16, D21, D29, D27-rent-burden, D27-gentrification.
Library: `src/krl_tutorials_data/{sources,standardization,reliability,tabulation,brackets,connectors,inequality,uncertainty}.py`.
Related: `README.md` (the 19 gates), `SOURCE_MAP.md`, `MIGRATION.md`, `DECISIONS/0004`.
