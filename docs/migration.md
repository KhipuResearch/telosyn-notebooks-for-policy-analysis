# Migration map — `notebooks/` to `projects/`

The original corpus is retained unmodified as audit evidence. Each rebuilt notebook
declares `krl.supersedes` pointing at the artifact it replaces.

| v2 artifact | Supersedes | Original disposition | Findings addressed |
|---|---|---|---|
| `projects/01-fundamentals/D01_income_and_poverty` | `projects/01-fundamentals/D01_income_and_poverty/D01_D01_income_and_poverty.ipynb` | parse failure at cell 9; R²=1.000 on constant target; 18 RNG calls | F-1, F-2, F-3, F-4, F-12, F-13, F-14 |
| `projects/01-fundamentals/D03_education` | `projects/01-fundamentals/D03_education/D03_D03_education.ipynb` | `SyntaxError` at cell 10 line 25; 12 code cells, 0 stored outputs, 0 execution counts | F-1, F-2, F-4, F-13, F-14, F-16 |
| `projects/03-inequality-demographics/D06_inequality_and_wealth` | `projects/03-inequality-demographics/D06_inequality_and_wealth/D06_D06_inequality_and_wealth.ipynb` | `SyntaxError` at cell 11 line 38; 11 code cells, 0 stored outputs, 0 execution counts; declared a wealth measure ACS cannot supply | F-1, F-2, F-3, F-4, F-13, F-14, F-16 |
| `projects/06-infrastructure-environment/D16_internet_and_technology_access` | `projects/06-infrastructure-environment/D16_internet_and_technology_access/D16_D16_internet_and_technology_access.ipynb` (and partially `projects/05-social-systems/D20_digital_economy/D20_D20_digital_economy.ipynb`) | `SyntaxError` at cell 10 line 24; 12 code cells, 0 stored outputs, 0 execution counts | F-1, F-2, F-4, F-13, F-14, F-16 |
| `projects/03-inequality-demographics/D07_demographics_and_migration` | `projects/03-inequality-demographics/D07_demographics_and_migration/D07_D07_demographics_and_migration.ipynb` | `SyntaxError` at cell 11 line 37; 11 code cells, 0 stored outputs, 0 execution counts | F-1, F-2, F-4, F-13, F-14, F-16 |

> **D07 is a rescope, not a port.** The archived artifact declared `B01003`, `B02001` and
> `B07001` with a county `net_migration_rate`. The replacement is built on `B17001` at state
> level and teaches composition confounding and direct age standardisation. **Migration is not
> covered by the replacement** and is recorded as an open item, not as delivered. See the D07
> note in `SOURCE_MAP.md`.

| `projects/08-culture-society/D27_housing_affordability_and_gentrification/D27_rent_burden` | `projects/08-culture-society/D27_housing_affordability_and_gentrification/D27_D27_housing_affordability_and_gentrification.ipynb` | rebuilt as rent burden only; the gentrification half declared Zillow bulk files | F-1, F-2, F-4, F-13, F-14, F-16 |

> **D16 absorbs half of D20.** The rebuilt D16 covers internet subscription from `B28002`,
> which is also D20's subscription content. **D20's device-access side (`B28001`) is not
> covered** and D20 stays open. See the D16/D20 note in `SOURCE_MAP.md`.

| `projects/08-culture-society/D27_housing_affordability_and_gentrification/D27_gentrification` | the gentrification half of `D27_D27_housing_affordability_and_gentrification.ipynb` | Zillow bulk files, now pinned by SHA-256 | F-1, F-2, F-4, F-14, F-16 |

| `projects/01-fundamentals/D02_employment_and_labor` | `projects/01-fundamentals/D02_employment_and_labor/D02_D02_employment_and_labor.ipynb` | `SyntaxError` at cell 10 line 28; 12 code cells, 0 stored outputs, 0 execution counts | F-1, F-2, F-4, F-13, F-14, F-16 |

