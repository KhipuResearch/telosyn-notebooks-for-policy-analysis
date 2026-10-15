"""Provenance records for every dataset that enters an analysis.

A notebook may not report a quantity whose provenance is unknown. This module
makes provenance a first-class object rather than a comment.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class DataMode(str, Enum):
    """How a reported quantity came to exist.

    The release contract requires every reported quantity to carry one of
    these. There is deliberately no ``SYNTHETIC`` member available to the
    tutorial corpus.
    """

    EMPIRICAL = "empirical"        # measured, retrieved from an authoritative source
    ESTIMATED = "estimated"        # derived from empirical data by a stated estimator
    ILLUSTRATIVE = "illustrative"  # shown to explain a concept; never a finding
    HYPOTHETICAL = "hypothetical"  # a stated what-if; never a finding


#: Query-parameter names that carry credentials at one or more of this corpus's
#: sources. Matched case-insensitively as a substring, because the same secret is
#: ``key`` at Census, ``api_key`` at FRED, ``UserID`` at BEA, ``registrationkey``
#: at BLS and ``API_KEY`` at the FBI CDE. Substring matching over-redacts -- a
#: parameter innocently named ``monkey`` would be dropped -- and that is the
#: correct direction for the error to run.
_CREDENTIAL_PARAMS: frozenset[str] = frozenset({"key", "token", "userid", "secret", "password"})

#: What replaces a redacted value, so a reader can see that a parameter was sent.
REDACTED: str = "<redacted>"


def redact_params(params: dict[str, Any]) -> dict[str, Any]:
    """Copy request parameters, replacing any credential value.

    Values are never partially preserved: no prefix, no length, no last four.
    A redacted parameter keeps its **name** so that a replayer knows to supply
    one, and nothing of its value.

    **Structure is preserved.** An earlier version called ``str(value)`` on every
    parameter, which turned the BLS request body's ``seriesid`` list into the
    string ``"['LAUCN...', ...]"``. Replaying that posted a string where the API
    expects an array, and both D02 records came back with the same generic
    response -- two different requests, one answer, and a DIFF that said nothing
    about the data. A parameter that cannot be replayed is not recorded, it is
    only described.
    """
    out: dict[str, Any] = {}
    for name, value in params.items():
        key = str(name)
        if any(marker in key.lower() for marker in _CREDENTIAL_PARAMS):
            out[key] = REDACTED
        elif isinstance(value, (str, int, float, bool, type(None), list, dict)):
            out[key] = value
        else:
            out[key] = str(value)
    return out


#: The permitted values of :attr:`DataProvenance.hash_basis`.
_HASH_BASES: frozenset[str] = frozenset(
    {
        "response-bytes",
        "canonical-json",
        "canonical-rows",
        "canonical-stable-json",
        #: A retrieval assembled from several requests, whose digest is taken over
        #: the ordered per-batch digests rather than over any one body. Named so
        #: that a verifier does not try to reproduce it from a single response.
        "composed-digests",
    }
)

#: Top-level JSON fields that vary between two identical requests and carry no
#: information about the data. Every entry here is a measured observation, not a
#: guess, and adding one is a deliberate act: it removes a field from what the
#: digest covers.
#:
#: ``responseTime`` -- BLS v2 returns the request's own latency in milliseconds
#: inside the payload. Three identical POSTs on 2026-09-18 returned three
#: distinct byte digests and one identical ``Results`` object. A digest over the
#: response body therefore never matches on re-fetch, so the corpus's recorded
#: BLS hashes could not verify anything at all.
#: ``UTCProductionTime`` -- BEA stamps each response with the time it was
#: produced, nested inside ``BEAAPI.Results`` rather than at the top level. A
#: digest pin on BEA fired within minutes of being set, which is how this was
#: found: the pin was right and the basis was wrong.
VOLATILE_JSON_FIELDS: frozenset[str] = frozenset({"responseTime", "UTCProductionTime"})


def _without_volatile(value: Any) -> Any:
    """Drop :data:`VOLATILE_JSON_FIELDS` wherever they occur, at any depth."""
    if isinstance(value, dict):
        return {k: _without_volatile(v) for k, v in value.items()
                if k not in VOLATILE_JSON_FIELDS}
    if isinstance(value, list):
        return [_without_volatile(v) for v in value]
    return value


def canonical_stable_json(payload: bytes) -> bytes:
    """Key-sorted JSON with :data:`VOLATILE_JSON_FIELDS` removed at every depth.

    Stripping only the top level was enough for BLS and not for BEA, whose
    timestamp sits one level down. Recursion is the honest rule: a field that
    carries no information about the data carries none wherever it appears.

    It is deliberately narrow. Each name in the set removes that key from every
    digest in the corpus, so the set stays short and every entry cites the
    measurement that put it there.
    """
    return json.dumps(_without_volatile(json.loads(payload)), sort_keys=True).encode()


def canonical_rows(payload: bytes) -> bytes:
    """Row-order-independent form of a Census-style ``[[header], [row], ...]`` body.

    The Census API does not guarantee row order, and does not hold it stable.
    Measured on 2026-09-18: **25 identical requests** to CBP 2022 county 51720
    returned **3 distinct byte digests**, a single distinct row multiset, and 89
    rows every time. The data is stable; the serialisation is not.

    A SHA-256 over the response body is therefore not a content identifier for
    this source -- it fails on roughly one request in twelve for reasons that have
    nothing to do with the data. Hashing the header plus the **sorted** rows gives
    an identifier that changes when the data changes and not otherwise.

    This is lossy by design: it discards row order. That is correct where the rows
    are an unordered set of geographies or industries, and **wrong for a series**,
    so it is chosen per fetcher rather than applied globally. FRED and BLS keep
    ``response-bytes``, because for a time series the order is the data.
    """
    parsed = json.loads(payload)
    if not isinstance(parsed, list) or not parsed:
        raise ValueError("canonical-rows expects a non-empty JSON array of rows")
    header, *rows = parsed
    return json.dumps([header, *sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))],
                      sort_keys=True).encode()


@dataclass(frozen=True)
class DataProvenance:
    """An immutable record of where one dataset came from."""

    source_name: str
    dataset: str
    vintage: str
    endpoint: str
    variables: dict[str, str]
    retrieved_utc: str
    row_count: int
    column_count: int
    content_sha256: str
    mode: DataMode = DataMode.EMPIRICAL
    notes: tuple[str, ...] = field(default_factory=tuple)

    #: Whether ``vintage`` is *enforceable*. True only where the publisher either
    #: serves prior vintages on request (FRED/ALFRED) or publishes each vintage as
    #: a separately addressed immutable asset (an ACS release year, a named PLACES
    #: release, a dated bulk file).
    #:
    #: False is the honest value for a source that revises and serves only "now" --
    #: QCEW, CBP, BDS, BEA, HUD CHAS, the FBI CDE, an undated bulk extract. For
    #: those, naming a ``year`` pins the **reference period**, not the vintage, and
    #: this retrieval is the only vintage that will ever exist (handbook §5.5).
    pinned: bool = True

    #: What ``content_sha256`` was computed over. Fetchers that hash the raw
    #: response body record ``"response-bytes"``; those that canonicalise a JSON
    #: body before hashing record ``"canonical-json"``.
    #:
    #: Recorded because a verifier has to know. Replaying a ``canonical-json``
    #: record against raw bytes reports a payload change that did not happen --
    #: which is exactly what the first run of
    #: ``scripts/verify_provenance_reproducibility.py`` did to D04.
    hash_basis: str = "response-bytes"

    #: The query parameters of the request, **with every credential removed**.
    #:
    #: Without these a record naming ``https://api.census.gov/data/2023/acs/acs5``
    #: cannot be replayed: the geography and the variable list are not in the URL.
    #: 29 of the corpus's first 40 provenance records are unreplayable for exactly
    #: that reason.
    #:
    #: Redaction is not optional and is not the caller's job. :meth:`build` strips
    #: any parameter whose name matches :data:`_CREDENTIAL_PARAMS` before storing,
    #: because these records are committed to the repository and several of the
    #: sources take the key as a query parameter. A replayer supplies its own key
    #: from the local secrets file.
    request_params: dict[str, Any] = field(default_factory=dict)

    #: The HTTP method the fetcher used. BLS posts a JSON body; replaying that
    #: record as a GET with the body as query parameters returns **HTTP 405**,
    #: which the first credential-aware sweep duly reported as an error against
    #: two D02 records. The method is part of the request, so it is part of the
    #: record.
    request_method: str = "GET"

    @staticmethod
    def hash_payload(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    @classmethod
    def build(
        cls,
        *,
        source_name: str,
        dataset: str,
        vintage: str,
        endpoint: str,
        variables: dict[str, str],
        payload: bytes,
        row_count: int,
        column_count: int,
        notes: tuple[str, ...] = (),
        pinned: bool = True,
        hash_basis: str = "response-bytes",
        request_params: dict[str, Any] | None = None,
        request_method: str = "GET",
    ) -> "DataProvenance":
        if hash_basis not in _HASH_BASES:
            raise ValueError(
                f"hash_basis {hash_basis!r} is not one of {sorted(_HASH_BASES)}; "
                "a basis a verifier cannot interpret is worse than none."
            )
        return cls(
            source_name=source_name,
            dataset=dataset,
            vintage=vintage,
            endpoint=endpoint,
            variables=dict(variables),
            retrieved_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            row_count=row_count,
            column_count=column_count,
            content_sha256=cls.hash_payload(payload),
            notes=tuple(notes),
            pinned=pinned,
            hash_basis=hash_basis,
            request_params=redact_params(request_params or {}),
            request_method=request_method.upper(),
        )

    def _pin_label(self) -> str:
        """Say which it is. The old block said "(pinned)" unconditionally.

        That line printed into the stored output of sixteen notebooks, including
        ones built on sources that serve no vintage at all, and it asserted
        something the corpus had not established. Naming a reference period is
        not pinning a vintage.
        """
        if self.pinned:
            return "(pinned)"
        return "(NOT pinned - the source serves no prior vintage; this retrieval is the only one)"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["mode"] = self.mode.value
        return d

    def write(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return p

    def render(self) -> str:
        """A provenance block for display directly above any table or figure."""
        lines = [
            f"Source      : {self.source_name} - {self.dataset}",
            f"Vintage     : {self.vintage}  {self._pin_label()}",
            f"Endpoint    : {self.endpoint}",
            f"Retrieved   : {self.retrieved_utc}",
            f"Shape       : {self.row_count} rows x {self.column_count} cols",
            f"Payload hash: {self.content_sha256[:16]}...  ({self.hash_basis})",
            f"Data mode   : {self.mode.value.upper()}",
            "Variables   :",
        ]
        for code, label in self.variables.items():
            lines.append(f"              {code:<16} {label}")
        if self.notes:
            lines.append("Limitations :")
            lines.extend(f"              - {n}" for n in self.notes)
        return "\n".join(lines)
