"""Fail-closed clients for authoritative public data.

Design contract
---------------
1. **Real data only.** There is no synthetic generator and no fallback path in
   this module. If a fetch cannot be completed and validated, it raises. A
   notebook that cannot get real data does not get data.
2. **No bare excepts.** Every failure mode is named and surfaced.
3. **Status codes are not trusted.** ``api.census.gov`` returns ``HTTP 200``
   with an HTML "Missing Key" page when the key is absent. Content-type and
   body shape are validated, not the status line.
4. **Sentinels are not numbers.** ACS encodes suppressed or unavailable
   estimates as large negative jam values. They become NaN, never figures.
5. **Vintages are pinned.** No caller may request "latest".
6. **Secrets are never logged.** Keys are read from the environment or from a
   secrets file and are never printed, echoed, or written to a notebook output.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import hashlib
import io
import json
import time
from collections import deque
import re
import os
from pathlib import Path
from urllib.parse import urlencode
from typing import Any, Final, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
import requests

from .provenance import DataProvenance, canonical_rows, canonical_stable_json, ledgered

# --------------------------------------------------------------------------- #
# Errors — each failure mode is distinguishable by type.
# --------------------------------------------------------------------------- #


class DataAccessError(RuntimeError):
    """Base class. A notebook that sees this must stop, not substitute."""


class MissingCredentialError(DataAccessError):
    """A required API key was not found. Never contains the key."""


class UpstreamError(DataAccessError):
    """The source returned a transport-level or documented API failure."""


class ResponseShapeError(DataAccessError):
    """The source returned 200 but the body is not the documented payload.

    This is the ``HTTP 200`` + HTML "Missing Key" case, and any other instance
    of a success status carrying a non-payload body.
    """


class SchemaError(DataAccessError):
    """The payload parsed but does not contain the columns that were requested."""


class RangeError(DataAccessError):
    """A value fell outside a stated plausible range for its variable."""


# --------------------------------------------------------------------------- #
# Credentials
# --------------------------------------------------------------------------- #

# Least privilege. The secrets file a reader points us at may hold far more than
# public-data API keys — database URLs, admin tokens, third-party credentials.
# This layer may read ONLY the keys the tutorial corpus actually needs, so that a
# tutorial kernel structurally cannot reach anything else in that file, whatever
# it is asked for.
ALLOWED_KEYS: Final[frozenset[str]] = frozenset({
    "CENSUS_API_KEY",   # U.S. Census Bureau (ACS, CBP, ...)
    "FRED_API_KEY",     # Federal Reserve Bank of St. Louis
    "BLS_API_KEY",      # Bureau of Labor Statistics
    "BEA_API_KEY",      # Bureau of Economic Analysis
    "HUD_API_KEY",      # HUD USER (Fair Market Rents, Income Limits)
    "DATA_GOV_API_KEY",  # api.data.gov: one key, every participating agency (FBI CDE)
})


#: Where a reader registers for each key. Free, and the only way to obtain one: this repository
#: stores and uses no key of its own, and nothing is read from a default location. The
#: addresses are the ones listed in ``.env.example``; a test holds the two together.
KEY_REGISTRATION: Final[dict[str, str]] = {
    "CENSUS_API_KEY": "https://api.census.gov/data/key_signup.html",  # pragma: allowlist secret
    "FRED_API_KEY": "https://fred.stlouisfed.org/docs/api/api_key.html",  # pragma: allowlist secret
    "BLS_API_KEY": "https://data.bls.gov/registrationEngine/",  # pragma: allowlist secret
    "BEA_API_KEY": "https://apps.bea.gov/API/signup/",  # pragma: allowlist secret
    "HUD_API_KEY": "https://www.huduser.gov/portal/dataset/fmr-api.html",  # pragma: allowlist secret
    "DATA_GOV_API_KEY": "https://api.data.gov/signup/",  # pragma: allowlist secret
}


class DisallowedCredentialError(DataAccessError):
    """A key outside :data:`ALLOWED_KEYS` was requested.

    Raised before any key file is opened, so a disallowed name is never
    matched against its contents.
    """


def secrets_path() -> Path | None:
    """The key file the reader named, or ``None``.

    There is **no default location**. A key file is read only when the reader sets
    ``KRL_SECRETS_PATH`` to a file of their own; otherwise keys come from the
    environment alone. Nothing under a home directory is ever opened unprompted.
    """
    if (override := os.environ.get("KRL_SECRETS_PATH")):
        return Path(override)
    return None


def load_key(name: str, *, path: Path | None = None) -> str:
    """Return an API key from the environment or from the reader's own key file.

    Order: the environment variable ``name``; then, only if ``KRL_SECRETS_PATH`` is
    set (or ``path`` is passed), that file. The key is returned to the caller for use
    in a request and is never logged. Raises :class:`MissingCredentialError` naming
    the *variable* and where to register for it, never a value, so that a traceback in
    a shared notebook cannot leak material.

    .. note::
       A key file should hold only the six names in :data:`ALLOWED_KEYS`. The
       allowlist stops this library asking for anything else, but it cannot stop
       another process in the same kernel from opening a file that holds more.
    """
    if name not in ALLOWED_KEYS:
        raise DisallowedCredentialError(
            f"{name} is not in the tutorial corpus's allowlist "
            f"({', '.join(sorted(ALLOWED_KEYS))}). No key file was opened. "
            f"Tutorials read only the public-data keys they need; anything else in "
            f"a file — database URLs, admin tokens — is out of reach by design."
        )
    if (val := os.environ.get(name)):
        _SEEN_SECRETS.add(val)
        return val
    path = path or secrets_path()
    if path is not None and path.exists():
        # Stream the file and stop at the first match: no non-matching line is
        # retained, and nothing beyond the requested key is parsed.
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                if k.strip() == name:
                    _value = v.strip().strip('"').strip("'")
                    _SEEN_SECRETS.add(_value)
                    return _value
    where = (
        f"the file KRL_SECRETS_PATH names does not define it"
        if path is not None else "KRL_SECRETS_PATH is not set"
    )
    raise MissingCredentialError(
        f"{name} is not set ({where}). Set {name} in your environment — register for a "
        f"free key at {KEY_REGISTRATION[name]} — or set KRL_SECRETS_PATH to a file of your "
        "own that defines it. No key is read from any other location. "
        "This tutorial uses real data only and has no synthetic fallback, "
        "so it stops here rather than fabricating a result."
    )


# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Bot challenges — a success code that is not a success
# --------------------------------------------------------------------------- #

#: Response headers a web application firewall uses to announce that it, rather
#: than the publisher, answered. AWS WAF sends ``x-amzn-waf-action: challenge``
#: with **HTTP 202 and a zero-length body**; Cloudflare marks its own with
#: ``cf-mitigated``.
#:
#: 202 is a *success* code. Any client testing ``status_code < 400`` accepts the
#: challenge and then parses nothing, which is the same trap as the Census
#: 200-plus-HTML page and BLS's 200-plus-``REQUEST_NOT_PROCESSED``.
#:
#: This was met in the field: HUD's ``/portal/`` paths are challenged while its
#: API is not, and the 202 was initially misdiagnosed as an egress block because
#: the status code was read and the headers were not.
WAF_ACTION_HEADERS: Final[tuple[str, ...]] = ("x-amzn-waf-action", "cf-mitigated")

#: Retained under its original name; the check is not HUD-specific.
HUD_WAF_HEADER: Final[str] = "x-amzn-waf-action"


class WafChallengeError(ResponseShapeError):
    """The publisher's bot defence answered instead of the publisher.

    Distinct from :class:`UpstreamError` because nothing is wrong upstream and
    retrying identically will not help: the request has to come from a client
    that can satisfy the challenge. Distinct from a plain
    :class:`ResponseShapeError` because the shape is not the publisher's fault
    and the remedy is different — a different client, not a different parse.
    """


def reject_bot_challenge(resp, *, source: str, endpoint: str) -> None:
    """Raise if a firewall answered instead of *source*.

    Called immediately after every request in this module. Without it a
    challenge still fails — every fetcher here tests ``status_code != 200``
    rather than ``< 400`` — but it fails with the wrong explanation, and a
    wrong explanation is what sends someone to reconfigure a proxy for an
    afternoon.
    """
    present = {h.lower() for h in resp.headers} & set(WAF_ACTION_HEADERS)
    if not present:
        return
    header = sorted(present)[0]
    action = next(
        (v for k, v in resp.headers.items() if k.lower() == header), "challenge"
    )
    raise WafChallengeError(
        f"A web application firewall answered {endpoint} on behalf of {source}: "
        f"{header}={action!r}, HTTP {resp.status_code}, {len(resp.content)} bytes. "
        f"This is not an error at {source} and not a network failure — the request "
        f"has to come from a client that can satisfy the challenge. Note that the "
        f"status code may be 2xx: a challenge is not signalled by failing."
    )


# --------------------------------------------------------------------------- #
# Census ACS
# --------------------------------------------------------------------------- #

# ACS "jam values": documented codes that occupy a numeric field but are not
# measurements. Treating them as numbers is a silent, severe data defect.
ACS_SENTINELS: Final[frozenset[int]] = frozenset(
    {-999999999, -888888888, -777777777, -666666666, -555555555,
     -333333333, -222222222, -111111111}
)

CENSUS_HOST: Final = "https://api.census.gov/data"


# The Census API accepts at most 50 comma-separated names in `get`. Requests
# carrying NAME plus 50 variables are rejected with a bare HTTP 400 and no
# explanatory body, which is indistinguishable from a malformed geography. The
# ceiling is enforced here so the failure names its own cause.
CENSUS_GET_CEILING: Final[int] = 50


#: Query-parameter names that carry a credential across the APIs used here.
#: HUD is the exception: it takes a Bearer token in a header rather than a
#: query parameter, so the URL is safe but the *headers* must never be
#: interpolated into an exception. `redact` covers it anyway via
#: `_SEEN_SECRETS`, which records every value `load_key` has returned.
_CREDENTIAL_PARAMS: Final[tuple[str, ...]] = (
    "api_key", "key", "registrationkey",
    # BEA takes its credential as ``UserID`` and is the only source here that
    # ECHOES it back inside the response body, at
    # ``BEAAPI.Request.RequestParam[i].ParameterValue``. Stripping that block is
    # `fetch_bea_regional`'s job; this entry covers the other direction, where a
    # requests exception carries the outbound URL into a traceback.
    "userid",
)

#: Literal secret values handed out by ``load_key`` during this process, kept so
#: a credential can be scrubbed wherever it appears and not only inside a
#: recognised query parameter. Values only; never names, never persisted.
_SEEN_SECRETS: set[str] = set()

_CRED_PARAM_RE: Final = re.compile(
    r"(?i)\b(" + "|".join(_CREDENTIAL_PARAMS) + r")=([^&\s'\"]+)"
)


def redact(text: object) -> str:
    """Scrub credentials from any text that is about to be surfaced.

    ``requests`` exceptions carry the full request URL, and the Census and FRED
    APIs take their key as a query parameter, so interpolating an exception into
    an error message publishes the credential into logs, tracebacks and stored
    notebook outputs. That is audit finding F-14 reaching the library itself,
    and it is why this function exists.

    Two passes: recognised credential query parameters, then any literal secret
    value this process has loaded, wherever it appears.
    """
    out = _CRED_PARAM_RE.sub(lambda m: m.group(1) + "=***REDACTED***", str(text))
    for secret in _SEEN_SECRETS:
        if secret and secret in out:
            out = out.replace(secret, "***REDACTED***")
    return out


def _assert_json_payload(resp: requests.Response, endpoint: str) -> object:
    """Reject a success status that carries a non-JSON body.

    ``api.census.gov`` answers a keyless request with ``200 text/html`` and a
    "Missing Key" page. Any code branching on ``status_code == 200`` alone will
    treat that page as data.
    """
    ctype = (resp.headers.get("content-type") or "").lower()
    body = resp.text.lstrip()
    if body[:1] not in "[{" or "html" in ctype:
        snippet = " ".join(body[:180].split())
        raise ResponseShapeError(
            f"{endpoint} returned HTTP {resp.status_code} with content-type "
            f"'{ctype}' and a non-JSON body. This is how the Census API "
            f"reports a missing or rejected key. Body began: {redact(snippet)!r}"
        )
    try:
        return resp.json()
    except json.JSONDecodeError as exc:  # pragma: no cover - guarded above
        raise ResponseShapeError(f"{endpoint} returned undecodable JSON: {redact(exc)}") from exc


def verify_digest(
    result: tuple[pd.DataFrame, DataProvenance],
    expected_sha256: str,
    *,
    label: str = "",
) -> tuple[pd.DataFrame, DataProvenance]:
    """Hold a retrieval to a digest recorded when the notebook was written.

    Most of this corpus's sources revise and serve no prior vintage (handbook
    §5.5), so naming a year pins a reference period and not a vintage. There is
    exactly one thing a client can do about that: record what it received and
    **refuse to continue** when a later run receives something else.

    That is a weaker guarantee than a pinned vintage and it is not the same kind
    of thing, so it gets its own name. A pinned vintage means the publisher will
    serve these numbers again. A pinned digest means nobody will be told these
    numbers changed *without noticing*: the notebook fails instead of quietly
    reporting different figures under the same prose.

    The digest is compared on the provenance record's own ``hash_basis``, which
    matters -- Census does not hold row order and BLS puts the request's latency
    in the payload, so a pin against raw bytes would fire on almost every run and
    be switched off within a week.

    Raises
    ------
    ChecksumError
        When the payload differs from the pin. The message names both digests and
        says what to do, because the correct response is a judgement: confirm the
        upstream revision, read what moved, and update the pin deliberately.
    """
    frame, prov = result
    if prov.content_sha256 != expected_sha256:
        raise ChecksumError(
            f"{label or prov.dataset} is {prov.content_sha256} on a "
            f"{prov.hash_basis} basis, not the pinned {expected_sha256}. The "
            "source has revised, or the request changed. Do not edit the pin to "
            "make this pass -- read what moved first, then update the pin and the "
            "prose together."
        )
    object.__setattr__(prov, "pinned", True)
    object.__setattr__(
        prov,
        "notes",
        prov.notes + (
            f"Digest pinned by the notebook and verified on this run "
            f"({prov.hash_basis}). The publisher serves no prior vintage; this "
            "pin does not restore one, it guarantees a change cannot pass "
            "unnoticed.",
        ),
    )
    return frame, prov


def acs_period_note(dataset: str) -> str:
    """What the estimates of this ACS product measure, for the provenance record.

    The 5-year product pools five years of responses; the 1-year product describes one calendar
    year. Saying the first of the second would mislabel a record.
    """
    if dataset.endswith("acs5"):
        return "5-year estimates are period estimates, not point-in-time measures."
    if dataset.endswith("acs1"):
        return "1-year estimates describe a single calendar year of data collection."
    return f"The estimation period of {dataset} is defined by the product, not by this record."


def acs_moe_note(variables: Mapping[str, str]) -> str:
    """Say whether margins of error were retrieved: they are when a margin-of-error variable (code ending in M) was requested."""
    margins = sorted(code for code in variables if code.endswith("M"))
    if margins:
        return (
            "ACS estimates are survey-based. Their margins of error were requested with the estimates "
            f"({', '.join(margins)}) and are returned as columns; differences between geographies may not "
            "be statistically distinguishable."
        )
    return (
        "ACS estimates are survey-based and carry margins of error that are "
        "not retrieved here; differences between geographies may not be "
        "statistically distinguishable."
    )


def fetch_acs(
    *,
    year: int,
    variables: Mapping[str, str],
    geography: str = "state:*",
    within: str | None = None,
    dataset: str = "acs/acs5",
    plausible: Mapping[str, tuple[float, float]] | None = None,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Fetch real ACS estimates, or raise.

    Parameters
    ----------
    year:
        Pinned vintage. Required; there is no "latest".
    variables:
        Mapping of ACS variable code to its **verbatim published label**. The
        label is carried into the provenance record so a reader can check the
        semantics of every column without leaving the notebook.
    plausible:
        Optional per-variable ``(low, high)`` bounds. A value outside its
        stated range raises :class:`RangeError` rather than flowing into a
        model. Bounds are documentation as much as validation: they record what
        the analyst believed the data should look like.

    Returns
    -------
    A tuple of the parsed frame and its :class:`DataProvenance` record.
    """
    if not variables:
        raise ValueError("At least one ACS variable is required.")
    if len(variables) + 1 > CENSUS_GET_CEILING:
        raise ValueError(
            f"{len(variables)} variables plus NAME exceeds the Census `get` "
            f"ceiling of {CENSUS_GET_CEILING}. The API rejects this with an "
            "unexplained HTTP 400. Use `fetch_acs_wide`, which splits the "
            "request and joins the batches on the geography key."
        )
    endpoint = f"{CENSUS_HOST}/{year}/{dataset}"
    if "&" in geography:
        raise ValueError(
            "Pass a containing geography via `within=`, not by embedding '&in=' in "
            "`geography`. The ampersand is URL-encoded into the `for` value and the "
            "API rejects the request with HTTP 400."
        )
    params = {
        "get": "NAME," + ",".join(variables),
        "for": geography,
        "key": load_key("CENSUS_API_KEY"),
    }
    if within:
        # Census requires the containing geography as its own `in` parameter,
        # e.g. for=county:*&in=state:51
        params["in"] = within
    http = session or requests
    try:
        resp = http.get(endpoint, params=params, timeout=60)
    except requests.RequestException as exc:
        raise UpstreamError(f"Census request to {endpoint} failed: {redact(exc)}") from exc
    reject_bot_challenge(resp, source="the Census Bureau", endpoint=endpoint)
    if resp.status_code != 200:
        raise UpstreamError(f"Census returned HTTP {resp.status_code} for {endpoint}.")

    rows = _assert_json_payload(resp, endpoint)
    if not isinstance(rows, list) or len(rows) < 2:
        raise ResponseShapeError(f"{endpoint} returned no data rows.")

    header, *body = rows
    df = pd.DataFrame(body, columns=header)

    missing = [v for v in variables if v not in df.columns]
    if missing:
        raise SchemaError(
            f"Census response is missing requested variables {missing}. "
            f"Returned columns: {list(df.columns)}"
        )

    # Numeric coercion is explicit, and sentinels become NaN before any maths.
    for code in variables:
        df[code] = pd.to_numeric(df[code], errors="coerce")
        df.loc[df[code].isin(ACS_SENTINELS), code] = pd.NA
        df[code] = pd.to_numeric(df[code], errors="coerce")

    for code, (low, high) in (plausible or {}).items():
        if code not in df.columns:
            continue
        s = df[code].dropna()
        if s.empty:
            raise RangeError(f"{code} is entirely missing after sentinel removal.")
        if (bad := s[(s < low) | (s > high)]).size:
            raise RangeError(
                f"{code} has {bad.size} value(s) outside the stated plausible "
                f"range [{low}, {high}]: e.g. {bad.iloc[0]}. Investigate the "
                f"variable definition before proceeding; do not widen the range "
                f"to make this pass."
            )

    prov = DataProvenance.build(
        hash_basis="canonical-rows",
        request_params=params,
        source_name="U.S. Census Bureau",
        dataset=f"American Community Survey ({dataset})",
        vintage=str(year),
        endpoint=endpoint,
        variables=dict(variables),
        payload=canonical_rows(resp.content),
        row_count=len(df),
        column_count=len(df.columns),
        notes=(
            acs_moe_note(variables),
            "Jam values (suppressed / unavailable estimates) were converted to "
            f"missing. Sentinels recognised: {sorted(ACS_SENTINELS)}.",
            acs_period_note(dataset),
        ),
    )
    return df, prov


