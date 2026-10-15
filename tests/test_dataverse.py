"""Harvard Dataverse, and the election returns that do not add up.

Two things distinguish this client from the corpus's other bulk-file readers.

**The publisher supplies the checksum.** Dataverse serves a manifest carrying a
dataset version, a release time and a per-file MD5 that the *publisher*
computed. A self-computed hash (the Zillow pin in D27) detects that our own copy
changed; this detects that the file was swapped. Both are useful and they are
not the same guarantee.

**Cleaning the data is the bug.** The ``candidate`` column carries ballot
dispositions -- OVERVOTES, UNDERVOTES, VOID -- alongside people, and
``totalvotes`` counts them in most states. Removing them, which is what a
careful analyst does first, takes the accounting identity from 661 of 663
state-years down to 625. So the client flags them and refuses to remove them,
and these tests pin that refusal.

No network: every test drives the argument contract or a canned payload.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd
import pytest

from krl_tutorials_data import sources
from krl_tutorials_data.sources import (
    ChecksumError,
    DATAVERSE_HEADERS,
    ELECTION_BALLOT_DISPOSITIONS,
    ELECTION_WRITE_IN_LABEL,
    EmptyResultError,
    MIT_PRESIDENT_DOI,
    MIT_PRESIDENT_FILE,
    ResponseShapeError,
    SchemaError,
    UpstreamError,
    fetch_dataverse_file,
    fetch_mit_president,
)

CSV = (
    "year,state,candidate,party_detailed,party_simplified,writein,"
    "candidatevotes,totalvotes,version\n"
    "2024,VERMONT,HARRIS KAMALA D.,DEMOCRAT,DEMOCRAT,False,100,160,2025-11-20\n"
    "2024,VERMONT,TRUMP DONALD J.,REPUBLICAN,REPUBLICAN,False,50,160,2025-11-20\n"
    "2024,VERMONT,UNDERVOTES,,OTHER,False,10,160,2025-11-20\n"
    "2024,VERMONT,WRITE-IN,NO PARTY,OTHER,True,5,160,2025-11-20\n"
).encode("utf-8")
CSV_MD5 = hashlib.md5(CSV, usedforsecurity=False).hexdigest()


class _Response:
    def __init__(self, *, status: int = 200, body: bytes = b"") -> None:
        self.status_code = status
        self.content = body
        self.headers = {"content-type": "application/json"}

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", "replace")

    def json(self) -> Any:
        return json.loads(self.content)


def _manifest(
    *, filename: str = MIT_PRESIDENT_FILE, md5: str | None = None,
    restricted: bool = False, files: list[dict] | None = None,
    checksum: bool = True,
) -> dict:
    entry = {
        "restricted": restricted,
        "dataFile": {
            "id": 13887042,
            "filename": filename,
            "filesize": len(CSV),
            **({"checksum": {"type": "MD5", "value": md5 or CSV_MD5}} if checksum else {}),
        },
    }
    return {
        "data": {
            "latestVersion": {
                "versionNumber": 10,
                "versionMinorNumber": 1,
                "releaseTime": "2026-09-04T16:15:49Z",
                "files": files if files is not None else [entry],
            }
        }
    }


class _Session:
    def __init__(self, manifest: dict | None = None, *, body: bytes = CSV,
                 metadata_status: int = 200, access_status: int = 200) -> None:
        self._manifest = manifest if manifest is not None else _manifest()
        self._body = body
        self._metadata_status = metadata_status
        self._access_status = access_status
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs: Any) -> _Response:
        self.calls.append((url, kwargs))
        if "/api/datasets/" in url:
            return _Response(
                status=self._metadata_status,
                body=json.dumps(self._manifest).encode("utf-8"),
            )
        return _Response(status=self._access_status, body=self._body)


# --------------------------------------------------------------------------
# The user agent, which is not cosmetic
# --------------------------------------------------------------------------

def test_every_dataverse_request_identifies_the_client() -> None:
    """Measured: this host answers 403 to the default requests UA and 200 to a named one."""
    session = _Session()
    fetch_dataverse_file(doi=MIT_PRESIDENT_DOI, filename=MIT_PRESIDENT_FILE, session=session)
    assert session.calls, "no request was made"
    for url, kwargs in session.calls:
        assert kwargs.get("headers") == DATAVERSE_HEADERS, (
            f"{url} went out without the identifying user agent"
        )
    assert "krl-tutorials" in DATAVERSE_HEADERS["User-Agent"]


def test_a_403_says_what_it_probably_means() -> None:
    session = _Session(metadata_status=403)
    with pytest.raises(UpstreamError, match="user agent"):
        fetch_dataverse_file(doi=MIT_PRESIDENT_DOI, filename=MIT_PRESIDENT_FILE, session=session)


# --------------------------------------------------------------------------
# Addressing, and the argument contract
# --------------------------------------------------------------------------

def test_a_doi_without_the_scheme_is_refused() -> None:
    with pytest.raises(ValueError, match="doi:"):
        fetch_dataverse_file(doi="10.7910/DVN/42MVDX", filename="x.csv", session=_Session())


def test_the_file_is_resolved_by_name_not_by_a_hardcoded_id() -> None:
    """Ids change between dataset versions; an id-addressed client eventually 404s."""
    manifest = _manifest()
    manifest["data"]["latestVersion"]["files"][0]["dataFile"]["id"] = 999_999
    session = _Session(manifest)
    fetch_dataverse_file(doi=MIT_PRESIDENT_DOI, filename=MIT_PRESIDENT_FILE, session=session)
    access = [url for url, _ in session.calls if "/api/access/datafile/" in url]
    assert access == [f"{sources.DATAVERSE_HOST}/api/access/datafile/999999"], (
        "the id must come from the manifest, not from the client"
    )


def test_a_missing_filename_lists_what_is_there() -> None:
    session = _Session(_manifest(filename="1976-2020-president.csv"))
    with pytest.raises(EmptyResultError) as exc:
        fetch_dataverse_file(
            doi=MIT_PRESIDENT_DOI, filename=MIT_PRESIDENT_FILE, session=session
        )
    message = str(exc.value)
    assert "1976-2020-president.csv" in message
    assert "renamed file is a revision" in message


def test_an_ambiguous_filename_is_refused_rather_than_guessed() -> None:
    entry = _manifest()["data"]["latestVersion"]["files"][0]
    session = _Session(_manifest(files=[entry, dict(entry)]))
    with pytest.raises(ResponseShapeError, match="does not identify a file"):
        fetch_dataverse_file(
            doi=MIT_PRESIDENT_DOI, filename=MIT_PRESIDENT_FILE, session=session
        )


def test_a_restricted_file_says_so_rather_than_failing_obscurely() -> None:
    session = _Session(_manifest(restricted=True))
    with pytest.raises(UpstreamError) as exc:
        fetch_dataverse_file(
            doi=MIT_PRESIDENT_DOI, filename=MIT_PRESIDENT_FILE, session=session
        )
    assert "property of the dataset, not a failure here" in str(exc.value)


def test_malformed_metadata_is_a_shape_error() -> None:
    with pytest.raises(ResponseShapeError, match="latestVersion"):
        fetch_dataverse_file(
            doi=MIT_PRESIDENT_DOI, filename=MIT_PRESIDENT_FILE,
            session=_Session({"data": {}}),
        )


# --------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------

def test_bytes_are_checked_against_the_publishers_own_checksum() -> None:
    session = _Session(body=CSV + b"tampered\n")
    with pytest.raises(ChecksumError) as exc:
        fetch_dataverse_file(
            doi=MIT_PRESIDENT_DOI, filename=MIT_PRESIDENT_FILE, session=session
        )
    assert "MD5 Dataverse publishes" in str(exc.value)


def test_a_caller_pin_catches_a_revision_the_manifest_agrees_with() -> None:
    """The manifest is consistent and the file has still changed underneath us."""
    other = b"year,state,candidate,party_detailed,party_simplified,writein,candidatevotes,totalvotes,version\n2024,VERMONT,X,,OTHER,False,1,1,2025-11-20\n"
    session = _Session(_manifest(md5=hashlib.md5(other, usedforsecurity=False).hexdigest()),
                       body=other)
    with pytest.raises(ChecksumError) as exc:
        fetch_dataverse_file(
            doi=MIT_PRESIDENT_DOI, filename=MIT_PRESIDENT_FILE,
            expected_md5=CSV_MD5, session=session,
        )
    message = str(exc.value)
    assert "not the pinned" in message
    assert "update the pin deliberately rather than removing it" in message


def test_an_unpinned_call_says_in_provenance_that_it_is_unpinned() -> None:
    _, prov = fetch_dataverse_file(
        doi=MIT_PRESIDENT_DOI, filename=MIT_PRESIDENT_FILE, session=_Session()
    )
    joined = " ".join(prov.notes)
    assert "No caller pin was supplied" in joined
    assert "pass expected_md5" in joined


def test_a_pinned_call_says_so() -> None:
    _, prov = fetch_dataverse_file(
        doi=MIT_PRESIDENT_DOI, filename=MIT_PRESIDENT_FILE,
        expected_md5=CSV_MD5, session=_Session(),
    )
    assert "any upstream revision raises" in " ".join(prov.notes)


def test_a_dataset_with_no_checksum_is_refused() -> None:
    session = _Session(_manifest(checksum=False))
    with pytest.raises(ResponseShapeError, match="nothing to"):
        fetch_dataverse_file(
            doi=MIT_PRESIDENT_DOI, filename=MIT_PRESIDENT_FILE, session=session
        )


def test_the_vintage_is_the_dataset_version_not_a_year() -> None:
    _, prov = fetch_dataverse_file(
        doi=MIT_PRESIDENT_DOI, filename=MIT_PRESIDENT_FILE, session=_Session()
    )
    assert prov.vintage == "dataset v10.1, released 2026-09-04T16:15:49Z"


def test_an_empty_body_is_an_empty_result_not_a_parse_error() -> None:
    session = _Session(_manifest(md5=hashlib.md5(b"", usedforsecurity=False).hexdigest()),
                       body=b"")
    with pytest.raises(EmptyResultError):
        fetch_dataverse_file(
            doi=MIT_PRESIDENT_DOI, filename=MIT_PRESIDENT_FILE, session=session
        )


# --------------------------------------------------------------------------
# The election-specific layer
# --------------------------------------------------------------------------

def test_ballot_dispositions_are_flagged() -> None:
    frame, _ = fetch_mit_president(session=_Session())
    flagged = frame.loc[frame["is_ballot_disposition"], "candidate"].tolist()
    assert flagged == ["UNDERVOTES"]


def test_ballot_dispositions_are_not_removed() -> None:
    """The refusal this client exists for.

    Removing them takes the published accounting identity from 661 of 663
    state-years to 625, because `totalvotes` counts them in most states.
    """
    frame, _ = fetch_mit_president(session=_Session())
    assert len(frame) == 4, "the flagged row must survive into the returned frame"
    assert frame["candidatevotes"].sum() == 165


def test_write_in_is_not_treated_as_a_disposition() -> None:
    """It aggregates real votes for real people. The others are ballots that made none."""
    assert ELECTION_WRITE_IN_LABEL not in ELECTION_BALLOT_DISPOSITIONS
    frame, _ = fetch_mit_president(session=_Session())
    write_in = frame[frame["candidate"] == ELECTION_WRITE_IN_LABEL]
    assert len(write_in) == 1
    assert not bool(write_in["is_ballot_disposition"].iloc[0])


def test_the_flag_is_case_and_whitespace_insensitive() -> None:
    body = CSV.replace(b"UNDERVOTES", b"  undervotes  ")
    session = _Session(_manifest(md5=hashlib.md5(body, usedforsecurity=False).hexdigest()),
                       body=body)
    frame, _ = fetch_mit_president(session=session)
    assert int(frame["is_ballot_disposition"].sum()) == 1


@pytest.mark.parametrize(
    "missing", ["year", "state", "candidate", "candidatevotes", "totalvotes", "version"]
)
def test_a_missing_load_bearing_column_is_named(missing: str) -> None:
    header, *rows = CSV.decode().strip().split("\n")
    index = header.split(",").index(missing)
    drop = lambda line: ",".join(  # noqa: E731
        part for i, part in enumerate(line.split(",")) if i != index
    )
    body = ("\n".join([drop(header)] + [drop(r) for r in rows]) + "\n").encode()
    session = _Session(_manifest(md5=hashlib.md5(body, usedforsecurity=False).hexdigest()),
                       body=body)
    with pytest.raises(SchemaError, match=missing):
        fetch_mit_president(session=session)


def test_provenance_names_the_regime_and_every_trap() -> None:
    _, prov = fetch_mit_president(session=_Session())
    joined = " ".join(prov.notes)
    assert "ADMINISTRATIVE ENUMERATION" in joined
    assert "not a sample" in joined and "no margin of error" in joined
    assert "FLAGGED and NOT removed" in joined
    assert "breaks the accounting identity rather than restoring it" in joined
    assert "party_simplified" in joined and "OTHER" in joined
    assert prov.source_name == "MIT Election Data and Science Lab"


def test_provenance_counts_the_vintages_inside_one_download() -> None:
    body = CSV.replace(b"2025-11-20\n2024,VERMONT,UNDERVOTES", b"20210113\n2024,VERMONT,UNDERVOTES")
    session = _Session(_manifest(md5=hashlib.md5(body, usedforsecurity=False).hexdigest()),
                       body=body)
    _, prov = fetch_mit_president(session=session)
    joined = " ".join(prov.notes)
    assert "2 distinct values in one file" in joined
    assert "A single download is not a single vintage" in joined
