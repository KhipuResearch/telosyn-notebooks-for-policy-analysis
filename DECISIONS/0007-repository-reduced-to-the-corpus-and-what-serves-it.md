<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# ADR 0007 — The Repository Is Reduced to the Corpus and What Serves It

- **Status:** Accepted, executed
- **Deciders:** Telosyn, Inc. (owner)
- **Date:** 2026-09-18

## 1. Title

The repository holds the corpus, the code that serves it, the tests that gate it,
and the records that explain it. Everything else is removed: 1,183 of 1,388
tracked files, including the frozen pre-rebuild corpus and the `khipu-showcase`
sub-project. Reader-facing documents state what is true now; `DECISIONS/` records
what changed. No document explains away a declaration a reader never saw, because
this repository has never been published.

## 2. Context

The deliverable is about 5 MB. The repository was 123 MB.

| | Files | Size | Imported by the corpus |
|---|---|---|---|
| `khipu-showcase/` | 117 | 60.0 MB | nothing |
| `notebooks/` (frozen archive) | 1,003 | 56.7 MB | nothing in `notebooks_v2/` |
| **`notebooks_v2/` — the corpus** | 77 | 3.6 MB | — |
| everything else | 191 | 2.6 MB | — |

Two things followed from preparing this repository to be publicly readable.

**The archive was not the audited artifact.** `notebooks/` was retained under
ADR 0005 §6 as audit evidence. But `docs/audits/audit_manifest_2026-09-13.jsonl`
verifies the copy under `KRL/backups/`, not the in-repo one, and the two had
diverged in ten notebooks. Checked directly, all **53** files in the external
corpus match the manifest byte for byte; the in-repo copy matched in 43. The
tree being kept for its evidentiary value was the copy without it — while
carrying truncated live API-key prefixes, ~282 operator home paths and retired
licence banners into a repository intended for public reading.

**The showcase was a second, unfinished project.** Its own `LICENSE`, MkDocs
site, Docker and Binder recipes, five roadmap and TODO documents, 52 MB of
notebooks with embedded plotting bundles, and badges and clone commands pointing
at `github.com/KR-Labs/khipu-showcase` — a repository that, as
`khipu-showcase/docs/about/license.md` itself records, does not exist.

## 3. Decision

Remove both trees, the five root packages that only the archive imported, the
tests that only exercised the archive, the internal audit-surface documents, and
the development logs. Reposition the reader-facing prose in the present tense.

## 4. What was removed, and why

| Removed | Reason |
|---|---|
| `notebooks/` (1,003 files) | Not the manifest-verified artifact; imported by nothing current; carried key prefixes and operator paths |
| `khipu-showcase/` (117 files) | Separate unfinished project, referenced by nothing, advertising a repository that does not exist |
| `sowellian_chains/`, `causal_workflow/`, `active_eligible_gap/`, `cultural_sowellian_chains/`, `cultural_network_helpers/` | Five packages at the repository root, imported only by the archive and by their own tests |
| `tests/` for those five, and `test_d{02,06,07,18,27}_l15_regression.py` + helper | Read notebooks in the removed archive |
| `SPEC.md`, `ARCHITECTURE.md`, `CALIBRATION_REQUIRED.md`, `CLAUDE.md` | Internal working documents; `CALIBRATION_REQUIRED.md` still held unfilled `<OWNER_TBD:…>` slots |
| `policy/` (4 files), `tests/README.md`, `.github/workflows/README.md`, `docs/WORKFLOWS.md` | Keyed to `SPEC.md` and the showcase's CI. All four described a repository that no longer exists — `tests/README.md` stated "0 test modules" against a suite of 1,525 |
| `docs/compound-notes/` (12), `docs/ce-findings/` (5) | Development logs about the retired corpus |
| Sphinx scaffolding, `.readthedocs.yml`, `.cspell.json`, `.markdownlint.json`, `.markdown-link-check.json` | Build and lint configuration for a docs site that is not built here |
| `docs/wiki/` (7 files, 2,375 lines) | Documented a corpus that has never existed — see below |

