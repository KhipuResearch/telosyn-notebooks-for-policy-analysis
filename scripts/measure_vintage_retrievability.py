"""Can each source be asked what it previously said?

Revision and *retrievability of the past* are separate properties, and this
corpus had only ever treated them as one. FRED revises and serves any vintage
through ALFRED. BEA revises four prior years in a single release and serves no
vintage at all. HUD CHAS serves only "the latest range". HUD FMR publishes an
original and a revised file with no series connecting them.

A source that revises and cannot be asked what it previously said cannot support
an as-of analysis, a back-test, or the reproduction of anyone's prior result --
including your own. The only defence is to pin your own copy at retrieval, which
is what §5.3 of the handbook already requires for bulk files and had not stated
as a property of *sources*.

This script establishes the BEA half empirically: it enumerates every BEA dataset
and reports whether any of them offers a vintage, as-of or archive parameter.

    KRL_SECRETS_PATH=... python scripts/measure_vintage_retrievability.py

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from krl_tutorials_data.sources import load_key

BEA_HOST = "https://apps.bea.gov/api/data"

#: Words a vintage-selecting parameter would plausibly use. Deliberately wide:
#: the claim is that nothing of this kind exists, so the search must be generous
#: or the absence proves nothing.
VINTAGE_WORDS = re.compile(r"vintage|as.?of|revision|release|archive|version|snapshot", re.I)


def bea(**params: Any) -> dict:
    query = urllib.parse.urlencode(
        {"UserID": load_key("BEA_API_KEY"), "ResultFormat": "JSON", **params}
    )
    with urllib.request.urlopen(f"{BEA_HOST}?{query}", timeout=60) as response:
        return json.loads(response.read())


def parameter_names(dataset: str) -> list[tuple[str, str]]:
    """(name, description) for each parameter, tolerating BEA's shape changes."""
    result = bea(method="GetParameterList", datasetname=dataset)["BEAAPI"]["Results"]
    raw = result.get("Parameter", []) if isinstance(result, dict) else []
    if isinstance(raw, dict):
        raw = [raw]
    out = []
    for item in raw:
        if isinstance(item, dict):
            out.append((item.get("ParameterName", "?"), item.get("ParameterDescription", "")))
    return out


#: A parameter a caller might reasonably invent when looking for a vintage, plus
#: one that is obviously nonsense as a control.
INVENTED_PARAMETERS = (
    ("no parameter", ""),
    ("?vintage=2024-09", "?vintage=2024-09"),
    ("?vintage=1970-01", "?vintage=1970-01"),
    ("?asof=2024-09-01", "?asof=2024-09-01"),
    ("?completely_made_up=xyz", "?completely_made_up=xyz"),
)

QCEW_PROBE = "https://data.bls.gov/cew/data/api/2024/1/area/51059.csv"


def check_ignored_parameters(base_url: str = QCEW_PROBE) -> int:
    """Does the server reject an unknown parameter, or silently ignore it?

    This matters more than it sounds. A caller looking for a vintage will *try*
    something, and a server that answers HTTP 200 with the current data hands them
    a confident wrong answer: they believe they hold a 1970 vintage of 2024Q1 and
    they hold today's. An error would have been kinder.
    """
    import hashlib

    import requests

    print("\nDoes QCEW reject an invented vintage parameter, or ignore it?")
    digests = {}
    for label, suffix in INVENTED_PARAMETERS:
        response = requests.get(base_url + suffix, timeout=60)
        digest = hashlib.sha256(response.content).hexdigest()
        digests[label] = digest
        print(
            f"  {label:<26} HTTP {response.status_code}  "
            f"{len(response.content):>8} bytes  sha {digest[:16]}"
        )
    distinct = len(set(digests.values()))
    print(f"\n  distinct responses: {distinct} of {len(INVENTED_PARAMETERS)}")
    if distinct == 1:
        print(
            "  Every invented parameter returns byte-identical CURRENT data, including a\n"
            "  vintage of 1970 for a 2024 quarter. The parameter is ignored, not honoured,\n"
            "  and nothing in the response says so."
        )
    return distinct


def main() -> None:
    datasets = bea(method="GetDataSetList")["BEAAPI"]["Results"]["Dataset"]
    names = [d["DatasetName"] for d in datasets]
    print(f"BEA datasets: {len(names)}\n")

    with_vintage, unreadable = [], []
    for dataset in names:
        try:
            params = parameter_names(dataset)
        except Exception as exc:  # noqa: BLE001 - the point is to report, not to stop
            unreadable.append((dataset, type(exc).__name__))
            print(f"  {dataset:<24} parameter list unreadable ({type(exc).__name__})")
            continue
        hits = [n for n, desc in params if VINTAGE_WORDS.search(n) or VINTAGE_WORDS.search(desc)]
        if hits:
            with_vintage.append((dataset, hits))
        print(f"  {dataset:<24} {', '.join(n for n, _ in params)[:56]:<56} {hits or ''}")
        time.sleep(0.2)

    checked = len(names) - len(unreadable)
    print(
        f"\ndatasets offering a vintage / as-of / archive parameter: "
        f"{len(with_vintage)} of {checked} readable ({len(unreadable)} unreadable)"
    )
    print(
        "\nEvery `Year` parameter above selects the REFERENCE PERIOD, not the publication\n"
        "vintage. BEA's own note on a Regional response reads: 'Last updated: February 5,\n"
        "2026 -- new statistics for 2024; revised statistics for 2020-2023.' Four prior\n"
        "years were revised, announced in free text, with no way to retrieve what the\n"
        "series said before."
    )


    check_ignored_parameters()


if __name__ == "__main__":
    main()
