# © 2026 Telosyn, Inc. All rights reserved.
# Exclusively licensed to Deloatch, Williams, Faison & Parker, LLLP.

"""BLS QCEW connector mock-fixture (D02 dependency).

Mocks ``data.bls.gov/cew/data/api/<year>/a/area/<area_code>.csv`` (CSV-slice
endpoint per W3-040 closure).

Synthetic data: NAICS=10 supersector + own_code=5 (private) row uniformly
across 3 DMV state-FIPS×year permutations × 5 years (2018-2022).
Cardinality target: 14 NAICS-10×own=5 rows per (state_FIPS, year) per
W3-040 closure precedent.
"""

from __future__ import annotations

from collections.abc import Iterable

import responses

# DMV state FIPS → 5-digit area_code (state_FIPS + '000' for state-level).
_DMV_STATE_FIPS = {"DC": "11000", "MD": "24000", "VA": "51000"}

_QCEW_CSV_HEADER = (
    "area_fips,own_code,industry_code,agglvl_code,size_code,year,qtr,"
    "disclosure_code,annual_avg_estabs,annual_avg_emplvl,total_annual_wages,"
    "annual_avg_wkly_wage"
)


def _build_qcew_csv_body(area_fips: str, year: int) -> str:
    """Build a 14-row NAICS-10×own=5 CSV body for the given (state, year).

    Cardinality matches W3-040 closure baseline (14 rows uniformly across DMV).
    Decoy rows (NAICS≠'10' OR own_code≠'5') excluded from the synthetic body
    since the connector's `.startswith('10')` filter in `_fetch_async` would
    drop them anyway — keeping the body compact reduces test fixture surface.
    """
    rows = [_QCEW_CSV_HEADER]
    # 14 NAICS codes that all start with '10' per W3-040 baseline (supersector
    # + 1011/1012/1013 goods/service-producing + 101N four-digit aggregates +
    # 102N four-digit aggregates).
    naics_codes = [
        "10",
        "101", "1011", "1012", "1013",
        "1021", "1022", "1023", "1024", "1025", "1026", "1027", "1028", "1029",
    ]
    for naics in naics_codes:
        rows.append(
            f'{area_fips},5,{naics},51,0,{year},A,,'
            f"100,1000,1000000,1000"
        )
    return "\n".join(rows) + "\n"


class MockBLSQcew:
    """Context manager mocking BLS QCEW CSV-slice endpoint for DMV 2018-2022.

    Usage::

        with MockBLSQcew():
            with responses.RequestsMock(...) as rsps:
                # papermill execution here
                pass

    Or, when used standalone::

        with MockBLSQcew() as mock:
            # responses is activated; papermill calls hit synthetic CSV
            pass
    """

    def __init__(
        self,
        states: Iterable[str] = ("DC", "MD", "VA"),
        years: Iterable[int] = range(2018, 2023),
    ) -> None:
        self._states = tuple(states)
        self._years = tuple(years)
        self._mock = responses.RequestsMock(assert_all_requests_are_fired=False)

    def __enter__(self) -> "MockBLSQcew":
        self._mock.start()
        for state in self._states:
            area_fips = _DMV_STATE_FIPS[state]
            for year in self._years:
                url = f"https://data.bls.gov/cew/data/api/{year}/a/area/{area_fips}.csv"
                self._mock.add(
                    responses.GET,
                    url,
                    body=_build_qcew_csv_body(area_fips, year),
                    status=200,
                    content_type="text/csv",
                )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        self._mock.stop()
        self._mock.reset()
