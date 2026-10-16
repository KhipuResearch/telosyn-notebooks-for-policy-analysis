<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# ADR 0003 — Missing `scripts/security/` Scripts and `.secrets.baseline` Referenced by Pre-Commit and Disabled Workflows

- **Status:** Accepted as a Known Gap; remediation pending
- **Deciders:** `<OWNER_TBD:contrib-gate-owner>`
- **Date:** `<OWNER_TBD:adr-0003-decision-date>`

## 1. Title

`.pre-commit-config.yaml` and `build-and-sign.yml.disabled` reference four local artifacts — `scripts/security/add_copyright_headers.py`, `scripts/security/check_trademarks.py`, `scripts/security/inject_watermark.py`, and `.secrets.baseline` — **none of which exist at this commit**. Three pre-commit hooks cannot execute; one disabled workflow is guaranteed to fail if re-enabled. This ADR documents the gap, establishes the immediate contributor-experience impact, and defines the remediation contract.

## 2. Context

Forensic evidence from `SPEC.md` §5.4, §7.1.2, §10.3, §16.2, and Appendix A.1:

### 2.1 Pre-commit hook references (`.pre-commit-config.yaml`)

| Hook id | Entry | File referenced | Present? |
|---|---|---|---|
| `copyright-headers` | `python scripts/security/add_copyright_headers.py` | `scripts/security/add_copyright_headers.py` | **No** |
| `trademark-check` | `python scripts/security/check_trademarks.py` | `scripts/security/check_trademarks.py` | **No** |
| `detect-secrets` | `detect-secrets-hook --baseline .secrets.baseline` | `.secrets.baseline` | **No** |

All three hooks are configured with `stages: [commit]`; the first and second are `always_run: true` and `pass_filenames: false`. A first-time contributor running `pre-commit install && pre-commit run --all-files` will fail **immediately on hook 1** with `No such file or directory: scripts/security/add_copyright_headers.py`.

### 2.2 Disabled-workflow references

| File | Line | Reference | Present? |
|---|---|---|---|
| `build-and-sign.yml.disabled` | 35 (approx.) | `python scripts/security/inject_watermark.py` | **No** |
| `security-checks.yml.disabled` | — | (likely references `check_trademarks.py` / `add_copyright_headers.py`) | **No** |

These files carry the `.disabled` suffix so GitHub Actions does not load them. They exist as historical artifacts of an earlier publish posture. Re-enabling any of them without also shipping the referenced scripts guarantees immediate failure.

### 2.3 Consequent behavior

- `pre-commit run --all-files` **fails** on first attempt for every contributor. Workarounds: (a) skip hooks with `--no-verify` (forbidden by global rules and by §5 trade-offs below), (b) comment out the hooks locally (creates commit-history drift), (c) ship the scripts.
- `detect-secrets-hook --baseline .secrets.baseline` errors because baseline is absent. `detect-secrets` emits `ERROR: baseline not found` and exits non-zero.
- The `the showcase sub-project/` sub-project is unaffected — its CI uses `reviewdog/action-detect-secrets@v0.15.0` + `gitleaks/gitleaks-action@v2` rather than the local `detect-secrets-hook`, and does not invoke the outer `scripts/security/` scripts (`SPEC.md` §7.2).

### 2.4 What the missing scripts are supposed to do

Inferred from hook id and entry line:

| Script | Inferred purpose | Downstream effect of absence |
|---|---|---|
| `add_copyright_headers.py` | Inject `© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.` header into Python / Markdown / YAML files missing one | New files can land without copyright headers; manual review catches most but not all |
| `check_trademarks.py` | Verify `README.md` contains the then-current trademark line (a retired mark and a retired owner name) | `README.md` could drift out of trademark compliance without detection |
| `inject_watermark.py` | Stamp a release watermark into distributed artifacts before signing | Disabled pipeline would publish unwatermarked artifacts if ever re-enabled |
| `.secrets.baseline` | Known-non-secret fingerprints to suppress false positives in `detect-secrets` | Every `detect-secrets` run treats the baseline as empty; false-positive-heavy output or outright hook failure |

## 3. Decision

1. **The three pre-commit hooks referencing missing scripts are broken and MUST be fixed in one of three ways:**
   - **3a. Ship the scripts.** Create `scripts/security/{add_copyright_headers,check_trademarks,inject_watermark}.py` with the inferred behavior above, plus corresponding unit tests, in a single PR. This is the preferred remediation.
   - **3b. Remove the hooks.** If the enforcement goals are no longer in scope, delete the `copyright-headers` and `trademark-check` hook blocks from `.pre-commit-config.yaml:20-42`. This is the fast-path remediation if engineering resources are unavailable.
   - **3c. Hybrid.** Ship `add_copyright_headers.py` and `check_trademarks.py` (both trivial, both enforce existing policy visible in `pyproject.toml:1-5` and `README.md:197`), and remove the `inject_watermark.py` reference from the disabled workflow. The `build-and-sign.yml.disabled` file is already disabled; its contents are moot until re-enabled.
