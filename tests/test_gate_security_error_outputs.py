"""The credential gate reads stored error tracebacks, not only stream and data outputs.

An exception raised by a fetcher can echo the request it made; if that request carried a
key, the traceback is the one place it would be stored. The gate in ``test_gate_security``
walks every output type, and these tests hold it to that with synthetic notebooks.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

from pathlib import Path

import pytest
from gate_support import Cell, Notebook

import test_gate_security as gate


def _notebook(outputs: list) -> Notebook:
    """A one-cell notebook whose only code cell carries the given stored outputs."""
    cell = Cell(index=0, kind="code", source="x = 1", outputs=outputs, execution_count=1)
    return Notebook(path=Path("synthetic.ipynb"), metadata={}, cells=[cell])


def _error(*traceback_lines: str) -> dict:
    return {
        "output_type": "error",
        "ename": "HTTPError",
        "evalue": "400",
        "traceback": list(traceback_lines),
    }


def test_a_key_in_a_stored_error_traceback_fails_the_gate() -> None:
    """A key in a stored error traceback fails the gate."""
    fake = "api_key=" + "Z" * 20  # synthetic, not a credential
    notebook = _notebook([_error("HTTPError: 400 for url: https://example.test/q?" + fake)])
    with pytest.raises(AssertionError, match="credential-shaped material"):
        gate.test_no_key_material_in_outputs(notebook)


def test_a_key_in_the_error_value_is_not_the_only_place_looked_at() -> None:
    """A key on a later traceback line is found as well as one on the first."""
    notebook = _notebook([_error("Traceback", "  File x", "  token: " + "Q" * 24)])
    with pytest.raises(AssertionError, match="credential-shaped material"):
        gate.test_no_key_material_in_outputs(notebook)


def test_an_error_without_key_material_passes() -> None:
    """An error without key material passes."""
    notebook = _notebook([_error("HTTPError: 404 for url: https://example.test/q?year=2023")])
    gate.test_no_key_material_in_outputs(notebook)
