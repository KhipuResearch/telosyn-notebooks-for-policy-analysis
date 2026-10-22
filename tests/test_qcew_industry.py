"""``fetch_qcew`` selects an area slice or an industry slice, never both or neither.

The industry slice returns one industry in every area for a quarter, which is what a
county-by-quarter panel needs (one request per quarter instead of one per county).

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import math

import pytest
import requests

from krl_tutorials_data import sources

CSV = (
    '"area_fips","own_code","industry_code","agglvl_code","disclosure_code","qtrly_estabs",'
    '"month1_emplvl","month2_emplvl","month3_emplvl","avg_wkly_wage"\n'
    '"51059","5","722","78","","300","100","110","120","400"\n'
    '"51013","5","722","78","N","4","0","0","0","0"\n'
)


class _Session:  # pylint: disable=too-few-public-methods
    """A stand-in session that records the URL and answers with a fixed response."""

    def __init__(self, status: int = 200, body: str = CSV) -> None:
        self.status, self.body, self.urls = status, body, []

    def get(self, url: str, **_: object) -> requests.Response:
        """Return the canned response."""
        self.urls.append(url)
        response = requests.Response()
        response.status_code = self.status
        response._content = self.body.encode()  # pylint: disable=protected-access
        response.headers["Content-Type"] = "text/csv"
        return response


def test_the_industry_slice_hits_the_industry_endpoint_and_makes_suppression_explicit() -> None:
    """An industry slice is requested by industry; a withheld cell becomes NaN, not 0."""
    session = _Session()
    frame, prov = sources.fetch_qcew(year=2016, quarter=1, industry="722", session=session)
    assert session.urls == [f"{sources.QCEW_HOST}/2016/1/industry/722.csv"]
    assert prov.dataset == "QCEW industry 722, 2016 Q1"
    withheld = frame[frame["suppressed"]]
    assert len(withheld) == 1 and math.isnan(withheld["month3_emplvl"].iloc[0])
    assert frame.loc[~frame["suppressed"], "month3_emplvl"].iloc[0] == 120


def test_the_area_slice_still_hits_the_area_endpoint() -> None:
    """The original call is unchanged."""
    session = _Session()
    sources.fetch_qcew(year=2016, quarter=1, area="51059", session=session)
    assert session.urls == [f"{sources.QCEW_HOST}/2016/1/area/51059.csv"]


@pytest.mark.parametrize("kwargs", [{}, {"area": "51059", "industry": "722"}, {"industry": " "}])
def test_exactly_one_selector_is_required(kwargs: dict) -> None:
    """Neither, both, or a blank selector raises before any request."""
    session = _Session()
    with pytest.raises(ValueError):
        sources.fetch_qcew(year=2016, quarter=1, session=session, **kwargs)
    assert not session.urls


def test_a_missing_quarter_is_an_upstream_error_that_names_the_industry() -> None:
    """A 404 (the API serves 2014 Q1 onward) is reported against the industry code."""
    with pytest.raises(sources.UpstreamError, match="industry 722"):
        sources.fetch_qcew(year=2013, quarter=1, industry="722", session=_Session(status=404))
