"""Tests for the connector adapters.

These run without `krl-data-connectors` installed, which is the point: the
adapters must fail with a typed, actionable error in that environment rather
than an ImportError at module scope that would break unrelated notebooks.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from krl_tutorials_data.connectors import (
    BulkFilePinError,
    BulkFileSource,
    ConnectorContractError,
    ConnectorUnavailableError,
    connectors_available,
    frame_from_bulk_file,
    load_connector,
    verify_bulk_file,
)
from krl_tutorials_data.provenance import DataMode
from krl_tutorials_data.sources import DataAccessError


@pytest.fixture()
def csv(tmp_path: Path) -> Path:
    p = tmp_path / "zhvi.csv"
    p.write_text("RegionName,StateName,Value\nLoudoun County,VA,612000\n", encoding="utf-8")
    return p


def _source(path: Path, **kw) -> BulkFileSource:
    base = dict(
        path=path, publisher="Zillow Research", dataset="ZHVI",
        vintage="2026-08 release", retrieved_on=date(2026, 9, 13),
    )
    base.update(kw)
    return BulkFileSource(**base)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# Vintage and pin validation
# --------------------------------------------------------------------------

def test_vintage_is_required(csv: Path):
    with pytest.raises(BulkFilePinError, match="explicit vintage"):
        _source(csv, vintage="")


def test_whitespace_vintage_is_not_a_vintage(csv: Path):
    with pytest.raises(BulkFilePinError, match="explicit vintage"):
        _source(csv, vintage="   ")


@pytest.mark.parametrize("bad", ["abc", "z" * 64, "A1" * 31])
def test_malformed_pin_rejected(csv: Path, bad: str):
    with pytest.raises(BulkFilePinError, match="64 hex"):
        _source(csv, sha256=bad)


def test_pin_is_normalised_to_lowercase(csv: Path):
    s = _source(csv, sha256=_sha(csv).upper())
    assert s.sha256 == _sha(csv)


def test_path_is_coerced_to_path(csv: Path):
    assert isinstance(_source(str(csv)).path, Path)


def test_source_is_frozen(csv: Path):
    s = _source(csv)
    with pytest.raises(Exception):
        s.vintage = "other"  # type: ignore[misc]


# --------------------------------------------------------------------------
# File verification
# --------------------------------------------------------------------------

def test_missing_file_names_the_publisher_and_the_vintage(tmp_path: Path):
    s = _source(tmp_path / "absent.csv", terms_url="https://example.org/terms")
    with pytest.raises(BulkFilePinError) as exc:
        verify_bulk_file(s)
    msg = str(exc.value)
    assert "Zillow Research" in msg and "2026-08 release" in msg
    assert "https://example.org/terms" in msg


def test_directory_is_not_a_file(tmp_path: Path):
    with pytest.raises(BulkFilePinError, match="directory"):
        verify_bulk_file(_source(tmp_path))


def test_empty_file_is_a_truncated_download(tmp_path: Path):
    p = tmp_path / "empty.csv"
    p.write_bytes(b"")
    with pytest.raises(BulkFilePinError, match="empty"):
        verify_bulk_file(_source(p))


def test_unpinned_run_returns_the_digest_for_pinning(csv: Path):
    digest, size = verify_bulk_file(_source(csv))
    assert digest == _sha(csv)
    assert size == csv.stat().st_size


def test_matching_pin_passes(csv: Path):
    digest, _ = verify_bulk_file(_source(csv, sha256=_sha(csv)))
    assert digest == _sha(csv)


def test_changed_bytes_fail_the_pin_and_say_why(csv: Path):
    pinned = _sha(csv)
    csv.write_text("RegionName,StateName,Value\nLoudoun County,VA,999999\n", encoding="utf-8")
    with pytest.raises(BulkFilePinError) as exc:
        verify_bulk_file(_source(csv, sha256=pinned))
    msg = str(exc.value)
    assert pinned in msg and _sha(csv) in msg
    assert "Do not update the pin" in msg


def test_digest_streams_rather_than_loading(tmp_path: Path):
    """A large file must hash without being read into memory whole."""
    p = tmp_path / "big.csv"
    with p.open("wb") as fh:
        for _ in range(64):
            fh.write(b"x" * 65536)          # 4 MiB across many chunks
    digest, size = verify_bulk_file(_source(p))
    assert size == 64 * 65536
    assert digest == hashlib.sha256(b"x" * (64 * 65536)).hexdigest()


# --------------------------------------------------------------------------
# Loading through a connector method
# --------------------------------------------------------------------------

def test_frame_and_provenance_from_a_loader(csv: Path):
    frame, prov = frame_from_bulk_file(
        _source(csv, sha256=_sha(csv), terms_url="https://example.org/terms"),
        loader=pd.read_csv,
        expected_columns={"Value": "Zillow Home Value Index, USD"},
    )
    assert len(frame) == 1
    assert prov.content_sha256 == _sha(csv)   # the file's own digest (an earlier version hashed the digest text)
    assert prov.vintage == "2026-08 release"
    assert prov.mode is DataMode.EMPIRICAL
    assert prov.variables == {"Value": "Zillow Home Value Index, USD"}
    rendered = prov.render()
    assert "Zillow Research" in rendered
    assert "read-only upstream" in rendered
    assert "https://example.org/terms" in rendered


def test_unpinned_provenance_says_it_was_unpinned(csv: Path):
    _, prov = frame_from_bulk_file(_source(csv), loader=pd.read_csv)
    assert any("No digest was pinned" in n for n in prov.notes)


def test_pinned_provenance_says_it_matched(csv: Path):
    _, prov = frame_from_bulk_file(_source(csv, sha256=_sha(csv)), loader=pd.read_csv)
    assert any("matched" in n for n in prov.notes)


def test_missing_expected_column_is_a_contract_error(csv: Path):
    with pytest.raises(ConnectorContractError, match="rename columns"):
        frame_from_bulk_file(
            _source(csv), loader=pd.read_csv,
            expected_columns={"NotThere": "a column the publisher dropped"},
        )


def test_empty_frame_is_a_failure_not_a_finding(csv: Path):
    with pytest.raises(ConnectorContractError, match="empty frame"):
        frame_from_bulk_file(_source(csv), loader=lambda p: pd.DataFrame())


def test_non_dataframe_return_rejected(csv: Path):
    with pytest.raises(ConnectorContractError, match="not a DataFrame"):
        frame_from_bulk_file(_source(csv), loader=lambda p: {"rows": 1})


def test_loader_exception_is_wrapped_with_its_type(csv: Path):
    def boom(_path):
        raise ValueError("unparseable header")
    with pytest.raises(ConnectorContractError, match="ValueError: unparseable header"):
        frame_from_bulk_file(_source(csv), loader=boom)


def test_pin_is_checked_before_the_loader_runs(csv: Path):
    """A failed pin must not reach the connector at all."""
    called = []
    def loader(p):
        called.append(p)
        return pd.read_csv(p)
    with pytest.raises(BulkFilePinError):
        frame_from_bulk_file(_source(csv, sha256="0" * 64), loader=loader)
    assert called == []


# --------------------------------------------------------------------------
# Absent upstream package
# --------------------------------------------------------------------------

def test_missing_connector_module_raises_a_typed_actionable_error():
    with pytest.raises(ConnectorUnavailableError) as exc:
        load_connector("professional.housing.definitely_not_a_module", "Nope")
    msg = str(exc.value)
    assert "krl-data-connectors" in msg
    assert "no synthetic fallback" in msg


def test_connector_errors_are_data_access_errors():
    """Notebooks catch DataAccessError; these must be caught by that handler."""
    assert issubclass(ConnectorUnavailableError, DataAccessError)
    assert issubclass(ConnectorContractError, DataAccessError)
    assert issubclass(BulkFilePinError, DataAccessError)


def test_availability_probe_does_not_raise():
    assert connectors_available() in (True, False)


@pytest.mark.skipif(not connectors_available(), reason="upstream package not installed")
def test_zillow_connector_loads_when_upstream_is_present():
    cls = load_connector("professional.housing.zillow_research", "ZillowConnector")
    assert cls.__name__ == "ZillowConnector"


# --------------------------------------------------------------------------
# The upstream package is read-only
# --------------------------------------------------------------------------

REPO = Path(__file__).resolve().parents[1]


def test_this_package_never_writes_to_the_upstream_connector():
    """No source here may patch, subclass-override, or write into the upstream package.

    `krl-data-connectors` is a declared dependency and is maintained elsewhere.
    Adapters call its public methods; they do not reach into it.
    """
    suspicious = ("monkeypatch", "setattr(krl_data_connectors", "krl_data_connectors.__file__")
    hits = []
    for path in sorted((REPO / "src" / "krl_tutorials_data").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in suspicious:
            if token in text:
                hits.append(f"{path.name}: {token}")
    assert not hits, "Adapters must not modify the upstream package: " + "; ".join(hits)


def test_upstream_is_imported_lazily_not_at_module_scope():
    """A top-level import would break every Census-only notebook where it is absent."""
    text = (REPO / "src" / "krl_tutorials_data" / "connectors.py").read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")) and "krl_data_connectors" in stripped:
            pytest.fail(f"module-scope import of the upstream package: {stripped!r}")
