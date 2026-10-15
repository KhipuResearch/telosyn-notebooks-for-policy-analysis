"""CDC open data, and a flat table holding several classifications at once.

CDC WONDER refuses automated query. data.cdc.gov's Socrata API does not, and
serves much of the same NCHS material -- so this is the route, and it is not a
WONDER substitute, because WONDER's custom cross-tabulations are not here.

Two hazards the client exists to stop:

1.  **Socrata's default page is 1,000 rows.** A client that does not pass
    `$limit` returns a truncated table that looks complete. This one passes it
    explicitly, and refuses to return a result that exactly fills the limit --
    the one case where full and truncated are indistinguishable.

2.  **`stub_name` is not a stratum, it is a classification scheme.** The NCHS
    suicide table packs twelve of them into one column, of which one is the
    total, and two use incompatible race-coding standards that overlap in the
    changeover year. Any aggregate over the estimate column without filtering
    `stub_name` counts the same deaths repeatedly.

No network: every test drives the argument contract or a canned payload.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import json
from typing import Any

import pandas as pd
import pytest

from krl_tutorials_data.sources import (
    CDC_SOCRATA_MAX_LIMIT,
    EmptyResultError,
    NCHS_SINGLE_RACE_MARKER,
    NCHS_SUICIDE_DATASET,
    NCHS_TOTAL_STUB,
    ResponseShapeError,
    UpstreamError,
    describe_stub_levels,
    fetch_cdc_socrata,
)

ROWS = [
    {"year": "2018", "stub_name": "Total", "estimate": "14.2"},
    {"year": "2018", "stub_name": "Sex", "estimate": "22.8"},
    {"year": "2018", "stub_name": "Sex and race", "estimate": "20.1"},
    {"year": "2018", "stub_name": f"Sex and race {NCHS_SINGLE_RACE_MARKER}", "estimate": "20.4"},
    {"year": "2017", "stub_name": "Total", "estimate": "14.0"},
]


class _Response:
    def __init__(self, *, status: int = 200, body: Any = None) -> None:
        self.status_code = status
        self.content = json.dumps(body if body is not None else ROWS).encode()
        self.headers = {"content-type": "application/json"}

    @property
    def text(self) -> str:
        return self.content.decode()

    def json(self) -> Any:
        return json.loads(self.content)


class _Session:
    def __init__(self, response: _Response | None = None) -> None:
        self._response = response or _Response()
        self.calls: list[dict] = []

    def get(self, url: str, **kwargs: Any) -> _Response:
        self.calls.append({"url": url, **kwargs})
        return self._response


# --------------------------------------------------------------------------
# Argument contract
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["suicide", "9j2vjamp", "9J2V-JAMP", "9j2v-jam", ""])
def test_a_non_socrata_identifier_is_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="Socrata dataset identifier"):
        fetch_cdc_socrata(dataset=bad, session=_Session())


@pytest.mark.parametrize("bad", [0, -1, CDC_SOCRATA_MAX_LIMIT + 1])
def test_an_out_of_range_limit_is_refused(bad: int) -> None:
    with pytest.raises(ValueError, match="offset"):
        fetch_cdc_socrata(dataset=NCHS_SUICIDE_DATASET, limit=bad, session=_Session())


def test_the_limit_is_sent_explicitly_and_defaults_to_the_maximum() -> None:
    """Socrata's default is 1,000 rows; taking it is how a table silently truncates."""
    session = _Session()
    fetch_cdc_socrata(dataset=NCHS_SUICIDE_DATASET, session=session)
    params = session.calls[0]["params"]
    assert params["$limit"] == str(CDC_SOCRATA_MAX_LIMIT)


def test_a_where_clause_reaches_the_query_and_is_recorded() -> None:
    session = _Session()
    _, prov = fetch_cdc_socrata(
        dataset=NCHS_SUICIDE_DATASET, where="year > '2000'", session=session
    )
    assert session.calls[0]["params"]["$where"] == "year > '2000'"
    assert prov.variables["where"] == "year > '2000'"


