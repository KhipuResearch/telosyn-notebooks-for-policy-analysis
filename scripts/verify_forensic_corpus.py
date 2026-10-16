#!/usr/bin/env python3
"""Verify the archived forensic corpus against the audit manifest.

The rebuild in ``projects/`` is premised on the audited corpus remaining
byte-identical to what the audit recorded. That premise is worth nothing unless
it is checked, and checked in a way that cannot report success by accident.

**Fail-closed.** An earlier ad-hoc version of this check resolved manifest paths
against the wrong tree, fell back to matching notebooks by *basename*, and
reported ten files as modified when none were. A verifier whose miss mode is a
plausible-looking wrong answer is worse than no verifier. This one refuses to
guess: a manifest path that does not resolve is an error, never a search prompt.

**Redacted manifest.** The published manifest names the audited tree as
``<audited-tree>`` and the notebooks that are not in the published corpus by
neutral identifiers. Resolving either needs information that is deliberately
not in this repository: ``KRL_AUDITED_TREE`` points at the tree, and
``KRL_AUDIT_NAMEMAP`` points at a private JSON file mapping each redacted
manifest path to its real path relative to that tree. Without the map, only
unredacted records can be verified and the rest are reported as unresolved.

Usage::

    KRL_AUDITED_TREE=/path/to/tree python scripts/verify_forensic_corpus.py
    KRL_AUDITED_TREE=/path/to/tree KRL_AUDIT_NAMEMAP=/path/to/namemap.json \
        python scripts/verify_forensic_corpus.py

Exit codes: 0 intact; 1 a notebook changed or is missing; 2 the check itself
could not be run (bad manifest, unresolvable root, unresolved records).

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "docs" / "audits" / "audit_manifest_2026-09-13.jsonl"


REDACTED_PREFIX = "<audited-tree>/"
#: Neutral identifiers the published manifest uses for notebooks not in the corpus.
REDACTED_STEM = re.compile(r"^(?:D34(?:_variant_[a-z]|_demo|_spatial)?|ML_\d{2})(?: (?:copy.*|\d+))?\.ipynb$")


def audited_tree() -> Path | None:
    """The directory the manifest's ``<audited-tree>`` stands for. Never guessed."""
    if env := os.environ.get("KRL_AUDITED_TREE"):
        return Path(env).expanduser().resolve()
    return None


def name_map() -> dict[str, str]:
    """Private map from redacted manifest path to real path under the audited tree."""
    if env := os.environ.get("KRL_AUDIT_NAMEMAP"):
        return json.loads(Path(env).expanduser().read_text())
    return {}


def main() -> int:
    if not MANIFEST.exists():
        print(f"ERROR: manifest not found at {MANIFEST}", file=sys.stderr)
        return 2
    records = [json.loads(line) for line in MANIFEST.read_text().splitlines() if line.strip()]
    if not records:
        print("ERROR: manifest is empty.", file=sys.stderr)
        return 2

    root = audited_tree()
    if root is None:
        print("ERROR: set KRL_AUDITED_TREE to the directory the manifest's "
              "<audited-tree> stands for; this verifier does not guess.", file=sys.stderr)
        return 2
    mapping = name_map()
    intact: list[str] = []
    changed: list[str] = []
    missing: list[str] = []
    unresolved: list[str] = []

    for rec in records:
        try:
            rel, expected = rec["path"], rec["artifact_sha256"]
        except KeyError as exc:
            print(f"ERROR: manifest record lacks {exc}; cannot verify.", file=sys.stderr)
            return 2
        if rel in mapping:
            real = mapping[rel]
        elif rel.startswith(REDACTED_PREFIX):
            real = rel[len(REDACTED_PREFIX):]
        else:
            real = rel
        if REDACTED_STEM.match(Path(real).name):
            unresolved.append(rel)  # still a redacted name; needs the private map
            continue
        path = root / real
        if not path.exists():
            missing.append(rel)
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        (intact if digest == expected else changed).append(rel)

    print(f"Manifest records : {len(records)}")
    print(f"Audited tree     : {root}")
    print(f"Intact           : {len(intact)}")
    print(f"Changed          : {len(changed)}")
    print(f"Missing          : {len(missing)}")
    print(f"Unresolved       : {len(unresolved)}  (redacted names with no KRL_AUDIT_NAMEMAP entry)")
    for rel in changed:
        print(f"  CHANGED {rel}")
    for rel in missing:
        print(f"  MISSING {rel}")
    for rel in unresolved:
        print(f"  UNRESOLVED {rel}")

    if missing and not intact:
        print(
            "\nNothing resolved. This is a misconfigured tree, not a corpus "
            "failure: KRL_AUDITED_TREE must be the directory the manifest paths hang off.",
            file=sys.stderr,
        )
        return 2
    if unresolved:
        print("\nSome records could not be resolved; the check is incomplete.", file=sys.stderr)
        return 2
    if changed or missing:
        print("\nThe audited corpus is not byte-identical to the manifest.", file=sys.stderr)
        return 1
    print("\nForensic corpus intact.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
