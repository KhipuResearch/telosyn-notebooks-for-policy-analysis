"""Contract tests for ``sources.fetch_epa_ria_pdf``: one EPA document, size checked before the body, cached outside the repository, with the digest the caller expects.

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
    def __init__(self, body: bytes = b"", status: int = 200, headers: dict[str, str] | None = None, url: str = URL) -> None:
        self.status_code, self.content, self.headers = status, body, headers or {}
        self.history: list[Any] = []
        self.url = url
        self.chunks_read = 0

    def iter_content(self, chunk_size: int = 1 << 20):
        for start in range(0, len(self.content), max(1, chunk_size // 1024)):    # small chunks so tests can see an early abort
            self.chunks_read += 1
            yield self.content[start:start + max(1, chunk_size // 1024)]


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


def test_returns_a_cached_path_and_a_record_with_the_digest_size_and_last_modified(tmp_path: Path) -> None:
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


def test_a_redirect_to_another_host_is_refused_for_the_head_and_for_the_body(tmp_path: Path) -> None:
    elsewhere = "https://evil.example/x.pdf"
    head_off = _Session(_Response(b"", 200, {"content-length": str(len(PDF))}, url=elsewhere), _Response(PDF))
    with pytest.raises(sources.ResponseShapeError, match="redirect"):
        sources.fetch_epa_ria_pdf(url=URL, expected_bytes=len(PDF), cache_dir=tmp_path, session=head_off)
    assert [c[0] for c in head_off.calls] == ["HEAD"]
    body_off = _Session(_Response(b"", 200, {"content-length": str(len(PDF))}), _Response(PDF, url=elsewhere))
    with pytest.raises(sources.ResponseShapeError, match="redirect"):
        sources.fetch_epa_ria_pdf(url=URL, expected_bytes=len(PDF), cache_dir=tmp_path, session=body_off)
    assert list(tmp_path.iterdir()) == []


def test_a_body_longer_than_the_approved_size_is_aborted_before_it_is_all_read(tmp_path: Path) -> None:
    big = PDF + b"x" * 50_000
    get = _Response(big)
    session = _Session(_Response(b"", 200, {"content-length": str(len(PDF))}), get)
    with pytest.raises(sources.SizeMismatchError):
        sources.fetch_epa_ria_pdf(url=URL, expected_bytes=len(PDF), cache_dir=tmp_path, session=session)
    assert get.chunks_read < len(big) // 100 and list(tmp_path.iterdir()) == []


def test_the_expected_digest_is_checked_on_a_fresh_fetch_and_on_a_cache_hit(tmp_path: Path) -> None:
    good = hashlib.sha256(PDF).hexdigest()
    sources.fetch_epa_ria_pdf(url=URL, expected_bytes=len(PDF), cache_dir=tmp_path, session=_session(), expected_sha256=good)
    again = _session()
    path, _ = sources.fetch_epa_ria_pdf(url=URL, expected_bytes=len(PDF), cache_dir=tmp_path, session=again, expected_sha256=good)
    assert [c[0] for c in again.calls] == ["HEAD"] and path.exists()            # a verified cache hit needs no body request
    other = tmp_path / "other"
    with pytest.raises(sources.ChecksumError):
        sources.fetch_epa_ria_pdf(url=URL, expected_bytes=len(PDF), cache_dir=other, session=_session(), expected_sha256="0" * 64)
    assert not other.exists() or list(other.iterdir()) == []
    # a cached file whose digest differs from the expected one is not trusted: the body is fetched again and then checked
    (tmp_path / URL.rsplit("/", 1)[-1]).write_bytes(b"%PDF-1.7\n" + b"y" * (len(PDF) - 9))
    refetch = _session()
    sources.fetch_epa_ria_pdf(url=URL, expected_bytes=len(PDF), cache_dir=tmp_path, session=refetch, expected_sha256=good)
    assert [c[0] for c in refetch.calls] == ["HEAD", "GET"]
