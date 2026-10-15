"""The EPA Toxics Release Inventory client, and what a self-reported number is.

TRI is not a measurement programme. Facilities above a reporting threshold
report their own releases, and EPA publishes what they report. The unusual and
valuable thing is that TRI makes each number say how it was produced: every
release record carries a basis-of-estimate code distinguishing continuous
monitoring from periodic monitoring from mass balance from a published emission
factor from best engineering judgment. Epistemic provenance arrives per record,
not per dataset.

Three hazards this module exists to stop:

1.  **Silent truncation.** Envirofacts caps a response at 10,000 rows and
    signals truncation in no way whatsoever. A query matching 12,069 rows
    returns a full, well-formed, complete-looking page that is missing 17% of
    the answer. The client asks the ``count`` endpoint first and refuses to
    return a frame that disagrees with it.

2.  **Mixed code schemes.** The basis vocabulary changed in reporting year 2007:
    ``M`` split into ``M1``/``M2`` and ``E`` into ``E1``/``E2``. Envirofacts
    returns oldest-first, so an unpinned sample is dominated by the retired
    scheme. ``reporting_year`` is therefore mandatory.

3.  **The range-code hole.** Small releases may be reported as a range code
    instead of a quantity. EPA documents the stored amount as the range
    midpoint; the API serves ``total_release`` as null while ``release_na``
    marks the release APPLICABLE. Summing ``total_release`` silently drops the
    small end -- a directional loss, not noise. The midpoint is reconstructed
    into its own column and never merged into the reported quantity.

No network: every test drives the argument contract or a canned payload.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd
import pytest

from krl_tutorials_data import sources
from krl_tutorials_data.sources import (
    EmptyResultError,
    ResponseShapeError,
    SchemaError,
    TRI_BASIS_CODES,
    TRI_CODE_SCHEME_CHANGE_YEAR,
    TRI_MEASURED_CODES,
    TRI_PAGE_LIMIT,
    TRI_RANGE_BANDS,
    TRI_REQUEST_ROWS,
    UpstreamError,
    fetch_tri_releases,
)


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


def _json(payload: Any, status: int = 200) -> _Response:
    return _Response(status=status, body=json.dumps(payload).encode("utf-8"))


def _row(
    *,
    basis: str | None = "M1",
    range_code: str | None = None,
    total: str | None = "100",
    na: str = "0",
    doc: str = "DOC1",
) -> dict[str, Any]:
    return {
        "doc_ctrl_num": doc,
        "environmental_medium": "AIR FUG",
        "release_basis_est_code": basis,
        "release_range_code": range_code,
        "total_release": total,
        "release_na": na,
    }


_RANGE = re.compile(r"/rows/(\d+):(\d+)/")


class _Session:
    """A faithful Envirofacts stub: honours the requested row range.

    Serving pages in call order regardless of the range asked for would let a
    client that computes its offsets wrongly still pass, which is precisely the
    bug class these tests exist to catch.
    """

    def __init__(self, count: int, rows: list[dict] | None = None,
                 *, count_response: _Response | None = None,
                 counts: dict[str, int] | None = None,
                 short_page_at: int | None = None,
                 overlong: bool = False) -> None:
        self._count_response = count_response
        self._count = count
        self._counts = counts or {}
        self._rows = list(rows or [])
        self._short_page_at = short_page_at
        self._overlong = overlong
        self.urls: list[str] = []

    def get(self, url: str, **_kwargs: Any) -> _Response:
        self.urls.append(url)
        if "/count/" in url:
            if self._count_response is not None:
                return self._count_response
            for fragment, value in self._counts.items():
                if fragment in url:
                    return _json([{"TOTALQUERYRESULTS": value}])
            return _json([{"TOTALQUERYRESULTS": self._count}])
        match = _RANGE.search(url)
        if match is None:
            return _json([])
        lo, hi = int(match.group(1)), int(match.group(2))
        if self._short_page_at is not None and lo >= self._short_page_at:
            return _json([])
        page = self._rows[lo : hi + 1]
        if self._overlong:
            page = page + [dict(page[-1], doc_ctrl_num="EXTRA")] if page else page
        return _json(page)


# --------------------------------------------------------------------------
# The argument contract
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["Virginia", "V", "51", "va1", "", "  "])
def test_a_state_that_is_not_a_two_letter_code_is_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="two-letter"):
        fetch_tri_releases(state=bad, reporting_year=2022, session=_Session(0))


def test_lowercase_and_padded_state_codes_are_accepted() -> None:
    """The caller's shift key is not a data-quality signal."""
    session = _Session(1, [_row()])
    frame, _ = fetch_tri_releases(state=" va ", reporting_year=2022, session=session)
    assert len(frame) == 1
    assert "/state_abbr/VA/" in session.urls[0]


