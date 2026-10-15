"""The credential-leak check in the release workflow, exercised rather than assumed.

This file exists because of an asymmetry that is easy to miss. On 2026-09-14 the
execution lane ran against live sources and reported "no credential reached an
output" for twelve notebooks. That is the right answer, and it is *not* evidence
that the detector works: a check that always returned nothing would print exactly
the same line. Every other gate in this repository has been mutation-tested; this
one -- the only security control among them -- had not been, which left it in the
same position the whole execution lane was in that morning.

The check had also already been wrong once. Its first version ran only on
notebooks that PASSED. The FRED key exposed in this project leaked through a
*traceback* printing a request URL with ``api_key=`` still in the query string,
so a FAILED notebook's partial outputs are the likeliest place for a key to
surface -- precisely where it was not looking. ``test_a_leak_in_a_failed_notebook``
below is the regression test for that, and it is the most important case here.

The subject under test is the script embedded in the workflow, extracted from the
YAML, so this tests the artifact that actually ships rather than a copy of it.
Refactoring the workflow step will break the extraction loudly, which is the
intended behaviour for a guard on a security control.

No network and no kernel: the NotebookClient call is replaced by a hook that
injects outputs directly.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import contextlib
import io
import os
import pathlib
import re
from typing import Callable

import pytest
import yaml

#: Obviously synthetic. Never a real credential, and short-circuits the question
#: of whether a test could ever print one.
SENTINEL = "SENTINEL-fake-value-not-a-real-credential-0000"

WORKFLOW = pathlib.Path(__file__).resolve().parents[1] / ".github/workflows/notebook-release-gates.yml"
STEP_NAME = "Restart & Run All against live sources"

_PRELUDE = "def _code(nb):\n    return next(c for c in nb.cells if c.cell_type=='code')\n"


def _embedded_script() -> str:
    """Return the Python embedded in the execution step, with the kernel stubbed."""
    workflow = yaml.safe_load(WORKFLOW.read_text())
    steps = [s for job in workflow["jobs"].values() for s in job["steps"]]
    matching = [s for s in steps if s.get("name") == STEP_NAME]
    assert len(matching) == 1, (
        f"expected exactly one step named {STEP_NAME!r}, found {len(matching)}. "
        "If the step was renamed, update STEP_NAME -- do not delete this test."
    )
    run = matching[0]["run"]
    assert "<<'PY'" in run, f"step {STEP_NAME!r} no longer embeds a heredoc script"
    script = run.split("<<'PY'", 1)[1].rsplit("PY", 1)[0]

    script = script.replace("from nbclient import NotebookClient", "")
    script = script.replace(
        "from nbclient.exceptions import CellExecutionError",
        "class CellExecutionError(Exception): pass",
    )
    stubbed, count = re.subn(
        r"NotebookClient\((?:.|\n)*?\)\.execute\(\)", "HOOK(notebook)", script
    )
    assert count == 1, (
        "expected exactly one NotebookClient(...).execute() call to stub, found "
        f"{count}. The extraction is stale; fix it rather than skipping the test."
    )
    return _PRELUDE + stubbed


def _run(hook_source: str, env: dict[str, str]) -> tuple[int | None, str]:
    """Execute the gate script with ``hook_source`` standing in for the kernel.

    Returns ``(exit_code, stdout)``; ``exit_code`` is None when the script ran to
    completion without calling ``sys.exit``.
    """
    source = _embedded_script().replace("HOOK(notebook)", hook_source)
    saved = dict(os.environ)
    os.environ.update(env)
    buffer = io.StringIO()
    code: int | None = None
    try:
        with contextlib.redirect_stdout(buffer):
            exec(compile(source, "<release-gate>", "exec"), {"__name__": "__main__"})
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    finally:
        os.environ.clear()
        os.environ.update(saved)
    return code, buffer.getvalue()


_CLEAN = '_code(notebook).outputs.append({"output_type":"stream","text":"ordinary output"})'
_LEAK_ON_SUCCESS = (
    '_code(notebook).outputs.append('
    f'{{"output_type":"stream","text":"https://api.example/data?key={SENTINEL}"}})'
)
_LEAK_ON_FAILURE = (
    '(_code(notebook).outputs.append('
    f'{{"output_type":"error","traceback":["...api_key={SENTINEL}..."]}}), '
    '(_ for _ in ()).throw(CellExecutionError("cell failed")))'
)


def test_a_clean_run_reports_no_leak() -> None:
    """Negative control. Without this, every assertion below could pass vacuously."""
    code, out = _run(_CLEAN, {"CENSUS_API_KEY": SENTINEL})
    assert code is None, out
    assert "CREDENTIAL LEAK" not in out


def test_a_leak_in_a_successful_notebook_fails_the_gate() -> None:
    code, out = _run(_LEAK_ON_SUCCESS, {"CENSUS_API_KEY": SENTINEL})
    assert code == 1, f"a key in an output must fail the gate\n{out}"
    assert "CREDENTIAL LEAK" in out
    assert "CENSUS_API_KEY appears in an executed output" in out
    assert SENTINEL not in out, "the gate must name the key, never print its value"


def test_a_leak_in_a_failed_notebook_fails_the_gate() -> None:
    """Regression test for the defect this check shipped with.

    The first version skipped failed notebooks. A traceback is how the real
    exposure happened, so this is the case that matters most.
    """
    code, out = _run(_LEAK_ON_FAILURE, {"FRED_API_KEY": SENTINEL})
    assert code == 1, f"a key in a FAILED notebook's traceback must fail the gate\n{out}"
    assert "CREDENTIAL LEAK" in out
    assert "FRED_API_KEY appears in an executed output" in out
    assert SENTINEL not in out, "the gate must name the key, never print its value"


def test_a_leak_outranks_an_execution_failure() -> None:
    """A leak is a rotation event and must not be buried under a red build."""
    _, out = _run(_LEAK_ON_FAILURE, {"FRED_API_KEY": SENTINEL})
    banners = [
        line.strip()
        for line in out.splitlines()
        if line.strip().startswith(("CREDENTIAL LEAK", "Notebooks that did not"))
    ]
    assert banners, out
    assert banners[0].startswith("CREDENTIAL LEAK"), (
        "the leak banner must be reported before execution failures, so that a "
        f"rotation event is not missed in a noisy log. Got: {banners}"
    )


@pytest.mark.parametrize("value", ["", "   ", "\n", "short"])
def test_a_degenerate_secret_does_not_match_everything(value: str) -> None:
    """A missing or junk secret must not be reported as leaking from every notebook.

    ``"" in blob`` is True for every blob, and so is ``" " in blob`` for any
    indented JSON -- so an empty or whitespace-only secret would raise a
    CREDENTIAL LEAK on the whole corpus and send someone to rotate a key for no
    reason. Found by this test, not by review.
    """
    code, out = _run(_LEAK_ON_SUCCESS, {"CENSUS_API_KEY": value})
    assert code is None, f"a degenerate secret ({value!r}) must not fire the leak check\n{out}"
    assert "CREDENTIAL LEAK" not in out


def test_a_secret_with_surrounding_whitespace_is_still_detected() -> None:
    """The dangerous direction: a pasted-with-newline secret must still match.

    GitHub stores what was pasted. If the secret carries a trailing newline, the
    key as it appears in an output does not, so an unstripped comparison silently
    misses a real leak -- failing open on the one control that must fail closed.
    """
    code, out = _run(_LEAK_ON_SUCCESS, {"CENSUS_API_KEY": f"  {SENTINEL}\n"})
    assert code == 1, f"a secret stored with surrounding whitespace must still be caught\n{out}"
    assert "CENSUS_API_KEY appears in an executed output" in out


def test_the_check_runs_on_every_notebook_not_only_the_passing_ones() -> None:
    """Structural guard: the leak scan must not sit behind a pass-only branch.

    ``test_a_leak_in_a_failed_notebook_fails_the_gate`` proves the behaviour; this
    catches the specific shape of the original defect if it is reintroduced in a
    form that happens to keep that test green.
    """
    script = _embedded_script()
    leak_index = script.index('appears in an executed output')
    preceding = script[:leak_index]
    assert "if notebook is not None" not in preceding, (
        "the leak scan is gated behind a `notebook is not None` guard again -- "
        "that is the pass-only branch this check was fixed to remove"
    )
