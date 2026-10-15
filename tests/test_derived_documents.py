# © 2026 Telosyn, Inc. All rights reserved.
# SPDX-License-Identifier: LicenseRef-Proprietary
"""The generated documents must match what the generators would write now.

Project READMEs, the project index and data/README.md are derived from the
notebooks and their provenance records by scripts in `scripts/`. A derived
document that has drifted from its source describes a repository other than
this one, which is the defect the whole corpus exists to refuse.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("script", ["scripts/build_project_readmes.py", "scripts/build_data_readme.py"])
def test_generated_documents_are_current(script: str) -> None:
    r = subprocess.run([sys.executable, script, "--check"], cwd=REPO_ROOT, capture_output=True, text=True)
    assert r.returncode == 0, f"{script} --check reports drift:\n{r.stdout}{r.stderr}"


def test_every_provenance_record_matches_the_published_schema() -> None:
    """data/schemas/provenance_record.json is a claim about the records; check it."""
    schema = json.loads((REPO_ROOT / "data/schemas/provenance_record.json").read_text(encoding="utf-8"))
    fields = {f["name"]: f for f in schema["fields"]}
    required = {n for n, f in fields.items() if f.get("constraints", {}).get("required")}
    problems: list[str] = []
    for p in sorted(REPO_ROOT.glob("projects/*/*/provenance/*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        for r in (d if isinstance(d, list) else [d]):
            if not isinstance(r, dict):
                continue
            rel = p.relative_to(REPO_ROOT)
            missing = required - set(r)
            if missing:
                problems.append(f"{rel}: missing {sorted(missing)}")
            unknown = set(r) - set(fields)
            if unknown:
                problems.append(f"{rel}: fields not in schema {sorted(unknown)}")
            for name, f in fields.items():
                enum = f.get("constraints", {}).get("enum")
                if enum and name in r and r[name] not in enum:
                    problems.append(f"{rel}: {name}={r[name]!r} not in {enum}")
    assert not problems, "\n".join(problems)
