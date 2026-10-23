"""Helpers for the tests of the committed policy tables.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[1]


def load_script(module_name: str, filename: str) -> ModuleType:
    """Import ``scripts/<filename>`` as a module under ``module_name``."""
    spec = importlib.util.spec_from_file_location(module_name, REPO / "scripts" / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_file_matches_sources(folder: Path, name: str) -> None:
    """The file's size and SHA-256 equal the row ``SOURCES.md`` gives for it."""
    text = (folder / "SOURCES.md").read_text(encoding="utf-8")
    data = (folder / name).read_bytes()
    pattern = rf"\|\s*`{re.escape(name)}`\s*\|\s*([\d,]+)\s*\|\s*`([0-9a-f]{{64}})`"
    row = re.search(pattern, text)
    assert row, f"{name} has no row in SOURCES.md"
    assert int(row.group(1).replace(",", "")) == len(data)
    assert row.group(2) == hashlib.sha256(data).hexdigest()
