"""Contract tests for ``sources.fetch_acs_pums``.

The function reads person-level records from the Census API and must return only
weighted cell counts. These tests inject the response, so no network and no
credential is used, and they pin every way the aggregate-only promise could be
broken: a row-level return, a cell small enough to identify a person, a key that
survives into an error message, a digest that depends on row order.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import ast
import inspect
import json
from typing import Any

import numpy as np
import pandas as pd
import pytest
import requests
from hypothesis import given, settings
from hypothesis import strategies as st

from krl_tutorials_data import sources
from krl_tutorials_data.sources import (
    RangeError,
    ResponseShapeError,
    SchemaError,
    UpstreamError,
)

KEY = "stub-census_api_key-not-a-credential"


@pytest.fixture(autouse=True)
def _stub_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lookup is stubbed so the test measures the fetcher, not the machine's keys."""
    monkeypatch.setattr(sources, "load_key", lambda name, **_: KEY)


class _Response:
    """The minimum of ``requests.Response`` the fetcher touches."""

    def __init__(self, rows: list[list[Any]] | None = None, *, status: int = 200,
                 body: bytes | None = None) -> None:
        """Init."""
        self.status_code = status
        self.content = body if body is not None else json.dumps(rows).encode()
        self.headers = {"content-type": "application/json"}

    @property
    def text(self) -> str:
        """Body as text."""
        return self.content.decode()

    def json(self) -> Any:
        """Body as JSON."""
        return json.loads(self.text)


class _Session:  # pylint: disable=too-few-public-methods
    """Answers every GET with one canned response and records the request."""

    def __init__(self, response: _Response | Exception) -> None:
        """Init."""
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> _Response:
        """Record, then answer or raise."""
        self.calls.append({"url": url, **kwargs})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


HEADER = ["AGEP", "HICOV", "PWGTP", "state"]
VARIABLES = {"AGEP": "Age", "HICOV": "Health insurance coverage recode"}


def _rows() -> list[list[Any]]:
    """6 records at 64/covered, 5 at 65/covered, 2 at 65/uncovered (a small cell)."""
    out = [[64, 1, w, "51"] for w in (10, 20, 30, 40, 50, 60)]
    out += [[65, 1, 100, "51"] for _ in range(5)]
    out += [[65, 2, 7, "51"], [65, 2, 9, "51"]]
    return [HEADER, *[[str(v) if i < 3 else v for i, v in enumerate(r)] for r in out]]


def _fetch(rows: list[list[Any]] | None = None, **overrides: Any):
    """Fetch."""
    session = overrides.pop("session", None) or _Session(_Response(rows or _rows()))
    kwargs: dict[str, Any] = {
        "year": 2023, "variables": VARIABLES, "aggregate_by": ["AGEP", "HICOV"],
        "geography": "state:51", "session": session,
    }
    kwargs.update(overrides)
    kwargs.setdefault("min_cell_records", 5)
    return sources.fetch_acs_pums(**kwargs), session


def test_cells_are_weighted_sums_worked_by_hand() -> None:
    """64/covered: 10+20+30+40+50+60 = 210 over 6 records; 65/covered: 5 x 100 = 500."""
    (frame, _), _ = _fetch()
    assert list(frame.columns) == ["AGEP", "HICOV", "weighted_n", "n_records"]
    cells = {(r.AGEP, r.HICOV): (r.weighted_n, r.n_records) for r in frame.itertuples()}
    assert cells == {(64, 1): (210.0, 6), (65, 1): (500.0, 5)}


def test_a_cell_below_the_floor_is_withheld_and_accounted_for() -> None:
    """The 65/uncovered cell has 2 records (weights 7 + 9): never returned, always counted."""
    (frame, prov), _ = _fetch()
    assert (65, 2) not in {(r.AGEP, r.HICOV) for r in frame.itertuples()}
    assert frame.attrs["suppressed_cells"] == 1
    assert frame.attrs["suppressed_weighted_n"] == 16.0
    assert frame.attrs["min_cell_records"] == 5
    assert frame.attrs["suppressed_records"] == 2
    assert any("withheld" in n for n in prov.notes)


def test_every_cell_returned_meets_the_floor_and_the_floor_has_a_minimum() -> None:
    """Every cell returned meets the floor and the floor has a minimum."""
    (frame, _), _ = _fetch(min_cell_records=6)
    assert (frame["n_records"] >= 6).all()
    assert len(frame) == 1
    with pytest.raises(ValueError, match="at least 5"):
        _fetch(min_cell_records=4)


def test_no_person_level_column_is_ever_returned() -> None:
    """No person level column is ever returned."""
    (frame, _), _ = _fetch()
    assert "PWGTP" not in frame.columns and "state" not in frame.columns
    assert len(frame) <= 2