**The wiki described a different repository.** `Tutorial-Catalog.md` catalogued 33
tutorials under names and a directory scheme found in no version of this work
(`D02 Health Economics & Insurance`, `D04 Education Economics`,
`notebooks/01_economic/D01_income_wealth/`), sourced from NOAA, the UN, the World
Bank, OECD, Gallup, Pew, CMS, NCES, BJS and BRFSS — **none of which this corpus
uses**. The only occurrences of those names anywhere in `notebooks_v2/` are the
substring inside the word *references*. `Home.md` linked to nine wiki pages that
were never written. The corpus documents itself in
`notebooks_v2/DATA_SOURCE_HANDBOOK.md`, 2,270 lines against the sources actually
used; the wiki duplicated that badly and contradicted it.

**Two removals have a cost, stated plainly.** `CLAUDE.md` was the agent operating
brief, and the licence gate's `test_the_operating_brief_states_the_posture` went
with it. `.readthedocs.yml` was the Read the Docs build configuration; there is no
docs-site build in this repository now. Either can be restored.

The truncated key prefixes, the Jina key prefix and its length, the GCP project id
and the operator home paths were **redacted** in the two audit documents that
quote them rather than deleted — the finding is unchanged by redaction, the
material is not.

## 5. A finding the removal surfaced

`tests/test_retirement_basis.py` was re-pointed at the external corpus. Eighteen
of its twenty-two assertions passed there; four failed. They failed because they
read **stored outputs**, and the audited artifacts have none.

| | `notebooks_v2/MIGRATION.md` said | the manifest records |
|---|---|---|
| D31 | 150,815 bytes, 17 stored outputs | **58,077 bytes, 0 stored outputs** |
| D32 | 150,680 bytes, 17 stored outputs | **57,941 bytes, 0 stored outputs** |
| D33 | 58,067 bytes, 0 stored outputs | 58,067 bytes, 0 stored outputs |
| D01 | 58,089 bytes, 0 stored outputs | 58,089 bytes, 0 stored outputs |

The register was right about two of four files and wrong about the other two by
roughly 92,700 bytes each. Three further facts it drew "from the stored outputs"
— D31's output naming itself as D01, a synthetic fallback announced and then
reported as a Census retrieval, two RNG-derived scores as the sole difference
between D31 and D32 — come from outputs the audited artifacts do not contain.
They were measured from working-tree copies executed after the audit.

**The retirement conclusion stands.** It rests on the code being byte-identical,
which the manifest records as `code_source_sha256` and which the test verifies
against the external corpus. MIGRATION.md now carries the retraction; the three
tests that asserted the retracted facts are removed, because a test asserting a
claim its own register has withdrawn is worse than no test.

This is the second correction to that passage. The first (2026-09-15) retracted
"SHA-256 identical to D01". Both are kept: a register that hides its corrections
teaches nothing.

## 6. Repositioning

This repository was never published. No reader ever saw the retired MIT and
CC-BY-SA-4.0 declarations, so no document needs to explain them away. The history
paragraphs are removed from `README.md`, `CONTRIBUTING.md` and the wiki FAQ, and
`LICENCE_HISTORY_FILES` in the licence gate is now **empty** — the fence
mechanism remains, and nothing may use it. What changed is in `DECISIONS/0001`
and `DECISIONS/0005`, which is where it belongs.

## 7. Consequences

1. **Clone is ~5 MB of content** against 123 MB before; 205 tracked files against 1,388.
2. **The evidence chain is unbroken and better located.** `KRL/backups/` holds the manifest-verified corpus; `docs/audits/` holds the manifest and the audit; `DECISIONS/` holds the reasoning. `scripts/verify_forensic_corpus.py` already verified the external copy and is unaffected.
3. **`tests/test_retirement_basis.py` skips unless the archive is mounted**, via `KRL_ARCHIVE_ROOT`. A skip is honest: the artifact is not in this repository, and a test that passed without it would be checking nothing.
4. **The documented install was broken and is now checked.** `pytest.ini` puts `--cov` in `addopts`, and `addopts` is read before command-line `-o`, so `-o addopts=""` cannot waive it — yet no extra shipped `pytest-cov`. `[test]` now does, and `tests/test_documented_commands_work.py` fails if the README ever names an extra that cannot run the suite.
