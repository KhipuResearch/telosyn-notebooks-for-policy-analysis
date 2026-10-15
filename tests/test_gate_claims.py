"""Gate 6 — narrative consistency.

Catches F-4 (conclusions printed with no computational antecedent) and F-7
(narrative contradicting the computed result).

A substantive claim may not be authored as a string literal. It must be
rendered from a value the notebook computed.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import ast
import re

import pytest

from gate_support import Notebook

# Categorical assertions that require a computed antecedent.
ASSERTION_WORDS = (
    "significant", "significantly", "causal", "causes", "proves", "proven",
    "validated", "passed", "best-performing", "outperform", "robust",
    "production ready", "peer review", "demonstrates that", "confirms",
)
PERFORMANCE_CLAIM = re.compile(
    r"(?:achiev\w+|accuracy of|r2 of|r\u00b2 of|exceeds?|>\s*\d{1,3}\s*%)", re.I
)
# A print/markdown string containing a hard number presented as a result.
NUMERIC_IN_LITERAL = re.compile(r"[\"'][^\"'\n]*?\b\d{1,3}(?:\.\d+)?\s*%[^\"'\n]*?[\"']")
FSTRING = re.compile(r"f[\"']")


#: Literals shorter than this are not substantive claims; matches the original scan.
_MIN_CLAIM_CHARS: int = 25


def _literal_strings(src: str) -> list[str]:
    """Every plain string literal in *src*, excluding f-string content.

    Parsed, not pattern-matched. The regex this replaces excluded f-strings with
    a ``(?<!f)`` lookbehind on the opening quote, which an apostrophe inside an
    f-string defeats: in

        f"    ...whose area's internal spread exceeds {t}%: {n}"

    the apostrophe closed the match and the remainder was read as a fresh non-f
    literal, so a line whose every number was computed was reported as a hardcoded
    claim. A gate that fails correct code gets switched off, so the detection here
    is exact rather than approximate.

    An f-string's literal segments are deliberately excluded: the defect this gate
    exists to catch is a figure with no computational antecedent, and an f-string is
    the antecedent. Plain literals nested inside an f-string's expressions are
    excluded too - they are format specs and dictionary keys, not prose.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        # test_every_code_cell_compiles owns that failure; do not double-report it,
        # and do not silently pass either - fall back to the coarse scan.
        return re.findall(r"(?<!f)(?<!r)[\"']{1}([^\"'\n]{25,})[\"']{1}", src)

    inside_fstring: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            for inner in ast.walk(node):
                inside_fstring.add(id(inner))

    # Docstrings are documentation, not output. F-4 is about a figure PRINTED with
    # no computational antecedent; a docstring that quotes a source's own threshold
    # ("Cost burden > 30%") asserts nothing about a result. Flagging those made the
    # gate fire on a cell whose every printed number was computed.
    #
    # Measured before accepting the change, because narrowing a gate to fit new
    # content is how gates die: against the forensic archive the exclusion drops
    # **23 detections and 0 true positives**. All 23 were ordinary API docstrings
    # ("Create soft causal mask...", "Run all validation checks...") matching
    # assertion words like "causal" and "validated" inside prose about code. The
    # gate got stricter in the sense that matters.
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstrings.add(id(body[0].value))

    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in inside_fstring
        and id(node) not in docstrings
        and len(node.value) >= _MIN_CLAIM_CHARS
    ]


def test_no_hardcoded_performance_claims(notebook: Notebook) -> None:
    hits = []
    for cell in notebook.code:
        for lit in _literal_strings(cell.source):
            if PERFORMANCE_CLAIM.search(lit) and "%" in lit:
                hits.append(f"cell {cell.index}: {lit[:90]!r}")
    assert not hits, (
        f"{notebook.path.name} prints a performance figure as a string literal with "
        f"no computational antecedent (F-4). Render it from the computed value:\n  "
        + "\n  ".join(hits)
    )


# A disclaimer is the opposite of the defect this gate exists to catch. F-4 and
# F-7 concern notebooks *asserting* a conclusion ("validated", ">85% accuracy",
# "PRODUCTION READY"). A notebook stating that its design does NOT support a
# causal reading is doing the right thing and must not be penalised for it.
NEGATORS = (
    "no ", "not ", "never ", "cannot ", "can not ", "is not", "are not",
    "does not", "do not", "without ", "rather than", "neither ", "nor ",
    "n't ", "avoid ", "must not", "may not", "beyond ", "only.",
)


