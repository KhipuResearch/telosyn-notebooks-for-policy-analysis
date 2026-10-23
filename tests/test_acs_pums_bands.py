"""``keep`` and ``bands`` on ``fetch_acs_pums``: restrict and coarsen inside the aggregator.

Both act on the private person frame before it is grouped, so neither offers a way to see a
record. A design that needs a sample restriction (income below a threshold) or a coarse covariate
(age in five-year bands) can then be run on cells without cells exploding past the small-cell floor.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from krl_tutorials_data import sources
from krl_tutorials_data.sources import RangeError


@pytest.fixture(autouse=True)
def _stub_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub the key lookup so the test measures the fetcher."""
    monkeypatch.setattr(sources, "load_key", lambda name, **_: "stub-not-a-credential")


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


class _Session:  # pylint: disable=too-few-public-methods
    """Answers every GET with one canned response."""

    def __init__(self, rows: list[list[Any]]) -> None:
        """Init."""
        self.response = _Response(rows)

    def get(self, url: str, **kwargs: Any) -> _Response:  # pylint: disable=unused-argument
        """Answer."""
        return self.response


HEADER = ["AGEP", "POVPIP", "PWGTP"]
VARS = {"AGEP": "Age", "POVPIP": "Income-to-poverty ratio"}


def _rows(spec: list[tuple[int, int, int]]) -> list[list[Any]]:
    """Rows from (age, income ratio, weight) triples, as the API returns them (strings)."""
    return [HEADER, *[[str(a), str(p), str(w)] for a, p, w in spec]]


def _fetch(spec: list[tuple[int, int, int]], **kwargs: Any):
    """Fetch through the stub with the shared arguments."""
    base: dict[str, Any] = {
        "year": 2023,
        "variables": VARS,
        "aggregate_by": ["AGEP"],
        "geography": "state:51",
        "min_cell_records": 5,
        "session": _Session(_rows(spec)),
    }
    base.update(kwargs)
    return sources.fetch_acs_pums(**base)


# five records at each of ages 19, 24 (band 19), 25, 29 (band 25), 30 and 64 (band 30) at income
# ratio 100, then five at 30 and five at 64 with ratio 400: 40 records, each weighing 10
SPEC = (
    [(a, 100, 10) for a in (19, 24, 25, 29, 30) for _ in range(5)]
    + [(a, 100, 10) for a in [64] * 5]
    + [(a, 400, 10) for a in [30] * 5 + [64] * 5]
)


def test_bands_label_each_record_by_the_lower_edge_of_its_band_by_hand() -> None:
    """Ages 19 and 24 share band 19 (10 records); 25 and 29 band 25; 30 and 64 band 30 (20)."""
    frame, prov = _fetch(SPEC, bands={"AGEP": [19, 25, 30, 65]})
    cells = {int(r.AGEP): (r.weighted_n, r.n_records) for r in frame.itertuples()}
    assert cells == {19: (100.0, 10), 25: (100.0, 10), 30: (200.0, 20)}
    assert any("Coarsened" in n for n in prov.notes)


def test_keep_restricts_the_records_before_grouping_and_says_how_many() -> None:
    """Income ratio at most 199 drops the ten records at 400: 40 read, 30 kept."""
    frame, prov = _fetch(SPEC, keep={"POVPIP": (0, 199)}, bands={"AGEP": [19, 25, 30, 65]})
    assert frame.attrs["records_read"] == 40 and frame.attrs["records_kept"] == 30
    assert {int(r.AGEP): r.n_records for r in frame.itertuples()} == {19: 10, 25: 10, 30: 10}
    assert any("Kept 30 of 40" in n for n in prov.notes)


def test_a_value_outside_the_bands_raises_instead_of_being_dropped_or_clamped() -> None:
    """Age 64 against bands ending at 60 stops the retrieval; the message says how to restrict."""
    with pytest.raises(RangeError, match="restrict the records with `keep` first"):
        _fetch(SPEC, bands={"AGEP": [19, 25, 30, 60]})
    kept = _fetch(SPEC, keep={"AGEP": (19, 59)}, bands={"AGEP": [19, 25, 30, 60]})[0]
    assert kept["n_records"].sum() == 30


