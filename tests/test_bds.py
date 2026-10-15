"""The BDS fetcher's contract, and the three ways its aggregations lie.

Business Dynamics Statistics is the corpus's case where the published values
are internally exact and the *sums* are not, for three unrelated reasons acting
in opposite directions. Only one of them is the disclosure-avoidance
perturbation analysts are trained to look for, and it is the smallest by two
orders of magnitude.

These tests hold the client to the part it can enforce: it must never turn a
suppressed cell into a number, never accept an undocumented flag, never let a
caller ask for "latest", and never return a frame whose provenance is silent
about which of the requested variables are firm-level or noise-infused.

No network: every test drives the argument contract or a canned payload.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import json
import math
from typing import Any

import pandas as pd
import pytest

from krl_tutorials_data import sources
from krl_tutorials_data.sources import (
    BDS_DISCLOSURE_REGIME,
    BDS_FIRM_LEVEL_VARIABLES,
    BDS_FLAG_MEANINGS,
    BDS_NOISE_INFUSED_VARIABLES,
    BDS_YEARS,
    CENSUS_GET_CEILING,
    EmptyResultError,
    SchemaError,
    bds_prior_year_establishments,
    fetch_bds,
)


@pytest.fixture(autouse=True)
def _no_credential_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub the credential lookup. These are unit tests of the contract.

    ``fetch_bds`` calls ``load_key`` on the way to the request. Without the
    stub, every test that reaches the request would fail with
    ``MissingCredentialError`` on any machine without a secrets file -- CI's
    static lane included, which holds no secrets by design.
    """
    monkeypatch.setattr(
        sources, "load_key", lambda name, **_: f"stub-{name.lower()}-not-a-credential"
    )


class _Response:
    def __init__(self, *, status: int = 200, body: bytes = b"", content_type: str = "application/json") -> None:
        self.status_code = status
        self.content = body
        self.headers = {"content-type": content_type}

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", "replace")

    def json(self) -> Any:
        return json.loads(self.text)


class _Session:
    """Answers with one canned payload and records what was asked for."""

    def __init__(self, response: _Response) -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []

    def get(self, *args: Any, **kwargs: Any) -> _Response:
        self.calls.append(kwargs.get("params", {}))
        return self._response


def _payload(header: list[str], *rows: list[Any]) -> _Response:
    return _Response(body=json.dumps([header, *rows]).encode())


# --------------------------------------------------------------------------- #
# The vintage contract
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("year", [1977, 2024, 2030, 0])
def test_an_unpublished_year_is_refused_before_the_key_is_read(year: int) -> None:
    """The year check must precede the credential lookup.

    Ordering is the point. If the key were read first, a reader with no secrets
    file would be told their credentials are missing when their real mistake is
    a year the series does not cover, and they would go looking in the wrong
    place.
    """
    with pytest.raises(ValueError, match="outside the published series"):
        fetch_bds(year=year, variables=["ESTAB"], session=_Session(_payload(["ESTAB"])))


def test_there_is_no_latest() -> None:
    """``year`` is keyword-only and required; no default can drift."""
    with pytest.raises(TypeError):
        fetch_bds(variables=["ESTAB"])  # type: ignore[call-arg]


def test_the_published_range_matches_what_census_serves() -> None:
    """1978-2023 is the range Census documents for the time series endpoint.

    Pinned so that extending the client to a new release is a deliberate edit
    with a test to update, not something that happens by accident.
    """
    assert BDS_YEARS.start == 1978
    assert BDS_YEARS.stop - 1 == 2023


@pytest.mark.parametrize("variables", [[], ["", "ESTAB"], ["  "]])
def test_blank_or_empty_variables_are_refused(variables: list[str]) -> None:
    with pytest.raises(ValueError):
        fetch_bds(year=2022, variables=variables, session=_Session(_payload(["ESTAB"])))


# --------------------------------------------------------------------------- #
# Flags: a withheld cell is never a number
# --------------------------------------------------------------------------- #


def test_flags_are_requested_alongside_every_variable() -> None:
    session = _Session(_payload(["ESTAB", "ESTAB_F", "state"], ["100", None, "51"]))
    fetch_bds(year=2022, variables=["ESTAB"], session=session)
    requested = session.calls[0]["get"].split(",")
    assert requested == ["ESTAB", "ESTAB_F"], (
        "the flag column must be requested by default; a suppressed cell that "
        "arrives without its flag is indistinguishable from data"
    )


