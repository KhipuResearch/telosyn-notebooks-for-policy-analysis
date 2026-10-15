"""Call-site contracts for the fetchers.

A fetcher that fails deep inside itself, naming an internal variable, costs the
caller more than one that refuses the argument it was actually given. These
tests pin the refusals, not the happy paths - the happy paths need the network
and are exercised by the notebooks.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import pytest

from krl_tutorials_data import sources


def test_fetch_acs_wide_rejects_a_list_of_codes() -> None:
    """A list of variable codes must fail at the call site, not six frames deep.

    ``variables`` is a mapping of code -> the name the notebook uses. Passing a
    list reached the per-batch subset and raised ``TypeError: list indices must
    be integers``, which names nothing the caller wrote. Found while building
    the HUD FMR notebook.
    """
    with pytest.raises(TypeError) as exc:
        sources.fetch_acs_wide(
            year=2023,
            variables=["B25031_004E", "B25031_004M"],
            geography="county:*",
            within="state:*",
        )
    message = str(exc.value)
    assert "mapping" in message, "the error must say what the argument should be"
    assert "list" in message, "the error must name what was actually passed"
    assert "B25031_004E" in message, "the error must show the shape that works"


def test_fetch_acs_wide_still_rejects_an_empty_request() -> None:
    """The emptiness check must not be shadowed by the type check."""
    with pytest.raises(ValueError, match="At least one ACS variable"):
        sources.fetch_acs_wide(year=2023, variables={}, geography="state:*")


@pytest.mark.parametrize("size", [0, -1, sources.CENSUS_GET_CEILING])
def test_fetch_acs_wide_rejects_an_unusable_batch_size(size: int) -> None:
    """Batch sizes that cannot work are refused before any request is made."""
    with pytest.raises(ValueError):
        sources.fetch_acs_wide(
            year=2023,
            variables={"B25031_004E": "rent"},
            geography="state:*",
            batch_size=size,
        )
