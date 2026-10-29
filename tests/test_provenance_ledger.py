"""Known-answer tests for the fetch-layer run ledger (F12 redesign, REVIEW-4 item 5).

Every ``fetch_*`` function appends a line to the notebook's ledger before it raises as well as after it succeeds, with a
status (ok / failed) and whether the data came from a cache; a notebook that stops on a rule calls ``ledger_stop`` before it
raises. A line carries the plan chain in force (set once with ``use_ledger``). Nothing is appended when no ledger is in use.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from krl_tutorials_data import provenance as pv
from krl_tutorials_data import sources


def _prov(tag: str = "x") -> pv.DataProvenance:
    return pv.DataProvenance.build(source_name="s", dataset="d", vintage="v", endpoint="e", variables={}, payload=tag.encode(),
                                   row_count=1, column_count=1)


@pytest.fixture
def ledger(tmp_path: Path):
    plan, a1 = tmp_path / "plan.md", tmp_path / "a1.md"
    plan.write_text("plan", encoding="utf-8")
    a1.write_text("amend", encoding="utf-8")
    folder = tmp_path / "provenance"
    folder.mkdir()
    chain = pv.use_ledger(folder / "_runs.jsonl", plan, a1)
    yield folder / "_runs.jsonl", chain
    pv.stop_ledger()


def lines(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def test_use_ledger_returns_the_chain_of_the_plan_and_amendments(ledger) -> None:
    path, chain = ledger
    d = [hashlib.sha256(b).hexdigest() for b in (b"plan", b"amend")]
    assert chain == pv.pap_chain(d)


def test_a_wrapped_fetcher_appends_an_ok_line_with_the_chain_and_the_payload_digest(ledger) -> None:
    path, chain = ledger

    @pv.ledgered
    def fetch_thing():
        return [1], _prov("payload")

    out = fetch_thing()
    assert out[0] == [1]
    (line,) = lines(path)
    assert line["kind"] == "fetch" and line["fetcher"] == "fetch_thing" and line["status"] == "ok" and line["cache_hit"] is False
    assert line["content_sha256"] == _prov("payload").content_sha256 and line["pap_chain_sha256"] == chain
    assert line["retrieved_utc"]


def test_a_fetcher_that_raises_leaves_a_failed_line_before_the_error_propagates(ledger) -> None:
    path, chain = ledger

    @pv.ledgered
    def fetch_broken():
        raise sources.UpstreamError("HTTP 502")

    with pytest.raises(sources.UpstreamError):
        fetch_broken()
    (line,) = lines(path)
    assert line["status"] == "failed" and line["content_sha256"] is None and line["error"] == "UpstreamError"
    assert line["pap_chain_sha256"] == chain


def test_cache_hit_is_reported_when_the_fetcher_says_so(ledger) -> None:
    path, _ = ledger

    @pv.ledgered
    def fetch_cached():
        pv.ledger_flag(cache_hit=True)
        return None, _prov()

    fetch_cached()
    assert lines(path)[0]["cache_hit"] is True
    fetch_cached()
    assert [x["cache_hit"] for x in lines(path)] == [True, True]


def test_flags_do_not_leak_from_one_call_to_the_next(ledger) -> None:
    path, _ = ledger
    calls = iter([True, False])

    @pv.ledgered
    def fetch_sometimes():
        if next(calls):
            pv.ledger_flag(cache_hit=True)
        return None, _prov()

    fetch_sometimes()
    fetch_sometimes()
    assert [x["cache_hit"] for x in lines(path)] == [True, False]


def test_ledger_stop_appends_a_stopped_line_with_the_reason(ledger) -> None:
    path, chain = ledger
    pv.ledger_stop("withheld share 1.36% exceeds 1%")
    (line,) = lines(path)
    assert line["kind"] == "stop" and line["status"] == "stopped" and "1.36%" in line["reason"] and line["pap_chain_sha256"] == chain


def test_without_a_ledger_in_use_nothing_is_written_and_the_call_still_works(tmp_path: Path) -> None:
    pv.stop_ledger()

    @pv.ledgered
    def fetch_plain():
        return 5, _prov()

    assert fetch_plain()[0] == 5
    pv.ledger_stop("nothing to write to")
    assert not list(tmp_path.rglob("_runs.jsonl"))


def test_write_adds_a_record_line_with_the_status_ok(ledger) -> None:
    path, chain = ledger
    prov = _prov().with_pap_chain(path.parent / ".." / "plan.md")
    prov.write(path.parent / "r.json")
    rec = [x for x in lines(path) if x["kind"] == "record"]
    assert rec and rec[0]["record"] == "r.json" and rec[0]["status"] == "ok"


def test_every_fetch_function_in_sources_is_ledgered() -> None:
    names = [n for n in dir(sources) if n.startswith("fetch_") and callable(getattr(sources, n))]
    assert names and all(getattr(getattr(sources, n), "__ledgered__", False) for n in names), names
