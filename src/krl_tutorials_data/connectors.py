"""Adapters that let a tutorial use `krl-data-connectors` without modifying it.

`krl-data-connectors` is a hard dependency of this repository
(``pyproject.toml:36``) and is **upstream, read-only**. Nothing in this package
writes to it, subclasses to override its behaviour, or monkey-patches it. The
adapters here sit on top: they call a connector's public methods and wrap the
result in the release contract this corpus has to meet.

What the connector supplies
    Fetching or parsing, caching, rate limiting, licensing, and the
    source-specific reshaping a publisher's file needs.

What this module adds, because the tutorial contract requires it and the
connector does not provide it
    * **Fail-closed behaviour.** A missing package, a missing file or a failed
      pin raises. There is no synthetic fallback anywhere in this package.
    * **A pinned vintage.** Bulk publishers overwrite their files in place. A
      notebook that says "Zillow ZHVI" without saying *which* download is not
      reproducible, so a vintage label is required, never inferred.
    * **A content hash of the bytes actually read**, carried in a
      :class:`~krl_tutorials_data.provenance.DataProvenance` record alongside
      the publisher, the terms URL and the retrieval date.
    * **A typed error hierarchy** the notebooks already handle.

This is the layer that was actually missing for the bulk sources. The
connectors for Zillow Research, Eviction Lab, HUD CHAS and HUD Fair Market
Rents already exist upstream; what a tutorial could not do was state which
download it used and prove the file had not changed underneath it.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import hashlib
import importlib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Mapping

import pandas as pd

from .provenance import DataMode, DataProvenance
from .sources import DataAccessError

__all__ = [
    "ConnectorUnavailableError",
    "ConnectorContractError",
    "BulkFilePinError",
    "BulkFileSource",
    "CONNECTOR_DISTRIBUTION",
    "connectors_available",
    "load_connector",
    "verify_bulk_file",
    "frame_from_bulk_file",
]

#: The upstream distribution. Named once so error messages stay accurate.
CONNECTOR_DISTRIBUTION = "krl-data-connectors"
CONNECTOR_PACKAGE = "krl_data_connectors"


class ConnectorUnavailableError(DataAccessError):
    """`krl-data-connectors` (or the requested connector) could not be imported."""


class ConnectorContractError(DataAccessError):
    """A connector returned something the tutorial contract cannot accept."""


class BulkFilePinError(DataAccessError):
    """A bulk file is missing, empty, or does not match its pinned digest."""


def connectors_available() -> bool:
    """Whether the upstream package can be imported in this environment."""
    try:
        importlib.import_module(CONNECTOR_PACKAGE)
    except ImportError:
        return False
    return True


def load_connector(module_path: str, class_name: str) -> type:
    """Import a connector class by name, or raise with installation guidance.

    The import is deliberately lazy and by string. A top-level import would make
    every notebook in this corpus fail to parse in an environment without the
    upstream package, including the Census-only notebooks that do not need it.

    ``module_path`` is relative to the upstream package, e.g.
    ``"professional.housing.zillow_research"``.
    """
    full = f"{CONNECTOR_PACKAGE}.{module_path}"
    try:
        module = importlib.import_module(full)
    except ImportError as exc:
        raise ConnectorUnavailableError(
            f"Could not import {full}. This tutorial needs the "
            f"{CONNECTOR_DISTRIBUTION} package, which is a declared dependency of "
            f"this repository (pyproject.toml). Install it, then re-run. This "
            f"tutorial uses real data only and has no synthetic fallback, so it "
            f"stops here rather than fabricating a result."
        ) from exc
    try:
        return getattr(module, class_name)
    except AttributeError as exc:
        raise ConnectorUnavailableError(
            f"{full} does not define {class_name}. The upstream package is "
            f"read-only here; do not patch it - check the name against the "
            f"installed version."
        ) from exc


@dataclass(frozen=True)
class BulkFileSource:
    """A pinned local copy of a bulk publisher's file.

    Bulk publishers overwrite their downloads in place, so "the Zillow ZHVI
    file" is not an identifier. This records which download was used and lets a
    later reader prove they have the same bytes.

    Attributes
    ----------
    path:
        Where the file sits on this machine. Not part of the identity of the
        data; recorded so a failure message can name it.
    publisher / dataset:
        Who published it and which product it is, in their words.
    vintage:
        The publisher's own version label for this download (a release date, a
        quarter, a file date). **Required.** There is no "latest".
    retrieved_on:
        The date the file was downloaded, which for a rolling publisher is the
        only thing that fixes the vintage.
    sha256:
        Optional pin. When set, the file's digest must match or the load fails.
        Leave unset on first use, then paste the digest the loader reports.
    terms_url:
        Where the publisher's terms of use live. Bulk sources generally carry
        attribution or redistribution conditions that an API does not.
    notes:
        Anything a reader needs in order to interpret the file.
    """

    path: Path
    publisher: str
    dataset: str
    vintage: str
    retrieved_on: date
    sha256: str | None = None
    terms_url: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not str(self.vintage).strip():
            raise BulkFilePinError(
                "A bulk source requires an explicit vintage label. Bulk publishers "
                "overwrite files in place, so a notebook without one cannot be "
                "reproduced."
            )
        if self.sha256 is not None:
            digest = str(self.sha256).strip().lower()
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise BulkFilePinError(
                    f"sha256 pin must be 64 hex characters; got {self.sha256!r}."
                )
            object.__setattr__(self, "sha256", digest)
        object.__setattr__(self, "path", Path(self.path))


def _digest(path: Path) -> tuple[str, int]:
    """SHA-256 and byte count, streamed so a multi-gigabyte file is not loaded."""
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def verify_bulk_file(source: BulkFileSource) -> tuple[str, int]:
    """Check the file exists, is non-empty, and matches its pin. Return digest and size.

    When ``source.sha256`` is unset the digest is computed and returned so the
    analyst can paste it into the pin. That is the intended first-use flow: run
    once unpinned, record the digest, pin it, and every later run proves the
    bytes are identical.
    """
    path = source.path
    if not path.exists():
        raise BulkFilePinError(
            f"{source.dataset} file not found at {path}. {source.publisher} "
            f"publishes this as a download rather than an API, so the file has to "
            f"be placed on disk before this notebook can run"
            + (f" - terms at {source.terms_url}" if source.terms_url else "")
            + f". Expected vintage: {source.vintage}."
        )
    if path.is_dir():
        raise BulkFilePinError(f"{path} is a directory; a single file was expected.")
    digest, size = _digest(path)
    if size == 0:
        raise BulkFilePinError(f"{path} is empty; a truncated download is not data.")
    if source.sha256 is not None and digest != source.sha256:
        raise BulkFilePinError(
            f"{source.dataset} at {path} does not match its pinned digest.\n"
            f"  pinned : {source.sha256}\n"
            f"  actual : {digest}\n"
            f"The publisher overwrites downloads in place, so this usually means "
            f"the file was re-downloaded at a different vintage than "
            f"{source.vintage!r}. Do not update the pin to make this pass without "
            f"also updating the vintage and re-checking every number derived from it."
        )
    return digest, size


def frame_from_bulk_file(
    source: BulkFileSource,
    loader: Callable[[Path], pd.DataFrame],
    *,
    expected_columns: Mapping[str, str] | None = None,
    mode: DataMode = DataMode.EMPIRICAL,
) -> tuple[pd.DataFrame, DataProvenance]:
    """Verify the pin, load through ``loader``, and return the frame with provenance.

    ``loader`` is normally a bound method of an upstream connector, e.g.
    ``ZillowConnector().load_zhvi_data``. It is called with the verified path and
    is otherwise untouched - the connector does the parsing, this function does
    the pinning and the record-keeping.

    ``expected_columns`` maps column name to the meaning the notebook relies on.
    Columns are checked for presence (a publisher silently renaming a column is a
    normal bulk-file event) and the mapping is carried into provenance so a
    reader can see what each column was taken to mean.
    """
    digest, size = verify_bulk_file(source)

    try:
        frame = loader(source.path)
    except Exception as exc:  # noqa: BLE001 - re-raised as a typed error below
        raise ConnectorContractError(
            f"The connector failed to load {source.path}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if not isinstance(frame, pd.DataFrame):
        raise ConnectorContractError(
            f"The connector returned {type(frame).__name__}, not a DataFrame."
        )
    if frame.empty:
        raise ConnectorContractError(
            f"The connector returned an empty frame from {source.path}. An empty "
            f"result is a failure here, not a finding."
        )
    if expected_columns:
        missing = [c for c in expected_columns if c not in frame.columns]
        if missing:
            raise ConnectorContractError(
                f"{source.dataset} is missing expected column(s) {missing}. Bulk "
                f"publishers rename columns between vintages; check the file at "
                f"vintage {source.vintage!r} before adjusting the analysis."
            )

    notes = [
        f"Bulk download, not an API. Publisher: {source.publisher}.",
        f"Vintage {source.vintage}, retrieved {source.retrieved_on.isoformat()}.",
        f"File size {size:,} bytes; SHA-256 of the bytes read is recorded above.",
        (
            "Digest was pinned in the notebook and matched."
            if source.sha256
            else "No digest was pinned for this run; pin the recorded hash to make "
            "later runs prove they read the same bytes."
        ),
        "Parsed by krl-data-connectors, which this package treats as read-only "
        "upstream and does not modify.",
    ]
    if source.terms_url:
        notes.append(f"Publisher terms: {source.terms_url}")
    notes.extend(source.notes)

    #: Repo-relative when the file lives inside the repository, absolute only when
    #: it does not. An absolute path names the machine that ran the notebook --
    #: the committed Zillow record carried a sandbox path under `/sessions/...`,
    #: which tells a later reader nothing and does not exist for them.
    _path = Path(source.path).resolve()
    _root = next((d for d in Path(__file__).resolve().parents if (d / "pyproject.toml").is_file()),
                 Path(__file__).resolve().parent.parent)
    try:
        _located = _path.relative_to(_root).as_posix()
    except ValueError:
        _located = str(_path)

    prov = DataProvenance.build(
        source_name=source.publisher,
        dataset=f"{source.dataset} ({source.vintage})",
        vintage=str(source.vintage),
        endpoint=f"file://{_located}",
        variables=dict(expected_columns or {}),
        payload=digest.encode("ascii"),
        row_count=len(frame),
        column_count=len(frame.columns),
        notes=tuple(notes),
    )
    if mode is not DataMode.EMPIRICAL:
        object.__setattr__(prov, "mode", mode)
    return frame, prov
