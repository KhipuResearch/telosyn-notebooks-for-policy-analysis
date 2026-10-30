"""DECISIONS/0012: pymc is an optional extra for one notebook, never core, never needed by a library test.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

from pathlib import Path

from test_src_imports_declared import (
    REPO,
    _name,
    _pyproject,
    _src_imports,
    _test_and_notebook_imports,
    module_of,
    third_party_imports,
)


def _library_test_imports() -> set[str]:
    """Third-party modules imported by library tests (not notebooks), excluding the files that only name the extra."""
    seen: set[str] = set()
    for path in sorted((REPO / "tests").rglob("test_*.py")):
        if path.name in {Path(__file__).name, "test_src_imports_declared.py"}:
            continue
        seen |= set(third_party_imports(path.read_text(encoding="utf-8")))
    return seen


def test_pymc_is_its_own_optional_extra_with_a_lower_bound_and_is_never_core() -> None:
    extras = _pyproject()["project"]["optional-dependencies"]
    assert [r for r in extras["pymc"] if _name(r) == "pymc"] and all(">=" in r for r in extras["pymc"])
    for place in ("notebooks", "methods", "test", "dev", "connectors"):
        assert "pymc" not in {_name(r) for r in extras.get(place, [])}, f"pymc must not ride in the {place} extra"
    runtime = {module_of(_name(r)) for r in _pyproject()["project"]["dependencies"]}
    assert "pymc" not in runtime
    assert "pymc" not in _src_imports(), "the package must not import pymc"
    assert "pymc" not in _library_test_imports(), "no library test may require pymc"
    assert "pymc" in _test_and_notebook_imports(), "a declared extra must be imported by the notebook that needs it"
