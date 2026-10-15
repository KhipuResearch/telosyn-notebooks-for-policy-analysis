"""The FBI CDE client, and the difference between "no data" and "not today".

NIBRS reporting is voluntary, so the population a crime series covers is itself
a time series. This source publishes that coverage and normalises its rates by
it -- both of which are more than most publishers do -- and neither is enough,
because the covered subset is not a random sample of places and the sign of the
residual bias is not recoverable from the coverage figure.

The transport has its own hazard. The FBI backend behind api.usa.gov returns 503
intermittently and recovers within seconds, so one failed call says nothing about
whether data exists. A client that reads that as an empty result records an
absence of crime where there is only an absence of service.

No network: every test drives the argument contract or a canned payload.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import json
from typing import Any

import pandas as pd
import pytest

from krl_tutorials_data import sources
from krl_tutorials_data.sources import (
    CDEUpstreamUnavailable,
    EmptyResultError,
    FBI_CDE_COVERAGE_PATH,
    FBI_CDE_PERIOD_PATTERN,
    FBI_CDE_REGIME,
    ResponseShapeError,
    SchemaError,
    UpstreamError,
    fetch_fbi_cde_agencies,
    fetch_fbi_cde_summarized,
)


@pytest.fixture(autouse=True)
def _stub_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sources, "load_key", lambda name, **_: "stub-not-a-credential")


@pytest.fixture(autouse=True)
def _no_sleeping(monkeypatch: pytest.MonkeyPatch) -> None:
    """The retry loop backs off. These tests must not actually wait."""
    monkeypatch.setattr(sources.time, "sleep", lambda _seconds: None)


class _Response:
    def __init__(self, *, status: int = 200, body: bytes = b"",
                 headers: dict[str, str] | None = None) -> None:
        self.status_code = status
        self.content = body
        self.headers = {"content-type": "application/json", **(headers or {})}

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", "replace")

    def json(self) -> Any:
        return json.loads(self.text)


class _Session:
    def __init__(self, *responses: _Response) -> None:
        self._responses = list(responses)
        self.calls = 0

    def get(self, *args: Any, **kwargs: Any) -> _Response:
        self.calls += 1
        return self._responses[min(self.calls - 1, len(self._responses) - 1)]


def _summarized(**overrides: Any) -> _Response:
    months = ["01-2021", "02-2021"]
    doc: dict[str, Any] = {
        "offenses": {
            "rates": {"Pennsylvania Offenses": {"01-2021": 34.91, "02-2021": 33.0}},
            "actuals": {"Pennsylvania Offenses": {"01-2021": 1903, "02-2021": 1800}},
        },
        "populations": {
            "population": {"Pennsylvania": {"01-2021": 12_990_000, "02-2021": 12_990_000}},
            "participated_population": {"Pennsylvania": {"01-2021": 5_450_000, "02-2021": 5_454_000}},
        },
        "tooltips": {FBI_CDE_COVERAGE_PATH[1]: {"Pennsylvania": {"01-2021": 42.05, "02-2021": 42.0}}},
        "cde_properties": {"max_data_date": {"UCR": "09/2026"}},
    }
    doc.update(overrides)
    return _Response(body=json.dumps(doc).encode())


AGENCIES = _Response(body=json.dumps({
    "LEE": [
        {"ori": "PA0001", "agency_name": "Lee PD", "is_nibrs": True,
         "nibrs_start_date": "2021-03-01", "agency_type_name": "City"},
        {"ori": "PA0002", "agency_name": "Bath PD", "is_nibrs": False,
         "nibrs_start_date": None, "agency_type_name": "City"},
    ]
}).encode())


# --------------------------------------------------------------------------- #
# 503 is not an absence
# --------------------------------------------------------------------------- #


def test_a_persistent_503_is_an_outage_not_an_empty_result() -> None:
    """The distinction this whole client exists for.

    Recording "no violent crime reported in Pennsylvania" because a gateway
    blinked is a fabricated finding, and it looks exactly like a real one.
    """
    session = _Session(_Response(status=503, body=b"upstream connect error"))
    with pytest.raises(CDEUpstreamUnavailable) as exc:
        fetch_fbi_cde_summarized(state="PA", offense="violent-crime",
                                 from_month="01-2021", to_month="02-2021",
                                 session=session)
    message = str(exc.value)
    assert "do NOT record it as an absence" in message
    assert "says nothing about whether the data exists" in message


def test_a_503_is_retried_and_a_later_success_is_returned() -> None:
    """Observed live: the same endpoint failed, then answered seconds later."""
    session = _Session(_Response(status=503), _Response(status=503), _summarized())
    frame, _ = fetch_fbi_cde_summarized(state="PA", offense="violent-crime",
                                        from_month="01-2021", to_month="02-2021",
                                        session=session)
    assert session.calls == 3
    assert len(frame) == 2


def test_a_404_is_not_retried_because_the_path_is_wrong() -> None:
    """Retrying a bad path shape wastes the budget that the real outage needs.

    Measured: /participation/state/VA and /estimate/state/VA/2016/2023 are 404,
    while /summarized/state/VA/violent-crime is 200. Both look like "no data".
    """
    session = _Session(_Response(status=404, body=b"<html>Not Found</html>"))
    with pytest.raises(UpstreamError, match="path shape is wrong"):
        fetch_fbi_cde_summarized(state="PA", offense="violent-crime",
                                 from_month="01-2021", to_month="02-2021",
                                 session=session)
    assert session.calls == 1


def test_the_outage_error_is_still_inside_the_error_hierarchy() -> None:
    assert issubclass(CDEUpstreamUnavailable, UpstreamError)
    assert issubclass(CDEUpstreamUnavailable, sources.DataAccessError)


# --------------------------------------------------------------------------- #
# The period format
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("period", ["2021", "2021-01", "13-2021", "00-2021", "1-2021", ""])
def test_a_period_that_is_not_month_year_is_refused_before_the_request(period: str) -> None:
    """CDE rejects a bare year with HTTP 400 and a date-format complaint.

    Catching it here turns a remote 400 into a local message that names the
    format, which is the difference between a five-second fix and a session
    spent suspecting the credential.
    """
    session = _Session(_summarized())
    with pytest.raises(ValueError, match="MM-YYYY"):
        fetch_fbi_cde_summarized(state="PA", offense="violent-crime",
                                 from_month=period, to_month="12-2021", session=session)
    assert session.calls == 0


@pytest.mark.parametrize("period", ["01-2021", "12-1999", "09-2026"])
def test_valid_periods_pass_the_pattern(period: str) -> None:
    assert FBI_CDE_PERIOD_PATTERN.match(period)


@pytest.mark.parametrize("state", ["Pennsylvania", "P", "pa1", "", "USA"])
def test_a_bad_state_abbreviation_is_refused(state: str) -> None:
    with pytest.raises(ValueError, match="two-letter abbreviation"):
        fetch_fbi_cde_summarized(state=state, offense="violent-crime",
                                 from_month="01-2021", to_month="02-2021",
                                 session=_Session(_summarized()))


# --------------------------------------------------------------------------- #
# Coverage, and what it does not promise
# --------------------------------------------------------------------------- #


def test_the_coverage_series_is_lifted_out_of_the_tooltips_block() -> None:
    """It is a data series and it is filed under chart furniture.

    Nobody looks for the variable that decides whether a crime series means
    anything inside a key called `tooltips`, which is why the path is pinned as
    a named constant rather than indexed inline.
    """
    assert FBI_CDE_COVERAGE_PATH == ("tooltips", "Percent of Population Coverage")
    frame, _ = fetch_fbi_cde_summarized(state="PA", offense="violent-crime",
                                        from_month="01-2021", to_month="02-2021",
                                        session=_Session(_summarized()))
    assert list(frame["coverage_pct"]) == [42.05, 42.0]


def test_both_candidate_denominators_are_returned_beside_the_published_rate() -> None:
    """So the reader can check which one the publisher used instead of trusting it.

    Measured on Pennsylvania and Florida: the published rate matches
    actual / participated_population to a mean absolute error of 0.002, against
    12.49 for actual / total population.
    """
    frame, _ = fetch_fbi_cde_summarized(state="PA", offense="violent-crime",
                                        from_month="01-2021", to_month="02-2021",
                                        session=_Session(_summarized()))
    assert {"population", "participated_population", "published_rate"} <= set(frame.columns)
    row = frame.iloc[0]
    from_participated = 100_000 * row["offenses"] / row["participated_population"]
    from_total = 100_000 * row["offenses"] / row["population"]
    assert abs(from_participated - row["published_rate"]) < 0.05
    assert abs(from_total - row["published_rate"]) > 5


def test_provenance_refuses_to_let_coverage_read_as_a_quality_guarantee() -> None:
    """Florida reports 99.78% coverage across a window in which 54 of 96 monthly
    offence counts are under 200 and many are exactly zero."""
    _, prov = fetch_fbi_cde_summarized(state="PA", offense="violent-crime",
                                       from_month="01-2021", to_month="02-2021",
                                       session=_Session(_summarized()))
    joined = " ".join(prov.notes)
    assert "COVERAGE IS NOT A QUALITY GUARANTEE" in joined
    assert "not a random sample of places" in joined
    assert FBI_CDE_REGIME in joined


def test_provenance_records_that_national_counts_are_not_served() -> None:
    _, prov = fetch_fbi_cde_summarized(state="PA", offense="violent-crime",
                                       from_month="01-2021", to_month="02-2021",
                                       session=_Session(_summarized()))
    assert "National actuals are not served" in " ".join(prov.notes)


def test_a_response_without_state_actuals_names_the_reason() -> None:
    doc = json.loads(_summarized().text)
    doc["offenses"]["actuals"] = {}
    with pytest.raises(SchemaError, match="National actuals are not served"):
        fetch_fbi_cde_summarized(state="PA", offense="violent-crime",
                                 from_month="01-2021", to_month="02-2021",
                                 session=_Session(_Response(body=json.dumps(doc).encode())))


def test_a_payload_without_an_offenses_block_raises() -> None:
    with pytest.raises(ResponseShapeError, match="no offenses block"):
        fetch_fbi_cde_summarized(state="PA", offense="violent-crime",
                                 from_month="01-2021", to_month="02-2021",
                                 session=_Session(_Response(body=b'{"tooltips": {}}')))


# --------------------------------------------------------------------------- #
# Agencies: the coverage variable at its source
# --------------------------------------------------------------------------- #


def test_agency_rows_carry_nibrs_status_and_join_year() -> None:
    frame, _ = fetch_fbi_cde_agencies(state="PA", session=_Session(AGENCIES))
    assert list(frame["is_nibrs"]) == [True, False]
    assert frame["nibrs_start_year"].iloc[0] == "2021"
    assert pd.isna(frame["nibrs_start_year"].iloc[1])


def test_provenance_says_a_non_reporting_agency_is_not_a_crimeless_one() -> None:
    """The inference this source most invites, and the one it cannot support."""
    _, prov = fetch_fbi_cde_agencies(state="PA", session=_Session(AGENCIES))
    joined = " ".join(prov.notes)
    assert "not an agency with no crime" in joined
    assert "has not joined" in joined
    assert "1 of 2" in joined


def test_an_empty_agency_map_raises_rather_than_returning_no_agencies() -> None:
    with pytest.raises(EmptyResultError, match="no agencies"):
        fetch_fbi_cde_agencies(state="PA", session=_Session(_Response(body=b'{"LEE": []}')))


def test_a_missing_agency_map_raises() -> None:
    with pytest.raises(ResponseShapeError, match="no agency map"):
        fetch_fbi_cde_agencies(state="PA", session=_Session(_Response(body=b"{}")))
