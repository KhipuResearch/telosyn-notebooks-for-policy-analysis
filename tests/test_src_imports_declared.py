"""Nothing is imported that is not declared; nothing is declared that is not imported.

DECISIONS/0009 section 3.6. ``test_ci_dependencies`` already checks that what the
*tests and notebooks* import can be installed by CI. This checks the package
itself: every third-party import in ``src/krl_tutorials_data`` is a declared
runtime dependency, every declared runtime dependency is imported (or has a stated
reason it cannot be seen), and the optional ``methods`` extra declares nothing that
no test or notebook imports.

The helpers are exercised on synthetic input so the check is shown able to fail.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import ast
import json
import re
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "krl_tutorials_data"

#: Distribution name -> import name, where they differ.
ALIASES = {"scikit-learn": "sklearn", "pyyaml": "yaml", "pytest-cov": "pytest_cov"}

#: Runtime dependencies that no import statement in ``src`` can show, with the reason.
NOT_VISIBLE = {
    "openpyxl": "pandas.read_excel loads it lazily and never imports it by name",
}


def _pyproject() -> dict:
    """Pyproject."""
    return tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))


def _name(requirement: str) -> str:
    """Name."""
    return re.split(r"[<>=!\[;\s]", requirement, maxsplit=1)[0].strip().lower()


def module_of(distribution: str) -> str:
    """Import name of a distribution."""
    return ALIASES.get(distribution, distribution.replace("-", "_"))


def third_party_imports(source: str) -> dict[str, bool]:
    """``{module: imported_at_module_level}`` for non-stdlib, non-package imports."""
    tree = ast.parse(source)
    top = {id(n) for n in tree.body}
    found: dict[str, bool] = {}
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module.split(".")[0]]
        for name in names:
            if name in sys.stdlib_module_names or name == "krl_tutorials_data":
                continue
            found[name] = found.get(name, False) or id(node) in top
    return found


def undeclared(imports: set[str], declared: set[str]) -> set[str]:
    """Imports with no declaration."""
    return imports - declared


def declared_but_unused(declared: set[str], imports: set[str], not_visible: set[str]) -> set[str]:
    """Declarations nothing imports and nothing excuses."""
    return declared - imports - not_visible


def _src_imports() -> dict[str, bool]:
    """Src imports."""
    merged: dict[str, bool] = {}
    for path in sorted(SRC.rglob("*.py")):
        for name, top in third_party_imports(path.read_text(encoding="utf-8")).items():
            merged[name] = merged.get(name, False) or top
    return merged


def test_every_third_party_import_in_src_is_a_declared_runtime_dependency() -> None:
    """Every third party import in src is a declared runtime dependency."""
    runtime = {module_of(_name(r)) for r in _pyproject()["project"]["dependencies"]}
    missing = undeclared(set(_src_imports()), runtime)
    assert not missing, (
        f"src/krl_tutorials_data imports {sorted(missing)} but pyproject.toml does not declare "
        "them as runtime dependencies (DECISIONS/0009 section 3.6)"
    )


def test_every_declared_runtime_dependency_is_imported_or_excused() -> None:
    """Every declared runtime dependency is imported or excused."""
    runtime = {module_of(_name(r)) for r in _pyproject()["project"]["dependencies"]}
    unused = declared_but_unused(runtime, set(_src_imports()), set(NOT_VISIBLE))
    assert not unused, f"declared but imported nowhere in src/: {sorted(unused)}"
    for name in NOT_VISIBLE:
        assert name in runtime, f"{name} is excused but no longer declared; drop the excuse"


def test_the_connector_extra_is_reached_only_by_name_at_runtime() -> None:
    """The connector extra is reached only by name at runtime."""
    extras = _pyproject()["project"]["optional-dependencies"]
    assert [_name(r) for r in extras["connectors"]] == ["krl-data-connectors"]
    assert "import_module(" in (SRC / "connectors.py").read_text(encoding="utf-8")


def _test_and_notebook_imports() -> set[str]:
    """And notebook imports."""
    seen: set[str] = set()
    for path in sorted((REPO / "tests").rglob("test_*.py")):
        seen |= set(third_party_imports(path.read_text(encoding="utf-8")))
    for path in sorted((REPO / "projects").rglob("*.ipynb")):
        cells = json.loads(path.read_text(encoding="utf-8")).get("cells", [])
        code = "\n".join(
            "".join(c.get("source", [])) for c in cells if c.get("cell_type") == "code"
        )
        code = "\n".join(
            line for line in code.splitlines() if not line.lstrip().startswith(("%", "!"))
        )
        try:
            seen |= set(third_party_imports(code))
        except SyntaxError:
            continue
    return seen


def test_the_methods_extra_declares_only_what_something_imports() -> None:
    """The methods extra declares only what something imports."""
    methods = _pyproject()["project"]["optional-dependencies"].get("methods")
    assert methods is not None, "the optional `methods` extra must exist (DECISIONS/0009 3.6)"
    declared = {module_of(_name(r)) for r in methods}
    unused = declared_but_unused(declared, _test_and_notebook_imports(), set())
    assert not unused, f"`methods` declares {sorted(unused)}, which no test or notebook imports"


def test_pypdf_is_declared_in_the_notebooks_extra_with_a_lower_bound_and_something_imports_it() -> None:
    """DECISIONS/0010: pypdf is declared where readers install it, bounded, imported by a test or notebook,
    and not by the package (so the runtime dependency list is unchanged)."""
    notebooks = _pyproject()["project"]["optional-dependencies"]["notebooks"]
    declared = [r for r in notebooks if _name(r) == "pypdf"]
    assert len(declared) == 1 and ">=" in declared[0], declared
    assert "pypdf" in _test_and_notebook_imports()
    assert "pypdf" not in _src_imports()
    runtime = {module_of(_name(r)) for r in _pyproject()["project"]["dependencies"]}
    assert "pypdf" not in runtime


def test_the_package_ships_its_type_marker() -> None:
    """The package ships its type marker."""
    assert (SRC / "py.typed").exists()
    assert _pyproject()["tool"]["setuptools"]["package-data"]["krl_tutorials_data"] == ["py.typed"]


# --- the helpers can fail -------------------------------------------------
def test_the_import_scan_separates_top_level_from_lazy_and_ignores_stdlib() -> None:
    """The import scan separates top level from lazy and ignores stdlib."""
    found = third_party_imports(
        "import os, numpy as np\nfrom scipy import stats\n"
        "def f():\n    import statsmodels.api\n    from krl_tutorials_data import x\n"
    )
    assert found == {"numpy": True, "scipy": True, "statsmodels": False}


def test_undeclared_and_unused_are_reported() -> None:
    """Undeclared and unused are reported."""
    assert undeclared({"numpy", "pymc"}, {"numpy"}) == {"pymc"}
    assert declared_but_unused({"numpy", "mesa"}, {"numpy"}, set()) == {"mesa"}
    assert declared_but_unused({"numpy", "openpyxl"}, {"numpy"}, {"openpyxl"}) == set()


def test_distribution_names_map_to_import_names() -> None:
    """Distribution names map to import names."""
    assert module_of("scikit-learn") == "sklearn"
    assert module_of("krl-data-connectors") == "krl_data_connectors"
    assert _name("numpy>=1.26.0") == "numpy" and _name("pkg[extra]>=1; python_version>'3'") == "pkg"
