"""Gate 2 — static. Every code cell must compile.

Catches audit finding F-1: an orphaned ``else:`` left by a generation step made
31 of 33 domain notebooks unparseable. ``ast.parse`` rejects them before any
interpreter state exists, so no environment or key can rescue them.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import ast

from gate_support import Notebook, strip_magics


def test_every_code_cell_compiles(notebook: Notebook) -> None:
    failures = []
    for cell in notebook.code:
        try:
            ast.parse(strip_magics(cell.source))
        except SyntaxError as exc:
            line = (cell.source.split("\n")[(exc.lineno or 1) - 1]).strip()
            failures.append(
                f"cell {cell.index}: {type(exc).__name__}: {exc.msg} "
                f"(line {exc.lineno}) -> {line[:80]!r}"
            )
    assert not failures, f"{notebook.path.name} has uncompilable cells:\n  " + "\n  ".join(failures)


def test_no_code_parked_in_markdown(notebook: Notebook) -> None:
    """Catches F-11: failing code cells demoted to markdown to fake a clean run."""
    suspects = []
    for cell in notebook.markdown:
        src = cell.source
        if src.count("\n") < 3:
            continue
        signals = sum(
            bool(s in src)
            for s in ("import ", "def ", "print(", " = ", "for ", "if ", "return ")
        )
        fenced = "```" in src
        if signals >= 4 and not fenced:
            suspects.append(f"cell {cell.index}: {src.strip()[:70]!r}")
    assert not suspects, (
        f"{notebook.path.name} appears to hold executable code inside markdown cells, "
        f"which silently removes it from execution:\n  " + "\n  ".join(suspects)
    )
