<!--
© 2026 Telosyn, Inc. All rights reserved.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# ADR 0001 — Dual-License Advertising (MIT + CC-BY-SA-4.0) Contradicts Proprietary `LICENSE*` Files

- **Status:** **Remediated 2026-09-18.** Accepted as a Known Gap on the original date;
  the decision below stands unchanged and the action items are now carried out.
- **Deciders:** `<OWNER_TBD:legal-and-engineering-lead>`
- **Date:** `<OWNER_TBD:adr-0001-decision-date>`

## 1. Title

`the private source repository` carries three mutually contradictory license declarations. `LICENSE`, `LICENSE-CODE`, and `LICENSE-CONTENT` are byte-identical proprietary text; `pyproject.toml:49-50` declares `LicenseRef-Proprietary`; `README.md:150-173` (pre-rewrite) advertised MIT for code + CC-BY-SA-4.0 for content; notebook cell-0 banners declare `SPDX-License-Identifier: MIT AND CC-BY-SA-4.0`. This ADR records the authoritative posture and the remediation action items without modifying source files.

## 2. Context

Forensic evidence from `SPEC.md` §10.1 and Appendix A.2:

| Location | Declares | Evidence |
|---|---|---|
| `LICENSE` | Proprietary (<retired-name>, Inc. → Deloatch, Williams, Faison & Parker, LLLP) | `LICENSE:1-8` (2,268 B) |
| `LICENSE-CODE` | **Identical** proprietary text; advertised in README as MIT | `LICENSE-CODE:1-8` (2,268 B, SHA-identical to `LICENSE`) |
| `LICENSE-CONTENT` | **Identical** proprietary text; advertised in README as CC-BY-SA-4.0 | `LICENSE-CONTENT:1-8` (2,268 B, SHA-identical to `LICENSE`) |
| `pyproject.toml:49-50` | `LicenseRef-Proprietary` | `pyproject.toml:49-50` |
| `pyproject.toml:1-5` | Header comment: *"CONFIDENTIAL AND PROPRIETARY..."* | `pyproject.toml:1-5` |
| Previous `README.md:150-173` | MIT (code) + CC-BY-SA-4.0 (content), with learner-facing marketing | Superseded by the Tier U README rewrite |
| `CONTRIBUTING.md:150-159` | Dual-license pitch to contributors | `CONTRIBUTING.md:150-159` |
| Notebook cell-0 banners | `SPDX-License-Identifier: MIT AND CC-BY-SA-4.0` (e.g. `notebooks/01_fundamentals/D01_income_and_poverty/D01_D01_income_and_poverty.ipynb` cell 0) | `SPEC.md` §10.1 |
| `<tool>.md:35` (internal operating brief) | *"Dual license: MIT for code, CC-BY-SA 4.0 for educational content"* | `<tool>.md:35` |
| `the showcase sub-project/pyproject.toml:19` | `Apache-2.0` | `the showcase sub-project/pyproject.toml:19` |
| `the showcase sub-project/LICENSE` | Proprietary text (contradicts the Apache-2.0 declaration) | `the showcase sub-project/LICENSE:1-10` |

There are **two independent drifts**: (a) the outer repo's three-way mismatch among `LICENSE*` files, `pyproject.toml`, and README/notebook banners; (b) the sub-project's two-way mismatch between `the showcase sub-project/pyproject.toml` (Apache-2.0) and `the showcase sub-project/LICENSE` (proprietary). Neither has ever been adjudicated in a commit.

No CI gate scans for self-contradiction across these sources. `markdown-link-check`, `cspell`, and `markdownlint` all leave license text alone. A learner or third party following `README.md:150-173` would commit derivative works under MIT+CC-BY-SA-4.0 terms that the actual `LICENSE` file disavows.

## 3. Decision

1. **The authoritative license is proprietary.** `LICENSE` + `pyproject.toml:49-50` prevail over any contradicting README marketing, notebook banner, or `<tool>.md` instruction.
2. **`LICENSE-CODE` and `LICENSE-CONTENT` are misleading file names.** Their byte-identical proprietary content means the split-filename convention is cosmetic. Either (a) both files must be replaced with real MIT / CC-BY-SA-4.0 text matching the advertising, or (b) both files must be deleted and the dual-license claim removed from every downstream surface.
3. **The `the showcase sub-project/` Apache-2.0 vs proprietary drift is a parallel gap** and must be resolved in the same remediation PR.
4. **Notebook cell-0 SPDX banners are drift** and must be corrected to `SPDX-License-Identifier: LicenseRef-Proprietary` (or the chosen OSS license if remediation goes the other way). Because notebook content is owned by many contributors, corrections will cross 52 outer + 26 showcase notebooks.
5. **The Tier U README rewrite already removes the MIT/CC-BY-SA-4.0 advertising** and replaces it with a license-posture warning (`README.md` §3). This ADR is the formal record of why.
6. **Remediation is explicitly deferred.** This ADR does NOT modify source notebooks, `LICENSE*` files, `pyproject.toml`, `CONTRIBUTING.md`, or `<tool>.md`. Remediation is captured in `CALIBRATION_REQUIRED.md` under `<OWNER_TBD:license-drift-remediation-owner>`.
7. **A CI gate MUST be added** that fails when the SPDX identifier in any notebook cell-0 does not match `pyproject.toml:49-50`. Tracked at `<OWNER_TBD:license-drift-ci-gate-owner>`.

