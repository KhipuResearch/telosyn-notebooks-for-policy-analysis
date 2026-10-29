"""Known-answer tests for ``krl_tutorials_data.cps_repweights`` and ``fetch_cps_asec(replicates=True)``.

The fixture file follows the Bureau's SAS layout in miniature: weights are nine-character fields with four
implied decimals ("006015748" is 601.5748), then the match keys H_SEQ (five digits) and PPPOS (two characters).
Hand arithmetic: replicate totals by cell are plain sums of the replicate weights of the records in the cell.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from krl_tutorials_data import cps_repweights as rw
from krl_tutorials_data import sources
from krl_tutorials_data.sources import RangeError, SchemaError, UpstreamError

DAT_NAME = "CPS_ASEC_ASCII_REPWGT_2024.DAT"


def sas_text(n_weights: int, sums: list[float]) -> str:
    """A miniature of the Bureau's SAS file: ``n_weights`` weights f9.4, then h_seq f5.0 and pppos $char2."""
    lrecl = 9 * n_weights + 7
    lines = ["/* miniature */", f"data sas.repwgt_2024;", f"   infile link lrecl={lrecl};", "   input"]
    for k in range(n_weights):
        lines.append(f"      @{9 * k + 1}  pwwgt{k} f9.4")
    lines.append(f"      @{9 * n_weights + 1} h_seq f5.0")
    lines.append(f"      @{9 * n_weights + 6} pppos $char2;")
    lines.append("run;")
    lines.append("/* SUM of Weights for Verification:")
    lines.append("")
    for k, v in enumerate(sums):
        lines.append(f"   PWWGT{k} = {v:>16.4f}")
    lines.append("*/")
    return "\n".join(lines) + "\n"


def dat_bytes(rows: list[tuple[list[float], int, int]]) -> bytes:
    out = []
    for weights, h, p in rows:
        out.append("".join(f"{round(w * 1e4):09d}" for w in weights) + f"{h:05d}{p:02d}\n")
    return "".join(out).encode()


def zipped(payload: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(DAT_NAME, payload)
    return buf.getvalue()


ROWS = [([601.5748, 600.0, 602.5, 599.0], 6, 41), ([100.25, 99.0, 101.0, 100.0], 6, 42), ([50.0, 49.5, 50.5, 51.0], 9, 41)]
SUMS = [float(sum(r[0][k] for r in ROWS)) for k in range(4)]


def make_files(tmp_path: Path, rows=ROWS, sums=None) -> tuple[Path, Path]:
    sas = tmp_path / "x.SAS"
    sas.write_text(sas_text(4, sums or [float(sum(r[0][k] for r in rows)) for k in range(4)]), encoding="utf-8")
    zp = tmp_path / "x.ZIP"
    zp.write_bytes(zipped(dat_bytes(rows)))
    return sas, zp


# ----------------------------------------------------------------------------------- layout
def test_the_layout_is_read_from_the_sas_text(tmp_path: Path) -> None:
    sas, _ = make_files(tmp_path)
    lay = rw.parse_layout(sas.read_text(encoding="utf-8"))
    assert lay.lrecl == 43
    assert [(w.name, w.start, w.width, w.decimals) for w in lay.weights][:2] == [("pwwgt0", 1, 9, 4), ("pwwgt1", 10, 9, 4)]
    assert len(lay.weights) == 4
    assert (lay.h_seq.start, lay.h_seq.width) == (37, 5) and (lay.pppos.start, lay.pppos.width) == (42, 2)
    assert lay.published_sums["pwwgt0"] == pytest.approx(SUMS[0])


def test_a_layout_missing_a_key_or_weights_is_refused() -> None:
    with pytest.raises(SchemaError):
        rw.parse_layout("data x; infile link lrecl=10; input @1 pwwgt0 f9.4; run;")
    with pytest.raises(SchemaError):
        rw.parse_layout("nothing here")


# ----------------------------------------------------------------------------------- reading
def test_the_dat_is_read_with_implied_decimals_and_the_published_sums_check(tmp_path: Path) -> None:
    sas, zp = make_files(tmp_path)
    lay = rw.parse_layout(sas.read_text(encoding="utf-8"))
    r = rw.read_replicate_file(zp, lay, member=DAT_NAME)
    assert r.weights.shape == (3, 4)
    assert r.weights[0, 0] == pytest.approx(601.5748)
    assert r.h_seq.tolist() == [6, 6, 9] and r.pppos.tolist() == [41, 42, 41]
    assert r.weights.sum(axis=0) == pytest.approx(SUMS, abs=1e-6)


def test_wrong_sums_or_a_ragged_file_stop_the_read(tmp_path: Path) -> None:
    sas, zp = make_files(tmp_path, sums=[1.0, 2.0, 3.0, 4.0])
    with pytest.raises(RangeError, match="published sum"):
        rw.read_replicate_file(zp, rw.parse_layout(sas.read_text(encoding="utf-8")), member=DAT_NAME)
    sas, _ = make_files(tmp_path)
    ragged = tmp_path / "r.ZIP"
    ragged.write_bytes(zipped(dat_bytes(ROWS) + b"short\n"))
    with pytest.raises(SchemaError, match="record length"):
        rw.read_replicate_file(ragged, rw.parse_layout(sas.read_text(encoding="utf-8")), member=DAT_NAME)


# ----------------------------------------------------------------------------------- download and cache
class _Resp:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.status_code, self._body, self.headers = status, body, {}
        self.content = body

    def iter_content(self, chunk_size: int = 1 << 20):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]


