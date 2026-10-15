# Real-source and target map for regeneration

Under the real-data-only constraint, a domain notebook cannot be regenerated until three
things are named: an **authoritative source that can actually be retrieved**, an
**explicit target variable**, and the **unit of analysis**. A generic regeneration across
33 domains without this mapping would recreate the target-by-position defect (F-3) in a
new tree.

The 33 archived notebooks declare **30 distinct source-sets** spanning roughly 25 external
systems. They are not uniformly retrievable, and that — not notebook authoring — is the
gate on finishing the rebuild.

**Verification status** is explicit. `VERIFIED` means this session reached the endpoint.
`UNVERIFIED` means the source is named in the archived config but reachability and access
terms have not been checked. Nothing here is asserted as available on the strength of the
old notebooks' own claims, since those claims were part of what the audit found unreliable.

---

## Tier A — buildable now (keyed REST API, reachable)

| Domain | Source | Proposed target | Unit | Status |
|---|---|---|---|---|
| **D01 income & poverty** | Census ACS | `poverty_rate` | state | **BUILT — 19/19 gates** |
| **D03 education** | Census ACS `B15003` | `bachelors_or_higher_share` | state / county | **BUILT — 19/19 gates** |
| **D06 inequality & wealth** | Census ACS `B19001`, `B19083` | five measures | state | **BUILT — 19/19 gates** |
| **D07 demographics & migration** | Census ACS `B17001` | `age_standardized_poverty_rate` | state | **BUILT — 19/19 gates · RESCOPED, see below** |
| **D16 internet & tech access** | Census ACS `B28002` | `broadband_any_share` | county | **BUILT — 19/19 gates** |
| ~~D18 social services~~ | Census ACS `B22003` | `snap_household_share` | state | **BUILT** as `D18_social_services`. 57.0% of SNAP households are at or above the poverty line, which disproves the non-take-up reading the table invites. |
| ~~D20 digital economy~~ | Census ACS `B28001`–`B28011` | `device_access_share` | county | **BUILT** as `D20_device_access`. `B28001` carries two partitions in one flat list; summing the overlapping rows overcounts by 148.2% in 3,222 of 3,222 counties. |
| **D05/D18 housing needs — CHAS** | HUD CHAS API (pinned county extract + live); Census ACS `B25070` 2022 and 2023 | `I16` | county x ACS 5-year vintage | **BUILT — all gates · second Tier B source; introduces the custom-tabulation regime** |
| **D05 housing — Fair Market Rents** | HUD FMR FY2026/FY2027 (pinned bulk); HUD FMR API (live, keyed); HUD ArcGIS layer (live); Census ACS `B25031` | `fmr_2` | county / town x fiscal year | **BUILT — all gates · first Tier B source; introduces the administratively determined regime** |
| **D05 housing — home values** | Census ACS `B25077`, `B25075`, `B25003` | `median_value` | county / state / US | **BUILT — `D05_home_values`.** Medians are not aggregable: mean of county medians is 31.0% low, owner-unit-weighted mean 15.3% high and high in 44 of 52 states. Pooling `B25075` brackets reproduces the published state median within 0.0260% in 52 of 52. `county:*` includes Puerto Rico and `us:*` does not — 844,228 units, a 0.99% national error, caught by `check_partition`. Handbook §17. |
| **D27 housing affordability** | Census ACS `B25070`, `B25064`, `B25119`, `B19013`; DP04 profile | `rent_burdened_share` | county | **BUILT — 19/19 gates** |
| **D27 gentrification** | Zillow ZHVI (pinned 2026-08); ACS `B19013`, `B25003`; FRED `CPIAUCSL`, `CUUR0000SA0L2` | `real_home_value_change` | county | **BUILT — 19/19 gates · scoped, see below** |
| **D02 employment & labor** | BLS LAUS (API v2) + ACS `B23025` | `unemployment_rate` | state (+1 state's counties) | **BUILT — 19/19 gates · LAUS only, no OES** |
| **D09 industry structure** | BLS QCEW open CSV (no key) | `suppression_rate` | area x industry cell | **BUILT — 19/19 gates · disclosure suppression** |
| **D08 consumer spending** | FRED/ALFRED `PCE`, `PCEC96`, `{ST}PCE` | `pce_growth_revision` | national month (+ state annual) | **BUILT — 19/19 gates · vintages & revision** |
| **D15 business & entrepreneurship** | Census CBP 2022 + BLS QCEW 2022Q1 | `industry_roster_overlap` | county x NAICS | **BUILT — 19/19 gates · counterpart to D09** |
| **D29 innovation & entrepreneurship** | Census BDS time series 2022 (`api.census.gov/data/timeseries/bds`) | `firm_double_count_pct`, `county_coverage_gap_pct` | nation / state / county x NAICS | **BUILT — all gates · introduces the tenth regime: disclosure-avoidance method as a dated policy variable (DAO 216-26)** |
| **D11 cultural economics** | BEA Regional / ACPSA 2023 (`apps.bea.gov/api/data`, keyed) — `SAACArtsVA`, `SAACVALQ` | `arts_location_quotient`, `core_arts_share` | nation / state x ACPSA industry | **BUILT — all gates · introduces the eleventh regime: the satellite account, where the definition is the error bar** |
| **D21 social capital** | Social Capital Atlas 2022 (HDX CKAN resources; no key) — county, ZIP, college, high school | `economic_connectedness`, `rank_span` | county / ZIP / college / high school | **BUILT — all gates · introduces the twelfth regime: differential privacy at a published budget, where part of the uncertainty is a policy choice · settles handbook §7.2** |

> **Note on D07 — the target was changed, and the change is not cosmetic.** The archived
> notebook declares `B01003`, `B02001` and `B07001` with a county-level `net_migration_rate`.
> The rebuild uses `B17001` (poverty status by sex by age) at state level and targets an
> **age-standardised poverty rate**.
>
> The reason is that the domain's teaching content is *composition confounding* — the failure
> mode in which a headline rate compares two populations' age structures rather than their
> outcomes — and that needs an outcome cross-tabulated by age, which `B01003` (a single
> population count) and `B02001` (race alone) cannot supply. `B07001` measures geographic
> mobility over a different reference period and a different universe again; combining it with
> a stock table in one notebook would model neither correctly.
>
> **Migration is therefore not covered by this notebook and is not claimed to be.** It is named
> as an explicit limitation in the notebook itself and remains an open item: a genuine migration
> notebook on `B07001` is a separate build, not a section. The domain name is inherited from the
> archived corpus and is now wider than its contents.

> **Note on D16/D20 — one notebook, one and a half domains.** The rebuilt D16 covers
> internet subscription from `B28002` and, with it, the subscription half of D20. **Device
> access (`B28001`) and the wider digital-economy framing of D20 are not covered** and D20
> remains open. The two archived artifacts are near-duplicates of each other in structure;
> collapsing their overlapping content into one notebook is deliberate, and what is left over
> is recorded rather than quietly dropped.
>
> Two defects found in the source table are worth carrying forward to any ACS notebook:
> `B28002`'s subscription-type rows are **not** a partition (they exceed their parent by a
> factor of 1.7–3.1 in every US county), and "Broadband of any type" **includes cellular data
> plans**, so it is not a fixed-broadband measure. `krl_tutorials_data.tabulation.check_partition`
> exists to make the first testable.

