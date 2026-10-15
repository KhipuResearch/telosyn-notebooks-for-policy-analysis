"""HUD Fair Market Rents fetcher — contracts that must hold without a network.

The HUD path introduced two things the other fetchers did not have: a credential
carried in a header rather than a query parameter, and a publisher whose bot
defence answers with a **success** status code. Both are pinned here.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import inspect

import pytest

from krl_tutorials_data import sources
from krl_tutorials_data.sources import (
    ALLOWED_KEYS,
    DataAccessError,
    DisallowedCredentialError,
    HUD_BEDROOMS,
    HUD_WAF_HEADER,
    ResponseShapeError,
    WafChallengeError,
    fetch_hud_fmr_county,
)


def test_hud_key_is_allowed_and_the_allowlist_is_still_closed() -> None:
    """Adding one public-data key must not open the operator's secrets file.

    The allowlist exists because that file also holds database URLs and admin
    tokens. Widening it by one name is a decision; widening it by accident is
    the failure it was built to prevent.

    The set is pinned by equality rather than by membership, so every addition
    fails this test until someone writes the new name here on purpose. That is
    the whole mechanism: the guard is not the allowlist, it is the requirement
    that widening the allowlist be a deliberate, reviewed edit.

    Six entries, each a public-data key and nothing else:

    * ``DATA_GOV_API_KEY`` is the newest. api.data.gov issues one key that
      authenticates across every participating agency, so a single name covers
      the FBI Crime Data Explorer and any other api.data.gov-fronted source the
      corpus reaches later. It is named for the issuer rather than for one
      agency precisely so that the next addition needs no new key at all.
    """
    assert "HUD_API_KEY" in ALLOWED_KEYS
    assert "DATA_GOV_API_KEY" in ALLOWED_KEYS
    assert ALLOWED_KEYS == {
        "CENSUS_API_KEY", "FRED_API_KEY", "BLS_API_KEY", "BEA_API_KEY", "HUD_API_KEY",
        "DATA_GOV_API_KEY",
    }
    assert all(name.endswith("_API_KEY") for name in ALLOWED_KEYS), (
        "every allowlisted name must read as a public-data API key; a database "
        "URL or a token reaching this set is the failure mode it exists to stop"
    )
    for forbidden in ("DATABASE_URL", "PAX_ADMIN_DATABASE_URL", "OPENAI_API_KEY"):
        with pytest.raises(DisallowedCredentialError):
            sources.load_key(forbidden)


def test_a_waf_challenge_is_an_error_not_a_result() -> None:
    """202 is a success code. The challenge must still fail closed.

    HUD's ``/portal/`` paths answer a non-browser client with HTTP 202, a
    zero-length body and ``x-amzn-waf-action: challenge``. A pipeline testing
    ``status_code < 400`` accepts that and parses an empty body, which is the
    same class of trap as the Census 200-plus-HTML page. This was mistaken for
    an egress block during the D05 build before the headers were read.
    """
    assert issubclass(WafChallengeError, ResponseShapeError)
    assert issubclass(WafChallengeError, DataAccessError)
    assert HUD_WAF_HEADER == "x-amzn-waf-action"

    # The check began here and was promoted to `reject_bot_challenge`, which every
    # fetcher now calls. Assert the behaviour, not the implementation that carried
    # it: this test previously named the inline block and broke when it moved,
    # while the protection itself was intact the whole time.
    assert "reject_bot_challenge" in inspect.getsource(sources._hud_get), (
        "the challenge check is no longer reached; a 202 would be read as data"
    )
    with pytest.raises(WafChallengeError):
        sources.reject_bot_challenge(
            _FirewallResponse(), source="HUD USER", endpoint="fmr/data/x"
        )


class _FirewallResponse:
    """A WAF challenge exactly as HUD sends it: 202, no body, one header."""

    status_code = 202
    content = b""
    headers = {"x-amzn-waf-action": "challenge"}


def test_the_fiscal_year_cannot_be_omitted() -> None:
    """HUD defaults to the current schedule, so an un-pinned call drifts.

    Same defect ``fetch_fred`` refuses an open date range for: the call returns
    different numbers after October 1 with no change to the code.
    """
    params = inspect.signature(fetch_hud_fmr_county).parameters
    assert params["year"].default is inspect.Parameter.empty, (
        "`year` acquired a default; an un-pinned HUD call silently changes "
        "schedule at the start of each federal fiscal year"
    )
    assert params["year"].kind is inspect.Parameter.KEYWORD_ONLY


def test_an_empty_entity_id_is_refused_before_any_request() -> None:
    with pytest.raises(ValueError, match="entity id"):
        fetch_hud_fmr_county(fips="   ", year=2027)


def test_bedroom_mapping_is_ordered_and_matches_the_bulk_file_columns() -> None:
    """The API's bedroom labels must land in the same columns as HUD's own CSVs."""
    assert [col for _, col in HUD_BEDROOMS] == [f"fmr_{b}" for b in range(5)]
    assert [key for key, _ in HUD_BEDROOMS] == [
        "Efficiency", "One-Bedroom", "Two-Bedroom", "Three-Bedroom", "Four-Bedroom",
    ]


def test_small_area_metros_are_refused_rather_than_averaged() -> None:
    """For a SAFMR metro there is no county figure, and inventing one is the bug."""
    src = inspect.getsource(fetch_hud_fmr_county)
    assert "isinstance(basic, list)" in src, "the Small Area FMR shape is no longer detected"
    assert "mean" not in src and "average" not in src.lower().replace("averaging", ""), (
        "a Small Area FMR metro must not be collapsed to a single county number"
    )


def test_the_credential_never_reaches_raised_text() -> None:
    """HUD's token rides in a header, so the URL is safe and the headers are not."""
    src = inspect.getsource(sources._hud_get)

    # The request headers dict is the object that holds the Bearer token. It must
    # never be formatted into any message, redacted or not.
    assert "{headers" not in src and "headers!r" not in src, (
        "the request headers dict, which carries the Bearer token, is interpolated "
        "into a message"
    )

    # An upstream exception can carry the request, so it is redacted or absent.
    unredacted = [
        line.strip() for line in src.splitlines()
        if "{exc}" in line and "redact" not in line
    ]
    assert not unredacted, (
        "an upstream exception is interpolated into raised text without redact():\n  "
        + "\n  ".join(unredacted)
    )

    # Named non-credential response headers are fine and are what the rate-limit
    # message reports; this records that the distinction is deliberate.
    assert "x-ratelimit-limit" in src, (
        "the rate-limit budget is no longer surfaced, so a quota failure would be "
        "discovered by hitting it"
    )
