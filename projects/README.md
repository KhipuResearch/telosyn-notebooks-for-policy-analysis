# projects — the rebuilt tutorial corpus

This is the corpus. It replaced an earlier tree that the audit of 2026-09-13
covered; that tree is not in this repository, because the manifest verifies the
copy held outside it and the in-repo copy had drifted from it. See `DECISIONS/0007`.

## The contract every notebook here meets

> A notebook is releasable only if its executable state, data provenance, computational
> results, statistical interpretation and narrative claims are mutually consistent, and
> every reported quantity is explicitly classified as empirical, estimated, illustrative
> or hypothetical.

## Real data only

There is no synthetic generator and no fallback path in `krl_tutorials_data`. A notebook
that cannot obtain real data raises and stops. The `DataMode` enum deliberately has no
`SYNTHETIC` member. Randomness is permitted only in a notebook that declares
`krl.data_mode = "illustrative"`, and `test_no_randomness_in_analysis_path` enforces it.

## Required metadata

```json
"krl": {
  "artifact_class": "tutorial",       // demo | simulation | tutorial | exploratory
                                      // predictive_study | causal_analysis | external_facing
  "data_mode": "empirical",           // empirical | estimated | illustrative | hypothetical
  "target_column": "poverty_rate",    // named, never inferred from column order
  "vintage_pinned": true,
  "synthetic_fallback": false,
  "release_status": "review_required"
}
```

## The 19 blocking gates

| Gate | Catches |
|---|---|
| `test_every_code_cell_compiles` | F-1 — 31 of 33 notebooks could not parse |
| `test_no_code_parked_in_markdown` | F-11 — failing cells demoted to markdown to fake a clean run |
| `test_no_rng_derived_metrics` | F-2 — `np.random` reported as model Complexity/Interpretability |
| `test_no_randomness_in_analysis_path` | the real-data constraint |
| `test_no_hardcoded_metric_in_exception_handler` | F-9 — silhouette constants inside a bare `except:` |
| `test_no_bare_except` | F-9 — data failure converted to silent substitution |
| `test_target_is_not_selected_by_column_position` | F-3 — R²=1.000 against a constant `year` column |
| `test_target_is_named_and_validated` | F-3 — implicit or constant target |
| `test_preprocessing_is_not_fitted_before_the_split` | F-12 — test-set statistics baked into training |
| `test_no_hardcoded_performance_claims` | F-4 — ">85% accuracy" with no computational antecedent |
| `test_categorical_assertions_are_computed` | F-4, F-7 — asserted conclusions that cannot drift with the data |
| `test_no_key_material_in_outputs` | F-14 — live key prefixes in committed outputs |
| `test_no_absolute_developer_paths` | 282 hardcoded `/Users/...` paths |
| `test_no_license_bypass` | `skip_license_check` in 7 notebooks |
| `test_artifact_class_is_declared` | the metadata contract |
| `test_required_sections_present` | F-15 — objectives and exercises, previously unenforced |
| `test_every_code_cell_carries_an_execution_count` | F-1, F-2 — an artifact that evidences no run |
| `test_execution_counts_are_a_single_ordered_run` | outputs that cannot be attributed to one top-to-bottom run |
| `test_a_notebook_that_reports_results_stores_some_output` | a narrative with nothing to check it against |

Run them: `KRL_NOTEBOOK_ROOT=projects pytest tests/ -v`

The three evidence gates were added after the then-five notebooks in this tree had been described
as executed against live data while **three of them stored no output and carried no execution
count at all** — the exact F-1/F-2 signature, in the corpus built to prevent it. They were
re-executed; the gate now makes the claim unfalsifiable by inspection rather than by assertion.
It fails 83 of 159 checks against the archived corpus.

## Corpus documents

| File | What it is |
|---|---|
| `DATA_SOURCE_HANDBOOK.md` | The corpus's own guidance: the six data regimes, the sentinel catalogue, source-selection and vintage rules, and the defects found in this build. Every figure is traceable to a notebook and gated by `tests/test_handbook_traceability.py` |
| `SOURCE_MAP.md` | Which notebook draws on which dataset, and via which fetcher |
| `MIGRATION.md` | What changed from `notebooks/`, domain by domain |
| `../DECISIONS/` | Architecture decision records, including 0004 on the upstream connector boundary |

