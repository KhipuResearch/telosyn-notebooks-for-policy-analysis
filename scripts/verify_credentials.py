#!/usr/bin/env python3
"""Check that every credential the corpus needs is present and live.

Run this **after** rotating a key, to confirm the new value works before
discovering it in a failed notebook run half an hour later.

It makes one cheap, real request per credential and reports pass or fail. It
never prints, logs or returns a key value: the only thing it says about a
credential is its name and whether the provider accepted it. A provider error is
reported through ``sources.redact`` for the same reason -- several of these APIs
take the key as a query parameter and echo the request URL back in their errors.

Usage::

    KRL_SECRETS_PATH=~/.config/telosyn-notebooks/keys.env python scripts/verify_credentials.py

Exit codes: 0 all present and accepted; 1 at least one missing or rejected.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from krl_tutorials_data import sources  # noqa: E402 - after the path is set

#: One cheap call per credential, chosen to be the smallest request that still
#: proves the key was accepted rather than merely well-formed.
PROBES = {
    "CENSUS_API_KEY": lambda: sources.fetch_acs(
        year=2023, variables={"B01003_001E": "population"}, geography="state:01"),
    "FRED_API_KEY": lambda: sources.fetch_fred(
        series_id="CPIAUCSL", start="2024-01-01", end="2024-03-01"),
    "BLS_API_KEY": lambda: sources.fetch_bls(
        series={"LAUST510000000000003": "VA unemployment rate"},
        start_year=2023, end_year=2023),
    "BEA_API_KEY": lambda: sources.fetch_bea_regional(
        table="SAACArtsVA", line_code="ALL", year=2023, geo_fips="00000"),
    "HUD_API_KEY": lambda: sources.fetch_hud_fmr_county(fips="5105999999", year=2026),
    "DATA_GOV_API_KEY": lambda: sources.fetch_fbi_cde_summarized(
        state="VA", offense="V", from_month="01-2023", to_month="03-2023"),
}


def main() -> int:
    failures = 0
    print(f"key file (KRL_SECRETS_PATH): {sources.secrets_path() or 'not set; environment only'}")
    print(f"allowed names: {len(sources.ALLOWED_KEYS)}\n")

    for name in sorted(sources.ALLOWED_KEYS):
        try:
            sources.load_key(name)
        except Exception as exc:  # noqa: BLE001 - reported, not raised
            print(f"  MISSING   {name:<20} {type(exc).__name__}")
            failures += 1
            continue

        probe = PROBES.get(name)
        if probe is None:
            print(f"  PRESENT   {name:<20} (no probe defined)")
            continue
        try:
            probe()
            print(f"  LIVE      {name:<20} provider accepted it")
        except Exception as exc:  # noqa: BLE001 - reported, not raised
            # HUD's small-area response and the CDE's upstream flapping are
            # service behaviour, not credential failure: a rejected key does not
            # get far enough to produce them.
            #
            # Checked rather than assumed, because a lenient branch that also
            # swallowed a bad key would report a broken credential as LIVE --
            # the one failure this script exists to prevent. Probed 2026-09-18
            # with a syntactically valid wrong key: BLS raises BLSRequestError
            # and HUD raises MissingCredentialError. Neither is in this set.
            kind = type(exc).__name__
            if kind in {"ResponseShapeError", "CDEUpstreamUnavailable"}:
                print(f"  LIVE      {name:<20} accepted (service returned {kind})")
                continue
            print(f"  REJECTED  {name:<20} {kind}: {sources.redact(str(exc))[:90]}")
            failures += 1

    print()
    print("all six credentials present and accepted" if not failures
          else f"{failures} credential(s) need attention")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
