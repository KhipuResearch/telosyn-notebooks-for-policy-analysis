"""Known-answer tests for the plan chain a provenance record carries (card F12).

Hand arithmetic: the chain of the digests (a, b) is SHA-256 of the text "a\\nb"; of one digest d it is SHA-256 of "d".
A record written under a plan and two amendments lists the two amendments by file and digest, in order.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from krl_tutorials_data.provenance import DataProvenance, pap_chain


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _prov() -> DataProvenance:
    return DataProvenance.build(source_name="s", dataset="d", vintage="v", endpoint="e", variables={},
                                payload=b"x", row_count=1, column_count=1)


def test_the_chain_is_the_hash_of_the_newline_joined_digests() -> None:
    assert pap_chain(["a"]) == _sha(b"a")
    assert pap_chain(["a", "b"]) == _sha(b"a\nb")
    assert pap_chain(["a", "b"]) != pap_chain(["b", "a"])


def test_the_chain_rejects_nothing_to_chain() -> None:
    with pytest.raises(ValueError):
        pap_chain([])


def test_with_pap_chain_binds_the_plan_and_lists_amendments_in_order(tmp_path: Path) -> None:
    plan, a1, a2 = tmp_path / "plan.md", tmp_path / "a1.md", tmp_path / "a2.md"
    for f, text in ((plan, "p"), (a1, "one"), (a2, "two")):
        f.write_text(text, encoding="utf-8")
    prov = _prov().with_pap_chain(plan, a1, a2)
    assert prov.pap_sha256 == _sha(b"p")
    assert prov.pap_amendments == ({"file": "a1.md", "sha256": _sha(b"one")}, {"file": "a2.md", "sha256": _sha(b"two")})
    assert prov.pap_chain_sha256 == pap_chain([_sha(b"p"), _sha(b"one"), _sha(b"two")])


def test_with_pap_chain_of_the_plan_alone_has_no_amendments(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text("p", encoding="utf-8")
    prov = _prov().with_pap_chain(plan)
    assert prov.pap_amendments == () and prov.pap_chain_sha256 == _sha(_sha(b"p").encode())


def test_the_written_record_carries_the_chain_and_an_unbound_record_is_unchanged(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text("p", encoding="utf-8")
    out = _prov().with_pap_chain(plan).write(tmp_path / "provenance" / "r.json")
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["pap_chain_sha256"] == _sha(_sha(b"p").encode()) and doc["pap_amendments"] == [] and doc["pap_sha256"] == _sha(b"p")
    bare = json.loads(_prov().write(tmp_path / "provenance" / "bare.json").read_text(encoding="utf-8"))
    assert "pap_chain_sha256" not in bare and "pap_amendments" not in bare and "pap_sha256" not in bare


def test_every_write_into_a_provenance_folder_is_appended_to_the_run_ledger(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text("p", encoding="utf-8")
    prov = _prov().with_pap_chain(plan)
    prov.write(tmp_path / "provenance" / "r.json")
    prov.write(tmp_path / "provenance" / "r.json")          # the same name written again is two runs
    lines = [json.loads(x) for x in (tmp_path / "provenance" / "_runs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [x["record"] for x in lines] == ["r.json", "r.json"]
    assert lines[0]["content_sha256"] == prov.content_sha256 and lines[0]["pap_chain_sha256"] == _sha(_sha(b"p").encode())
    assert lines[0]["retrieved_utc"] == prov.retrieved_utc


def test_a_write_outside_a_provenance_folder_has_no_ledger(tmp_path: Path) -> None:
    _prov().write(tmp_path / "elsewhere" / "r.json")
    assert not (tmp_path / "elsewhere" / "_runs.jsonl").exists()
