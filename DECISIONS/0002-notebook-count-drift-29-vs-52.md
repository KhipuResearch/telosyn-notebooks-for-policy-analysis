<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# ADR 0002 — Notebook-Count Drift: "29 Interactive Notebooks" vs 52 Outer + 26 Showcase Files

- **Status:** Accepted as a Known Gap; remediation pending (single source of truth + CI gate)
- **Deciders:** `<OWNER_TBD:curriculum-owner>`
- **Date:** `<OWNER_TBD:adr-0002-decision-date>`

## 1. Title

Public and internal documentation state *"29 interactive Jupyter notebooks"*, while the working tree contains 52 `.ipynb` files under `notebooks/` plus 26 under `khipu-showcase/notebooks/`. This ADR establishes a single source-of-truth count, enumerates the causes of drift, and mandates a CI gate that blocks further divergence.

## 2. Context

Forensic inventory from `SPEC.md` §15 (every notebook enumerated with cell counts produced by `jq '.cells | length'`):

| Source | Claim | Evidence |
|---|---|---|
| `CLAUDE.md:3-4` | *"29 interactive Jupyter notebooks organized across 8 domains with 33 specialized topics"* | `CLAUDE.md:3-4` |
| `README.md:49` (pre-rewrite) | *"8 core domains with 29 interactive notebooks spanning 33 specialized topics"* | Superseded by Tier U rewrite |
| Outer `notebooks/` tree | **52** `.ipynb` files | `SPEC.md` §2.1, §15 |
| `khipu-showcase/notebooks/` tree | **26** `.ipynb` files (23 canonical + 1 duplicate + 2 validation + 1 executed-for-PDF) | `SPEC.md` §15.12 |
| `khipu-showcase/templates/` | **1** `notebook_template.ipynb` | `SPEC.md` §15.12 |

### 2.1 Breakdown of the outer 52-file count

| Domain code | Path | Canonical | Planned | Duplicates/Copies | Other |
|---|---|---:|---:|---:|---:|
| D01 | `notebooks/01_fundamentals/D01_income_and_poverty/` | 1 | 0 | 0 | 0 |
| D02 | `notebooks/01_fundamentals/D02_employment_and_labor/` | 1 | 0 | 0 | 0 |
| D03 | `notebooks/01_fundamentals/D03_education/` | 1 | 0 | 0 | 0 |
| D04 | `notebooks/02_health_housing/D04_health/` | 1 | 0 | 0 | 0 |
| D05 | `notebooks/02_health_housing/D05_housing/` | 1 | 0 | 0 | 0 |
| D06 | `notebooks/03_inequality_demographics/D06_inequality_and_wealth/` | 1 | 0 | 0 | 0 |
| D07 | `notebooks/03_inequality_demographics/D07_demographics_and_migration/` | 1 | 0 | 0 | 0 |
| D08 | `notebooks/04_economic_behavior/D08_consumer_behavior_and_spending/` | 1 | 0 | 0 | 0 |
| D09 | `notebooks/04_economic_behavior/D09_industry_and_economic_structure/` | 1 | 0 | 0 | 0 |
| D10 | `notebooks/05_social_systems/D10_social_mobility_and_opportunity/` | 1 | 0 | 0 | 0 |
| D11 | `notebooks/08_culture_society/D11_cultural_economics/` | 1 | 0 | 0 | 0 |
| D12 | `notebooks/06_infrastructure_environment/D12_environmental_economics/` | 1 | 0 | 0 | 0 |
| D13 | `notebooks/07_justice_equity/D13_crime_and_public_safety/` | 1 | 0 | 0 | 0 |
| D14 | `notebooks/06_infrastructure_environment/D14_transportation_and_commuting/` | 1 | 0 | 0 | 0 |
| D15 | `notebooks/04_economic_behavior/D15_business_and_entrepreneurship/` | 1 | 0 | 0 | 0 |
| D16 | `notebooks/06_infrastructure_environment/D16_internet_and_technology_access/` | 1 | 0 | 0 | 0 |
| D17 | `notebooks/06_infrastructure_environment/D17_food_security_and_agriculture/` | 1 | 0 | 0 | 0 |
| D18 | `notebooks/05_social_systems/D18_social_services_and_safety_net/` | 1 | 0 | 0 | 0 |
| D19 | `notebooks/05_social_systems/D19_civic_engagement_and_political/` | 1 | 0 | 0 | 0 |
| D20 | `notebooks/05_social_systems/D20_digital_economy/` | 1 | 0 | 0 | 0 |
| D21 | `notebooks/05_social_systems/D21_social_capital/` | 1 | 0 | 0 | 0 |
| D22 | `notebooks/08_culture_society/D22_cultural_consumption/` | 1 | 0 | 0 | 0 |
| D23 | `notebooks/07_justice_equity/D23_transportation_equity/` | 1 | 0 | 0 | 0 |
| D24 | `notebooks/07_justice_equity/D24_environmental_justice/` | 1 | 0 | 0 | 0 |
| D25 | `notebooks/08_culture_society/D25_food_and_nutrition/` | 1 | 0 | 0 | 0 |
| D26 | `notebooks/07_justice_equity/D26_public_safety/` | 1 | 0 | 0 | 0 |
| D27 | `notebooks/08_culture_society/D27_housing_affordability_and_gentrification/` | 1 | 0 | 0 | 0 |
| D28 | `notebooks/02_health_housing/D28_mental_health_and_wellbeing/` | 1 | 0 | 0 | 0 |
| D29 | `notebooks/05_social_systems/D29_innovation_and_entrepreneurship/` | 1 | 0 | 0 | 0 |
| D30 | `notebooks/09_planned/D30_subjective_wellbeing/` | 0 | 1 | 0 | 0 |
| D31 | `notebooks/09_planned/D31_civic_trust/` | 0 | 1 | 0 | 0 |
| D32 | `notebooks/09_planned/D32_freedom_civil/` | 0 | 1 | 0 | 0 |
| D33 | `notebooks/09_planned/D33_gender_equality/` | 0 | 1 | 0 | 0 |
| D34 | `notebooks/10_advanced_nlp/D34_media_intelligence/` | 1 | 0 | **11** | 0 |
| — | `notebooks/*.ipynb` (flat, advanced ML) | 7 | 0 | 1 | 1 (empty `test_kernel.ipynb`) |
| **Totals** | — | **36 canonical** | **4 planned** | **12 duplicates/copies** | **1 empty kernel** → = **52 .ipynb** files |