@pytest.mark.parametrize("bad_year", [1986, 1900, 2101])
def test_a_year_outside_the_programme_is_refused(bad_year: int) -> None:
    with pytest.raises(ValueError, match="1987"):
        fetch_tri_releases(state="VA", reporting_year=bad_year, session=_Session(0))


def test_the_reporting_year_reaches_the_url() -> None:
    """Not pinning the year is the mixed-scheme bug. Prove the pin is applied."""
    session = _Session(1, [_row()])
    fetch_tri_releases(state="VA", reporting_year=2022, session=session)
    assert all("/reporting_year/2022/" in url for url in session.urls)


def test_a_nonpositive_row_budget_is_refused() -> None:
    with pytest.raises(ValueError, match="row_budget must be positive"):
        fetch_tri_releases(
            state="VA", reporting_year=2022, row_budget=0, session=_Session(5)
        )


# --------------------------------------------------------------------------
# Truncation: the hazard the count endpoint exists to close
# --------------------------------------------------------------------------

def test_the_count_endpoint_is_consulted_before_any_row_is_fetched() -> None:
    session = _Session(1, [_row()])
    fetch_tri_releases(state="VA", reporting_year=2022, session=session)
    assert "/count/" in session.urls[0], (
        "the row count must be known before paging begins; discovering it "
        "afterwards is how a full page gets mistaken for a full answer"
    )


def test_a_result_larger_than_one_page_is_paged_not_truncated() -> None:
    """The regression this module was written for.

    VA RY2022 matches 12,069 rows. A single unpaged request returns at most one
    page and looks complete. Assert the client assembles all of them, and that
    every offset it asks for is the one that follows the last row it holds.
    """
    total = TRI_REQUEST_ROWS * 2 + 69
    rows = [_row(doc=f"D{i}") for i in range(total)]
    session = _Session(total, rows)
    frame, prov = fetch_tri_releases(state="VA", reporting_year=2022, session=session)

    assert len(frame) == total
    assert prov.row_count == total
    assert list(frame["doc_ctrl_num"]) == [f"D{i}" for i in range(total)], (
        "paging must preserve order and drop nothing in the seams"
    )
    ranges = [tuple(map(int, m.groups()))
              for m in (_RANGE.search(u) for u in session.urls) if m]
    assert ranges == [(0, TRI_REQUEST_ROWS - 1),
                      (TRI_REQUEST_ROWS, 2 * TRI_REQUEST_ROWS - 1),
                      (2 * TRI_REQUEST_ROWS, total - 1)]


def test_the_request_size_stays_well_under_the_api_cap() -> None:
    """Measured, not assumed: Envirofacts does not return 10,000 rows in time.

    A 10,000-row request for VA RY2022 did not complete inside 175 seconds,
    while 2,000 rows returned in 11.4. Paging at the documented ceiling is
    paging into a timeout, so the client's request size is a separate constant
    and must stay below it.
    """
    assert TRI_REQUEST_ROWS < TRI_PAGE_LIMIT


def test_a_page_request_never_exceeds_the_declared_count() -> None:
    """Ask for exactly what is left, so a short final page is a real error."""
    total = TRI_REQUEST_ROWS + 3
    session = _Session(total, [_row(doc=f"D{i}") for i in range(total)])
    fetch_tri_releases(state="VA", reporting_year=2022, session=session)
    last = [u for u in session.urls if "/rows/" in u][-1]
    assert f"/rows/{TRI_REQUEST_ROWS}:{total - 1}/" in last


