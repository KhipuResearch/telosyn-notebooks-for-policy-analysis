<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# ADR 0006 — Git History Rewritten to Remove a Vendored SDK Tarball

- **Status:** Accepted, executed
- **Deciders:** Telosyn, Inc. (owner)
- **Date:** 2026-09-18

## 1. Title

The published history of the private source repository was rewritten across every ref to remove a
55 MB vendored Google Cloud SDK tarball that had never been part of the corpus and
accounted for 62% of the repository's packed size. All commit, tag and branch SHAs
below the rewrite point changed. Tracked content is unchanged.

## 2. Context

`ADR 0005` establishes that this repository is intended to be publicly visible for
marketing, showcase and transparency. A repository whose purpose is to be *looked
at* pays a cost for every megabyte a reader must download before they can look.

The repository cloned at roughly 98 MB. One object accounted for most of it:

| | |
|---|---|
| Blob | `525c8311fd2afbc67518facfb0fad1f132a7bc74` |
| Size | 57,803,372 bytes (55.1 MiB) uncompressed; ~54.9 MB packed |
| Share of pack | 62% of 88.89 MiB |
| Next largest object | 2.9 MB |

It was `google-cloud-cli-darwin-arm.tar.gz` — a macOS Google Cloud SDK installer,
committed during D34 development, at three paths:

```
notebooks/10_advanced_nlp/D34/google-cloud-cli-darwin-arm.tar.gz
notebooks/10_advanced_nlp/D34/google-cloud-cli-darwin-arm 2.tar.gz
notebooks/10_advanced_nlp/D34/lean_validation/google-cloud-cli-darwin-arm.tar.gz
```

Commit `3cd6880` ("Prune: drop 163 MB of tracked vendor binary and root scratch")
removed it from the tree in 2026. Removing a file from a tree does not remove it
from history: it remained reachable from three commits and from fifteen of the
repository's twenty-two refs, and every clone still downloaded it.

Deleting a file from the tip is not deletion. Only a rewrite is.

## 3. Decision

Rewrite the history across **all** refs — branches and tags — stripping the blob,
and force-push the result. Accept that every SHA below the rewrite point changes
and that any existing clone must be re-cloned rather than pulled.

The alternative — leaving it — was rejected because the cost is paid by every
future reader of a repository whose stated purpose is to be read, and because the
cost of rewriting rises monotonically with every commit added after this one.

## 4. Method

`git-filter-repo` 2.47.0.

**The first attempt was wrong and is recorded because the failure mode is silent.**
The pass was scoped by path glob, derived from:

```
git rev-list --objects --all | grep <blob-sha>
```

That command prints an object **once**, under whichever path it is first
encountered at. It reported one path. The blob had three. The path-scoped pass
removed one name and left the blob fully reachable under the other two — and the
repack still reported a plausible-looking size, because 89.54 MiB is not obviously
wrong if you are not checking the object itself.

The correct enumeration is `git log --all --raw --no-abbrev`, which shows every
add and delete of a blob with its path. The rewrite was then re-run scoped by
**blob id**, which is path-independent and cannot miss a name:

```
git filter-repo --force --strip-blobs-with-ids <file-containing-blob-sha>
```

**Verify by the object, not by the path, and not by the size.**

## 5. Verification

A full-ref backup bundle was taken first (`git bundle create --all`;
`git bundle verify` → "The bundle records a complete history") and the rewritten
repository was checked against it independently:

| Check | Result |
|---|---|
| Blob `525c8311…` | object does not exist; `git cat-file` fails |
| `main` tip tree | `87000e7f6b645b1fec967e2968dc14963f7dda34` — **byte-identical**; `main` was already clean |
| Other 15 changed refs | tip-tree diff contains **only** `D` entries for the three tarball paths; zero other changes |
| Commits | 185 → 185 |
| Refs | 22 → 22 (9 branches, 13 tags); none lost, none added |
| `git fsck` | clean |
| Gate and provenance suites | 888 passed |
| Full suite | 1,739 passed, 1 skipped; 2 failures and 3 errors, all `ModuleNotFoundError` for packages absent from that host (`networkx`, `krl_data_connectors`, `krl_policy`) |
| Packed size | 88.89 MiB → **34.63 MiB** |
| Push | 3,231 objects, 34.54 MiB total |

`main`: `ddb1bfa` → `8039190`.

Tree-SHA equality is the load-bearing check. It proves every tracked byte survived;
no test run can establish more than that, and a test run that failed for want of a
third-party package establishes nothing about the rewrite.

## 6. A second failure, recorded

The force-push was performed with `git push --force --mirror`, on the stated
premise that the remote held exactly what the local repository held. That premise
was checked against `refs/remotes/origin/*`.

**Remote-tracking refs are not the remote.** They are a snapshot from the last
fetch. The real remote had moved: Dependabot had superseded three branches and
opened two more. The mirror push therefore deleted five remote branches that were
not represented locally, and recreated three obsolete ones plus two that had been
deleted after merge.

Nothing authored by a person was lost — every deleted branch was machine-generated
and regenerable — but the safety argument was unsound as given. `--mirror` is
correct for this operation, because a partial push leaves the blob reachable from
an un-rewritten branch and the remote never shrinks. The precondition is
`git fetch --prune` **immediately before**, not a tracking ref of unknown age.

The five resurrected branches were subsequently deleted; the five Dependabot
branches are regenerated on the next run.

## 7. Consequences

1. **Existing clones cannot be reconciled by `git pull`.** Re-clone.
2. **Commit SHAs in prior references are stale.** Links, notes, PR bodies and audit
   documents citing a pre-rewrite SHA no longer resolve. Tag *names* are preserved;
   only their targets moved.
3. **The forensic corpus is unaffected.** It lives outside this repository, under
   `KRL/backups/`, and is verified against
   `docs/audits/audit_manifest_2026-09-13.jsonl` by
   `scripts/verify_forensic_corpus.py`.
4. **The class is already guarded.** `.gitignore` lines 116-122 refuse `*.tar.gz`,
   `*.tgz` and `*.zip` outright, added alongside the `3cd6880` prune. That guard
   stops the next one from entering; it could do nothing about the one already in
   history, which is what required this rewrite. Note the arithmetic difference
   between the two records: the ignore comment counts *168 MB of vendor binary*,
   which is what three 56 MB files occupy in a checkout, while this ADR counts one
   55 MB object, which is what git stores. Both are correct about different things.
5. **A clone is now ~35 MB**, which is the point: a public showcase that costs
   98 MB to look at is not a showcase.
