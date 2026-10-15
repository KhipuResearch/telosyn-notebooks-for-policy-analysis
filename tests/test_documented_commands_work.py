# © 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
# SPDX-License-Identifier: LicenseRef-Proprietary
"""The commands the README gives a reader must actually run.

`pytest.ini` puts `--cov` in `addopts`, so every pytest invocation needs
`pytest-cov` present -- and `addopts` is read before command-line `-o`, which
means a reader cannot work around a missing plugin with `-o addopts=""`. The
README told readers to install `.[dev]`; neither `[dev]` nor `[test]` shipped
`pytest-cov`, so the documented install produced a suite that failed at start-up
with "unrecognized arguments: --cov" before collecting a single test.

A README is a claim about the software like any other. This checks the claim.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parent.parent


def _extras() -> dict[str, list[str]]:
    """Parse `[project.optional-dependencies]` without tomllib.

    `tomllib` is 3.11+, and this check should run on whatever interpreter a
    reader has, including the one whose install it is validating.
    """
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r"^\[project\.optional-dependencies\]\n(.*?)(?=^\[)", text,
                  re.S | re.M)
    assert m, "pyproject.toml has no [project.optional-dependencies] section"
    out: dict[str, list[str]] = {}
    for name, body in re.findall(r"^(\w[\w-]*)\s*=\s*\[(.*?)^\]", m.group(1),
                                 re.S | re.M):
        out[name] = re.findall(r'"([^"]+)"', body)
    return out


def _readme_install_extras() -> list[str]:
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(r"pip install -e '?\.\[([a-z,]+)\]'?", text)
    assert m, "README no longer documents an editable install with an extra"
    return m.group(1).split(",")


def test_every_extra_the_readme_names_exists() -> None:
    for extra in _readme_install_extras():
        assert extra in _extras(), (
            f"README tells readers to install '.[{extra}]', which pyproject.toml "
            f"does not define. Available: {sorted(_extras())}"
        )


def test_that_extra_supplies_every_plugin_pytest_ini_requires() -> None:
    """Whatever `addopts` demands has to be installable by the documented command."""
    addopts = (REPO_ROOT / "pytest.ini").read_text(encoding="utf-8")
    required = {"--cov": "pytest-cov"}
    named = " ".join(d for e in _readme_install_extras() for d in _extras()[e]).lower()
    for flag, dist in required.items():
        if flag in addopts:
            assert dist in named, (
                f"pytest.ini's addopts use {flag}, which needs {dist}, but the "
                f"extra the README names does not provide it. The documented "
                f"install produces a suite that cannot start."
            )


def test_pytest_ini_flags_cannot_be_waived_from_the_command_line() -> None:
    """Why the check above matters rather than being a nicety.

    `addopts` is consumed during early config, before `-o` is parsed, so
    `pytest -o addopts=""` does not clear it. A reader who lacks the plugin has
    no command-line escape; the dependency has to be declared.
    """
    assert "addopts" in (REPO_ROOT / "pytest.ini").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Declared dependencies must be real dependencies.
#
# Until 2026-10-15 `dependencies` named four private KRL distributions --
# krl-open-core, krl-data-connectors, krl-model-zoo, krl-dashboard -- three of
# which were imported by nothing in the repository and the fourth only through a
# code path no notebook calls. `pip install -e .` therefore failed for anyone
# without access to a private index, before a single notebook could open. The
# suite passed locally only because the repository root was on sys.path.
#
# At the same time four packages the code does import -- scipy, requests,
# statsmodels, scikit-learn -- were not runtime dependencies at all.
# --------------------------------------------------------------------------- #

import json
import subprocess

#: Distribution name -> import name, where they differ.
_IMPORT_NAME = {"scikit-learn": "sklearn", "krl-data-connectors": "krl_data_connectors"}

#: Extras whose members are tools rather than imports (a kernel, a test runner).
_TOOL_EXTRAS = {"test", "dev"}
_TOOLS = {"jupyterlab", "notebook"}


def _runtime_deps() -> list[str]:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r"^dependencies\s*=\s*\[(.*?)^\]", text, re.S | re.M)
    assert m, "pyproject.toml has no dependencies list"
    return [d.split("[")[0] for d in re.findall(r'"([A-Za-z0-9_.-]+)', m.group(1))]


def _imported_modules() -> set[str]:
    """Top-level modules imported anywhere in the package, scripts, tests or corpus."""
    files = subprocess.check_output(["git", "ls-files", "*.py", "*.ipynb"],
                                    cwd=REPO_ROOT, text=True).split("\n")
    found: set[str] = set()
    pat = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][\w]*)", re.M)
    for f in files:
        if not f:
            continue
        path = REPO_ROOT / f
        if f.endswith(".ipynb"):
            cells = json.loads(path.read_text(encoding="utf-8")).get("cells", [])
            src = "\n".join("".join(c.get("source", [])) for c in cells
                            if c.get("cell_type") == "code")
        else:
            src = path.read_text(encoding="utf-8")
        found.update(pat.findall(src))
        # a string passed to importlib.import_module counts as an import
        found.update(re.findall(r'import_module\(\s*"([A-Za-z_][\w]*)', src))
        found.update(re.findall(r'^[A-Z_]+\s*=\s*"([a-z_][\w]*)"\s*$', src, re.M))
    return found


def test_every_runtime_dependency_is_actually_imported() -> None:
    """A dependency nothing imports is a reason the install fails, and no more."""
    imported = _imported_modules()
    # Engines pandas loads lazily are declared without being imported by name;
    # test_lazy_engine_dependencies_are_declared is the check that owns them.
    lazy_engines = {"openpyxl", "pyarrow"}
    phantom = [d for d in _runtime_deps()
               if d not in lazy_engines
               and _IMPORT_NAME.get(d, d.replace("-", "_")) not in imported]
    assert not phantom, (
        f"pyproject.toml declares runtime dependencies nothing imports: {phantom}. "
        "Each one is a package every reader must be able to install before a "
        "single notebook opens. Remove it or move it to an optional extra."
    )


def test_every_import_the_package_makes_is_a_runtime_dependency() -> None:
    """The mirror image: the package must not import what it does not declare."""
    # ast, not regex: a docstring sentence beginning "from every source" is
    # prose, and a regex reports it as an import of a module named `every`.
    pkg_imports: set[str] = set()
    for f in (REPO_ROOT / "src" / "krl_tutorials_data").glob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                pkg_imports.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                pkg_imports.add(node.module.split(".")[0])
    stdlib = set(sys.stdlib_module_names) | {"krl_tutorials_data"}
    third_party = {m for m in pkg_imports if m not in stdlib}
    declared = {_IMPORT_NAME.get(d, d.replace("-", "_")) for d in _runtime_deps()}
    missing = sorted(third_party - declared)
    assert not missing, (
        f"krl_tutorials_data imports {missing} but pyproject.toml does not declare "
        "them as runtime dependencies, so `pip install -e .` yields ImportError."
    )


def test_the_notebooks_extra_covers_what_the_notebooks_import() -> None:
    """A reader who installs `.[notebooks]` must be able to execute every notebook."""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r"^notebooks\s*=\s*\[(.*?)^\]", text, re.S | re.M)
    assert m, "pyproject.toml has no [notebooks] extra"
    extra = {_IMPORT_NAME.get(d, d.replace("-", "_"))
             for d in re.findall(r'"([A-Za-z0-9_.-]+)', m.group(1))}
    runtime = {_IMPORT_NAME.get(d, d.replace("-", "_")) for d in _runtime_deps()}
    pat = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][\w]*)", re.M)
    stdlib = set(sys.stdlib_module_names) | {"krl_tutorials_data"}
    needed: set[str] = set()
    for nb in (REPO_ROOT / "projects").rglob("*.ipynb"):
        cells = json.loads(nb.read_text(encoding="utf-8")).get("cells", [])
        src = "\n".join("".join(c.get("source", [])) for c in cells if c.get("cell_type") == "code")
        needed.update(m for m in pat.findall(src) if m not in stdlib)
    uncovered = sorted(needed - runtime - extra)
    assert not uncovered, (
        f"notebooks import {uncovered}, which neither the runtime dependencies nor "
        "the [notebooks] extra provide."
    )


def test_env_example_names_exactly_the_keys_the_client_accepts() -> None:
    """The template a reader copies must match ALLOWED_KEYS, name for name.

    It once listed CDC_API_KEY, which the client never reads, and omitted
    HUD_API_KEY and DATA_GOV_API_KEY, which it requires -- so a reader who
    filled it in faithfully got two silent failures and one ignored line.
    """
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from krl_tutorials_data.sources import ALLOWED_KEYS  # noqa: E402

    text = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    named = set(re.findall(r"^([A-Z_]+)=", text, re.M))
    assert named == set(ALLOWED_KEYS), (
        f"missing from .env.example: {sorted(set(ALLOWED_KEYS) - named)}; "
        f"present but never read: {sorted(named - set(ALLOWED_KEYS))}"
    )
    assert not re.search(r"^[A-Z_]+=\S", text, re.M), ".env.example must carry no values"


def test_lazy_engine_dependencies_are_declared() -> None:
    """Some runtime needs never appear as an import statement.

    `pandas.read_excel` loads its engine lazily, so a module that reads a
    workbook depends on openpyxl without ever naming it. The declared-imports
    test above cannot see that, and CI run #2 on a clean runner found it the
    hard way: four food-atlas tests failing with ModuleNotFoundError.
    """
    lazy = {"read_excel": "openpyxl", "read_parquet": "pyarrow", "to_parquet": "pyarrow"}
    used: set[str] = set()
    for f in (REPO_ROOT / "src" / "krl_tutorials_data").glob("*.py"):
        src = f.read_text(encoding="utf-8")
        used.update(dist for call, dist in lazy.items() if f".{call}(" in src)
    declared = {d.replace("-", "_") for d in _runtime_deps()}
    missing = sorted(d for d in used if d not in declared)
    assert not missing, (
        f"the package calls pandas I/O that needs {missing} at runtime, but "
        "pyproject.toml does not declare it; a clean install will fail at the call."
    )
