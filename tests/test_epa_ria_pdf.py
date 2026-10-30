"""Contract tests for ``sources.fetch_epa_ria_pdf``: one pinned EPA document, size checked before the body, cached outside the repository.

Responses are injected; no network is used.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from krl_tutorials_data import sources
from krl_tutorials_data.sources import EmptyResultError, ResponseShapeError, UpstreamError

URL = "https://www.epa.gov/system/files/documents/2024-10/508_lcri_final_ea_10-21-2024.pdf"
PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


class _Response:
    def __init__(self, body: bytes = b"", status: int = 200, headers: dict[str, str] | None = None) -> None:
        self.status_code, self.content, self.headers = status, body, headers or {}
        self.history: list[Any] = []
        self.url = URL


class _Session:
    def __init__(self, head: _Response, get: _Response) -> None:
        self.head_response, self.get_response = head, get
        self.calls: list[tuple[str, str]] = []

    def head(self, url: str, **kwargs: Any) -> _Response:
        self.calls.append(("HEAD", url))
        return self.head_response

    def get(self, url: str, **kwargs: Any) -> _Response:
        self.calls.append(("GET", url))
        return self.get_response


def _session(size: int | None = None, body: bytes = PDF, status: int = 200) -> _Session:
    headers = {"content-length": str(len(body) if size is None else size), "last-modified": "Thu, 24 Oct 2024 18:07:44 GMT"}
    return _Session(_Response(b"", 200, headers), _Response(body, status))


def test_returns_a_cached_path_and_a_pinned_record_with_the_digest_size_and_last_modified(tmp_path: Path) -> None:
    session = _session()
    path, prov = sources.fetch_epa_ria_pdf(url=URL, expected_bytes=len(PDF), cache_dir=tmp_path, session=session)
    assert path.read_bytes() == PDF and path.parent == tmp_path
    assert prov.content_sha256 == hashlib.sha256(PDF).hexdigest() and prov.pinned is False
    assert prov.endpoint == URL
    assert any("24 Oct 2024" in n for n in prov.notes) and any(str(len(PDF)) in n.replace(",", "") for n in prov.notes)
    assert [c[0] for c in session.calls] == ["HEAD", "GET"]


def test_a_size_that_differs_stops_before_the_body_is_fetched(tmp_path: Path) -> None:
    session = _session(size=len(PDF) + 1)
    with pytest.raises(sources.SizeMismatchError, match=str(len(PDF) + 1)):
        sources.fetch_epa_ria_pdf(url=URL, expected_bytes=len(PDF), cache_dir=tmp_path, session=session)
    assert [c[0] for c in session.calls] == ["HEAD"] and list(tmp_path.iterdir()) == []


def test_a_body_whose_length_differs_from_the_header_is_refused_and_not_cached(tmp_path: Path) -> None:
    session = _session(size=len(PDF), body=PDF + b"x")
    with pytest.raises(sources.SizeMismatchError):
        sources.fetch_epa_ria_pdf(url=URL, expected_bytes=len(PDF), cache_dir=tmp_path, session=session)
    assert list(tmp_path.iterdir()) == []


def test_a_cached_file_of_the_right_size_is_reused_without_a_body_request(tmp_path: Path) -> None:
    sources.fetch_epa_ria_pdf(url=URL, expected_bytes=len(PDF), cache_dir=tmp_path, session=_session())
    again = _session()
    path, prov = sources.fetch_epa_ria_pdf(url=URL, expected_bytes=len(PDF), cache_dir=tmp_path, session=again)
    assert [c[0] for c in again.calls] == ["HEAD"] and prov.content_sha256 == hashlib.sha256(PDF).hexdigest() and path.exists()


@pytest.mark.parametrize("bad", [
    "http://www.epa.gov/system/files/documents/2024-10/x.pdf",
    "https://evil.example/system/files/documents/2024-10/x.pdf",
    "https://www.epa.gov/system/files/documents/2024-10/x.zip",
    "https://www.epa.gov/system/files/documents/2024-10/../x.pdf",
    "https://www.epa.gov/other/x.pdf",
    "https://www.epa.gov/system/files/documents/2024-10/x.pdf?a=1",
    "",
])
def test_other_urls_are_refused_before_any_request(bad: str, tmp_path: Path) -> None:
    session = _session()
    with pytest.raises(ValueError):
        sources.fetch_epa_ria_pdf(url=bad, expected_bytes=len(PDF), cache_dir=tmp_path, session=session)
    assert session.calls == []


def test_a_cache_directory_inside_a_git_working_tree_is_refused(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    inner = tmp_path / "cache"
    session = _session()
    with pytest.raises(ValueError, match="repository"):
        sources.fetch_epa_ria_pdf(url=URL, expected_bytes=len(PDF), cache_dir=inner, session=session)
    assert session.calls == []


def test_errors(tmp_path: Path) -> None:
    with pytest.raises(UpstreamError, match="404"):
        sources.fetch_epa_ria_pdf(url=URL, expected_bytes=len(PDF), cache_dir=tmp_path,
                                  session=_Session(_Response(b"", 404), _Response(PDF)))
    with pytest.raises(ResponseShapeError, match="content-length"):
        sources.fetch_epa_ria_pdf(url=URL, expected_bytes=len(PDF), cache_dir=tmp_path,
                                  session=_Session(_Response(b"", 200, {}), _Response(PDF)))
    with pytest.raises(ResponseShapeError, match="PDF"):
        sources.fetch_epa_ria_pdf(url=URL, expected_bytes=len(b"<html>no"), cache_dir=tmp_path, session=_session(body=b"<html>no"))
    with pytest.raises(EmptyResultError):
        sources.fetch_epa_ria_pdf(url=URL, expected_bytes=0, cache_dir=tmp_path, session=_session(body=b""))