def test_a_short_page_raises_rather_than_returning_a_partial_frame() -> None:
    total = TRI_REQUEST_ROWS + 100
    session = _Session(total, [_row(doc=f"D{i}") for i in range(total)],
                       short_page_at=TRI_REQUEST_ROWS)
    with pytest.raises(UpstreamError, match="incomplete"):
        fetch_tri_releases(state="VA", reporting_year=2022, session=session)


def test_an_overlong_page_is_caught_as_a_shape_error() -> None:
    """More rows than declared means the query moved under us."""
    session = _Session(2, [_row(doc="A"), _row(doc="B")], overlong=True)
    with pytest.raises(ResponseShapeError, match="declared"):
        fetch_tri_releases(state="VA", reporting_year=2022, session=session)


def test_a_query_above_the_row_budget_raises_rather_than_truncating() -> None:
    with pytest.raises(ValueError) as exc:
        fetch_tri_releases(
            state="TX", reporting_year=2022, row_budget=100, session=_Session(5_000)
        )
    message = str(exc.value)
    assert "5,000" in message and "100" in message
    assert "truncated" in message, (
        "the error must say what it is protecting the caller from"
    )


def test_a_malformed_count_payload_is_a_shape_error() -> None:
    for payload in ([], [{"WRONG": 5}], [{"TOTALQUERYRESULTS": 1}, {"TOTALQUERYRESULTS": 2}]):
        session = _Session(0, count_response=_json(payload))
        with pytest.raises(ResponseShapeError, match="TOTALQUERYRESULTS"):
            fetch_tri_releases(state="VA", reporting_year=2022, session=session)


def test_a_nonnumeric_count_is_a_shape_error() -> None:
    session = _Session(0, count_response=_json([{"TOTALQUERYRESULTS": "many"}]))
    with pytest.raises(ResponseShapeError, match="not an integer"):
        fetch_tri_releases(state="VA", reporting_year=2022, session=session)


# --------------------------------------------------------------------------
# Absence
# --------------------------------------------------------------------------

def test_zero_matching_rows_raises_and_explains_what_zero_means() -> None:
    with pytest.raises(EmptyResultError) as exc:
        fetch_tri_releases(state="VA", reporting_year=2022, session=_Session(0))
    message = str(exc.value)
    assert "threshold" in message, (
        "TRI silence is a threshold artefact, and the error is the only place a "
        "reader is guaranteed to see that said"
    )
    assert "not that no releases occurred" in message


# --------------------------------------------------------------------------
# The basis code: epistemic provenance per record
# --------------------------------------------------------------------------

def test_every_documented_basis_code_is_translated() -> None:
    rows = [_row(basis=code, doc=code) for code in TRI_BASIS_CODES]
    frame, _ = fetch_tri_releases(
        state="VA", reporting_year=2022, session=_Session(len(rows), rows)
    )
    assert frame["basis_meaning"].notna().all()
    assert set(frame["basis_meaning"]) == set(TRI_BASIS_CODES.values())


def test_an_undocumented_basis_code_raises_rather_than_being_guessed() -> None:
    """A new code is a change in how a number was produced. Refuse to assume."""
    session = _Session(1, [_row(basis="Q9")])
    with pytest.raises(SchemaError) as exc:
        fetch_tri_releases(state="VA", reporting_year=2022, session=session)
    assert "Q9" in str(exc.value)
    assert "Refusing to guess" in str(exc.value)


def test_measured_flags_only_the_monitoring_codes() -> None:
    rows = [_row(basis=code, doc=code) for code in TRI_BASIS_CODES]
    frame, _ = fetch_tri_releases(
        state="VA", reporting_year=2022, session=_Session(len(rows), rows)
    )
    measured = set(frame.loc[frame["is_measured"] == True, "release_basis_est_code"])  # noqa: E712
    assert measured == set(TRI_MEASURED_CODES)