> **Note on D15 — the other way to hide a number, and why it is worse.** Counterpart to D09.
> Census protects CBP by **noise infusion plus silent omission**; BLS protects QCEW by
> **suppression plus a flag**. On the surface CBP looks cleaner — a value in every published cell,
> nothing to filter. That reading is backwards.
>
> In Fairfax County, QCEW lists **692** six-digit industries and CBP lists **469**, with only
> **365** in both. Of the **327** CBP omits, QCEW openly reports employment for **120 of them,
> totalling 59,834 jobs** — absent from CBP with no flag, no zero and no row.
>
> And where both disclose they **correlate without agreeing**: log-employment correlation 0.875,
> but only **17%** within 10%, **28%** differing by more than 2x, CBP **+30%** higher in total. So
> the universes genuinely differ and the non-overlap **cannot** be attributed to disclosure policy
> alone. That is the sharper cost of silent omission: disclosure and universe are indistinguishable
> from the data.
>
> CBP's `EMP_N` noise flag is uniform across every cell retrieved and the API publishes no
> enumeration of its values, so the perturbation on any figure is documented but not measurable.

> **Note on D09 — a fourth kind of imperfect data, and the trap in it.** QCEW is a near-census, so
> there is no sampling margin; its imperfection is **disclosure suppression**, applied where few
> establishments would make a cell identifying. Three properties, all measured:
>
> 1. **A withheld cell is published as `0`, not blank** — the ACS jam-value defect (F-13) at another
>    publisher. Be precise about the damage: it leaves **sums untouched** (adding zeros changes a
>    total by zero) and corrupts every **per-cell** statistic. In Fairfax County the naive mean
>    employment per industry is wrong by **−42%** and the median by **−88%**.
> 2. **Missingness is informative and not at random** — suppression runs **95%** at 1–3
>    establishments and **2%** at 50+, so the flag identifies concentrated industries. Establishment
>    counts are disclosed even for suppressed cells, so the rule is recoverable.
> 3. **It is worst where most needed** — 6-digit suppression is **41.9%** in Fairfax County and
>    **88.9%** in Radford city. Detailed industry data is least available in the small economies
>    most exposed to a single employer.
>
> `fetch_qcew` converts withheld zeros to NaN and records the count in provenance. **No API key is
> required for QCEW** — the only such source in the corpus.

