"""Re-fetch every recorded provenance payload and ask whether it still reproduces.

Handbook §5.1 clause 1 says that if a number will be read twice it must be the
same number twice. Every notebook records a `content_sha256` for each dataset it
retrieved. Nothing had ever re-issued those requests, so the corpus asserted
reproducibility without having tested it once.

This script tests it. For each `provenance/*.json` under `projects/` whose
`endpoint` is a complete, directly re-fetchable URL, it re-issues the request and
compares the digest against the recorded one.

**The hash basis matters and is why this script exists in this form.** Fetchers
that hash the raw response body record `hash_basis: "response-bytes"`; those that
canonicalise a JSON body first record `"canonical-json"`. A verifier that assumes
one basis reports a payload change that did not happen. The first run of this
sweep did exactly that to D04: PLACES came back `DIFF` with an identical row count
and an identical byte length, and the difference was key ordering in a re-
serialisation, not a revision. Records written before that field existed carry no
basis, so this script tries every basis and reports which one matched.

What a SAME result establishes, and what it does not: the payload behind a
recorded number is still retrievable and unchanged **as of this run**. It is not a
measurement of revision magnitude. A source that revises annually will read SAME
all year and then not.

Usage:  python scripts/verify_provenance_reproducibility.py [--json]

Exit status is 1 if any record failed to reproduce, 0 otherwise. A record that
cannot be replayed at all is reported and does not fail the run — it is a gap in
what provenance stores, not evidence about the data.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from krl_tutorials_data import sources  # noqa: E402 - after the path is set
from krl_tutorials_data.provenance import (  # noqa: E402
    canonical_rows,
    canonical_stable_json,
)

PROVENANCE_GLOB = "projects/**/provenance/*.json"
TIMEOUT_SECONDS = 60

#: Same header every fetcher sends. Harvard Dataverse answers 403 to the default
#: `python-requests` agent, so an unnamed client would mis-report a failure.
HEADERS = {"User-Agent": "krl-tutorials/1.0 (research corpus; provenance replay)"}

#: How each recorded basis turns response bytes into the hashed payload.
BASES: dict[str, Callable[[bytes], bytes]] = {
    "response-bytes": lambda raw: raw,
    "canonical-json": lambda raw: json.dumps(json.loads(raw), sort_keys=True).encode(),
    "canonical-rows": canonical_rows,
    "canonical-stable-json": canonical_stable_json,
}


#: Parameter values that stand in for a credential the record refuses to store.
#: The replayer supplies its own from the local secrets file; it never learns the
#: original, and the original is not in the file it is reading.
REDACTED_MARKER = "<redacted>"

#: Which secret each source's credential parameter wants. Keyed by host fragment
#: so one entry covers every endpoint at that host.
CREDENTIAL_FOR_HOST: dict[str, str] = {
    "api.census.gov": "CENSUS_API_KEY",
    "api.stlouisfed.org": "FRED_API_KEY",
    "apps.bea.gov": "BEA_API_KEY",
    "api.bls.gov": "BLS_API_KEY",
    "api.usa.gov": "FBI_CDE_API_KEY",
    "www.huduser.gov": "HUD_API_KEY",
}


def _replayable(record: dict[str, Any]) -> bool:
    """Either a complete URL, or a base plus the parameters to rebuild one."""
    endpoint = record.get("endpoint", "")
    if not endpoint.startswith(("http://", "https://")):
        return False
    if endpoint.endswith(".csv") or "?" in endpoint:
        return True
    return bool(record.get("request_params"))


def _restore_credentials(params: dict[str, str], endpoint: str) -> dict[str, str] | None:
    """Put this machine's own key back where the record kept a placeholder.

    Returns None when a credential is needed and not available, so the record is
    reported as skipped rather than replayed against a broken request.
    """
    restored = dict(params)
    for name, value in params.items():
        if value != REDACTED_MARKER:
            continue
        secret = next((s for host, s in CREDENTIAL_FOR_HOST.items() if host in endpoint), None)
        if secret is None:
            return None
        try:
            restored[name] = sources.load_key(secret)
        except Exception:  # noqa: BLE001 - a missing key is a skip, not a failure
            return None
    return restored


def _age_days(record: dict[str, Any]) -> int:
    recorded = datetime.fromisoformat(record["retrieved_utc"])
    return (datetime.now(timezone.utc) - recorded).days


def _digests(raw: bytes) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, transform in BASES.items():
        try:
            out[name] = hashlib.sha256(transform(raw)).hexdigest()
        except (ValueError, UnicodeDecodeError):
            continue
    return out


def verify(records: list[tuple[Path, dict[str, Any]]]) -> list[dict[str, Any]]:
    session = requests.Session()
    session.headers.update(HEADERS)
    results: list[dict[str, Any]] = []
    for path, record in records:
        row: dict[str, Any] = {
            "file": str(path.relative_to(REPO_ROOT)),
            "dataset": record.get("dataset", "?"),
            "recorded_basis": record.get("hash_basis"),
            "age_days": _age_days(record),
        }
        params_recorded = record.get("request_params") or {}
        if "assembled_from_batches" in params_recorded:
            row["status"] = "NOT_REPLAYABLE"
            row["reason"] = (f"joined from {params_recorded['assembled_from_batches']} batched "
                             "requests; there is no single request to reissue")
            results.append(row)
            continue
        if record.get("endpoint", "").startswith("file://"):
            row["status"] = "PINNED_LOCALLY"
            row["reason"] = "a bulk file, verified by BulkFileSource against its pinned digest"
            results.append(row)
            continue
        if not _replayable(record):
            row["status"] = "NOT_REPLAYABLE"
            row["reason"] = "endpoint is not a complete URL; the query is not stored"
            results.append(row)
            continue
        params = record.get("request_params") or {}
        if params:
            restored = _restore_credentials(params, record["endpoint"])
            if restored is None:
                row["status"] = "NO_CREDENTIAL"
                row["reason"] = "the request needs a key this machine does not hold"
                results.append(row)
                continue
            params = restored
        try:
            method = (record.get("request_method") or "GET").upper()
            if method == "POST":
                response = session.post(record["endpoint"], json=params or None,
                                        timeout=TIMEOUT_SECONDS)
            else:
                response = session.get(record["endpoint"], params=params or None,
                                       timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001 - reported, not raised
            # `requests` exceptions carry the request URL, and several of these
            # sources take the key as a query parameter. Never surface it raw.
            row["status"] = "ERROR"
            row["reason"] = sources.redact(f"{type(exc).__name__}: {exc}")[:160]
            results.append(row)
            continue
        digests = _digests(response.content)
        matched = [name for name, digest in digests.items()
                   if digest == record["content_sha256"]]
        row["bytes"] = len(response.content)
        if matched:
            row["status"] = "SAME"
            row["matched_basis"] = matched[0]
        else:
            row["status"] = "DIFF"
            row["digests"] = {k: v[:16] for k, v in digests.items()}
            row["recorded"] = record["content_sha256"][:16]
        results.append(row)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    args = parser.parse_args()

    records = [(p, json.loads(p.read_text(encoding="utf-8")))
               for p in sorted(REPO_ROOT.glob(PROVENANCE_GLOB))]
    results = verify(records)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        width = max((len(r["dataset"]) for r in results), default=10)
        for row in results:
            extra = row.get("matched_basis") or row.get("reason", "")
            print(f"  {row['status']:<15} {row['dataset'][:width]:<{width}}  "
                  f"{row['age_days']:>3}d  {extra}")
        counts: dict[str, int] = {}
        for row in results:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        print()
        print(f"{len(results)} provenance records")
        for status in ("SAME", "DIFF", "PINNED_LOCALLY", "ERROR", "NO_CREDENTIAL", "NOT_REPLAYABLE"):
            if status in counts:
                print(f"  {status:<15} {counts[status]}")
    return 1 if any(r["status"] == "DIFF" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
