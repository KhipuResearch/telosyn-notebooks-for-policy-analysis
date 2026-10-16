"""The workflows give the history-reading checks the history they need, and run them.

The public-surface check compares a branch with ``origin/main``; a shallow checkout
has no such base, and the checker treats an unknown base as an error rather than a
pass. So every checkout in the workflows fetches full history, and the blocking
workflow runs the checker. The coverage floor only ever rises.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((REPO / ".github" / "workflows").glob("*.yml"))

#: The coverage floor reached at the close of Timebox 0. Raise this constant, and
#: pytest.ini, together after each timebox; never lower either.
FLOOR_AT_TB0 = 84


def _steps(path: Path):
    """Steps."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    for job in doc["jobs"].values():
        yield from job.get("steps", [])


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda p: p.name)
def test_every_checkout_fetches_full_history(workflow: Path) -> None:
    """Every checkout fetches full history."""
    checkouts = [
        s for s in _steps(workflow) if str(s.get("uses", "")).startswith("actions/checkout")
    ]
    assert checkouts, f"{workflow.name} has no checkout step; the test is scanning nothing"
    for step in checkouts:
        assert step.get("with", {}).get("fetch-depth") == 0, (
            f"{workflow.name}: a checkout without `fetch-depth: 0` cannot supply origin/main to "
            "the public-surface check"
        )


def test_the_blocking_workflow_runs_the_public_surface_check_and_is_not_neutralised() -> None:
    """The blocking workflow runs the public surface check and is not neutralised."""
    steps = list(_steps(REPO / ".github" / "workflows" / "notebook-release-gates.yml"))
    runs = [s for s in steps if "check_public_surface.py" in str(s.get("run", ""))]
    assert runs, "the blocking workflow does not run scripts/check_public_surface.py"
    for step in runs:
        assert not step.get("continue-on-error"), "the surface step must be able to fail the build"
        assert "--range" in step["run"] and "--tree" in step["run"]


def _floor() -> int:
    """Floor."""
    text = (REPO / "pytest.ini").read_text(encoding="utf-8")
    match = re.search(r"^\s*--cov-fail-under=(\d+)\s*$", text, re.M)
    assert match, "pytest.ini has no --cov-fail-under"
    return int(match.group(1))


def test_the_coverage_floor_only_ratchets_up() -> None:
    """The coverage floor only ratchets up."""
    assert _floor() >= FLOOR_AT_TB0, (
        f"pytest.ini's floor is {_floor()}, below the {FLOOR_AT_TB0} reached at the close of "
        "Timebox 0. The floor is never lowered."
    )
    assert "--cov=src" in (REPO / "pytest.ini").read_text(encoding="utf-8")


def test_the_gate_make_target_describes_the_gates_it_runs() -> None:
    """The gate make target describes the gates it runs."""
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    line = next(line for line in makefile.splitlines() if line.startswith("gates:"))
    assert "test_gate_*.py" in makefile and "nine" not in line
    gates = sorted(p.stem for p in (REPO / "tests").glob("test_gate_*.py"))
    for needed in ("test_gate_identification", "test_gate_data_mode_reserved",
                   "test_gate_pums_aggregate_only"):
        assert needed in gates