The tagline "29 interactive notebooks" is reproduced in internal documentation but does not map cleanly to any of the natural cuts:

- 29 ≠ 36 canonical (D01–D29 gives 29; D34 + 7 flat = 8 more; the tagline evidently pre-dates D30–D34 and the flat ML notebooks).
- 29 ≠ 52 total tracked files.
- 29 ≠ 36 + 4 planned = 40 canonical-plus-planned.

The most coherent reading: the "29" count is the D01–D29 canonical set that existed at an earlier commit, before the `09_planned/` domain, `10_advanced_nlp/` domain, and the flat advanced-ML notebooks were added. No subsequent commit updated the tagline.

### 2.2 Breakdown of the 26-file showcase count

| File | Count |
|---|---:|
| Canonical numbered `01-*.ipynb` through `25-*.ipynb` (with gaps at 08, 09, 24; two `17-*` entries) | 23 |
| `pdf_exports/11-heterogeneous-treatment-effects_executed.ipynb` | 1 |
| `validation/NB_VALIDATION_DID.ipynb` | 1 |
| `validation/NB_VALIDATION_SCM.ipynb` | 1 |
| **Total under `khipu-showcase/notebooks/`** | **26** |
| `khipu-showcase/templates/notebook_template.ipynb` | 1 (not counted in notebooks/) |

The public catalog gaps at 08, 09, 24 (`SPEC.md` §15.12) are a separate drift — the numbering implies a 25-notebook sequence; only 22 + the duplicate-numbered `17-spatial-causal-fusion.ipynb` exist.

## 3. Decision

1. **The single source-of-truth notebook count is a machine-generated manifest**, not a hard-coded number in prose. The manifest MUST be produced by a CI step that walks `notebooks/**/*.ipynb` and `khipu-showcase/notebooks/**/*.ipynb`, classifies each entry (canonical / planned / duplicate / validation / executed-for-PDF / empty-kernel), and emits a `docs/notebook_manifest.json` artifact on every `main` push.
2. **Prose documentation MUST NOT state a hard-coded notebook count.** `README.md` (post-rewrite) no longer states a count. `CLAUDE.md:3-4` and any future revision MUST reference the manifest instead of a literal number.
3. **Three categorical axes are authoritative going forward:**
   - **`Dnn` domain code** (D01–D34 today; expandable to D99)
   - **Status** (`canonical` | `planned` | `duplicate` | `validation` | `executed_for_pdf` | `empty_kernel`)
   - **Surface** (`outer` | `showcase` | `template`)
4. **A CI gate (`notebook-inventory-gate`) MUST fail** when any notebook is missing a `Dnn` prefix, when a duplicate is not classified in the manifest, or when the manifest is stale relative to the tree.
5. **`tutorial-quality.yml:78-100` tier-axis code (`D1`–`D6`) is incorrect and MUST be replaced** with the `Dnn` axis declared in §3 above. The present implementation reports `Missing tutorials in tiers: ['D1', 'D2', 'D3', 'D4', 'D5', 'D6']` on every run because every notebook uses a `Dnn` prefix, not a `Dn` prefix. Non-blocking today, but noisy.
6. **The 11 duplicate variants in `10_advanced_nlp/D34_media_intelligence/` and the duplicate `economic_forecasting_transformer copy.ipynb` + duplicate `17-*.ipynb` pair MUST be resolved** before the manifest is considered stable. Either (a) pick one canonical form per topic and delete the rest, or (b) rename variants to carry explicit semantic distinctions (`_v3_production.ipynb`, `_advanced_edition.ipynb`, etc.) and mark them `duplicate` in the manifest.
7. **`notebooks/test_kernel.ipynb`** (0 cells) MUST be renamed `_scratch/kernel_smoke_test.ipynb` or deleted. An empty notebook at the root confuses learners browsing the flat advanced-ML set.

