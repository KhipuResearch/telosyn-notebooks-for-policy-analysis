# © 2026 Telosyn, Inc. All rights reserved.
# Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.

"""HUD CHAS connector mock-fixture (D27 dependency).

Mocks ``data.hud.gov/data/`` (or HUD CHAS bulk-download endpoints) returning
synthetic state-level housing-cost-burden data with sufficient column
cardinality for D27 cell-5 wiring (HUD CHAS contributes ~290+ columns to
the (15, 313) df_primary shape per W3-044-followup state).
"""

from __future__ import annotations

from collections.abc import Iterable

import responses

# DMV state FIPS for HUD CHAS state-level queries.
_DMV_STATE_FIPS = {"DC": "11", "MD": "24", "VA": "51"}


def _build_chas_response(state_fips: str, year: int) -> list[dict[str, object]]:
    """Build a synthetic HUD CHAS state-level response.

    Returns a single-row list-of-dicts (HUD CHAS state-level grain) with
    a representative subset of T1_est* + T1_moe* columns. Connector applies
    state-level aggregation; downstream cell-5 wiring widens to ~290 cols.
    """
    row: dict[str, object] = {
        "geoid": f"04000US{state_fips}",
        "name": f"State {state_fips}",
        "st": state_fips,
        "year": year,
        "sumlevel": "040",
        "source": "CHAS",
    }
    # Representative T1_est1..T1_est147 + T1_moe1..T1_moe147 (HUD CHAS cost-burden tables).
    # Connector widens these to per-income-bracket × tenure × cost-burden-pct combinations.
    for i in range(1, 148):
        row[f"T1_est{i}"] = 100 + i * 10
        row[f"T1_moe{i}"] = 5 + i
    return [row]


class MockHUDCHAS:
    """Context manager mocking HUD CHAS endpoints for D27 cell-5 wiring.

    Intercepts ``data.hud.gov/data/`` queries with regex pattern; returns
    state-level synthetic data per DMV state × year permutation.
    """

    def __init__(
        self,
        states: Iterable[str] = ("DC", "MD", "VA"),
        years: Iterable[int] = range(2018, 2023),
    ) -> None:
        self._states = tuple(states)
        self._years = tuple(years)
        self._mock = responses.RequestsMock(assert_all_requests_are_fired=False)

    def __enter__(self) -> "MockHUDCHAS":
        import re
        self._mock.start()
        # Regex covers all data.hud.gov queries (state-FIPS + year combos).
        url_pattern = re.compile(r"https?://(www\.)?data\.hud\.gov/.*")
        # Build a single response body with one row per (state, year) — connector
        # consumer applies state-FIPS filter post-fetch.
        all_rows = []
        for state in self._states:
            state_fips = _DMV_STATE_FIPS[state]
            for year in self._years:
                all_rows.extend(_build_chas_response(state_fips, year))
        self._mock.add(
            responses.GET,
            url_pattern,
            json=all_rows,
            status=200,
            content_type="application/json",
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        self._mock.stop()
        self._mock.reset()
