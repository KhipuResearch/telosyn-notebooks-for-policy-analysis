# © 2026 Telosyn, Inc. All rights reserved.
# Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.

"""Census ACS public connector mock-fixture (D02/D06/D07/D27 shared dependency).

Mocks ``api.census.gov/data/<year>/acs/acs5?get=<vars>&for=state:*`` returning
a 52-row state-level JSON array per Census API convention.

Synthetic data shape: header row + 52 state rows (50 states + DC + Puerto Rico).
Identity columns: NAME + variables + state. Connector applies DMV state filter
post-fetch via ``state in {"11", "24", "51"}`` mapping to DC/MD/VA.
"""

from __future__ import annotations

from collections.abc import Iterable

import responses

# Census ACS variables typically requested by D02/D06/D07/D27 cell-5 wiring.
# Fixture returns synthetic numeric values that satisfy downstream aggregation
# without invoking complex sklearn/numpy heavy-ops paths.
_DEFAULT_ACS_VARS = (
    "B01001_001E",  # total population
    "B01002_001E",  # median age
    "B02001_002E",  # white alone
    "B02001_003E",  # Black alone
    "B02001_005E",  # Asian alone
    "B03003_003E",  # Hispanic
    "B19013_001E",  # median household income
    "B17001_002E",  # poverty count
)


def _build_acs_response(variables: Iterable[str]) -> list[list[str]]:
    """Build a 52-row Census-API-shape JSON response.

    Format: [[header_row], [state_row_1], ..., [state_row_52]]
    Header: ["NAME", *variables, "state"]
    Rows: synthetic numeric values for each variable + state FIPS.
    """
    var_list = list(variables)
    header = ["NAME", *var_list, "state"]
    rows = [header]
    # All 50 states + DC + Puerto Rico (52 total) — connector filters to DMV
    state_fips_codes = [f"{i:02d}" for i in range(1, 57) if i not in (3, 7, 14, 43, 52)]
    for fips in state_fips_codes[:52]:
        name = f"State {fips}"
        # Synthetic values: realistic magnitudes for connector aggregation logic.
        values = [
            "1000000",  # total population
            "38",       # median age
            "600000",   # white
            "200000",   # Black
            "50000",    # Asian
            "100000",   # Hispanic
            "65000",    # median income
            "100000",   # poverty count
        ]
        rows.append([name, *values[: len(var_list)], fips])
    return rows


class MockCensusACS:
    """Context manager mocking Census ACS public API for D02/D06/D07/D27.

    Intercepts ``api.census.gov/data/<year>/acs/acs5`` queries with regex match
    (responses URL pattern) so any year/variable combination resolves to the
    same 52-row synthetic body.
    """

    def __init__(
        self,
        years: Iterable[int] = range(2018, 2023),
        variables: Iterable[str] = _DEFAULT_ACS_VARS,
    ) -> None:
        self._years = tuple(years)
        self._variables = tuple(variables)
        self._mock = responses.RequestsMock(assert_all_requests_are_fired=False)

    def __enter__(self) -> "MockCensusACS":
        import re
        self._mock.start()
        body = _build_acs_response(self._variables)
        # Regex match — covers all year × variable combinations
        url_pattern = re.compile(r"https?://api\.census\.gov/data/\d{4}/acs/acs5.*")
        self._mock.add(
            responses.GET,
            url_pattern,
            json=body,
            status=200,
            content_type="application/json",
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        self._mock.stop()
        self._mock.reset()
