"""A bulk file inside the repository is recorded by its repository-relative path.

The relative path was computed against the package's grandparent, which is ``src/`` in this layout, so a file
under ``data/`` was always recorded as an absolute path naming the machine that ran the notebook.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from krl_tutorials_data.connectors import BulkFileSource, frame_from_bulk_file

REPO_ROOT = Path(__file__).resolve().parent.parent


def _source(path: Path) -> BulkFileSource:
    return BulkFileSource(path=path, publisher="p", dataset="d", vintage="v", retrieved_on=date(2026, 1, 1))


def test_a_file_under_the_repository_is_recorded_relative_to_its_root() -> None:
    file = REPO_ROOT / "data" / "cbo" / "62761-supp-data.xlsx"
    _, prov = frame_from_bulk_file(_source(file), lambda p: pd.DataFrame({"a": [1]}))
    assert prov.endpoint == "file://data/cbo/62761-supp-data.xlsx"


def test_a_file_outside_the_repository_keeps_its_absolute_path(tmp_path: Path) -> None:
    file = tmp_path / "x.csv"
    file.write_text("a\n1\n", encoding="utf-8")
    _, prov = frame_from_bulk_file(_source(file), lambda p: pd.read_csv(p))
    assert prov.endpoint == f"file://{file.resolve()}"


def test_the_recorded_digest_is_the_digest_of_the_file_bytes(tmp_path: Path) -> None:
    import hashlib
    file = tmp_path / "x.csv"
    file.write_bytes(b"a,b\n1,2\n")
    _, prov = frame_from_bulk_file(_source(file), lambda p: pd.read_csv(p))
    assert prov.content_sha256 == hashlib.sha256(b"a,b\n1,2\n").hexdigest()
    assert prov.hash_basis == "response-bytes"
