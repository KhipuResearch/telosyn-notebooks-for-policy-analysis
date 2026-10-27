"""Contract and known-answer tests for ``sources.fetch_cps_asec``.

The function reads CPS ASEC person records and must return weighted cells only. The response is
injected, so no network and no credential is used.

Hand arithmetic for the fixture: five households of four (reference person 40, spouse 38,
children 10 and 8; household income 80,000; non-Hispanic White), every person weighted 10, so
income adjusted for size is 80,000 / sqrt(4) = 40,000. The adult cell has 10 records, weighted
100, sum of squared weights 10 x 100 = 1,000, weighted income 100 x 40,000 = 4,000,000; the child
cell has the same counts. Five single Hispanic reference persons aged 70 with household income
12,300 and weights 10..50: weighted 150, squared weights 100+400+900+1,600+2,500 = 5,500, weighted
income 150 x 12,300 = 1,845,000, bin 12,000.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import json
from typing import Any

import pandas as pd
import pytest

from krl_tutorials_data import sources
from krl_tutorials_data.sources import RangeError, SchemaError

KEY = "stub-census_api_key-not-a-credential"
HEADER = ["PH_SEQ", "A_EXPRRP", "A_AGE", "PRDTRACE", "PEHSPNON", "HTOTVAL", "H_NUMPER", "MARSUPWT"]


@pytest.fixture(autouse=True)
def _stub_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sources, "load_key", lambda name, **_: KEY)


class _Response:
    def __init__(self, rows: list[list[Any]], status: int = 200) -> None:
        self.status_code = status
        self.content = json.dumps(rows).encode()
        self.headers = {"content-type": "application/json"}

    @property
    def text(self) -> str:
        return self.content.decode()

    def json(self) -> Any:
        return json.loads(self.text)


class _Session:  # pylint: disable=too-few-public-methods
    def __init__(self, rows: list[list[Any]]) -> None:
        self.rows = rows
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> _Response:
        self.calls.append({"url": url, **kwargs})
        return _Response(self.rows)


def _hh(seq: int, members: list[tuple[int, int, int, int, int]], income: int, w: int) -> list[list[Any]]:
    """Rows of one household: members are (A_EXPRRP, A_AGE, PRDTRACE, PEHSPNON, weight)."""
    n = len(members)
    return [
        [str(seq), str(rp), str(age), str(race), str(hisp), str(income), str(n), str(wt or w)]
        for rp, age, race, hisp, wt in members
    ]


def _rows() -> list[list[Any]]:
    out: list[list[Any]] = [HEADER]
    for seq in range(1, 6):
        out += _hh(seq, [(1, 40, 1, 2, 10), (3, 38, 1, 2, 10), (5, 10, 1, 2, 10), (5, 8, 1, 2, 10)],
                   80000, 10)
    for i, wt in enumerate((10, 20, 30, 40, 50)):
        out += _hh(10 + i, [(2, 70, 2, 1, wt)], 12300, wt)
    return out


def _fetch(rows: list[list[Any]] | None = None, **overrides: Any):
    session = overrides.pop("session", None) or _Session(rows or _rows())
    kwargs: dict[str, Any] = {"year": 2024, "session": session, "min_cell_records": 5}
    kwargs.update(overrides)
    return sources.fetch_cps_asec(**kwargs), session


def _cell(frame: pd.DataFrame, **keys: Any) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    for k, v in keys.items():
        mask &= frame[k] == v
    assert mask.sum() == 1, keys
    return frame[mask].iloc[0]


def test_cells_by_hand() -> None:
    (frame, _), _ = _fetch(bin_width=1000.0)
    adult = _cell(frame, income_bin=40000.0, race="White alone", ref_age="35-64", child=0)
    assert (adult.weighted_n, adult.sum_w2, adult.weighted_income, adult.n_records) == (
        100.0, 1000.0, 4_000_000.0, 10)
    kids = _cell(frame, income_bin=40000.0, race="White alone", ref_age="35-64", child=1)
    assert (kids.weighted_n, kids.n_records) == (100.0, 10)
    hisp = _cell(frame, income_bin=12000.0, race="Hispanic", ref_age="65 and over", child=0)
    assert (hisp.weighted_n, hisp.sum_w2, hisp.weighted_income, hisp.n_records) == (
        150.0, 5500.0, 1_845_000.0, 5)


def test_total_weight_is_conserved() -> None:
    (frame, _), _ = _fetch()
    assert frame["weighted_n"].sum() == 4 * 5 * 10 + 150
    assert frame.attrs["suppressed_cells"] == 0


def test_no_person_level_column_and_no_request_for_a_geography_by_default() -> None:
    (frame, _), session = _fetch()
    assert not {"PH_SEQ", "A_AGE", "HTOTVAL", "MARSUPWT"} & set(frame.columns)
    call = session.calls[0]
    assert "for" not in call["params"]
    assert call["params"]["get"] == ",".join(HEADER)
    assert call["url"].endswith("/2024/cps/asec/mar")


def test_key_is_redacted_in_provenance() -> None:
    (_, prov), _ = _fetch()
    assert prov.request_params["key"] == "<redacted>"
    assert KEY not in json.dumps(prov.to_dict())
    assert prov.hash_basis == "canonical-rows" and prov.pinned is True
    assert prov.vintage == "2024"


def test_digest_ignores_row_order_and_responds_to_a_change() -> None:
    rows = _rows()
    shuffled = [rows[0], *reversed(rows[1:])]
    (f1, p1), _ = _fetch(rows)
    (f2, p2), _ = _fetch(shuffled)
    assert p1.content_sha256 == p2.content_sha256
    pd.testing.assert_frame_equal(f1, f2)
    changed = [r[:] for r in rows]
    changed[-1][5] = "12301"
    assert _fetch(changed)[0][1].content_sha256 != p1.content_sha256


def test_collapsed_tails_are_labelled_and_exact_income_is_kept() -> None:
    rows: list[list[Any]] = [HEADER]
    for seq in range(1, 6):
        rows += _hh(seq, [(2, 50, 1, 2, 10)], 500_000, 10)          # above the cap
    for seq in range(6, 11):
        rows += _hh(seq, [(2, 50, 1, 2, 10)], -40_000, 10)          # below the floor
    (frame, _), _ = _fetch(rows, bin_width=1000.0, income_cap=150_000.0, income_floor=0.0)
    top = _cell(frame, income_bin=150_000.0)
    assert top.weighted_income == 50 * 500_000.0
    low = _cell(frame, income_bin=-1000.0)
    assert low.weighted_income == 50 * -40_000.0


@pytest.mark.parametrize(
    ("race", "hisp", "label"),
    [(1, 2, "White alone"), (2, 2, "Black alone"), (4, 2, "Asian alone"),
     (3, 2, "Other non-Hispanic"), (5, 2, "Other non-Hispanic"), (6, 2, "Other non-Hispanic"),
     (26, 2, "Other non-Hispanic"), (1, 1, "Hispanic"), (4, 1, "Hispanic")],
)
def test_race_groups(race: int, hisp: int, label: str) -> None:
    rows: list[list[Any]] = [HEADER]
    for seq in range(1, 6):
        rows += _hh(seq, [(2, 50, race, hisp, 10)], 30_000, 10)
    (frame, _), _ = _fetch(rows)
    assert frame["race"].tolist() == [label]


@pytest.mark.parametrize(("age", "label"), [(34, "Under 35"), (35, "35-64"), (64, "35-64"), (65, "65 and over")])
def test_reference_age_groups(age: int, label: str) -> None:
    rows: list[list[Any]] = [HEADER]
    for seq in range(1, 6):
        rows += _hh(seq, [(1, age, 1, 2, 10)], 30_000, 10)
    (frame, _), _ = _fetch(rows)
    assert frame["ref_age"].tolist() == [label]


def test_children_take_the_reference_persons_age_group() -> None:
    (frame, _), _ = _fetch()
    assert set(frame.loc[frame["child"] == 1, "ref_age"]) == {"35-64"}


def test_small_cells_are_withheld_and_counted() -> None:
    rows = _rows()
    rows += _hh(99, [(2, 50, 4, 2, 7)], 20_000, 7)
    (frame, prov), _ = _fetch(rows)
    assert (frame["n_records"] >= 5).all()
    assert frame.attrs["suppressed_cells"] == 1
    assert frame.attrs["suppressed_weighted_n"] == 7.0
    assert any("withheld" in n for n in prov.notes)


def test_floor_has_a_minimum() -> None:
    with pytest.raises(ValueError, match="at least 5"):
        _fetch(min_cell_records=4)


def test_household_without_exactly_one_reference_person_raises() -> None:
    rows = _rows()
    rows += _hh(77, [(3, 30, 1, 2, 10)], 20_000, 10)
    with pytest.raises(SchemaError, match="reference person"):
        _fetch(rows)
    rows = _rows()
    rows += _hh(78, [(1, 30, 1, 2, 10), (2, 31, 1, 2, 10)], 20_000, 10)
    with pytest.raises(SchemaError, match="reference person"):
        _fetch(rows)


def test_nonnumeric_and_nonpositive_weight_and_bad_household_size_raise() -> None:
    rows = _rows()
    rows[1][5] = "abc"
    with pytest.raises(SchemaError):
        _fetch(rows)
    rows = _rows()
    rows[1][7] = "0"
    with pytest.raises(RangeError):
        _fetch(rows)
    rows = _rows()
    rows[1][6] = "0"
    with pytest.raises(RangeError, match="H_NUMPER"):
        _fetch(rows)


def test_bad_binning_arguments_raise() -> None:
    with pytest.raises(ValueError):
        _fetch(bin_width=0.0)
    with pytest.raises(ValueError):
        _fetch(income_cap=-1.0, income_floor=0.0)