## Status

| Notebook | Supersedes | Gates | Executed against live data |
|---|---|---|---|
| `D01_income_and_poverty` | `D01_D01_income_and_poverty.ipynb` | 19/19 | yes — ACS 2023 5-Year |
| `D03_education` | `D03_D03_education.ipynb` | 19/19 | yes — ACS 2023 5-Year |
| `D06_inequality_and_wealth` | `D06_D06_inequality_and_wealth.ipynb` | 19/19 | yes — ACS 2023 5-Year |
| `D07_demographics_and_migration` | `D07_D07_demographics_and_migration.ipynb` | 19/19 | yes — ACS 2023 5-Year |
| `D16_internet_and_technology_access` | `D16_D16_...ipynb`, part of `D20_D20_...ipynb` | 19/19 | yes — ACS 2023 5-Year |
| `D27_rent_burden` | `D27_D27_housing_affordability_and_gentrification.ipynb` (rent burden half) | 19/19 | yes — ACS 2023 5-Year |
| `D27_gentrification` | `D27_D27_...ipynb` (gentrification half) | 19/19 | yes — ACS 2023, Zillow 2026-08, FRED |
| `D02_employment_and_labor` | `D02_D02_employment_and_labor.ipynb` | 19/19 | yes — BLS LAUS 2019–2024, ACS 2023 |
| `D08_consumer_spending` | `D08_D08_consumer_spending.ipynb` | 19/19 | yes — FRED/ALFRED pinned vintages |
| `D09_industry_structure` | `D09_D09_industry_structure.ipynb` | 19/19 | yes — QCEW 2024Q1 (no key needed) |
| `D15_business_and_entrepreneurship` | `D15_D15_...ipynb` | 19/19 | yes — CBP 2022 + QCEW 2022Q1 |
| remaining domains | — | not yet built | — |

Gate runs are also exercised **against the archived corpus** (`KRL_NOTEBOOK_ROOT=notebooks/`)
whenever a gate is narrowed, to prove it was made more precise rather than merely quieter. A
narrowing that stops the archived corpus failing has been blunted, not fixed.

## Execution environment — a known inconsistency

`pyproject.toml` declares `requires-python = ">=3.11"`. The six notebooks in this tree were
executed in an isolated environment where only **Python 3.10.12** was available, and each artifact's
`language_info` truthfully records that. The artifacts therefore carry an execution-environment
stamp that does not match the project's declared floor.

What has been verified instead: every notebook code cell (64) and every data-layer, test and
script module (28) **compiles under Python 3.11.15**, checked with a real 3.11 interpreter. The
corpus uses no version-specific syntax, and F-1 in the archived corpus turned on exactly this
class of problem — PEP 701 nested same-quote f-strings, which are legal on 3.12+ and a
`SyntaxError` on 3.11 and below — so the check is not theoretical.

**Outstanding:** re-execute on 3.11 or later in an environment that matches the declared floor,
so the recorded `language_info` and `requires-python` agree. Until then this paragraph is the
disclosure.

## The data layer

| Module | Provides |
|---|---|
| `provenance.py` | `DataProvenance`, `DataMode` — no `SYNTHETIC` member exists |
| `sources.py` | `fetch_acs`, `fetch_acs_wide`, `fetch_fred`, `fetch_bls`, `fetch_qcew`, `fetch_cbp`; credential allowlist, jam-value handling, 200+HTML rejection |
| `uncertainty.py` | ACS margins of error at 90%, aggregation, proportions, significance, Holm and BH |
| `inequality.py` | Lorenz, Gini, Theil, Atkinson, percentile ratios, top-share identification guard |
| `standardization.py` | direct age standardisation, the Kitagawa decomposition, correlation bounds |
| `reliability.py` | CV screen with named thresholds, exact rank-interval bounds, boundary-artefact detection |
| `tabulation.py` | `check_partition` — whether published categories actually sum to their parent |
| `brackets.py` | percentile interpolation from bracket counts, with an open-bracket identification guard |
| `connectors.py` | read-only adapters over `krl-data-connectors`; vintage pinning and digest verification for bulk files |