## 4. Alternatives Considered

### Alternative A — Update the "29" tagline to "52" and leave duplicates in place

**Rejected because:** updating to 52 immortalizes duplicate clutter as real content. The 52 number is not a curriculum count; it is a file count inflated by `copy`, `copy 2`, `copy 3`, `copy 4` artifacts. Advertising 52 to learners misrepresents the product.

### Alternative B — Delete every duplicate and every `09_planned/` placeholder; advertise a smaller canonical count

**Rejected at this commit because:** the `09_planned/` placeholders are intentional scaffolds for future tutorials (`CLAUDE.md:22`). Deleting them removes commitment signals to learners. Deletion of advanced-NLP duplicates alone is safe and recommended as a follow-up PR, but the manifest-based approach handles the semantics correctly either way.

### Alternative C — Hard-code the count in `CLAUDE.md` + `README.md` + a CI gate that greps for the number

**Rejected because:** hand-counting is exactly the pattern that drifted to 29 while the tree grew past 52. Any substitute based on human-maintained literals will drift again. A machine-readable manifest is the only self-correcting solution.

### Alternative D — Keep the drift as documented but non-blocking

**Rejected because:** the drift affects learner expectations (`README.md:49` is the first thing a prospective contributor reads) and contradicts the `CLAUDE.md:4` operating brief that steers AI-assisted tooling. Both surfaces are load-bearing.

## 5. Trade-offs Accepted

- **Every PR that adds a notebook MUST also update the manifest** (or the CI step regenerates it). This is one additional merge step per content PR.
- **Duplicate cleanup is cross-cutting** — resolving the 11 `D34_media_intelligence/` variants plus the `economic_forecasting_transformer copy.ipynb` and the dual `17-*.ipynb` showcase pair requires editorial decisions, not mechanical edits. The manifest CI gate can surface the duplicates but cannot adjudicate which is canonical.
- **Manifest JSON becomes a new artifact** that must itself be versioned and diff-reviewed. Accepting this governance surface is the cost of eliminating prose drift.
- **`09_planned/` placeholders remain counted as `planned` in the manifest.** Learners see them as coming-soon rather than fully formed — this is the correct signal but requires narrative alignment in `CLAUDE.md` and Sphinx intro pages.

## 6. Consequences

- `README.md` (Tier U rewrite) removes the "29 notebooks" tagline in favor of referencing `SPEC.md` §15 for the authoritative inventory.
- `CLAUDE.md:3-4` and `CLAUDE.md:43` (Content Standards) MUST be corrected in a follow-up PR per `CALIBRATION_REQUIRED.md`.
- `tutorial-quality.yml:78-100` MUST be corrected to use the `Dnn` axis; until then, CI continues to print the `Missing tutorials in tiers: ['D1', 'D2', 'D3', 'D4', 'D5', 'D6']` warning on every run.
- `policy/ci-authority.yaml` declares `CLAUDE.md` and `README.md` as `must_never_modify` for CI auto-fix agents — the manifest update required here must land via human PR.
- `khipu-showcase/notebooks/` catalog gaps at 08, 09, 24 are a parallel drift not covered by this ADR. They are documented in `SPEC.md` §15.12 and tracked as a separate `CALIBRATION_REQUIRED.md` item.
- Future notebook additions under new domain codes (`D35+`) proceed automatically through the manifest without prose edits.

## 7. Reversal Conditions

This ADR is reversed when **all** of the following are true:

1. `docs/notebook_manifest.json` exists and is regenerated by CI on every `main` push.
2. `CLAUDE.md` and `README.md` contain zero hard-coded notebook counts.
3. A `notebook-inventory-gate` CI step blocks merge on manifest staleness or on notebooks lacking a `Dnn` prefix.
4. The 11 duplicate variants in `10_advanced_nlp/D34_media_intelligence/` are either resolved to one canonical plus renamed variants, or deleted.
5. `tutorial-quality.yml:78-100` tier-axis logic is rewritten around the `Dnn` axis.
6. `notebooks/test_kernel.ipynb` is moved out of the content path or deleted.
7. `khipu-showcase/notebooks/` catalog gaps at 08, 09, 24 are either filled, renumbered, or explicitly declared reserved in the manifest.

At that point, a follow-up ADR (0004+) records the remediation outcome and this ADR is marked **Superseded**.
