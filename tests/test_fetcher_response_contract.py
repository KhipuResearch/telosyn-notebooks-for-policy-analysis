"""Every fetcher, against the responses that look like success and are not.

This file exists because of a mistake. HUD answered `/portal/` with HTTP 202, a
zero-length body and `x-amzn-waf-action: challenge`; it was diagnosed as an
egress block, and that wrong diagnosis reached three committed documents before
the headers were read. The sweep that followed asked what *every* fetcher here
does with such a response.

The answer was better than feared and not good enough: all five original
fetchers already tested ``status_code != 200`` rather than ``< 400``, so nothing
accepted a challenge. But ``fetch_qcew`` surfaced an empty body as pandas's
``EmptyDataError`` -- outside this module's ``DataAccessError`` hierarchy, so a
caller following the documented contract would not catch it -- and only the HUD
path named a challenge as a challenge. The others raised with the wrong cause,
which is precisely the failure that cost the afternoon.

No network: each fetcher takes a ``session``, so the response is injected.
No credentials either -- see ``_no_credential_lookup`` below.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import json
from typing import Any, Callable

import pytest

from krl_tutorials_data import sources
from krl_tutorials_data.sources import (
    WAF_ACTION_HEADERS,
    DataAccessError,
    ResponseShapeError,
    WafChallengeError,
)


@pytest.fixture(autouse=True)
def _no_credential_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub credential lookup so these tests measure what they claim to.

    Every keyed fetcher calls ``load_key`` on the way to the request, *before*
    the injected session is ever reached. Without this, a machine with no
    ``~/.krl/secrets.env`` sees fifteen of these raise ``MissingCredentialError``
    -- red for a reason that has nothing to do with firewall handling, and green
    only where a live key happens to exist. That is the whole defect this file
    was written to catch, reproduced in the file itself.

    CI's static lane holds no secrets by design; the four keys live in the
    ``notebook-release`` environment that only the execution lane uses. So the
    stub is not a convenience -- it is what makes this a unit test.
    """
    monkeypatch.setattr(
        sources, "load_key", lambda name, **_: f"stub-{name.lower()}-not-a-credential"
    )


class _Response:
    """The minimum of ``requests.Response`` these fetchers touch."""

    def __init__(
        self,
        *,
        status: int = 200,
        body: bytes = b"",
        headers: dict[str, str] | None = None,
        content_type: str = "application/json",
    ) -> None:
        self.status_code = status
        self.content = body
        self.headers = {"content-type": content_type, **(headers or {})}

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", "replace")

    def json(self) -> Any:
        return json.loads(self.text)


class _Session:
    """A session that answers every request with one canned response."""

    def __init__(self, response: _Response) -> None:
        self._response = response

    def get(self, *args: Any, **kwargs: Any) -> _Response:
        return self._response

    def post(self, *args: Any, **kwargs: Any) -> _Response:
        return self._response


#: One call per fetcher, with arguments valid enough to reach the request.
FETCHERS: dict[str, Callable[[_Session], Any]] = {
    "fetch_acs": lambda s: sources.fetch_acs(
        year=2023, variables={"B01003_001E": "pop"}, geography="state:*", session=s
    ),
    "fetch_acs_pums": lambda s: sources.fetch_acs_pums(
        year=2023, variables={"AGEP": "Age"}, aggregate_by=["AGEP"],
        geography="state:51", session=s
    ),
    "fetch_fred": lambda s: sources.fetch_fred(
        series_id="PCE", start="2020-01-01", end="2020-06-01", session=s
    ),
    "fetch_bls": lambda s: sources.fetch_bls(
        series=["LAUST010000000000003"], start_year=2020, end_year=2021, session=s
    ),
    "fetch_qcew": lambda s: sources.fetch_qcew(
        year=2024, quarter=1, area="51059", session=s
    ),
    "fetch_cbp": lambda s: sources.fetch_cbp(
        year=2022, variables={"EMP": "emp"}, geography="county:*", within="state:51", session=s
    ),
    "fetch_bds": lambda s: sources.fetch_bds(
        year=2022, variables=["ESTAB"], geography="state:*", session=s
    ),
    "fetch_bea_regional": lambda s: sources.fetch_bea_regional(
        table="SAACArtsVA", line_code="10", year=2023, geo_fips="00000", session=s
    ),
    "fetch_social_capital_atlas": lambda s: sources.fetch_social_capital_atlas(
        geography="county", session=s
    ),
    "fetch_fbi_cde_agencies": lambda s: sources.fetch_fbi_cde_agencies(
        state="PA", session=s
    ),
    "fetch_tri_releases": lambda s: sources.fetch_tri_releases(
        state="VA", reporting_year=2022, session=s
    ),
    "fetch_dataverse_file": lambda s: sources.fetch_dataverse_file(
        doi="doi:10.7910/DVN/42MVDX", filename="1976-2024-president.csv", session=s
    ),
    "fetch_food_environment_atlas": lambda s: sources.fetch_food_environment_atlas(
        sheet="ACCESS", session=s
    ),
    "fetch_irs_bmf": lambda s: sources.fetch_irs_bmf(regions=["eo1"], session=s),
    "_hud_get": lambda s: sources._hud_get("fmr/data/5100199999?year=2027", session=s),
}

