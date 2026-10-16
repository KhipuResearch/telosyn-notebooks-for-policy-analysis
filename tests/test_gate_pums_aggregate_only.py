"""Gate -- no notebook may request person-level PUMS records.

``sources.fetch_acs_pums`` returns weighted cell counts. Its ``return_rows=True``
escape hatch returns person records and exists for tests of the aggregation
itself; the corpus does not print, store or write person rows (DIRECTIVE
standing order 6). A notebook source containing the argument fails here.

The planted-violation test proves the scan can fail: the corpus has no PUMS
notebook until C02, so without it this gate would pass on nothing.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import ast
import re

import pytest

from gate_support import Notebook

#: ``return_rows`` with a truthy value, however spaced, on any call.
_TEXTUAL = re.compile(r"return_rows\s*=\s*(?!False\b|0\b|None\b)\w")


def person_rows_requested(source: str) -> list[str]:
    """Return a description of each call that asks for person-level records.

    Parsed, not just grepped, so ``return_rows = flag`` and a ``**kwargs``
    spread that includes it are reported; text that merely mentions the name
    in a comment or string is not. Unparseable source falls back to the text
    scan rather than passing silently.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [m.group(0) for m in _TEXTUAL.finditer(source)]
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                falsy = isinstance(value, ast.Constant) and value.value in (False, 0, None)
                if isinstance(key, ast.Constant) and key.value == "return_rows" and not falsy:
                    found.append(f"line {node.lineno}: {{'return_rows': {ast.unparse(value)}}}")
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg == "return_rows" and not (
                isinstance(kw.value, ast.Constant) and kw.value.value in (False, 0, None)
            ):
                found.append(f"line {node.lineno}: return_rows={ast.unparse(kw.value)}")
            if kw.arg is None and "return_rows" in ast.unparse(kw.value):
                found.append(f"line {node.lineno}: **{ast.unparse(kw.value)}")
    return found


def test_no_notebook_requests_person_level_records(notebook: Notebook) -> None:
    """The corpus asks for aggregates only."""
    hits = person_rows_requested(notebook.code_source)
    assert not hits, (
        f"{notebook.path.name} asks for person-level PUMS records ({'; '.join(hits)}). "
        "Notebooks use fetch_acs_pums as an aggregator; remove return_rows."
    )


@pytest.mark.parametrize(
    "source",
    [
        "fetch_acs_pums(year=2023, return_rows=True)",
        "fetch_acs_pums(year=2023, return_rows = 1)",
        "flag = True\nfetch_acs_pums(year=2023, return_rows=flag)",
        "opts = {'return_rows': True}\nfetch_acs_pums(year=2023, **opts)",
        "fetch_acs_pums(year=2023, return_rows=True",  # does not parse: text fallback
    ],
)
def test_the_scan_catches_every_spelling(source: str) -> None:
    """Each spelling of the request is reported."""
    assert person_rows_requested(source)


@pytest.mark.parametrize(
    "source",
    [
        "fetch_acs_pums(year=2023)",
        "fetch_acs_pums(year=2023, return_rows=False)",
        "# return_rows=True is refused here\nfetch_acs_pums(year=2023)",
        "msg = 'never pass return_rows=True'\nfetch_acs_pums(year=2023)",
    ],
)
def test_the_scan_does_not_flag_compliant_source(source: str) -> None:
    """A comment, a string or an explicit False is not a request."""
    assert not person_rows_requested(source)