def fetch_acs_wide(
    *,
    year: int,
    variables: Mapping[str, str],
    geography: str = "state:*",
    within: str | None = None,
    dataset: str = "acs/acs5",
    plausible: Mapping[str, tuple[float, float]] | None = None,
    session: requests.Session | None = None,
    batch_size: int = CENSUS_GET_CEILING - 1,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Fetch more variables than one Census request permits, then join them.

    Detailed cross-tabulated tables routinely exceed the API's 50-name ceiling:
    B17001 alone has 59 estimate cells. Splitting the request is therefore
    unavoidable, and the join is where a silent error would live -- a batch
    returning a different set or order of geographies would misalign every
    downstream rate without raising.

    Two invariants are checked rather than assumed:

    1. Every batch returns the identical geography key set. A batch that
       silently dropped or added a geography raises :class:`SchemaError`.
    2. The joined frame has exactly the requested variables and the same row
       count as the first batch.

    Ordering is imposed by an explicit merge on the geography key columns, not
    inherited from response order, so a reordered batch cannot misalign.

    The returned provenance record hashes the concatenated payloads of all
    batches in request order, so the digest still identifies the exact bytes the
    analysis was computed from.
    """
    if not variables:
        raise ValueError("At least one ACS variable is required.")
    if not hasattr(variables, "keys"):
        # A list of codes survives to the per-batch subset below and fails there
        # with `TypeError: list indices must be integers`, several frames from the
        # call site and naming nothing the caller wrote. Reject it where it is passed.
        raise TypeError(
            "`variables` must be a mapping of Census variable code -> the name the "
            f"notebook uses for it, not {type(variables).__name__}. Pass "
            '{"B25031_004E": "median_gross_rent_2br"}, not a list of codes.'
        )
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1.")
    if batch_size > CENSUS_GET_CEILING - 1:
        raise ValueError(
            f"batch_size {batch_size} would exceed the Census `get` ceiling of "
            f"{CENSUS_GET_CEILING} once NAME is added."
        )

    codes = list(variables)
    batches = [codes[i : i + batch_size] for i in range(0, len(codes), batch_size)]
    http = session or requests.Session()

    joined: pd.DataFrame | None = None
    key_cols: list[str] = []
    payloads: list[bytes] = []
    endpoint = f"{CENSUS_HOST}/{year}/{dataset}"

    for n, batch in enumerate(batches, start=1):
        sub = {c: variables[c] for c in batch}
        # Plausible bounds are applied per batch; each only knows its own columns.
        sub_bounds = {c: b for c, b in (plausible or {}).items() if c in sub}
        frame, prov = fetch_acs(
            year=year,
            variables=sub,
            geography=geography,
            within=within,
            dataset=dataset,
            plausible=sub_bounds or None,
            session=http,
        )
        payloads.append(prov.content_sha256.encode("ascii"))
        if joined is None:
            key_cols = [c for c in frame.columns if c not in sub and c != "NAME"]
            if not key_cols:
                raise SchemaError(
                    "No geography key column was returned; the batches cannot be "
                    f"joined safely. Columns: {list(frame.columns)}"
                )
            joined = frame
            continue

        left_keys = set(map(tuple, joined[key_cols].astype(str).to_numpy()))
        right_keys = set(map(tuple, frame[key_cols].astype(str).to_numpy()))
        if left_keys != right_keys:
            only_left = sorted(left_keys - right_keys)[:5]
            only_right = sorted(right_keys - left_keys)[:5]
            raise SchemaError(
                f"Batch {n} returned a different geography set. "
                f"Missing from batch: {only_left}; unexpected in batch: "
                f"{only_right}. Joining these would misalign every row."
            )
        joined = joined.merge(
            frame.drop(columns=["NAME"], errors="ignore"),
            on=key_cols,
            how="inner",
            validate="one_to_one",
        )

    assert joined is not None  # guaranteed: `codes` is non-empty

    missing = [c for c in codes if c not in joined.columns]
    if missing:
        raise SchemaError(f"Joined frame is missing variables {missing}.")

    prov = DataProvenance.build(
        #: There is no single request behind this frame -- it is the join of
        #: several batched ones -- so a replayer is told that rather than
        #: being handed parameters that would rebuild only the last batch.
        request_params={"assembled_from_batches": str(len(batches))},
        hash_basis="composed-digests",
        source_name="U.S. Census Bureau",
        dataset=f"American Community Survey ({dataset})",
        vintage=str(year),
        endpoint=endpoint,
        variables=dict(variables),
        payload=b"|".join(payloads),
        row_count=len(joined),
        column_count=len(joined.columns),
        notes=(
            f"Retrieved in {len(batches)} request(s) of at most {batch_size} "
            "variables and joined on the geography key; the Census `get` ceiling "
            f"is {CENSUS_GET_CEILING} names including NAME.",
            "Payload hash is over the concatenated per-batch payload digests in "
            "request order, not over a single response body.",
            acs_moe_note(variables),
            "Jam values (suppressed / unavailable estimates) were converted to "
            f"missing. Sentinels recognised: {sorted(ACS_SENTINELS)}.",
            acs_period_note(dataset),
        ),
    )
    return joined, prov


# ---------------------------------------------------------------------------
# Census ACS PUMS -- person records, returned as weighted cell counts only
# ---------------------------------------------------------------------------

#: The person weight in the ACS PUMS (``PWGTP``, 1 to 9999 per the API's variable
#: metadata). Replicate weights are not used here.
PUMS_PERSON_WEIGHT: Final[str] = "PWGTP"

#: The smallest ``min_cell_records`` a caller may ask for. A cell built from fewer
#: records than this is withheld, because a count of one or two people is a person
#: row under another name. The floor is this repository's rule, not a Census rule.
PUMS_CELL_FLOOR: Final[int] = 5
PUMS_DEFAULT_MIN_CELL: Final[int] = 10


def _pums_person_frame(raw: pd.DataFrame, requested: Sequence[str], weight: str) -> pd.DataFrame:
    """Numeric person frame from the API's rows. Private: it is never returned.

    Nothing is coerced silently: a non-null value that is not a number raises, and a
    weight that is missing or not positive raises.
    """
    person = pd.DataFrame(index=raw.index)
    for code in requested:
        column = pd.to_numeric(raw[code], errors="coerce")
        broken = column.isna() & raw[code].notna()
        if broken.any():
            raise SchemaError(
                f"{code} holds {int(broken.sum())} non-numeric value(s) that are not "
                f"null, e.g. {str(raw.loc[broken, code].iloc[0])!r}; nothing is coerced."
            )
        person[code] = column
    w = person[weight]
    if w.isna().any() or (w <= 0).any():
        raise RangeError(
            f"the weight {weight} is missing or not positive in "
            f"{int((w.isna() | (w <= 0)).sum())} record(s); a person weight is at least 1."
        )
    return person


def _pums_restrict(
    person: pd.DataFrame,
    keep: Mapping[str, tuple[float, float]] | None,
    bands: Mapping[str, Sequence[float]] | None,
) -> tuple[pd.DataFrame, list[str]]:
    """Restrict records and coarsen columns, inside the aggregator, before any grouping.

    ``keep`` retains the records whose value lies in the inclusive range (a missing value
    is not in any range). ``bands`` replaces a column's value with the lower edge of its
    right-open band ``[edge_i, edge_i+1)``; a value outside the outermost edges raises
    rather than being dropped or clamped. Missing values stay missing.
    """
    notes: list[str] = []
    if keep:
        mask = pd.Series(True, index=person.index)
        for column, (low, high) in keep.items():
            mask &= person[column].between(low, high)
        notes.append(
            f"Kept {int(mask.sum())} of {len(person)} person record(s) inside "
            + ", ".join(f"{c} in [{lo}, {hi}]" for c, (lo, hi) in keep.items()) + "."
        )
        person = person[mask]
    if bands:
        person = person.copy()
        for column, edges in bands.items():
            values = person[column]
            outside = values.notna() & ((values < edges[0]) | (values >= edges[-1]))
            if outside.any():
                raise RangeError(
                    f"{column} has {int(outside.sum())} value(s) outside the bands "
                    f"[{edges[0]}, {edges[-1]}); restrict the records with `keep` first."
                )
            index = np.digitize(values.to_numpy(dtype=float), np.asarray(edges, dtype=float)) - 1
            edge_array = np.asarray(edges, dtype=float)
            lower = np.where(values.notna(), edge_array[np.clip(index, 0, len(edges) - 2)], np.nan)
            person[column] = lower
        notes.append(
            "Coarsened "
            + ", ".join(
                f"{c} into {len(e) - 1} band(s), labelled by lower edge" for c, e in bands.items()
            )
            + "."
        )
    return person, notes


def _pums_apply_floor(
    cells: pd.DataFrame, aggregate_by: Sequence[str], min_cell_records: int, read: int, kept: int
) -> tuple[pd.DataFrame, str]:
    """Withhold cells under the floor and account for them. Operates on cells, never records."""
    small = cells["n_records"] < min_cell_records
    withheld = cells[small]
    out = cells[~small].sort_values(list(aggregate_by), na_position="last").reset_index(drop=True)
    out["weighted_n"] = out["weighted_n"].astype(float)
    out["n_records"] = out["n_records"].astype(int)
    out.attrs.update(
        suppressed_cells=int(small.sum()),
        suppressed_records=int(withheld["n_records"].sum()),
        suppressed_weighted_n=float(withheld["weighted_n"].sum()),
        min_cell_records=int(min_cell_records),
        records_read=int(read),
        records_kept=int(kept),
    )
    note = (
        f"Aggregated to {len(out)} cell(s) from {kept} person record(s); "
        f"{int(small.sum())} cell(s) with fewer than {min_cell_records} records were "
        f"withheld ({int(withheld['n_records'].sum())} record(s), weighted "
        f"{float(withheld['weighted_n'].sum()):,.0f}). No person-level row is returned."
    )
    return out, note


def _pums_cells(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    person: pd.DataFrame,
    aggregate_by: Sequence[str],
    weight: str,
    min_cell_records: int,
    keep: Mapping[str, tuple[float, float]] | None = None,
    bands: Mapping[str, Sequence[float]] | None = None,
    apply_floor: bool = True,
) -> tuple[pd.DataFrame, list[str]]:
    """The only reader of the person frame: weighted cell counts, small cells withheld.

    Returns ``(cells, notes)``. ``cells`` has the grouping columns plus ``weighted_n`` and
    ``n_records``; what was withheld is in ``cells.attrs`` and in ``notes``. Missing values
    in a grouping column form their own cell. ``keep`` and ``bands`` restrict and coarsen
    the records first (see :func:`_pums_restrict`). With ``apply_floor=False`` the cells
    are returned whole, for :func:`_pums_pool` to sum across states before the floor is
    applied; they stay inside ``fetch_acs_pums``. Complexity O(n log n) in the records.
    """
    notes = [
        "PUMS is a sample of person records; weighted cell counts estimate population "
        "counts with sampling error that is not computed here (no replicate weights).",
        "Missing values in grouping columns are kept as their own cell; their meaning "
        "is the variable's universe in the PUMS data dictionary.",
    ]
    read = len(person)
    person, restrict_notes = _pums_restrict(person, keep, bands)
    notes.extend(restrict_notes)
    grouped = person.groupby(list(aggregate_by), dropna=False)
    cells = grouped.agg(weighted_n=(weight, "sum"), n_records=(weight, "size")).reset_index()
    if not apply_floor:
        cells.attrs.update(records_read=int(read), records_kept=int(len(person)))
        return cells, notes
    out, floor_note = _pums_apply_floor(cells, aggregate_by, min_cell_records, read, len(person))
    notes.append(floor_note)
    return out, notes


def _pums_pool(
    partials: Sequence[pd.DataFrame], aggregate_by: Sequence[str], min_cell_records: int
) -> tuple[pd.DataFrame, list[str]]:
    """Sum whole cells across states, then apply the floor to the pooled counts."""
    stacked = pd.concat(partials, ignore_index=True)
    pooled = (
        stacked.groupby(list(aggregate_by), dropna=False)[["weighted_n", "n_records"]]
        .sum()
        .reset_index()
    )
    read = sum(int(p.attrs["records_read"]) for p in partials)
    kept = sum(int(p.attrs["records_kept"]) for p in partials)
    out, note = _pums_apply_floor(pooled, aggregate_by, min_cell_records, read, kept)
    return out, [
        f"Pooled {len(partials)} state(s): each cell's weight and record count were summed "
        "across states before the small-cell floor was applied.",
        note,
    ]


#: Pauses before each attempt at a PUMS request: none, then growing (seconds).
PUMS_RETRY_PAUSES: Final[tuple[float, ...]] = (0.0, 5.0, 15.0, 45.0)

_sleep = time.sleep


def _pums_predicates(keep: Mapping[str, tuple[float, float]] | None) -> dict[str, str]:
    """The ``keep`` ranges as Census range predicates (``AGEP=19:64``), where they are whole.

    The service then returns only the matching records, a fraction of the payload. The same
    ranges are applied again to what comes back, so a service that ignored a predicate would
    change the size of the response and nothing else.
    """
    return {
        column: f"{int(low)}:{int(high)}"
        for column, (low, high) in (keep or {}).items()
        if low == int(low) and high == int(high)
    }


def _pums_fetch_raw(
    http: Any, endpoint: str, params: dict[str, str], requested: Sequence[str]
) -> tuple[pd.DataFrame, bytes]:
    """One state's response as a raw string frame, and its canonical rows for the digest.

    A timeout, a dropped connection or an HTTP 503 (the service's way of slowing a burst) is
    retried after a growing pause, at most ``len(PUMS_RETRY_PAUSES)`` times; every other
    failure stops at once.
    """
    resp = None
    for attempt, pause in enumerate(PUMS_RETRY_PAUSES):
        _sleep(pause)
        last = attempt == len(PUMS_RETRY_PAUSES) - 1
        try:
            resp = http.get(endpoint, params=params, timeout=300)
        except (requests.Timeout, requests.ConnectionError) as exc:
            if last:
                raise UpstreamError(
                    f"Census request to {endpoint} failed after {len(PUMS_RETRY_PAUSES)} "
                    f"attempts: {redact(exc)}"
                ) from exc
            continue
        except requests.RequestException as exc:
            raise UpstreamError(f"Census request to {endpoint} failed: {redact(exc)}") from exc
        if resp.status_code != 503 or last:
            break
    assert resp is not None
    reject_bot_challenge(resp, source="the Census Bureau", endpoint=endpoint)
    if resp.status_code != 200:
        raise UpstreamError(f"Census returned HTTP {resp.status_code} for {endpoint}.")
    rows = _assert_json_payload(resp, endpoint)
    if not isinstance(rows, list) or len(rows) < 2:
        raise ResponseShapeError(f"{endpoint} returned no data rows.")
    header, *body = rows
    raw = pd.DataFrame(body, columns=header)
    raw = _pums_drop_echoed_columns(raw)
    missing = [c for c in requested if c not in raw.columns]
    if missing:
        raise SchemaError(
            f"PUMS response is missing requested variables {missing}. "
            f"Returned columns: {list(raw.columns)}"
        )
    return raw, canonical_rows(resp.content)


def _pums_drop_echoed_columns(raw: pd.DataFrame) -> pd.DataFrame:
    """Drop the columns a range predicate makes the service repeat.

    A request with ``AGEP=19:64`` returns ``AGEP`` a second time. The copy must equal the
    first or the response is refused; nothing is silently chosen between two values.
    """
    repeated = raw.columns[raw.columns.duplicated()].unique()
    for name in repeated:
        same = raw.loc[:, name]
        if not (same.nunique(axis=1, dropna=False) <= 1).all():
            raise SchemaError(f"PUMS response repeats {name} with differing values.")
    return raw.loc[:, ~raw.columns.duplicated()]


def _pums_check_request(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-branches
    variables: Mapping[str, str],
    aggregate_by: Sequence[str],
    weight: str,
    states: Sequence[str],
    min_cell_records: int,
    keep: Mapping[str, tuple[float, float]] | None,
    bands: Mapping[str, Sequence[float]] | None,
) -> None:
    """Refuse a specification that could not be honoured before any request is made."""
    if not variables:
        raise ValueError("At least one PUMS variable is required.")
    if not aggregate_by or not set(aggregate_by) <= set(variables):
        raise ValueError(
            "aggregate_by must be a non-empty subset of `variables`; "
            f"got {list(aggregate_by)} against {list(variables)}."
        )
    if weight in aggregate_by:
        raise ValueError(f"the weight {weight!r} cannot also be an aggregation column.")
    for name, spec in (("keep", keep), ("bands", bands)):
        unknown = set(spec or {}) - set(variables)
        if unknown:
            raise ValueError(f"{name} names {sorted(unknown)}, which are not in `variables`.")
    for column, (low, high) in (keep or {}).items():
        if not low <= high:
            raise ValueError(f"keep[{column!r}] must be (low, high) with low <= high.")
    for column, edges in (bands or {}).items():
        if column not in aggregate_by:
            raise ValueError(f"bands[{column!r}] must also be in `aggregate_by`.")
        if len(edges) < 2 or any(b <= a for a, b in zip(edges, edges[1:])):
            raise ValueError(f"bands[{column!r}] needs at least two strictly ascending edges.")
    if not states or len(set(states)) != len(states):
        raise ValueError("geography must name at least one state, each once.")
    if any("*" in g for g in states):
        raise ValueError(
            "Request one state per call (e.g. 'state:51') or a list of named states: a "
            "wildcard geography pulls every person record in the country into memory."
        )
    if min_cell_records < PUMS_CELL_FLOOR:
        raise ValueError(
            f"min_cell_records must be at least {PUMS_CELL_FLOOR}: a cell of fewer "
            "people is a person row under another name."
        )


def fetch_acs_pums(  # pylint: disable=too-many-arguments,too-many-locals
    *,
    year: int,
    variables: Mapping[str, str],
    aggregate_by: Sequence[str],
    geography: str | Sequence[str],
    weight: str = PUMS_PERSON_WEIGHT,
    dataset: str = "acs/acs1/pums",
    min_cell_records: int = PUMS_DEFAULT_MIN_CELL,
    keep: Mapping[str, tuple[float, float]] | None = None,
    bands: Mapping[str, Sequence[float]] | None = None,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Fetch ACS PUMS person records and return weighted cell counts, or raise.

    The Census API serves one record per person. This function reads them into
    memory, groups them by ``aggregate_by`` and returns, per cell, the sum of
    ``weight`` (``weighted_n``) and the number of records (``n_records``). **No
    person-level row is returned, printed or stored, and there is no argument
    that asks for one**: the person frame exists only inside this call and
    :func:`_pums_cells`, the single place it is read, returns cells.

    Parameters
    ----------
    year:
        Pinned release. A PUMS 1-year file is a separately addressed immutable
        product, so the retrieval is pinned.
    variables:
        Variable code -> verbatim published label (the provenance dictionary).
        ``aggregate_by`` must be a subset; the weight is requested in addition.
    geography:
        One state, e.g. ``"state:51"``, or a list of states to pool. A wildcard is refused:
        it would pull every person record in the country into memory at once. With a list,
        each state is read in turn, aggregated to whole cells and released, the cells are
        summed across states, and the small-cell floor is applied to the pooled counts.
    min_cell_records:
        Cells with fewer records are withheld and reported in ``frame.attrs``
        (``suppressed_cells``, ``suppressed_records``, ``suppressed_weighted_n``)
        and in the provenance notes. Not below :data:`PUMS_CELL_FLOOR`.
    keep:
        Variable -> inclusive ``(low, high)``. Only records inside every range are
        aggregated; the counts read and kept are in ``frame.attrs`` and the notes.
    bands:
        Variable -> ascending band edges. The variable's value is replaced by the
        lower edge of its band ``[edge_i, edge_i+1)`` before grouping, so a continuous
        or fine-grained covariate becomes a coarse one. ``keep`` and ``bands`` take
        place inside the aggregator: they give no way to see a record.

    Notes
    -----
    A missing value in a grouping column is kept as its own cell (the variable's
    "not in universe"); it is never dropped or recoded. A non-numeric, non-null
    value, a missing requested column, a weight that is missing or not positive,
    or an unexpected empty response raises. The digest is taken over the
    canonicalised **rows** the API returned, so it does not depend on row order.
    """
    states = [geography] if isinstance(geography, str) else list(geography)
    _pums_check_request(variables, aggregate_by, weight, states, min_cell_records, keep, bands)
    requested = [*variables, *([] if weight in variables else [weight])]
    if len(requested) + 1 > CENSUS_GET_CEILING:
        raise ValueError(
            f"{len(requested)} variables exceeds the Census `get` ceiling of "
            f"{CENSUS_GET_CEILING}."
        )
    endpoint = f"{CENSUS_HOST}/{year}/{dataset}"
    api_key = load_key("CENSUS_API_KEY")
    http = session or requests
    pooled = len(states) > 1
    partials: list[pd.DataFrame] = []
    payloads: list[bytes] = []
    n_person = 0
    for state in states:
        params = {
            "get": ",".join(requested),
            "for": state,
            **_pums_predicates(keep),
            "key": api_key,
        }
        raw, payload = _pums_fetch_raw(http, endpoint, params, requested)
        person = _pums_person_frame(raw, requested, weight)
        n_person += len(person)
        payloads.append(payload)
        out, notes = _pums_cells(
            person, list(aggregate_by), weight, min_cell_records, keep, bands,
            apply_floor=not pooled,
        )
        partials.append(out)
    if pooled:
        out, pool_notes = _pums_pool(partials, list(aggregate_by), min_cell_records)
        notes = [*notes[:2], *_pums_restriction_notes(keep, bands), *pool_notes]

    prov = DataProvenance.build(
        hash_basis="canonical-rows",
        request_params={
            "get": ",".join(requested),
            "for": states if pooled else states[0],
            **_pums_predicates(keep),
            "key": api_key,
        },
        source_name="U.S. Census Bureau",
        dataset=f"American Community Survey Public Use Microdata Sample ({dataset})",
        vintage=str(year),
        endpoint=endpoint,
        variables=dict(variables),
        payload=b"\n".join(payloads),
        row_count=n_person,
        column_count=len(requested),
        notes=tuple(notes),
    )
    return out, prov


def _pums_restriction_notes(
    keep: Mapping[str, tuple[float, float]] | None, bands: Mapping[str, Sequence[float]] | None
) -> list[str]:
    """Describe the restriction applied to every state, without per-state counts."""
    notes = []
    if keep:
        ranges = ", ".join(f"{c} in [{lo}, {hi}]" for c, (lo, hi) in keep.items())
        notes.append(f"Records kept inside {ranges}.")
    if bands:
        notes.append(f"Coarsened {', '.join(bands)} into bands labelled by lower edge.")
    return notes


# ---------------------------------------------------------------------------
# Census CPS ASEC -- person records, returned as weighted income-bin cells only
# ---------------------------------------------------------------------------

#: The CPS ASEC person weight. Replicate weights are not served by the API.
CPS_ASEC_WEIGHT: Final[str] = "MARSUPWT"

#: Variable code -> verbatim label from the API's ``variables.json`` (checked 2026-10-27).
CPS_ASEC_VARIABLES: Final[dict[str, str]] = {
    "PH_SEQ": "Household sequence number",
    "A_EXPRRP": "Demographics, Relationship expanded code",
    "A_AGE": "Demographics, Age",
    "PRDTRACE": "Demographic - race of respondent",
    "PEHSPNON": "Demographics- hispanic/non-hispanic origin",
    "HTOTVAL": "Household income amount",
    "H_NUMPER": "Number of persons in household",
    "MARSUPWT": "Weight, March supplement - Person",
}

CPS_RACE_LABELS: Final[dict[int, str]] = {1: "White alone", 2: "Black alone", 4: "Asian alone"}
CPS_CELL_KEYS: Final[tuple[str, ...]] = ("income_bin", "race", "ref_age", "child")


def _cps_race(race: pd.Series, hispanic: pd.Series) -> pd.Series:
    """Five mutually exclusive groups: Hispanic of any race, else White, Black, Asian, other."""
    label = race.map(CPS_RACE_LABELS).fillna("Other non-Hispanic")
    return label.where(hispanic != 1, "Hispanic")


def _cps_reference_age(person: pd.DataFrame) -> pd.Series:
    """Each person's household reference person's age group; raises unless exactly one exists."""
    ref = person[person["A_EXPRRP"].isin((1, 2))]
    per_household = ref.groupby("PH_SEQ").size()
    households = person["PH_SEQ"].unique()
    if len(per_household) != len(households) or (per_household != 1).any():
        raise SchemaError(
            "every household needs exactly one reference person (A_EXPRRP 1 or 2); "
            f"{len(households) - int((per_household == 1).sum())} household(s) do not have one."
        )
    age = ref.set_index("PH_SEQ")["A_AGE"].reindex(person["PH_SEQ"]).to_numpy()
    return pd.Series(
        np.select([age < 35, age < 65], ["Under 35", "35-64"], default="65 and over"),
        index=person.index,
    )


def _cps_income_bin(adjusted: pd.Series, width: float, floor: float, cap: float) -> pd.Series:
    """Lower edge of the bin; everything at or above ``cap`` is one bin, below ``floor`` another."""
    binned = np.floor(adjusted / width) * width
    binned = binned.where(adjusted < cap, cap)
    return binned.where(adjusted >= floor, floor - width)


def _cps_check_request(bin_width: float, income_floor: float, income_cap: float,
                       min_cell_records: int) -> None:
    if bin_width <= 0.0:
        raise ValueError("bin_width must be positive.")
    if not income_floor < income_cap:
        raise ValueError("income_floor must be below income_cap.")
    if min_cell_records < PUMS_CELL_FLOOR:
        raise ValueError(
            f"min_cell_records must be at least {PUMS_CELL_FLOOR}: a cell of fewer "
            "people is a person row under another name."
        )


def _cps_person_frame(raw: pd.DataFrame) -> pd.DataFrame:
    requested = list(CPS_ASEC_VARIABLES)
    person = _pums_person_frame(raw, requested, CPS_ASEC_WEIGHT)
    if person["PH_SEQ"].isna().any() or person["A_EXPRRP"].isna().any():
        raise SchemaError("PH_SEQ and A_EXPRRP must be present in every record.")
    if (person["H_NUMPER"].isna() | (person["H_NUMPER"] < 1)).any():
        raise RangeError("H_NUMPER must be at least 1 in every record.")
    if person["HTOTVAL"].isna().any() or person["A_AGE"].isna().any():
        raise SchemaError("HTOTVAL and A_AGE must be present in every record.")
    return person


def _cps_cells(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    person: pd.DataFrame, bin_width: float, income_floor: float, income_cap: float,
    min_cell_records: int, child_age: int,
) -> tuple[pd.DataFrame, str]:
    """The only reader of the CPS person frame: weighted cells, small cells withheld."""
    w = person[CPS_ASEC_WEIGHT]
    adjusted = person["HTOTVAL"] / np.sqrt(person["H_NUMPER"])
    keyed = pd.DataFrame(
        {
            "income_bin": _cps_income_bin(adjusted, bin_width, income_floor, income_cap),
            "race": _cps_race(person["PRDTRACE"], person["PEHSPNON"]),
            "ref_age": _cps_reference_age(person),
            "child": (person["A_AGE"] < child_age).astype(int),
            "w": w,
            "w2": w * w,
            "wx": w * adjusted,
        }
    )
    cells = (
        keyed.groupby(list(CPS_CELL_KEYS))
        .agg(weighted_n=("w", "sum"), sum_w2=("w2", "sum"),
             weighted_income=("wx", "sum"), n_records=("w", "size"))
        .reset_index()
    )
    return _pums_apply_floor(cells, CPS_CELL_KEYS, min_cell_records, len(person), len(person))


def fetch_cps_asec(  # pylint: disable=too-many-arguments,too-many-locals
    *,
    year: int,
    geography: str | None = None,
    bin_width: float = 2500.0,
    income_floor: float = 0.0,
    income_cap: float = 150_000.0,
    child_age: int = 18,
    min_cell_records: int = PUMS_DEFAULT_MIN_CELL,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Fetch CPS ASEC person records and return weighted cells, or raise.

    Mirrors :func:`fetch_acs_pums`: the person frame exists only inside this call and
    :func:`_cps_cells`, and **no person-level row is returned or stored**. A cell is
    ``(income_bin, race, ref_age, child)`` where ``income_bin`` is the lower edge of the
    bin of household income divided by the square root of household size (CBO's
    adjustment), ``race`` is one of five mutually exclusive groups, ``ref_age`` is the
    household reference person's age group and ``child`` is 1 when the person is under
    ``child_age``. Values at or above ``income_cap`` share one bin (labelled by the cap);
    values below ``income_floor`` share another (labelled ``income_floor - bin_width``).
    Each cell carries ``weighted_n`` (sum of weights), ``sum_w2`` (sum of squared weights,
    for Kish's effective sample size), ``weighted_income`` (sum of weight times the exact
    adjusted income, so tail bins keep their means) and ``n_records``; cells under
    ``min_cell_records`` are withheld and counted in ``frame.attrs`` and the notes.

    The API serves no replicate weights, so no sampling error is computed here.
    """
    _cps_check_request(bin_width, income_floor, income_cap, min_cell_records)
    requested = list(CPS_ASEC_VARIABLES)
    endpoint = f"{CENSUS_HOST}/{year}/cps/asec/mar"
    api_key = load_key("CENSUS_API_KEY")
    http = session or requests
    params = {
        "get": ",".join(requested),
        **({"for": geography} if geography else {}),
        "key": api_key,
    }
    raw, payload = _pums_fetch_raw(http, endpoint, params, requested)
    person = _cps_person_frame(raw)
    out, floor_note = _cps_cells(
        person, bin_width, income_floor, income_cap, min_cell_records, child_age
    )
    notes = (
        "CPS ASEC is a sample of person records; weighted cells estimate population "
        "counts. The API serves no replicate weights, so sampling error is not computed here.",
        f"Household income (HTOTVAL) divided by the square root of household size, in "
        f"${bin_width:,.0f} bins labelled by lower edge; at or above ${income_cap:,.0f} one "
        f"bin, below ${income_floor:,.0f} one bin labelled {income_floor - bin_width:,.0f}.",
        f"Children are persons under {child_age}; race is Hispanic of any race, else "
        "White, Black, Asian alone, else other non-Hispanic; age group is the household "
        "reference person's.",
        floor_note,
    )
    prov = DataProvenance.build(
        hash_basis="canonical-rows",
        request_params=params,
        source_name="U.S. Census Bureau",
        dataset="Current Population Survey Annual Social and Economic Supplement (cps/asec/mar)",
        vintage=str(year),
        endpoint=endpoint,
        variables=dict(CPS_ASEC_VARIABLES),
        payload=payload,
        row_count=len(person),
        column_count=len(requested),
        notes=notes,
    )
    return out, prov


# ---------------------------------------------------------------------------
# FRED (Federal Reserve Bank of St. Louis)
# ---------------------------------------------------------------------------

FRED_HOST: Final[str] = "https://api.stlouisfed.org/fred"

#: FRED writes a missing observation as a single period. It is a sentinel, not a
#: number, and `pd.to_numeric` would turn it into NaN silently either way - this
#: constant exists so the conversion is deliberate and documented.
FRED_MISSING: Final[str] = "."


def fetch_fred(
    *,
    series_id: str,
    start: str,
    end: str,
    frequency: str = "m",
    units: str = "lin",
    vintage: str | None = None,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Fetch one real FRED series over a pinned window, or raise.

    ``vintage`` requests the series **as it stood on that date** (ALFRED), which
    is how a figure someone acted on at the time can be recovered. Omitting it
    returns the current, revised series. The distinction matters: FRED rewrites
    history at every revision and rebasing, so "the 2023 number" is not a single
    value but one per vintage.

    Both ``start`` and ``end`` are required. A series fetched without an end date
    changes every time a notebook is re-run, which makes every number derived
    from it unreproducible - the same failure the bulk-file pin exists to
    prevent, in a different guise.

    Returns a frame indexed by observation date with a single ``value`` column,
    and a provenance record hashing the response body.
    """
    if not series_id:
        raise ValueError("A FRED series_id is required.")
    for label, value in (("start", start), ("end", end)):
        if not value:
            raise ValueError(
                f"`{label}` is required. A FRED window with an open end makes "
                f"every derived number change on re-run."
            )
    endpoint = f"{FRED_HOST}/series/observations"
    params = {
        "series_id": series_id,
        "api_key": load_key("FRED_API_KEY"),
        "file_type": "json",
        "observation_start": start,
        "observation_end": end,
        "frequency": frequency,
        "units": units,
    }
    if vintage:
        params["vintage_dates"] = vintage
    http = session or requests
    try:
        resp = http.get(endpoint, params=params, timeout=60)
    except requests.RequestException as exc:
        raise UpstreamError(f"FRED request for {series_id} failed: {redact(exc)}") from exc
    reject_bot_challenge(resp, source="FRED", endpoint=endpoint)
    if resp.status_code != 200:
        raise UpstreamError(
            f"FRED returned HTTP {resp.status_code} for {series_id}. "
            f"A 400 here is usually an unknown series_id or a rejected key."
        )
    payload = _assert_json_payload(resp, endpoint)
    if not isinstance(payload, dict) or "observations" not in payload:
        raise ResponseShapeError(
            f"FRED response for {series_id} has no 'observations' key."
        )
    observations = payload["observations"]
    if not observations:
        raise ResponseShapeError(
            f"FRED returned no observations for {series_id} between {start} and "
            f"{end}. Check the series' own coverage before widening the window."
        )

    df = pd.DataFrame(observations)[["date", "value"]].copy()
    missing = int((df["value"] == FRED_MISSING).sum())
    df["value"] = pd.to_numeric(
        df["value"].replace(FRED_MISSING, pd.NA), errors="coerce"
    )
    df["date"] = pd.to_datetime(df["date"])
    if df["value"].notna().sum() == 0:
        raise RangeError(
            f"Every observation of {series_id} in [{start}, {end}] is missing."
        )

    prov = DataProvenance.build(
        request_params=params,
        source_name="Federal Reserve Bank of St. Louis",
        dataset=f"FRED series {series_id}",
        vintage=(f"{start} to {end}"
                 + (f", as published {vintage}" if vintage else ", current revision")),
        endpoint=endpoint,
        variables={series_id: f"FRED {series_id}, frequency={frequency}, units={units}"},
        payload=resp.content,
        row_count=len(df),
        column_count=len(df.columns),
        notes=(
            "Window is pinned at both ends; an open end would change every "
            "derived number on re-run.",
            f"{missing} observation(s) were published as the missing sentinel "
            f"{FRED_MISSING!r} and became NaN before any arithmetic.",
            ("Requested as the series stood on " + vintage + " (ALFRED vintage)."
             if vintage else
             "Current revision: FRED rewrites history at each revision and "
             "rebasing, so these values differ from what was published earlier. "
             "Pass `vintage` to recover a historical publication."),
        ),
    )
    return df, prov


# ---------------------------------------------------------------------------
# BLS (Bureau of Labor Statistics) -- LAUS and friends
# ---------------------------------------------------------------------------

BLS_HOST: Final[str] = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

#: The v2 API accepts at most 50 series identifiers per request. Over the limit
#: it returns HTTP 200 with a REQUEST_NOT_PROCESSED status and an explanatory
#: message rather than an error code, so the ceiling is enforced here and the
#: status is checked below.
BLS_SERIES_CEILING: Final[int] = 50

#: BLS writes the annual average as a thirteenth period.
BLS_ANNUAL_PERIOD: Final[str] = "M13"


class BLSRequestError(DataAccessError):
    """BLS returned HTTP 200 with a non-success status in the payload."""


def fetch_bls(
    *,
    series: Mapping[str, str],
    start_year: int,
    end_year: int,
    annual_average: bool = True,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Fetch real BLS series over a pinned year range, or raise.

    ``series`` maps a BLS series identifier to what it means, in words. The
    label travels into provenance, because a LAUS identifier such as
    ``LAUCN51059000000000 5`` encodes geography and measure positionally and is
    unreadable otherwise -- exactly the shape of defect F-13 (a variable assumed
    from its position and meaning something else).

    Requests are split at the API's 50-series ceiling and the batches joined.
    **BLS signals failure with HTTP 200 and a status field**, so the status is
    checked explicitly; treating 200 as success would accept an error page as
    data, which is the same trap as the Census HTML masquerade.

    Returns a long frame -- one row per series, year and period -- and a
    provenance record hashing the concatenated batch payloads.
    """
    if not series:
        raise ValueError("At least one BLS series identifier is required.")
    if end_year < start_year:
        raise ValueError(f"end_year {end_year} precedes start_year {start_year}.")

    key = load_key("BLS_API_KEY")
    http = session or requests.Session()
    ids = list(series)
    batches = [
        ids[i : i + BLS_SERIES_CEILING]
        for i in range(0, len(ids), BLS_SERIES_CEILING)
    ]

    frames: list[pd.DataFrame] = []
    digests: list[bytes] = []
    returned: set[str] = set()

    for n, batch in enumerate(batches, start=1):
        body = {
            "seriesid": batch,
            "startyear": str(start_year),
            "endyear": str(end_year),
            "registrationkey": key,
            "annualaverage": bool(annual_average),
        }
        try:
            resp = http.post(
                BLS_HOST, json=body,
                headers={"Content-type": "application/json"}, timeout=90,
            )
        except requests.RequestException as exc:
            raise UpstreamError(f"BLS request (batch {n}) failed: {redact(exc)}") from exc
        reject_bot_challenge(resp, source="BLS", endpoint=BLS_HOST)
        if resp.status_code != 200:
            raise UpstreamError(f"BLS returned HTTP {resp.status_code} on batch {n}.")

        payload = _assert_json_payload(resp, BLS_HOST)
        if not isinstance(payload, dict):
            raise ResponseShapeError(f"BLS batch {n} did not return an object.")
        status = payload.get("status")
        if status != "REQUEST_SUCCEEDED":
            raise BLSRequestError(
                f"BLS batch {n} returned status {status!r} with HTTP 200. "
                f"Messages: {payload.get('message')}. A 200 from this API does "
                f"not mean success."
            )
        #: Canonicalised per batch, because BLS puts the request's own latency
        #: (`responseTime`) inside the payload -- three identical POSTs give
        #: three different digests and one identical `Results`.
        digests.append(canonical_stable_json(resp.content))

        for item in payload.get("Results", {}).get("series", []):
            sid = item.get("seriesID")
            returned.add(sid)
            for obs in item.get("data", []):
                frames.append({
                    "series_id": sid,
                    "label": series.get(sid, "<unlabelled>"),
                    "year": int(obs["year"]),
                    "period": obs["period"],
                    "period_name": obs.get("periodName"),
                    "value": pd.to_numeric(obs.get("value"), errors="coerce"),
                    "footnotes": ";".join(
                        f.get("code", "") for f in obs.get("footnotes", []) if f
                    ),
                })

    missing = [s for s in ids if s not in returned]
    if missing:
        raise SchemaError(
            f"BLS returned no data for {len(missing)} requested series, e.g. "
            f"{missing[:5]}. A silently short response would drop geographies "
            f"from every downstream comparison."
        )
    if not frames:
        raise ResponseShapeError("BLS returned no observations at all.")

    df = pd.DataFrame(frames)
    if df.value.notna().sum() == 0:
        raise RangeError("Every BLS observation returned is non-numeric.")

    footnoted = int((df.footnotes.fillna("") != "").sum())
    prov = DataProvenance.build(
        hash_basis="canonical-stable-json",
        #: Only replayable when there was a single batch. `body` is the LAST
        #: batch's body, so recording it for a multi-batch retrieval would
        #: describe a request that produces a fraction of this frame.
        request_params=(body if len(batches) == 1
                        else {"assembled_from_batches": str(len(batches))}),
        request_method="POST",
        pinned=False,
        source_name="U.S. Bureau of Labor Statistics",
        dataset="BLS timeseries API v2",
        vintage=f"{start_year} to {end_year}",
        endpoint=BLS_HOST,
        variables=dict(series),
        payload=b"|".join(digests),
        row_count=len(df),
        column_count=len(df.columns),
        notes=(
            f"Retrieved in {len(batches)} request(s) of at most "
            f"{BLS_SERIES_CEILING} series; that is the API's ceiling.",
            "BLS signals failure with HTTP 200 plus a status field; the status "
            "was checked rather than the status code alone.",
            f"Annual averages are period {BLS_ANNUAL_PERIOD}.",
            f"{footnoted} observation(s) carry a BLS footnote code (preliminary, "
            "revised, or otherwise qualified); inspect before treating as final.",
            "LAUS sub-state estimates are MODEL-BASED and are controlled to sum "
            "to the state estimate. They are not independent survey tabulations "
            "and carry no published margin of error.",
        ),
    )
    return df, prov


# ---------------------------------------------------------------------------
# BLS QCEW -- Quarterly Census of Employment and Wages
# ---------------------------------------------------------------------------

QCEW_HOST: Final[str] = "https://data.bls.gov/cew/data/api"

#: QCEW withholds a cell when disclosing it could identify an employer.
QCEW_SUPPRESSED: Final[str] = "N"

#: **A suppressed QCEW cell is published as 0, not as blank.** Summing or
#: averaging these fields without consulting ``disclosure_code`` silently treats
#: withheld industries as industries with no employment. This is the ACS
#: jam-value defect (F-13) in a different publisher's clothing, and it is the
#: reason this fetcher exists rather than a bare ``read_csv``.
QCEW_SUPPRESSED_FIELDS: Final[tuple[str, ...]] = (
    "qtrly_estabs", "month1_emplvl", "month2_emplvl", "month3_emplvl",
    "total_qtrly_wages", "taxable_qtrly_wages", "qtrly_contributions",
    "avg_wkly_wage",
)

#: Establishment counts are disclosed even for suppressed cells, so they are
#: left alone: the fact that an industry exists, and roughly how many firms are
#: in it, is public even when its employment is not.
QCEW_DISCLOSED_EVEN_IF_SUPPRESSED: Final[tuple[str, ...]] = ("qtrly_estabs",)


def fetch_qcew(
    *,
    year: int,
    quarter: int | str,
    area: str | None = None,
    industry: str | None = None,
    contact: str | None = None,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Fetch one QCEW slice, with suppressed cells made explicit.

    Exactly one of ``area`` (every industry in one area, e.g. ``"51000"``) and
    ``industry`` (one industry in every area, e.g. ``"722"``) selects the slice.
    The Bureau serves both from 2014 Q1; earlier quarters return HTTP 404.

    QCEW needs no API key, which makes it the one source here with no
    credential to leak and no quota to exhaust. It returns CSV rather than JSON.

    **Suppression is handled, not ignored.** Every field in
    :data:`QCEW_SUPPRESSED_FIELDS` is set to ``NaN`` on rows whose
    ``disclosure_code`` is ``"N"``, except the establishment count, which the
    Bureau discloses regardless. The number of values converted is recorded in
    provenance so a reader can see how much of the slice was withheld rather
    than inferring it from a suspiciously round total.

    ``contact`` is sent in the User-Agent. BLS asks automated users to identify
    themselves; the request succeeds without it, and sending one is courtesy
    rather than a requirement.
    """
    if (area is None) == (industry is None):
        raise ValueError("Give exactly one of `area` (e.g. '51059') or `industry` (e.g. '722').")
    kind, key = ("area", area) if area is not None else ("industry", industry)
    if not str(key).strip():
        raise ValueError(f"A QCEW {kind} code is required, e.g. '51059' or 'US000'.")
    qtr = str(quarter)
    endpoint = f"{QCEW_HOST}/{year}/{qtr}/{kind}/{key}.csv"
    agent = f"telosyn-notebooks/1.0 ({contact})" if contact else "telosyn-notebooks/1.0"

    http = session or requests
    try:
        resp = http.get(endpoint, timeout=120, headers={"User-Agent": agent})
    except requests.RequestException as exc:
        raise UpstreamError(f"QCEW request for {kind} {key} failed: {redact(exc)}") from exc
    reject_bot_challenge(resp, source="BLS QCEW", endpoint=endpoint)
    if resp.status_code != 200:
        raise UpstreamError(
            f"QCEW returned HTTP {resp.status_code} for {kind} {key}. A 404 here "
            f"usually means the {kind} code or the quarter does not exist."
        )

    text = resp.text
    head = text.lstrip()[:200].lower()
    if "<html" in head or "<!doctype" in head:
        raise ResponseShapeError(
            f"{endpoint} returned HTML rather than CSV. Treating a 200 as data "
            f"would parse an error page into a frame."
        )

    if not text.strip():
        # pandas raises EmptyDataError here, which is outside this module's
        # DataAccessError hierarchy: a caller following the documented contract
        # would not catch it. Found by sweeping every fetcher against an empty
        # body after the HUD challenge was diagnosed.
        raise ResponseShapeError(
            f"QCEW returned an empty body for {kind} {key} with HTTP "
            f"{resp.status_code}. An empty 200 is not an empty result set."
        )

    df = pd.read_csv(io.StringIO(text), dtype=str)
    required = {"area_fips", "own_code", "industry_code", "agglvl_code",
                "disclosure_code", "month3_emplvl"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise SchemaError(f"QCEW response for {kind} {key} lacks column(s) {missing}.")
    if df.empty:
        raise ResponseShapeError(f"QCEW returned no rows for {kind} {key}.")

    suppressed = df.disclosure_code.fillna("") == QCEW_SUPPRESSED
    zeroed = 0
    for field in QCEW_SUPPRESSED_FIELDS:
        if field not in df.columns:
            continue
        df[field] = pd.to_numeric(df[field], errors="coerce")
        if field in QCEW_DISCLOSED_EVEN_IF_SUPPRESSED:
            continue
        zeroed += int((suppressed & df[field].notna()).sum())
        df.loc[suppressed, field] = np.nan

    df["suppressed"] = suppressed

    prov = DataProvenance.build(
        pinned=False,
        source_name="U.S. Bureau of Labor Statistics",
        dataset=f"QCEW {kind} {key}, {year} Q{qtr}",
        vintage=f"{year}Q{qtr}",
        endpoint=endpoint,
        variables={f: "QCEW field" for f in QCEW_SUPPRESSED_FIELDS if f in df.columns},
        payload=resp.content,
        row_count=len(df),
        column_count=len(df.columns),
        notes=(
            f"{int(suppressed.sum())} of {len(df)} rows carry disclosure_code "
            f"'{QCEW_SUPPRESSED}' (withheld to protect employer identity).",
            f"{zeroed} withheld values were published as 0 and have been set to "
            "NaN. Summing them as zeros would treat withheld industries as "
            "industries with no employment.",
            "Establishment counts are disclosed even for suppressed cells and "
            "were left unchanged.",
            "Suppression is NOT missing-at-random: it is applied where few "
            "establishments would make a cell identifying, so it correlates "
            "with industry concentration.",
            "No API key is required for QCEW.",
        ),
    )
    return df, prov


# ---------------------------------------------------------------------------
# Census County Business Patterns
# ---------------------------------------------------------------------------

#: CBP protects confidentiality by **noise infusion** rather than by
#: suppression: a published value may be perturbed, and a flag column reports
#: the noise range. This is the opposite strategy to QCEW, which withholds. The
#: analytical consequences differ completely and are the subject of D15.
CBP_NOISE_FLAGS: Final[tuple[str, ...]] = ("EMP_N", "PAYANN_N")


def fetch_cbp(
    *,
    year: int,
    variables: Mapping[str, str],
    geography: str = "county:*",
    within: str | None = None,
    naics: str | None = None,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Fetch County Business Patterns, or raise.

    CBP shares the Census API's transport with ACS -- and therefore the same
    HTTP 200 + ``text/html`` failure mode -- but not its statistics: these are
    establishment-register counts, not survey estimates, so there are no margins
    of error and the ACS jam-value sentinels do not apply.

    What does apply is noise infusion. Any flag column in
    :data:`CBP_NOISE_FLAGS` that is present is preserved as text rather than
    coerced to a number, so it cannot be silently summed.
    """
    if not variables:
        raise ValueError("At least one CBP variable is required.")
    endpoint = f"{CENSUS_HOST}/{year}/cbp"
    params = {
        "get": ",".join(variables),
        "for": geography,
        "key": load_key("CENSUS_API_KEY"),
    }
    if within:
        params["in"] = within
    if naics:
        params["NAICS2017"] = naics

    http = session or requests
    try:
        resp = http.get(endpoint, params=params, timeout=120)
    except requests.RequestException as exc:
        raise UpstreamError(f"CBP request to {endpoint} failed: {redact(exc)}") from exc
    reject_bot_challenge(resp, source="the Census Bureau (CBP)", endpoint=endpoint)
    if resp.status_code != 200:
        raise UpstreamError(f"CBP returned HTTP {resp.status_code} for {endpoint}.")

    rows = _assert_json_payload(resp, endpoint)
    if not isinstance(rows, list) or len(rows) < 2:
        raise ResponseShapeError(f"{endpoint} returned no data rows.")
    header, *body = rows
    df = pd.DataFrame(body, columns=header)

    missing = [v for v in variables if v not in df.columns]
    if missing:
        raise SchemaError(f"CBP response is missing requested variables {missing}.")

    flags_present = [c for c in CBP_NOISE_FLAGS if c in df.columns]
    for code in variables:
        if code in flags_present or not code.isupper():
            continue
        if code.endswith("_LABEL") or code in {"NAME", "NAICS2017"}:
            continue
        df[code] = pd.to_numeric(df[code], errors="coerce")

    prov = DataProvenance.build(
        hash_basis="canonical-rows",
        request_params=params,
        pinned=False,
        source_name="U.S. Census Bureau",
        dataset=f"County Business Patterns {year}",
        vintage=str(year),
        endpoint=endpoint,
        variables=dict(variables),
        payload=canonical_rows(resp.content),
        row_count=len(df),
        column_count=len(df.columns),
        notes=(
            "CBP counts establishments from the Business Register; these are not "
            "survey estimates and carry no margin of error.",
            "Confidentiality is protected by NOISE INFUSION, not suppression: a "
            "published value may be perturbed. Flag column(s) present: "
            + (", ".join(flags_present) if flags_present else "none requested") + ".",
            "CBP omits industry cells it does not publish rather than flagging "
            "them, so an industry absent from a response may not exist or may "
            "simply be unpublished. The response cannot distinguish the two.",
            "Reference period is the pay period including 12 March.",
        ),
    )
    return df, prov


# --------------------------------------------------------------------------- #
# HUD USER — Fair Market Rents
# --------------------------------------------------------------------------- #

HUD_HOST: Final[str] = "https://www.huduser.gov/hudapi/public"

#: HUD's API is rate limited. The response carries the budget in headers; the
#: fetcher surfaces what is left rather than discovering the limit by hitting it.
HUD_RATELIMIT_HEADERS: Final[tuple[str, ...]] = ("x-ratelimit-limit", "x-ratelimit-remaining")

#: The bedroom keys HUD returns, in order, and the column names used here.
HUD_BEDROOMS: Final[tuple[tuple[str, str], ...]] = (
    ("Efficiency", "fmr_0"),
    ("One-Bedroom", "fmr_1"),
    ("Two-Bedroom", "fmr_2"),
    ("Three-Bedroom", "fmr_3"),
    ("Four-Bedroom", "fmr_4"),
)

#: HUD's published per-minute request budget. Observed from the response headers
#: and used as the pacing target; the constant is only the starting assumption.
HUD_DEFAULT_RATE_LIMIT: Final[int] = 60

#: Timestamps of recent HUD requests, for proactive pacing.
_HUD_REQUEST_TIMES: deque[float] = deque()
_HUD_OBSERVED_LIMIT: list[int] = [HUD_DEFAULT_RATE_LIMIT]


#: Pace at a fraction of the published budget. Pacing exactly at the stated 60
#: per minute still drew 429s in practice, which means the server's window is not
#: the same rolling window measured here. Leaving headroom is cheaper than
#: reverse-engineering someone else's limiter.
HUD_RATE_SAFETY: Final[float] = 0.75


def _hud_wait_for_budget() -> None:
    """Sleep, if needed, to stay inside HUD's per-minute budget.

    A county-level CHAS sweep is one request per county: Virginia alone is 134,
    which exceeds the minute budget and fails partway through with a 429. Pacing
    belongs here rather than in every notebook that loops over geographies --
    otherwise each one reinvents it, and the ones that forget fail at a different
    county each run, which reads as a data problem rather than a quota.
    """
    limit = max(1, int(_HUD_OBSERVED_LIMIT[0] * HUD_RATE_SAFETY))
    window = 60.0
    min_gap = window / max(1, limit)
    while True:
        now = time.monotonic()
        while _HUD_REQUEST_TIMES and now - _HUD_REQUEST_TIMES[0] >= window:
            _HUD_REQUEST_TIMES.popleft()
        # A steady interval as well as a window cap: a burst that fits the window
        # can still trip a server-side limiter aligned to a different minute.
        gap = now - _HUD_REQUEST_TIMES[-1] if _HUD_REQUEST_TIMES else min_gap
        if len(_HUD_REQUEST_TIMES) < limit and gap >= min_gap:
            _HUD_REQUEST_TIMES.append(now)
            return
        if gap < min_gap:
            time.sleep(min_gap - gap)
            continue
        time.sleep(max(0.05, window - (now - _HUD_REQUEST_TIMES[0]) + 0.05))


def _hud_get(
    path: str,
    *,
    session: requests.Session | None = None,
    timeout: int = 60,
    _retry: bool = False,
) -> tuple[dict, dict[str, str]]:
    """One authenticated HUD request, paced, with the challenge and shape checks."""
    _hud_wait_for_budget()
    endpoint = f"{HUD_HOST}/{path}"
    headers = {
        "Authorization": f"Bearer {load_key('HUD_API_KEY')}",
        "Accept": "application/json",
    }
    http = session or requests
    try:
        resp = http.get(endpoint, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        raise UpstreamError(f"HUD request for {path} failed: {redact(exc)}") from exc

    # HUD challenges /portal/ (the bulk files) and not /hudapi/ (this path), but
    # which paths are challenged is HUD's decision and can change.
    reject_bot_challenge(resp, source="HUD USER", endpoint=endpoint)
    if resp.status_code == 401:
        raise MissingCredentialError(
            "HUD rejected the credential (HTTP 401). Check HUD_API_KEY is a current "
            "token from https://www.huduser.gov/portal/dataset/fmr-api.html."
        )
    if resp.status_code == 429:
        # One bounded wait, then fail. A rate limit is a known, self-clearing
        # condition with a published window, so a single wait is honest recovery
        # rather than retrying into an unknown error; a second 429 means the
        # pacing assumption is wrong and should surface rather than loop.
        if not _retry:
            time.sleep(61.0)
            _HUD_REQUEST_TIMES.clear()
            return _hud_get(path, session=session, timeout=timeout, _retry=True)
        raise UpstreamError(
            f"HUD rate limit exceeded for {path} after waiting out one full window. "
            f"Limit {resp.headers.get('x-ratelimit-limit', '?')} per minute; this "
            f"module paces at {HUD_RATE_SAFETY:.0%} of it."
        )
    if resp.status_code != 200:
        raise UpstreamError(
            f"HUD returned HTTP {resp.status_code} for {path}. A 404 here means the "
            f"entity id or the year does not exist, not that the value is zero."
        )

    head = resp.text.lstrip()[:200].lower()
    if "<html" in head or "<!doctype" in head:
        raise ResponseShapeError(
            f"HUD returned HTML rather than JSON for {path}; a 200 carrying an error "
            f"page would otherwise be parsed as data."
        )
    try:
        payload = resp.json()
    except ValueError as exc:
        raise ResponseShapeError(f"HUD response for {path} is not JSON: {redact(exc)}") from exc

    budget = {h: resp.headers[h] for h in HUD_RATELIMIT_HEADERS if h in resp.headers}
    if (observed := budget.get("x-ratelimit-limit")) and str(observed).isdigit():
        _HUD_OBSERVED_LIMIT[0] = int(observed)
    return payload, budget


def fetch_hud_fmr_county(
    *,
    fips: str,
    year: int,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Fetch one county's Fair Market Rents for one fiscal year.

    ``year`` is **required**. HUD's API defaults to the current schedule when the
    parameter is omitted, which makes an un-pinned call return different numbers
    after October 1 — the same defect :func:`fetch_fred` refuses an open date
    range for.

    **Small-area rows are not silently flattened.** For a metropolitan area with
    Small Area FMRs, ``basicdata`` is a *list* of ZIP-level records rather than a
    single object. Averaging them would invent a county figure HUD does not
    publish, so this raises instead and names the condition.
    """
    if not str(fips).strip():
        raise ValueError("A HUD 10-character entity id is required, e.g. '5100199999'.")

    payload, budget = _hud_get(f"fmr/data/{fips}?year={int(year)}", session=session)
    data = payload.get("data")
    if not isinstance(data, dict):
        raise SchemaError(f"HUD response for {fips} has no `data` object.")

    basic = data.get("basicdata")
    if isinstance(basic, list):
        raise ResponseShapeError(
            f"HUD returned {len(basic)} Small Area FMR records for {fips} rather than "
            f"one county figure. This area sets payment standards by ZIP code; there "
            f"is no single county FMR to return, and averaging the ZIPs would "
            f"manufacture one."
        )
    if not isinstance(basic, dict):
        raise SchemaError(f"HUD response for {fips} has no `basicdata` object.")

    missing = [key for key, _ in HUD_BEDROOMS if key not in basic]
    if missing:
        raise SchemaError(f"HUD response for {fips} lacks bedroom key(s) {missing}.")

    row = {
        "fips": str(fips),
        "area_name": data.get("area_name"),
        "county_name": data.get("county_name"),
        "metro_status": data.get("metro_status"),
        "year": str(basic.get("year", year)),
    }
    row.update({col: basic[key] for key, col in HUD_BEDROOMS})
    frame = pd.DataFrame([row])

    returned_year = str(basic.get("year", "")).strip()
    if returned_year and returned_year != str(year):
        raise ResponseShapeError(
            f"HUD was asked for FY{year} and answered with FY{returned_year} for {fips}. "
            f"Silently accepting it would put one year's payment standard in another "
            f"year's column."
        )

    prov = DataProvenance.build(
        hash_basis="canonical-json",
        pinned=False,
        source_name="U.S. Department of Housing and Urban Development (HUD USER)",
        dataset="Fair Market Rents, county level",
        vintage=f"FY{year}",
        endpoint=f"{HUD_HOST}/fmr/data/{fips}?year={int(year)}",
        variables={col: f"FMR, {key}" for key, col in HUD_BEDROOMS},
        payload=json.dumps(payload, sort_keys=True).encode(),
        row_count=len(frame),
        column_count=len(frame.columns),
        notes=(
            "Administratively determined: an estimate of a 40th-percentile gross "
            "rent by definition (24 CFR 888.113) and binding by statute "
            "(42 USC 1437f). No uncertainty is published.",
            "The figure is trended forward to the fiscal year it binds, so it is "
            "not comparable to a contemporaneous survey estimate without stating "
            "both reference periods.",
            "HUD revises schedules after they take effect and publishes no "
            "revision series; this records the value the API served on this date.",
            f"Rate-limit budget at retrieval: {budget or 'not reported'}.",
        ),
    )
    return frame, prov


# --------------------------------------------------------------------------- #
# HUD USER — CHAS (Comprehensive Housing Affordability Strategy)
# --------------------------------------------------------------------------- #

#: CHAS summary levels, as the API numbers them.
CHAS_SUMMARY_LEVELS: Final[dict[str, int]] = {
    "nation": 1, "state": 2, "county": 3, "mcd": 4, "place": 5,
}

#: The vintage the API serves when ``year`` is omitted is "the latest", which
#: moves. Every call here names one. The documented list stops at 2014-2018
#: while later ranges are served, so the documentation is not the authority on
#: which vintages exist — the API is.
CHAS_YEAR_PATTERN: Final = re.compile(r"^\d{4}-\d{4}$")

#: Columns the published data dictionary describes but the API never returns.
#: Recorded so a caller asking for one gets an explanation rather than a
#: ``KeyError`` on a name they read in HUD's own documentation.
CHAS_DOCUMENTED_NOT_SERVED: Final[frozenset[str]] = frozenset(
    {"G21", "G22", "G23", "H17", "I17", "J17"}
)

#: Dictionary entries whose descriptions are duplicated in HUD's documentation.
#: For each pair the second is documented identically to the first, and the data
#: contradicts that: the second is smaller in almost every county, consistent
#: with it being the ">50%" cut rather than a repeat of ">30%".
CHAS_MISDOCUMENTED: Final[dict[str, str]] = {
    "H14": "H13", "I14": "I13", "J14": "J13",
}


class EmptyResultError(ResponseShapeError):
    """The publisher returned success and no rows.

    CHAS answers an unrecognised ``entityId`` with **HTTP 200 and ``[]``** rather
    than a 404, so a zero-padded county code — the spelling HUD's own FMR API
    requires — silently yields nothing. An empty frame is not an empty
    population, and the difference has to be raised rather than returned.
    """


def _chas_number(value: object) -> float | None:
    """CHAS counts arrive as float-formatted strings, or as JSON ``null``.

    ``"205.0"`` defeats ``int()``, and ``null`` is how disclosure suppression
    reaches the caller — there is no flag column. Suppression is preserved as
    ``NaN`` rather than zero, because a suppressed cell is unknown and a zero is
    a measurement (the mistake QCEW's published zeros invite; see D09).
    """
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_chas(
    *,
    year: str,
    summary_level: str = "county",
    state_id: str | int | None = None,
    entity_id: str | int | None = None,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Fetch one CHAS record set for one explicit vintage.

    CHAS is a **custom tabulation**: the Census Bureau retabulates ACS microdata
    to HUD's specification, cross-cutting household income — measured against
    HUD's own Area Median Family Income (HAMFI) — with housing problems and
    tenure. Two consequences shape this function.

    **The uncertainty does not survive the tabulation.** CHAS serves 129 count
    columns and no margin of error on any of them, though every figure descends
    from the same survey whose defining feature is a published margin. Nothing
    here can reconstruct it; the notebook that uses this compares against the ACS
    table the counts derive from and reports the interval CHAS drops.

    **``entity_id`` must not be zero-padded.** ``59`` is Fairfax County;
    ``059`` returns HTTP 200 and ``[]``. The same publisher's FMR API requires
    the padded ten-character form, so the two are incompatible and neither
    fails loudly. Padding is stripped here and an empty result is raised.
    """
    if summary_level not in CHAS_SUMMARY_LEVELS:
        raise ValueError(
            f"summary_level must be one of {sorted(CHAS_SUMMARY_LEVELS)}, not {summary_level!r}."
        )
    if not CHAS_YEAR_PATTERN.match(str(year)):
        raise ValueError(
            f"year must be an explicit ACS range such as '2018-2022', not {year!r}. "
            f"The API defaults to 'the latest range', which changes under a "
            f"notebook that does not name one."
        )
    level = CHAS_SUMMARY_LEVELS[summary_level]
    params = [f"type={level}", f"year={year}"]
    if level >= 2:
        if state_id is None:
            raise ValueError(f"state_id is required for summary_level {summary_level!r}.")
        params.append(f"stateId={int(state_id)}")
    if level >= 3:
        if entity_id is None:
            raise ValueError(f"entity_id is required for summary_level {summary_level!r}.")
        # Stripping the padding rather than rejecting it: the padded spelling is
        # what this publisher's other API requires, so it is the likely input.
        params.append(f"entityId={int(str(entity_id).lstrip('0') or 0)}")

    query = "&".join(params)
    payload, budget = _hud_get(f"chas?{query}", session=session)
    if not isinstance(payload, list):
        raise SchemaError(f"CHAS returned {type(payload).__name__}, expected a list of records.")
    if not payload:
        raise EmptyResultError(
            f"CHAS returned HTTP 200 and no rows for `{query}`. This is how an "
            f"unrecognised entityId or an unserved year range fails — not with a "
            f"404. Check that entityId is unpadded and that the year range exists."
        )

    frame = pd.DataFrame(payload)
    coded = [c for c in frame.columns if re.fullmatch(r"[A-Z]+\d+", c)]
    suppressed = int(frame[coded].isna().sum().sum()) if coded else 0
    for column in coded:
        frame[column] = frame[column].map(_chas_number)
    suppressed += int(frame[coded].isna().sum().sum()) - suppressed

    returned = set(frame.get("year", pd.Series(dtype=str)).astype(str))
    if returned and returned != {str(year)}:
        raise ResponseShapeError(
            f"CHAS was asked for {year!r} and answered with {sorted(returned)}."
        )

    prov = DataProvenance.build(
        hash_basis="canonical-json",
        pinned=False,
        source_name="U.S. Department of Housing and Urban Development (HUD USER)",
        dataset=f"CHAS custom tabulation, {summary_level} summary level",
        vintage=str(year),
        endpoint=f"{HUD_HOST}/chas?{query}",
        variables={c: "see HUD CHAS data dictionary" for c in coded},
        payload=json.dumps(payload, sort_keys=True).encode(),
        row_count=len(frame),
        column_count=len(frame.columns),
        notes=(
            "Custom tabulation of ACS microdata prepared by the Census Bureau for "
            "HUD. Income categories are relative to HAMFI, an administratively "
            "determined figure, so the category boundaries move between vintages.",
            "No margin of error is published on any column, though every count "
            "descends from a survey that publishes one.",
            f"Suppressed cells arrive as JSON null and are kept as NaN: "
            f"{suppressed} of {len(frame) * len(coded)} coded cells.",
            f"Columns documented but never served: {sorted(CHAS_DOCUMENTED_NOT_SERVED)}.",
            f"Dictionary entries duplicated in HUD's documentation and distinct in "
            f"the data: {sorted(CHAS_MISDOCUMENTED)}.",
            f"Rate-limit budget at retrieval: {budget or 'not reported'}.",
        ),
    )
    return frame, prov


# --------------------------------------------------------------------- PLACES
#
# CDC PLACES is the corpus's eighth regime and the first MODELLED one: a county
# value is a prediction from a multilevel model fitted to BRFSS and
# poststratified, not a measurement taken in that county. There may be no BRFSS
# respondents in the county at all. The interval is therefore a modelled
# credible interval, not a sampling margin -- see handbook §1.8 and §7.2.
#
# Note the host. The upstream `krl-data-connectors` CDC connector targets
# wonder.cdc.gov, which answers 403 to datacenter addresses from every network
# path tested on 2026-09-14, so it cannot run in CI or any cloud environment.
# data.cdc.gov (Socrata) is a different host and answers normally. That
# connector also coerces "Suppressed", "Unreliable" and "Not Applicable" to a
# single NaN; this module never uses it, and PLACES does not use those markers.
PLACES_HOST: Final[str] = "https://data.cdc.gov/resource"

#: Release year -> Socrata asset id, county level, GIS-friendly format. Each
#: release is a SEPARATE immutable asset, which is a third retrievability mode
#: alongside FRED's vintages and everything else's current-only (handbook §5.5).
PLACES_COUNTY_RELEASES: Final[dict[str, str]] = {
    "2025": "i46a-9kgh",
    "2024": "d3i6-k6z5",
    "2023": "7cmc-7y5g",
    "2022": "xyst-f73f",
    "2021": "kmvs-jkvx",
    "2020": "mssc-ksj7",
}

PLACES_INTERVAL_PATTERN: Final[re.Pattern[str]] = re.compile(r"-?\d+\.?\d*")


def parse_places_interval(text: object) -> tuple[float, float]:
    """Parse a PLACES interval, which ships as the string ``'( 8.8, 11.3)'``.

    The space after the opening parenthesis is real. Extracting numerals is
    robust to it; slicing by position is not. This is exported because every
    notebook touching PLACES needs it and none should reimplement it.
    """
    if not isinstance(text, str):
        return (float("nan"), float("nan"))
    found = PLACES_INTERVAL_PATTERN.findall(text)
    if len(found) < 2:
        return (float("nan"), float("nan"))
    return (float(found[0]), float(found[1]))


def fetch_places_county(
    *,
    measures: Sequence[str],
    release: str = "2025",
    adjustment: str = "crude",
    state: str | None = None,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Fetch CDC PLACES county estimates for one explicit release.

    ``adjustment`` selects crude or age-adjusted prevalence and is required to be
    explicit because the two answer different questions: age-adjusted is for
    COMPARING places, crude is for COUNTING burden in one. Defaulting silently
    is how the wrong one ends up in a figure.

    The returned frame carries, per measure, ``<m>_prev``, ``<m>_lo``, ``<m>_hi``
    and ``<m>_se`` -- the last a symmetric-normal standard error recovered from
    the interval, which is an APPROXIMATION because PLACES intervals are mildly
    asymmetric. The provenance records the worst asymmetry observed so a caller
    can decide whether the approximation is tolerable for their purpose.

    No credential is required. PLACES is public and unkeyed.
    """
    if release not in PLACES_COUNTY_RELEASES:
        raise ValueError(
            f"release must be one of {sorted(PLACES_COUNTY_RELEASES)}, not {release!r}. "
            f"Each PLACES release is a separate dataset; naming one pins the vintage."
        )
    if adjustment not in {"crude", "adj"}:
        raise ValueError(
            f"adjustment must be 'crude' or 'adj', not {adjustment!r}. Age-adjusted "
            f"prevalence compares places; crude prevalence counts burden in one."
        )
    if not measures:
        raise ValueError("measures must name at least one PLACES measure.")

    asset = PLACES_COUNTY_RELEASES[release]
    columns = ["countyfips", "countyname", "statedesc", "totalpopulation"]
    for measure in measures:
        columns += [f"{measure}_{adjustment}prev", f"{measure}_{adjustment}95ci"]
    params: dict[str, str] = {"$select": ",".join(columns), "$limit": "5000"}
    if state is not None:
        params["$where"] = f"statedesc='{state}'"

    url = f"{PLACES_HOST}/{asset}.json"
    resp = (session or requests).get(url, params=params, timeout=120)
    reject_bot_challenge(resp, source="CDC PLACES", endpoint=url)
    if resp.status_code != 200:
        raise DataAccessError(
            f"CDC PLACES returned HTTP {resp.status_code} for release {release}. "
            f"Body begins: {resp.text[:200]!r}"
        )
    payload = resp.json()
    if not isinstance(payload, list):
        raise SchemaError(
            f"CDC PLACES returned {type(payload).__name__}, expected a list of records."
        )
    if not payload:
        raise EmptyResultError(
            f"CDC PLACES returned HTTP 200 and no rows for release {release}"
            + (f", state {state!r}" if state else "")
            + ". An unrecognised measure name or state spelling fails this way, "
            "not with a 404."
        )

    frame = pd.DataFrame(payload)
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise SchemaError(
            f"CDC PLACES release {release} does not serve {missing}. Measure names "
            f"differ between releases; check the release's own column list."
        )

    worst_asymmetry = 0.0
    for measure in measures:
        est = pd.to_numeric(frame[f"{measure}_{adjustment}prev"], errors="coerce")
        bounds = frame[f"{measure}_{adjustment}95ci"].map(parse_places_interval)
        lo = pd.Series([b[0] for b in bounds], index=frame.index)
        hi = pd.Series([b[1] for b in bounds], index=frame.index)
        frame[f"{measure}_prev"] = est
        frame[f"{measure}_lo"] = lo
        frame[f"{measure}_hi"] = hi
        frame[f"{measure}_se"] = (hi - lo) / (2 * 1.959964)
        asym = ((hi - est) - (est - lo)).abs().max()
        worst_asymmetry = max(worst_asymmetry, float(asym) if pd.notna(asym) else 0.0)

    prov = DataProvenance.build(
        hash_basis="canonical-json",
        source_name="Centers for Disease Control and Prevention (PLACES)",
        dataset=f"PLACES county estimates, {release} release, {adjustment} prevalence",
        vintage=release,
        endpoint=f"{url}?{urlencode(params)}",
        variables={m: f"{m} {adjustment} prevalence and 95% interval" for m in measures},
        payload=json.dumps(payload, sort_keys=True).encode(),
        row_count=len(frame),
        column_count=len(frame.columns),
        notes=(
            "MODEL-BASED estimate. Each county value is a prediction from a "
            "multilevel model fitted to BRFSS and poststratified against Census "
            "population and ACS covariates; it is not a measurement taken in that "
            "county, and a county may contribute no BRFSS respondents at all.",
            "The published interval is a modelled credible interval, not a "
            "sampling margin of error. It is not comparable to an ACS MOE.",
            f"Standard errors here are recovered from the interval assuming "
            f"symmetry. Worst observed asymmetry in this pull: "
            f"{worst_asymmetry:.3f} percentage points.",
            "Measures within one release may rest on different BRFSS years: the "
            "2025 release uses 2023 BRFSS for 35 measures and 2022 for 5. A single "
            "release is not a single vintage.",
            "Do not rank counties on these estimates. Handbook §7.2 measures the "
            "consequence: 0 of 2,956 counties have a determined rank, including "
            "for a measure whose reliability is 0.87.",
        ),
    )
    return frame, prov


# --------------------------------------------- Opportunity Atlas (Opportunity Insights)
#
# The corpus's ninth regime and the first LINKED LONGITUDINAL one. Every other
# source here describes a population at a moment. This one describes a COHORT
# across four decades: children born 1978-1983, located by where they GREW UP,
# with adult outcomes measured at age 35. A county's value is therefore a
# statement about that place in the 1980s and 90s, and it does not update when
# the place changes -- see handbook §1.9.
#
# Estimates are built from linked federal tax and Census records, so the
# uncertainty is not sampling error in the ACS sense. Opportunity Insights
# states that it adds "small random numbers (known as 'noise') to all our
# estimates to protect the privacy of individuals", and suppresses cells with
# fewer than 20 children. The published counts are visibly non-integer as a
# result: all 3,134 counties with data carry a fractional count.
OPPORTUNITY_ATLAS_HOST: Final[str] = "https://opportunityinsights.org/wp-content/uploads"

#: Geography -> published file. These are bulk CSVs, not an API. They are fetched
#: at runtime rather than committed: the corpus has no verified redistribution
#: licence for them, and the same caution that keeps Zillow's files out of the
#: repository applies here.
OPPORTUNITY_ATLAS_FILES: Final[dict[str, str]] = {
    "county": "2018/10/county_outcomes_simple.csv",
    "cz": "2018/10/cz_outcomes_simple.csv",
    "tract": "2024/08/tract_outcomes_late_simple.csv",
}

#: The cohort this source describes, from Opportunity Insights' own FAQ.
OPPORTUNITY_ATLAS_COHORT: Final[str] = "children born 1978-1983, outcomes at age 35"


def fetch_opportunity_atlas(
    *,
    geography: str = "county",
    state_fips: str | int | None = None,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Fetch one Opportunity Atlas outcomes file.

    ``geography`` must be named explicitly. The tract file is far larger than the
    county file and the two are not interchangeable: suppression bites much
    harder at tract level, where the threshold is 20 children in the tract.

    The frame is returned as published, with two additions: ``fips`` (the
    zero-padded five-character county code, which the source does not provide --
    it ships ``state`` and ``county`` as unpadded integers) and nothing else. No
    column is renamed and no value is coerced, because the suppression pattern is
    part of what a reader needs to see.

    No credential is required.
    """
    if geography not in OPPORTUNITY_ATLAS_FILES:
        raise ValueError(
            f"geography must be one of {sorted(OPPORTUNITY_ATLAS_FILES)}, not "
            f"{geography!r}. Suppression differs sharply between them, so the "
            f"choice is analytic rather than a matter of resolution."
        )
    path = OPPORTUNITY_ATLAS_FILES[geography]
    url = f"{OPPORTUNITY_ATLAS_HOST}/{path}"

    resp = (session or requests).get(url, timeout=180)
    reject_bot_challenge(resp, source="Opportunity Insights", endpoint=url)
    if resp.status_code != 200:
        raise DataAccessError(
            f"Opportunity Insights returned HTTP {resp.status_code} for {path}. "
            f"These are bulk files on a WordPress host and their paths have moved "
            f"between releases; check the data page rather than assuming a 404 "
            f"means the file is gone. Body begins: {resp.text[:160]!r}"
        )

    frame = pd.read_csv(io.BytesIO(resp.content))
    if frame.empty:
        raise EmptyResultError(f"Opportunity Atlas file {path} parsed to zero rows.")
    for required in ("state", "county"):
        if required not in frame.columns:
            raise SchemaError(
                f"Opportunity Atlas {geography} file lacks {required!r}; columns "
                f"begin {list(frame.columns)[:6]}."
            )

    # The source ships state and county as UNPADDED integers, so Virginia's
    # Accomack County is state=51, county=1. Joining that to a Census FIPS
    # without padding silently matches nothing.
    frame["fips"] = (
        frame["state"].astype("Int64").astype(str).str.zfill(2)
        + frame["county"].astype("Int64").astype(str).str.zfill(3)
    )
    if state_fips is not None:
        frame = frame[frame["state"].astype("Int64") == int(state_fips)].copy()
        if frame.empty:
            raise EmptyResultError(
                f"No Opportunity Atlas rows for state FIPS {state_fips}."
            )

    count_col = "pooled_pooled_count"
    fractional = 0
    if count_col in frame.columns:
        counts = pd.to_numeric(frame[count_col], errors="coerce").dropna()
        fractional = int(((counts % 1).abs() > 1e-9).sum())

    prov = DataProvenance.build(
        source_name="Opportunity Insights (Opportunity Atlas)",
        dataset=f"Opportunity Atlas outcomes, {geography} level",
        vintage=OPPORTUNITY_ATLAS_COHORT,
        endpoint=url,
        variables={
            c: "see Opportunity Insights codebook"
            for c in frame.columns
            if c.startswith(("kfr", "jail", "has_dad"))
        },
        payload=resp.content,
        row_count=len(frame),
        column_count=len(frame.columns),
        notes=(
            "COHORT-FIXED. These are children born 1978-1983 with adult outcomes "
            "measured at age 35, located by WHERE THEY GREW UP rather than where "
            "they live as adults. A value describes the place decades ago and does "
            "not update as the place changes.",
            "Built from linked federal tax and Census records, not a survey. The "
            "published standard errors are not ACS-style sampling margins.",
            "Opportunity Insights states it adds random noise to all estimates for "
            "privacy, and suppresses cells with fewer than 20 children (in a tract, "
            "or of a given race and gender in a county).",
            f"Counts carrying a fractional part in this pull: {fractional} -- a "
            f"visible consequence of that noise, since a count of people cannot "
            f"genuinely be fractional.",
            "Estimates were cleared by the Census Bureau's Disclosure Review Board.",
            "`state` and `county` ship UNPADDED; the `fips` column added here is "
            "zero-padded so a join against Census geography does not silently fail.",
        ),
    )
    return frame, prov


def fetch_chas_county_list(
    *,
    state_id: str | int,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """List a state's CHAS county entity ids, **deduplicated**.

    HUD's listing repeats itself: Virginia returns 267 entries for 134 distinct
    counties, each id appearing twice. Iterating it as served fetches every
    county twice, and a frame built from it double-counts every household in the
    state without anything looking wrong. The duplication is removed here and
    the counts are reported so the caller can see it happened.
    """
    payload, _ = _hud_get(f"chas/listCounties/{int(state_id)}", session=session)
    if not isinstance(payload, list) or not payload:
        raise EmptyResultError(f"CHAS returned no county list for state {state_id}.")
    served = pd.DataFrame(payload)
    deduped = served.drop_duplicates(subset=["entityId"]).reset_index(drop=True)
    deduped.attrs["served_rows"] = len(served)
    deduped.attrs["duplicate_rows"] = len(served) - len(deduped)
    return deduped


# ------------------------------------------------------- Business Dynamics Statistics
#
# BDS is the corpus's case of a source whose *published values* are almost
# perfectly consistent and whose *aggregations* are almost never what a reader
# expects. Three distinct mechanisms break "the parts sum to the whole", they
# act in opposite directions, and only one of them is the disclosure-avoidance
# perturbation that analysts are trained to worry about:
#
#   1. FIRM is not additive over any dimension, by definition. The Census FAQ:
#      "Geography and industry are defined at the establishment level instead of
#      the firm level. So firms with multiple establishments operating in
#      different geographies or industries will show up in the total firm data
#      for each geography or industry in which they operate at least one
#      establishment."  Summing counties therefore OVERSTATES firms, and the
#      overstatement grows with how finely the geography is cut.
#
#   2. County tabulations exclude the statewide records. The BDS codebook:
#      "The BDS also includes statewide (999) county codes. Statewide county
#      codes are assigned to establishments without a fixed location such as
#      employee leasing establishments."  The API's ``county:*`` wildcard does
#      not return them and ``for=county:999`` is rejected outright, so the
#      county-level API data CANNOT be reconciled to the state total from the
#      API alone. Summing counties therefore UNDERSTATES employment, heavily
#      and unevenly across industries.
#
#   3. Noise infusion, which is the smallest of the three by two orders of
#      magnitude and touches only the job-flow variables. Census FAQ: "Noise is
#      added at the cell level for certain variables, including: job creation,
#      job creation births, job creation continuers, job destruction, job
#      destruction deaths, job destruction continuers, and net job creation,
#      this can cause discrepancies in these statistics across tables."
#
# And the protection method is itself a dated policy variable. Department of
# Commerce Administrative Order 216-26, "Disclosure Avoidance for Statistical
# Products" (effective 4 June 2026), Sec. 5.01(c): "Noise infusion shall not be
# used for any statistical product." Sec. 5.02 makes coarsening the preferred
# replacement and permits suppression "as a last resort". The BDS methodology
# page now carries a notice that its description is no longer current. Every
# value this client returns today was produced under the prohibited method;
# values published after the transition will not be, and the two are not
# interchangeable in a time series.

BDS_HOST: Final[str] = "https://api.census.gov/data/timeseries/bds"

#: Years the published BDS time series covers. There is no "latest": a caller
#: names a year or gets an error, so a notebook re-run next year cannot
#: silently change its reference period.
BDS_YEARS: Final[range] = range(1978, 2024)

#: Variables that are **not additive over geography or industry** because the
#: unit of count is the firm, which spans both. Summing any of these across
#: counties, states or sectors double-counts, and the client says so rather
#: than leaving it to be discovered.
BDS_FIRM_LEVEL_VARIABLES: Final[frozenset[str]] = frozenset({
    "FIRM", "FIRMDEATH_FIRMS",
})

#: Variables Census documents as noise-infused at the cell level. Sums of these
#: over a partition are consistent only to within the noise.
BDS_NOISE_INFUSED_VARIABLES: Final[frozenset[str]] = frozenset({
    "JOB_CREATION", "JOB_CREATION_BIRTHS", "JOB_CREATION_CONTINUERS",
    "JOB_DESTRUCTION", "JOB_DESTRUCTION_DEATHS", "JOB_DESTRUCTION_CONTINUERS",
    "NET_JOB_CREATION",
})

#: Meanings of the ``<VAR>_F`` flag columns, from the BDS codebook and glossary.
#: A flagged cell has no usable number: ``D`` and ``S`` are withheld, ``X`` is
#: structurally absent, ``N`` is an undefined rate. All four become NaN here.
BDS_FLAG_MEANINGS: Final[dict[str, str]] = {
    "D": "disclosure suppression -- too few firms in the cell",
    "S": "data-quality suppression -- cell unreliable on time-series grounds",
    "X": "structurally missing or structurally zero",
    "N": "rate not calculable -- denominator is zero",
}

#: The disclosure-avoidance regime the currently published series was produced
#: under, and the order that ends it. Carried into provenance so a stored
#: notebook output records which regime its numbers came from.
BDS_DISCLOSURE_REGIME: Final[str] = (
    "hybrid balanced multiplicative noise infusion (adapted from County "
    "Business Patterns); prohibited prospectively by DoC DAO 216-26 "
    "Sec. 5.01(c), effective 2026-06-04, with coarsening preferred and "
    "suppression permitted only as a last resort under Sec. 5.02"
)


def fetch_bds(
    *,
    year: int,
    variables: Sequence[str],
    geography: str = "state:*",
    within: str | None = None,
    naics: str | None = None,
    extra_dimensions: Mapping[str, str] | None = None,
    include_flags: bool = True,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Fetch Business Dynamics Statistics for one year, or raise.

    Parameters
    ----------
    year:
        A year in :data:`BDS_YEARS`. Required, and not defaultable: BDS is a
        time series endpoint, and omitting ``YEAR`` returns every vintage at
        once, which is a very large response that silently changes shape
        between releases.
    variables:
        BDS variable codes, e.g. ``("FIRM", "ESTAB", "EMP")``.
    geography:
        A Census ``for`` clause: ``"us:*"``, ``"state:*"``, ``"county:*"``.
    within:
        A Census ``in`` clause, e.g. ``"state:51"``.
    naics:
        A 2017 NAICS code, or ``"*"`` for the sector decomposition. Omitted
        means the published total for all sectors (``"00"``).
    extra_dimensions:
        Further BDS dimensions such as ``{"FAGE": "*"}`` (firm age) or
        ``{"EMPSZFI": "*"}`` (firm size).
    include_flags:
        Request the ``<VAR>_F`` companion column for each requested variable
        and honour it. A flagged cell becomes NaN and the flag is preserved as
        text, so a suppressed cell can never be summed as if it were data.

    Notes
    -----
    Additivity is **not** checked here, because whether a sum is legitimate
    depends on which variable and which dimension, and the client cannot know
    the caller's intent. What it does instead is record, in provenance, which
    of the requested variables are firm-level and which are noise-infused, so
    that a stored notebook output carries the warning next to the numbers.
    """
    if year not in BDS_YEARS:
        raise ValueError(
            f"BDS year {year} is outside the published series "
            f"{BDS_YEARS.start}-{BDS_YEARS.stop - 1}. Name a published year; "
            "there is no 'latest'."
        )
    requested = [str(v).strip() for v in variables]
    if not requested:
        raise ValueError("At least one BDS variable is required.")
    if any(not v for v in requested):
        raise ValueError("BDS variable names may not be blank.")

    get_list = list(requested)
    if include_flags:
        for code in requested:
            flag = f"{code}_F"
            if flag not in get_list:
                get_list.append(flag)
    if len(get_list) > CENSUS_GET_CEILING:
        raise ValueError(
            f"{len(get_list)} columns requested (variables plus flags) exceeds "
            f"the Census API ceiling of {CENSUS_GET_CEILING}. Split the request; "
            "do not drop the flags."
        )

    params: dict[str, str] = {
        "get": ",".join(get_list),
        "for": geography,
        "YEAR": str(year),
        "key": load_key("CENSUS_API_KEY"),
    }
    if within:
        params["in"] = within
    if naics:
        params["NAICS"] = naics
    for name, value in (extra_dimensions or {}).items():
        if name in params:
            raise ValueError(f"extra_dimensions may not override {name!r}.")
        params[name] = str(value)

    http = session or requests
    try:
        resp = http.get(BDS_HOST, params=params, timeout=120)
    except requests.RequestException as exc:
        raise UpstreamError(f"BDS request to {BDS_HOST} failed: {redact(exc)}") from exc
    reject_bot_challenge(resp, source="the Census Bureau (BDS)", endpoint=BDS_HOST)
    if resp.status_code == 204:
        raise EmptyResultError(
            f"BDS returned HTTP 204 (no content) for year {year}, "
            f"geography {geography!r}. That dimension combination is not "
            "published; it is not an empty result to be treated as zero."
        )
    if resp.status_code != 200:
        raise UpstreamError(f"BDS returned HTTP {resp.status_code} for {BDS_HOST}.")

    rows = _assert_json_payload(resp, BDS_HOST)
    if not isinstance(rows, list) or len(rows) < 2:
        raise ResponseShapeError(f"{BDS_HOST} returned no data rows.")
    header, *body = rows
    frame = pd.DataFrame(body, columns=header)

    missing = [v for v in requested if v not in frame.columns]
    if missing:
        raise SchemaError(f"BDS response is missing requested variables {missing}.")

    suppressed: dict[str, int] = {}
    for code in requested:
        numeric = pd.to_numeric(frame[code], errors="coerce")
        flag_col = f"{code}_F"
        if flag_col in frame.columns:
            flag = frame[flag_col].astype("string")
            unknown = sorted(
                set(flag.dropna().unique()) - set(BDS_FLAG_MEANINGS)
            )
            if unknown:
                raise SchemaError(
                    f"BDS returned unrecognised flag value(s) {unknown} in "
                    f"{flag_col}. The documented values are "
                    f"{sorted(BDS_FLAG_MEANINGS)}. Refusing to guess."
                )
            blocked = flag.notna()
            if blocked.any():
                numeric = numeric.mask(blocked)
                suppressed[code] = int(blocked.sum())
            frame[flag_col] = flag
        frame[code] = numeric

    firm_level = sorted(set(requested) & BDS_FIRM_LEVEL_VARIABLES)
    noisy = sorted(set(requested) & BDS_NOISE_INFUSED_VARIABLES)
    notes = [
        f"Disclosure-avoidance regime of this vintage: {BDS_DISCLOSURE_REGIME}.",
        "Noise is fixed at tabulation, not per request: repeating a query "
        "returns identical values, so the perturbation cannot be averaged away "
        "by resampling.",
    ]
    if firm_level:
        notes.append(
            "NOT ADDITIVE over geography or industry: "
            + ", ".join(firm_level)
            + ". A firm with establishments in several counties, states or "
            "sectors is counted once in each, so summing these across a "
            "partition double-counts."
        )
    if noisy:
        notes.append(
            "Noise-infused at the cell level: " + ", ".join(noisy)
            + ". Sums over a partition are consistent only to within the noise."
        )
    if geography.startswith("county"):
        notes.append(
            "County tabulations exclude the statewide (999) records, which the "
            "codebook assigns to 'establishments without a fixed location such "
            "as employee leasing establishments'. The API does not serve them, "
            "so county rows cannot be reconciled to the state total from the "
            "API alone, and summing them understates employment -- most "
            "severely in NAICS 56."
        )
    if suppressed:
        notes.append(
            "Suppressed or structurally-missing cells set to NaN (never zero): "
            + ", ".join(f"{k}={v}" for k, v in sorted(suppressed.items()))
            + ". Flag meanings: "
            + "; ".join(f"{k}={v}" for k, v in sorted(BDS_FLAG_MEANINGS.items()))
            + "."
        )
    notes.append(
        "Rate variables use a Davis-Haltiwanger-Schuh denominator. DENOM is the "
        "EMPLOYMENT DHS denominator and is the wrong denominator for "
        "establishment entry and exit rates; use "
        "bds_prior_year_establishments() instead."
    )

    prov = DataProvenance.build(
        hash_basis="canonical-rows",
        pinned=False,
        source_name="U.S. Census Bureau",
        dataset=f"Business Dynamics Statistics {year}",
        vintage=str(year),
        endpoint=BDS_HOST,
        variables={code: code for code in requested},
        payload=canonical_rows(resp.content),
        row_count=len(frame),
        column_count=len(frame.columns),
        notes=tuple(notes),
    )
    return frame, prov


def bds_prior_year_establishments(frame: pd.DataFrame) -> pd.Series:
    """Prior-year establishment count, derived **within the same vintage**.

    The Census BDS FAQ gives the establishment entry rate as
    ``100 * estabs_entry_t / (0.5 * (estabs_t + estabs_{t-1}))`` and instructs
    that the prior-year count be derived as
    ``estabs_{t-1} = estabs_t + estabs_exit_t - estabs_entry_t`` rather than
    read from the previous year's published file.

    The distinction is not pedantic. Measured on Virginia's 133 county
    equivalents for 2022, the within-vintage derivation reproduces every
    published entry rate to five decimal places (133/133), while substituting
    the 2021 published ESTAB reproduces 119/133 -- because 27 of the 133
    counties have a different prior-year establishment count depending on which
    route is taken. A longitudinal statistic has to be built inside one
    vintage; mixing vintages reintroduces revision as measurement error.
    """
    for column in ("ESTAB", "ESTABS_EXIT", "ESTABS_ENTRY"):
        if column not in frame.columns:
            raise SchemaError(
                f"bds_prior_year_establishments() needs {column}; the frame has "
                f"{sorted(frame.columns)}."
            )
    return (
        frame["ESTAB"].astype(float)
        + frame["ESTABS_EXIT"].astype(float)
        - frame["ESTABS_ENTRY"].astype(float)
    )


# --------------------------------------------------------- BEA Regional (ACPSA)
#
# The Bureau of Economic Analysis is the corpus's first SATELLITE ACCOUNT, and it
# fails in none of the ways the other ten regimes do. Nothing is sampled, so there
# is no margin. Nothing is withheld: 408 state-by-industry cells checked across the
# eight smallest ACPSA lines returned 408 numbers and no suppression flag. Nothing
# is perturbed, and the parts sum to the whole exactly -- states to the nation at
# 0.0000%, subtotals to their total at 0.00000%.
#
# That is because a satellite account is not a measurement. It is a RE-PARTITION of
# an account that already exists, under a published boundary decision about what
# belongs inside it. The entire error budget sits in that boundary, and none of it
# is published as a number.
#
# Three transport-level traps are specific to this source and are handled here.
#
# 1. BEA ECHOES THE CREDENTIAL. Every response carries the submitted UserID back at
#    ``BEAAPI.Request.RequestParam[i].ParameterValue``. Probed against a live key:
#    exactly one occurrence, at exactly that path. `redact` would scrub it from an
#    error string, but a parsed payload is not a string -- it reaches a DataFrame,
#    a ``print``, and a stored notebook output as structured data that no display
#    filter sees. So the Request block is removed from the parsed document before
#    anything else touches it, and the provenance hash is taken over the STRIPPED
#    payload. Hashing the raw body would have made every analyst's hash different
#    from every other analyst's, because each one's key is in it -- a provenance
#    record nobody else can reproduce is not a provenance record.
#
# 2. AN ERROR ARRIVES AS HTTP 200. A rejected request returns status 200 with
#    ``BEAAPI.Error`` present and ``BEAAPI.Results`` absent. Code that branches on
#    the status line reads the error envelope as an empty result set.
#
# 3. ``Year`` IS OPTIONAL AND DEFAULTS TO ``LAST5``. The Regional endpoint takes
#    four parameters and none of them is a vintage; the only temporal control is a
#    window that moves with each annual release. A call that omits Year returns
#    different years next year and raises nothing. It is required here.

BEA_HOST: Final[str] = "https://apps.bea.gov/api/data"

#: The path, as a key sequence, at which BEA returns the submitted credential.
BEA_CREDENTIAL_ECHO_PATH: Final[tuple[str, ...]] = ("BEAAPI", "Request")

#: ACPSA tables in the Regional dataset. Named so a caller cannot reach for an
#: arbitrary Regional table through this function and inherit ACPSA's provenance
#: notes, which would attach the wrong caveats to the wrong numbers.
BEA_ACPSA_TABLES: Final[dict[str, str]] = {
    "SAACArtsVA": "ACPSA value added by ACPSA industry",
    "SAACArtsComp": "ACPSA compensation by ACPSA industry",
    "SAACArtsEmp": "ACPSA full-time and part-time employment by ACPSA industry",
    "SAACVALQ": "Arts value added location quotient",
    "SAACCompLQ": "Arts compensation location quotient",
    "SAACVARatio": "Arts value added ratio",
    "SAACCompRatio": "Arts compensation ratio",
}

#: The line-code hierarchy of the ACPSA value-added table, which the API does not
#: express. Every line arrives as a sibling row with no depth column, and the
#: column therefore contains a grand total, a subject total, three subtotals and
#: thirty-four leaves at the same level. Summing it naively gives 26.54x the true
#: ACPSA total, because line 1 is the whole state economy rather than an arts line.
BEA_ACPSA_LINE_ROLES: Final[dict[str, str]] = {
    "1": "grand total -- TOTAL VALUE ADDED OF THE WHOLE ECONOMY, not an arts line",
    "10": "subject total -- total ACPSA value added",
    "100": "subtotal -- core arts and cultural production",
    "200": "subtotal -- supporting arts and cultural production",
    "300": "subtotal -- all other industries",
}


class BEARequestError(DataAccessError):
    """BEA returned HTTP 200 carrying ``BEAAPI.Error`` instead of results."""


def _strip_bea_credential_echo(document: object) -> object:
    """Remove the block in which BEA repeats the submitted credential.

    Returns the same document with ``BEAAPI.Request`` removed. Called before any
    other read of the payload, so no later code path -- frame construction,
    provenance, an exception message -- can carry the key.
    """
    if isinstance(document, dict):
        envelope = document.get("BEAAPI")
        if isinstance(envelope, dict):
            envelope.pop("Request", None)
    return document


def fetch_bea_regional(
    *,
    table: str,
    line_code: str,
    year: int | str,
    geo_fips: str = "STATE",
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Fetch one ACPSA table, line and year from BEA Regional, or raise.

    Parameters
    ----------
    table:
        A key of :data:`BEA_ACPSA_TABLES`.
    line_code:
        A single ACPSA line code, or ``"ALL"``. BEA accepts ``"ALL"`` only when
        one geography is requested, and says so in an HTTP 200 error envelope;
        that combination is rejected here before the request is sent.
    year:
        A four-digit year. Required. BEA's own default is ``LAST5``, a window
        that moves with each annual release, which is not a vintage a stored
        artifact can cite.
    geo_fips:
        ``"STATE"`` for the 51 state rows, ``"00000"`` for the United States row,
        or an explicit 5-character code. Note that ``"US"`` is accepted by the
        API and returns **zero rows**, which is the shape of a successful empty
        result rather than an error.
    """
    if table not in BEA_ACPSA_TABLES:
        raise ValueError(
            f"{table!r} is not an ACPSA table. This client serves only "
            f"{sorted(BEA_ACPSA_TABLES)}; other Regional tables carry different "
            "caveats and must not inherit ACPSA's provenance notes."
        )
    code = str(line_code).strip()
    if not code:
        raise ValueError("A BEA line code is required.")
    text_year = str(year).strip()
    if not re.fullmatch(r"\d{4}", text_year):
        raise ValueError(
            f"year must be a four-digit year, not {year!r}. BEA's own default is "
            "'LAST5', a moving window; a stored artifact cannot cite it."
        )
    if code.upper() == "ALL" and geo_fips.upper() in {"STATE", "COUNTY", "MSA"}:
        raise ValueError(
            "BEA accepts line_code='ALL' only for a single geography. Asking for "
            f"'ALL' across {geo_fips!r} returns an HTTP 200 error envelope, not "
            "data. Request one geography, or iterate the line codes."
        )

    params = {
        "UserID": load_key("BEA_API_KEY"),
        "method": "GetData",
        "datasetname": "Regional",
        "TableName": table,
        "LineCode": code,
        "GeoFIPS": geo_fips,
        "Year": text_year,
        "ResultFormat": "JSON",
    }
    http = session or requests
    try:
        resp = http.get(BEA_HOST, params=params, timeout=120)
    except requests.RequestException as exc:
        raise UpstreamError(f"BEA request to {BEA_HOST} failed: {redact(exc)}") from exc
    reject_bot_challenge(resp, source="the Bureau of Economic Analysis", endpoint=BEA_HOST)
    if resp.status_code != 200:
        raise UpstreamError(f"BEA returned HTTP {resp.status_code} for {BEA_HOST}.")

    document = _strip_bea_credential_echo(_assert_json_payload(resp, BEA_HOST))
    if not isinstance(document, dict) or "BEAAPI" not in document:
        raise ResponseShapeError(f"{BEA_HOST} returned JSON without a BEAAPI envelope.")
    envelope = document["BEAAPI"]

    if "Error" in envelope:
        error = envelope["Error"]
        detail = error.get("ErrorDetail") or {}
        raise BEARequestError(
            "BEA returned HTTP 200 carrying an error envelope rather than results "
            f"(APIErrorCode {error.get('APIErrorCode')!r}): "
            f"{redact(error.get('APIErrorDescription'))} "
            f"{redact(detail.get('Description', ''))}".strip()
        )

    results = envelope.get("Results")
    if isinstance(results, list):
        results = results[0] if results else None
    if not isinstance(results, dict) or "Data" not in results:
        raise ResponseShapeError(
            f"{BEA_HOST} returned a BEAAPI envelope with neither Error nor Data."
        )
    rows = results["Data"]
    if not rows:
        raise EmptyResultError(
            f"BEA returned zero rows for {table} line {code}, geography "
            f"{geo_fips!r}, year {text_year}. A zero-row success is BEA's answer "
            "to an unrecognised geography -- 'US' does this -- and is not an "
            "empty region."
        )

    frame = pd.DataFrame(rows)
    for column in ("Code", "GeoFips", "GeoName", "TimePeriod", "CL_UNIT", "DataValue"):
        if column not in frame.columns:
            raise SchemaError(f"BEA response is missing the {column!r} column.")

    # DataValue arrives comma-grouped. Anything that does not parse is kept
    # visible rather than coerced: BEA footnotes non-disclosure and
    # not-applicable as text, and a silent NaN would hide that they occurred.
    frame["DataValueText"] = frame["DataValue"].astype("string")
    frame["DataValue"] = pd.to_numeric(
        frame["DataValueText"].str.replace(",", "", regex=False), errors="coerce"
    )
    unparsed = frame.loc[frame["DataValue"].isna(), "DataValueText"]
    frame["LineCode"] = frame["Code"].astype("string").str.rsplit("-", n=1).str[-1]
    frame["LineRole"] = frame["LineCode"].map(BEA_ACPSA_LINE_ROLES).fillna("leaf")

    units = sorted(frame["CL_UNIT"].dropna().unique())
    notes = [
        f"BEA Regional table {table} -- {BEA_ACPSA_TABLES[table]}. Units: "
        + ", ".join(units) + ".",
        "SATELLITE ACCOUNT. These are not counts, survey estimates or model "
        "predictions of an observable quantity: they are an accounting "
        "re-partition of value added under a published boundary decision about "
        "which industries, and which shares of them, constitute arts and "
        "cultural production. No margin of error exists because nothing was "
        "sampled. The uncertainty is in the boundary and is not published.",
        "The submitted credential is echoed by BEA at BEAAPI.Request and was "
        "removed before parsing; the payload hash below is over the stripped "
        "document, so another analyst using a different key reproduces it.",
        f"Vintage pinned to {text_year}. The Regional endpoint exposes no vintage "
        "parameter -- only a Year window whose default, 'LAST5', moves with each "
        "annual release -- so a past vintage of this statistic is not retrievable.",
    ]
    if code.upper() == "ALL":
        notes.append(
            "LINE CODES ARE NOT A FLAT LIST. This response mixes a grand total "
            "(line 1, the whole economy), a subject total (line 10), three "
            "subtotals (100/200/300) and the leaf industries as sibling rows with "
            "no depth column. Summing the DataValue column gives many times the "
            "true total. The LineRole column added here records which is which."
        )
    if not unparsed.empty:
        notes.append(
            "Non-numeric DataValue entries preserved in DataValueText and set to "
            f"NaN in DataValue: {sorted(set(unparsed.dropna()))}."
        )

    prov = DataProvenance.build(
        hash_basis="canonical-stable-json",
        pinned=False,
        source_name="U.S. Bureau of Economic Analysis",
        dataset=f"Regional / {table} ({BEA_ACPSA_TABLES[table]})",
        vintage=text_year,
        endpoint=BEA_HOST,
        variables={"TableName": table, "LineCode": code, "GeoFIPS": geo_fips},
        payload=canonical_stable_json(json.dumps(document).encode("utf-8")),
        row_count=len(frame),
        column_count=len(frame.columns),
        notes=tuple(notes),
    )
    return frame, prov


# ------------------------------------------------- Social Capital Atlas (Meta / OI)
#
# The corpus's first source protected by FORMAL DIFFERENTIAL PRIVACY with a
# PUBLISHED privacy budget, and the first whose published standard error is
# documented as containing both statistical and disclosure error at once.
#
# The release README states the mechanism in full: Laplace noise at epsilon = 8,
# with a smoothed sensitivity term, and minimum cell sizes of 100 low-SES and 100
# high-SES users. It then defines the standard-error columns as
#
#     "The standard error of economic connectedness, incorporating both sampling
#      error and error from the addition of noise to protect privacy."
#
# That sentence is why this source needs its own regime. Everywhere else in the
# corpus, published uncertainty is a statistical property of a sample. Here part
# of it is a POLICY PARAMETER -- epsilon is a choice, and a different choice would
# have produced a different standard error for the same underlying network -- and
# the two parts arrive added together in one column.
#
# They cannot be separated from the release. The sensitivity term depends on the
# degree distribution of low-SES users within each unit, which is not published
# (publishing it would leak the network structure the noise exists to protect),
# and no size variable in the files is the count the noise formula uses:
# `num_below_p50` is children with below-median parental income from the
# Opportunity Atlas, and `pop2018` is ACS population. Both are external proxies
# for a Facebook user count that is never released.
#
# Distribution note. The dataset page at data.humdata.org answers a plain request
# with HTTP 202 and a zero-length body -- the WAF-challenge signature catalogued in
# handbook section 2. The CKAN API and the resource download paths are not
# challenged, so the resource ids are pinned here rather than scraped.
#
# Licence. Unlike the Opportunity Atlas files used in D10, redistribution IS
# permitted: Meta Platforms grants use and redistribution "with or without
# modification" provided the licence travels with the copy, the contributors are
# not used for endorsement, and -- condition 4 -- the data are not combined with
# other sources in any way that could identify an individual. This client still
# fetches at runtime rather than vendoring the files, so that a vintage and a
# payload hash are recorded on every use; that is a provenance choice, not a
# licence constraint, and the distinction is recorded so nobody re-derives it.

SOCIAL_CAPITAL_HOST: Final[str] = "https://data.humdata.org/dataset"

#: HDX dataset id for the Social Capital Atlas.
SOCIAL_CAPITAL_DATASET: Final[str] = "85ee8e10-0c66-4635-b997-79b6fad44c71"

#: Resource ids, pinned. The dataset landing page is WAF-challenged; these are not.
SOCIAL_CAPITAL_RESOURCES: Final[dict[str, tuple[str, str]]] = {
    "county": ("ec896b64-c922-4737-b759-e4bd7f73b8cc", "social_capital_county.csv"),
    "zip": ("ab878625-279b-4bef-a2b3-c132168d536e", "social_capital_zip.csv"),
    "college": ("7bd697cf-c572-47a6-b15b-8450cc5c7ef8", "social_capital_college.csv"),
    "high_school": ("0de85271-031d-4849-bda8-c8582a67e11b", "social_capital_high_school.csv"),
}

#: The published universe of each geography BEFORE the minimum-cell-size rule,
#: from the release README. Held here so a notebook can measure what the rule
#: removed rather than only what survived -- a file cannot report its own absences.
SOCIAL_CAPITAL_UNIVERSE: Final[dict[str, int]] = {
    "county": 3096, "zip": 29062, "college": 2673, "high_school": 21483,
}

#: The one published release. There is no second vintage and no vintage parameter.
SOCIAL_CAPITAL_VINTAGE: Final[str] = "2022-07-31 release; network snapshot 2022-05-28"

#: The disclosure mechanism, as documented, carried into provenance.
SOCIAL_CAPITAL_PRIVACY: Final[str] = (
    "formal differential privacy: Laplace noise at epsilon = 8 with a smoothed "
    "sensitivity term, and minimum cell sizes of 100 low-SES and 100 high-SES "
    "users. The published standard-error columns are documented as "
    "'incorporating both sampling error and error from the addition of noise to "
    "protect privacy' -- the two are added together and cannot be separated from "
    "the release, because the sensitivity term depends on the within-unit degree "
    "distribution, which is not published"
)

#: What the universe actually is. Not a population, and not a sample of one.
SOCIAL_CAPITAL_UNIVERSE_NOTE: Final[str] = (
    "Facebook users aged 25-44, active in the previous 30 days, with at least "
    "100 US friends and a valid residential ZIP as of 2022-05-28. This is a "
    "platform universe, not a demographic one: coverage varies across places for "
    "reasons plausibly correlated with the social connectedness being measured, "
    "and no user count is published at any geography"
)


def fetch_social_capital_atlas(
    *,
    geography: str,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Fetch one Social Capital Atlas file, or raise.

    Parameters
    ----------
    geography:
        One of :data:`SOCIAL_CAPITAL_RESOURCES` -- ``"county"``, ``"zip"``,
        ``"college"`` or ``"high_school"``.

    Notes
    -----
    Two kinds of absence are distinguished and both are reported in provenance,
    because they mean different things and a file can only show one of them:

    * a unit **absent from the file**, removed by the minimum-cell-size rule
      before publication -- countable only against
      :data:`SOCIAL_CAPITAL_UNIVERSE`;
    * a unit **present with an empty estimate**, which is the same rule applied
      to one statistic rather than the whole row.

    Nothing is coerced. An empty estimate stays NaN so it can never be summed,
    averaged or ranked as if it were a measurement of zero connectedness.
    """
    if geography not in SOCIAL_CAPITAL_RESOURCES:
        raise ValueError(
            f"{geography!r} is not a Social Capital Atlas geography. "
            f"Choose one of {sorted(SOCIAL_CAPITAL_RESOURCES)}."
        )
    resource_id, filename = SOCIAL_CAPITAL_RESOURCES[geography]
    endpoint = f"{SOCIAL_CAPITAL_HOST}/{SOCIAL_CAPITAL_DATASET}/resource/{resource_id}/download/{filename}"

    http = session or requests
    try:
        resp = http.get(endpoint, timeout=180)
    except requests.RequestException as exc:
        raise UpstreamError(
            f"Social Capital Atlas request failed: {redact(exc)}"
        ) from exc
    reject_bot_challenge(
        resp, source="the Humanitarian Data Exchange", endpoint=endpoint
    )
    if resp.status_code != 200:
        raise UpstreamError(
            f"Social Capital Atlas returned HTTP {resp.status_code} for {filename}."
        )
    body = resp.content
    if not body:
        raise ResponseShapeError(
            f"{filename} came back empty. HDX answers a challenged request with a "
            "zero-length 2xx body, so an empty payload here is a firewall response "
            "rather than an empty dataset."
        )
    head = body[:200].lstrip()
    if head[:1] in b"<{":
        raise ResponseShapeError(
            f"{filename} returned markup rather than CSV; the first bytes were "
            f"{redact(head[:80])!r}."
        )

    frame = pd.read_csv(io.BytesIO(body), low_memory=False)
    if frame.empty:
        raise EmptyResultError(f"{filename} parsed to zero rows.")

    universe = SOCIAL_CAPITAL_UNIVERSE[geography]
    removed = universe - len(frame)
    estimate_columns = [c for c in frame.columns if c.startswith("ec_") and "_se_" not in c]
    blank = {c: int(frame[c].isna().sum()) for c in estimate_columns}

    notes = [
        f"Social Capital Atlas, {geography}. Vintage: {SOCIAL_CAPITAL_VINTAGE}. "
        "There is one release and no vintage parameter.",
        f"Universe: {SOCIAL_CAPITAL_UNIVERSE_NOTE}.",
        f"Disclosure protection: {SOCIAL_CAPITAL_PRIVACY}.",
        f"Minimum-cell-size removal BEFORE publication: {removed:,} of {universe:,} "
        f"{geography} units ({removed / universe:.1%}) are absent from the file "
        "entirely. A file cannot report its own absences; that count comes from "
        "the release README and is pinned in SOCIAL_CAPITAL_UNIVERSE.",
        "Empty estimates present in the file (the same rule applied per statistic, "
        "left as NaN and never zero): "
        + ", ".join(f"{k}={v:,}" for k, v in sorted(blank.items()) if v),
        "Licence: Meta Platforms permits use and redistribution with or without "
        "modification, provided the licence accompanies any copy and the data are "
        "not combined with other sources in a way that could identify an "
        "individual. Fetched at runtime here so a vintage and payload hash are "
        "recorded; that is a provenance choice, not a licence constraint.",
        "Economic connectedness is twice the share of above-median-SES friends "
        "among below-median-SES users, so 1.0 is parity and the measure is a "
        "RATIO, not a count or a rate.",
    ]

    prov = DataProvenance.build(
        source_name="Meta Platforms / Opportunity Insights (Social Capital Atlas)",
        dataset=f"Social Capital Atlas -- {geography}",
        vintage=SOCIAL_CAPITAL_VINTAGE,
        endpoint=endpoint,
        variables={"geography": geography, "file": filename},
        payload=body,
        row_count=len(frame),
        column_count=len(frame.columns),
        notes=tuple(n for n in notes if n),
    )
    return frame, prov


# ------------------------------------------------------- FBI Crime Data Explorer
#
# The thirteenth regime, and the only one here whose COVERAGE is a time series in
# its own right. NIBRS participation is voluntary. An agency reports because it
# chose to and was ready to, which makes the reporting population a variable that
# moves for administrative reasons and moves differently in different places.
#
# What the publisher does well, measured rather than assumed:
#
#   * Coverage IS published. `populations.participated_population` gives the
#     population served by reporting agencies, and a percentage sits under
#     `tooltips` -> "Percent of Population Coverage".
#   * Rates ARE normalised by it. Checked on Pennsylvania and Florida, where
#     coverage falls far enough to discriminate: the published rate matches
#     actual / participated_population to a mean absolute error of 0.002, against
#     12.49 for actual / total population. The publisher is dividing by the right
#     denominator.
#
# And neither of those is sufficient, which is the point of the regime.
#
#   * The covered subset is not a random sample of places, and the direction of
#     the resulting bias is not predictable from the coverage figure. Across nine
#     states the correlation between the change in coverage and the change in the
#     published rate is +0.236: Pennsylvania's rate rose 35.5% as coverage fell
#     52.9 points, New York's FELL 78.6% as coverage fell 29.5. A coverage number
#     tells you a problem exists. It does not tell you its sign, so it cannot be
#     used to correct anything.
#   * Coverage measures population under SOME reporting arrangement, not
#     population measured by THIS series. Florida reads 99.78% coverage across
#     2016-2020 while 54 of its 96 monthly offence counts sit below 200 and many
#     are exactly zero. An analyst who checks the coverage field -- the correct
#     instinct -- is waved through.
#
# Transport: the FBI backend behind api.usa.gov flaps. Endpoints return HTTP 503
# intermittently and recover within seconds, so a single failed call says nothing
# about whether data exists. This client retries with backoff and, when it gives
# up, raises an error that names the outage rather than returning an empty frame.

FBI_CDE_HOST: Final[str] = "https://api.usa.gov/crime/fbi/cde"

#: CDE takes month-year, not year. A four-digit year is rejected with HTTP 400.
FBI_CDE_PERIOD_PATTERN: Final[re.Pattern[str]] = re.compile(r"^(0[1-9]|1[0-2])-\d{4}$")

#: Where the coverage series lives in the payload. Recorded as a constant because
#: nobody would look for a data series under this key.
FBI_CDE_COVERAGE_PATH: Final[tuple[str, ...]] = ("tooltips", "Percent of Population Coverage")

FBI_CDE_REGIME: Final[str] = (
    "voluntary NIBRS reporting: the population covered by reporting agencies is "
    "a time series that moves for administrative reasons, varies by state, and "
    "is not a random sample of places. Coverage is published and rates are "
    "normalised by it, and neither is sufficient -- the sign of the residual "
    "bias is not recoverable from the coverage figure"
)


class CDEUpstreamUnavailable(UpstreamError):
    """The FBI backend returned 503 for every attempt.

    A distinct type because the correct response is to retry later, not to record
    an absence. Treating this as "no crime data for that state" is the failure
    mode the retry loop exists to prevent.
    """


def _cde_get(
    path: str,
    params: Mapping[str, str],
    *,
    session: requests.Session | None = None,
    attempts: int = 5,
) -> object:
    """GET one CDE path, retrying only the intermittent 503."""
    endpoint = f"{FBI_CDE_HOST}{path}"
    query = {**params, "API_KEY": load_key("DATA_GOV_API_KEY")}
    http = session or requests
    last_status: int | None = None
    for attempt in range(attempts):
        try:
            resp = http.get(endpoint, params=query, timeout=90)
        except requests.RequestException as exc:
            raise UpstreamError(f"CDE request failed: {redact(exc)}") from exc
        reject_bot_challenge(resp, source="the FBI Crime Data Explorer", endpoint=endpoint)
        if resp.status_code == 200:
            return _assert_json_payload(resp, endpoint)
        last_status = resp.status_code
        if resp.status_code != 503:
            # 404 here means the path shape is wrong, which retrying cannot fix.
            raise UpstreamError(
                f"CDE returned HTTP {resp.status_code} for {path}. A 404 from this "
                "API means the path shape is wrong rather than that the data is "
                "missing; check the endpoint before concluding anything about "
                "coverage."
            )
        time.sleep(1.2 * (attempt + 1))
    raise CDEUpstreamUnavailable(
        f"CDE returned HTTP {last_status} on all {attempts} attempts for {path}. "
        "The FBI backend behind api.usa.gov flaps and recovers within seconds, so "
        "this says nothing about whether the data exists. Retry later; do NOT "
        "record it as an absence."
    )


def fetch_fbi_cde_agencies(
    *,
    state: str,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Every law-enforcement agency in one state, with its NIBRS status.

    This is the coverage variable at its source: ``is_nibrs`` says whether an
    agency reports, and ``nibrs_start_date`` says when it began. Nothing else in
    the corpus publishes the date a unit entered the measurement.
    """
    code = str(state).strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", code):
        raise ValueError(f"state must be a two-letter abbreviation, not {state!r}.")
    payload = _cde_get(f"/agency/byStateAbbr/{code}", {}, session=session)
    if not isinstance(payload, dict) or not payload:
        raise ResponseShapeError(f"CDE returned no agency map for {code}.")

    rows: list[dict[str, object]] = []
    for county, entries in payload.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict):
                rows.append({"county_key": county, **entry})
    if not rows:
        raise EmptyResultError(f"CDE returned an agency map for {code} with no agencies.")

    frame = pd.DataFrame(rows)
    for column in ("ori", "agency_name", "is_nibrs"):
        if column not in frame.columns:
            raise SchemaError(f"CDE agency response is missing {column!r}.")
    frame["is_nibrs"] = frame["is_nibrs"].astype("boolean")
    if "nibrs_start_date" in frame.columns:
        frame["nibrs_start_year"] = (
            frame["nibrs_start_date"].astype("string").str.slice(0, 4)
        )

    reporting = int(frame["is_nibrs"].fillna(False).sum())
    prov = DataProvenance.build(
        hash_basis="canonical-json",
        pinned=False,
        source_name="FBI Criminal Justice Information Services",
        dataset=f"Crime Data Explorer -- agencies, {code}",
        vintage="live; NIBRS status as published at fetch time",
        endpoint=f"{FBI_CDE_HOST}/agency/byStateAbbr/{code}",
        variables={"state": code},
        payload=json.dumps(payload, sort_keys=True).encode("utf-8"),
        row_count=len(frame),
        column_count=len(frame.columns),
        notes=(
            f"Regime: {FBI_CDE_REGIME}.",
            f"{reporting:,} of {len(frame):,} agencies in {code} report NIBRS "
            f"({reporting / len(frame):.1%}). An agency absent from NIBRS is not "
            "an agency with no crime; it is an agency that has not joined.",
            "nibrs_start_date is the date the agency entered the measurement. A "
            "series that spans it is not measuring the same set of places before "
            "and after.",
        ),
    )
    return frame, prov


def fetch_fbi_cde_summarized(
    *,
    state: str,
    offense: str,
    from_month: str,
    to_month: str,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Monthly offences, rates, population and COVERAGE for one state.

    Returns one row per month with the published rate beside the two candidate
    denominators, so the reader can see which one the publisher used rather than
    assume it.

    ``from_month`` and ``to_month`` are ``MM-YYYY``. A four-digit year is
    rejected by the API with HTTP 400 and is rejected here first.
    """
    code = str(state).strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", code):
        raise ValueError(f"state must be a two-letter abbreviation, not {state!r}.")
    for label, period in (("from_month", from_month), ("to_month", to_month)):
        if not FBI_CDE_PERIOD_PATTERN.match(str(period)):
            raise ValueError(
                f"{label} must be MM-YYYY, not {period!r}. CDE rejects a bare year "
                "with HTTP 400."
            )
    payload = _cde_get(
        f"/summarized/state/{code}/{offense}",
        {"from": from_month, "to": to_month},
        session=session,
    )
    if not isinstance(payload, dict) or "offenses" not in payload:
        raise ResponseShapeError(f"CDE summarized response for {code} has no offenses block.")

    offenses = payload["offenses"]
    rates = offenses.get("rates", {})
    actuals = offenses.get("actuals", {})
    populations = payload.get("populations", {})
    coverage = payload.get("tooltips", {}).get(FBI_CDE_COVERAGE_PATH[1], {})

    # The state's own series is keyed by full state name, which the response
    # supplies rather than the caller. Take it from the actuals, which are served
    # only for the requested state -- national actuals are NOT served here.
    state_keys = [k for k in actuals if k.endswith(" Offenses")]
    if not state_keys:
        raise SchemaError(
            "CDE returned no state offence actuals. National actuals are not "
            "served by this endpoint; only national rates are."
        )
    state_label = state_keys[0].removesuffix(" Offenses")

    months = sorted(
        actuals[f"{state_label} Offenses"],
        key=lambda m: (m[-4:], m[:2]),
    )
    frame = pd.DataFrame({
        "month": months,
        "offenses": [actuals[f"{state_label} Offenses"].get(m) for m in months],
        "published_rate": [rates.get(f"{state_label} Offenses", {}).get(m) for m in months],
        "population": [populations.get("population", {}).get(state_label, {}).get(m) for m in months],
        "participated_population": [
            populations.get("participated_population", {}).get(state_label, {}).get(m)
            for m in months
        ],
        "coverage_pct": [coverage.get(state_label, {}).get(m) for m in months],
    })
    frame["state"] = state_label
    for column in ("offenses", "published_rate", "population",
                   "participated_population", "coverage_pct"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    worst = frame["coverage_pct"].min()
    median_coverage = frame["coverage_pct"].median()
    prov = DataProvenance.build(
        hash_basis="canonical-json",
        pinned=False,
        source_name="FBI Criminal Justice Information Services",
        dataset=f"Crime Data Explorer -- {offense}, {state_label}",
        vintage=f"{from_month} to {to_month}; "
                f"max data date {payload.get('cde_properties', {}).get('max_data_date', {})}",
        endpoint=f"{FBI_CDE_HOST}/summarized/state/{code}/{offense}",
        variables={"state": code, "offense": offense,
                   "from": from_month, "to": to_month},
        payload=json.dumps(payload, sort_keys=True).encode("utf-8"),
        row_count=len(frame),
        column_count=len(frame.columns),
        notes=(
            f"Regime: {FBI_CDE_REGIME}.",
            f"Population coverage over this window: median {median_coverage:.1f}%, "
            f"minimum {worst:.1f}%. The published rate is normalised by "
            "participated_population, not by total population -- verified, not "
            "assumed, and the notebook re-verifies it.",
            "COVERAGE IS NOT A QUALITY GUARANTEE. It counts population under some "
            "reporting arrangement, not population measured by this series, and "
            "the covered subset is not a random sample of places. A high coverage "
            "figure has been observed alongside months of zero reported offences.",
            "National actuals are not served by this endpoint; national rates are. "
            "A national count cannot be recomputed from what is published here.",
        ),
    )
    return frame, prov


# ------------------------------------------------------------- EPA TRI (Envirofacts)
#
# The fourteenth regime, and the only source here that publishes the EPISTEMIC
# PROVENANCE OF EACH INDIVIDUAL NUMBER. Every release record carries a
# basis-of-estimate code saying how that quantity was arrived at -- continuous
# monitoring, periodic monitoring, mass balance, a published emission factor, a
# site-specific factor, or "best engineering judgment". Nothing else in this
# corpus tells you, record by record, whether a figure was measured or guessed.
#
# EPA's TRI Data Dictionary, quoted verbatim from the Envirofacts column
# metadata for RELEASE_BASIS_EST_CODE:
#
#   M1  "Estimate is based on continuous monitoring data or measurements"
#   M2  "Estimate is based on periodic or random monitoring data or measurements"
#   M   monitoring; "replaced by M1 and M2 in reporting year 2007"
#   C   "Estimate is based on mass balance calculations"
#   E1  "Estimate is based on published emission factors"
#   E2  "Estimate is based on site specific emission factors"
#   E   published emission factors; "replaced by E1 and E2 in reporting year 2007"
#   O   "Estimate is based on other approaches such as engineering calculations
#        ... or best engineering judgment"
#   X   "Invalid entry."
#   N   "Not Applicable."
#
# Two consequences the client enforces.
#
# THE CODE SCHEME CHANGED IN REPORTING YEAR 2007. A series spanning it mixes two
# vocabularies in one column, and an unfiltered Envirofacts query returns the
# OLDEST records first -- so a naive sample gets the pre-2007 scheme and maps it
# against the modern one. `reporting_year` is therefore required, not optional.
#
# A RANGE-CODED RELEASE HAS NO QUANTITY IN THE API. Releases under 1,000 pounds
# may be reported as a band. EPA's dictionary for RELEASE_RANGE_CODE says: "When
# a facility uses a range code, the amount reported to TRI is the midpoint of the
# range... '1' represents range 'A' [1-10 lb], '3' represents range 'B' [11-499
# lb], and '4' represents range 'C' [500-999 lb]. The historical value '2' =
# 1-499 pounds."
#
# The served data does not agree with that. Measured on 213 range-coded records
# in an unfiltered sample and 59 in a Virginia 2022 slice, `total_release` is
# null in every single case, while `release_na` is '0' -- the flag that marks the
# release as APPLICABLE. So these are real releases, affirmatively not-absent,
# carrying no number. Summing `total_release` drops every one of them, and what
# it drops is specifically the small end: a directional loss, not noise.
#
# This client therefore computes the documented midpoint itself, into a separate
# column, and never silently substitutes it for a measured quantity.

TRI_HOST: Final[str] = "https://data.epa.gov/efservice"

#: Envirofacts caps a single response at 10,000 rows. Verified: rows/0:9999
#: returned exactly 10,000 and rows/10000:10099 returned a further 100.
TRI_PAGE_LIMIT: Final[int] = 10_000

#: What this client actually asks for per request, which is deliberately far
#: below the API's own cap. Measured against VA RY2022: 100 rows in 5.8s, 1,000
#: in 26.2s, 2,000 in 11.4s, 5,000 in 21.0s -- and 10,000 did not return inside
#: 175 seconds. The service degrades sharply as it approaches its documented
#: ceiling, so a client that pages at the ceiling is a client that times out.
TRI_REQUEST_ROWS: Final[int] = 2_000

#: Verbatim from the EPA TRI Data Dictionary via Envirofacts column metadata.
TRI_BASIS_CODES: Final[dict[str, str]] = {
    "M1": "continuous monitoring data or measurements (added RY2007)",
    "M2": "periodic or random monitoring data or measurements (added RY2007)",
    "M": "monitoring data or measurements (pre-RY2007; replaced by M1/M2)",
    "C": "mass balance calculations",
    "E1": "published emission factors (added RY2007)",
    "E2": "site specific emission factors (added RY2007)",
    "E": "published emission factors (pre-RY2007; replaced by E1/E2)",
    "O": "other approaches such as engineering calculations or best engineering judgment",
    "X": "invalid entry",
    "N": "not applicable",
}

#: Which codes rest on measurement rather than calculation or judgement. The
#: split is the point of the source, so it is named here rather than inferred at
#: each call site.
TRI_MEASURED_CODES: Final[frozenset[str]] = frozenset({"M1", "M2", "M"})

#: The reporting-year boundary at which M/E were split into M1/M2 and E1/E2.
TRI_CODE_SCHEME_CHANGE_YEAR: Final[int] = 2007

#: Range code -> (low, high) pounds, from the EPA dictionary. The stored amount
#: is documented as the midpoint; the API does not populate it.
TRI_RANGE_BANDS: Final[dict[str, tuple[int, int]]] = {
    "1": (1, 10),        # Form R code A
    "2": (1, 499),       # historical
    "3": (11, 499),      # Form R code B
    "4": (500, 999),     # Form R code C
}


def _tri_get(path: str, *, session: requests.Session | None = None) -> list[dict]:
    """GET one Envirofacts path and return its rows."""
    endpoint = f"{TRI_HOST}/{path}/JSON"
    http = session or requests
    try:
        resp = http.get(endpoint, timeout=180)
    except requests.RequestException as exc:
        raise UpstreamError(f"Envirofacts request failed: {redact(exc)}") from exc
    reject_bot_challenge(resp, source="EPA Envirofacts", endpoint=endpoint)
    if resp.status_code != 200:
        raise UpstreamError(f"Envirofacts returned HTTP {resp.status_code} for {path}.")
    payload = _assert_json_payload(resp, endpoint)
    if not isinstance(payload, list):
        raise ResponseShapeError(f"Envirofacts returned {type(payload).__name__}, not a row list.")
    return payload


def _tri_count(query: str, *, session: requests.Session | None = None) -> int:
    """Ask Envirofacts how many rows ``query`` matches, before fetching any.

    This exists so the client can never mistake a full page for a full answer.
    Envirofacts caps a response at :data:`TRI_PAGE_LIMIT` rows and gives no
    truncation signal, so a query matching 12,069 rows returns 10,000 that look
    exactly like a complete result.
    """
    rows = _tri_get(f"{query}/count", session=session)
    if len(rows) != 1 or "TOTALQUERYRESULTS" not in rows[0]:
        raise ResponseShapeError(
            "Envirofacts count endpoint did not return a single TOTALQUERYRESULTS "
            f"row; got {rows!r:.200}."
        )
    try:
        return int(rows[0]["TOTALQUERYRESULTS"])
    except (TypeError, ValueError) as exc:
        raise ResponseShapeError(
            f"Envirofacts TOTALQUERYRESULTS was not an integer: {rows[0]!r}."
        ) from exc


def fetch_tri_releases(
    *,
    state: str,
    reporting_year: int,
    applicable_only: bool = False,
    row_budget: int = 200_000,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Fetch every TRI release record for one state and reporting year, or raise.

    ``reporting_year`` is required. Envirofacts returns the oldest records first
    on an unfiltered query, and the basis-of-estimate vocabulary changed in
    :data:`TRI_CODE_SCHEME_CHANGE_YEAR`, so an unpinned sample silently mixes two
    code schemes and is dominated by the older one.

    The result is **complete or an exception**. Envirofacts caps a response at
    :data:`TRI_PAGE_LIMIT` rows and signals truncation in no way at all, so this
    client asks the ``count`` endpoint first, pages until it has that many rows,
    and refuses to return a frame whose length disagrees with the declared count.
    ``row_budget`` is a guard against pulling an unintended multi-year sweep: a
    query larger than the budget raises rather than truncating.

    A TRI form enumerates every environmental medium, and most of those rows are
    marked not-applicable: they carry no basis code and no quantity. In VA
    RY2022 that is 9,969 of 12,069 rows -- 83% of the payload, and the slow part
    of the download. ``applicable_only=True`` asks Envirofacts to filter them
    server-side. It narrows what is downloaded, **not** what is reported: the
    full universe is counted either way and both counts are recorded in
    provenance, so a reader can always see what was left on the server.

    The returned frame adds three columns the API does not serve:

    ``basis_meaning``
        The EPA dictionary text for the record's basis code.
    ``is_measured``
        Whether the quantity rests on monitoring rather than calculation or
        judgement.
    ``range_midpoint_lb``
        The documented midpoint for a range-coded release. **Kept separate from
        ``total_release`` on purpose.** It is a reconstruction of what the
        documentation says should be stored, not a reported quantity, and
        merging the two would hide exactly the distinction this source exists to
        make visible.
    """
    code = str(state).strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", code):
        raise ValueError(f"state must be a two-letter abbreviation, not {state!r}.")
    year = int(reporting_year)
    if not 1987 <= year <= 2100:
        raise ValueError(
            f"reporting_year {year} is outside TRI's published range. The programme "
            "begins with reporting year 1987."
        )
    if row_budget < 1:
        raise ValueError(f"row_budget must be positive, not {row_budget}.")

    universe_query = (
        f"tri_facility/state_abbr/{code}"
        f"/tri_reporting_form/reporting_year/{year}"
        f"/tri_release_qty"
    )
    universe_rows = _tri_count(universe_query, session=session)
    query = f"{universe_query}/release_na/0" if applicable_only else universe_query
    declared = (
        _tri_count(query, session=session) if applicable_only else universe_rows
    )
    if universe_rows == 0:
        raise EmptyResultError(
            f"Envirofacts reports no TRI release records for {code}, reporting year "
            f"{year}. TRI covers only facilities above its reporting thresholds, so "
            "an empty result means no facility in that state crossed a threshold and "
            "filed -- not that no releases occurred."
        )
    if declared == 0:
        raise EmptyResultError(
            f"{code} RY{year} has {universe_rows:,} TRI medium-rows but none marked "
            "applicable (release_na='0'). Every row is a medium the filer reported "
            "as not-applicable, so there is no release quantity to analyse."
        )
    if declared > row_budget:
        raise ValueError(
            f"{code} RY{year} matches {declared:,} rows, above the {row_budget:,}-row "
            "budget. Narrow the query or raise row_budget deliberately; this client "
            "will not return a truncated slice."
        )

    rows: list[dict] = []
    while len(rows) < declared:
        lo = len(rows)
        hi = min(lo + TRI_REQUEST_ROWS, declared) - 1
        page = _tri_get(f"{query}/rows/{lo}:{hi}", session=session)
        if not page:
            raise UpstreamError(
                f"Envirofacts returned an empty page at rows {lo}:{hi} while "
                f"{declared:,} rows were declared. The result is incomplete; "
                "refusing to return a partial frame."
            )
        rows.extend(page)

    if len(rows) != declared:
        raise ResponseShapeError(
            f"Assembled {len(rows):,} TRI rows but Envirofacts declared {declared:,}. "
            "Either the upstream result changed mid-query or paging is misaligned; "
            "either way the frame is not a trustworthy census of the query."
        )
    frame = pd.DataFrame(rows)
    for column in ("release_basis_est_code", "release_range_code", "total_release", "release_na"):
        if column not in frame.columns:
            raise SchemaError(f"TRI response is missing {column!r}.")

    frame["total_release"] = pd.to_numeric(frame["total_release"], errors="coerce")
    frame["release_basis_est_code"] = frame["release_basis_est_code"].astype("string")
    frame["release_range_code"] = frame["release_range_code"].astype("string")

    unknown = sorted(
        set(frame["release_basis_est_code"].dropna().unique()) - set(TRI_BASIS_CODES)
    )
    if unknown:
        raise SchemaError(
            f"TRI returned unrecognised basis-of-estimate code(s) {unknown}. The "
            f"documented values are {sorted(TRI_BASIS_CODES)}. Refusing to guess "
            "what a new code means about how a number was produced."
        )
    frame["basis_meaning"] = frame["release_basis_est_code"].map(TRI_BASIS_CODES)
    frame["is_measured"] = (
        frame["release_basis_est_code"]
        .isin(TRI_MEASURED_CODES)
        .astype("boolean")
        .mask(frame["release_basis_est_code"].isna())
    )

    bands = frame["release_range_code"].map(TRI_RANGE_BANDS)
    frame["range_midpoint_lb"] = bands.map(
        lambda b: (b[0] + b[1]) / 2 if isinstance(b, tuple) else pd.NA
    )
    frame["range_midpoint_lb"] = pd.to_numeric(frame["range_midpoint_lb"], errors="coerce")

    ranged = frame["release_range_code"].notna()
    ranged_without_quantity = int((ranged & frame["total_release"].isna()).sum())
    coded = frame["release_basis_est_code"].notna()
    measured = int(frame["is_measured"].fillna(False).sum())

    withheld = universe_rows - len(frame)
    scope = (
        f"A TRI form enumerates every environmental medium. This query matched "
        f"{universe_rows:,} medium-rows for {code} RY{year}; "
        + (
            f"{len(frame):,} of them are marked applicable (release_na='0') and were "
            f"downloaded, while {withheld:,} not-applicable rows were filtered "
            "server-side. Those rows carry no basis code and no quantity, but they "
            "are not nothing: they record that the filer considered the medium."
            if applicable_only
            else f"all {len(frame):,} were downloaded, applicable and not-applicable alike."
        )
    )

    notes = [
        f"EPA Toxics Release Inventory via Envirofacts, {code}, reporting year {year}.",
        scope,
        "REGULATORY SELF-REPORT. Facilities report their own releases; EPA does not "
        "measure them. TRI covers only facilities above its reporting thresholds, so "
        "a facility absent from the data has not been shown to release nothing.",
        "Each record carries its own basis-of-estimate code -- the epistemic "
        "provenance of that individual number. In this slice "
        f"{measured:,} of {int(coded.sum()):,} coded records rest on monitoring "
        f"({', '.join(sorted(TRI_MEASURED_CODES))}); the remainder are mass balance, "
        "emission factors, or best engineering judgment.",
        f"The basis-code vocabulary changed in reporting year "
        f"{TRI_CODE_SCHEME_CHANGE_YEAR}: M became M1/M2 and E became E1/E2. A series "
        "spanning that year mixes two schemes in one column, and an unfiltered "
        "Envirofacts query returns the oldest records first.",
        f"{ranged_without_quantity:,} of {int(ranged.sum()):,} range-coded records "
        "carry no numeric total_release. EPA's dictionary states the stored amount "
        "is the midpoint of the range; the API does not populate it, while release_na "
        "marks these releases APPLICABLE. Summing total_release drops them, and what "
        "it drops is the small end -- a directional loss, not noise. The documented "
        "midpoint is supplied separately as range_midpoint_lb and is NOT merged into "
        "total_release.",
    ]

    prov = DataProvenance.build(
        pinned=False,
        source_name="U.S. Environmental Protection Agency",
        dataset=f"Toxics Release Inventory -- releases, {code} RY{year}",
        vintage=f"reporting year {year}",
        endpoint=f"{TRI_HOST}/{query}",
        variables={
            "state": code,
            "reporting_year": str(year),
            "applicable_only": str(applicable_only),
            "universe_rows": str(universe_rows),
        },
        payload=json.dumps(rows, sort_keys=True, default=str).encode("utf-8"),
        row_count=len(frame),
        column_count=len(frame.columns),
        notes=tuple(notes),
    )
    return frame, prov


# ---------------------------------------------------------------------------
# Harvard Dataverse, and the MIT Election Data and Science Lab
# ---------------------------------------------------------------------------
#
# A bulk file behind a DOI, which is a better position than most bulk sources in
# this corpus: Dataverse serves a machine-readable manifest carrying a dataset
# version, a release time and a per-file MD5 that the *publisher* computed. So a
# client can detect a silent file swap rather than merely detect that its own
# cached copy changed, which is all a self-computed hash can do (contrast the
# Zillow pin in D27, handbook 5.3).
#
# Two properties of the election file shape the client:
#
#   1. File ids change between dataset versions; filenames do not. Addressing a
#      file by id pins a vintage and then 404s when it is superseded. This client
#      resolves by name and records the version it actually got.
#
#   2. `candidate` is not always a person. The column also carries ballot
#      dispositions -- OVERVOTES, UNDERVOTES, VOID, SCATTERING -- and the
#      published `totalvotes` counts them in most states. Dropping them, which is
#      the obvious cleaning step, *breaks* the accounting identity rather than
#      restoring it. The client flags them and says so in provenance; it does not
#      remove them, because removing them is the mistake.

DATAVERSE_HOST: Final[str] = "https://dataverse.harvard.edu"

#: Dataverse returns HTTP 403 to the default ``python-requests`` user agent and
#: 200 to an identified one. Measured, not guessed: the same URL that failed from
#: this client answered immediately once a UA was sent. An unidentified client is
#: not entitled to a public archive's bandwidth, and saying who is asking is the
#: minimum courtesy -- so this is the right behaviour, not a workaround.
DATAVERSE_HEADERS: Final[dict[str, str]] = {
    "User-Agent": "telosyn-notebooks/1.0 (research corpus; +https://github.com/KhipuResearch/telosyn-notebooks-for-policy-analysis)"
}

#: The MIT Election Data and Science Lab presidential returns, by state and year.
MIT_PRESIDENT_DOI: Final[str] = "doi:10.7910/DVN/42MVDX"
MIT_PRESIDENT_FILE: Final[str] = "1976-2024-president.csv"

#: Values of ``candidate`` that name a ballot disposition rather than a person.
#: Five of these six occur in the 2026-09-04 release, across 48 rows carrying
#: 473,830 votes; ``BLANK`` does not appear in that vintage and is declared
#: anyway, because the set is a statement about the column's vocabulary rather
#: than an inventory of one download. Published here so a notebook can flag them
#: without re-deriving the list, and so a change is visible as a diff rather than
#: as a silent shift.
ELECTION_BALLOT_DISPOSITIONS: Final[frozenset[str]] = frozenset({
    "OVERVOTES",
    "UNDERVOTES",
    "VOID",
    "SCATTERING",
    "BLANK",
    "NONE OF THESE CANDIDATES",
})

#: ``WRITE-IN`` is deliberately **not** in the set above. It is an aggregate of
#: real votes for real people and is counted as such by the publisher; the other
#: labels are ballots that produced no candidate vote. Conflating them is the
#: error this separation exists to prevent.
ELECTION_WRITE_IN_LABEL: Final[str] = "WRITE-IN"


class ChecksumError(DataAccessError):
    """Downloaded bytes do not match the checksum the publisher published."""


def _dataverse_get(path: str, *, session: requests.Session | None = None) -> Any:
    endpoint = f"{DATAVERSE_HOST}{path}"
    http = session or requests
    try:
        resp = http.get(endpoint, timeout=180, headers=DATAVERSE_HEADERS)
    except requests.RequestException as exc:
        raise UpstreamError(f"Dataverse request failed: {redact(exc)}") from exc
    reject_bot_challenge(resp, source="Harvard Dataverse", endpoint=endpoint)
    if resp.status_code == 403:
        raise UpstreamError(
            f"Dataverse returned HTTP 403 for {path}. This host refuses the default "
            "python-requests user agent; if this fires, DATAVERSE_HEADERS is not "
            "reaching the request."
        )
    if resp.status_code != 200:
        raise UpstreamError(f"Dataverse returned HTTP {resp.status_code} for {path}.")
    return resp


def fetch_dataverse_file(
    *,
    doi: str,
    filename: str,
    expected_md5: str | None = None,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Fetch one file from a Harvard Dataverse dataset, verified, or raise.

    Parameters
    ----------
    doi
        Dataset DOI, e.g. ``doi:10.7910/DVN/42MVDX``.
    filename
        Name of the file within the dataset. Resolved by **name**, because file
        ids change when a dataset is revised and an id-addressed client pins
        itself to a vintage that will eventually stop existing.
    expected_md5
        Optional. When given, the download must match it, which pins an exact
        vintage and turns any upstream revision into a loud failure. When
        omitted, the bytes are still checked against the MD5 **the publisher
        declares in its own manifest**, so a corrupted or swapped file is caught
        either way -- what is not caught is a deliberate, consistent revision.

    Returns
    -------
    The parsed frame and its provenance, whose ``vintage`` carries the dataset
    version and release time rather than a year, because that is what identifies
    a Dataverse release.
    """
    if not doi.startswith("doi:"):
        raise ValueError(f"doi must begin with 'doi:', got {doi!r}.")

    payload = _dataverse_get(
        f"/api/datasets/:persistentId/?persistentId={doi}", session=session
    )
    try:
        version = payload.json()["data"]["latestVersion"]
    except (ValueError, KeyError) as exc:
        raise ResponseShapeError(
            f"Dataverse metadata for {doi} has no latestVersion block."
        ) from exc

    matches = [f for f in version.get("files", []) if f["dataFile"]["filename"] == filename]
    if not matches:
        available = sorted(f["dataFile"]["filename"] for f in version.get("files", []))
        raise EmptyResultError(
            f"{doi} has no file named {filename!r}. Available: {available}. "
            "A renamed file is a revision, not a transport error."
        )
    if len(matches) > 1:
        raise ResponseShapeError(
            f"{doi} lists {len(matches)} files named {filename!r}; the name does "
            "not identify a file and this client cannot choose."
        )
    entry = matches[0]
    data_file = entry["dataFile"]
    if entry.get("restricted"):
        raise UpstreamError(
            f"{filename} in {doi} is restricted and needs credentials this corpus "
            "does not hold. That is a property of the dataset, not a failure here."
        )

    declared_md5 = (data_file.get("checksum") or {}).get("value") or data_file.get("md5")
    if not declared_md5:
        raise ResponseShapeError(
            f"Dataverse declares no checksum for {filename}; there is nothing to "
            "verify the download against."
        )

    resp = _dataverse_get(f"/api/access/datafile/{data_file['id']}", session=session)
    raw = resp.content
    if not raw:
        raise EmptyResultError(f"Dataverse returned an empty body for {filename}.")

    actual_md5 = hashlib.md5(raw, usedforsecurity=False).hexdigest()
    if actual_md5 != declared_md5:
        raise ChecksumError(
            f"{filename} does not match the MD5 Dataverse publishes for it "
            f"(declared {declared_md5}, got {actual_md5}). The file was corrupted "
            "in transit or replaced without the manifest being updated."
        )
    if expected_md5 and actual_md5 != expected_md5:
        raise ChecksumError(
            f"{filename} is MD5 {actual_md5}, not the pinned {expected_md5}. "
            f"The dataset is at version {version.get('versionNumber')}."
            f"{version.get('versionMinorNumber')}, released "
            f"{version.get('releaseTime')}. Upstream has revised the file; read "
            "the changes and update the pin deliberately rather than removing it."
        )

    try:
        frame = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise ResponseShapeError(f"{filename} did not parse as CSV: {redact(exc)}") from exc
    if frame.empty:
        raise EmptyResultError(f"{filename} parsed to zero rows.")

    release = version.get("releaseTime", "unknown")
    label = f"v{version.get('versionNumber')}.{version.get('versionMinorNumber')}"
    prov = DataProvenance.build(
        pinned=expected_md5 is not None,
        source_name="Harvard Dataverse",
        dataset=f"{doi} :: {filename}",
        vintage=f"dataset {label}, released {release}",
        endpoint=f"{DATAVERSE_HOST}/api/access/datafile/{data_file['id']}",
        variables={"doi": doi, "filename": filename, "md5": actual_md5},
        payload=raw,
        row_count=len(frame),
        column_count=len(frame.columns),
        notes=(
            f"Harvard Dataverse {doi}, file {filename}, dataset {label} released "
            f"{release}.",
            f"Bytes verified against the MD5 the publisher declares ({actual_md5}). "
            + (
                "The caller also pinned that MD5, so any upstream revision raises."
                if expected_md5
                else "No caller pin was supplied, so a deliberate upstream revision "
                "would be accepted silently; pass expected_md5 to prevent that."
            ),
            "Resolved by filename rather than file id: ids change when a dataset is "
            "revised, so an id-addressed client pins a vintage and then 404s.",
        ),
    )
    return frame, prov


def fetch_mit_president(
    *,
    expected_md5: str | None = None,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Fetch MIT Election Lab presidential returns by state and year, or raise.

    Adds one derived column the file does not carry:

    ``is_ballot_disposition``
        Whether ``candidate`` names a ballot disposition (:data:`ELECTION_BALLOT_DISPOSITIONS`)
        rather than a person. **The rows are flagged, not removed.** The published
        ``totalvotes`` counts them in most states, so dropping them breaks the
        accounting identity instead of restoring it -- which is the finding D19
        is built on, not an incidental caveat.
    """
    frame, prov = fetch_dataverse_file(
        doi=MIT_PRESIDENT_DOI,
        filename=MIT_PRESIDENT_FILE,
        expected_md5=expected_md5,
        session=session,
    )
    for column in ("year", "state", "candidate", "candidatevotes", "totalvotes", "version"):
        if column not in frame.columns:
            raise SchemaError(f"MIT presidential returns are missing {column!r}.")

    labels = frame["candidate"].astype("string").str.strip().str.upper()
    frame["is_ballot_disposition"] = labels.isin(ELECTION_BALLOT_DISPOSITIONS).fillna(False)

    flagged = int(frame["is_ballot_disposition"].sum())
    flagged_votes = int(frame.loc[frame["is_ballot_disposition"], "candidatevotes"].sum())
    vintages = sorted(frame["version"].astype("string").dropna().unique())
    notes = list(prov.notes) + [
        "ADMINISTRATIVE ENUMERATION. These are counted ballots, not a sample, so "
        "no margin of error exists anywhere in the file. The residual uncertainty "
        "is definitional, and it is not small.",
        f"`candidate` is not always a person: {flagged:,} of {len(frame):,} rows name a "
        f"ballot disposition ({', '.join(sorted(ELECTION_BALLOT_DISPOSITIONS))}), "
        f"carrying {flagged_votes:,} votes. They are FLAGGED and NOT removed: "
        "`totalvotes` counts them in most states, so dropping them breaks the "
        "accounting identity rather than restoring it.",
        f"`WRITE-IN` is deliberately not treated as a disposition. It aggregates real "
        "votes for real people; the others are ballots that produced no candidate vote.",
        f"The `version` column carries {len(vintages)} distinct values in one file "
        f"({', '.join(vintages)}), in two different date formats. A single download "
        "is not a single vintage.",
        "`party_simplified` collapses every party outside Democrat, Republican and "
        "Libertarian into OTHER. The collapse is lossy and the loss is the entire "
        "identity of the third-party field.",
    ]
    return frame, DataProvenance(
        source_name="MIT Election Data and Science Lab",
        dataset=prov.dataset,
        vintage=prov.vintage,
        endpoint=prov.endpoint,
        variables=prov.variables,
        retrieved_utc=prov.retrieved_utc,
        row_count=len(frame),
        column_count=len(frame.columns),
        content_sha256=prov.content_sha256,
        mode=prov.mode,
        notes=tuple(notes),
    )


# ---------------------------------------------------------------------------
# USDA ERS Food Environment Atlas
# ---------------------------------------------------------------------------
#
# A single .xls with thirteen sheets, 3,143 county rows and a FIPS column. It
# looks like a county dataset throughout and it is not one throughout: measured
# on the 2026-09-15 copy, 49 of 280 numeric variables (17.5%) hold ONE value per
# state, replicated into every county row in that state. Two whole sheets --
# INSECURITY and TAXES -- are state data wearing a county FIPS, and ASSISTANCE
# is 33 of 53.
#
# Nothing in the file marks the difference. So this client computes it, and
# returns the classification beside the data rather than leaving each caller to
# rediscover it or, more likely, not.

FEA_URL: Final[str] = (
    "https://www.ers.usda.gov/sites/default/files/_laserfiche/DataFiles/80526/"
    "FoodEnvironmentAtlas.xls"
)

#: Sheets carrying county rows. Read_Me, the variable list and the two
#: Supplemental sheets are documentation and are not served here.
FEA_DATA_SHEETS: Final[tuple[str, ...]] = (
    "ACCESS", "STORES", "RESTAURANTS", "ASSISTANCE", "INSECURITY",
    "TAXES", "LOCAL", "HEALTH", "SOCIOECONOMIC",
)


class GrainError(DataAccessError):
    """A column's stated geography is not the geography it varies at."""


def _fea_bytes(*, session: requests.Session | None = None) -> bytes:
    http = session or requests
    try:
        resp = http.get(FEA_URL, timeout=300, headers={"User-Agent": "telosyn-notebooks/1.0"})
    except requests.RequestException as exc:
        raise UpstreamError(f"Food Environment Atlas request failed: {redact(exc)}") from exc
    reject_bot_challenge(resp, source="USDA ERS", endpoint=FEA_URL)
    if resp.status_code != 200:
        raise UpstreamError(
            f"USDA ERS returned HTTP {resp.status_code} for the Food Environment "
            "Atlas. The file has moved before; check the data-access page rather "
            "than assuming the dataset is gone."
        )
    if not resp.content:
        raise EmptyResultError("USDA ERS returned an empty body for the Atlas.")
    return resp.content


def classify_geographic_grain(
    frame: pd.DataFrame, *, group: str = "State", exclude: Sequence[str] = ("FIPS",)
) -> pd.DataFrame:
    """Say, per numeric column, whether it actually varies within ``group``.

    Returns one row per column with the number of groups in which the column
    takes a single value. A column constant within **every** group is not a
    measurement at the row's geography, whatever the row's identifier says.

    This is four lines of pandas and it is the whole defence against an entire
    class of false precision, so it lives here rather than in a notebook.
    """
    if group not in frame.columns:
        raise ValueError(f"{group!r} is not a column of this frame.")
    rows = []
    for column in frame.columns:
        if column == group or column in exclude:
            continue
        if not pd.api.types.is_numeric_dtype(frame[column]):
            continue
        present = frame[[group, column]].dropna()
        if present[column].nunique() < 2:
            continue                      # constant everywhere; nothing to classify
        per_group = present.groupby(group)[column].nunique()
        rows.append({
            "column": column,
            "rows": len(present),
            "groups": len(per_group),
            "groups_with_one_value": int((per_group == 1).sum()),
            "median_distinct_per_group": float(per_group.median()),
            "distinct_overall": int(present[column].nunique()),
        })
    grain = pd.DataFrame(rows)
    if grain.empty:
        return grain
    grain["is_group_replicated"] = grain["groups_with_one_value"] == grain["groups"]
    return grain


def fetch_food_environment_atlas(
    *,
    sheet: str,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Fetch one sheet of the USDA Food Environment Atlas, or raise.

    The returned provenance names every column in the sheet that is a **state
    value replicated into county rows**, computed from the data rather than from
    documentation, because the file documents it nowhere.
    """
    if sheet not in FEA_DATA_SHEETS:
        raise ValueError(
            f"{sheet!r} is not a county data sheet. Available: {list(FEA_DATA_SHEETS)}. "
            "Read_Me, the variable list and the Supplemental sheets are documentation."
        )
    raw = _fea_bytes(session=session)
    try:
        frame = pd.read_excel(io.BytesIO(raw), sheet_name=sheet)
    except Exception as exc:
        raise ResponseShapeError(
            f"Could not read sheet {sheet!r} from the Atlas: {redact(exc)}"
        ) from exc
    for column in ("FIPS", "State", "County"):
        if column not in frame.columns:
            raise SchemaError(f"Atlas sheet {sheet!r} is missing {column!r}.")

    grain = classify_geographic_grain(frame)
    replicated = sorted(grain.loc[grain["is_group_replicated"], "column"]) if not grain.empty else []
    varying = sorted(grain.loc[~grain["is_group_replicated"], "column"]) if not grain.empty else []

    notes = [
        f"USDA ERS Food Environment Atlas, sheet {sheet!r}, {len(frame):,} county rows.",
        "BULK FILE. The Atlas is an .xls download with no API and no published "
        "version number; the payload hash below is the only vintage identifier "
        "available, and it is computed here rather than supplied by USDA.",
        f"GRAIN: {len(replicated)} of {len(replicated) + len(varying)} numeric columns in "
        f"this sheet hold a single value per state, replicated into every county "
        f"row. They carry a county FIPS and are not county measurements.",
    ]
    if replicated:
        notes.append("State-replicated in this sheet: " + ", ".join(replicated) + ".")
        notes.append(
            "A statistic computed over county rows on one of these columns has an "
            "effective sample size of the number of states, not the number of "
            "counties, and any standard error taken at the county count is too "
            "small by roughly the square root of their ratio."
        )
    else:
        notes.append("No column in this sheet is state-replicated.")

    prov = DataProvenance.build(
        pinned=False,
        source_name="U.S. Department of Agriculture, Economic Research Service",
        dataset=f"Food Environment Atlas -- sheet {sheet}",
        vintage="undated bulk release; identified by payload hash only",
        endpoint=FEA_URL,
        variables={"sheet": sheet},
        payload=raw,
        row_count=len(frame),
        column_count=len(frame.columns),
        notes=tuple(notes),
    )
    return frame, prov


# ---------------------------------------------------------------------------
# IRS Exempt Organizations Business Master File
# ---------------------------------------------------------------------------
#
# Every organisation the IRS recognises as tax-exempt, in four regional CSVs
# totalling roughly 341 MB. It carries NTEE_CD, the classification any
# sector analysis of the nonprofit economy depends on -- and NTEE_CD is null for
# 29.2% of the file, with the missingness running from 21% among 501(c)(3)
# charities to 90% among some other subsections. The client therefore reports
# the classification coverage beside the data, because a sector total computed
# over the classified rows alone is a total over a non-random subset.

IRS_BMF_HOST: Final[str] = "https://www.irs.gov/pub/irs-soi"

#: The four regional files. Together they are the whole master file; there is no
#: national single download.
IRS_BMF_REGIONS: Final[tuple[str, ...]] = ("eo1", "eo2", "eo3", "eo4")

#: NTEE major group -> what it covers. Only the first letter is used here; the
#: full code has three more characters of detail this corpus does not need.
NTEE_MAJOR_GROUPS: Final[dict[str, str]] = {
    "A": "Arts, Culture and Humanities",
    "B": "Education",
    "C": "Environment",
    "D": "Animal-Related",
    "E": "Health Care",
    "F": "Mental Health and Crisis Intervention",
    "G": "Voluntary Health Associations and Medical Disciplines",
    "H": "Medical Research",
    "I": "Crime and Legal-Related",
    "J": "Employment",
    "K": "Food, Agriculture and Nutrition",
    "L": "Housing and Shelter",
    "M": "Public Safety, Disaster Preparedness and Relief",
    "N": "Recreation and Sports",
    "O": "Youth Development",
    "P": "Human Services",
    "Q": "International, Foreign Affairs and National Security",
    "R": "Civil Rights, Social Action and Advocacy",
    "S": "Community Improvement and Capacity Building",
    "T": "Philanthropy, Voluntarism and Grantmaking Foundations",
    "U": "Science and Technology",
    "V": "Social Science",
    "W": "Public and Societal Benefit",
    "X": "Religion-Related",
    "Y": "Mutual and Membership Benefit",
    "Z": "Unknown",
}

#: Columns whose values are amounts and must be numeric before anything is summed.
IRS_BMF_AMOUNTS: Final[tuple[str, ...]] = ("ASSET_AMT", "INCOME_AMT", "REVENUE_AMT")


def fetch_irs_bmf(
    *,
    regions: Sequence[str] = IRS_BMF_REGIONS,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Fetch the IRS exempt-organisation master file, or raise.

    **This is a large download**: the four regional files are about 341 MB in
    total and there is no national single file and no API. The size is reported
    in provenance rather than hidden, because a tutorial that quietly pulls a
    third of a gigabyte is not being honest with its reader.

    Adds two derived columns:

    ``ntee_major``
        The first character of ``NTEE_CD``, or NA. The major group is the level
        at which sector questions are usually asked.
    ``is_classified``
        Whether the organisation carries an NTEE code at all. **29.2% of the
        file does not**, and section 3 of D22 shows that share is strongly
        related to subsection, which means a sector total over the classified
        rows is a total over a non-random subset.
    """
    unknown = sorted(set(regions) - set(IRS_BMF_REGIONS))
    if unknown:
        raise ValueError(
            f"unknown BMF region(s) {unknown}; the file is published as "
            f"{list(IRS_BMF_REGIONS)}."
        )
    if not regions:
        raise ValueError("at least one region is required.")

    http = session or requests
    frames, payloads, sizes = [], [], {}
    for region in regions:
        endpoint = f"{IRS_BMF_HOST}/{region}.csv"
        try:
            resp = http.get(endpoint, timeout=300,
                            headers={"User-Agent": "telosyn-notebooks/1.0"})
        except requests.RequestException as exc:
            raise UpstreamError(f"IRS BMF request failed: {redact(exc)}") from exc
        reject_bot_challenge(resp, source="IRS", endpoint=endpoint)
        if resp.status_code != 200:
            raise UpstreamError(f"IRS returned HTTP {resp.status_code} for {region}.csv.")
        if not resp.content:
            raise EmptyResultError(f"IRS returned an empty body for {region}.csv.")
        payloads.append(resp.content)
        sizes[region] = len(resp.content)
        frames.append(pd.read_csv(io.BytesIO(resp.content), dtype=str, low_memory=False))

    frame = pd.concat(frames, ignore_index=True)
    for column in ("EIN", "NAME", "STATE", "SUBSECTION", "NTEE_CD"):
        if column not in frame.columns:
            raise SchemaError(f"The BMF is missing {column!r}.")
    for column in IRS_BMF_AMOUNTS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    # Uppercased before the first character is taken: the live file carries a
    # handful of lowercase codes (c030, c032, c300), and reading those as a
    # separate group would invent one.
    raw_major = frame["NTEE_CD"].astype("string").str.strip().str.upper().str[0]

    # A code whose first character is not a letter is not an NTEE code. The live
    # file has 25 such rows out of 1,964,958 -- values like "052" and "0000".
    # They are recorded as MALFORMED rather than either raising (which would make
    # the client unusable over 0.0013% of the file) or being accepted (which would
    # put a digit in a sector table). They count as unclassified, because that is
    # what they are.
    malformed = raw_major.notna() & ~raw_major.isin(NTEE_MAJOR_GROUPS)
    frame["ntee_major"] = raw_major.where(~malformed)
    frame["ntee_malformed"] = malformed.fillna(False)
    frame["is_classified"] = frame["ntee_major"].notna()

    unrecognised = sorted(
        set(frame.loc[malformed, "NTEE_CD"].astype("string").str.strip().unique())
    )

    classified = float(frame["is_classified"].mean())
    total_bytes = sum(sizes.values())
    notes = (
        f"IRS Exempt Organizations Business Master File, regions "
        f"{', '.join(regions)}, {len(frame):,} organisations.",
        f"LARGE BULK DOWNLOAD: {total_bytes / 1e6:,.0f} MB across {len(regions)} files "
        f"({', '.join(f'{r} {sizes[r] / 1e6:,.0f} MB' for r in regions)}). No API and no "
        "national single file.",
        f"CLASSIFICATION COVERAGE: NTEE_CD is present for {classified:.1%} of rows and "
        f"absent for {1 - classified:.1%}. Any sector total computed over the classified "
        "rows is a total over a subset, and the subset is not random -- the missing "
        "share varies strongly by SUBSECTION.",
        "The BMF is a registration file, not a financial one. REVENUE_AMT is present "
        "only where a return supplied it, is the most recent period on file rather "
        "than a common year, and is absent for organisations below filing thresholds.",
        "NTEE codes are assigned at registration and are not systematically revised, so "
        "an organisation's code may describe what it was founded to do rather than what "
        "it does.",
        (
            f"MALFORMED CODES: {int(malformed.sum()):,} rows carry an NTEE_CD whose first "
            f"character is not a documented major group ({', '.join(unrecognised[:8])}"
            f"{', ...' if len(unrecognised) > 8 else ''}). They are counted as "
            "unclassified, not as a group of their own."
            if malformed.any()
            else "MALFORMED CODES: none; every NTEE_CD present begins with a documented "
            "major group."
        ),
    )
    prov = DataProvenance.build(
        pinned=False,
        source_name="Internal Revenue Service, Statistics of Income",
        dataset="Exempt Organizations Business Master File",
        vintage="undated rolling extract; identified by payload hash only",
        endpoint=f"{IRS_BMF_HOST}/{{{','.join(regions)}}}.csv",
        variables={"regions": ",".join(regions)},
        payload=b"".join(payloads),
        row_count=len(frame),
        column_count=len(frame.columns),
        notes=notes,
    )
    return frame, prov


# ---------------------------------------------------------------------------
# CDC open data (Socrata), and NCHS Health, United States
# ---------------------------------------------------------------------------
#
# CDC WONDER refuses automated query (HTTP 403 to this client, checked
# 2026-09-15), but a large part of what an analyst wants from NCHS is also
# published through data.cdc.gov's Socrata API, which does not.
#
# The NCHS "Health, United States" tables served there share one structure worth
# naming: a flat table in which `stub_name` carries SEVERAL DIFFERENT
# cross-classifications of the same deaths. In the suicide table, 84 of 6,390
# rows are the total and the other 98.7% are subgroup estimates at seven levels
# of crossing, plus a race-coding changeover year in which two incompatible
# standards are both published. Any aggregate over the estimate column that does
# not first filter `stub_name` is summing a population several times over.

CDC_SOCRATA_HOST: Final[str] = "https://data.cdc.gov"

#: Socrata's default page is 1,000 rows and its documented maximum for a single
#: request is 50,000. A client that takes the default silently truncates.
CDC_SOCRATA_MAX_LIMIT: Final[int] = 50_000

#: NCHS Health, United States -- death rates for suicide.
NCHS_SUICIDE_DATASET: Final[str] = "9j2v-jamp"

#: The stub level that is the whole population. Everything else is a subgroup.
NCHS_TOTAL_STUB: Final[str] = "Total"

#: Marker NCHS appends to stub names computed under the post-1997 single-race
#: coding standard. Rows with and without it are not comparable and, in the
#: changeover year, both are published.
NCHS_SINGLE_RACE_MARKER: Final[str] = "(Single race)"


def fetch_cdc_socrata(
    *,
    dataset: str,
    limit: int = CDC_SOCRATA_MAX_LIMIT,
    where: str | None = None,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Fetch one CDC open-data resource, or raise.

    ``limit`` is explicit and defaults to the documented maximum rather than
    Socrata's 1,000-row default, because the default is how a client silently
    returns a truncated table. If the response fills the limit exactly, this
    raises rather than returning what may be a partial result.
    """
    if not re.fullmatch(r"[a-z0-9]{4}-[a-z0-9]{4}", dataset):
        raise ValueError(
            f"{dataset!r} is not a Socrata dataset identifier (xxxx-xxxx)."
        )
    if not 1 <= limit <= CDC_SOCRATA_MAX_LIMIT:
        raise ValueError(
            f"limit must be between 1 and {CDC_SOCRATA_MAX_LIMIT:,}; got {limit:,}. "
            "Page with $offset for a larger table."
        )
    params = {"$limit": str(limit)}
    if where:
        params["$where"] = where
    endpoint = f"{CDC_SOCRATA_HOST}/resource/{dataset}.json"
    http = session or requests
    try:
        resp = http.get(endpoint, params=params, timeout=180,
                        headers={"User-Agent": "telosyn-notebooks/1.0"})
    except requests.RequestException as exc:
        raise UpstreamError(f"CDC Socrata request failed: {redact(exc)}") from exc
    reject_bot_challenge(resp, source="CDC open data", endpoint=endpoint)
    if resp.status_code != 200:
        raise UpstreamError(
            f"CDC Socrata returned HTTP {resp.status_code} for {dataset}."
        )
    payload = _assert_json_payload(resp, endpoint)
    if not isinstance(payload, list):
        raise ResponseShapeError(
            f"CDC Socrata returned {type(payload).__name__}, not a row list."
        )
    if not payload:
        raise EmptyResultError(f"CDC Socrata returned no rows for {dataset}.")
    if len(payload) == limit:
        raise ResponseShapeError(
            f"CDC Socrata returned exactly {limit:,} rows, which is the requested "
            "limit. The result may be truncated and this client will not return a "
            "table it cannot certify as complete. Page with $offset, or narrow the "
            "query."
        )

    frame = pd.DataFrame(payload)
    prov = DataProvenance.build(
        pinned=False,
        hash_basis="canonical-json",
        source_name="Centers for Disease Control and Prevention",
        dataset=f"data.cdc.gov resource {dataset}",
        vintage="Socrata resource; no version served, identified by payload hash",
        endpoint=endpoint,
        variables={"dataset": dataset, "limit": str(limit), "where": where or ""},
        payload=json.dumps(payload, sort_keys=True, default=str).encode("utf-8"),
        row_count=len(frame),
        column_count=len(frame.columns),
        notes=(
            f"CDC open data (Socrata) resource {dataset}, {len(frame):,} rows.",
            "CDC WONDER refuses automated query; this API does not, and serves much "
            "of the same NCHS material. It is not a WONDER substitute -- WONDER's "
            "custom cross-tabulations are not available here.",
            f"Requested $limit={limit:,} explicitly. Socrata's default is 1,000 rows, "
            "which is how a client silently returns a truncated table.",
        ),
    )
    return frame, prov


def describe_stub_levels(frame: pd.DataFrame, *, column: str = "stub_name") -> pd.DataFrame:
    """Summarise the cross-classifications packed into one NCHS flat table.

    Returns one row per distinct ``stub_name`` with its row count, its year span
    and whether it uses the single-race coding standard. The point is to make
    visible that these are not comparable strata of one breakdown but several
    different breakdowns of the same deaths.
    """
    if column not in frame.columns:
        raise ValueError(f"{column!r} is not a column of this frame.")
    work = frame.copy()
    work["_single_race"] = work[column].astype("string").str.contains(
        re.escape(NCHS_SINGLE_RACE_MARKER), na=False
    )
    aggregations = {"rows": (column, "size"), "single_race": ("_single_race", "first")}
    if "year" in work.columns:
        years = pd.to_numeric(work["year"], errors="coerce")
        work = work.assign(_year=years)
        aggregations |= {"first_year": ("_year", "min"), "last_year": ("_year", "max")}
    if "estimate" in work.columns:
        work = work.assign(_estimate=pd.to_numeric(work["estimate"], errors="coerce"))
        aggregations |= {"with_estimate": ("_estimate", "count")}
    levels = work.groupby(column).agg(**aggregations).sort_values("rows", ascending=False)
    return levels.reset_index()


# Every public fetcher appends to the notebook's run ledger (provenance.use_ledger), before it raises as well as after success.
for _name in [n for n, f in list(globals().items()) if n.startswith("fetch_") and callable(f) and not getattr(f, "__ledgered__", False)]:
    globals()[_name] = ledgered(globals()[_name])
del _name
