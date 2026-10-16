"""Gate 12 — CI must supply every credential the corpus actually needs.

The live-run job in `.github/workflows/notebook-release-gates.yml` executes every
notebook in `projects/` against real sources. Its `env:` block listed four
keys — CENSUS, FRED, BLS, HUD — and stayed at four while the corpus grew past it.

By 2026-09-18 three notebooks needed keys that block did not supply: D11 calls
`fetch_bea_regional` (BEA), and D13 and D26 call the FBI CDE (DATA_GOV). Every
client in this library **fails closed**, so those three would have failed the
release gate for want of two secrets rather than for anything wrong with them —
and a gate that fails for the wrong reason is a gate people learn to ignore.

Nothing caught it because the two lists were maintained by different hands at
different times: the fetchers know which key they need, the workflow does not, and
no one compared them.

This gate compares them.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from typing import Final

import pytest

from krl_tutorials_data import sources

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
WORKFLOW: Final = REPO_ROOT / ".github" / "workflows" / "notebook-release-gates.yml"
NOTEBOOKS: Final = REPO_ROOT / "projects"

FETCHER_CALL: Final = re.compile(r"\b(fetch_[a-z0-9_]+)\s*\(")
LOAD_KEY: Final = re.compile(r"load_key\(\s*[\"']([A-Z_]+)[\"']")


def _keys_supplied_by_ci() -> set[str]:
    """Every name the workflow exports from `secrets.`, whatever it is called.

    An earlier version matched only names ending `_API_KEY`, which made the
    stray-credential test below blind to precisely what it claims to guard: a
    mutation exporting `PAX_ADMIN_DATABASE_URL` was not caught, because the
    parser could not see it. A gate that cannot perceive the thing it forbids is
    worse than none, since it is reported as coverage.
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    return set(re.findall(r"^\s+([A-Z][A-Z0-9_]*):\s*\$\{\{\s*secrets\.", text, re.M))


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
        found = LOAD_KEY.findall(body)
        if found:
            mapping[name] = found[0]
    return mapping


def _keys_each_notebook_needs() -> dict[str, set[str]]:
    by_fetcher = _key_for_fetcher()
    out: dict[str, set[str]] = {}
    for path in sorted(NOTEBOOKS.rglob("*.ipynb")):
        code = "\n".join(
            "".join(c.get("source", []))
            for c in json.loads(path.read_text(encoding="utf-8"))["cells"]
            if c["cell_type"] == "code"
        )
        needed = {by_fetcher[f] for f in {m.group(1) for m in FETCHER_CALL.finditer(code)}
                  if f in by_fetcher}
        if needed:
            out[path.name] = needed
    return out


def test_the_workflow_supplies_credentials_at_all() -> None:
    """Guard the parser: a gate that reads zero keys would pass vacuously."""
    supplied = _keys_supplied_by_ci()
    assert len(supplied) >= 4, f"parsed only {supplied} from the workflow env block"


def test_every_credential_a_notebook_needs_is_supplied_by_ci() -> None:
    supplied = _keys_supplied_by_ci()
    gaps: list[str] = []
    for notebook, needed in _keys_each_notebook_needs().items():
        missing = needed - supplied
        if missing:
            gaps.append(f"{notebook}: {sorted(missing)}")
    assert not gaps, (
        "the live-run workflow does not supply credentials these notebooks need, "
        "and every client fails closed, so each would fail the release gate for "
        f"want of a secret:\n  " + "\n  ".join(gaps)
    )


#: Secrets the workflow may export that are NOT credentials for any data source and that
#: no code in this library can load (``load_key`` refuses anything outside ALLOWED_KEYS).
#: Each is exempt from the closed-set rule only for the one purpose named, and
#: ``test_a_ci_only_secret_reaches_nothing_but_its_own_step`` proves the scope.
CI_ONLY_SECRETS: Final[dict[str, str]] = {
    "KRL_SURFACE_DENYLIST_JSON": "the private name patterns for scripts/check_public_surface.py",
}


def test_ci_supplies_no_credential_outside_the_allowed_set() -> None:
    """The workflow may not reach for a key this layer refuses to load.

    `ALLOWED_KEYS` is a closed set precisely so a tutorial kernel cannot reach
    the rest of an operator's secrets file. A workflow that exported something
    outside it would be re-opening that door from the other side.
    """
    stray = _keys_supplied_by_ci() - set(sources.ALLOWED_KEYS) - set(CI_ONLY_SECRETS)
    assert not stray, (
        f"the workflow exports {sorted(stray)}, which ALLOWED_KEYS does not "
        "permit this library to read."
    )


@pytest.mark.parametrize("fetcher,key", sorted(_key_for_fetcher().items()))
def test_each_fetchers_key_is_in_the_allowed_set(fetcher: str, key: str) -> None:
    assert key in sources.ALLOWED_KEYS, (
        f"{fetcher} loads {key}, which is not in ALLOWED_KEYS, so it can never "
        "succeed."
    )


def test_a_ci_only_secret_reaches_nothing_but_its_own_step() -> None:
    """The denylist secret is written to a temp file for the surface check and goes no further.

    It must not be in the job that runs notebooks against real data, must not be loadable
    by the library, and must appear only in a step that runs the public-surface check.
    """
    import yaml

    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for name in CI_ONLY_SECRETS:
        assert name not in sources.ALLOWED_KEYS
        holders = [
            (job_name, step)
            for job_name, job in doc["jobs"].items()
            for step in job.get("steps", [])
            if name in json.dumps(step)
        ]
        assert holders, f"{name} is declared exempt but the workflow never uses it"
        for job_name, step in holders:
            assert job_name == "static-gates", f"{name} must not reach the {job_name} job"
            assert "check_public_surface.py" in step.get("run", ""), (
                f"{name} appears in a step that does not run the public-surface check"
            )
