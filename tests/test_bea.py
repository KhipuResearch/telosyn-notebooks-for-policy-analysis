"""The BEA fetcher's contract, and the credential it hands back to you.

BEA is the only source in this corpus that ECHOES the submitted credential
inside the response body, at ``BEAAPI.Request.RequestParam[i].ParameterValue``.
``redact`` cannot help there: it scrubs strings on their way into an error
message, and a parsed payload is not a string -- it becomes a DataFrame, a
``print``, and a stored notebook output as structured data no display filter
sees. The key therefore has to be removed from the document itself, before
anything else reads it.

The strongest test here is not "is the key absent" but
``test_the_provenance_hash_does_not_depend_on_whose_key_was_used``: two analysts
with different credentials must produce the same hash for the same data. A
provenance record nobody else can reproduce is not a provenance record, and that
property holds only if the stripping happened before hashing.

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
    BEA_ACPSA_LINE_ROLES,
    BEA_ACPSA_TABLES,
    BEARequestError,
    EmptyResultError,
    SchemaError,
    fetch_bea_regional,
    redact,
)

#: Shaped like a real key, and deliberately not one.
STUB_KEY = "AAAAAAAA-1111-2222-3333-BBBBBBBBBBBB"


@pytest.fixture(autouse=True)
def _stub_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sources, "load_key", lambda name, **_: STUB_KEY)


class _Response:
    def __init__(self, *, status: int = 200, body: bytes = b"",
                 content_type: str = "application/json") -> None:
        self.status_code = status
        self.content = body
        self.headers = {"content-type": content_type}

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", "replace")

    def json(self) -> Any:
        return json.loads(self.text)


class _Session:
    def __init__(self, response: _Response) -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []

    def get(self, *args: Any, **kwargs: Any) -> _Response:
        self.calls.append(kwargs.get("params", {}))
        return self._response


def _envelope(data: list[dict[str, Any]], *, key: str = STUB_KEY) -> _Response:
    """A BEA payload shaped exactly as the live API returns one, echo included."""
    return _Response(body=json.dumps({
        "BEAAPI": {
            "Request": {"RequestParam": [
                {"ParameterName": "USERID", "ParameterValue": key},
                {"ParameterName": "METHOD", "ParameterValue": "GETDATA"},
            ]},
            "Results": {"Data": data},
        }
    }).encode())


ROW = {
    "Code": "SAACARTSVA-10", "GeoFips": "00000", "GeoName": "United States",
    "TimePeriod": "2023", "CL_UNIT": "Thousands of dollars", "UNIT_MULT": "3",
    "DataValue": "1,169,836,000",
}


# --------------------------------------------------------------------------- #
# The credential
# --------------------------------------------------------------------------- #


def test_the_echoed_credential_never_reaches_the_frame() -> None:
    frame, _ = fetch_bea_regional(
        table="SAACArtsVA", line_code="10", year=2023, geo_fips="00000",
        session=_Session(_envelope([ROW])),
    )
    rendered = frame.to_json() + frame.to_string()
    assert STUB_KEY not in rendered


def test_the_echoed_credential_never_reaches_provenance() -> None:
    _, prov = fetch_bea_regional(
        table="SAACArtsVA", line_code="10", year=2023, geo_fips="00000",
        session=_Session(_envelope([ROW])),
    )
    assert STUB_KEY not in " ".join(prov.notes)
    assert STUB_KEY not in json.dumps(prov.__dict__, default=str)


def test_the_provenance_hash_does_not_depend_on_whose_key_was_used() -> None:
    """Two analysts, two credentials, one hash -- or the record is unverifiable.

    This is the test that proves the stripping happens BEFORE hashing rather
    than merely before display. Hashing the raw body would give every analyst a
    different digest for identical data, and nobody could ever check anybody's.
    """
    hashes = set()
    for key in (STUB_KEY, "ZZZZZZZZ-9999-8888-7777-CCCCCCCCCCCC"):
        _, prov = fetch_bea_regional(
            table="SAACArtsVA", line_code="10", year=2023, geo_fips="00000",
            session=_Session(_envelope([ROW], key=key)),
        )
        hashes.add(prov.content_sha256)
    assert len(hashes) == 1, (
        "the payload hash differs between credentials, so the Request block was "
        "still present when the hash was taken"
    )


def test_provenance_says_the_echo_was_stripped() -> None:
    _, prov = fetch_bea_regional(
        table="SAACArtsVA", line_code="10", year=2023, geo_fips="00000",
        session=_Session(_envelope([ROW])),
    )
    joined = " ".join(prov.notes)
    assert "echoed" in joined and "removed before parsing" in joined


def test_redact_covers_the_outbound_url_too() -> None:
    """The echo is one direction. A requests exception carries the other."""
    assert STUB_KEY not in redact(
        f"HTTPSConnectionPool: /api/data?UserID={STUB_KEY}&method=GetData"
    )


# --------------------------------------------------------------------------- #
# HTTP 200 is not success
# --------------------------------------------------------------------------- #


def test_an_error_envelope_arriving_as_http_200_is_an_error() -> None:
    """BEA reports a rejected request with status 200 and no Results key.

    Code that branches on the status line reads this as an empty result set and
    carries on with zero rows, which is how a rejected query becomes a finding
    that a region has no arts economy.
    """
    body = json.dumps({"BEAAPI": {"Error": {
        "APIErrorCode": "41",
        "APIErrorDescription": "Multiple parameter values were supplied for a parameter that only allows single values.",
        "ErrorDetail": {"Description": "Only one geography can be submitted when LineCode value= ALL"},
    }}}).encode()
    with pytest.raises(BEARequestError) as exc:
        fetch_bea_regional(table="SAACArtsVA", line_code="10", year=2023,
                           session=_Session(_Response(body=body)))
    message = str(exc.value)
    assert "HTTP 200" in message and "41" in message


def test_zero_rows_is_refused_rather_than_returned_empty() -> None:
    """GeoFIPS='US' is accepted and returns no rows. That is not a region with
    no arts production; it is an unrecognised geography reported as success."""
    with pytest.raises(EmptyResultError, match="not an empty region"):
        fetch_bea_regional(table="SAACArtsVA", line_code="10", year=2023,
                           geo_fips="US", session=_Session(_envelope([])))


def test_a_missing_column_raises_rather_than_producing_a_short_frame() -> None:
    row = {k: v for k, v in ROW.items() if k != "CL_UNIT"}
    with pytest.raises(SchemaError, match="CL_UNIT"):
        fetch_bea_regional(table="SAACArtsVA", line_code="10", year=2023,
                           session=_Session(_envelope([row])))


# --------------------------------------------------------------------------- #
# The vintage, which BEA does not give you
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("year", ["LAST5", "ALL", "", "20233", "2023-2024", None])
def test_year_must_be_a_single_four_digit_year(year: object) -> None:
    """BEA's own default is LAST5 -- a window that moves with each release.

    The Regional endpoint takes four parameters and none of them is a vintage,
    so the year in the request is the only thing a stored artifact can cite.
    """
    with pytest.raises(ValueError, match="four-digit year"):
        fetch_bea_regional(table="SAACArtsVA", line_code="10", year=year,  # type: ignore[arg-type]
                           session=_Session(_envelope([ROW])))


def test_the_year_is_sent_explicitly() -> None:
    session = _Session(_envelope([ROW]))
    fetch_bea_regional(table="SAACArtsVA", line_code="10", year=2019, session=session)
    assert session.calls[0]["Year"] == "2019"


def test_provenance_records_that_no_past_vintage_is_retrievable() -> None:
    _, prov = fetch_bea_regional(table="SAACArtsVA", line_code="10", year=2023,
                                 session=_Session(_envelope([ROW])))
    assert "no vintage parameter" in " ".join(prov.notes)


# --------------------------------------------------------------------------- #
# The line-code hierarchy the API does not express
# --------------------------------------------------------------------------- #


def test_line_one_is_labelled_as_the_whole_economy() -> None:
    """The single most expensive misreading available in this table.

    Line 1 is total value added of the entire state economy. A reader who takes
    "the first line" as "the first arts line" reports GDP as arts output.
    """
    assert "WHOLE ECONOMY" in BEA_ACPSA_LINE_ROLES["1"]
    assert "not an arts line" in BEA_ACPSA_LINE_ROLES["1"]


def test_roles_are_attached_to_every_row() -> None:
    rows = [
        {**ROW, "Code": "SAACARTSVA-1", "DataValue": "27,567,300,000"},
        {**ROW, "Code": "SAACARTSVA-10", "DataValue": "1,169,836,000"},
        {**ROW, "Code": "SAACARTSVA-111", "DataValue": "17,800,000"},
    ]
    frame, _ = fetch_bea_regional(table="SAACArtsVA", line_code="ALL", year=2023,
                                  geo_fips="00000", session=_Session(_envelope(rows)))
    roles = dict(zip(frame["LineCode"], frame["LineRole"]))
    assert "WHOLE ECONOMY" in roles["1"]
    assert roles["10"].startswith("subject total")
    assert roles["111"] == "leaf"


def test_an_all_line_request_warns_that_the_column_is_not_summable() -> None:
    frame, prov = fetch_bea_regional(table="SAACArtsVA", line_code="ALL", year=2023,
                                     geo_fips="00000", session=_Session(_envelope([ROW])))
    joined = " ".join(prov.notes)
    assert "NOT A FLAT LIST" in joined
    assert "many times the true total" in joined
    assert "LineRole" in frame.columns


def test_all_across_many_geographies_is_refused_before_the_request() -> None:
    """BEA answers that combination with an error envelope. Catching it here
    keeps a reader from debugging an API error that is really an argument bug."""
    session = _Session(_envelope([ROW]))
    with pytest.raises(ValueError, match="only for a single geography"):
        fetch_bea_regional(table="SAACArtsVA", line_code="ALL", year=2023,
                           geo_fips="STATE", session=session)
    assert not session.calls, "the request must not be sent"


# --------------------------------------------------------------------------- #
# Scope
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("table", ["SAGDP1", "CAINC1", "", "saacartsva"])
def test_only_acpsa_tables_are_served(table: str) -> None:
    """Other Regional tables have different caveats. Letting them through this
    function would attach ACPSA's provenance notes to numbers they do not describe."""
    with pytest.raises(ValueError, match="not an ACPSA table"):
        fetch_bea_regional(table=table, line_code="10", year=2023,
                           session=_Session(_envelope([ROW])))


def test_every_served_table_has_a_description() -> None:
    assert set(BEA_ACPSA_TABLES) >= {"SAACArtsVA", "SAACArtsComp", "SAACArtsEmp", "SAACVALQ"}
    assert all(BEA_ACPSA_TABLES.values())


def test_a_comma_grouped_value_parses_and_the_text_is_kept() -> None:
    """The text column is what makes a non-numeric footnote visible later."""
    frame, _ = fetch_bea_regional(table="SAACArtsVA", line_code="10", year=2023,
                                  session=_Session(_envelope([ROW])))
    assert float(frame["DataValue"].iloc[0]) == 1_169_836_000.0
    assert frame["DataValueText"].iloc[0] == "1,169,836,000"


def test_an_unparseable_value_is_nan_and_reported_not_silently_dropped() -> None:
    rows = [ROW, {**ROW, "Code": "SAACARTSVA-111", "DataValue": "(D)"}]
    frame, prov = fetch_bea_regional(table="SAACArtsVA", line_code="ALL", year=2023,
                                     geo_fips="00000", session=_Session(_envelope(rows)))
    assert pd.isna(frame["DataValue"].iloc[1])
    assert frame["DataValueText"].iloc[1] == "(D)"
    assert "(D)" in " ".join(prov.notes)