@pytest.mark.parametrize("flag", sorted(BDS_FLAG_MEANINGS))
def test_a_flagged_cell_becomes_nan_and_never_zero(flag: str) -> None:
    """D, S, X and N all mean "there is no number here".

    Zero is the dangerous coercion: it survives a sum, a mean and a rank, and
    the result looks like a county with no businesses rather than a cell that
    was withheld.
    """
    session = _Session(_payload(
        ["ESTAB", "ESTAB_F", "state"],
        ["0", flag, "51"],
        ["250", None, "24"],
    ))
    frame, _ = fetch_bds(year=2022, variables=["ESTAB"], session=session)
    assert math.isnan(frame["ESTAB"].iloc[0])
    assert frame["ESTAB"].iloc[1] == 250
    assert frame["ESTAB"].sum() == 250, "a masked cell must not contribute to a sum"


def test_an_undocumented_flag_value_is_refused_rather_than_guessed() -> None:
    """A new flag means Census changed something. Guessing its meaning is how a
    disclosure convention silently becomes a data value."""
    session = _Session(_payload(["ESTAB", "ESTAB_F", "state"], ["0", "Q", "51"]))
    with pytest.raises(SchemaError, match="unrecognised flag"):
        fetch_bds(year=2022, variables=["ESTAB"], session=session)


def test_suppression_is_recorded_in_provenance_not_only_in_the_frame() -> None:
    session = _Session(_payload(
        ["ESTAB", "ESTAB_F", "state"], ["0", "D", "51"], ["12", None, "24"],
    ))
    _, prov = fetch_bds(year=2022, variables=["ESTAB"], session=session)
    joined = " ".join(prov.notes)
    assert "ESTAB=1" in joined
    assert "never zero" in joined


def test_flags_can_be_declined_but_the_ceiling_still_holds() -> None:
    """Asking for more columns than the API accepts must fail loudly here.

    The Census API truncates rather than erroring on an over-long ``get``, so a
    request that silently loses its flag columns returns suppressed cells with
    no flag attached -- the exact failure this client exists to prevent.
    """
    many = [f"V{i}" for i in range(CENSUS_GET_CEILING)]
    with pytest.raises(ValueError, match="do not drop the flags"):
        fetch_bds(year=2022, variables=many, session=_Session(_payload(many)))


# --------------------------------------------------------------------------- #
# Provenance carries the additivity warnings
# --------------------------------------------------------------------------- #


def test_a_firm_level_variable_is_labelled_non_additive() -> None:
    """FIRM is the trap that costs the most and looks the least like one.

    Census: geography and industry are defined at the establishment level, so a
    firm with establishments in several counties appears in each county's firm
    count. Summing counties overstates firms, and nothing in the response says so.
    """
    session = _Session(_payload(["FIRM", "FIRM_F", "state"], ["10", None, "51"]))
    _, prov = fetch_bds(year=2022, variables=["FIRM"], session=session)
    joined = " ".join(prov.notes)
    assert "NOT ADDITIVE" in joined
    assert "FIRM" in joined
    assert "double-counts" in joined


def test_a_count_variable_is_not_labelled_non_additive() -> None:
    """The warning has to discriminate, or readers learn to ignore it.

    ESTAB and EMP do sum exactly over a partition of the same records -- that is
    what "balanced" noise infusion buys. Warning about them too would make the
    FIRM warning worthless.
    """
    session = _Session(_payload(["ESTAB", "ESTAB_F", "state"], ["10", None, "51"]))
    _, prov = fetch_bds(year=2022, variables=["ESTAB"], session=session)
    assert "NOT ADDITIVE" not in " ".join(prov.notes)


def test_job_flow_variables_are_labelled_noise_infused() -> None:
    session = _Session(_payload(["JOB_CREATION", "JOB_CREATION_F", "state"], ["10", None, "51"]))
    _, prov = fetch_bds(year=2022, variables=["JOB_CREATION"], session=session)
    assert "Noise-infused at the cell level" in " ".join(prov.notes)


def test_a_county_request_warns_that_statewide_records_are_missing() -> None:
    """The county gap is not noise and is not small.

    Statewide (999) records hold establishments with no fixed location. The API
    does not serve them, so county rows cannot be reconciled to the state total,
    and the shortfall lands overwhelmingly in one sector.
    """
    session = _Session(_payload(["EMP", "EMP_F", "state", "county"], ["10", None, "51", "001"]))
    _, prov = fetch_bds(year=2022, variables=["EMP"], geography="county:*",
                        within="state:51", session=session)
    joined = " ".join(prov.notes)
    assert "999" in joined and "NAICS 56" in joined


def test_provenance_records_the_disclosure_regime_of_the_vintage() -> None:
    """A stored notebook output has to say which regime produced its numbers.

    DAO 216-26 prohibits noise infusion prospectively. Once coarsening replaces
    it, two BDS vintages in the same chart will have been protected by different
    mechanisms with different error structures, and nothing in the values will
    announce the change.
    """
    session = _Session(_payload(["ESTAB", "ESTAB_F", "state"], ["10", None, "51"]))
    _, prov = fetch_bds(year=2022, variables=["ESTAB"], session=session)
    joined = " ".join(prov.notes)
    assert BDS_DISCLOSURE_REGIME in joined
    assert "216-26" in joined
    assert "cannot be averaged away by resampling" in joined


