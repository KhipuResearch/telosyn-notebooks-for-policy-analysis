"""The vintage flag, the hash basis, and the rule that neither may be guessed.

Three defects in this corpus's provenance handling are guarded here, all of them
found during the handbook §5.4 vintage-policy pass.

**1. `(pinned)` was printed unconditionally.** `DataProvenance.render()` labelled
every vintage `(pinned)` regardless of whether the source can serve a prior
vintage at all. That line printed into the stored output of sixteen notebooks,
three of which are built on QCEW, CBP or BLS LAUS -- sources that handbook §5.5
had already measured as serving no vintage. Naming a reference period is not
pinning a vintage, and the block asserted otherwise.

**2. The hash basis was not recorded.** Nine fetchers hash the raw response body;
two canonicalise a JSON body first. A verifier that assumes one basis reports a
payload change that did not happen -- which is what the first run of
`scripts/verify_provenance_reproducibility.py` did to D04.

**3. Credentials could reach a committed file.** `request_params` exists so a
record can be replayed, and several of these sources take the key as a query
parameter. Redaction therefore happens inside `build`, not at the call site.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from typing import Final

import pytest

from krl_tutorials_data import sources
from krl_tutorials_data.provenance import (
    REDACTED,
    DataProvenance,
    redact_params,
)

REPO_ROOT: Final = Path(__file__).resolve().parent.parent

#: Sources that either serve prior vintages on request, or publish each vintage
#: as a separately addressed immutable asset. Everything else revises and serves
#: only "now", so its `year` argument selects a reference period and this
#: retrieval is the only vintage that will ever exist (handbook §5.5).
#:
#: This list is the reviewed judgement, and the test below holds every other
#: fetcher to `pinned=False`. Adding a fetcher without deciding which it is fails.
PINNED_FETCHERS: Final[frozenset[str]] = frozenset({
    "fetch_acs",                  # each ACS release is a distinct, permanent product
    "fetch_acs_wide",
    "fetch_acs_pums",             # a PUMS 1-year file is a separately addressed, immutable release
    "fetch_fred",                 # ALFRED serves any vintage by date
    "fetch_places_county",        # each release is a separately addressed asset
    "fetch_opportunity_atlas",    # static archived research release
    "fetch_social_capital_atlas",  # named dated release
    "fetch_dataverse_file",       # conditional: pinned only with expected_md5
    "fetch_mit_president",        # delegates to fetch_dataverse_file
})


def _fetcher_bodies() -> dict[str, str]:
    out: dict[str, str] = {}
    for name, obj in vars(sources).items():
        if name.startswith("fetch_") and callable(obj):
            try:
                out[name] = inspect.getsource(obj)
            except (OSError, TypeError):  # pragma: no cover
                continue
    return out


# ------------------------------------------------------------------ redaction

@pytest.mark.parametrize(
    "param", ["key", "api_key", "API_KEY", "UserID", "registrationkey", "token", "secret"]
)
def test_a_credential_parameter_never_survives(param: str) -> None:
    """Every spelling these sources use for the same secret."""
    out = redact_params({param: "0123456789abcdef", "for": "state:*"})
    assert out[param] == REDACTED
    assert "0123456789abcdef" not in json.dumps(out)
    assert out["for"] == "state:*", "a non-credential parameter must survive intact"


def test_redaction_keeps_the_name_and_none_of_the_value() -> None:
    """A replayer must know a key was sent; it must learn nothing about it."""
    secret = "S3CR3T-material-9999"  # pragma: allowlist secret -- a fake value, redaction is the subject
    out = redact_params({"key": secret})
    assert "key" in out
    for fragment in (secret, secret[:6], secret[-4:], str(len(secret))):
        assert fragment not in json.dumps(out)


def test_build_redacts_rather_than_trusting_the_caller() -> None:
    """The call sites pass their live params dict straight through."""
    record = DataProvenance.build(
        source_name="s", dataset="d", vintage="2023", endpoint="https://x/y",
        variables={}, payload=b"p", row_count=1, column_count=1,
        request_params={"get": "NAME", "key": "LEAKME-0123456789"},
    )
    assert "LEAKME" not in json.dumps(record.to_dict())
    assert record.request_params["key"] == REDACTED


def test_no_committed_provenance_record_carries_a_credential() -> None:
    """The records are in the repository, so this is the check that matters."""
    pattern = re.compile(
        r'"(?:[^"]*(?:key|token|userid|secret|password)[^"]*)"\s*:\s*"(?!<redacted>)([^"]{8,})"',
        re.IGNORECASE,
    )
    offenders: list[str] = []
    for path in REPO_ROOT.glob("projects/**/provenance/*.json"):
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.name}: {match.group(0)[:60]}")
    assert not offenders, f"credential-shaped values in committed provenance: {offenders}"


# ------------------------------------------------------------------ hash basis

def test_an_uninterpretable_hash_basis_is_refused() -> None:
    with pytest.raises(ValueError, match="hash_basis"):
        DataProvenance.build(
            source_name="s", dataset="d", vintage="v", endpoint="e", variables={},
            payload=b"p", row_count=1, column_count=1, hash_basis="whatever",
        )


def test_a_json_canonicalising_fetcher_declares_it() -> None:
    """The defect that produced a false DIFF against D04."""
    bodies = _fetcher_bodies()
    for name, body in bodies.items():
        canonicalises = "json.dumps(payload, sort_keys=True" in body
        if canonicalises:
            assert 'hash_basis="canonical-json"' in body, (
                f"{name} hashes a re-serialised payload but does not say so. A "
                "verifier replaying it against raw response bytes will report a "
                "payload change that did not happen."
            )


def test_the_render_block_says_which_it_is() -> None:
    """`(pinned)` used to print unconditionally, including where it was false."""
    def record(pinned: bool) -> str:
        return DataProvenance.build(
            source_name="s", dataset="d", vintage="2024Q1", endpoint="e", variables={},
            payload=b"p", row_count=1, column_count=1, pinned=pinned,
        ).render()

    assert "(pinned)" in record(True)
    assert "NOT pinned" in record(False)
    assert "(pinned)" not in record(False).replace("NOT pinned", "")


# ------------------------------------------------------------------ the classification

def test_every_fetcher_has_a_decided_pinning_status() -> None:
    """No fetcher may take the default by accident.

    `pinned` defaults to True, which is the convenient default and the wrong one
    for most of this corpus's sources. Every fetcher not on the reviewed
    PINNED_FETCHERS list must say `pinned=False` in its own body.
    """
    undecided: list[str] = []
    for name, body in _fetcher_bodies().items():
        if "DataProvenance.build(" not in body:
            continue          # returns no provenance record
        if name in PINNED_FETCHERS:
            continue
        if "pinned=False" not in body:
            undecided.append(name)
    assert not undecided, (
        f"{undecided} build a provenance record without declaring pinned=False, so "
        "they claim their vintage is enforceable. Either it is -- add the fetcher "
        "to PINNED_FETCHERS with the reason -- or say pinned=False."
    )


def test_dataverse_is_pinned_only_when_a_checksum_is_supplied() -> None:
    """The one genuinely conditional case in the corpus."""
    body = _fetcher_bodies()["fetch_dataverse_file"]
    assert "pinned=expected_md5 is not None" in body, (
        "fetch_dataverse_file records the publisher's MD5 whether or not the "
        "caller pins one. Recording a checksum is not verifying against it."
    )


@pytest.mark.parametrize("name", sorted(PINNED_FETCHERS))
def test_the_pinned_list_names_real_fetchers(name: str) -> None:
    """Guard the allowlist against drift when a fetcher is renamed."""
    assert name in _fetcher_bodies(), f"{name} is on PINNED_FETCHERS but does not exist"
