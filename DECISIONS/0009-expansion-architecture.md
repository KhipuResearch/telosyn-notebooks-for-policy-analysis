<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# ADR 0009 — Expansion Architecture: an Identification Layer under the Corpus's Invariants

- **Status:** Accepted, in execution (Timebox 0)
- **Deciders:** Telosyn, Inc. (owner)
- **Date:** 2026-10-15
- **Amended 2026-10-15:** precedence of a pre-analysis plan over the data is proven by digest equality (notebook declaration = plan file = `pap_sha256` in every provenance record), not by commit time; commit order is a warning, and §3.2 rule 3–4 and the fail-closed clause read accordingly.
- **Amended 2026-10-23:** C06 does not adopt `linearmodels`: the exactly identified, one-instrument case is short enough to implement and test in `methods/iv.py` (§3.6), against the textbook projection form, so no dependency is added. `fetch_acs_pums` also gains `keep`, `bands` and pooled states, still returning cells only (§3.8).
- **Amended 2026-10-16:** the PUMS and CPS ASEC clients return cells only and have no row-level path at all (§3.8); the public-surface check reads its name patterns from a private denylist outside the repository (§3.10).

## 1. Title

The corpus gains projects `09`–`14`: identification, economic appraisal,
distribution, synthesis and implementation (project `12`, simulation, is
designed here and held to the next release). They are built on the same
retrieval, provenance and gate machinery as projects `01`–`08`, plus four
additions: an identification contract, a pre-analysis-plan rule, a
policy-reference-table convention and a tested `methods` subpackage.

## 2. Context

ADR 0008 recorded that the first 33 notebooks contain no causal claim, by design:
for each source they say what a number measures, what it withholds and what
conclusion it cannot carry. It also left the layout open for a causal track
beginning at `09-`.

A policy decision needs the layer that corpus deliberately omits, in the order
the evidence hierarchy ranks it: what changed because of a policy (identification),
whether it was worth it (appraisal), for whom (distribution), whether it
replicates (synthesis) and whether it reaches the people it names
(implementation).

Adding that layer weakens nothing the corpus claims **unless** the new notebooks
inherit its invariants. Three carry over unchanged: every number traces to a
pinned retrieval; uncertainty is carried, never dropped; and each notebook states
the specific conclusion its design is not entitled to. This ADR adds a fourth:
**every causal estimate ships with its identification assumption, a falsification
test that was actually run, and a pre-analysis plan committed before the data
were retrieved.**

## 3. Decision

### 3.1 Data modes

`krl.data_mode` keeps its two values in use. A third, `model`, is **designed and
not released**.

| Mode | Meaning | Where allowed | Gate treatment |
|---|---|---|---|
| `empirical` | Every number traces to a pinned retrieval | Everywhere | Unchanged |
| `illustrative` | Simulated to teach a statistical property | D30 only | Unchanged |
| `model` | A structural or stochastic model calibrated to pinned inputs; scenario outputs, not evidence | Project 12 only | **Not built this release** |

The pedagogy gate already accepts `estimated` and `hypothetical` as `data_mode`
values, and the no-synthetic gate fails any random generator outside a notebook
declaring `illustrative`; both are left exactly as they are. `model` is
**reserved and not accepted**: a test asserts that a notebook declaring it fails
with a message that names this ADR, so the reservation is enforced rather than
remembered.

When `model` is released it requires, in `krl.model`, a seed, the list of
calibration sources (each with a provenance record) and the verbatim disclosure
banner as the first markdown cell, and it is accepted under `projects/12-*/`
only. Until then **no notebook may declare it**. D30's exemption is unchanged.
`DataMode` in `provenance.py` is likewise not extended in this release; a member
that no gate constrains would be a permission with no check behind it.

### 3.2 Identification contract

`krl.identification` is required on every notebook in project `09` and on
Q01, Q02 and M01. Its fields are `design`, `estimand`, `assumption`,
`falsification` (a list of `{test, cell, result}`), `inference`, `pap` and
`pap_sha256`. A gate enforces it mechanically:

1. every listed falsification `cell` exists, is a code cell and has stored output;
2. that output contains a line beginning `FALSIFICATION:` that carries
   `statistic=<number>` and `verdict=PASS` or `verdict=FAIL`, so a bare string
   cannot satisfy it. A `FAIL` is a finding, reported and not tuned away;
3. `pap_sha256` equals the SHA-256 of the committed PAP file;
4. the PAP's first git commit predates the earliest committed
   `retrieved_utc` among the notebook's provenance records.

Three details come from reading the repository rather than the plan:

- The provenance field is `retrieved_utc`, not `retrieved_at`.
- D01 and D03 print a provenance block but **write no record**; a record is only
  a file when the notebook calls `DataProvenance.write`. Every notebook in
  projects 09–14 must write one per retrieval, and the gate fails a notebook that
  declares an identification block and has none, because rule 4 would otherwise
  pass vacuously.