> **Note on D08 — data vintages, and a diagnostic that does not work.** The notebook's subject is
> that a national-accounts figure changes after publication. Two mechanisms are separated:
> **rebasing** (a chained series re-expressed in a new base year — levels shift, growth survives)
> and **revision** (the estimate actually changed).
>
> The obvious data-only test — threshold the cross-vintage ratio's variability — **fails**, and the
> notebook shows it failing: nominal PCE has ratio sd 0.0072 and real PCE 0.0061, which no
> threshold separates. Only the *shift* differs (+1.30% vs +7.54%), and whether a shift is a
> base-year change depends on whether the series is **chained** — metadata, not something in the
> observations.
>
> Consequences for any FRED work here: never compare **levels** of a chained series across vintages;
> **3 of 51** months had the sign of nominal PCE growth reverse between the 2023-06 vintage and
> today (7 of 51 for real PCE), so an analysis run then reached the opposite conclusion from one run
> now; and state PCE revisions span **6.7 pp** across states, so how revisable a figure is, is itself
> uneven and unpublished. `fetch_fred(..., vintage=...)` pins a publication date.

> **Note on D02 — the first non-Census publisher, and what it costs.** LAUS publishes **no margins
> of error**, because sub-state estimates are state-space model output benchmarked to sum to the
> state total, not survey tabulations. Every MOE-based technique in D01/D03/D07/D16/D27 is therefore
> unavailable, and county figures are **not independent observations** — verified here: Virginia's
> 133 counties reproduce the state employment total to within 7 persons (0.00016%).
>
> Two findings constrain any employment work: the change in a state's unemployment rate correlates
> **+0.05** with its change in employment over 2019–2024, so the rate alone is near-uninformative
> about whether more people are working; and ACS and LAUS disagree on the *same* state rate by a
> median **1.49 pp**, with all 51 states differing by more than the ACS margin. Matching the
> reference period (ACS 5-year vs LAUS pooled 2019–2023) closes **72%** of that gap, so the
> discrepancy is mostly the window — but 40 of 51 still exceed the margin, so it is not only the
> window.
>
> **OES/QCEW occupation and industry detail is not covered** and belongs to D09.

