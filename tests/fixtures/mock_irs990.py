# © 2026 Telosyn, Inc. All rights reserved.
# Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.

"""ProPublica IRS 990 connector mock-fixture (D06/D27 dependency).

Mocks ``projects.propublica.org/nonprofits/api/v2/search.json?ntee[id]=...&state[id]=...``.

Synthetic data: returns a small organizations list per (state, NTEE-major) query
with sufficient cardinality for connector's per-state aggregation to produce
non-empty rows. Mocks the W3-029 Path A workaround pattern (broken state filter
upstream → client-side filter post-retrieval).
"""

from __future__ import annotations

from collections.abc import Iterable

import responses

# NTEE major-letter → numeric ID per IRS convention (used by ProPublica).
_NTEE_LETTER_TO_NUM = {chr(ord("A") + i): i + 1 for i in range(26)}


def _build_propublica_response(state_letter_pair: tuple[str, str]) -> dict[str, object]:
    """Build a synthetic ProPublica /search.json response body.

    Returns 5 nonprofits per query — sufficient for D06 narrow-slice + D27
    aggregation patterns. Each org has minimal IRS 990 fields that connectors
    consume: ein, name, state, ntee_code.
    """
    state, letter = state_letter_pair
    orgs = []
    for i in range(5):
        orgs.append(
            {
                "ein": f"00-{state}{letter}{i:03d}",
                "name": f"Synthetic Nonprofit {state}-{letter}-{i}",
                "state": state,
                "ntee_code": f"{letter}{20 + i}",
                "income_amount": 1_000_000 + i * 100_000,
                "revenue_amount": 1_200_000 + i * 100_000,
                "tax_period": 202012,
            }
        )
    return {
        "total_results": len(orgs),
        "organizations": orgs,
        "filters": {"state": state, "ntee_id": _NTEE_LETTER_TO_NUM.get(letter, 0)},
    }


class MockIRS990:
    """Context manager mocking ProPublica IRS 990 search.json for D06/D27.

    Returns deterministic synthetic nonprofit lists per (state, NTEE-major)
    combination. Covers NTEE-A (Arts) for D27 cultural-org wiring; configurable
    NTEE majors for D06 narrow-slice.
    """

    def __init__(
        self,
        states: Iterable[str] = ("DC", "MD", "VA"),
        ntee_letters: Iterable[str] = ("A",),
    ) -> None:
        self._states = tuple(states)
        self._ntee_letters = tuple(ntee_letters)
        self._mock = responses.RequestsMock(assert_all_requests_are_fired=False)

    def __enter__(self) -> "MockIRS990":
        import re
        self._mock.start()
        # Regex covers any ntee[id]= + state[id]= + page= combination.
        url_pattern = re.compile(
            r"https?://projects\.propublica\.org/nonprofits/api/v2/search\.json.*"
        )
        # Single response shape covers all queries (deterministic; 5 orgs each).
        # The connector applies its own NTEE/state client-side filter so a
        # generic body satisfies the cardinality contract.
        canonical_state = self._states[0] if self._states else "DC"
        canonical_letter = self._ntee_letters[0] if self._ntee_letters else "A"
        body = _build_propublica_response((canonical_state, canonical_letter))
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