def test_the_request_names_a_state_and_carries_the_key_only_as_a_parameter() -> None:
    """The request names a state and carries the key only as a parameter."""
    (_, prov), session = _fetch()
    call = session.calls[0]
    assert call["url"].endswith("/2023/acs/acs1/pums")
    assert call["params"]["for"] == "state:51"
    assert call["params"]["get"] == "AGEP,HICOV,PWGTP"
    assert prov.request_params["key"] == "<redacted>"
    assert KEY not in json.dumps(prov.to_dict())


def test_the_digest_is_over_the_rows_and_ignores_their_order() -> None:
    """The digest is over the rows and ignores their order."""
    rows = _rows()
    shuffled = [rows[0], *reversed(rows[1:])]
    (f1, p1), _ = _fetch(rows)
    (f2, p2), _ = _fetch(shuffled)
    assert p1.content_sha256 == p2.content_sha256
    assert p1.hash_basis == "canonical-rows" and p1.pinned is True
    pd.testing.assert_frame_equal(f1, f2)
    changed = [rows[0], *rows[1:-1], ["65", "2", "9", "52"]]
    assert _fetch(changed)[0][1].content_sha256 != p1.content_sha256


def test_a_key_in_a_transport_error_is_redacted() -> None:
    """A key in a transport error is redacted."""
    boom = requests.ConnectionError(f"GET https://api.census.gov/data/2023/acs/acs1/pums?key={KEY}")
    with pytest.raises(UpstreamError) as exc:
        _fetch(session=_Session(boom))
    assert KEY not in str(exc.value)
    assert "REDACTED" in str(exc.value)


def test_a_key_in_an_html_error_page_is_redacted_from_the_message() -> None:
    """A key in an html error page is redacted from the message."""
    page = f"<html>invalid key={KEY}</html>".encode()
    session = _Session(_Response(body=page))
    session.response.headers["content-type"] = "text/html"
    with pytest.raises(ResponseShapeError) as exc:
        _fetch(session=session)
    assert KEY not in str(exc.value)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"geography": "state:*"}, "one state"),
        ({"variables": {}}, "At least one"),
        ({"aggregate_by": ["AGEP", "ESR"]}, "subset"),
        ({"aggregate_by": []}, "aggregate_by"),
        ({"weight": "AGEP"}, "weight"),
        ({"variables": {f"V{i}": "x" for i in range(60)}, "aggregate_by": ["V1"]}, "ceiling"),
    ],
)
def test_invalid_specifications_raise_before_any_request(kwargs: dict, message: str) -> None:
    """Invalid specifications raise before any request."""
    session = _Session(_Response(_rows()))
    with pytest.raises(ValueError, match=message):
        _fetch(session=session, **kwargs)
    assert not session.calls


def test_bad_responses_are_named_not_coerced() -> None:
    """Bad responses are named not coerced."""
    with pytest.raises(UpstreamError):
        _fetch(session=_Session(_Response(status=500, body=b"x")))
    with pytest.raises(ResponseShapeError, match="no data rows"):
        _fetch([HEADER])
    with pytest.raises(SchemaError, match="missing"):
        _fetch([["AGEP", "PWGTP", "state"], ["64", "10", "51"]])
    bad = _rows()
    bad[1][1] = "abc"
    with pytest.raises(SchemaError, match="non-numeric"):
        _fetch(bad)
    nonpos = _rows()
    nonpos[2][2] = "0"
    with pytest.raises(RangeError, match="weight"):
        _fetch(nonpos)


def test_a_missing_value_in_a_grouping_column_is_its_own_cell_not_dropped() -> None:
    """Not-in-universe values arrive as null; they are a category, never silently removed."""
    rows = [HEADER] + [["64", None, "10", "51"] for _ in range(6)] \
        + [["64", "1", "10", "51"] for _ in range(6)]
    (frame, _), _ = _fetch(rows)
    assert len(frame) == 2
    assert frame["HICOV"].isna().sum() == 1
    assert frame["weighted_n"].sum() == 120.0


@settings(max_examples=40, deadline=None)
@given(
    records=st.lists(
        st.tuples(st.integers(0, 3), st.integers(1, 2), st.integers(1, 500)),
        min_size=1, max_size=120,
    ),
    floor=st.integers(5, 12),
)
def test_property_returned_plus_withheld_weight_is_the_total_weight(
    records: list[tuple[int, int, int]], floor: int
) -> None:
    """Conservation: nothing is lost between the records and the report of what was withheld."""
    rows = [HEADER] + [[str(a), str(h), str(w), "51"] for a, h, w in records]
    (frame, _), _ = _fetch(rows, min_cell_records=floor)
    total = float(sum(w for _, _, w in records))
    got = float(frame["weighted_n"].sum()) + float(frame.attrs["suppressed_weighted_n"])
    assert got == pytest.approx(total)
    assert (frame["n_records"] >= floor).all()
    assert int(frame["n_records"].sum()) + int(frame.attrs["suppressed_records"]) == len(records)
    assert not np.isnan(frame["weighted_n"]).any()