def test_the_denom_trap_is_stated_on_every_response() -> None:
    """DENOM is an employment denominator with a name that suggests otherwise.

    Using it for an establishment entry rate reproduces no published value:
    measured on Virginia's 133 counties for 2022 the median error is 9.34
    percentage points, which is larger than most of the rates themselves.
    """
    session = _Session(_payload(["ESTAB", "ESTAB_F", "state"], ["10", None, "51"]))
    _, prov = fetch_bds(year=2022, variables=["ESTAB"], session=session)
    assert "wrong denominator" in " ".join(prov.notes)


# --------------------------------------------------------------------------- #
# Transport
# --------------------------------------------------------------------------- #


def test_http_204_is_an_unpublished_cell_not_an_empty_result() -> None:
    """204 means that dimension combination is not published.

    Treating it as an empty frame turns "not published" into "zero businesses",
    which is a fabricated observation rather than a missing one.
    """
    with pytest.raises(EmptyResultError, match="not published"):
        fetch_bds(year=2022, variables=["ESTAB"], geography="county:*",
                  session=_Session(_Response(status=204)))


def test_a_missing_requested_variable_raises_rather_than_returning_a_short_frame() -> None:
    session = _Session(_payload(["ESTAB", "state"], ["10", "51"]))
    with pytest.raises(SchemaError, match="missing requested variables"):
        fetch_bds(year=2022, variables=["ESTAB", "EMP"], session=session)


def test_extra_dimensions_cannot_overwrite_the_pinned_year_or_geography() -> None:
    """Otherwise ``extra_dimensions={"YEAR": "*"}`` quietly defeats the vintage pin."""
    for name in ("YEAR", "for", "get", "key"):
        with pytest.raises(ValueError, match="may not override"):
            fetch_bds(year=2022, variables=["ESTAB"],
                      extra_dimensions={name: "*"},
                      session=_Session(_payload(["ESTAB"])))


def test_the_year_is_pinned_in_the_request_not_left_to_the_endpoint() -> None:
    session = _Session(_payload(["ESTAB", "ESTAB_F", "state"], ["1", None, "51"]))
    fetch_bds(year=1994, variables=["ESTAB"], session=session)
    assert session.calls[0]["YEAR"] == "1994"


# --------------------------------------------------------------------------- #
# The within-vintage denominator
# --------------------------------------------------------------------------- #


def test_prior_year_establishments_is_derived_within_the_vintage() -> None:
    """estabs_{t-1} = estabs_t + exits_t - entries_t, per the Census FAQ."""
    frame = pd.DataFrame({"ESTAB": [626.0, 2615.0], "ESTABS_EXIT": [60.0, 249.0],
                          "ESTABS_ENTRY": [66.0, 231.0]})
    assert list(bds_prior_year_establishments(frame)) == [620.0, 2633.0]


def test_the_derived_denominator_reproduces_a_published_rate() -> None:
    """Accomack County, Virginia, 2022, as served by the API.

    ESTAB 626, entries 66, exits 60, published entry rate 10.594. The derived
    denominator gives 10.5942..., which rounds to the published figure. The
    prior-year published file is not guaranteed to: 27 of Virginia's 133
    counties disagree with it on estabs_{t-1}.
    """
    frame = pd.DataFrame({"ESTAB": [626.0], "ESTABS_EXIT": [60.0], "ESTABS_ENTRY": [66.0]})
    prior = bds_prior_year_establishments(frame)
    rate = 100 * frame["ESTABS_ENTRY"] / (0.5 * (frame["ESTAB"] + prior))
    assert round(float(rate.iloc[0]), 3) == 10.594


@pytest.mark.parametrize("missing", ["ESTAB", "ESTABS_EXIT", "ESTABS_ENTRY"])
def test_the_denominator_helper_names_the_column_it_needs(missing: str) -> None:
    columns = {"ESTAB": [1.0], "ESTABS_EXIT": [1.0], "ESTABS_ENTRY": [1.0]}
    del columns[missing]
    with pytest.raises(SchemaError, match=missing):
        bds_prior_year_establishments(pd.DataFrame(columns))


# --------------------------------------------------------------------------- #
# Structural
# --------------------------------------------------------------------------- #


def test_the_two_variable_classes_do_not_overlap() -> None:
    """A variable cannot be both firm-level-nonadditive and noise-infused here.

    If one ever is, the provenance note would describe the same number two
    incompatible ways and the reader would have to guess which applies.
    """
    assert not (BDS_FIRM_LEVEL_VARIABLES & BDS_NOISE_INFUSED_VARIABLES)


def test_every_documented_flag_has_a_meaning_recorded() -> None:
    assert set(BDS_FLAG_MEANINGS) == {"D", "S", "X", "N"}
    assert all(BDS_FLAG_MEANINGS.values())