| `projects/01-fundamentals/D08_consumer_spending` | `projects/01-fundamentals/D08_consumer_spending/D08_D08_consumer_spending.ipynb` | rebuilt around data vintages; the archived version treated a FRED figure as fixed | F-1, F-2, F-4, F-14, F-16 |

| `projects/04-economy-industry/D09_industry_structure` | `projects/04-economy-industry/D09_industry_structure/D09_D09_industry_structure.ipynb` | rebuilt around disclosure suppression; the archived version summed QCEW without consulting `disclosure_code` | F-1, F-2, F-4, F-13, F-14, F-16 |

| `projects/04-economy-industry/D15_business_and_entrepreneurship` | `projects/04-economy-industry/D15_business_and_entrepreneurship/D15_D15_business_and_entrepreneurship.ipynb` | rebuilt as the disclosure counterpart to D09 | F-1, F-2, F-4, F-13, F-14, F-16 |

> **D27 is now two notebooks.** `D27_rent_burden` and `D27_gentrification` together replace the
> archived artifact. The second is scoped by construct: it establishes that the available grain
> cannot resolve the process and reports its statistic accordingly.

> **Superseded by the row above (2026-09-13).** This note was written when only the rent-burden
> half existed; the gentrification half is now built. Retained because the record logs amendments
> rather than rewriting them. The archived artifact paired housing affordability with
> gentrification; the rent-burden rebuild covers the first and not the second. Gentrification needs
> Zillow indices, which are a bulk download rather than an API — but `krl-data-connectors`
> (a hard dependency of this repo) already ships `zillow_research.py` to parse and cache them, so
> the outstanding work is a pinned vintage on disk and a gentrification definition. See **ADR
> 0004**, which retracts an earlier claim in this file that the acquisition layer did not exist.
> The v2 filename says `D27_rent_burden` rather than inheriting the wider archived name, so the
> artifact does not claim scope it lacks.

## Added without a predecessor

Not every notebook in `projects/` replaces one. `krl.supersedes` is absent on these, and
its absence is deliberate rather than an omission.

