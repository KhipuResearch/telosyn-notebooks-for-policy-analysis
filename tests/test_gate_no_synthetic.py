"""Gate 4 — the real-data constraint.

The tutorial corpus is real-data-only. Randomness may not produce any value
that a reader could mistake for a measurement or a model property.

Catches F-2 (RNG reported as model Complexity/Interpretability), F-3
(tautological target built from RNG), F-8 (simulated content reported with a
measured success rate) and F-9 (hardcoded metric constants in a bare except).

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import re

from gate_support import Notebook

RNG_CALL = re.compile(r"\b(?:np|numpy)\.random\.\w+|(?<![\w.])random\.(?:random|uniform|gauss|normal|choice|randint|sample)\b")

# A random draw bound to a name that reads as a measurement or model property.
RNG_AS_METRIC = re.compile(
    r"\b(\w*(?:score|metric|accuracy|precision|recall|auc|rmse|mae|r2|confidence|"
    r"reliability|coverage|complexity|interpretability|importance|silhouette|"
    r"davies\w*|pvalue|p_value|effect|estimate|word_count)\w*)\s*=\s*"
    r"(?:np\.|numpy\.)?random\.",
    re.I,
)

# A numeric literal assigned to a metric name inside an exception handler.
EXCEPT_BLOCK = re.compile(r"except[^\n:]*:\s*\n((?:[ \t]+.*\n)+)")
LITERAL_METRIC = re.compile(
    r"\b(\w*(?:score|silhouette|davies\w*|rmse|mae|r2|accuracy|auc|coverage|"
    r"confidence|reliability)\w*)\s*=\s*-?\d+(?:\.\d+)?\s*(?:#.*)?$",
    re.I | re.M,
)

BARE_EXCEPT = re.compile(r"except\s*:")


def test_no_rng_derived_metrics(notebook: Notebook) -> None:
    hits = []
    for cell in notebook.code:
        for m in RNG_AS_METRIC.finditer(cell.source):
            hits.append(f"cell {cell.index}: {m.group(0).strip()!r}")
    assert not hits, (
        f"{notebook.path.name} binds a random draw to a name that reads as a "
        f"measurement. A reader cannot distinguish it from a computed value:\n  "
        + "\n  ".join(hits)
    )


def test_no_randomness_in_analysis_path(notebook: Notebook) -> None:
    """Randomness is permitted only where it is declared and cannot become a finding."""
    declared = "illustrative" in notebook.metadata.get("krl", {}).get("data_mode", "")
    if declared:
        return
    hits = [
        f"cell {c.index}: {m.group(0)}"
        for c in notebook.code
        for m in RNG_CALL.finditer(c.source)
    ]
    assert not hits, (
        f"{notebook.path.name} calls a random number generator but does not declare "
        f"krl.data_mode = 'illustrative'. This corpus is real-data-only:\n  "
        + "\n  ".join(hits)
    )


def test_no_hardcoded_metric_in_exception_handler(notebook: Notebook) -> None:
    hits = []
    for cell in notebook.code:
        for blk in EXCEPT_BLOCK.finditer(cell.source):
            for m in LITERAL_METRIC.finditer(blk.group(1)):
                hits.append(f"cell {cell.index}: {m.group(0).strip()!r}")
    assert not hits, (
        f"{notebook.path.name} substitutes a literal for a metric inside an "
        f"exception handler. The reader cannot tell it from a measured value:\n  "
        + "\n  ".join(hits)
    )


def test_no_bare_except(notebook: Notebook) -> None:
    hits = [f"cell {c.index}" for c in notebook.code if BARE_EXCEPT.search(c.source)]
    assert not hits, (
        f"{notebook.path.name} uses a bare `except:`, which converts a data failure "
        f"into a silent substitution: {', '.join(hits)}"
    )