> **Note on D27 gentrification — built, and scoped by construct rather than precision.** The
> second notebook completes the archived D27's other half. Its thesis is that **county grain
> cannot resolve a neighbourhood process**, so the statistic is reported as county home-value
> appreciation conditioned on baseline income and explicitly *not* as a gentrification measure.
> Doing it properly needs ZIP/neighbourhood ZHVI paired with tract-level ACS — named in the
> notebook as the next acquisition rather than approximated.
>
> Three findings from it constrain any follow-on work: long-run ZHVI covers **31.8% of counties
> but 72.4% of occupied units** (so household-weighted claims survive and county-level national
> claims do not); **71% of the 2000–2026 nominal change is the price level**, and 3.6% of counties
> are worth less in real terms than in 2000; and two equally defensible definitions differing only
> in reference population overlap at **Jaccard 0.301**.

> **Note on D27 — rent burden only.** The rebuilt notebook covers rent burden from `B25070`
> and validates it against the Bureau's own DP04 percentage. **Gentrification — the archived
> D27's other half — is not covered.** It needs Zillow indices, which are a bulk download rather
> than an API; `krl-data-connectors` already provides `zillow_research.py` to parse and cache
> them, so what is outstanding is placing a pinned vintage of the CSVs on disk and deciding the
> gentrification definition — not building an acquisition layer (ADR 0004 retracts the earlier
> claim that one was missing). D05's median-home-value material (`B25077`) is likewise not built;
> only median gross rent appears, and only inside the aggregation demonstration.
>
> One finding from it generalises to any ACS bracket table. `B25070_011E` **"Not computed"** is
> inside the published total but is not part of the distribution: it covers no-cash-rent
> households and those with non-positive income. Dividing by `_001E` rather than by
> `_001E − _011E` matches the Bureau's own published figure in **14 of 3,220 counties**; the
> corrected base matches in **3,220 of 3,220**. Check the base against DP04 before publishing
> any derived ACS share that has a "Not computed" sibling.

> **Note on D05/D27.** The archived versions declare **Zillow** indices. Zillow is a bulk
> CSV download under its own terms, not an API. Both domains are placed in Tier A on the
> ACS variables alone; the Zillow component moves to Tier B.

## Tier B — bulk-file sources

These sources publish files, not queryable APIs.

> **Corrected 2026-09-13 (ADR 0004).** An earlier revision of this document said the acquisition
> layer "does not yet exist". **That was wrong.** `krl-data-connectors` — a *hard dependency of
> this repository* (`pyproject.toml:36`) — already ships connectors for
> several sources below, including `zillow_research.py`, `eviction_lab.py`, `hud_chas.py` and
> `hud_fair_market_rents.py`, on a `BaseConnector` with caching, SHA-256 cache keying, a rate
> limiter and a connector registry.
>
> The gap that does remain is narrower: Zillow Research and Eviction Lab publish no API, so those
> two connectors parse files a human places on disk rather than fetching them. Tier B work on
> those sources is **manual file placement plus a defensible vintage pin**, not infrastructure to
> build. `hud_chas.py` does fetch over HTTP already.
>
> The vintage-pinning half now exists here: `krl_tutorials_data.connectors.BulkFileSource` makes
> the vintage label mandatory and pins a SHA-256 over the bytes read, and
> `frame_from_bulk_file` loads through the upstream connector's own method and returns a
> provenance record. The connector package itself is **upstream and read-only** (ADR 0004) — this
> repo adapts it, never edits it. A Tier B notebook now needs only the file on disk and its
> vintage recorded.

> **How to read what is left.** Every row below is struck through and marked BUILT or RETIRED except
> three, and those three are **alternative or supplementary sources for domains that are already
> built** — not unbuilt domains. D04 is built on CDC PLACES; D27 is built on ACS and Zillow; D29 is
> built on Census BDS. County Health Rankings, Eviction Lab and PatentsView would each add a second
> source to a domain that has one, and each carries the obstacle named beside it.