def _is_negated(literal_lower: str, at: int) -> bool:
    """True when the assertion word at ``at`` sits inside a negated clause.

    The window is bounded by sentence punctuation so that a negation in a
    previous sentence cannot launder a positive claim in this one.
    """
    start = max(0, at - 60)
    window = literal_lower[start:at]
    for stop in (". ", "; ", "! "):
        if (cut := window.rfind(stop)) != -1:
            window = window[cut + len(stop):]
    return any(neg in window for neg in NEGATORS)


def test_categorical_assertions_are_computed(notebook: Notebook) -> None:
    """A word like 'significant' in a printed literal must come from a test result.

    Positive assertions only: disclaimers and stated non-claims are permitted,
    and are in fact what this corpus wants notebooks to say.
    """
    hits = []
    for cell in notebook.code:
        for lit in _literal_strings(cell.source):
            low = lit.lower()
            for word in ASSERTION_WORDS:
                # Word-boundary match. Substring matching produced false
                # positives: "robust" fired inside "robustness" in a sentence
                # giving methodological advice rather than claiming a result.
                m = re.search(rf"\b{re.escape(word)}\b", low)
                at = m.start() if m else -1
                if at != -1 and not _is_negated(low, at):
                    hits.append(f"cell {cell.index}: [{word}] {lit[:80]!r}")
                    break
    assert not hits, (
        f"{notebook.path.name} asserts a categorical conclusion in a string literal. "
        f"Derive it from the computed result so it cannot drift (F-4, F-7):\n  "
        + "\n  ".join(hits)
    )


# --------------------------------------------------------------------------- #
# The gate's own regression tests.
#
# `_literal_strings` was a regex that excluded f-strings with a `(?<!f)`
# lookbehind on the opening quote. An apostrophe inside an f-string defeated it,
# so a line whose every figure was computed was reported as a hardcoded claim.
# These pin both directions: a gate that stops firing is worse than the defect,
# and a gate that fires on correct code gets switched off.
# --------------------------------------------------------------------------- #

HARDCODED = 'print("The model achieves an accuracy of 92% on held-out data")'
COMPUTED_WITH_APOSTROPHE = (
    "print(f\"    ...whose area's internal spread exceeds {t:>3}%: "
    '{n:>4} ({100 * n / m:.1f}% of those rows)")'
)
COMPUTED_PLAIN = 'print(f"accuracy of {acc:.1%} exceeds the {floor:.0%} floor")'


def test_a_hardcoded_performance_claim_is_still_detected() -> None:
    """The defect this gate exists for must survive every repair to the gate."""
    flagged = [
        lit for lit in _literal_strings(HARDCODED)
        if PERFORMANCE_CLAIM.search(lit) and "%" in lit
    ]
    assert flagged, "the gate no longer detects a hardcoded performance figure"


@pytest.mark.parametrize(
    "source", [COMPUTED_WITH_APOSTROPHE, COMPUTED_PLAIN],
    ids=["apostrophe inside an f-string", "plain f-string"],
)
def test_a_computed_figure_is_not_reported_as_hardcoded(source: str) -> None:
    """An f-string IS the computational antecedent and must never be flagged."""
    flagged = [
        lit for lit in _literal_strings(source)
        if PERFORMANCE_CLAIM.search(lit) and "%" in lit
    ]
    assert not flagged, (
        "the gate flagged a figure rendered from a computed value. This is the "
        "false positive that makes a gate get disabled; fix the detection, not "
        f"the notebook. Flagged: {flagged}"
    )


def test_unparseable_source_falls_back_rather_than_passing_silently() -> None:
    """A cell that does not parse must not become a free pass for this gate."""
    broken = 'print("achieves an accuracy of 99% on everything"\n'  # unclosed call
    assert _literal_strings(broken), (
        "a syntactically invalid cell returned no literals, which would let a "
        "hardcoded claim through whenever a cell fails to parse"
    )
