"""Gate -- no notebook may reach for person-level PUMS records.

``sources.fetch_acs_pums`` returns weighted cell counts and has no argument that
asks for anything else (DECISIONS/0009, amendment of 2026-10-16). This gate keeps a
notebook from working around that: it may not name the removed ``return_rows``
argument, nor reach into the module's private PUMS helpers, which are where a person
frame exists. Both are structurally unreachable by the public function now; the gate
is the second lock.

The planted-violation tests prove the scan can fail: the corpus has no PUMS notebook
until C02, so without them this gate would pass on nothing.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import ast

import pytest

from gate_support import Notebook

#: Names a notebook must not use: the removed argument and the private helpers.
FORBIDDEN = ("return_rows", "_pums_person_frame", "_pums_cells", "_cps_person_frame", "_cps_cells", "_cps_attach_replicates")


def person_rows_requested(source: str) -> list[str]:
    """Return a description of each use of a forbidden name in ``source``.

    Parsed so a keyword, an attribute, a bare name, a dict key and a ``getattr``
    string are all reported; text that merely mentions a name in a comment is not.
    Unparseable source falls back to a text scan rather than passing silently.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [name for name in FORBIDDEN if name in source]
    found: list[str] = []
    for node in ast.walk(tree):
        hit = None
        if isinstance(node, ast.keyword) and node.arg in FORBIDDEN:
            hit = node.arg
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN:
            hit = node.attr
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN:
            hit = node.id
        elif isinstance(node, ast.alias) and node.name.split(".")[-1] in FORBIDDEN:
            hit = node.name
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in FORBIDDEN:
            hit = node.value
        if hit:
            found.append(f"line {getattr(node, 'lineno', '?')}: {hit}")
    return found


def test_no_notebook_reaches_for_person_level_records(notebook: Notebook) -> None:
    """The corpus asks for aggregates only."""
    hits = person_rows_requested(notebook.code_source)
    assert not hits, (
        f"{notebook.path.name} reaches for person-level PUMS records ({'; '.join(hits)}). "
        "Notebooks use fetch_acs_pums as an aggregator and nothing else."
    )


@pytest.mark.parametrize(
    "source",
    [
        "fetch_acs_pums(year=2023, return_rows=True)",
        "opts = {'return_rows': True}\nfetch_acs_pums(year=2023, **opts)",
        "from krl_tutorials_data.sources import _pums_cells",
        "import krl_tutorials_data.sources as s\ns._pums_person_frame(raw, [], 'PWGTP')",
        "getattr(sources, '_pums_cells')",
        "fetch_acs_pums(year=2023, return_rows=True",  # does not parse: text fallback
    ],
)
def test_the_scan_catches_every_spelling(source: str) -> None:
    """Each way of reaching for the person frame is reported."""
    assert person_rows_requested(source)


@pytest.mark.parametrize(
    "source",
    [
        "fetch_acs_pums(year=2023)",
        "# return_rows is gone\nfetch_acs_pums(year=2023)",
        "msg = 'there is no return_rows argument'\nfetch_acs_pums(year=2023)",
    ],
)
def test_the_scan_does_not_flag_compliant_source(source: str) -> None:
    """A comment or a sentence in a string is not a use."""
    assert not person_rows_requested(source)
