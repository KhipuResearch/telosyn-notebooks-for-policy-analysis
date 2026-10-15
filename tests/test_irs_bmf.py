"""The IRS master file, and a sector you cannot size.

The Business Master File lists every organisation the IRS recognises as
tax-exempt and carries NTEE_CD, the classification every sector analysis of the
nonprofit economy runs on. NTEE_CD is null for 29.2% of the file.

That would be survivable if the missingness were random. It is not: the
unclassified share runs from 21% among 501(c)(3) charities to 90% in some other
subsections. So a sector total over the classified rows is a total over a
non-random subset, and the client says so in provenance rather than leaving each
caller to discover it.

No network: every test drives the argument contract or a canned payload.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from krl_tutorials_data.sources import (
    EmptyResultError,
    IRS_BMF_AMOUNTS,
    IRS_BMF_REGIONS,
    NTEE_MAJOR_GROUPS,
    SchemaError,
    UpstreamError,
    fetch_irs_bmf,
)

HEADER = "EIN,NAME,STATE,SUBSECTION,NTEE_CD,ASSET_AMT,INCOME_AMT,REVENUE_AMT"
ROWS = [
    "000000001,ARTS COUNCIL,VA,03,A26,1000,2000,3000",
    "000000002,A CHURCH,VA,03,,0,0,",
    "000000003,A CLINIC,MD,03,E21,5000,6000,7000",
    "000000004,A LODGE,MD,08,,100,200,300",
]


def _csv(rows: list[str] | None = None, header: str = HEADER) -> bytes:
    return ("\n".join([header, *(rows if rows is not None else ROWS)]) + "\n").encode()


class _Response:
    def __init__(self, *, status: int = 200, body: bytes = b"") -> None:
        self.status_code = status
        self.content = body
        self.headers = {"content-type": "text/csv"}

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", "replace")


class _Session:
    def __init__(self, body: bytes | None = None, *, status: int = 200) -> None:
        self._body = _csv() if body is None else body
        self._status = status
        self.urls: list[str] = []

    def get(self, url: str, **kwargs: Any) -> _Response:
        self.urls.append(url)
        return _Response(status=self._status, body=self._body)


# --------------------------------------------------------------------------
# Argument contract
# --------------------------------------------------------------------------

def test_an_unknown_region_is_refused_and_the_real_ones_named() -> None:
    with pytest.raises(ValueError) as exc:
        fetch_irs_bmf(regions=["eo9"], session=_Session())
    assert "eo9" in str(exc.value)
    assert "eo1" in str(exc.value)


def test_an_empty_region_list_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one region"):
        fetch_irs_bmf(regions=[], session=_Session())


def test_every_region_is_requested_once() -> None:
    session = _Session()
    fetch_irs_bmf(session=session)
    assert len(session.urls) == len(IRS_BMF_REGIONS)
    assert all(any(f"/{r}.csv" in u for u in session.urls) for r in IRS_BMF_REGIONS)


def test_a_non_200_names_the_region() -> None:
    with pytest.raises(UpstreamError, match="eo1.csv"):
        fetch_irs_bmf(regions=["eo1"], session=_Session(status=404))


def test_an_empty_body_is_an_empty_result() -> None:
    with pytest.raises(EmptyResultError):
        fetch_irs_bmf(regions=["eo1"], session=_Session(b""))


def test_a_missing_load_bearing_column_is_named() -> None:
    body = _csv(header="EIN,NAME,STATE,SUBSECTION,ASSET_AMT,INCOME_AMT,REVENUE_AMT",
                rows=["000000001,X,VA,03,1,2,3"])
    with pytest.raises(SchemaError, match="NTEE_CD"):
        fetch_irs_bmf(regions=["eo1"], session=_Session(body))


# --------------------------------------------------------------------------
# The classification, which is the point
# --------------------------------------------------------------------------

def test_the_major_group_is_the_first_character() -> None:
    frame, _ = fetch_irs_bmf(regions=["eo1"], session=_Session())
    assert list(frame["ntee_major"]) == ["A", pd.NA, "E", pd.NA]


def test_unclassified_rows_are_flagged_not_dropped() -> None:
    """Dropping them is how a non-random subset becomes a sector total."""
    frame, _ = fetch_irs_bmf(regions=["eo1"], session=_Session())
    assert len(frame) == len(ROWS), "no row may be removed for lacking a classification"
    assert int((~frame["is_classified"]).sum()) == 2


def test_a_malformed_code_is_counted_as_unclassified_not_as_a_group() -> None:
    """The live file has 25 such rows. Raising over them makes the client unusable;
    accepting them puts a digit in a sector table."""
    body = _csv(rows=ROWS + ["000000009,MYSTERY ORG,VA,03,052,1,2,3"])
    frame, prov = fetch_irs_bmf(regions=["eo1"], session=_Session(body))
    assert len(frame) == len(ROWS) + 1, "the row must survive"
    row = frame[frame["EIN"] == "000000009"]
    assert bool(row["ntee_malformed"].iloc[0])
    assert not bool(row["is_classified"].iloc[0])
    assert pd.isna(row["ntee_major"].iloc[0])
    joined = " ".join(prov.notes)
    assert "MALFORMED CODES" in joined and "052" in joined
    assert "not as a group of their own" in joined


def test_a_lowercase_code_is_not_read_as_a_new_group() -> None:
    """The live file carries c030, c032, c300. Uppercase first, or invent a group."""
    body = _csv(rows=["000000009,ENVIRO ORG,VA,03,c030,1,2,3"])
    frame, _ = fetch_irs_bmf(regions=["eo1"], session=_Session(body))
    assert frame["ntee_major"].iloc[0] == "C"
    assert not bool(frame["ntee_malformed"].iloc[0])


def test_a_clean_file_says_there_were_no_malformed_codes() -> None:
    _, prov = fetch_irs_bmf(regions=["eo1"], session=_Session())
    assert "MALFORMED CODES: none" in " ".join(prov.notes)


def test_every_documented_major_group_is_accepted() -> None:
    rows = [f"00000{i:04d},ORG {letter},VA,03,{letter}11,1,2,3"
            for i, letter in enumerate(sorted(NTEE_MAJOR_GROUPS))]
    frame, _ = fetch_irs_bmf(regions=["eo1"], session=_Session(_csv(rows)))
    assert set(frame["ntee_major"].dropna()) == set(NTEE_MAJOR_GROUPS)


def test_whitespace_around_a_code_does_not_create_a_new_group() -> None:
    body = _csv(rows=["000000001,ARTS,VA,03,  A26  ,1,2,3"])
    frame, _ = fetch_irs_bmf(regions=["eo1"], session=_Session(body))
    assert frame["ntee_major"].iloc[0] == "A"


# --------------------------------------------------------------------------
# Amounts and provenance
# --------------------------------------------------------------------------

@pytest.mark.parametrize("column", IRS_BMF_AMOUNTS)
def test_amount_columns_are_numeric(column: str) -> None:
    frame, _ = fetch_irs_bmf(regions=["eo1"], session=_Session())
    assert pd.api.types.is_numeric_dtype(frame[column])


def test_a_blank_amount_becomes_na_not_zero() -> None:
    """A missing return is not a zero-revenue organisation."""
    frame, _ = fetch_irs_bmf(regions=["eo1"], session=_Session())
    assert frame.loc[frame["EIN"] == "000000002", "REVENUE_AMT"].isna().all()


def test_provenance_reports_the_classification_coverage() -> None:
    _, prov = fetch_irs_bmf(regions=["eo1"], session=_Session())
    joined = " ".join(prov.notes)
    assert "CLASSIFICATION COVERAGE" in joined
    assert "50.0%" in joined, "two of four rows are classified in the fixture"
    assert "the subset is not random" in joined


def test_provenance_reports_the_download_size() -> None:
    """A tutorial that quietly pulls a third of a gigabyte is not being honest."""
    _, prov = fetch_irs_bmf(regions=["eo1"], session=_Session())
    joined = " ".join(prov.notes)
    assert "LARGE BULK DOWNLOAD" in joined
    assert "MB" in joined


def test_provenance_warns_that_revenue_is_not_a_common_year() -> None:
    _, prov = fetch_irs_bmf(regions=["eo1"], session=_Session())
    joined = " ".join(prov.notes)
    assert "registration file, not a financial one" in joined
    assert "most recent period on file rather than a common year" in joined
    assert "assigned at registration" in joined