2. **`.secrets.baseline` MUST be created in the same remediation PR** via `detect-secrets scan > .secrets.baseline` executed in a clean checkout. Without this, hook 3 will continue to fail.
3. **Until remediation lands, `.pre-commit-config.yaml` carries a KNOWN-BROKEN status.** The Tier U `tests/README.md` and `.github/workflows/README.md` both reference this ADR so contributors understand why pre-commit fails on fresh clone.
4. **`policy/ci-authority.yaml` marks `.pre-commit-config.yaml` as `may_modify` only via 2-approver PR** — autonomous fixing of broken hooks is forbidden because the "fix" could silently delete the hooks entirely, masking the underlying gap.
5. **No hook MUST be bypassed with `--no-verify`** — the global rule forbids `--no-verify` across all KRL repos (per the repository-group review policy). Contributors blocked by this gap must either apply one of §3.1 remediations or surface the block to `<OWNER_TBD:contrib-gate-owner>`.

## 4. Alternatives Considered

### Alternative A — Keep the broken hooks "to preserve policy intent"

**Rejected because:** a broken hook is worse than a missing hook. It forces `--no-verify` into the contributor's muscle memory or blocks every first-time contributor. Intent without enforcement is technical debt, not policy.

### Alternative B — Silently disable the hooks in `.pre-commit-config.yaml` by commenting out without ADR

**Rejected because:** undocumented removal of enforcement obscures the original policy (copyright headers, trademark notice, secret detection) from future maintainers. Every removal of a security-adjacent hook MUST have an ADR justifying it.

### Alternative C — Depend on the sub-project's CI to catch secrets instead of the outer pre-commit

**Rejected because:** the sub-project's CI runs *after* push. Pre-commit is the only mechanism preventing secrets from reaching the repository history. The outer `.gitleaks.toml` is the main-branch gate; the pre-commit `detect-secrets` hook is the local gate. Both are needed.

### Alternative D — Consolidate the outer scripts with similar scripts in sibling KRL repos

**Partially accepted as a follow-up.** `krl-open-core`, `krl-data-connectors`, `krl-model-zoo`, and `krl-dashboard` have analogous `scripts/security/*.py` patterns (or gaps). A cross-repo shared-script package would eliminate duplication but is out of scope for this ADR. Recommend tracking under the repository-group shared-tooling consolidation work.

## 5. Trade-offs Accepted

- **Until remediation, `pre-commit install && pre-commit run --all-files` fails immediately.** This is a direct cost on every first-time contributor. The block is visible and attributable; contributors are not silently affected.
- **The `.secrets.baseline` absence means `detect-secrets` operates without a suppressed-finding set.** If the baseline is eventually shipped via `detect-secrets scan > .secrets.baseline`, historical findings in already-committed files will be auto-suppressed — a consequence acceptable *only* if the baseline is reviewed by a human before commit.
- **`inject_watermark.py` remains referenced by a disabled workflow.** Since the workflow is `.disabled`, no CI runs fail; the reference is a dormant land-mine for anyone re-enabling the workflow without reading this ADR.
- **Inferred purpose in §2.4 may diverge from the original author's intent.** The remediation PR should check git history (`git log --all --diff-filter=D -- scripts/security/`) to recover the original files if they were deleted rather than never committed.

## 6. Consequences

- Tier U `tests/README.md` §4 documents this gap as "Known Gaps → Missing pre-commit scripts" and links here.
- Tier U `.github/workflows/README.md` references this ADR in its "Known CI Gaps" section for the disabled-workflow side of the gap.
- `policy/ci-authority.yaml` declares `.pre-commit-config.yaml` as a change surface requiring human approval per §3.4.
- New contributors are directed to `CONTRIBUTING.md` + `tests/README.md` before running pre-commit; both now warn that the hooks fail until this ADR is closed.
- `CODE_OF_CONDUCT.md`, `SECURITY.md`, and `CONTRIBUTING.md` are preserved unmodified — the gap does not affect behavioral standards.

## 7. Reversal Conditions

This ADR is reversed when **all** of the following are true:

1. `scripts/security/add_copyright_headers.py` exists and passes a unit test covering at least `.py`, `.md`, and `.yml` file types.
2. `scripts/security/check_trademarks.py` exists and passes a unit test against the `README.md` trademark line (currently at `README.md:197` pre-rewrite; post-rewrite the trademark notice is part of the footer region or may be relocated — the script must be robust to either location).
3. **Either** `scripts/security/inject_watermark.py` exists and the corresponding step in `build-and-sign.yml.disabled:34-39` is updated, **or** that step is removed from the disabled workflow.
4. `.secrets.baseline` is committed, generated from `detect-secrets scan` in a clean checkout, and human-reviewed.
5. `pre-commit run --all-files` on a fresh clone passes without any `--no-verify` usage.
6. The gap-notice paragraphs in `tests/README.md` §4 and `.github/workflows/README.md` are removed in the same PR.
7. A follow-up ADR (0004+) records the remediation outcome and this ADR is marked **Superseded**.