## 4. Alternatives Considered

### Alternative A — Adopt genuine dual-licensing (replace `LICENSE-CODE` with real MIT text, `LICENSE-CONTENT` with CC-BY-SA-4.0)

**Rejected at this commit because:** the license chain recorded in `LICENSE:1-8` (`<retired-name>, Inc. → Deloatch, Williams, Faison & Parker, LLLP`) is an exclusive commercial arrangement. Relaxing it to MIT requires counterparty consent documented in a separate legal process — outside engineering scope. This alternative remains open as a future ADR (0004+) once legal sign-off exists.

### Alternative B — Delete `LICENSE-CODE` and `LICENSE-CONTENT` and normalize everything to proprietary

**Rejected as the single action now because:** it requires cross-cutting edits to `README.md`, `CONTRIBUTING.md`, `<tool>.md`, and 78 notebook cell-0 banners. The Tier U stack corrects `README.md` only; the rest is tracked in `CALIBRATION_REQUIRED.md` so the remediation can land as one coherent legal-review PR rather than piecemeal.

### Alternative C — Keep the contradictions in place (no ADR)

**Rejected because:** the drift is visible to any viewer of the repository on GitHub and to any reader of a notebook cell-0 banner. Public legal ambiguity cannot stay undocumented once detected.

### Alternative D — Dual-license the outer repo (proprietary) and the sub-project (Apache-2.0) intentionally, treating them as separate products

**Partially accepted.** `the showcase sub-project/` is architecturally distinct (own `pyproject.toml`, own CI, own LICENSE, own build backend — `SPEC.md` §2.2). If legal sign-off approves Apache-2.0 for the showcase alone, the fix is to replace `the showcase sub-project/LICENSE` with actual Apache-2.0 text. The outer repo remains proprietary. This is the recommended remediation shape; still requires legal confirmation.

## 5. Trade-offs Accepted

- **Public-facing ambiguity persists** until remediation. Every day the drift remains, the probability of a third party cloning under the wrong license grows.
- **Notebook contributor trust is undermined.** Contributors following `CONTRIBUTING.md:150-159` ("Code: MIT / Content: CC-BY-SA-4.0") commit under terms that the repository's actual `LICENSE` file disavows. Pending remediation, contributor attribution may be retroactively renegotiated.
- **Three file names (`LICENSE`, `LICENSE-CODE`, `LICENSE-CONTENT`) with identical content** is itself a governance smell — it implies policy that the files do not encode. Until files diverge, the split naming is pure noise.
- **No CI gate today**: `markdownlint`, `cspell`, and `markdown-link-check` do not touch license text. `licensee` is only run in the sub-project (`the showcase sub-project/.github/workflows/ci.yml`), not the outer repo.

## 6. Consequences

- The Tier U `README.md` rewrite removes the MIT+CC-BY-SA-4.0 advertising block and installs a §3 "License Posture (Read Before Contributing)" warning pointing to this ADR.
- `policy/ci-authority.yaml` declares `LICENSE`, `LICENSE-CODE`, `LICENSE-CONTENT`, `pyproject.toml`, and all `notebooks/**/*.ipynb` as `must_never_modify` for CI auto-fix agents — this ADR is the justification.
- Downstream learners reading the notebook SPDX banner will continue to see `MIT AND CC-BY-SA-4.0` until remediation lands. Consumers MUST NOT rely on notebook banners as the source of truth for distribution terms.
- The <tool> `security-reviewer` <tool> (invoked on escalation per CE/<tool> boundary in `Private IP/<tool>.md`) will flag this gap on every PR that touches any `LICENSE*` file or any notebook cell-0.
- `CONTRIBUTING.md:150-159` becomes a document that misrepresents the legal posture until corrected. Accepting contributions in this state requires an explicit contributor acknowledgment; `<OWNER_TBD:legal-and-engineering-lead>` must decide whether to pause merges until remediation.

## 7. Reversal Conditions

This ADR is reversed when **all** of the following are true:

1. `LICENSE-CODE` either contains true MIT License text (and `README.md` §3 is updated to match) or is deleted from the tree.
2. `LICENSE-CONTENT` either contains true CC-BY-SA-4.0 text (and `README.md` §3 is updated to match) or is deleted from the tree.
3. `the showcase sub-project/LICENSE` either contains true Apache-2.0 text or `the showcase sub-project/pyproject.toml:19` is changed to declare proprietary.
4. Every notebook cell-0 in `notebooks/**/*.ipynb` and `the showcase sub-project/notebooks/**/*.ipynb` carries a `SPDX-License-Identifier` that matches the authoritative `LICENSE` file(s) for its tree.
5. `pyproject.toml:49-50` and any source-level `__license__` string agree (the outer repo has no `src/` so no `__license__` exists today; any future `src/` must observe this rule).
6. `CONTRIBUTING.md:150-159` and `<tool>.md:35` (Content Standards → Dual License line) are updated to reflect the final posture.
7. A CI gate exists and passes that asserts SPDX-banner-to-`pyproject.toml` consistency, implemented by `<OWNER_TBD:license-drift-ci-gate-owner>`.