| v2 artifact | Why it has no predecessor |
|---|---|
| `projects/02-health-housing/D05_housing_fair_market_rents/D05_fair_market_rents` | The archived corpus has a `D05_housing` notebook, but it is an ACS median-rent notebook: nothing in it concerns Fair Market Rents, and this is not a rebuild of it. D05-as-archived remains open in `SOURCE_MAP.md` under "D05 housing — remainder". This notebook exists because the corpus met a kind of number the first eleven never did — one defined as an estimate and used as a rule — and the handbook's regime table had no row for it. |
| `projects/02-health-housing/D05_housing_needs_chas/D05_chas_custom_tabulation` | The archived corpus has no CHAS notebook at all. This one exists because CHAS is a kind of source the handbook had no row for — a third-party retabulation that keeps a survey's values and drops its published margins — and because it is where D05's administrative numbers (HAMFI) and D27's ACS housing tables meet. |
| `projects/03-inequality-demographics/D33_gender_earnings_gap` | The archived `D33_gender_equality` is retired above, and this does not replace it: that artifact ran D01's income-and-poverty code and retrieved nothing about sex. This notebook shares its domain name and nothing else, so `krl.supersedes` is absent. It exists because the corpus had no case of a headline statistic its own source publishes three defensible ways, and because handbook §7.3 named an open question — an estimand whose spread is small relative to its level — that a ratio of two medians answers. |
| `projects/02-health-housing/D30_subjective_wellbeing` | The archived `D30` is the artifact this one examines, not the one it replaces. It is the corpus's only `data_mode: illustrative` notebook, and `krl.supersedes` is absent because a notebook that audits another is not a port of it. |
| `projects/07-justice-equity/D19_civic_engagement` | The archived corpus has no election-returns notebook. This one exists because the corpus had never met a source with **zero sampling error** — counted ballots, no estimator — and the handbook's regime table had no row for what is left over when that is true. |
| `projects/05-social-systems/D20_device_access` | The archived `D20_digital_economy` declared `B28001`–`B28011` and retrieved none of it; D16 already absorbed its subscription half from `B28002`. This notebook covers the device half on `B28001` and is scoped to that, so it does not inherit the wider "digital economy" name it could not support. |
| `projects/07-justice-equity/D26_crime_aggregates` | D13 already rebuilt the archived crime notebook and established the CDE's regime. This one has no predecessor of its own: it exists because no notebook in the corpus had yet met an aggregate whose arithmetic is exactly right and whose movement is still uninformative. |
| `projects/05-social-systems/D18_social_services` | The archived corpus has no social-services notebook. This one exists because `B22003` is the clearest case the corpus has found of a table whose own off-diagonal cell disproves the rate a reader would compute from it. |
| `projects/02-health-housing/D17_food_security` | The archived corpus has no food-security notebook. This one exists because the corpus had no case of a file whose **row geography is fictional for some columns and real for others**, which is regime §16 and the cheapest defect here to detect. |
| `projects/08-culture-society/D22_nonprofit_arts` | D11 rebuilt cultural economics from BEA. This is not a second attempt at that: it sizes a different sector from a different agency, and its output is that the sector cannot be sized from the file. It exists because no notebook here had yet ended in a refusal with the bound stated. |
| `projects/02-health-housing/D28_mental_health` | The archived corpus recorded this domain as blocked because CDC WONDER refuses automated query, and that refusal is real. The block was on a route, not on the data: `data.cdc.gov` serves the published NCHS tables without it. The notebook exists because no artifact here had yet met a table that is tidy by every mechanical test and still cannot be averaged — twelve classification schemes stacked in one column, crossed by two rate definitions in another. Regime §14. |
| `projects/02-health-housing/D05_housing_home_values` | The third D05 artifact, and the only one built on ACS. FMR covers the administratively determined number and CHAS the custom tabulation; this one covers `B25077`, which the register had carried as unbuilt since the migration began. It exists because no notebook here had met a statistic that cannot be aggregated at all — and because the correct method, pooling the published distribution, turns out to reproduce the Bureau's own figure exactly, which makes it checkable rather than merely principled. Regime §17. |
| ~~`D24_environmental_justice`~~ | **Retired, not deferred.** EJScreen's distribution is withdrawn: three independent checks on 2026-09-15 (gaftp root listing, the EJSCREEN directory, EPA's own download page) find a healthy server and no product. The corpus does not build on unversioned third-party mirrors and will not re-implement an agency's composite index under that agency's name. |
| ~~`D25_food_and_nutrition`~~ | **Retired on measurement, not on access.** Its declared Atlas variables are D17's file — one of them at a grain that does not exist in it, another that is a state value in county clothing — and its declared CDC route is D28's 403 while its actual subject is D04's. Retiring it is a finding about the archived corpus rather than a gap in this one: the domain was specified from variable names rather than from the files behind them. |

## Retired without replacement

| Original | Reason |
|---|---|
| `09_planned/D31_civic_trust` | **Code-identical to D01** (see the note below). A civic-trust tutorial containing income-and-poverty code is not a notebook to port; it is a notebook to write. |
| `09_planned/D32_freedom_civil` | Code-identical to D01. |
| ~~`09_planned/D33_gender_equality`~~ | Code-identical to D01. **Retired, and a real notebook commissioned in its place** — `projects/03-inequality-demographics/D33_gender_earnings_gap`, built on ACS `B20017` and `B20005`. That is a new notebook, not a port: it shares the domain name and nothing else. |
| `test_kernel.ipynb` | Zero cells. |
| `D34_variant_b copy.ipynb` | Byte-identical duplicate. |
| `D34_demo copy 2 / copy 4.ipynb` | Renamed stale backups, never executed, four cells newline-corrupted into comments. |

