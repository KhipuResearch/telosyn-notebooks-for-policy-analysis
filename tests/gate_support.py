"""Shared helpers for the notebook release gates.

Kept out of ``conftest.py`` so that the repository's existing fixture module is
extended rather than replaced. Gates import from here explicitly.

The notebook root is overridable via ``KRL_NOTEBOOK_ROOT`` so the same gates can
be run against the rebuilt corpus or, as a regression check, against the
archived one.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[1]
MAGIC_RE = re.compile(r"^\s*[%!]", re.M)


def notebook_root() -> Path:
    return Path(os.environ.get("KRL_NOTEBOOK_ROOT", str(REPO_ROOT / "projects")))


class Cell(NamedTuple):
    index: int
    kind: str
    source: str
    outputs: list
    execution_count: int | None


class Notebook(NamedTuple):
    path: Path
    metadata: dict
    cells: list[Cell]

    @property
    def krl(self) -> dict[str, Any]:
        """The ``metadata.krl`` block, or ``{}`` when the notebook declares none."""
        block = self.metadata.get("krl")
        return block if isinstance(block, dict) else {}

    @property
    def identification(self) -> dict[str, Any] | None:
        """``krl.identification`` (DECISIONS/0009 section 3.2), or ``None`` if undeclared.

        ``None`` and an empty block are different facts: the identification gate
        treats a notebook that must declare one and declares none as a failure,
        so the accessor does not collapse the two.
        """
        block = self.krl.get("identification")
        return block if isinstance(block, dict) else None

    @property
    def pap(self) -> str | None:
        """The pre-analysis plan path named by ``krl.identification.pap``, or ``None``.

        The path has one home, inside the identification block, so that the plan
        and the contract it belongs to cannot be declared apart.
        """
        block = self.identification
        value = block.get("pap") if block else None
        return value if isinstance(value, str) and value else None

    @property
    def code(self) -> list[Cell]:
        return [c for c in self.cells if c.kind == "code"]

    @property
    def markdown(self) -> list[Cell]:
        return [c for c in self.cells if c.kind == "markdown"]

    @property
    def code_source(self) -> str:
        return "\n".join(c.source for c in self.code)

    @property
    def markdown_source(self) -> str:
        return "\n".join(c.source for c in self.markdown)


def load_notebook(path: Path) -> Notebook:
    raw = json.loads(path.read_text(encoding="utf-8"))
    cells = [
        Cell(
            index=i,
            kind=c.get("cell_type", ""),
            source="".join(c.get("source", [])),
            outputs=c.get("outputs", []) or [],
            execution_count=c.get("execution_count"),
        )
        for i, c in enumerate(raw.get("cells", []))
    ]
    return Notebook(path=path, metadata=raw.get("metadata", {}), cells=cells)


def discover(root: Path | None = None) -> list[Path]:
    root = root or notebook_root()
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.ipynb") if ".ipynb_checkpoints" not in p.parts)


def strip_magics(src: str) -> str:
    """Neutralise IPython magics so ``ast.parse`` sees valid Python."""
    return "\n".join("pass" if MAGIC_RE.match(line) else line for line in src.split("\n"))


def parametrize_notebooks(metafunc) -> None:
    """Attach to ``pytest_generate_tests`` in conftest to feed the gates."""
    if "notebook" in metafunc.fixturenames:
        paths = discover()
        metafunc.parametrize(
            "notebook", [load_notebook(p) for p in paths], ids=[p.stem for p in paths]
        )
