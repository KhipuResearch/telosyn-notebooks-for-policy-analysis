"""Contract tests for ``sources.fetch_cbo_workbook``.

CBO publishes dated, per-edition workbooks under ``cbo.gov/system/files/<yyyy-mm>/``. The client
fetches one named .xlsx, refuses any other host or file type, returns every sheet unparsed
(``header=None``) so the notebook, not the client, decides where a table starts, and pins the
payload by hash. The response is injected; no network is used.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import io
from typing import Any

import pandas as pd
import pytest

from krl_tutorials_data import sources
from krl_tutorials_data.sources import EmptyResultError, ResponseShapeError, UpstreamError

URL = "https://www.cbo.gov/system/files/2026-09/62761-supp-data.xlsx"


def _xlsx() -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        pd.DataFrame([["Table 1", None], ["Lowest quintile", 10.0], ["Highest quintile", 90.0]]).to_excel(
            xl, sheet_name="Table 1", header=False, index=False)
        pd.DataFrame([["x", 1]]).to_excel(xl, sheet_name="Notes", header=False, index=False)
    return buf.getvalue()


class _Response:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.status_code = status
        self.content = body
        self.headers: dict[str, str] = {"content-type": "application/vnd.openxmlformats"}


class _Session:  # pylint: disable=too-few-public-methods
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> _Response:
        self.calls.append({"url": url, **kwargs})
        return self.response


def test_every_sheet_is_returned_unparsed_with_the_hash_of_the_bytes() -> None:
    body = _xlsx()
    sheets, prov = sources.fetch_cbo_workbook(url=URL, session=_Session(_Response(body)))
    assert list(sheets) == ["Table 1", "Notes"]
    assert sheets["Table 1"].shape == (3, 2)
    assert sheets["Table 1"].iloc[1, 0] == "Lowest quintile"
    assert prov.content_sha256 == prov.hash_payload(body)
    assert prov.hash_basis == "response-bytes"
    assert prov.endpoint == URL
    assert prov.source_name == "Congressional Budget Office"
    assert any("2 sheet" in n and "Table 1" in n for n in prov.notes)


def test_refuses_other_hosts_and_file_types_before_any_request() -> None:
    session = _Session(_Response(_xlsx()))
    for bad in (
        "https://example.com/system/files/2026-09/62761-supp-data.xlsx",
        "http://www.cbo.gov/system/files/2026-09/62761-supp-data.xlsx",
        "https://www.cbo.gov/system/files/2026-09/62761-additional-data-for-researchers.zip",
        "https://www.cbo.gov/publication/62761",
        "https://www.cbo.gov.evil.example/system/files/2026-09/x.xlsx",
    ):
        with pytest.raises(ValueError):
            sources.fetch_cbo_workbook(url=bad, session=session)
    assert session.calls == []


def test_http_error_empty_body_and_non_workbook_raise() -> None:
    with pytest.raises(UpstreamError, match="404"):
        sources.fetch_cbo_workbook(url=URL, session=_Session(_Response(b"", 404)))
    with pytest.raises(EmptyResultError):
        sources.fetch_cbo_workbook(url=URL, session=_Session(_Response(b"")))
    with pytest.raises(ResponseShapeError):
        sources.fetch_cbo_workbook(url=URL, session=_Session(_Response(b"<html>not a workbook")))


def test_user_agent_is_the_neutral_one() -> None:
    session = _Session(_Response(_xlsx()))
    sources.fetch_cbo_workbook(url=URL, session=session)
    assert session.calls[0]["headers"]["User-Agent"] == "telosyn-notebooks/1.0"