> **Correction (2026-09-15): "SHA-256 identical to D01" was wrong, and the truth is worse.**
> An earlier revision of this table claimed the three artifacts were SHA-256 identical to D01.
> They are not, at the file level: D31 is 150,815 bytes, D32 150,680, D33 58,067 and D01 58,089,
> with four different file digests. An auditor checking the stated basis would have found it
> false and had reason to distrust the rest of this register.
>
> What is true is narrower to state and harder to defend. **The code of all four notebooks is
> byte-identical** — SHA-1 `9a5a5afdf75b`, 37,835 bytes, 11 code cells, 18 `np.random` calls, and
> the same three ACS variables (`B19013_001E` median income, `B17001_002E` poverty,
> `B19083_001E` Gini). The file sizes differ only because D31 and D32 carry 17 stored outputs
> each and D01 and D33 carry none.
>
> **The only difference between the four artifacts is one markdown cell.** Each has a
> *References* section naming sources the code never calls: the General Social Survey for civic
> trust, Freedom House and the Heritage Foundation for civil liberties, the WEF Global Gender Gap
> Report for gender equality. The references are the entire differentiation.
>
> Three further facts, from the stored outputs:
>
> - **D31's own output identifies it as a different notebook.** It prints
>   `Notebook: D01_income_and_poverty.ipynb` and `Analytics ready for Income & Poverty domain`,
>   from inside the `D31_civic_trust` directory.
> - **Both executed artifacts report a source they never reached.** The output reads
>   `Census API key not found - will use synthetic data`, and then, four lines later,
>   `Loaded 100 records from Census ACS` and `Primary data source: Census ACS`. A fallback to
>   generated values is announced and then described as a retrieval.
> - **The only substantive difference between D31's and D32's outputs is two random numbers.**
>   Diffing them line by line gives 14 differing lines: two timestamps, one execution ID, one
>   completion timestamp — and `Complexity` / `Interpretability` scores of 0.462 / 0.938 against
>   0.252 / 0.777. That is audit finding **F-2** (an RNG draw reported as a model property), and
>   it is the sole thing distinguishing a civic-trust notebook from a civil-liberties one.
>
> Recorded at this length because the corrected basis is the retirement argument. Three artifacts
> that differ from each other in a bibliography and two random numbers are not three notebooks.
>
> **Second correction (2026-09-18): the stored-output evidence above is not in the audited
> artifacts.** The three bullets and the file sizes were measured from the working-tree copies
> under `notebooks/`, which had been executed after the audit. They are not the artifacts the
> audit of record covers. Against `docs/audits/audit_manifest_2026-09-13.jsonl`, which the
> external corpus matches byte for byte in all 53 files:
>
> | | this register said | the manifest records |
> |---|---|---|
> | D31 | 150,815 bytes, 17 stored outputs | **58,077 bytes, 0 stored outputs** |
> | D32 | 150,680 bytes, 17 stored outputs | **57,941 bytes, 0 stored outputs** |
> | D33 | 58,067 bytes, 0 stored outputs | 58,067 bytes, 0 stored outputs |
> | D01 | 58,089 bytes, 0 stored outputs | 58,089 bytes, 0 stored outputs |
>
> Two of four figures were right. The other two were wrong by roughly 92,700 bytes each, and
> every fact drawn "from the stored outputs" — the D01 self-identification, the announced
> synthetic fallback reported as a retrieval, the two RNG-derived scores — comes from outputs the
> audited artifacts do not contain. Those observations may well be true of some execution of
> those notebooks; they are not evidence about the corpus of record, and are not cited as such.
>
> **The retirement conclusion is unaffected and independently checkable.** It rests on the code
> being byte-identical — SHA-1 `9a5a5afdf75b`, 37,835 bytes, 11 code cells — which the manifest
> records as `code_source_sha256` and which `tests/test_retirement_basis.py` verifies against the
> external corpus. Eighteen of its twenty-two assertions pass there. The four that fail are the
> four that read stored outputs, which is how this was found.


## Reclassified, not ported

The seven root ML notebooks are not tutorials. They carry no estimand, no identification
strategy and no refutation test, while being named "causal". They move to a separate
research-review track and do not re-enter the tutorial corpus until they have one.
