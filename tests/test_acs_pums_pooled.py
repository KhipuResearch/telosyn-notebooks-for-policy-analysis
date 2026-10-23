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
import requests

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


class _Flaky:  # pylint: disable=too-few-public-methods
    """Answers with a failing response a set number of times, then the rows."""

    def __init__(self, failures: list[Any], rows: list[list[Any]]) -> None:
        """Init."""
        self.failures, self.rows, self.attempts = list(failures), rows, 0

    def get(self, url: str, **kwargs: Any) -> Any:  # pylint: disable=unused-argument
        """Fail, then answer."""
        self.attempts += 1
        if self.failures:
            failure = self.failures.pop(0)
            if isinstance(failure, Exception):
                raise failure
            response = _Response([])
            response.status_code = failure
            return response
        return _Response(self.rows)


def _flaky_fetch(session: _Flaky):
    """Fetch one state through the flaky session."""
    return sources.fetch_acs_pums(
        year=2023,
        variables=VARS,
        aggregate_by=["AGEP"],
        geography="state:51",
        min_cell_records=5,
        session=session,
    )


def test_a_transient_503_timeout_or_reset_is_retried_and_the_pauses_grow(monkeypatch) -> None:
    """Two failures then success: three attempts, with the documented pauses between them."""
    pauses: list[float] = []
    monkeypatch.setattr(sources, "_sleep", pauses.append)
    session = _Flaky([503, requests.ConnectionError("reset")], _rows(30, 6, 10))
    (frame, _) = _flaky_fetch(session)
    assert session.attempts == 3 and frame["n_records"].sum() == 6
    assert pauses == [0.0, 5.0, 15.0]


def test_persistent_503s_stop_after_the_last_pause_and_other_statuses_stop_at_once(
    monkeypatch,
) -> None:
    """Four 503s end in an UpstreamError; a 400 is not retried."""
    monkeypatch.setattr(sources, "_sleep", lambda _: None)
    always = _Flaky([503] * 10, _rows(30, 6, 10))
    with pytest.raises(sources.UpstreamError, match="503"):
        _flaky_fetch(always)
    assert always.attempts == len(sources.PUMS_RETRY_PAUSES)
    once = _Flaky([400], _rows(30, 6, 10))
    with pytest.raises(sources.UpstreamError, match="400"):
        _flaky_fetch(once)
    assert once.attempts == 1
    slow = _Flaky([requests.Timeout("slow")] * 10, _rows(30, 6, 10))
    with pytest.raises(sources.UpstreamError, match="failed after 4 attempts"):
        _flaky_fetch(slow)
    assert slow.attempts == len(sources.PUMS_RETRY_PAUSES)
    reset = _Flaky([requests.ConnectionError("reset")] * 10, _rows(30, 6, 10))
    with pytest.raises(sources.UpstreamError, match="failed after 4 attempts"):
        _flaky_fetch(reset)
    assert reset.attempts == len(sources.PUMS_RETRY_PAUSES)
    broken = _Flaky([requests.exceptions.InvalidURL("bad")], _rows(30, 6, 10))
    with pytest.raises(sources.UpstreamError, match="failed"):
        _flaky_fetch(broken)
    assert broken.attempts == 1