- `artifact_class` already has a value for this work, `causal_analysis`. No
  `causal` or `synthesis` class is added and the pedagogy gate's vocabulary is
  unchanged: M01 and Q01/Q02 declare `causal_analysis`.

The gate applies to every notebook that declares `krl.identification`, and to
every notebook under `projects/09-*/` or `projects/13-*/`, and to any under
`projects/11-*/` with `artifact_class: causal_analysis`, so omitting the block is
itself a failure. It **fails closed**: if git history is unavailable (a shallow
clone) the gate errors rather than skipping, and CI fetches full history.

A falsification is a test that **could** have failed. A notebook whose
falsification fails reports that as its finding; the design is not tuned until
it passes.

### 3.3 Pre-analysis plan

One short markdown file per causal notebook, committed before the first
retrieval: outcome, treatment definition, sample, estimator, covariates,
falsification tests, and the result that would count as "no effect". The
notebook's Limitations section states whether the analysis departed from the plan
and why. Binding means the gate in §3.2, not the author's intention.

### 3.4 Policy reference tables

Treatment timing comes from authoritative non-API sources. Convention, following
`data/hud/`: `data/policy/<topic>/<file>.csv` with a `SOURCES.md` beside it
recording publisher, URL, access date, SHA-256 of the downloaded original and the
transformation applied, and the transformation itself committed under `scripts/`.
A table is never typed from memory. If the publisher page cannot be reached, the
card is blocked and the question is recorded.

### 3.5 Methods subpackage

`src/krl_tutorials_data/methods/` holds the estimators the notebooks share:
`did`, `rdd`, `synth`, `matching`, `meta`, `cea`, `discount`. Functions are pure,
typed and perform no I/O. Each module is held to at least 95% line coverage with
known-answer tests against small hand-computed cases and property-based tests on
the estimators. `statsmodels` is imported lazily where cluster-robust OLS is
needed, with an error that names the `notebooks` extra.

### 3.6 Dependency policy

Runtime dependencies are unchanged. The `notebooks` extra gains at most
`linearmodels`, and only if `statsmodels` proves insufficient for the IV card
(C06); that choice is documented when made. A new optional `methods` extra may
hold packages that a single Could-tier notebook needs. Every addition requires
existence verified on PyPI at execution time, a pinned lower bound, a
cost–benefit paragraph appended to this ADR, and an update to the
declared-imports test: nothing is imported that is not declared and nothing is
declared that is not imported.

| Package | Used by | Status this release |
|---|---|---|
| `linearmodels` | C06 | **Not adopted** (2026-10-23): the C06 design is one endogenous regressor and one instrument, so the estimator is written in `methods/iv.py` (about 100 lines, tested against the projection form) and no dependency is added |
| `pymc` | Q03 | Could; verified and declared only if Q03 is released |
| `econml` | Q02 | Could; verified and declared only if Q02 is released |
| `mesa` | S03 | Deferred with project 12 |
| `policyengine-us` | E04 | **Deferred**: a CI increase above five minutes is not accepted |

### 3.7 Numbering and layout

Notebook identifiers are prefixed by track (`C`, `E`, `Q`, `S`, `M`, `I`) and
never reuse a retired `D`-number. Layout is the existing one:
`projects/<NN-slug>/<ID_slug>/<ID_slug>.ipynb` with a sibling `provenance/`
folder. Generated READMEs, the project index, the source map and the handbook are
updated in the same change as the notebook.

### 3.8 Person-level microdata

ACS PUMS and CPS ASEC are retrieved through clients that return **weighted
aggregates only**. There is no row-level return and no argument that asks for one:
the client reads person records into a frame that exists only inside the call,
reads it in one private function that returns weighted cells, and a gate keeps any
notebook from reaching for the person frame. No person-level row is printed,
stored in an output or written inside the repository. Analyses that would have used
person rows (C05, C06) are specified on cells: covariates discretised, estimators
weighted by cell population. *(Amended 2026-10-16; the first version of this
section allowed an opt-in row return behind a gated argument.)*

### 3.9 Retrieval, hashing and vintage for new sources

New fetchers meet the standard the handbook set in §5 and §11 rather than
rediscovering it. Each declares a `hash_basis` and hashes through that basis's
helper, never over bytes the publisher does not hold stable: PUMS and CPS
aggregates use `canonical-rows`, because Census does not hold row order. Each
decides `vintage_pinned` explicitly (a PUMS release year is a separately
addressed immutable asset, so `true`), and `tests/test_provenance_pinning.py`
carries the per-source judgement. Policy tables are bulk files pinned by SHA-256
under §5.3 of the handbook. Responses that arrive as HTTP 200 with an error body,
jam values and truncated pages are guarded by content, not status line.

### 3.10 Gate discipline

A rule with no gate is a preference (handbook §11, row 21), and a gate that
cannot fail is counted as coverage (§11, closing). Every new gate therefore ships
with a compliant fixture and a planted-violation fixture, and is mutation-tested:
the defect it exists to catch is introduced and the gate is confirmed to fail.
A gate is never weakened to make a notebook pass.

