"""The provenance record can carry the digest of the plan it was retrieved under.

DECISIONS/0009 (amendment of 2026-10-15): precedence of a pre-analysis plan over
the data is proven by digest equality between the notebook, the plan and every
record, not by commit time. These tests pin the record's side of that binding.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from krl_tutorials_data.provenance import DataProvenance


def _record() -> DataProvenance:
    return DataProvenance.build(
        source_name="Fixture", dataset="table", vintage="2023",
        endpoint="https://example.test/data", variables={"X": "label"},
        payload=b"[[\"X\"],[\"1\"]]", row_count=1, column_count=1,
    )


def test_a_record_without_a_plan_is_unchanged() -> None:
    """Records written before the field existed keep the same key set."""
    doc = _record().to_dict()
    assert "pap_sha256" not in doc
    assert "Plan digest" not in _record().render()


def test_with_pap_hashes_the_file_bytes_not_a_typed_value(tmp_path: Path) -> None:
    """The digest comes from the plan on disk at the moment of binding."""
    plan = tmp_path / "plan.md"
    plan.write_bytes(b"outcome: employment\n")
    bound = _record().with_pap(plan)
    assert bound.pap_sha256 == hashlib.sha256(b"outcome: employment\n").hexdigest()
    assert bound.to_dict()["pap_sha256"] == bound.pap_sha256
    assert "Plan digest" in bound.render()


def test_binding_to_a_missing_plan_raises(tmp_path: Path) -> None:
    """Binding to nothing is not a weaker binding."""
    with pytest.raises(FileNotFoundError):
        _record().with_pap(tmp_path / "absent.md")


def test_the_original_record_is_not_mutated(tmp_path: Path) -> None:
    """The dataclass is frozen; binding returns a copy."""
    plan = tmp_path / "plan.md"
    plan.write_text("p\n")
    original = _record()
    original.with_pap(plan)
    assert original.pap_sha256 is None


def test_the_written_record_round_trips_and_matches_the_schema(tmp_path: Path) -> None:
    """The written file carries the digest, and the published schema names the field."""
    plan = tmp_path / "plan.md"
    plan.write_text("p\n")
    written = _record().with_pap(plan).write(tmp_path / "provenance" / "r.json")
    doc = json.loads(written.read_text(encoding="utf-8"))
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "data/schemas/provenance_record.json").read_text()
    )
    fields = {f["name"]: f for f in schema["fields"]}
    assert doc["pap_sha256"] in {hashlib.sha256(b"p\n").hexdigest()}
    assert set(doc) <= set(fields)
    assert "required" not in fields["pap_sha256"].get("constraints", {})
