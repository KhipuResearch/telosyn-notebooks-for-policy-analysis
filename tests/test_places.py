"""The PLACES fetcher's contract, including the traps it exists to remove.

PLACES is the corpus's first MODELLED source, and three of its behaviours are
easy to get wrong in ways that produce a plausible wrong number rather than an
error: the interval ships as a string with a leading space, crude and
age-adjusted prevalence answer different questions under near-identical column
names, and each release year is a separate dataset so "latest" is a choice
someone has to make explicitly.

No network: every test here drives the parser or the argument contract.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import math

import pytest

from krl_tutorials_data import sources
from krl_tutorials_data.sources import (
    PLACES_COUNTY_RELEASES,
    parse_places_interval,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("( 8.8, 11.3)", (8.8, 11.3)),      # the real shape, leading space included
        ("(8.8, 11.3)", (8.8, 11.3)),
        ("( 0.0, 100.0)", (0.0, 100.0)),
        ("(-1.5, 2.25)", (-1.5, 2.25)),
    ],
)
def test_an_interval_parses_whatever_the_spacing(text: str, expected: tuple[float, float]) -> None:
    assert parse_places_interval(text) == expected


@pytest.mark.parametrize("text", [None, "", "no numbers here", "( 8.8)", float("nan"), 12.0])
def test_an_unparseable_interval_is_nan_not_a_guess(text: object) -> None:
    """Returning NaN keeps the cell missing. Returning a partial bound would put
    a fabricated number into a confidence interval, which is worse than missing."""
    lo, hi = parse_places_interval(text)
    assert math.isnan(lo) and math.isnan(hi)


def test_position_slicing_fails_silently_and_that_is_why_this_parser_exists() -> None:
    """The trap, stated as a test.

    A fixed slice tuned on a one-digit lower bound keeps working -- wrongly --
    when the bound has two digits. It does not raise; it truncates. That is the
    dangerous failure, because a prevalence of 11.3 silently becomes 11.0 and
    every downstream interval is narrowed by three-tenths of a point.
    """
    assert float("( 8.8, 11.3)"[1:5]) == 8.8       # tuned here, looks correct
    assert float("( 11.3, 14.2)"[1:5]) == 11.0     # same slice, silently truncated
    assert parse_places_interval("( 11.3, 14.2)")[0] == 11.3  # the parser does not


def test_release_must_be_named_and_known() -> None:
    with pytest.raises(ValueError, match="release must be one of"):
        sources.fetch_places_county(measures=["diabetes"], release="latest")
    with pytest.raises(ValueError, match="release must be one of"):
        sources.fetch_places_county(measures=["diabetes"], release="2019")


def test_every_declared_release_is_a_distinct_asset() -> None:
    """A copy-paste in the release map would silently pin the wrong vintage."""
    assets = list(PLACES_COUNTY_RELEASES.values())
    assert len(assets) == len(set(assets)), f"duplicate asset id in {PLACES_COUNTY_RELEASES}"


def test_adjustment_must_be_chosen_explicitly() -> None:
    """Crude and age-adjusted are different questions, not different precisions."""
    with pytest.raises(ValueError, match="adjustment must be"):
        sources.fetch_places_county(measures=["diabetes"], adjustment="age-adjusted")
    with pytest.raises(ValueError, match="adjustment must be"):
        sources.fetch_places_county(measures=["diabetes"], adjustment="")


def test_an_empty_measure_list_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one PLACES measure"):
        sources.fetch_places_county(measures=[])


def test_places_needs_no_credential() -> None:
    """PLACES is public. It must not appear in the keyed-source machinery, or a
    notebook using only PLACES would demand a key it never needs."""
    assert "PLACES_API_KEY" not in sources.ALLOWED_KEYS
    assert "CDC_API_KEY" not in sources.ALLOWED_KEYS