| Domain | Source | Obstacle |
|---|---|---|
| D04 health | County Health Rankings | annual XLSX release — **supplementary**; D04 is built on PLACES |
| ~~D10 social mobility~~ | Opportunity Insights | **BUILT** — fetched at runtime, files stay uncommitted; a test enforces it |
| ~~D12 environmental economics~~ | EPA TRI | **BUILT** on Envirofacts — unauthenticated, no key. Count-first paging; the API caps a response at 10,000 rows and signals truncation in no way. |
| ~~D13~~, ~~D26~~ crime & public safety | FBI Crime Data Explorer | **BOTH BUILT.** D13 is the coverage regime; D26 is `D26_crime_aggregates` — property crime moved −0.6% while its components spread 85.1 pp, with the parts reconciling to the whole exactly in 30 of 30 state-years. |
| ~~D17 food security~~ | USDA Food Environment Atlas | **BUILT.** The file had moved (two recorded URLs 404); live location found on the data-access page. **49 of 280 numeric columns are state values replicated into 3,143 county rows** — `INSECURITY` and `TAXES` 100%, `ACCESS`/`STORES`/`LOCAL`/`SOCIOECONOMIC` 0%. |
| ~~D19 civic engagement~~ | MIT Election Lab | **BUILT.** The "registration" claim was wrong: Harvard Dataverse serves it unrestricted with a publisher MD5. Handbook §15 — the administrative enumeration. |
| ~~D24 environmental justice~~ | EPA EJScreen | **RETIRED — source withdrawn.** Re-confirmed 2026-09-15: `gaftp.epa.gov/` returns 200 and lists 33 entries, none of them `EJSCREEN/`; `gaftp.epa.gov/EJSCREEN/` returns 404; and EPA's own download page `epa.gov/ejscreen/download-ejscreen-data` returns 404. `epadatacommons/` exists and lists nothing. The server is healthy and the product is gone. **A third-party mirror is not a substitute here**: EJScreen is a composite index, a mirror carries no publisher checksum and no version, and this corpus pins vintages (§5). Rebuilding the composite from its inputs would be re-implementing EPA's methodology under EPA's name, which is worse than not building it. Its main environmental input, RSEI, derives from TRI — already built as D12. |
| ~~D25 food & nutrition~~ | USDA Food Environment Atlas / CDC WONDER | **RETIRED — every declared component is built, unreachable, or fictional.** The archived notebook declares two sources. (1) The USDA Food Environment Atlas — **D17 is built on that file**. Its headline variable `FOOD_INSECURITY` is declared at county *and tract*: the `INSECURITY` sheet is 6 of 6 columns 100% state-replicated, and the workbook has no tract sheet at all. Its `OBESITY_RATE` is declared at county: `PCT_OBESE_ADULTS12` and `PCT_OBESE_ADULTS17` are state values copied into every county row, while `PCT_DIABETES_ADULTS08/13` on the same sheet are genuinely county-level. (2) CDC WONDER for county diabetes — **WONDER refuses automated query** (D28, HTTP 403, re-confirmed 2026-09-15), and county diabetes prevalence is PLACES, which is **D04** — including §6, the circularity demonstration the warning below asked a D25 rebuild to make explicit. Its own loader is a stub: `# Simulate data loading (replace with actual API calls)`. Basis pinned by `tests/test_retirement_basis.py`. |
| D27 gentrification | Eviction Lab | **supplementary** — `D27_gentrification` is built on ACS and Zillow; this is the eviction half. Registration required, **and** `evictionlab.org` returns HTTP 403 to datacenter addresses — no programmatic retrieval from a cloud environment (checked 2026-09-14) |
| ~~D28 mental health~~ | CDC / NCHS via `data.cdc.gov` | **BUILT.** WONDER does block automated query — HTTP 403, re-confirmed 2026-09-15 — but it is not the only route to NCHS material. The Socrata API serves the published tables (not WONDER's query engine, so it is no substitute). The finding is the file's shape: `stub_name` holds **twelve classification schemes**, `unit` crosses all twelve with two rate definitions, and only 84 of 6,390 rows are the whole population. Handbook §14. |
| D29 innovation | USPTO PatentsView | API, terms need checking — **supplementary**; D29 is built on Census BDS |
| ~~D11~~, ~~D22~~ cultural economics | IRS BMF / BEA ACPSA | **BOTH BUILT.** D11 is the satellite account; D22 is `D22_nonprofit_arts` on the IRS Business Master File — and its finding is a refusal: NTEE is null for 29.2% of 1,964,958 organisations, the gap runs 21.2% to 89.7% by subsection, and the sector cannot be sized from this file. The two notebooks do not measure the same sector. |

> **Circularity warning, carried from audit finding F-11.** CDC PLACES county and tract
> estimates are *model-based* small-area estimates whose covariates include ACS poverty
> and demographics. Regressing a PLACES outcome on ACS predictors substantially recovers
> CDC's own model rather than an epidemiological relationship. Any D25 or D04 rebuild must
> either avoid that pairing or make the circularity the explicit teaching point.

## Tier C — no authoritative free source identified

| Domain | Problem | Recommended disposition |
|---|---|---|
| ~~D30 subjective wellbeing~~ | No US subnational life-satisfaction series is freely published. BRFSS carries poor-mental-health-days, which is **not** life satisfaction. | **BUILT as the false-discovery lesson.** `artifact_class: simulation`, `data_mode: illustrative` — the corpus's only synthetic artifact. The DGP is declared in `src/krl_tutorials_data/simulation.py`, reproduces all 10 of the archived notebook's published numbers, and scores each against a truth known by construction. Handbook §13. |
| ~~D21 social capital~~ | "Civic Engagement Index" and "MIT Civic Data" do not resolve to a specific published product. | **RESCOPED AND BUILT** on the Social Capital Atlas (Meta / Opportunity Insights), a named published product with four geographies. |
| ~~D31 civic trust~~ | Declares D01's sources. No trust measure is retrieved or retrievable. | **RETIRED.** Code-identical to D01 (SHA-1 `9a5a5afdf75b`); the only difference is a References cell naming the GSS. Basis pinned in `tests/test_retirement_basis.py`. |
| ~~D32 freedom / civil liberties~~ | Declares D01's sources. | **RETIRED.** Same code body; differs from D31 only in a References cell and two RNG-derived "Complexity"/"Interpretability" figures (F-2). |
| ~~D33 gender equality~~ | Declares D01's sources. | **RETIRED, AND COMMISSIONED.** `D33_gender_earnings_gap` is built on ACS `B20017` + `B20005`: three published ratios for one question, composition from the counts table, and a fourth row in handbook §7.3 answering its open narrow-spread question. Not a port — it shares the domain name and nothing else. |

---

## What this means for sequencing

Regenerating all 33 is **not** 32 more notebooks. It is roughly:

1. ~9 further Tier A notebooks on ACS/BLS/FRED — tractable now; **11 are built**
   (D01, D03, D06, D07, D16, D27 rent burden, D27 gentrification, D02, D08, D09, D15).
   All four publishers are exercised: Census, FRED/ALFRED, BLS LAUS and BLS QCEW
   (the last needing no credential at all).
   Remaining Tier A is D05 housing, D18 social services and D20 device access — all ACS
   variants of patterns already built. The distinct methodological ground in this tier
   is covered: margins, model-based estimates, revision, suppression and noise infusion.
2. For the bulk sources, a pinned vintage placed on disk for the connectors that already exist
   in `krl-data-connectors`, plus a retention policy. **Corrected (ADR 0004):** an earlier
   revision called this "the actual long pole … infrastructure, not content". The connectors
   exist and are a hard dependency of this repo; the remaining work is acquisition policy and
   vintage pinning, which is smaller and is content-adjacent, not infrastructure.
3. ~12 Tier B notebooks, gated on (2). **Started 2026-09-14 with D05 (HUD FMR).** Of the four
   sources the connectors already cover, one is built and three are blocked at the publisher
   rather than at this repo — see the obstacle table. Reachability should be checked before a
   Tier B notebook is scheduled, not after it is designed.
4. 5 Tier C domains that should be retired or rescoped rather than rebuilt.

The sequencing claim above was revised on 2026-09-13; see ADR 0004. Nothing in this document
should assert that a capability is absent without checking this repository's declared
dependencies first.

Under the real-data-only constraint, **5 of the 33 archived domains cannot be rebuilt as
empirical tutorials at all**, because no authoritative free source exists for what they
claim to measure. That is the honest finding, and it is better surfaced now than
discovered at notebook 30.
