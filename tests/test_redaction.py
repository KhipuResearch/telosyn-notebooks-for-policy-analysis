"""Credential redaction in surfaced error text.

A live key was echoed into a traceback during development because
``requests`` exceptions carry the request URL and both the Census and FRED APIs
take their key as a query parameter. That is audit finding F-14 (key material in
outputs) occurring inside the library rather than inside a notebook, so it is
guarded here rather than only by the notebook-output gate.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import pytest
import requests

from krl_tutorials_data import sources
from krl_tutorials_data.sources import redact

FAKE = "0123456789abcdef0123456789abcdef"


@pytest.fixture(autouse=True)
def _isolate_seen_secrets():
    before = set(sources._SEEN_SECRETS)
    yield
    sources._SEEN_SECRETS.clear()
    sources._SEEN_SECRETS.update(before)


@pytest.mark.parametrize("param", ["api_key", "key", "registrationkey", "API_KEY"])
def test_credential_query_parameters_are_scrubbed(param):
    url = f"https://example.org/data?series_id=X&{param}={FAKE}&file_type=json"
    out = redact(url)
    assert FAKE not in out
    assert "***REDACTED***" in out
    assert "series_id=X" in out, "non-credential parameters must survive"


def test_scrubbing_stops_at_the_parameter_boundary():
    out = redact(f"https://example.org/d?api_key={FAKE}&observation_start=2020-01-01")
    assert "observation_start=2020-01-01" in out
    assert FAKE not in out


def test_a_loaded_secret_is_scrubbed_even_outside_a_query_parameter():
    sources._SEEN_SECRETS.add(FAKE)
    assert FAKE not in redact(f"connection refused while presenting {FAKE} upstream")


def test_requests_exception_carrying_a_url_is_scrubbed():
    exc = requests.exceptions.ConnectionError(
        f"HTTPSConnectionPool(host='api.stlouisfed.org'): url: "
        f"/fred/series/observations?series_id=PCE&api_key={FAKE}"
    )
    out = redact(exc)
    assert FAKE not in out
    assert "api.stlouisfed.org" in out, "the useful part of the message must survive"


def test_text_without_credentials_is_unchanged():
    msg = "Census returned HTTP 400 for https://api.census.gov/data/2023/acs/acs5."
    assert redact(msg) == msg


def test_redact_accepts_non_string_objects():
    assert redact(ValueError("boom")) == "boom"
    assert redact(404) == "404"


def test_every_fetcher_redacts_its_upstream_exception():
    """Each fetcher interpolates an exception; none may do so unredacted."""
    import inspect
    src = inspect.getsource(sources)
    offenders = [
        line.strip() for line in src.splitlines()
        if "failed: {exc}" in line or "JSON: {exc}" in line
    ]
    assert not offenders, (
        "an exception is interpolated without redact(): " + "; ".join(offenders)
    )


def test_no_credential_reaches_a_raised_error(monkeypatch):
    """End to end: a transport failure must not surface the key."""
    monkeypatch.setenv("FRED_API_KEY", FAKE)

    class Boom:
        def get(self, *a, **k):
            raise requests.exceptions.ConnectionError(
                f"failed connecting to /fred?api_key={FAKE}"
            )

    with pytest.raises(sources.UpstreamError) as exc:
        sources.fetch_fred(
            series_id="PCE", start="2020-01-01", end="2020-02-01", session=Boom(),
        )
    assert FAKE not in str(exc.value)
    assert "***REDACTED***" in str(exc.value)
