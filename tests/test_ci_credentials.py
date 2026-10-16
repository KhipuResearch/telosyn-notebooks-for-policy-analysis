"""CI exports no secret.

Owner rule (2026-10-16): the repository stores and uses no secrets. The workflows
therefore reference no ``secrets.`` context, declare no deployment environment, and
contain no job that re-executes the notebooks against live sources, which would need
keys. A reader re-executes them with their own keys.

This replaces the earlier gate that compared the keys CI supplied with the keys the
fetchers load: with nothing supplied, the comparison is "zero". What remains of that
gate's purpose -- every key a fetcher loads is one the library may read -- stays.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path
from typing import Final

import pytest
import yaml

from krl_tutorials_data import sources

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
WORKFLOWS: Final = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))

LOAD_KEY: Final = re.compile(r"load_key\(\s*[\"']([A-Z_]+)[\"']")
SECRETS_CONTEXT: Final = re.compile(r"\$\{\{[^}]*\bsecrets\b", re.I)


def test_there_are_workflows_to_scan() -> None:
    """There are workflows to scan."""
    assert len(WORKFLOWS) >= 2, "the scan is reading nothing"


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda p: p.name)
def test_a_workflow_exports_zero_secrets(workflow: Path) -> None:
    """A workflow exports zero secrets."""
    text = workflow.read_text(encoding="utf-8")
    assert not SECRETS_CONTEXT.search(text), (
        f"{workflow.name} reads the `secrets` context; this repository stores and uses none"
    )
    assert "secrets." not in re.sub(r"\.secrets\.\w+", "", text), (
        f"{workflow.name} mentions `secrets.` outside a temporary file name"
    )


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda p: p.name)
def test_no_job_declares_an_environment_or_exports_a_credential_named_variable(
    workflow: Path,
) -> None:
    """No job declares an environment or exports a credential named variable."""
    doc = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    for job_name, job in doc["jobs"].items():
        assert "environment" not in job, f"{workflow.name}:{job_name} declares an environment"
        blocks = [job.get("env", {})] + [s.get("env", {}) for s in job.get("steps", [])]
        for block in blocks:
            for name in block:
                assert name not in sources.ALLOWED_KEYS and not name.endswith("_API_KEY"), (
                    f"{workflow.name}:{job_name} exports {name}"
                )


def test_no_job_re_executes_notebooks_against_live_sources() -> None:
    """No job re executes notebooks against live sources."""
    for workflow in WORKFLOWS:
        text = workflow.read_text(encoding="utf-8")
        assert "execution-gate" not in text and "Restart & Run All" not in text, (
            f"{workflow.name} still carries the live-execution lane"
        )
        assert "jupyter nbconvert" not in text and "--execute" not in text


def _key_for_fetcher() -> dict[str, str]:
    """Which credential each fetcher loads, read from the fetcher itself."""
    mapping: dict[str, str] = {}
    for name, obj in vars(sources).items():
        if not name.startswith("fetch_") or not callable(obj):
            continue
        try:
            body = inspect.getsource(obj)
        except (OSError, TypeError):  # pragma: no cover
            continue
        found = LOAD_KEY.search(body)
        if found:
            mapping[name] = found.group(1)
    return mapping


def test_the_fetcher_scan_reads_something() -> None:
    """The fetcher scan reads something."""
    assert len(_key_for_fetcher()) >= 5


@pytest.mark.parametrize("fetcher,key", sorted(_key_for_fetcher().items()))
def test_each_fetchers_key_is_in_the_allowed_set(fetcher: str, key: str) -> None:
    """Each fetchers key is in the allowed set."""
    assert key in sources.ALLOWED_KEYS, (
        f"{fetcher} loads {key}, which is not in ALLOWED_KEYS, so it can never succeed."
    )
