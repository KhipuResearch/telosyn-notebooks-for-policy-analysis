"""Contract tests for ``sources.fetch_fns_pdf``, ``sources.fetch_irs_eitc_participation`` and ``html_tables``.

Responses are injected; no network is used. FNS serves its files through a redirect to a second host, which
``requests`` follows; the client checks the final bytes are a PDF and records the URL it was asked for.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

from typing import Any

import pytest

from krl_tutorials_data import html_tables, sources
from krl_tutorials_data.sources import EmptyResultError, ResponseShapeError, UpstreamError

PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


class _Response:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.status_code = status
        self.content = body
        self.text = body.decode("utf-8", "replace")
        self.headers: dict[str, str] = {}


class _Session:  # pylint: disable=too-few-public-methods
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> _Response:
        self.calls.append({"url": url, **kwargs})
        return self.response


def test_fns_pdf_returns_the_bytes_and_a_hash_of_them() -> None:
    session = _Session(_Response(PDF))
    body, prov = sources.fetch_fns_pdf(path="resource-files/snap2019reaching.pdf", vintage="FY 2019", session=session)
    assert body == PDF
    assert prov.content_sha256 == prov.hash_payload(PDF)
    assert prov.endpoint == "https://www.fna.usda.gov/sites/default/files/resource-files/snap2019reaching.pdf"
    assert prov.pinned is False and prov.vintage == "FY 2019"
    assert session.calls[0]["headers"]["User-Agent"] == "telosyn-notebooks/1.0"


@pytest.mark.parametrize("bad", [
    "../etc/passwd.pdf", "resource-files/x.zip", "https://evil.example/x.pdf", "resource-files/a/b.pdf",
    "resource-files/x.pdf?x=1", "other/x.pdf", "",
])
def test_fns_pdf_refuses_other_paths_before_any_request(bad: str) -> None:
    session = _Session(_Response(PDF))
    with pytest.raises(ValueError):
        sources.fetch_fns_pdf(path=bad, vintage="v", session=session)
    assert session.calls == []


def test_fns_pdf_errors() -> None:
    with pytest.raises(UpstreamError, match="404"):
        sources.fetch_fns_pdf(path="ops/x.pdf", vintage="v", session=_Session(_Response(b"", 404)))
    with pytest.raises(EmptyResultError):
        sources.fetch_fns_pdf(path="ops/x.pdf", vintage="v", session=_Session(_Response(b"")))
    with pytest.raises(ResponseShapeError, match="PDF"):
        sources.fetch_fns_pdf(path="ops/x.pdf", vintage="v", session=_Session(_Response(b"<html>no")))


HTML = """
<html><body><table><tr><th>other</th></tr><tr><td>1</td></tr></table>
<table>
 <thead><tr><th>Participation rate by state</th><th>Tax year 2022</th><th>Tax year 2021</th></tr></thead>
 <tbody>
  <tr><td>Alabama</td><td>80.5%</td><td>79.1%</td></tr>
  <tr><td> District&nbsp;of Columbia </td><td>73.6%</td><td>n/a</td></tr>
 </tbody></table></body></html>
