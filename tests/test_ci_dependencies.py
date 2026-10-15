"""Every third-party import in CI's scope must be installable by CI.

This gate exists because the same defect occurred three times in one day, each
time discovered only by a red run:

  * ``responses``/``load_key`` coupling in the fetcher contract tests, which
    passed locally because a credential file happened to exist;
  * ``statsmodels``, imported by one notebook, absent from the execution lane's
    install list, found when Lane 2 ran for the first time;
  * ``pyyaml``, imported by ``tests/test_leak_check.py`` -- a file written to
    close a verification gap, which itself opened one.

Each was the same mistake: a dependency added without checking what CI installs.
Each cost a full run to find. The pattern is mechanical, so this turns it into a
check that fails in a second instead of a check that fails in CI.

The install list is read from the workflow itself rather than restated here, so
this cannot drift from what actually runs. It is parsed as text, not YAML,
because this module must not itself depend on a package whose presence it is
responsible for verifying.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/notebook-release-gates.yml"

#: Distribution name -> module name, where they differ. The pragma is the
#: scanner's own allowlist marker, kept inline so the exception is visible where
#: it applies: the workflow's secret scan flags this line on the keyword
#: "secret" in the scanner's own package name. A false positive, and exactly the
#: kind that should be annotated at the point of exception rather than excused by
#: widening the scan.
#: Distributions whose PyPI name is not their import name. Without an entry here
#: the gate reports a module as unsatisfiable while the workflow installs it
#: perfectly well -- a false alarm, which is how a useful gate gets switched off.
_DISTRIBUTION_ALIASES = {  # pragma: allowlist secret
    "pyyaml": "yaml",
    "detect-secrets": "detect_secrets",  # pragma: allowlist secret
    "scikit-learn": "sklearn",
}

#: Paths the workflow passes to pytest as --ignore. Their imports are out of
#: scope because they never execute in CI. Read from the workflow, not restated.
def _ci_exclusions() -> set[str]:
    text = WORKFLOW.read_text()
    return {m.rstrip(",") for m in re.findall(r"--ignore=(\S+)", text)}


def _ci_installable_modules() -> set[str]:
    """Module names CI can import, derived from the workflow's pip install lines."""
    text = WORKFLOW.read_text()
    lines = re.findall(r"^\s*pip install (?!-e\b|--upgrade\b)(.+)$", text, re.M)
    modules: set[str] = set()
    # The documented install: `pip install -e '.[a,b]'` resolves through
    # pyproject.toml -- runtime dependencies plus the named extras.
    for extras in re.findall(r"pip install -e '?\.\[([a-z,]+)\]'?", text):
        py = (ROOT / "pyproject.toml").read_text()
        blocks = [re.search(r"^dependencies\s*=\s*\[(.*?)^\]", py, re.S | re.M).group(1)]
        for e in extras.split(","):
            m = re.search(rf"^{e}\s*=\s*\[(.*?)^\]", py, re.S | re.M)
            assert m, f"workflow installs extra [{e}] which pyproject.toml does not define"
            blocks.append(m.group(1))
        for name in re.findall(r'"([A-Za-z0-9_.-]+)', "\n".join(blocks)):
            name = re.split(r"[<>=!\[]", name)[0].strip().lower()
            modules.add(_DISTRIBUTION_ALIASES.get(name, name.replace("-", "_")))
    assert lines or modules, "no `pip install` lines found in the workflow; parsing is stale"
    for line in lines:
        for token in line.split():
            if token.startswith("-"):
                continue
            name = re.split(r"[<>=!\[]", token)[0].strip().lower()
            modules.add(_DISTRIBUTION_ALIASES.get(name, name.replace("-", "_")))
    return modules


def _local_modules() -> set[str]:
    """Importable names that resolve inside the repository, not from PyPI."""
    local: set[str] = set()
    for base in (ROOT, ROOT / "src", ROOT / "tests"):
        for child in base.iterdir():
            if child.is_dir() and (child / "__init__.py").exists():
                local.add(child.name)
            elif child.is_dir() and not child.name.startswith("."):
                local.add(child.name)
            elif child.suffix == ".py":
                local.add(child.stem)
    return local


def _imports(source: str, origin: str) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        pytest.fail(f"{origin} does not parse")
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module.split(".")[0])
    return found


def _in_ci_scope(path: pathlib.Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    return not any(
        relative == excluded or relative.startswith(excluded.rstrip("/") + "/")
        for excluded in _ci_exclusions()
    )


def _sources() -> list[tuple[str, str]]:
    """(origin, source) for every file CI imports or executes."""
    out: list[tuple[str, str]] = []
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        if _in_ci_scope(path):
            out.append((path.relative_to(ROOT).as_posix(), path.read_text()))
    conftest = ROOT / "tests" / "conftest.py"
    if conftest.exists():
        out.append(("tests/conftest.py", conftest.read_text()))
    for path in sorted((ROOT / "projects").rglob("*.ipynb")):
        cells = json.loads(path.read_text()).get("cells", [])
        code = "\n".join(
            "".join(c.get("source", [])) for c in cells if c.get("cell_type") == "code"
        )
        out.append((path.relative_to(ROOT).as_posix(), code))
    return out


def test_every_ci_import_is_satisfied() -> None:
    available = _ci_installable_modules() | _local_modules() | set(sys.stdlib_module_names)
    missing: dict[str, set[str]] = {}
    for origin, source in _sources():
        for module in _imports(source, origin) - available:
            missing.setdefault(module, set()).add(origin)
    assert not missing, "imports CI cannot satisfy — add them to the workflow's pip install:\n" + "\n".join(
        f"  {module}: needed by {', '.join(sorted(origins)[:3])}"
        for module, origins in sorted(missing.items())
    )


def test_the_gate_is_not_vacuous() -> None:
    """A gate that can never fail is worse than no gate; prove this one can."""
    available = _ci_installable_modules() | _local_modules() | set(sys.stdlib_module_names)
    assert "definitely_not_a_real_package" not in available
    assert _imports("import definitely_not_a_real_package", "<synthetic>") - available

    # and prove it is reading the real install list rather than a permissive default
    assert "pandas" in _ci_installable_modules()
    assert "pyyaml" not in _ci_installable_modules(), "distribution name should map to its module"
    assert "yaml" in _ci_installable_modules()


def test_the_sources_it_scans_are_not_empty() -> None:
    """The commonest way a gate like this dies is by silently scanning nothing."""
    origins = [origin for origin, _ in _sources()]
    assert sum(o.endswith(".ipynb") for o in origins) >= 10, origins
    assert sum(o.startswith("tests/") for o in origins) >= 10, origins