CHALLENGES = {
    "aws waf, 202": _Response(status=202, headers={"x-amzn-waf-action": "challenge"}),
    "aws waf, 200": _Response(status=200, headers={"x-amzn-waf-action": "challenge"}),
    "cloudflare": _Response(status=200, headers={"cf-mitigated": "challenge"}),
}


@pytest.mark.parametrize("fetcher", sorted(FETCHERS))
@pytest.mark.parametrize("kind", sorted(CHALLENGES))
def test_a_firewall_challenge_is_named_as_one(fetcher: str, kind: str) -> None:
    """Failing is not enough. The error must name the actual cause.

    A challenge reported as "returned HTML rather than JSON" sends the reader to
    debug a parser, and a challenge reported as a network failure sends them to
    debug a proxy. Both are wrong and both waste the same afternoon.
    """
    with pytest.raises(WafChallengeError) as exc:
        FETCHERS[fetcher](_Session(CHALLENGES[kind]))
    message = str(exc.value)
    assert "firewall" in message.lower()
    assert "status code may be 2xx" in message, (
        "the message must warn that a challenge does not arrive as a failure"
    )


@pytest.mark.parametrize("fetcher", sorted(FETCHERS))
def test_an_empty_body_stays_inside_the_error_hierarchy(fetcher: str) -> None:
    """An empty 200 must raise a DataAccessError, not a library's own exception.

    ``fetch_qcew`` raised ``pandas.errors.EmptyDataError`` here. Callers are told
    to catch ``DataAccessError``; anything outside it escapes their handling and
    surfaces as an unrelated traceback.
    """
    with pytest.raises(DataAccessError):
        FETCHERS[fetcher](_Session(_Response(status=200, body=b"")))


@pytest.mark.parametrize("fetcher", sorted(FETCHERS))
def test_no_fetcher_treats_a_non_200_success_code_as_data(fetcher: str) -> None:
    """202, 204 and 206 are successes that carry no usable body here.

    The guard is ``status_code != 200``. If any fetcher is ever relaxed to
    ``< 400``, this fails.
    """
    for status in (202, 204, 206):
        with pytest.raises(DataAccessError):
            FETCHERS[fetcher](_Session(_Response(status=status, body=b"")))


def test_the_challenge_check_is_reached_by_every_fetcher() -> None:
    """Structural: a new fetcher must not be able to skip the check silently."""
    import inspect

    entry_points = {
        name: inspect.getsource(getattr(sources, name))
        for name in dir(sources)
        if name.startswith(("fetch_", "_hud_get")) and callable(getattr(sources, name))
    }
    # A function is covered if it calls the check itself, or if it delegates to one
    # that does. An allowlist of "these ones are fine" was the first version of this
    # test and it went stale the moment a fetcher was added, which is the failure
    # mode a structural test is supposed to avoid.
    #
    # Guards are discovered across EVERY module-level callable, not only the
    # fetch_* entry points. Restricting the search by name was a second, quieter
    # version of the same staleness: `fetch_fbi_cde_agencies` delegates to
    # `_cde_get`, which does call the check, and the test reported it as unguarded
    # because the helper's name did not match the prefix it happened to look for.
    # The protection is unchanged; the discovery no longer depends on naming.
    module_callables = {
        name: inspect.getsource(getattr(sources, name))
        for name in dir(sources)
        if callable(getattr(sources, name, None))
        and getattr(getattr(sources, name, None), "__module__", None) == sources.__name__
    }
    guards = {n for n, body in module_callables.items() if "reject_bot_challenge" in body}
    assert guards, "nothing calls reject_bot_challenge; the check is unreachable"

    # Delegation is followed TRANSITIVELY, not one hop. `fetch_mit_president`
    # delegates to `fetch_dataverse_file`, which delegates to `_dataverse_get`,
    # which is where the check lives -- and a one-hop version of this test
    # reported the entry point as unguarded. That is the third time discovery in
    # this test has been too narrow (an allowlist, then a name prefix, now a
    # single hop), so it is now a closure and stops being a question.
    covered = set(guards)
    changed = True
    while changed:
        changed = False
        for name, body in module_callables.items():
            if name in covered:
                continue
            if any(f"{target}(" in body for target in covered):
                covered.add(name)
                changed = True

    for name, body in entry_points.items():
        assert name in covered, (
            f"{name} neither calls reject_bot_challenge nor reaches a function "
            f"that does, by any chain of module-level calls, so a firewall "
            f"response would be reported with the wrong cause. Functions that "
            f"check directly: {sorted(guards)}"
        )
    assert "x-amzn-waf-action" in WAF_ACTION_HEADERS
    assert "cf-mitigated" in WAF_ACTION_HEADERS
    assert issubclass(WafChallengeError, ResponseShapeError)
