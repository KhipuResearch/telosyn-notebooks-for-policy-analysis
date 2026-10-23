"""``fetch_acs_pums`` with several states: cells are summed across states before the floor.

A grouping fine enough to be useful (age band by sex by education by disability ...) leaves most
cells under the floor within one state. Pooling sums whole cells across states inside the call and
applies the floor to the pooled count, so the reader still receives cells only.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from krl_tutorials_data import sources

KEY = "stub-census_api_key-not-a-credential"


@pytest.fixture(autouse=True)
def _stub_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub the key lookup so the test measures the fetcher."""
    monkeypatch.setattr(sources, "load_key", lambda name, **_: KEY)


class _Response:  # pylint: disable=too-few-public-methods
    """The minimum of ``requests.Response`` the fetcher touches."""

    def __init__(self, rows: list[list[Any]]) -> None:
        """Init."""
        self.status_code = 200
        self.content = json.dumps(rows).encode()
        self.headers = {"content-type": "application/json"}
        self.text = self.content.decode()

    def json(self) -> Any:
        """Body as JSON."""
        return json.loads(self.text)


class _ByState:  # pylint: disable=too-few-public-methods
    """Answers each request with the rows registered for its ``for`` parameter."""

    def __init__(self, per_state: dict[str, list[list[Any]]]) -> None:
        """Init."""
        self.per_state, self.calls = per_state, []

    def get(self, url: str, **kwargs: Any) -> _Response:  # pylint: disable=unused-argument
        """Answer."""
        state = kwargs["params"]["for"]
        self.calls.append(state)
        return _Response(self.per_state[state])


HEADER = ["AGEP", "PWGTP"]
VARS = {"AGEP": "Age"}


def _rows(age: int, n: int, weight: int) -> list[list[Any]]:
    """``n`` records at one age, each with the same weight, as the API returns them."""
    return [HEADER, *[[str(age), str(weight)] for _ in range(n)]]


def _fetch(per_state: dict[str, list[list[Any]]], geography: Any, **kwargs: Any):
    """Fetch through the stub."""
    session = _ByState(per_state)
    out = sources.fetch_acs_pums(
        year=2023,
        variables=VARS,
        aggregate_by=["AGEP"],
        geography=geography,
        min_cell_records=5,
        session=session,
        **kwargs,
    )
    return out, session


TWO = {
    "state:51": _rows(30, 3, 10) + _rows(40, 6, 5)[1:],
    "state:56": _rows(30, 3, 20),
}


def test_a_cell_under_the_floor_in_each_state_survives_when_pooled() -> None:
    """Age 30: 3 records in each state is withheld alone, but 6 pooled meets the floor of 5."""
    (alone, _), _ = _fetch({"state:51": TWO["state:51"]}, "state:51")
    assert 30 not in set(alone["AGEP"])
    (pooled, prov), session = _fetch(TWO, ["state:51", "state:56"])
    cells = {int(r.AGEP): (r.weighted_n, r.n_records) for r in pooled.itertuples()}
    assert cells == {30: (3 * 10 + 3 * 20, 6), 40: (30.0, 6)}
    assert session.calls == ["state:51", "state:56"]
    assert pooled.attrs["records_read"] == 12 and pooled.attrs["suppressed_records"] == 0
    assert any("Pooled 2 state(s)" in n for n in prov.notes)


def test_the_pooled_record_names_every_state_and_still_redacts_the_key() -> None:
    """The provenance request lists the states; the key is redacted and never stored."""
    (_, prov), _ = _fetch(TWO, ["state:51", "state:56"])
    assert prov.request_params["for"] == ["state:51", "state:56"]
    assert prov.request_params["key"] == "<redacted>"
    assert KEY not in json.dumps(prov.to_dict())
    assert prov.row_count == 12


def test_a_single_state_in_a_list_behaves_like_the_string() -> None:
    """One named state, as a list or as a string, gives the same cells."""
    (as_list, _), _ = _fetch({"state:51": TWO["state:51"]}, ["state:51"])
    (as_text, _), _ = _fetch({"state:51": TWO["state:51"]}, "state:51")
    assert as_list.equals(as_text)


@pytest.mark.parametrize(
    "geography", [[], ["state:51", "state:51"], ["state:*"], ["state:51", "state:*"]]
)
def test_an_empty_duplicated_or_wildcard_list_raises_before_any_request(geography: list) -> None:
    """The list must name at least one state, each once, and no wildcard."""
    with pytest.raises(ValueError):
        _fetch(TWO, geography)