At that point, a follow-up ADR (0004+) records the remediation outcome and this ADR is marked **Superseded**.

---

## 6. Remediation — carried out 2026-09-18

The posture in §3 was confirmed by the owner: **proprietary, copyright Telosyn, Inc.**
The repository stays under the existing `KhipuResearch` GitHub organisation. No open
licence was adopted, so §4 Alternative A remains closed and needs no legal process.

| §3 item | Action |
|---|---|
| 1. Proprietary is authoritative | Unchanged, and now the only statement anywhere outside the evidence files |
| 2. `LICENSE-CODE` / `LICENSE-CONTENT` misleading | **Option (b) taken.** Both deleted. They were byte-identical copies of the proprietary text under filenames advertising MIT and CC-BY-SA-4.0 |
| 3. `the showcase sub-project/` Apache-2.0 drift | **Resolved 2026-09-18** — and this ADR had it backwards; see §7 |
| 4. Notebook cell-0 SPDX banners | Corrected in the **rebuild** (`notebooks_v2/`). **Not** corrected in `notebooks/` — see below |
| 5. README advertising removed | Confirmed; the README now carries the licence-posture table |
| 6. Remediation deferred | No longer deferred |
| 7. CI gate | **Added:** `tests/test_gate_license_consistency.py`, which reads the authoritative identifier from `pyproject.toml` rather than hardcoding it, and fails on any banner that disagrees |

**The live misrepresentation is gone.** `CONTRIBUTING.md` had promised contributors
MIT for code and CC-BY-SA-4.0 for content, linking the two deleted files. Anyone who
relied on it would have granted and received terms the actual licence disavows. That
section now states the proprietary posture and says plainly what it used to say.

**The forensic corpus was deliberately not corrected.** `notebooks/` is audit evidence,
retained byte-identical and verified against `docs/audits/audit_manifest_2026-09-13.jsonl`.
Its cell-0 banners still read `MIT AND CC-BY-SA-4.0`. Editing them would alter evidence to
make the record look tidier, which is the opposite of what the corpus is for. The gate
excludes that tree and carries a test asserting the drift is **still there**, so the
exclusion cannot quietly become a sweep.

**Five documents keep the wrong identifier on purpose** — this ADR, `SPEC.md`,
`CALIBRATION_REQUIRED.md`, `ARCHITECTURE.md` and `README.md` quote it as evidence of the
drift. Rewriting those would erase the record of the problem while claiming to fix it.

**Two banners hid from the first sweep** and were caught by the gate on its first real
run: one in `krl_tutorials_data/reliability.py`, and one mid-sentence in the rebuilt
`D01` notebook's cell 0. The gate's pattern was widened from "identifier at the start of
a line" to "identifier anywhere", which is what found them.

---

## 7. A correction to this ADR's own record

§2's table states:

> `the showcase sub-project/LICENSE` | **Proprietary text** (contradicts the Apache-2.0 declaration)

**That is wrong, and in the opposite direction.** `the showcase sub-project/LICENSE` has held the
full Apache License 2.0 text since the commit that introduced it (`c2802f4`), and has
never contained proprietary text. The contradiction was between that file plus
`pyproject.toml:19` (`Apache-2.0`) on one side, and the `pyproject.toml` **header
comment** four lines above it (*"CONFIDENTIAL AND PROPRIETARY"*) on the other.

The drift was also wider than one file. Apache-2.0 was declared in eight places: the
README badge, a citation block, the README licence section, `pyproject.toml`'s `license`
field, an OSI trove classifier, `docs/about/license.md`, `docs/index.md`, and three
document footers.

**Resolution.** Aligned to the parent repository's posture — proprietary, Telosyn, Inc.
Two facts made that clean rather than a relicensing question:

1. **The Apache declaration was never acted on.** `github.com/<retired-name>/the showcase sub-project`
   returns **404**; the project was never published at the address it advertised, so no
   copy was ever distributed under Apache terms and no irrevocable grant exists.
2. **One copyright holder, no vendored third-party source.** `src/` carries a single
   copyright line and the tree holds no `NOTICE` or `THIRD_PARTY` file.

`mkdocs.yml` also pointed `site_url` and `repo_url` at that non-existent repository;
both now point at `the private source repository`, which is where this work actually lives.

`docs/about/license.md` states the history rather than erasing it, and
`tests/test_gate_license_consistency.py` now covers the sub-project — it had been
excluded from the gate, which is why eight Apache declarations sat unchallenged inside a
repository whose licence forbids redistribution.

**The lesson for this ADR specifically:** a finding recorded from a file listing rather
than from the file's contents can be exactly inverted and still read as authoritative for
months. This one did.
