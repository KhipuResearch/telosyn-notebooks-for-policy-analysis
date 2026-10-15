"""Gate 7 — execution evidence.

F-1 and F-2 turned on a corpus of 33 notebooks in which **every** code cell had
a null execution count and no stored output, while the surrounding prose
reported results. The audit's phrasing for this was *uncontrolled execution
provenance*: the artifact provides no evidence that the code it contains ever
produced the numbers described around it.

A released notebook in this corpus therefore has to carry its own evidence. The
invariant is not "someone ran it once" — that is unfalsifiable from the file —
but that the committed artifact shows a single, ordered, complete run.

This gate would have failed three notebooks in this very tree, which had been
described in the README as executed against live data while storing no output
at all. That is the exact overclaim the corpus exists to prevent, made about
the corpus itself.

**On stripping outputs.** ``test_no_key_material_in_outputs`` guards the risk
that committing outputs would otherwise create. The two gates are complementary:
outputs are retained so the artifact is self-evidencing, and screened so that
retention is safe.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

from gate_support import Notebook


def test_every_code_cell_carries_an_execution_count(notebook: Notebook) -> None:
    """No code cell may be unexecuted in a released artifact."""
    cells = [c for c in notebook.code if c.source.strip()]
    if not cells:
        return
    missing = [c.index for c in cells if c.execution_count is None]
    assert not missing, (
        f"{notebook.path.name} has {len(missing)} of {len(cells)} code cells with no "
        f"execution count (cells {missing[:12]}). This is the F-1/F-2 signature: the "
        f"artifact carries no evidence that its code produced the results described "
        f"around it. Execute the notebook in place before committing."
    )


def test_execution_counts_are_a_single_ordered_run(notebook: Notebook) -> None:
    """Counts must increase strictly, which a top-to-bottom run produces.

    Out-of-order counts mean cells were run in an order the reader cannot
    reconstruct, so the stored outputs may not correspond to the code as it now
    stands above them.
    """
    counts = [
        c.execution_count for c in notebook.code
        if c.source.strip() and c.execution_count is not None
    ]
    if len(counts) < 2:
        return
    assert counts == sorted(counts) and len(set(counts)) == len(counts), (
        f"{notebook.path.name} has non-monotonic execution counts {counts}. The "
        f"stored outputs cannot be attributed to a single top-to-bottom run."
    )


def test_a_notebook_that_reports_results_stores_some_output(notebook: Notebook) -> None:
    """At least one cell must have produced something.

    A notebook whose every cell is silent has nothing for a reviewer to check a
    narrative claim against.
    """
    cells = [c for c in notebook.code if c.source.strip()]
    if not cells:
        return
    produced = sum(1 for c in cells if c.outputs)
    assert produced > 0, (
        f"{notebook.path.name} stores no output in any of its {len(cells)} code "
        f"cells. Every reported quantity is then unverifiable from the artifact."
    )