The public-surface check (`scripts/check_public_surface.py`) is held to the same rule and one more: the patterns that name what must not be published are themselves not published. They live in a private denylist read from `KRL_SURFACE_DENYLIST`; the check exits with status 2, never 0, when that file is absent. CI holds no secret and so runs only the public rules (`--public-rules`), and says so; the private rules run locally. Its repository tests use a synthetic denylist. Lines that legitimately match are listed individually, each with its reason, in an allowlist that the check also verifies is not stale.

### 3.11 Where this work is authored

ADR 0008 §6.1 records that changes to the corpus are made in a private source of
record and re-exported. Projects 09–14, `methods/`, the new fetchers and the new
gates are authored **in this repository**, because the identification gate reads
this repository's git history and cannot be satisfied by an export. Whether the
export path also carries them back is an owner question and is recorded in the
delivery log; this ADR does not decide it.

## 4. Alternatives rejected

| Alternative | Why not |
|---|---|
| A separate repository for the causal track | Splits the gate regime, the provenance machinery and the handbook in two; every invariant would have to be re-implemented and kept in step, and the corpus's central claim, that the rules are mechanical, would become a convention |
| Causal notebooks without pre-analysis plans | An estimate chosen after seeing the data is a different object from one chosen before. Without the plan the falsification tests become decoration, and the corpus would be asserting identification it cannot show |
| A `model` mode available in every project | It would reopen the synthetic-data hole the no-synthetic gate exists to close. Scenario output sitting beside estimates in the same directory is exactly the reading error the corpus teaches against |
| Extending `DataMode` with `model` now | A member with no gate behind it is an unchecked permission; deferred with the project that needs it |
| Fixed-effects regression alone for staggered adoption | Its weights can be negative; C03 exists to show this, and a shared `did` module must therefore carry a decomposition and a heterogeneity-robust estimator |

## 5. Consequences

1. The corpus's first causal claims are stored together with the falsification
   that tested them and the plan that preceded them; a reader can see both without
   running anything.
2. Writing a causal notebook becomes slower by design: the plan, its digest and
   the policy table all precede the first retrieval.
3. `methods/` becomes a maintained surface with a coverage floor. A defect there
   propagates to every notebook that uses it, so changes to it are reviewed as
   estimator changes, not as refactors.
4. The repository-wide coverage floor ratchets up after each timebox and never
   down.
5. Project 12, the `model` mode and E04 are recorded as deferred with their
   design intact, so they are not re-litigated when released.
6. Public-visibility rules from ADR 0005 and ADR 0008 carry over without change,
   and are checked by a script rather than by a reader.

## 6. Gates affected

| Gate / test | Change |
|---|---|
| `test_gate_identification` | **New** — §3.2 |
| `test_gate_no_synthetic` | Unchanged this release; extended when `model` is released |
| `test_gate_claims`, `_evidence`, `_statistical`, `_vintage`, `_pedagogy`, `_executable`, `_security`, `_license_consistency` | Unchanged; apply to every new notebook |
| `test_gate_pedagogy` | Unchanged; `causal_analysis` and the existing modes already validate |
| Declared-imports test | Updated with every dependency addition |
| `scripts/check_public_surface.py` | **New** — public-visibility checklist as code, run in `make check` |
| README / data-README generators | Titles for projects 09–14; policy tables listed |

## 7. Failure modes of this design

| # | Failure mode | Mitigation or accepted risk |
|---|---|---|
| 1 | **Squash defeats the PAP-before-retrieval check.** One commit per card on merge puts the PAP and the notebook in one commit dated after the retrieval, so a history-based check fails on `main`, or passes for the wrong reason | The PAP is committed and merged as its own commit before the notebook's commit, which makes two commits for a causal card. Whether the hosting platform's squash preserves the author date is **not verified**; F03 must test it against real history before the gate is relied on. Owner decision recorded in the delivery log |
| 2 | **A re-run overwrites the first retrieval's record**, so `retrieved_utc` on disk is the latest, always after the PAP | The gate reads the earliest committed version of each record from history, not the working copy. Accepted: a record never committed is invisible to it |
| 3 | **`FALSIFICATION:` is a string.** A notebook can print the line without running a test | The line must carry the computed statistic and a verdict token, and the claims gate ties figures in prose to stored output. A printed constant with the right shape still passes; that residual is reviewed by reading the cell, which no gate replaces |
| 4 | **A shared estimator defect propagates to every notebook**, and the author's known-answer tests share the author's understanding of the estimator | Hand-computed cases, property-based tests, and a cross-check against `statsmodels` where one exists. Accepted for matching and synthetic control, where no second implementation is in the dependency set |
| 5 | **The reserved `model` mode is circumvented by a neighbour**: a model notebook declared `estimated` or `hypothetical`, which the pedagogy gate already accepts | The no-synthetic gate fails any random generator outside `illustrative`, independent of the declared mode, and is not changed. A deterministic scenario model with no RNG would pass it; that is a review matter until `model` ships |