def test_the_default_floor_is_ten_records_per_cell() -> None:
    """Called without a floor, the 6-record and 5-record cells are both withheld."""
    session = _Session(_Response(_rows()))
    frame, _ = sources.fetch_acs_pums(
        year=2023, variables=VARIABLES, aggregate_by=["AGEP", "HICOV"],
        geography="state:51", session=session,
    )
    assert frame.empty
    assert frame.attrs["suppressed_cells"] == 3 and frame.attrs["min_cell_records"] == 10


# --- there is no path to person rows -------------------------------------------
def test_the_public_function_has_no_argument_that_asks_for_rows() -> None:
    """The argument that once did is gone, and no name like it has replaced it."""
    names = set(inspect.signature(sources.fetch_acs_pums).parameters)
    assert names == {
        "year", "variables", "aggregate_by", "geography", "weight", "dataset",
        "min_cell_records", "session",
    }
    assert "return_rows" not in inspect.getsource(sources)


def test_the_person_frame_has_one_producer_and_one_reader() -> None:
    """Only fetch_acs_pums builds it, and only _pums_cells consumes it."""
    tree = ast.parse(inspect.getsource(sources))
    callers: dict[str, set[str]] = {"_pums_person_frame": set(), "_pums_cells": set()}
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        for call in [c for c in ast.walk(fn) if isinstance(c, ast.Call)]:
            if isinstance(call.func, ast.Name) and call.func.id in callers:
                callers[call.func.id].add(fn.name)
    assert callers == {"_pums_person_frame": {"fetch_acs_pums"}, "_pums_cells": {"fetch_acs_pums"}}


def _person(rows: list[tuple[float | None, float | None, float]]) -> pd.DataFrame:
    """Person."""
    return pd.DataFrame(rows, columns=["AGEP", "HICOV", "PWGTP"])


def test_the_private_aggregator_on_a_fixture_frame_by_hand() -> None:
    """Six records at (64, 1) weighing 10..60 sum to 210; five at (65, 1) at 100 sum to 500."""
    frame = _person(
        [(64, 1, w) for w in (10, 20, 30, 40, 50, 60)]
        + [(65, 1, 100)] * 5 + [(65, 2, 7), (65, 2, 9)]
    )
    cells, notes = sources._pums_cells(frame, ["AGEP", "HICOV"], "PWGTP", 5)
    assert cells.to_dict("records") == [
        {"AGEP": 64, "HICOV": 1, "weighted_n": 210.0, "n_records": 6},
        {"AGEP": 65, "HICOV": 1, "weighted_n": 500.0, "n_records": 5},
    ]
    assert list(cells.columns) == ["AGEP", "HICOV", "weighted_n", "n_records"]
    assert cells.attrs["suppressed_cells"] == 1 and cells.attrs["suppressed_weighted_n"] == 16.0
    assert any("No person-level row is returned" in n for n in notes)


def test_the_private_aggregator_keeps_a_missing_grouping_value_as_a_cell() -> None:
    """The private aggregator keeps a missing grouping value as a cell."""
    frame = _person([(64, None, 10)] * 5 + [(64, 1, 10)] * 5)
    cells, _ = sources._pums_cells(frame, ["AGEP", "HICOV"], "PWGTP", 5)
    assert len(cells) == 2 and cells["HICOV"].isna().sum() == 1
    assert cells["weighted_n"].sum() == 100.0


def test_the_private_aggregator_never_emits_the_weight_or_a_row_per_person() -> None:
    """The private aggregator never emits the weight or a row per person."""
    frame = _person([(a, 1, 3) for a in (1, 2, 3) for _ in range(5)])
    cells, _ = sources._pums_cells(frame, ["AGEP"], "PWGTP", 5)
    assert "PWGTP" not in cells.columns and len(cells) == 3 < len(frame)


def test_the_private_person_frame_refuses_what_it_cannot_make_numeric() -> None:
    """The private person frame refuses what it cannot make numeric."""
    raw = pd.DataFrame({"AGEP": ["64", "x"], "PWGTP": ["10", "20"]})
    with pytest.raises(SchemaError, match="non-numeric"):
        sources._pums_person_frame(raw, ["AGEP", "PWGTP"], "PWGTP")
    bad_weight = pd.DataFrame({"AGEP": ["64"], "PWGTP": ["0"]})
    with pytest.raises(RangeError, match="weight"):
        sources._pums_person_frame(bad_weight, ["AGEP", "PWGTP"], "PWGTP")
    good = pd.DataFrame({"AGEP": ["64", None], "PWGTP": ["10", "20"]})
    out = sources._pums_person_frame(good, ["AGEP", "PWGTP"], "PWGTP")
    assert out["AGEP"].isna().sum() == 1 and out["PWGTP"].tolist() == [10.0, 20.0]