class _Session:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files, self.calls = files, []

    def get(self, url: str, **kw: Any) -> _Resp:
        self.calls.append(url)
        name = url.rsplit("/", 1)[-1]
        return _Resp(self.files[name]) if name in self.files else _Resp(b"", 404)


@pytest.fixture
def pinned(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    sas, zp = make_files(tmp_path / "src") if (tmp_path / "src").mkdir() is None else (None, None)
    files = {"CPS_ASEC_ASCII_REPWGT_2024.SAS": sas.read_bytes(), "CPS_ASEC_ASCII_REPWGT_2024.ZIP": zp.read_bytes(),
             "2024_ASEC_Replicate_Weight_Usage_Instructions.docx": b"docx bytes"}
    table = {n: rw.PinnedFile(len(b), hashlib.sha256(b).hexdigest()) for n, b in files.items()}
    monkeypatch.setattr(rw, "PINNED", table)
    return files


def test_missing_files_are_downloaded_checked_and_recorded(tmp_path: Path, pinned: dict[str, bytes]) -> None:
    cache = tmp_path / "cache"
    session = _Session(pinned)
    directory, records = rw.ensure_files(cache_dir=cache, session=session)
    assert directory == cache and sorted(p.name for p in cache.iterdir()) == sorted(pinned)
    assert [r.endpoint.rsplit("/", 1)[-1] for r in records] == sorted(pinned)
    for r in records:
        assert r.content_sha256 == hashlib.sha256(pinned[r.endpoint.rsplit("/", 1)[-1]]).hexdigest()
        assert r.endpoint.startswith("https://www2.census.gov/programs-surveys/cps/datasets/2024/march/")
    assert len(session.calls) == 3
    again = _Session(pinned)
    rw.ensure_files(cache_dir=cache, session=again)
    assert again.calls == []                                   # present and verified: not fetched again


def test_a_file_whose_digest_differs_is_refused_and_removed(tmp_path: Path, pinned: dict[str, bytes]) -> None:
    bad = dict(pinned)
    bad["CPS_ASEC_ASCII_REPWGT_2024.SAS"] = pinned["CPS_ASEC_ASCII_REPWGT_2024.SAS"] + b" "
    cache = tmp_path / "cache"
    with pytest.raises(UpstreamError, match="digest"):
        rw.ensure_files(cache_dir=cache, session=_Session(bad))
    assert not (cache / "CPS_ASEC_ASCII_REPWGT_2024.SAS").exists()
    assert not list(cache.glob("*.part"))


def test_a_cached_file_that_has_changed_is_refused(tmp_path: Path, pinned: dict[str, bytes]) -> None:
    cache = tmp_path / "cache"
    rw.ensure_files(cache_dir=cache, session=_Session(pinned))
    (cache / "CPS_ASEC_ASCII_REPWGT_2024.SAS").write_bytes(b"tampered")
    with pytest.raises(UpstreamError, match="digest"):
        rw.ensure_files(cache_dir=cache, session=_Session({}))


def test_the_cache_may_not_be_inside_the_repository_or_a_synced_folder(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    with pytest.raises(ValueError, match="repository"):
        rw.check_cache_dir(repo / "data" / "cache")
    for name in ("Dropbox", "OneDrive", "Google Drive", "iCloud Drive", "Mobile Documents"):
        with pytest.raises(ValueError, match="synced"):
            rw.check_cache_dir(tmp_path / name / "telosyn")
    assert rw.check_cache_dir(tmp_path / "plain") == tmp_path / "plain"


def test_only_the_three_approved_files_are_pinned() -> None:
    assert sorted(rw.PINNED) == ["2024_ASEC_Replicate_Weight_Usage_Instructions.docx", "CPS_ASEC_ASCII_REPWGT_2024.SAS",
                                 "CPS_ASEC_ASCII_REPWGT_2024.ZIP"]
    assert rw.PINNED["CPS_ASEC_ASCII_REPWGT_2024.ZIP"].size == 73_050_090
    assert rw.PINNED["CPS_ASEC_ASCII_REPWGT_2024.SAS"].size == 10_093
    assert rw.PINNED["2024_ASEC_Replicate_Weight_Usage_Instructions.docx"].size == 79_166
    assert all(len(v.sha256) == 64 for v in rw.PINNED.values())


# ------------------------------------------------------------------ the run ledger's cache_hit flag
def _ledger_line_for(tmp_path: Path, name: str, call: Any) -> dict[str, Any]:
    """Run ``call`` inside a ledgered fetcher with a real ledger and return the one line it wrote."""
    from krl_tutorials_data import provenance as pv

    plan = tmp_path / f"{name}_plan.md"
    plan.write_text("plan", encoding="utf-8")
    path = tmp_path / f"{name}_runs.jsonl"
    pv.use_ledger(path, plan)
    try:
        @pv.ledgered
        def fetch_replicates() -> tuple[None, Any]:
            call()
            return None, pv.DataProvenance.build(source_name="s", dataset="d", vintage="v", endpoint="e", variables={}, payload=b"x",
                                                  row_count=0, column_count=0)

        fetch_replicates()
    finally:
        pv.stop_ledger()
    (line,) = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    return line


def test_the_ledger_line_says_cache_miss_when_a_file_was_downloaded(tmp_path: Path, pinned: dict[str, bytes]) -> None:
    line = _ledger_line_for(tmp_path, "miss", lambda: rw.ensure_files(cache_dir=tmp_path / "cache", session=_Session(pinned)))
    assert line["cache_hit"] is False


def test_the_ledger_line_says_cache_hit_when_every_file_was_already_present(tmp_path: Path, pinned: dict[str, bytes]) -> None:
    rw.ensure_files(cache_dir=tmp_path / "cache", session=_Session(pinned))
    line = _ledger_line_for(tmp_path, "hit", lambda: rw.ensure_files(cache_dir=tmp_path / "cache", session=_Session({})))
    assert line["cache_hit"] is True


def test_one_missing_file_is_a_cache_miss(tmp_path: Path, pinned: dict[str, bytes]) -> None:
    rw.ensure_files(cache_dir=tmp_path / "cache", session=_Session(pinned))
    (tmp_path / "cache" / "2024_ASEC_Replicate_Weight_Usage_Instructions.docx").unlink()
    line = _ledger_line_for(tmp_path, "part", lambda: rw.ensure_files(cache_dir=tmp_path / "cache", session=_Session(pinned)))
    assert line["cache_hit"] is False
