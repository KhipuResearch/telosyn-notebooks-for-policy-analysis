"""Gate 2 — secrets and portability.

Catches F-14 (live API-key prefixes committed in stored outputs) and the 282
hardcoded ``/Users/...`` paths that make the corpus unrunnable elsewhere.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import re

from gate_support import Notebook

KEY_NAME = re.compile(r"(?:API_KEY|TOKEN|SECRET|PASSWORD)", re.I)
KEYISH_VALUE = re.compile(r"\b[A-Za-z0-9_\-]{16,}\b")
ABSOLUTE_HOME = re.compile(r"(?:/Users/|/home/(?!runner)|C:\\\\Users\\\\)[A-Za-z0-9._\-]+")
LICENSE_BYPASS = re.compile(r"skip_license_check|SKIP_LICENSE_VALIDATION", re.I)


def _output_text(cell) -> str:
    parts = []
    for o in cell.outputs:
        if o.get("output_type") == "stream":
            parts.append("".join(o.get("text", [])))
        elif "data" in o:
            parts.append(str(o["data"].get("text/plain", "")))
        elif o.get("output_type") == "error":
            parts.append("\n".join(o.get("traceback", [])))
    return "\n".join(parts)


def test_no_key_material_in_outputs(notebook: Notebook) -> None:
    hits = []
    for cell in notebook.code:
        text = _output_text(cell)
        for line in text.split("\n"):
            if KEY_NAME.search(line) and KEYISH_VALUE.search(line):
                hits.append(f"cell {cell.index}: {line.strip()[:80]!r}")
    assert not hits, (
        f"{notebook.path.name} has credential-shaped material in a stored output "
        f"(F-14). Strip outputs before commit:\n  " + "\n  ".join(hits)
    )


def test_no_absolute_developer_paths(notebook: Notebook) -> None:
    hits = []
    for cell in notebook.cells:
        for m in ABSOLUTE_HOME.finditer(cell.source):
            hits.append(f"cell {cell.index}: {m.group(0)}")
        for m in ABSOLUTE_HOME.finditer(_output_text(cell) if cell.kind == "code" else ""):
            hits.append(f"cell {cell.index} (output): {m.group(0)}")
    assert not hits, (
        f"{notebook.path.name} hardcodes a developer home path, so it cannot run on "
        f"another machine:\n  " + "\n  ".join(sorted(set(hits)))
    )


def test_no_license_bypass(notebook: Notebook) -> None:
    hits = [f"cell {c.index}" for c in notebook.code if LICENSE_BYPASS.search(c.source)]
    assert not hits, (
        f"{notebook.path.name} disables a licence control: {', '.join(hits)}"
    )