def test_no_where_clause_sends_none() -> None:
    session = _Session()
    fetch_cdc_socrata(dataset=NCHS_SUICIDE_DATASET, session=session)
    assert "$where" not in session.calls[0]["params"]


# --------------------------------------------------------------------------
# Truncation, which is the transport hazard
# --------------------------------------------------------------------------

def test_a_result_that_exactly_fills_the_limit_is_refused() -> None:
    """The one case where complete and truncated look identical."""
    session = _Session(_Response(body=ROWS[:3]))
    with pytest.raises(ResponseShapeError) as exc:
        fetch_cdc_socrata(dataset=NCHS_SUICIDE_DATASET, limit=3, session=session)
    message = str(exc.value)
    assert "may be truncated" in message
    assert "$offset" in message


def test_a_result_under_the_limit_is_returned() -> None:
    frame, _ = fetch_cdc_socrata(dataset=NCHS_SUICIDE_DATASET, limit=10, session=_Session())
    assert len(frame) == len(ROWS)


def test_an_empty_result_is_named_as_one() -> None:
    with pytest.raises(EmptyResultError):
        fetch_cdc_socrata(dataset=NCHS_SUICIDE_DATASET, session=_Session(_Response(body=[])))


def test_a_non_list_payload_is_a_shape_error() -> None:
    with pytest.raises(ResponseShapeError, match="not a row list"):
        fetch_cdc_socrata(
            dataset=NCHS_SUICIDE_DATASET, session=_Session(_Response(body={"error": True}))
        )


def test_a_non_200_is_an_upstream_error() -> None:
    with pytest.raises(UpstreamError, match="HTTP 503"):
        fetch_cdc_socrata(
            dataset=NCHS_SUICIDE_DATASET, session=_Session(_Response(status=503))
        )


def test_provenance_says_this_is_not_a_wonder_substitute() -> None:
    _, prov = fetch_cdc_socrata(dataset=NCHS_SUICIDE_DATASET, session=_Session())
    joined = " ".join(prov.notes)
    assert "WONDER refuses automated query" in joined
    assert "not a WONDER substitute" in joined
    assert "default is 1,000 rows" in joined


# --------------------------------------------------------------------------
# The stub column, which is the analytical hazard
# --------------------------------------------------------------------------

def test_every_classification_level_is_listed_separately() -> None:
    levels = describe_stub_levels(pd.DataFrame(ROWS))
    assert set(levels["stub_name"]) == {
        "Total", "Sex", "Sex and race", f"Sex and race {NCHS_SINGLE_RACE_MARKER}",
    }


def test_the_single_race_standard_is_flagged() -> None:
    levels = describe_stub_levels(pd.DataFrame(ROWS)).set_index("stub_name")
    assert bool(levels.loc[f"Sex and race {NCHS_SINGLE_RACE_MARKER}", "single_race"])
    assert not bool(levels.loc["Sex and race", "single_race"])


def test_the_two_race_standards_are_not_merged() -> None:
    """They describe the same deaths under incompatible coding. Merging them is the bug."""
    levels = describe_stub_levels(pd.DataFrame(ROWS))
    names = set(levels["stub_name"])
    assert "Sex and race" in names and f"Sex and race {NCHS_SINGLE_RACE_MARKER}" in names


def test_year_span_is_reported_per_level() -> None:
    levels = describe_stub_levels(pd.DataFrame(ROWS)).set_index("stub_name")
    assert int(levels.loc["Total", "first_year"]) == 2017
    assert int(levels.loc["Total", "last_year"]) == 2018
    assert int(levels.loc["Sex", "first_year"]) == 2018


def test_a_frame_without_a_stub_column_is_refused() -> None:
    with pytest.raises(ValueError, match="not a column"):
        describe_stub_levels(pd.DataFrame({"year": ["2018"]}))


def test_the_total_stub_is_one_level_among_many_not_the_table() -> None:
    frame = pd.DataFrame(ROWS)
    totals = frame[frame["stub_name"] == NCHS_TOTAL_STUB]
    assert len(totals) == 2
    assert len(totals) < len(frame), (
        "if the total were most of the table there would be no aggregation hazard"
    )
