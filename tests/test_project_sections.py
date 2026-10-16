"""The project generators cope with the expansion's project numbers (09-14).

Written before the change. Projects 09-14 are empty when this lands, so the generators
must not render a README for a folder with no notebook, must not count one as a
project, and must say plainly when a populated folder has no title entry.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[1]


def _load() -> ModuleType:
    """Load."""
    spec = importlib.util.spec_from_file_location(
        "bpr_under_test", REPO / "scripts" / "build_project_readmes.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bpr = _load()

EXPANSION = {
    "09-causal-identification": "Causal Identification",
    "10-economic-evaluation": "Economic Evaluation",
    "11-distribution-heterogeneity": "Distribution and Heterogeneity",
    "12-simulation-foresight": "Simulation and Foresight",
    "13-evidence-synthesis": "Evidence Synthesis",
    "14-implementation": "Implementation and Take-up",
}


def _notebook(path: Path, title: str = "Demo notebook") -> None:
    """Notebook."""
    path.parent.mkdir(parents=True, exist_ok=True)
    cells = [{"cell_type": "markdown", "metadata": {}, "source": [f"# {title}\n"]}]
    path.write_text(json.dumps({"cells": cells, "metadata": {}, "nbformat": 4,
                                "nbformat_minor": 5}), encoding="utf-8")


@pytest.fixture(name="tree")
def _tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway repository root with its own ``projects`` and ``docs``."""
    (tmp_path / "projects").mkdir()
    (tmp_path / "docs").mkdir()
    monkeypatch.setattr(bpr, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(bpr, "PROJECTS", tmp_path / "projects")
    return tmp_path


def test_titles_for_the_expansion_projects_are_exactly_these() -> None:
    """Titles for the expansion projects are exactly these."""
    for name, title in EXPANSION.items():
        assert bpr.SECTION_TITLES[name] == title


def test_every_title_key_is_numbered_and_the_numbers_are_contiguous() -> None:
    """Every title key is numbered and the numbers are contiguous."""
    numbers = []
    for key in bpr.SECTION_TITLES:
        match = re.fullmatch(r"(\d{2})-[a-z]+(?:-[a-z]+)*", key)
        assert match, f"{key!r} is not NN-slug"
        numbers.append(int(match.group(1)))
    assert numbers == list(range(1, 15))


def test_an_empty_project_folder_gets_no_readme_and_is_not_counted(tree: Path) -> None:
    """An empty project folder gets no readme and is not counted."""
    _notebook(tree / "projects" / "01-fundamentals" / "D01_x" / "D01_x.ipynb")
    (tree / "projects" / "09-causal-identification").mkdir()
    assert bpr.main(check=False) == 0
    assert (tree / "projects" / "01-fundamentals" / "README.md").exists()
    assert not (tree / "projects" / "09-causal-identification" / "README.md").exists()
    assert bpr.main(check=True) == 0
    assert "1 notebooks across 1 projects." in (tree / "docs" / "project-index.md").read_text()


def test_a_populated_expansion_project_is_rendered_and_indexed(tree: Path) -> None:
    """A populated expansion project is rendered and indexed."""
    _notebook(tree / "projects" / "09-causal-identification" / "C01_x" / "C01_x.ipynb",
              "Difference-in-differences")
    assert bpr.main(check=False) == 0
    readme = (tree / "projects" / "09-causal-identification" / "README.md").read_text()
    assert "\n# 09. Causal Identification\n" in readme
    index = (tree / "docs" / "project-index.md").read_text()
    assert "[Causal Identification](../projects/09-causal-identification/README.md)" in index
    assert "1 notebooks across 1 projects." in index


def test_a_populated_folder_without_a_title_entry_fails_with_a_message(tree: Path) -> None:
    """A populated folder without a title entry fails with a message."""
    _notebook(tree / "projects" / "15-new-track" / "N01_x" / "N01_x.ipynb")
    with pytest.raises(ValueError, match="SECTION_TITLES"):
        bpr.main(check=False)


def test_check_mode_reports_a_stale_readme(tree: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Check mode reports a stale readme."""
    _notebook(tree / "projects" / "01-fundamentals" / "D01_x" / "D01_x.ipynb")
    bpr.main(check=False)
    (tree / "projects" / "01-fundamentals" / "README.md").write_text("edited", encoding="utf-8")
    assert bpr.main(check=True) == 1
    assert "stale" in capsys.readouterr().out