### Relationship to `krl-data-connectors`

This repository declares `krl-data-connectors>=1.0.0` as a **hard** dependency
(`pyproject.toml:36`). `krl_tutorials_data` was written beside it, not on top of it. Having read
the connector, the two are not redundant: `CensusACSPublicConnector` has no margin-of-error
concept, no ACS jam-value handling, no HTTP-200-plus-HTML check and a bare `except Exception`,
while every rebuilt notebook here turns on margins of error and on jam values being removed
before arithmetic.

**Ruling (ADR 0004): the connector package is upstream and read-only.** `krl_tutorials_data`
adapts it from above — no edits, no subclass overrides, no monkey-patching, no writes into its
tree — and is deliberately *not* refactored onto `BaseConnector`, which would couple this repo's
release contract to a class it does not own.

`connectors.py` is that adapter. The connector does the fetching, parsing, caching, rate limiting
and licensing; the adapter adds what the tutorial contract needs and the connector does not carry:
a **mandatory vintage label**, a **SHA-256 pin over the bytes actually read**, fail-closed errors
that subclass `DataAccessError`, and a `DataProvenance` record naming the publisher and terms.

That is the piece that was genuinely missing for bulk sources. The connectors existed; what a
notebook could not do was say *which* download it used, because bulk publishers overwrite files in
place. Run once unpinned, paste the reported digest into the pin, and every later run proves it
read identical bytes. Two properties are enforced by test rather than convention: adapters never
write into the upstream tree, and the upstream import is lazy and by string — a module-scope
import would break every Census-only notebook where the package is absent.

`fetch_acs_wide` exists because the Census API caps `get` at 50 names and returns a bare
`HTTP 400` above it. It splits the request and verifies that every batch returned the identical
geography key set before joining, since a silently misaligned join would corrupt every rate
without raising.

`sources.redact()` scrubs credentials from every error message the layer raises. During
development a live key was echoed into a traceback, because `requests` exceptions carry the request
URL and both the Census and FRED APIs take their key as a **query parameter** — so interpolating an
exception into an error string publishes the credential into logs, tracebacks and stored notebook
outputs. That is F-14 occurring inside the library rather than inside a notebook, which the
notebook-output gate could not have caught. It redacts recognised credential parameters and any
literal secret value the process has loaded, and `tests/test_redaction.py` asserts that no fetcher
interpolates an exception without it.

`fetch_bls` checks the **status field, not the status code**: the BLS API signals a rejected
request with HTTP 200 and `REQUEST_NOT_PROCESSED` in the body, so treating 200 as success would
accept an error payload as data — the Census HTML masquerade in a different costume. It also
batches at the API's 50-series ceiling and fails closed if any requested series comes back absent.

`reliability.py` separates two screens that are routinely conflated. A coefficient-of-variation
test certifies that an **estimate's level** is precise; a league table consumes its **rank**.
For shares near 1 these come apart almost entirely — in D16, 3,217 of 3,222 counties pass the
conventional CV screen and not one has a determined rank. `rank_intervals` gives the exact
interval-overlap bound, which makes no distributional or independence assumption and therefore
cannot understate the ambiguity.

## Verifying the audited corpus

The audited corpus must stay byte-identical to what the audit recorded, or every
SHA-256 and cell index in `docs/audits/` becomes meaningless. It lives outside this
repository; point the verifier at it.

```
KRL_AUDITED_TREE=/path/to/tree python scripts/verify_forensic_corpus.py          # exit 0 = intact
KRL_AUDITED_TREE=/path/to/tree KRL_AUDIT_NAMEMAP=<operator-path>/audit_namemap_2026-09-13.json \
    python scripts/verify_forensic_corpus.py
```

The check is fail-closed by design: an unresolvable manifest path is an error, never a prompt
to go looking for a file with the same name somewhere else. An ad-hoc version of this check
that did fall back to basename matching reported ten notebooks as modified when none were.