def test_a_missing_basis_code_is_unknown_not_false() -> None:
    """A record with no basis code has not been shown to be unmeasured.

    Collapsing null to False would let `~is_measured` count "we do not know"
    as "not monitored", which is the whole failure this column exists to avoid.
    """
    session = _Session(2, [_row(basis="M1", doc="A"), _row(basis=None, na="1",
                                                   total=None, doc="B")])
    frame, _ = fetch_tri_releases(state="VA", reporting_year=2022, session=session)
    assert str(frame["is_measured"].dtype) == "boolean"
    assert frame.loc[frame["doc_ctrl_num"] == "B", "is_measured"].isna().all()
    assert bool(frame.loc[frame["doc_ctrl_num"] == "A", "is_measured"].iloc[0]) is True


def test_the_scheme_change_year_matches_the_documented_code_pairs() -> None:
    """M1/M2 and E1/E2 exist because of the 2007 split. Keep them consistent."""
    assert TRI_CODE_SCHEME_CHANGE_YEAR == 2007
    for code in ("M1", "M2", "E1", "E2"):
        assert "added RY2007" in TRI_BASIS_CODES[code]
    for code in ("M", "E"):
        assert "pre-RY2007" in TRI_BASIS_CODES[code]
    assert {"M", "M1", "M2"} <= set(TRI_BASIS_CODES)
    assert not ({"E", "E1", "E2", "C", "O"} & TRI_MEASURED_CODES), (
        "emission factors, mass balance and engineering judgment are not measurements"
    )


# --------------------------------------------------------------------------
# The range-code hole
# --------------------------------------------------------------------------

@pytest.mark.parametrize("code,expected", [("1", 5.5), ("2", 250.0), ("3", 255.0), ("4", 749.5)])
def test_the_range_midpoint_is_the_documented_midpoint(code: str, expected: float) -> None:
    session = _Session(1, [_row(range_code=code, total=None)])
    frame, _ = fetch_tri_releases(state="VA", reporting_year=2022, session=session)
    assert float(frame["range_midpoint_lb"].iloc[0]) == expected


def test_the_midpoint_is_never_merged_into_the_reported_quantity() -> None:
    """The distinction is the point of the source. Assert it survives the client."""
    session = _Session(1, [_row(range_code="3", total=None)])
    frame, _ = fetch_tri_releases(state="VA", reporting_year=2022, session=session)
    assert frame["total_release"].isna().all(), (
        "a reconstructed midpoint must not become a reported quantity"
    )
    assert frame["range_midpoint_lb"].notna().all()


def test_a_row_with_no_range_code_has_no_midpoint() -> None:
    session = _Session(1, [_row(range_code=None, total="42")])
    frame, _ = fetch_tri_releases(state="VA", reporting_year=2022, session=session)
    assert frame["range_midpoint_lb"].isna().all()
    assert float(frame["total_release"].iloc[0]) == 42.0


def test_the_range_bands_are_ordered_and_nonempty() -> None:
    for code, (low, high) in TRI_RANGE_BANDS.items():
        assert low < high, f"band {code} is inverted"
        assert low >= 1, f"band {code} starts below one pound"


# --------------------------------------------------------------------------
# Schema and provenance
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "missing",
    ["release_basis_est_code", "release_range_code", "total_release", "release_na"],
)
def test_a_missing_load_bearing_column_is_named(missing: str) -> None:
    row = _row()
    del row[missing]
    session = _Session(1, [row])
    with pytest.raises(SchemaError, match=missing):
        fetch_tri_releases(state="VA", reporting_year=2022, session=session)


def test_provenance_names_the_self_report_regime() -> None:
    session = _Session(1, [_row()])
    _, prov = fetch_tri_releases(state="VA", reporting_year=2022, session=session)
    notes = " ".join(prov.notes)
    assert "REGULATORY SELF-REPORT" in notes
    assert "EPA does not" in notes and "measure" in notes
    assert "threshold" in notes
    assert str(TRI_CODE_SCHEME_CHANGE_YEAR) in notes
    assert "range_midpoint_lb" in notes and "NOT merged" in notes
    assert prov.source_name == "U.S. Environmental Protection Agency"
    assert prov.vintage == "reporting year 2022"


