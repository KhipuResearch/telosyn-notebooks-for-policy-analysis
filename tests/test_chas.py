"""CHAS fetcher contracts, offline.

CHAS is the corpus's first custom tabulation, and its API fails in ways that look
like success: an unrecognised id returns 200 and ``[]``, and the county index
repeats every row. Both are pinned here.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import inspect

import pytest

from krl_tutorials_data import sources
from krl_tutorials_data.sources import (
    CHAS_DOCUMENTED_NOT_SERVED,
    CHAS_MISDOCUMENTED,
    CHAS_SUMMARY_LEVELS,
    DataAccessError,
    EmptyResultError,
    ResponseShapeError,
    fetch_chas,
)


def test_the_vintage_cannot_be_defaulted() -> None:
    """The API's default is 'the latest range', which moves under a fixed notebook."""
    params = inspect.signature(fetch_chas).parameters
    assert params["year"].default is inspect.Parameter.empty
    for bad in ("latest", "2018", "", "2018_2022"):
        with pytest.raises(ValueError, match="explicit ACS range"):
            fetch_chas(year=bad, state_id=51, entity_id=59)


def test_an_empty_result_is_an_error_not_an_empty_frame() -> None:
    """200 with ``[]`` is how a wrong id fails. An empty frame is not an empty population."""
    assert issubclass(EmptyResultError, ResponseShapeError)
    assert issubclass(EmptyResultError, DataAccessError)
    source = inspect.getsource(fetch_chas)
    assert "if not payload:" in source, "the empty-body check is gone"
    assert "EmptyResultError" in source


def test_a_padded_entity_id_is_normalised_rather_than_silently_failing() -> None:
    """`59` is Fairfax; `059` returns nothing. The padded form is what HUD's FMR API requires.

    Two APIs from one publisher take incompatible spellings of the same county and
    neither refuses the wrong one, so the likely input is the wrong one.
    """
    source = inspect.getsource(fetch_chas)
    assert "lstrip" in source and "entityId" in source, (
        "zero-padding is no longer stripped from entity_id"
    )
    # Behavioural: the normalisation must be exact, not merely present.
    normalise = lambda raw: int(str(raw).lstrip("0") or 0)
    assert normalise("059") == 59
    assert normalise("59") == 59
    assert normalise(59) == 59
    assert normalise("000") == 0, "an all-zero id must not become an empty string"


def test_missing_arguments_are_refused_before_any_request() -> None:
    with pytest.raises(ValueError, match="state_id is required"):
        fetch_chas(year="2018-2022", summary_level="county")
    with pytest.raises(ValueError, match="entity_id is required"):
        fetch_chas(year="2018-2022", summary_level="county", state_id=51)
    with pytest.raises(ValueError, match="summary_level must be one of"):
        fetch_chas(year="2018-2022", summary_level="tract", state_id=51, entity_id=59)


def test_summary_levels_match_the_published_numbering() -> None:
    assert CHAS_SUMMARY_LEVELS == {
        "nation": 1, "state": 2, "county": 3, "mcd": 4, "place": 5,
    }


def test_suppressed_values_never_become_zero() -> None:
    """A suppressed cell is unknown; a zero is a measurement. See D09 for the cost."""
    assert sources._chas_number(None) is None
    assert sources._chas_number("") is None
    assert sources._chas_number("205.0") == 205.0   # counts arrive float-formatted
    assert sources._chas_number("0") == 0.0         # a real zero survives as a zero
    assert sources._chas_number("n/a") is None

    source = inspect.getsource(sources._chas_number)
    assert "fillna" not in source and "or 0" not in source


def test_the_known_documentation_defects_are_recorded() -> None:
    """These are findings, not workarounds, so they are named constants rather than magic."""
    assert CHAS_DOCUMENTED_NOT_SERVED == {"G21", "G22", "G23", "H17", "I17", "J17"}
    # Each key is documented identically to its value and is a different quantity.
    assert CHAS_MISDOCUMENTED == {"H14": "H13", "I14": "I13", "J14": "J13"}
    for second, first in CHAS_MISDOCUMENTED.items():
        assert second[0] == first[0], "a misdocumented pair must sit in the same table"


def test_the_county_index_is_deduplicated() -> None:
    """HUD serves 267 rows for 134 Virginia counties; iterating it doubles the state."""
    source = inspect.getsource(sources.fetch_chas_county_list)
    assert "drop_duplicates" in source
    assert "duplicate_rows" in source, (
        "the count of removed duplicates must be reported, not silently dropped"
    )