def test_a_missing_value_is_outside_every_keep_range_and_unbanded_otherwise() -> None:
    """A missing key variable is not kept; a missing banded value stays its own cell."""
    rows = [HEADER] + [[None, "100", "10"]] * 6 + [["20", "100", "10"]] * 6
    cells = _fetch([], session=_Session(rows), bands={"AGEP": [19, 30]})[0]
    assert set(cells["AGEP"].fillna(-1)) == {-1.0, 19.0}
    with_keep = _fetch([], session=_Session(rows), keep={"AGEP": (0, 99)})[0]
    assert with_keep["n_records"].sum() == 6


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"keep": {"NOPE": (0, 1)}}, "not in `variables`"),
        ({"bands": {"NOPE": [0, 1]}}, "not in `variables`"),
        ({"keep": {"AGEP": (50, 10)}}, "low <= high"),
        ({"bands": {"POVPIP": [0, 100, 200]}}, "must also be in `aggregate_by`"),
        ({"bands": {"AGEP": [30]}}, "at least two strictly ascending"),
        ({"bands": {"AGEP": [30, 30, 40]}}, "at least two strictly ascending"),
    ],
)
def test_invalid_specifications_raise_before_any_request(kwargs: dict, message: str) -> None:
    """A bad keep or bands specification never reaches the network."""
    session = _Session(_rows(SPEC))
    with pytest.raises(ValueError, match=message):
        _fetch(SPEC, session=session, **kwargs)


@settings(max_examples=25, deadline=None)
@given(seed=st.integers(0, 10_000))
def test_property_returned_plus_withheld_weight_is_the_weight_of_the_kept_records(
    seed: int,
) -> None:
    """Restricting and banding never creates or loses weight: kept = returned + withheld."""
    rng = np.random.default_rng(seed)
    n = 200
    frame = pd.DataFrame(
        {
            "AGEP": rng.integers(19, 65, n).astype(float),
            "POVPIP": rng.integers(0, 500, n).astype(float),
            "PWGTP": rng.integers(1, 300, n).astype(float),
        }
    )
    cells, _ = sources._pums_cells(  # pylint: disable=protected-access
        frame,
        ["AGEP"],
        "PWGTP",
        5,
        keep={"POVPIP": (0, 199)},
        bands={"AGEP": [19, 30, 45, 65]},
    )
    kept_weight = frame.loc[frame["POVPIP"] <= 199, "PWGTP"].sum()
    total = cells["weighted_n"].sum() + cells.attrs["suppressed_weighted_n"]
    assert total == pytest.approx(kept_weight)
    assert set(cells["AGEP"]) <= {19.0, 30.0, 45.0}


def test_whole_number_keep_ranges_are_sent_as_predicates_and_still_applied_locally() -> None:
    """The request carries AGEP=19:64; a service that ignored it changes nothing in the cells."""
    seen: list[dict] = []

    class _Recording(_Session):  # pylint: disable=too-few-public-methods
        def get(self, url: str, **kwargs: Any) -> _Response:
            seen.append(kwargs["params"])
            return super().get(url, **kwargs)

    session = _Recording(_rows(SPEC))
    frame, _ = _fetch(SPEC, session=session, keep={"POVPIP": (0, 199), "AGEP": (19, 64)})
    assert seen[0]["POVPIP"] == "0:199" and seen[0]["AGEP"] == "19:64"
    assert frame.attrs["records_kept"] == 30  # the stub ignored the predicate; the filter held


def test_a_fractional_keep_bound_is_not_sent_as_a_predicate() -> None:
    """Only whole-number ranges are expressed to the service."""
    predicates = sources._pums_predicates  # pylint: disable=protected-access
    assert predicates({"AGEP": (19, 64), "X": (0.5, 3)}) == {"AGEP": "19:64"}
    assert not predicates(None)


def test_a_column_the_service_echoes_back_is_collapsed_and_a_differing_echo_is_refused() -> None:
    """A range predicate makes the service repeat the variable; equal copies collapse."""
    rows = [["AGEP", "POVPIP", "PWGTP", "AGEP", "POVPIP"]] + [["30", "100", "10", "30", "100"]] * 6
    frame, _ = _fetch([], session=_Session(rows), keep={"AGEP": (19, 64)})
    assert frame["n_records"].sum() == 6
    clashing = [["AGEP", "POVPIP", "PWGTP", "AGEP"]] + [["30", "100", "10", "31"]] * 6
    with pytest.raises(sources.SchemaError, match="differing values"):
        _fetch([], session=_Session(clashing))


def test_the_provenance_request_records_the_range_predicates_that_were_sent() -> None:
    """A replay of the record must send what was sent: the predicates are in request_params."""
    seen: list[dict] = []

    class _Recording(_Session):  # pylint: disable=too-few-public-methods
        def get(self, url: str, **kwargs: Any) -> _Response:
            seen.append(kwargs["params"])
            return super().get(url, **kwargs)

    _, prov = _fetch(
        SPEC, session=_Recording(_rows(SPEC)), keep={"POVPIP": (0, 199), "AGEP": (19, 64)}
    )
    sent = {k: v for k, v in seen[0].items() if k not in ("key",)}
    recorded = {k: v for k, v in prov.request_params.items() if k != "key"}
    assert recorded == sent
    assert recorded["AGEP"] == "19:64" and recorded["POVPIP"] == "0:199"
    assert prov.request_params["key"] == "<redacted>"