def test_provenance_counts_the_range_coded_hole() -> None:
    rows = [_row(doc="A"), _row(range_code="3", total=None, doc="B"),
            _row(range_code="4", total=None, doc="C")]
    session = _Session(len(rows), rows)
    _, prov = fetch_tri_releases(state="VA", reporting_year=2022, session=session)
    notes = " ".join(prov.notes)
    assert "2 of 2 range-coded records" in notes


def test_provenance_counts_how_many_records_rest_on_monitoring() -> None:
    rows = [_row(basis="M1", doc="A"), _row(basis="O", doc="B"), _row(basis="C", doc="C")]
    session = _Session(len(rows), rows)
    _, prov = fetch_tri_releases(state="VA", reporting_year=2022, session=session)
    assert "1 of 3 coded records rest on monitoring" in " ".join(prov.notes)


def test_the_provenance_hash_covers_every_page_not_just_the_first() -> None:
    """A hash over page one would certify a truncated pull as reproducible."""
    head = [_row(doc=f"D{i}") for i in range(TRI_REQUEST_ROWS)]
    total = TRI_REQUEST_ROWS + 1
    _, prov_x = fetch_tri_releases(
        state="VA", reporting_year=2022, session=_Session(total, head + [_row(doc="X")])
    )
    _, prov_y = fetch_tri_releases(
        state="VA", reporting_year=2022, session=_Session(total, head + [_row(doc="Y")])
    )
    assert prov_x.content_sha256 != prov_y.content_sha256


# --------------------------------------------------------------------------
# applicable_only: narrowing the download without narrowing the account
# --------------------------------------------------------------------------

def test_applicable_only_filters_server_side() -> None:
    session = _Session(0, [_row(doc="A"), _row(doc="B")],
                       counts={"/release_na/0/": 2, "tri_release_qty/count": 10})
    frame, _ = fetch_tri_releases(
        state="VA", reporting_year=2022, applicable_only=True, session=session
    )
    assert len(frame) == 2
    row_urls = [u for u in session.urls if "/rows/" in u]
    assert all("/release_na/0/" in u for u in row_urls), (
        "the filter must reach the server; filtering after download saves nothing"
    )


def test_applicable_only_still_reports_the_full_universe() -> None:
    """Narrowing what is downloaded must not narrow what the reader is told.

    Without this, a 2,100-row frame would silently stand in for a 12,069-row
    query and the 9,969 not-applicable rows would vanish from the account.
    """
    session = _Session(0, [_row(doc="A"), _row(doc="B")],
                       counts={"/release_na/0/": 2, "tri_release_qty/count": 10})
    _, prov = fetch_tri_releases(
        state="VA", reporting_year=2022, applicable_only=True, session=session
    )
    assert prov.variables["universe_rows"] == "10"
    assert prov.variables["applicable_only"] == "True"
    notes = " ".join(prov.notes)
    assert "10 medium-rows" in notes
    assert "8 not-applicable rows were filtered" in notes
    assert "they are not nothing" in notes, (
        "a not-applicable row records that the filer considered the medium; "
        "the note must not let a reader read it as missing data"
    )


def test_the_unfiltered_path_says_it_downloaded_everything() -> None:
    session = _Session(2, [_row(doc="A"), _row(doc="B")])
    _, prov = fetch_tri_releases(state="VA", reporting_year=2022, session=session)
    assert prov.variables["applicable_only"] == "False"
    assert prov.variables["universe_rows"] == "2"
    assert "all 2 were downloaded" in " ".join(prov.notes)


def test_a_universe_with_no_applicable_rows_is_distinguished_from_no_universe() -> None:
    """'Nobody filed' and 'everyone filed nothing' are different facts."""
    session = _Session(0, [], counts={"/release_na/0/": 0, "tri_release_qty/count": 500})
    with pytest.raises(EmptyResultError) as exc:
        fetch_tri_releases(
            state="VA", reporting_year=2022, applicable_only=True, session=session
        )
    message = str(exc.value)
    assert "500 TRI medium-rows but none marked applicable" in message
    assert "threshold" not in message, (
        "this is not the threshold story; conflating the two teaches the wrong "
        "lesson about what TRI silence means"
    )
