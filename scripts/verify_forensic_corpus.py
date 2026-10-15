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

Usage::

    python scripts/verify_forensic_corpus.py            # exit 0 if intact
    KRL_ROOT=/path/to/KRL python scripts/verify_forensic_corpus.py

Exit codes: 0 intact; 1 a notebook changed or is missing; 2 the check itself
could not be run (bad manifest, unresolvable root).

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "docs" / "audits" / "audit_manifest_2026-09-13.jsonl"


def krl_root() -> Path:
    """The directory the manifest's relative paths hang off.

    Defaults to the grandparent of this repository (``KRL/<private-folder>/the private source repository``
    -> ``KRL``). Override with ``KRL_ROOT`` when the tree is mounted elsewhere.
    """
    if (env := os.environ.get("KRL_ROOT")):
        return Path(env).expanduser().resolve()
    return REPO_ROOT.parents[1]


def main() -> int:
    if not MANIFEST.exists():
        print(f"ERROR: manifest not found at {MANIFEST}", file=sys.stderr)
        return 2
    records = [json.loads(line) for line in MANIFEST.read_text().splitlines() if line.strip()]
    if not records:
        print("ERROR: manifest is empty.", file=sys.stderr)
        return 2

    root = krl_root()
    intact: list[str] = []
    changed: list[str] = []
    missing: list[str] = []

    for rec in records:
        try:
            rel, expected = rec["path"], rec["artifact_sha256"]
        except KeyError as exc:
            print(f"ERROR: manifest record lacks {exc}; cannot verify.", file=sys.stderr)
            return 2
        path = root / rel
        if not path.exists():
            missing.append(rel)
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        (intact if digest == expected else changed).append(rel)

    print(f"Manifest records : {len(records)}")
    print(f"Root             : {root}")
    print(f"Intact           : {len(intact)}")
    print(f"Changed          : {len(changed)}")
    print(f"Missing          : {len(missing)}")
    for rel in changed:
        print(f"  CHANGED {rel}")
    for rel in missing:
        print(f"  MISSING {rel}")

    if missing and not intact:
        print(
            "\nNothing resolved. This is a misconfigured root, not a corpus "
            "failure: set KRL_ROOT to the directory the manifest paths hang off.",
            file=sys.stderr,
        )
        return 2
    if changed or missing:
        print("\nThe audited corpus is not byte-identical to the manifest.", file=sys.stderr)
        return 1
    print("\nForensic corpus intact.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
