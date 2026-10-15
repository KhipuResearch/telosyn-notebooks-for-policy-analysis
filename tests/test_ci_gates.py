"""The blocking workflow must stay capable of failing.

Audit finding F-15 was not that a check was missing. It was that the checks
present could not fail: `notebook-validation.yml` printed "Valid structure" for
notebooks that could not parse, and every content step in `tutorial-quality.yml`
and `markdown-quality.yml` was neutralised — the markdown ones twice over, with
`|| true` inside the run block AND `continue-on-error: true` on the step, so
removing either alone changed nothing.

A comment saying "nothing here may carry continue-on-error" is the same kind of
artifact as the prose those workflows printed. This makes it checkable.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML is needed to parse the workflows")

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"

#: The workflow whose whole purpose is to be able to fail.
BLOCKING = "notebook-release-gates.yml"

#: Advisory by declaration. Each carries a header saying so; that header is what
#: this test holds them to, so a file cannot quietly become advisory.
#: No advisory workflows remain. The two that existed checked a tier scheme the
#: notebooks never used and a retired copyright string; both were removed 2026-10-15.
ADVISORY: tuple[str, ...] = ()


def _steps(path: Path) -> list[dict]:
    spec = yaml.safe_load(path.read_text())
    return [step for job in spec["jobs"].values() for step in job["steps"]]


def test_the_blocking_workflow_exists() -> None:
    assert (WORKFLOWS / BLOCKING).exists(), (
        f"{BLOCKING} is missing; there would be no blocking notebook CI at all"
    )


def test_no_step_in_the_blocking_workflow_is_neutralised() -> None:
    """`continue-on-error` and a trailing `|| true` both suppress a failure."""
    offenders = []
    for step in _steps(WORKFLOWS / BLOCKING):
        name = step.get("name", step.get("uses", "<unnamed>"))
        if step.get("continue-on-error"):
            offenders.append(f"{name}: continue-on-error")
        run = str(step.get("run", ""))
        # Only a trailing `|| true` suppresses the step's exit code; the string
        # may legitimately appear inside a heredoc.
        if any(line.rstrip().endswith("|| true") for line in run.splitlines()):
            offenders.append(f"{name}: run block ends in `|| true`")
    assert not offenders, (
        "the blocking workflow contains steps that cannot fail, which is audit "
        "finding F-15 reintroduced:\n  " + "\n  ".join(offenders)
    )


def test_the_blocking_workflow_can_actually_fail() -> None:
    """At least one step must have a real failure path, or it gates nothing."""
    sources = "\n".join(str(step.get("run", "")) for step in _steps(WORKFLOWS / BLOCKING))
    assert "sys.exit(1)" in sources, "no step raises a non-zero exit"
    assert "pytest" in sources, "the gate suite is not run"


def test_the_retired_validator_stays_retired() -> None:
    """`notebook-validation.yml` warned about the stored outputs this corpus requires."""
    assert not (WORKFLOWS / "notebook-validation.yml").exists(), (
        "notebook-validation.yml has been re-enabled. It checks that notebooks carry "
        "NO stored outputs, which is now backwards: tests/test_gate_evidence.py "
        "requires them, and a silent notebook is the F-1/F-2 defect."
    )
    # Retired means removed, not renamed: a `.disabled` file is one rename from live.
    assert not (WORKFLOWS / "notebook-validation.yml.disabled").exists()


@pytest.mark.parametrize("name", ADVISORY)
def test_advisory_workflows_say_they_are_advisory(name: str) -> None:
    """A file that cannot fail must not read as a gate.

    These are not required to become blocking. They are required to stop
    implying they already are.
    """
    header = (WORKFLOWS / name).read_text()[:200]
    assert header.startswith("# ADVISORY ONLY"), (
        f"{name} contains steps that cannot fail and no longer declares itself "
        f"advisory. Either give its checks a failure path and move them into "
        f"{BLOCKING}, or restore the header."
    )
