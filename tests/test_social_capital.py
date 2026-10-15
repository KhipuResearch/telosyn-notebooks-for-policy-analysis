"""The Social Capital Atlas client, and the absence a file cannot report.

This is the corpus's first source protected by formal differential privacy with
a published budget, and the first whose standard error is documented as holding
statistical and disclosure error in the same number. Two consequences drive
these tests.

**Part of the published uncertainty is a policy parameter.** Epsilon is a choice.
A different choice would have produced a different standard error for the same
underlying network, and nothing in the file distinguishes that component from
sampling error. The client cannot fix this; it can refuse to let it go
unrecorded.

**The minimum-cell-size rule removes units before publication.** A file with
23,028 rows cannot tell you that 6,034 were dropped -- absences leave no trace
in the artifact that survived them. The universe counts therefore live in the
module, from the release README, and provenance reports the difference.

No network: every test drives the argument contract or a canned payload.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from krl_tutorials_data.sources import (
    SOCIAL_CAPITAL_PRIVACY,
    SOCIAL_CAPITAL_RESOURCES,
    SOCIAL_CAPITAL_UNIVERSE,
    SOCIAL_CAPITAL_UNIVERSE_NOTE,
    SOCIAL_CAPITAL_VINTAGE,
    EmptyResultError,
    ResponseShapeError,
    UpstreamError,
    WafChallengeError,
    fetch_social_capital_atlas,
)

CSV = (
    b"county,county_name,num_below_p50,pop2018,ec_county,ec_se_county,clustering_county\n"
    b'1001,"Autauga, Alabama",5922.39,55200,.72077,.00831,.1\n'
    b'1003,"Baldwin, Alabama",1000.0,20000,,,.2\n'
)


class _Response:
    def __init__(self, *, status: int = 200, body: bytes = b"",
                 headers: dict[str, str] | None = None) -> None:
        self.status_code = status
        self.content = body
        self.headers = {"content-type": "text/csv", **(headers or {})}

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", "replace")


class _Session:
    def __init__(self, response: _Response) -> None:
        self._response = response
        self.calls: list[tuple[Any, ...]] = []

    def get(self, *args: Any, **kwargs: Any) -> _Response:
        self.calls.append(args)
        return self._response


# --------------------------------------------------------------------------- #
# Scope
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("geography", ["state", "tract", "", "County", "counties"])
def test_an_unknown_geography_is_refused(geography: str) -> None:
    with pytest.raises(ValueError, match="not a Social Capital Atlas geography"):
        fetch_social_capital_atlas(geography=geography, session=_Session(_Response(body=CSV)))


def test_all_four_published_geographies_are_reachable() -> None:
    assert set(SOCIAL_CAPITAL_RESOURCES) == {"county", "zip", "college", "high_school"}
    assert set(SOCIAL_CAPITAL_UNIVERSE) == set(SOCIAL_CAPITAL_RESOURCES)
    for resource_id, filename in SOCIAL_CAPITAL_RESOURCES.values():
        assert len(resource_id) == 36, "resource ids are pinned UUIDs, not scraped"
        assert filename.endswith(".csv")


def test_the_universe_counts_match_the_release_readme() -> None:
    """These are the only record of what the cell-size rule removed.

    The published files hold 3,089 / 23,028 / 2,586 / 17,525 rows. Subtracting
    from these universes reproduces the README's stated exclusions exactly --
    7 counties, 6,034 ZIPs, 87 colleges, 3,958 high schools. Pinned so a typo
    here cannot silently understate a suppression rate in a notebook.
    """
    assert SOCIAL_CAPITAL_UNIVERSE == {
        "county": 3096, "zip": 29062, "college": 2673, "high_school": 21483,
    }
    assert SOCIAL_CAPITAL_UNIVERSE["zip"] - 23028 == 6034
    assert SOCIAL_CAPITAL_UNIVERSE["high_school"] - 17525 == 3958
    assert SOCIAL_CAPITAL_UNIVERSE["college"] - 2586 == 87
    assert SOCIAL_CAPITAL_UNIVERSE["county"] - 3089 == 7


# --------------------------------------------------------------------------- #
# The firewall, which answers with a success code
# --------------------------------------------------------------------------- #


def test_a_waf_challenge_is_named_as_one() -> None:
    session = _Session(_Response(status=202, headers={"x-amzn-waf-action": "challenge"}))
    with pytest.raises(WafChallengeError):
        fetch_social_capital_atlas(geography="county", session=session)


def test_an_empty_body_is_reported_as_a_firewall_response_not_an_empty_dataset() -> None:
    """HDX answers a challenged request with a zero-length 2xx body.

    Read as data, that is a geography with no social capital anywhere in it.
    The message has to send the reader to the network rather than to the parser.
    """
    with pytest.raises(ResponseShapeError, match="firewall response"):
        fetch_social_capital_atlas(geography="county", session=_Session(_Response(body=b"")))


@pytest.mark.parametrize("body", [b"<!doctype html><html>", b'{"error": "nope"}'])
def test_markup_or_json_instead_of_csv_raises(body: bytes) -> None:
    with pytest.raises(ResponseShapeError, match="markup rather than CSV"):
        fetch_social_capital_atlas(geography="county", session=_Session(_Response(body=body)))


def test_a_non_200_status_raises() -> None:
    with pytest.raises(UpstreamError, match="HTTP 503"):
        fetch_social_capital_atlas(
            geography="county", session=_Session(_Response(status=503, body=CSV))
        )


def test_a_csv_with_only_a_header_raises_rather_than_returning_nothing() -> None:
    header_only = CSV.split(b"\n")[0] + b"\n"
    with pytest.raises(EmptyResultError, match="zero rows"):
        fetch_social_capital_atlas(
            geography="county", session=_Session(_Response(body=header_only))
        )


# --------------------------------------------------------------------------- #
# The two kinds of absence
# --------------------------------------------------------------------------- #


def test_a_withheld_estimate_stays_nan_and_never_becomes_zero() -> None:
    """Zero is a real value of economic connectedness: it means no cross-class
    friendships at all. A suppressed cell read as zero is the strongest possible
    finding manufactured out of a disclosure rule."""
    frame, _ = fetch_social_capital_atlas(geography="county", session=_Session(_Response(body=CSV)))
    assert pd.isna(frame["ec_county"].iloc[1])
    assert frame["ec_county"].notna().sum() == 1
    assert (frame["ec_county"] == 0).sum() == 0


def test_provenance_reports_the_units_removed_before_publication() -> None:
    """The count cannot come from the file. It has to come from the README."""
    _, prov = fetch_social_capital_atlas(geography="county", session=_Session(_Response(body=CSV)))
    joined = " ".join(prov.notes)
    assert "cannot report its own absences" in joined
    assert "3,096" in joined


def test_provenance_separates_removed_rows_from_blank_estimates() -> None:
    _, prov = fetch_social_capital_atlas(geography="county", session=_Session(_Response(body=CSV)))
    joined = " ".join(prov.notes)
    assert "Empty estimates present in the file" in joined
    assert "ec_county=1" in joined
    assert "never zero" in joined


# --------------------------------------------------------------------------- #
# The regime itself
# --------------------------------------------------------------------------- #


def test_provenance_records_that_the_standard_error_is_not_only_statistical() -> None:
    """The single most consequential documented fact about this source.

    Everywhere else in the corpus a published uncertainty is a property of a
    sample. Here it also contains a term set by a policy choice about epsilon,
    and the two arrive added together.
    """
    _, prov = fetch_social_capital_atlas(geography="county", session=_Session(_Response(body=CSV)))
    joined = " ".join(prov.notes)
    assert "epsilon = 8" in joined
    assert "both sampling error and error from the addition of noise" in joined
    assert "cannot be separated" in joined


def test_the_privacy_note_explains_why_the_components_cannot_be_split() -> None:
    assert "degree distribution" in SOCIAL_CAPITAL_PRIVACY
    assert "not published" in SOCIAL_CAPITAL_PRIVACY


def test_the_universe_is_described_as_a_platform_not_a_population() -> None:
    assert "platform universe, not a demographic one" in SOCIAL_CAPITAL_UNIVERSE_NOTE
    assert "no user count is published" in SOCIAL_CAPITAL_UNIVERSE_NOTE


def test_provenance_states_that_one_is_parity() -> None:
    """EC is a ratio scaled so that 1.0 is parity. Read as a share it is
    nonsense above 1.0, and values above 1.0 are common."""
    _, prov = fetch_social_capital_atlas(geography="county", session=_Session(_Response(body=CSV)))
    assert "1.0 is parity" in " ".join(prov.notes)


def test_the_vintage_names_the_snapshot_date_not_only_the_release() -> None:
    """The network was observed on one day. That is the reference period, and it
    is not the release date."""
    assert "2022-05-28" in SOCIAL_CAPITAL_VINTAGE
    _, prov = fetch_social_capital_atlas(geography="county", session=_Session(_Response(body=CSV)))
    assert SOCIAL_CAPITAL_VINTAGE in " ".join(prov.notes)


def test_provenance_records_that_redistribution_is_permitted() -> None:
    """Different from D10's source, and the difference is worth not re-deriving.

    Opportunity Insights' files carry no verified redistribution licence, so D10
    keeps them uncommitted. Meta's licence here permits redistribution. The
    runtime fetch is retained for provenance, and provenance says so.
    """
    _, prov = fetch_social_capital_atlas(geography="county", session=_Session(_Response(body=CSV)))
    joined = " ".join(prov.notes)
    assert "permits use and redistribution" in joined
    assert "provenance choice, not a licence constraint" in joined