"""


def test_html_tables_reads_every_table_with_normalised_cell_text() -> None:
    tables = html_tables.read_tables(HTML)
    assert len(tables) == 2
    assert tables[1][0] == ["Participation rate by state", "Tax year 2022", "Tax year 2021"]
    assert tables[1][2][0] == "District of Columbia"


def test_irs_table_is_numeric_and_hashed_over_its_content() -> None:
    session = _Session(_Response(HTML.encode()))
    frame, prov = sources.fetch_irs_eitc_participation(session=session)
    assert list(frame.columns) == ["state", "Tax year 2022", "Tax year 2021"]
    assert frame.loc[0, "Tax year 2022"] == 80.5
    assert frame["Tax year 2021"].isna().tolist() == [False, True]
    assert prov.hash_basis == "canonical-json" and prov.pinned is False
    other = HTML.replace("80.5%", "80.6%")
    _, prov2 = sources.fetch_irs_eitc_participation(session=_Session(_Response(other.encode())))
    assert prov2.content_sha256 != prov.content_sha256
    noisy = HTML.replace("<body>", "<body><!-- generated 12:00 -->")
    _, prov3 = sources.fetch_irs_eitc_participation(session=_Session(_Response(noisy.encode())))
    assert prov3.content_sha256 == prov.content_sha256


def test_irs_errors() -> None:
    with pytest.raises(UpstreamError, match="500"):
        sources.fetch_irs_eitc_participation(session=_Session(_Response(b"", 500)))
    with pytest.raises(EmptyResultError):
        sources.fetch_irs_eitc_participation(session=_Session(_Response(b"")))
    with pytest.raises(ResponseShapeError, match="Participation rate by state"):
        sources.fetch_irs_eitc_participation(session=_Session(_Response(b"<html><table><tr><th>x</th></tr></table></html>")))


class _Flaky:  # pylint: disable=too-few-public-methods
    """Answers with the given responses in order, then repeats the last."""

    def __init__(self, *responses: _Response) -> None:
        self.responses = list(responses)
        self.calls = 0

    def get(self, url: str, **kwargs: Any) -> _Response:
        r = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return r


def test_fns_pdf_retries_a_gateway_error_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sources, "_sleep", lambda s: None)
    session = _Flaky(_Response(b"", 502), _Response(b"", 503), _Response(PDF))
    body, _ = sources.fetch_fns_pdf(path="ops/x.pdf", vintage="v", session=session)
    assert body == PDF and session.calls == 3


def test_fns_pdf_gives_up_after_the_last_attempt_and_does_not_retry_a_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sources, "_sleep", lambda s: None)
    always = _Flaky(_Response(b"", 502))
    with pytest.raises(UpstreamError, match="502"):
        sources.fetch_fns_pdf(path="ops/x.pdf", vintage="v", session=always)
    assert always.calls == len(sources.FNS_RETRY_PAUSES)
    gone = _Flaky(_Response(b"", 404))
    with pytest.raises(UpstreamError, match="404"):
        sources.fetch_fns_pdf(path="ops/x.pdf", vintage="v", session=gone)
    assert gone.calls == 1


class _Redirected(_Response):
    """A response that arrived after following redirects, as requests reports it."""

    def __init__(self, body: bytes, final: str, hops: list[str]) -> None:
        super().__init__(body)
        self.url = final
        self.history = [type("H", (), {"url": u, "status_code": 302})() for u in hops]


def test_fns_pdf_records_the_final_url_and_each_hop_after_cross_host_redirects() -> None:
    final = "https://fna-example.z01.azurefd.us/sites/default/files/ops/x.pdf"
    hops = ["https://www.fna.usda.gov/sites/default/files/ops/x.pdf"]
    _, prov = sources.fetch_fns_pdf(path="ops/x.pdf", vintage="v", session=_Session(_Redirected(PDF, final, hops)))
    assert prov.endpoint == "https://www.fna.usda.gov/sites/default/files/ops/x.pdf"
    joined = " ".join(prov.notes)
    assert f"Final URL after redirects: {final}" in joined
    assert "Redirected from: " + hops[0] in joined


def test_fns_pdf_without_a_redirect_says_so() -> None:
    _, prov = sources.fetch_fns_pdf(path="ops/x.pdf", vintage="v", session=_Session(_Response(PDF)))
    assert any("No redirect" in n for n in prov.notes)


# --- review 4: what the publisher says about the file or page ------------------------------------------
class _Hdr(_Response):
    def __init__(self, body: bytes, headers: dict[str, str]) -> None:
        super().__init__(body)
        self.headers = headers


def test_fns_provenance_records_last_modified_etag_pdf_dates_and_the_former_address() -> None:
    body = PDF + b"/CreationDate (D:20230213100000-05'00') /ModDate (D:20230213101500-05'00')\n"
    session = _Session(_Hdr(body, {"last-modified": "Mon, 13 Feb 2023 15:25:10 GMT", "etag": '"ef7d8-5f49673e422ad"'}))
    _, prov = sources.fetch_fns_pdf(path="resource-files/snap2019reaching.pdf", vintage="v", session=session)
    text = " ".join(prov.notes)
    assert "Last-Modified: Mon, 13 Feb 2023 15:25:10 GMT" in text and 'ETag: "ef7d8-5f49673e422ad"' in text
    assert "PDF CreationDate D:20230213100000-05'00'" in text and "PDF ModDate D:20230213101500-05'00'" in text
    assert "https://www.fns.usda.gov/sites/default/files/resource-files/snap2019reaching.pdf" in text


def test_fns_provenance_says_so_when_the_headers_and_dates_are_absent() -> None:
    _, prov = sources.fetch_fns_pdf(path="ops/x.pdf", vintage="v", session=_Session(_Response(PDF)))
    text = " ".join(prov.notes)
    assert "No Last-Modified or ETag header" in text and "No PDF CreationDate" in text


def test_irs_provenance_records_the_raw_html_hash_and_the_page_review_date() -> None:
    html = HTML.replace("</body>", "<p>Page Last Reviewed or Updated: 19-Aug-2026</p></body>")
    _, prov = sources.fetch_irs_eitc_participation(session=_Session(_Response(html.encode())))
    text = " ".join(prov.notes)
    assert "Page Last Reviewed or Updated: 19-Aug-2026" in text
    import hashlib
    assert f"raw HTML SHA-256 {hashlib.sha256(html.encode()).hexdigest()}" in text
    _, prov2 = sources.fetch_irs_eitc_participation(session=_Session(_Response(HTML.encode())))
    assert "no 'Page Last Reviewed or Updated' date" in " ".join(prov2.notes)
