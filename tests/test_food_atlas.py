"""The USDA Food Environment Atlas, and a county column that is a state value.

The Atlas is one .xls with 3,143 county rows and a FIPS column. It looks like a
county dataset throughout and it is not one throughout: measured on the
2026-09-15 copy, 49 of 280 numeric variables hold a single value per state,
replicated into every county row in that state. Two whole sheets -- INSECURITY
and TAXES -- are state data wearing a county FIPS.

The file marks this nowhere, so the client computes it. These tests pin the
classifier, because a classifier that silently stops classifying would return a
frame that looks exactly like a correct one.

No network: the classifier is exercised on constructed frames.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd
import pytest

from krl_tutorials_data.sources import (
    EmptyResultError,
    FEA_DATA_SHEETS,
    SchemaError,
    UpstreamError,
    classify_geographic_grain,
    fetch_food_environment_atlas,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame({
        "FIPS": [1001, 1003, 1005, 2013, 2016, 2020],
        "State": ["AL", "AL", "AL", "AK", "AK", "AK"],
        "County": list("abcdef"),
        "state_value": [16.3, 16.3, 16.3, 11.2, 11.2, 11.2],
        "county_value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        "mixed": [1.0, 1.0, 1.0, 4.0, 5.0, 6.0],
        "constant": [7.0] * 6,
        "text": list("uvwxyz"),
    })


# --------------------------------------------------------------------------
# The classifier
# --------------------------------------------------------------------------

def test_a_state_replicated_column_is_identified() -> None:
    grain = classify_geographic_grain(_frame()).set_index("column")
    assert bool(grain.loc["state_value", "is_group_replicated"])
    assert int(grain.loc["state_value", "groups_with_one_value"]) == 2
    assert int(grain.loc["state_value", "groups"]) == 2


def test_a_genuinely_varying_column_is_not() -> None:
    grain = classify_geographic_grain(_frame()).set_index("column")
    assert not bool(grain.loc["county_value", "is_group_replicated"])
    assert float(grain.loc["county_value", "median_distinct_per_group"]) == 3.0


def test_a_column_constant_in_some_groups_but_not_all_is_not_replicated() -> None:
    """The test is ALL groups. One state reporting one value is not the defect."""
    grain = classify_geographic_grain(_frame()).set_index("column")
    assert not bool(grain.loc["mixed", "is_group_replicated"])
    assert int(grain.loc["mixed", "groups_with_one_value"]) == 1


def test_a_column_constant_everywhere_is_skipped_not_flagged() -> None:
    """A column with one value nationally carries no geography to misstate."""
    grain = classify_geographic_grain(_frame())
    assert "constant" not in set(grain["column"])


def test_non_numeric_columns_are_skipped() -> None:
    grain = classify_geographic_grain(_frame())
    assert "text" not in set(grain["column"])
    assert "County" not in set(grain["column"])


def test_the_grouping_column_and_the_identifier_are_excluded() -> None:
    grain = classify_geographic_grain(_frame())
    assert "State" not in set(grain["column"])
    assert "FIPS" not in set(grain["column"]), (
        "FIPS is numeric and varies per row; classifying it would put a row "
        "identifier in a table of measurements"
    )


def test_nulls_do_not_manufacture_a_single_value() -> None:
    """A state with one non-null row must not be read as replicated evidence."""
    frame = _frame()
    frame["county_value"] = frame["county_value"].astype("float64")
    frame.loc[frame["State"] == "AK", "county_value"] = [4.0, np.nan, np.nan]
    grain = classify_geographic_grain(frame).set_index("column")
    assert int(grain.loc["county_value", "groups_with_one_value"]) == 1
    assert not bool(grain.loc["county_value", "is_group_replicated"])


def test_a_missing_grouping_column_is_refused() -> None:
    with pytest.raises(ValueError, match="not a column"):
        classify_geographic_grain(_frame(), group="Region")


def test_the_classifier_reports_the_effective_distinct_count() -> None:
    """The number that bounds a real sample size, not the row count."""
    grain = classify_geographic_grain(_frame()).set_index("column")
    assert int(grain.loc["state_value", "distinct_overall"]) == 2
    assert int(grain.loc["state_value", "rows"]) == 6


# --------------------------------------------------------------------------
# The fetcher's contract
# --------------------------------------------------------------------------

class _Response:
    def __init__(self, *, status: int = 200, body: bytes = b"") -> None:
        self.status_code = status
        self.content = body
        self.headers = {"content-type": "application/vnd.ms-excel"}

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", "replace")


class _Session:
    def __init__(self, response: _Response) -> None:
        self._response = response
        self.calls: list[dict] = []

    def get(self, url: str, **kwargs) -> _Response:
        self.calls.append({"url": url, **kwargs})
        return self._response


def _workbook() -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        _frame().to_excel(writer, sheet_name="INSECURITY", index=False)
    return buffer.getvalue()


@pytest.mark.parametrize("bad", ["Read_Me", " Variable List", "Supplemental Data - County", "access"])
def test_a_documentation_sheet_is_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="not a county data sheet"):
        fetch_food_environment_atlas(sheet=bad, session=_Session(_Response()))


def test_every_named_data_sheet_is_a_real_sheet_name() -> None:
    assert len(set(FEA_DATA_SHEETS)) == len(FEA_DATA_SHEETS)
    assert all(name.isupper() for name in FEA_DATA_SHEETS)


def test_a_non_200_says_the_file_has_moved_before() -> None:
    session = _Session(_Response(status=404, body=b"x"))
    with pytest.raises(UpstreamError) as exc:
        fetch_food_environment_atlas(sheet="ACCESS", session=session)
    assert "moved before" in str(exc.value)
    assert "rather than assuming the dataset is gone" in str(exc.value)


def test_an_empty_body_is_an_empty_result() -> None:
    with pytest.raises(EmptyResultError):
        fetch_food_environment_atlas(sheet="ACCESS", session=_Session(_Response(body=b"")))


def test_the_request_identifies_the_client() -> None:
    session = _Session(_Response(body=_workbook()))
    fetch_food_environment_atlas(sheet="INSECURITY", session=session)
    assert "krl-tutorials" in session.calls[0]["headers"]["User-Agent"]


def test_provenance_names_the_state_replicated_columns() -> None:
    session = _Session(_Response(body=_workbook()))
    _, prov = fetch_food_environment_atlas(sheet="INSECURITY", session=session)
    joined = " ".join(prov.notes)
    assert "state_value" in joined
    assert "county_value" not in joined.split("State-replicated in this sheet:")[1]
    assert "effective sample size" in joined
    assert "square root of their ratio" in joined


def test_provenance_says_the_vintage_is_a_hash_because_there_is_nothing_else() -> None:
    session = _Session(_Response(body=_workbook()))
    _, prov = fetch_food_environment_atlas(sheet="INSECURITY", session=session)
    assert "payload hash only" in prov.vintage
    assert "no published version number" in " ".join(prov.notes)


def test_a_sheet_missing_its_geography_columns_is_a_schema_error() -> None:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        _frame().drop(columns=["County"]).to_excel(writer, sheet_name="INSECURITY", index=False)
    session = _Session(_Response(body=buffer.getvalue()))
    with pytest.raises(SchemaError, match="County"):
        fetch_food_environment_atlas(sheet="INSECURITY", session=session)
