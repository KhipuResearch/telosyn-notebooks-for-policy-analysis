"""The Census Bureau's CPS ASEC person replicate-weight file: download, check, parse.

The file, its SAS layout and the usage instructions are three approved downloads from the Bureau
(``CPS_ASEC_ASCII_REPWGT_2024.ZIP``, ``.SAS`` and ``2024_ASEC_Replicate_Weight_Usage_Instructions.docx``). They
are fetched into a **cache outside the repository** (never committed, never in a synced folder), each checked
against a pinned size and SHA-256, and a file whose digest differs is refused and removed.

The record layout is read from the ``.SAS`` file, not from anywhere else: weights are fixed-width fields
(``f9.4``, four implied decimals) and the match keys are ``h_seq`` (``f5.0``) and ``pppos`` (``$char2``). The
usage instructions describe a ten-digit, 1,617-column layout that does not match the file or the SAS code; the
SAS layout reproduces all 161 published column sums, so it is the one used.

Nothing here keeps person rows beyond the arrays a caller reduces to cell totals; ``sources.fetch_cps_asec`` is
the only reader.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import dataclasses
import hashlib
import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import numpy as np

from .provenance import DataProvenance

BASE_URL: Final[str] = "https://www2.census.gov/programs-surveys/cps/datasets/2024/march/"
DAT_MEMBER: Final[str] = "CPS_ASEC_ASCII_REPWGT_2024.DAT"
SYNCED_NAMES: Final[tuple[str, ...]] = ("dropbox", "onedrive", "google drive", "googledrive", "icloud", "mobile documents")
SUM_TOLERANCE: Final[float] = 0.01


@dataclass(frozen=True)
class PinnedFile:
    """The size and SHA-256 an approved file must have."""

    size: int
    sha256: str


#: The three approved files, checked 2026-10-28 (sizes as the owner approved them).
PINNED: dict[str, PinnedFile] = {
    "2024_ASEC_Replicate_Weight_Usage_Instructions.docx": PinnedFile(
        79_166, "a842240dc56e1bf73d9fb0aac1d2578427af2d3e8338e410f79c1e4a730f36a8"),
    "CPS_ASEC_ASCII_REPWGT_2024.SAS": PinnedFile(
        10_093, "3e5d1de838701cdde10352abc382a846ed0086e25c914234850c7a95c2fb4856"),
    "CPS_ASEC_ASCII_REPWGT_2024.ZIP": PinnedFile(
        73_050_090, "ddb5cbf3c0d4ff6c56e3928a3d7fb78f079ba4c7d0e52c709282294fe5e48ac3"),
}


# ---------------------------------------------------------------------------------------- cache
def default_cache_dir() -> Path:
    """``$TELOSYN_CACHE_DIR`` or ``~/.cache/telosyn-notebooks``, then ``/cps_asec_2024``."""
    base = os.environ.get("TELOSYN_CACHE_DIR") or str(Path.home() / ".cache" / "telosyn-notebooks")
    return Path(base) / "cps_asec_2024"


def check_cache_dir(path: Path) -> Path:
    """Refuse a cache inside the repository or under a synced folder; return the path."""
    resolved = Path(path).expanduser()
    absolute = resolved.resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            if absolute == parent or parent in absolute.parents:
                raise ValueError(f"{absolute} is inside the repository; the replicate-weight cache must be outside it.")
            break
    lowered = [part.lower() for part in absolute.parts]
    if any(name in part for part in lowered for name in SYNCED_NAMES):
        raise ValueError(f"{absolute} looks like a synced folder; use a cache that is not synchronised.")
    return resolved


def _digest(path: Path) -> tuple[str, int]:
    h, size = hashlib.sha256(), 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def _record(name: str, size: int, digest: str) -> DataProvenance:
    prov = DataProvenance.build(
        source_name="U.S. Census Bureau",
        dataset=f"CPS ASEC 2024 replicate-weight download: {name}",
        vintage="2024 ASEC (income year 2023)",
        endpoint=BASE_URL + name,
        variables={},
        payload=b"",
        row_count=0,
        column_count=0,
        notes=(f"{size:,} bytes; SHA-256 {digest}. Stored in a cache outside the repository and never committed; "
               "a file whose size or digest differs is refused.",),
    )
    return dataclasses.replace(prov, content_sha256=digest)


def ensure_files(*, cache_dir: Path | None = None, session: Any = None) -> tuple[Path, list[DataProvenance]]:
    """Download any missing approved file into the cache, check every file, and return the folder and records.

    A file already present is checked against its pinned size and digest and not fetched again; one that
    differs raises ``UpstreamError``. A download is written to a ``.part`` file, checked, then renamed; a failed
    check removes it. Records are returned in file-name order.
    """
    from . import sources  # pylint: disable=import-outside-toplevel

    directory = check_cache_dir(cache_dir if cache_dir is not None else default_cache_dir())
    directory.mkdir(parents=True, exist_ok=True)
    http = session or sources.requests
    records: list[DataProvenance] = []
    for name in sorted(PINNED):
        pinned, target = PINNED[name], directory / name
        if not target.exists():
            url = BASE_URL + name
            part = directory / (name + ".part")
            try:
                resp = http.get(url, stream=True, timeout=600, headers={"User-Agent": "telosyn-notebooks/1.0"})
            except sources.requests.RequestException as exc:
                raise sources.UpstreamError(f"Census request for {name} failed: {sources.redact(exc)}") from exc
            sources.reject_bot_challenge(resp, source="the Census Bureau", endpoint=url)
            if resp.status_code != 200:
                raise sources.UpstreamError(f"Census returned HTTP {resp.status_code} for {url}.")
            with part.open("wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    fh.write(chunk)
            part.replace(target)
        digest, size = _digest(target)
        if size != pinned.size or digest != pinned.sha256:
            target.unlink(missing_ok=True)
            raise sources.UpstreamError(
                f"{name}: size {size:,} / digest {digest[:12]}... differs from the pinned size {pinned.size:,} / "
                f"digest {pinned.sha256[:12]}...; the file was removed and nothing is read from it.")
        records.append(_record(name, size, digest))
    return directory, records


# ---------------------------------------------------------------------------------------- layout
@dataclass(frozen=True)
class Field:
    """A fixed-width field: 1-based start column, width and implied decimals."""

    name: str
    start: int
    width: int
    decimals: int = 0


@dataclass(frozen=True)
class Layout:
    """The record layout the SAS file documents."""

    lrecl: int
    weights: tuple[Field, ...]
    h_seq: Field
    pppos: Field
    published_sums: dict[str, float]


def parse_layout(sas_text: str) -> Layout:
    """Read the weights, the two match keys, the record length and the published sums from the SAS text."""
    from . import sources  # pylint: disable=import-outside-toplevel

    lrecl = re.search(r"lrecl\s*=\s*(\d+)", sas_text, re.I)
    weights = [Field(m.group(2).lower(), int(m.group(1)), int(m.group(3)), int(m.group(4)))
               for m in re.finditer(r"@(\d+)\s+(pwwgt\d+)\s+f(\d+)\.(\d+)", sas_text, re.I)]
    h = re.search(r"@(\d+)\s+h_seq\s+f(\d+)\.(\d+)", sas_text, re.I)
    p = re.search(r"@(\d+)\s+pppos\s+\$char(\d+)", sas_text, re.I)
    if not (lrecl and weights and h and p):
        raise sources.SchemaError("the SAS text does not define lrecl, pwwgt fields, h_seq and pppos.")
    sums = {m.group(1).lower(): float(m.group(2)) for m in re.finditer(r"PWWGT(\d+)\s*=\s*([-\d.]+)", sas_text)}
    sums = {f"pwwgt{k}": v for k, v in sums.items()}
    return Layout(int(lrecl.group(1)), tuple(weights), Field("h_seq", int(h.group(1)), int(h.group(2)), int(h.group(3))),
                  Field("pppos", int(p.group(1)), int(p.group(2))), sums)


@dataclass(frozen=True)
class RepWeights:
    """The replicate-weight file as arrays: weights (records x fields), and the two integer match keys."""

    weights: np.ndarray
    h_seq: np.ndarray
    pppos: np.ndarray


def read_replicate_file(zip_path: Path, layout: Layout, *, member: str = DAT_MEMBER) -> RepWeights:
    """Parse the fixed-width DAT inside the zip by the layout, and check every column sum against the published sum."""
    from . import sources  # pylint: disable=import-outside-toplevel

    with zipfile.ZipFile(zip_path) as z:
        raw = z.read(member)
    width = layout.lrecl + 1                                  # the record plus its newline
    if len(raw) % width:
        raise sources.SchemaError(f"the file length {len(raw):,} is not a whole number of {width}-byte records "
                                  f"(record length {layout.lrecl} plus a newline).")
    n = len(raw) // width
    a = np.frombuffer(raw, dtype=np.uint8).reshape(n, width)
    if not (a[:, layout.lrecl] == 10).all():
        raise sources.SchemaError("a record does not end where the layout says (record length mismatch).")
    cols = []
    for f in layout.weights:
        block = np.ascontiguousarray(a[:, f.start - 1: f.start - 1 + f.width])
        cols.append(block.view(f"S{f.width}").reshape(n).astype(np.float64) / (10 ** f.decimals))
    weights = np.column_stack(cols)
    for f, col in zip(layout.weights, weights.T):
        want = layout.published_sums.get(f.name)
        if want is None or abs(float(col.sum()) - want) > SUM_TOLERANCE:
            raise sources.RangeError(f"{f.name}: column sum {col.sum():,.4f} differs from the published sum {want}.")
    h = np.ascontiguousarray(a[:, layout.h_seq.start - 1: layout.h_seq.start - 1 + layout.h_seq.width])
    p = np.ascontiguousarray(a[:, layout.pppos.start - 1: layout.pppos.start - 1 + layout.pppos.width])
    return RepWeights(weights, h.view(f"S{layout.h_seq.width}").reshape(n).astype(int),
                      p.view(f"S{layout.pppos.width}").reshape(n).astype(int))
