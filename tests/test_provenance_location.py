"""Where provenance is written, and what its digest is allowed to cover.

Two classes of defect are guarded here, both found while clearing a stray
`provenance/` folder that had appeared at the repository root.

**1. The location depended on the working directory.** Eight notebooks wrote to
`Path.cwd() / "provenance"` and five to a repo-root-relative path. The two
conventions cannot both be satisfied by one working directory: a run from the
repo root put eight notebooks' records in a stray folder at the top of the tree,
and a run from a notebook's own directory would have done the same to the other
five. Sixteen records were written to the wrong place and the committed copies
went stale, with no failure anywhere. Every notebook now anchors to the
repository root found by walking **up** from wherever it runs.

**2. A digest over unstable bytes verifies nothing.** Two of this corpus's
sources return a different response body for two identical requests:

- **Census** does not hold row order, on every endpoint tested (ACS, CBP, BDS). 25 identical requests to CBP 2022 county
  51720 returned **3 distinct byte digests**, one distinct row multiset, and 89
  rows every time.
- **BLS** puts the request's own latency inside the payload as `responseTime`.

Both were recorded on a `response-bytes` basis, so neither could ever match on
re-fetch. `canonical-rows` and `canonical-stable-json` exist for that reason, and
the tests below hold each fetcher to a basis its source can actually satisfy.

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
    VOLATILE_JSON_FIELDS,
    canonical_rows,
    canonical_stable_json,
)

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
NOTEBOOKS: Final = REPO_ROOT / "projects"

#: Fetchers whose source is known not to hold its serialisation stable, and the
#: basis each one must therefore use. Measured, not assumed -- see the module
#: docstring for the observation behind each.
REQUIRED_BASIS: Final[dict[str, str]] = {
    "fetch_acs": "canonical-rows",
    "fetch_acs_wide": "composed-digests",
    "fetch_cbp": "canonical-rows",
    "fetch_bds": "canonical-rows",
    "fetch_bls": "canonical-stable-json",
    "fetch_bea_regional": "canonical-stable-json",
}


# ------------------------------------------------------------------- location

def test_no_provenance_directory_outside_the_notebook_tree() -> None:
    """The exact defect: a stray folder at the repository root."""
    strays = [p for p in REPO_ROOT.glob("*/") if p.name == "provenance"]
    strays += [p for p in REPO_ROOT.glob("provenance")]
    assert not strays, (
        f"provenance written outside projects: {[str(p) for p in strays]}. "
        "A notebook resolved its output directory from the working directory "
        "instead of from the repository root."
    )


def test_every_provenance_directory_sits_beside_a_notebook() -> None:
    for directory in NOTEBOOKS.rglob("provenance"):
        if not directory.is_dir():
            continue
        siblings = list(directory.parent.glob("*.ipynb"))
        assert siblings, (
            f"{directory} holds provenance records but its parent contains no "
            "notebook, so nothing there produced them."
        )


def test_no_notebook_resolves_its_output_from_the_working_directory() -> None:
    """`Path.cwd()` is where you happened to run it, not where the records go."""
    offenders: list[str] = []
    for path in NOTEBOOKS.rglob("*.ipynb"):
        code = "\n".join(
            "".join(c.get("source", []))
            for c in json.loads(path.read_text(encoding="utf-8"))["cells"]
            if c["cell_type"] == "code"
        )
        if re.search(r"^\s*(out_dir|OUT)\s*=\s*Path\.cwd\(\)", code, re.M):
            offenders.append(path.name)
        if re.search(r'^\s*(out_dir|OUT)\s*=\s*Path\(\s*"projects/', code, re.M):
            offenders.append(f"{path.name} (repo-root-relative, breaks when run in place)")
    assert not offenders, (
        f"{offenders} resolve their provenance directory from the working "
        "directory. Anchor to REPO_ROOT, found by walking up."
    )


def test_no_committed_record_names_the_machine_that_wrote_it() -> None:
    """An absolute path is provenance about a sandbox, not about the data."""
    offenders: list[str] = []
    for path in NOTEBOOKS.rglob("provenance/*.json"):
        endpoint = json.loads(path.read_text(encoding="utf-8")).get("endpoint", "")
        if re.search(r"(/sessions/|/Users/|/home/|C:\\\\)", endpoint):
            offenders.append(f"{path.name}: {endpoint[:70]}")
    assert not offenders, f"machine-specific paths in committed provenance: {offenders}"


# ---------------------------------------------------------------- hash basis

@pytest.mark.parametrize("fetcher,basis", sorted(REQUIRED_BASIS.items()))
def test_a_source_with_unstable_bytes_does_not_hash_its_bytes(
    fetcher: str, basis: str
) -> None:
    body = inspect.getsource(getattr(sources, fetcher))
    assert f'hash_basis="{basis}"' in body, (
        f"{fetcher} must record hash_basis={basis!r}: its source does not return "
        "byte-identical responses to identical requests, so a digest over the "
        "response body can never match on re-fetch."
    )
    helper = {"canonical-rows": "canonical_rows(",
              "canonical-stable-json": "canonical_stable_json(",
              #: Composed from per-batch digests that are themselves canonical.
              "composed-digests": 'b"|".join(payloads)'}[basis]
    assert helper in body, (
        f"{fetcher} declares hash_basis={basis!r} but its payload does not go "
        f"through {helper[:-1]}. A record whose declared basis and actual "
        "computation disagree is worse than one that never claimed a basis -- it "
        "was true of fetch_bls and then of fetch_bea_regional, both of which "
        "built their payload from something other than `resp.content` and so "
        "slipped past a check that only looked for that."
    )


def test_canonical_rows_ignores_order_and_not_content() -> None:
    a = json.dumps([["A", "B"], ["1", "2"], ["3", "4"]]).encode()
    b = json.dumps([["A", "B"], ["3", "4"], ["1", "2"]]).encode()
    c = json.dumps([["A", "B"], ["1", "2"], ["3", "5"]]).encode()
    assert canonical_rows(a) == canonical_rows(b), "row order must not change the digest"
    assert canonical_rows(a) != canonical_rows(c), "a changed value must change it"


def test_canonical_rows_keeps_the_header_in_place() -> None:
    """Sorting the header into the rows would silently reorder the columns."""
    out = json.loads(canonical_rows(json.dumps([["Z", "A"], ["1", "2"]]).encode()))
    assert out[0] == ["Z", "A"]


@pytest.mark.parametrize("payload", [b"{}", b"[]", b'{"a": 1}', b'"text"', b"3"])
def test_canonical_rows_refuses_a_body_that_is_not_rows(payload: bytes) -> None:
    """Found by mutation: removing this guard failed no test.

    Silently accepting a non-row body would hash something the caller did not
    mean, under a basis name that says it did.
    """
    with pytest.raises(ValueError, match="canonical-rows"):
        canonical_rows(payload)


def test_canonical_stable_json_strips_at_every_depth() -> None:
    """Top-level only was enough for BLS and not for BEA, whose stamp is nested."""
    a = json.dumps({"R": {"Data": [1], "UTCProductionTime": "2026-09-18T12:00"}}).encode()
    b = json.dumps({"R": {"Data": [1], "UTCProductionTime": "2026-09-18T13:00"}}).encode()
    c = json.dumps({"R": {"Data": [2], "UTCProductionTime": "2026-09-18T12:00"}}).encode()
    assert canonical_stable_json(a) == canonical_stable_json(b)
    assert canonical_stable_json(a) != canonical_stable_json(c)


def test_canonical_stable_json_drops_only_declared_volatile_fields() -> None:
    a = json.dumps({"Results": {"x": 1}, "responseTime": 114, "status": "OK"}).encode()
    b = json.dumps({"Results": {"x": 1}, "responseTime": 987, "status": "OK"}).encode()
    c = json.dumps({"Results": {"x": 2}, "responseTime": 114, "status": "OK"}).encode()
    assert canonical_stable_json(a) == canonical_stable_json(b)
    assert canonical_stable_json(a) != canonical_stable_json(c)
    assert "status" in canonical_stable_json(a).decode(), "only volatile fields go"


def test_the_volatile_field_list_stays_short_and_deliberate() -> None:
    """Each entry removes something from what every digest covers."""
    assert VOLATILE_JSON_FIELDS == frozenset({"responseTime", "UTCProductionTime"}), (
        "VOLATILE_JSON_FIELDS changed. Each entry narrows what a digest proves, "
        "so a new one needs a measurement in the docstring and a line here."
    )


def test_a_batched_fetcher_does_not_record_one_batch_as_the_whole_request() -> None:
    """`request_params` from a loop is the last iteration, not the retrieval."""
    for name in ("fetch_acs_wide", "fetch_bls"):
        body = inspect.getsource(getattr(sources, name))
        assert "assembled_from_batches" in body, (
            f"{name} joins several requests. Recording one batch's parameters "
            "describes a request that returns a fraction of the frame."
        )
