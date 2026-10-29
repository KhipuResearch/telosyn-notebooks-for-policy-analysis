"""Gate -- every notebook with a ``pap/`` folder is bound to its plan, its amendments and its runs (card F12, redesigned).

A notebook with a ``pap/`` folder declares ``krl.pap``: an ordered list of ``{file, sha256, authored_utc, relation}`` for the
plan and each amendment (``commit`` may be given, for readers, and is never relied on). The gate checks, against real history:

1. **Binding by content.** ``git log --reverse -- pap/<file>`` is walked in **HEAD's ancestry only**. The first commit whose
   blob hashes to ``sha256`` must have the author time ``authored_utc``, and no later commit in that ancestry may touch the
   file. A commit that is not reachable from HEAD (a dangling object, another branch) never satisfies the rule. Rebase keeps
   author dates, so this survives a rebase; a commit id does not.
2. **Order.** ``relation`` is ``before_retrieval`` when ``authored_utc`` is not after the earliest retrieval anywhere in the
   notebook's records or run ledger, else ``after_retrieval``; the plan must be ``before_retrieval``.
3. **Records.** Every provenance record holds ``pap_sha256``, ``pap_amendments`` (a prefix of the declared amendments, in
   order) and ``pap_chain_sha256``; amendments it lists were authored no later than its ``retrieved_utc`` and those it omits
   after it.
4. **Runs.** ``provenance/_runs.jsonl`` is the ledger. ``fetch_*`` functions append to it before they raise as well as after
   they succeed (status ok / failed, cache_hit), a notebook calls ``ledger_stop`` before it raises on a stop-rule, and each
   write of a record appends a record line. Each line's chain must be one the declared list can produce, with the same
   in-force rule as a record; each current record is on the ledger; lines are in time order; every committed version of the
   ledger is a byte-prefix of the next; reconstructed lines come first and carry a note.
5. **Limitations** says whether the analysis departed from the plan.

**History is fail-closed.** A shallow or unreadable clone fails the gate; ``KRL_ALLOW_SHALLOW=1`` skips the commit rules with
a warning, and never when ``CI=true``. **The legacy path** (digest only, no ``krl.pap``) is an allowlist of the six
notebooks that predate this gate, C01 to C06; a new notebook cannot opt into it.

Author dates are self-asserted, so order is proven against honest authors only. A plan and its amendments cite their
predecessors by file name and SHA-256, not by commit id, and squash merges stay off for a notebook with a plan.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import pytest

from gate_support import Notebook, load_notebook

LIMITATIONS = re.compile(r"^##\s*Limitations\b.*?(?=^##\s|\Z)", re.M | re.S | re.I)
ENTRY_KEYS = ("file", "sha256", "authored_utc", "relation")
#: The notebooks that predate this gate; the only ones that may omit ``krl.pap``.
LEGACY: frozenset[str] = frozenset({
    "C01_medicaid_expansion_did", "C02_medicare_age65_rdd", "C03_minimum_wage_staggered",
    "C04_ca_minimum_wage_synth", "C05_public_coverage_matching", "C06_medicaid_expansion_iv",
})
STATUSES = ("ok", "failed", "stopped")


class Facts(Protocol):
    """What the gate needs from version control; injected so every rule is testable."""

    def file_history(self, rel: str) -> list[tuple[str, int, str | None]]:
        """``(commit, author_epoch, sha256 of the file at that commit or None)`` for commits in HEAD's ancestry that touch ``rel``, oldest first."""

    def ledger_versions(self, rel: str) -> list[bytes]:
        """The committed contents of ``rel`` in HEAD's ancestry, oldest first."""


class RepoFacts:
    """Real history. Raises ``RuntimeError`` if it is shallow or unreadable."""

    def __init__(self, root: Path) -> None:
        self.root = root
        shallow = self._run("rev-parse", "--is-shallow-repository").decode().strip()
        if shallow != "false":
            raise RuntimeError(f"git history is shallow or unreadable (is-shallow={shallow!r})")

    @classmethod
    def containing(cls, folder: Path) -> "RepoFacts":
        """The repository that holds ``folder``."""
        done = subprocess.run(["git", "-C", str(folder), "rev-parse", "--show-toplevel"], check=False, capture_output=True, text=True)
        if done.returncode != 0:
            raise RuntimeError(f"{folder} is not inside a git repository")
        return cls(Path(done.stdout.strip()))

    def _run(self, *args: str) -> bytes:
        done = subprocess.run(["git", "-C", str(self.root), *args], check=False, capture_output=True)
        if done.returncode != 0:
            raise LookupError(done.stderr.decode(errors="replace").strip())
        return done.stdout

    def file_history(self, rel: str) -> list[tuple[str, int, str | None]]:
        """Commits touching ``rel`` in HEAD's ancestry, oldest first, with their author times and the file's digest there."""
        out = self._run("log", "--reverse", "--format=%H %at", "HEAD", "--", rel).decode().splitlines()
        history = []
        for line in out:
            commit, epoch_ = line.split()
            try:
                digest: str | None = hashlib.sha256(self._run("show", f"{commit}:{rel}")).hexdigest()
            except LookupError:
                digest = None
            history.append((commit, int(epoch_), digest))
        return history

    def ledger_versions(self, rel: str) -> list[bytes]:
        """Each committed version of ``rel`` in HEAD's ancestry, oldest first."""
        commits = self._run("log", "--reverse", "--format=%H", "HEAD", "--", rel).decode().split()
        versions = []
        for commit in commits:
            try:
                versions.append(self._run("show", f"{commit}:{rel}"))
            except LookupError:
                continue
        return versions


class FakeFacts:
    """Fixed history for fixture tests: ``{file name: [(commit, epoch, sha256), ...]}`` and ledger versions."""

    def __init__(self, histories: dict[str, list[tuple[str, int, str | None]]], ledger: list[bytes] | None = None) -> None:
        self.histories, self.ledger = histories, ledger or []

    def file_history(self, rel: str) -> list[tuple[str, int, str | None]]:
        """History of the file named by ``rel``."""
        return self.histories.get(Path(rel).name, [])

    def ledger_versions(self, rel: str) -> list[bytes]:
        """Committed ledger versions."""
        return self.ledger


def epoch(stamp: str) -> int:
    """Epoch of an ISO timestamp (UTC if none given)."""
    parsed = datetime.fromisoformat(stamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


def chain_of(digests: list[str]) -> str:
    """The plan chain (kept in step with ``provenance.pap_chain`` by a test below)."""
    return hashlib.sha256("\n".join(digests).encode("ascii")).hexdigest()


def pap_folder(nb: Notebook) -> Path:
    """The notebook's ``pap/`` folder (may not exist)."""
    return nb.path.parent / "pap"


def in_scope(nb: Notebook) -> bool:
    """Whether the notebook has a ``pap/`` folder with a file in it."""
    folder = pap_folder(nb)
    return folder.is_dir() and any(p.is_file() for p in folder.iterdir())


def _records(folder: Path) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for path in sorted((folder / "provenance").glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for item in doc if isinstance(doc, list) else [doc]:
            if isinstance(item, dict):
                out.append((path.name, item))
    return out


def _ledger(folder: Path) -> tuple[list[dict[str, Any]] | None, bytes]:
    path = folder / "provenance" / "_runs.jsonl"
    if not path.is_file():
        return None, b""
    raw = path.read_bytes()
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()], raw


def check_pap(nb: Notebook, facts: Facts | None, root: Path | None = None) -> list[str]:  # noqa: C901 - one rule per branch, on purpose
    """Return every violation, each stating rule and remedy. ``facts=None`` skips the commit rules (shallow, allowed locally)."""
    name = nb.path.name
    found: list[str] = []

    def fail(rule: str, fix: str) -> None:
        found.append(f"{name}: {rule} -> {fix}")

    folder = nb.path.parent
    files = sorted(p.name for p in pap_folder(nb).iterdir() if p.is_file())
    declared = nb.krl.get("pap")
    ident = nb.identification

    if declared is None:
        if folder.name in LEGACY and ident is not None and len(files) == 1 and isinstance(ident.get("pap"), str):
            target = (folder / ident["pap"]).resolve()
            if target.name != files[0] or not target.is_file():
                fail("legacy plan file named by `identification.pap` is not the one file in pap/", "declare `krl.pap`")
            elif hashlib.sha256(target.read_bytes()).hexdigest() != ident.get("pap_sha256"):
                fail("legacy `identification.pap_sha256` does not match the plan on disk", "restore the plan or declare the departure")
            return found
        fail("has a pap/ folder but no `krl.pap` list (the legacy digest-only path is an allowlist of C01 to C06)",
             "declare [{file, sha256, authored_utc, relation}] in order, the plan first")
        return found
    if not isinstance(declared, list) or not declared:
        fail("`krl.pap` is not a non-empty list", "list the plan first, then each amendment in order")
        return found

    entries: list[dict[str, Any]] = []
    for i, item in enumerate(declared):
        if not isinstance(item, dict) or any(not isinstance(item.get(k), str) or not item[k] for k in ENTRY_KEYS):
            fail(f"krl.pap[{i}] needs non-empty string keys {ENTRY_KEYS}", "complete the entry (`commit` is optional and informational)")
            continue
        entries.append(item)
    if len(entries) != len(declared):
        return found
    listed = [e["file"] for e in entries]
    if sorted(listed) != files or len(set(listed)) != len(listed):
        fail(f"`krl.pap` lists {listed}, but pap/ holds {files}", "list every file in pap/ exactly once, and nothing else")
        return found

    digests: list[str] = []
    authored: list[int] = []
    for i, e in enumerate(entries):
        path = pap_folder(nb) / e["file"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        digests.append(digest)
        try:
            authored.append(epoch(e["authored_utc"]))
        except ValueError:
            fail(f"krl.pap[{i}].authored_utc {e['authored_utc']!r} is not an ISO timestamp", "use the commit's author time in UTC")
            return found
        if digest != e["sha256"]:
            fail(f"krl.pap[{i}] {e['file']}: declared digest {e['sha256'][:12]}... != file {digest[:12]}...",
                 "a committed plan is never edited; add an amendment file instead")
        if e["relation"] not in ("before_retrieval", "after_retrieval"):
            fail(f"krl.pap[{i}].relation is {e['relation']!r}", "use before_retrieval or after_retrieval")
    if entries[0]["relation"] != "before_retrieval":
        fail("the plan (krl.pap[0]) is not before_retrieval", "the plan must precede the first retrieval")
    if authored != sorted(authored):
        fail("krl.pap authored times are not in order", "list the plan, then amendments in the order authored")

    records = _records(folder)
    ledger, ledger_raw = _ledger(folder)
    if not records:
        fail("no provenance record beside the notebook", "write a record for every retrieval")
    stamps = [epoch(r["retrieved_utc"]) for _, r in records if "retrieved_utc" in r]
    stamps += [epoch(line["retrieved_utc"]) for line in (ledger or []) if "retrieved_utc" in line]
    first = min(stamps) if stamps else None

    if facts is not None:
        rel_root = (root or _root(nb)).resolve()
        for i, e in enumerate(entries):
            rel = str((pap_folder(nb) / e["file"]).resolve().relative_to(rel_root))
            history = facts.file_history(rel)
            at = next((k for k, (_, _, sha) in enumerate(history) if sha == e["sha256"]), None)
            if at is None:
                fail(f"krl.pap[{i}] {e['file']}: no commit in HEAD's ancestry holds this exact file", "commit the file (before relying on it) on this branch")
                continue
            if history[at][1] != authored[i]:
                fail(f"krl.pap[{i}] {e['file']}: the first commit holding this file was authored at {history[at][1]}, not {authored[i]} ({e['authored_utc']})",
                     "set authored_utc to that commit's author time in UTC")
            if at != len(history) - 1:
                fail(f"krl.pap[{i}] {e['file']}: {len(history) - 1 - at} later commit(s) in HEAD's ancestry modify it", "a committed plan is never edited")
            if first is not None:
                computed = "before_retrieval" if authored[i] <= first else "after_retrieval"
                if computed != e["relation"]:
                    fail(f"krl.pap[{i}].relation is {e['relation']} but it was authored {'not after' if computed == 'before_retrieval' else 'after'} the earliest retrieval",
                         f"set it to {computed}")

    def in_force(label: str, chain: str | None, when: int | None) -> None:
        """A record or ledger line names a chain; check it is a prefix and that the amendments in force match its time."""
        if chain is None:
            fail(f"{label} carries no plan chain", "write it with DataProvenance.with_pap_chain / use_ledger")
            return
        k = next((n for n in range(1, len(digests) + 1) if chain_of(digests[:n]) == chain), None)
        if k is None:
            fail(f"{label} carries a chain the declared plans cannot produce", "re-run under the declared plans or declare the amendment")
            return
        if facts is not None and when is not None:
            if authored[0] > when:
                fail(f"{label} was retrieved before the plan was authored", "the plan must come first")
            for j in range(1, len(authored)):
                if j < k and authored[j] > when:
                    fail(f"{label} lists amendment {entries[j]['file']}, authored after the retrieval", "a record cannot cite a later amendment")
                if j >= k and authored[j] <= when:
                    fail(f"{label} omits amendment {entries[j]['file']}, authored before the retrieval", "list every amendment in force")

    for rec_name, r in records:
        for key in ("pap_sha256", "pap_amendments", "pap_chain_sha256"):
            if key not in r:
                fail(f"record {rec_name} has no `{key}`", "bind it with DataProvenance.with_pap_chain before writing")
        if "pap_chain_sha256" not in r or "pap_amendments" not in r:
            continue
        if r.get("pap_sha256") != digests[0]:
            fail(f"record {rec_name}: pap_sha256 {str(r.get('pap_sha256'))[:12]}... is not the plan's digest", "re-bind the record")
        held = r["pap_amendments"]
        want = [{"file": e["file"], "sha256": e["sha256"]} for e in entries[1:1 + len(held)]]
        if held != want:
            fail(f"record {rec_name}: pap_amendments is not a prefix of the declared amendments, in order", "re-bind the record")
            continue
        if r["pap_chain_sha256"] != chain_of(digests[:1 + len(held)]):
            fail(f"record {rec_name}: pap_chain_sha256 does not match its plan and amendments", "recompute it with pap_chain")
        in_force(f"record {rec_name}", r["pap_chain_sha256"], epoch(r["retrieved_utc"]) if "retrieved_utc" in r else None)

    if ledger is None:
        fail("no run ledger provenance/_runs.jsonl", "call provenance.use_ledger in the configuration cell; commit the ledger with the records")
    else:
        last = None
        seen_live = False
        for n, line in enumerate(ledger, start=1):
            label = f"ledger line {n}"
            kind = line.get("kind", "record")
            status = line.get("status", "ok")
            if "retrieved_utc" not in line:
                fail(f"{label} has no retrieved_utc", "write it with the ledger functions")
                continue
            if status not in STATUSES:
                fail(f"{label} has status {status!r}", f"use one of {STATUSES}")
            if kind == "fetch" and "cache_hit" not in line:
                fail(f"{label} (a fetch) has no cache_hit", "write it with provenance.ledgered")
            stamp = epoch(line["retrieved_utc"])
            order_key = epoch(line["logged_utc"]) if "logged_utc" in line else stamp      # live lines are ordered by when they were appended
            if last is not None and order_key < last:
                fail(f"{label} is out of time order", "the ledger is append-only")
            last = order_key
            if line.get("reconstructed"):
                if not str(line.get("note", "")).strip():
                    fail(f"{label} is reconstructed but has no note giving the source of its timestamp", "add a `note`")
                if seen_live:
                    fail(f"{label} is reconstructed but follows a contemporaneous line", "reconstructed lines come first")
            else:
                seen_live = True
            in_force(label, line.get("pap_chain_sha256"), stamp)
        seen = {(line.get("record"), line.get("retrieved_utc"), line.get("content_sha256")) for line in ledger if line.get("kind", "record") == "record"}
        for rec_name, r in records:
            if (rec_name, r.get("retrieved_utc"), r.get("content_sha256")) not in seen:
                fail(f"record {rec_name} (retrieved {r.get('retrieved_utc')}) is not a record line on the run ledger", "write records only through DataProvenance.write")
        if facts is not None:
            rel = str((folder / "provenance" / "_runs.jsonl").resolve().relative_to((root or _root(nb)).resolve()))
            versions = facts.ledger_versions(rel) + [ledger_raw]
            for a, b in zip(versions, versions[1:]):
                if not b.startswith(a):
                    fail("the ledger is not append-only: a committed version is not a byte-prefix of the next", "never rewrite or reorder the ledger; append")
                    break

    limits = LIMITATIONS.search(nb.markdown_source)
    if limits is None or not re.search(r"\bplan\b", limits.group(0), re.I) or not re.search(r"depart", limits.group(0), re.I):
        fail("Limitations does not say whether the analysis departed from the plan", "state the departure, or that there was none")
    return found


def _root(nb: Notebook) -> Path:
    done = subprocess.run(["git", "-C", str(nb.path.parent), "rev-parse", "--show-toplevel"], check=False, capture_output=True, text=True)
    return Path(done.stdout.strip() or ".").resolve()


def facts_or_problem(folder: Path, env: dict[str, str] | None = None) -> tuple[Facts | None, str | None]:
    """Real facts, or ``(None, None)`` when shallow history is explicitly allowed outside CI, else a problem message."""
    env = os.environ if env is None else env
    try:
        return RepoFacts.containing(folder), None
    except RuntimeError as exc:
        if env.get("KRL_ALLOW_SHALLOW") == "1" and env.get("CI", "").lower() != "true":
            warnings.warn(f"commit rules skipped ({exc}); KRL_ALLOW_SHALLOW=1", stacklevel=2)
            return None, None
        return None, f"git history is unavailable ({exc}); the gate fails closed. Fetch full history (CI uses fetch-depth 0); set KRL_ALLOW_SHALLOW=1 only locally"


# ---------------------------------------------------------------------------------- the corpus
def test_every_notebook_with_a_pap_folder_is_bound_to_its_plan(notebook: Notebook) -> None:
    """The corpus: every notebook that has a plan satisfies the rules above."""
    if not in_scope(notebook):
        return
    facts, problem = facts_or_problem(notebook.path.parent)
    assert problem is None, f"{notebook.path.name}: {problem}"
    problems = check_pap(notebook, facts)
    assert not problems, "\n  ".join(problems)


# ------------------------------------------------------------------------ planted violations
PLAN, A1, A2 = "plan one", "amendment one", "amendment two"
T0, T1, T2 = "2026-10-01T00:00:00+00:00", "2026-10-02T00:00:00+00:00", "2026-10-03T00:00:00+00:00"
R1, R2 = "2026-10-02T12:00:00+00:00", "2026-10-04T00:00:00+00:00"   # retrievals: after A1, after A2
C = {"plan": "a" * 40, "a1": "b" * 40, "a2": "c" * 40}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def build(tmp_path: Path, **tweak: Any) -> tuple[Notebook, FakeFacts]:
    """A compliant folder: plan at T0, amendment 1 at T1 (before retrieval R1), amendment 2 at T2 (after R1, before R2)."""
    folder = tmp_path / "X1_demo"
    (folder / "pap").mkdir(parents=True)
    (folder / "provenance").mkdir()
    files = {"X1_plan.md": PLAN, "X1_plan_amendment_1.md": A1, "X1_plan_amendment_2.md": A2}
    for name_, text in files.items():
        (folder / "pap" / name_).write_text(text, encoding="utf-8")
    d = [_sha(PLAN), _sha(A1), _sha(A2)]
    entries = [
        {"file": "X1_plan.md", "sha256": d[0], "authored_utc": T0, "relation": "before_retrieval"},
        {"file": "X1_plan_amendment_1.md", "sha256": d[1], "authored_utc": T1, "relation": "before_retrieval"},
        {"file": "X1_plan_amendment_2.md", "sha256": d[2], "authored_utc": T2, "relation": "after_retrieval"},
    ]
    rec1 = {"retrieved_utc": R1, "content_sha256": "1" * 64, "pap_sha256": d[0],
            "pap_amendments": [{"file": "X1_plan_amendment_1.md", "sha256": d[1]}], "pap_chain_sha256": chain_of(d[:2])}
    rec2 = {"retrieved_utc": R2, "content_sha256": "2" * 64, "pap_sha256": d[0],
            "pap_amendments": [{"file": "X1_plan_amendment_1.md", "sha256": d[1]}, {"file": "X1_plan_amendment_2.md", "sha256": d[2]}],
            "pap_chain_sha256": chain_of(d)}
    ledger = [
        {"kind": "fetch", "fetcher": "fetch_x", "status": "ok", "cache_hit": False, "retrieved_utc": R1, "content_sha256": "1" * 64, "pap_chain_sha256": chain_of(d[:2])},
        {"kind": "record", "status": "ok", "record": "stop_rule_run.json", "retrieved_utc": R1, "content_sha256": "1" * 64, "pap_chain_sha256": chain_of(d[:2])},
        {"kind": "stop", "status": "stopped", "reason": "bound exceeded", "retrieved_utc": R1, "pap_chain_sha256": chain_of(d[:2])},
        {"kind": "fetch", "fetcher": "fetch_x", "status": "ok", "cache_hit": True, "retrieved_utc": R2, "content_sha256": "2" * 64, "pap_chain_sha256": chain_of(d)},
        {"kind": "record", "status": "ok", "record": "final.json", "retrieved_utc": R2, "content_sha256": "2" * 64, "pap_chain_sha256": chain_of(d)},
    ]
    records = {"stop_rule_run.json": rec1, "final.json": rec2}
    hist = {"X1_plan.md": [(C["plan"], epoch(T0), d[0])], "X1_plan_amendment_1.md": [(C["a1"], epoch(T1), d[1])],
            "X1_plan_amendment_2.md": [(C["a2"], epoch(T2), d[2])]}
    nbdoc: dict[str, Any] = {
        "cells": [{"cell_type": "markdown", "metadata": {}, "source": ["## Limitations\n", "The pre-analysis plan was amended twice; the analysis departed from it as stated."]}],
        "metadata": {"krl": {"pap": entries}}, "nbformat": 4, "nbformat_minor": 5}
    versions: list[bytes] = []
    tweak.get("mutate", lambda *a: None)(nbdoc, records, ledger, hist, folder, versions)
    for rec_name, doc in records.items():
        (folder / "provenance" / rec_name).write_text(json.dumps(doc), encoding="utf-8")
    raw = "".join(json.dumps(x) + "\n" for x in ledger).encode()
    if ledger:
        (folder / "provenance" / "_runs.jsonl").write_bytes(raw)
    (folder / "X1_demo.ipynb").write_text(json.dumps(nbdoc), encoding="utf-8")
    return load_notebook(folder / "X1_demo.ipynb"), FakeFacts(hist, versions)


def _problems(tmp_path: Path, mutate: Any) -> str:
    nb, facts = build(tmp_path, mutate=mutate)
    return "\n".join(check_pap(nb, facts, tmp_path))


def test_the_compliant_fixture_passes(tmp_path: Path) -> None:
    nb, facts = build(tmp_path)
    assert check_pap(nb, facts, tmp_path) == []


def test_the_chain_function_matches_the_library() -> None:
    from krl_tutorials_data.provenance import pap_chain
    assert pap_chain(["x", "y"]) == chain_of(["x", "y"])


def _rewrite_ledger_line(ledger: list, i: int, **kw: Any) -> None:
    ledger[i].update(kw)


PLANTED = [
    ("no krl.pap", lambda nb, r, l, h, d, v: nb["metadata"]["krl"].pop("pap"), "no `krl.pap` list"),
    ("unlisted file", lambda nb, r, l, h, d, v: (d / "pap" / "X1_plan_amendment_3.md").write_text("late", encoding="utf-8"), "pap/ holds"),
    ("plan edited", lambda nb, r, l, h, d, v: (d / "pap" / "X1_plan.md").write_text("plan edited", encoding="utf-8"), "declared digest"),
    ("authored_utc wrong", lambda nb, r, l, h, d, v: nb["metadata"]["krl"]["pap"][1].update(authored_utc=T2), "was authored at"),
    ("never committed", lambda nb, r, l, h, d, v: h.update({"X1_plan_amendment_1.md": []}), "no commit in HEAD's ancestry holds this exact file"),
    ("only another content committed", lambda nb, r, l, h, d, v: h.update({"X1_plan_amendment_1.md": [(C["a1"], epoch(T1), "0" * 64)]}), "no commit in HEAD's ancestry holds"),
    ("modified after", lambda nb, r, l, h, d, v: h["X1_plan.md"].append(("d" * 40, epoch(T2), "9" * 64)), "later commit(s) in HEAD's ancestry modify it"),
    ("authored_utc not ISO", lambda nb, r, l, h, d, v: nb["metadata"]["krl"]["pap"][0].update(authored_utc="yesterday"), "not an ISO timestamp"),
    ("entry missing a key", lambda nb, r, l, h, d, v: nb["metadata"]["krl"]["pap"][0].pop("authored_utc"), "needs non-empty string keys"),
    ("times out of order", lambda nb, r, l, h, d, v: nb["metadata"]["krl"]["pap"][0].update(authored_utc=T2), "not in order"),
    ("plan marked after", lambda nb, r, l, h, d, v: nb["metadata"]["krl"]["pap"][0].update(relation="after_retrieval"), "not before_retrieval"),
    ("relation wrong", lambda nb, r, l, h, d, v: nb["metadata"]["krl"]["pap"][2].update(relation="before_retrieval"), "set it to after_retrieval"),
    ("record without the chain", lambda nb, r, l, h, d, v: r["final.json"].pop("pap_chain_sha256"), "no `pap_chain_sha256`"),
    ("record without amendments field", lambda nb, r, l, h, d, v: r["final.json"].pop("pap_amendments"), "no `pap_amendments`"),
    ("record bound to another plan", lambda nb, r, l, h, d, v: r["final.json"].update(pap_sha256="9" * 64), "is not the plan's digest"),
    ("record chain wrong", lambda nb, r, l, h, d, v: r["final.json"].update(pap_chain_sha256="8" * 64), "does not match its plan and amendments"),
    ("record amendments out of order", lambda nb, r, l, h, d, v: r["final.json"].update(pap_amendments=r["final.json"]["pap_amendments"][::-1]), "not a prefix"),
    ("record cites a later amendment", lambda nb, r, l, h, d, v: r["stop_rule_run.json"].update(
        pap_amendments=r["final.json"]["pap_amendments"], pap_chain_sha256=r["final.json"]["pap_chain_sha256"]), "authored after the retrieval"),
    ("record omits an amendment in force", lambda nb, r, l, h, d, v: r["final.json"].update(
        pap_amendments=r["final.json"]["pap_amendments"][:1], pap_chain_sha256=r["stop_rule_run.json"]["pap_chain_sha256"]), "omits amendment"),
    ("no ledger", lambda nb, r, l, h, d, v: l.clear(), "no run ledger"),
    ("record not on the ledger", lambda nb, r, l, h, d, v: l.pop(), "not a record line on the run ledger"),
    ("ledger out of order", lambda nb, r, l, h, d, v: l.reverse(), "out of time order"),
    ("ledger chain unknown", lambda nb, r, l, h, d, v: _rewrite_ledger_line(l, 0, pap_chain_sha256="7" * 64), "chain the declared plans cannot produce"),
    ("ledger line without a chain", lambda nb, r, l, h, d, v: l[0].pop("pap_chain_sha256"), "carries no plan chain"),
    ("ledger line cites a later amendment", lambda nb, r, l, h, d, v: _rewrite_ledger_line(l, 0, pap_chain_sha256=r["final.json"]["pap_chain_sha256"]), "authored after the retrieval"),
    ("ledger line omits an amendment in force", lambda nb, r, l, h, d, v: _rewrite_ledger_line(l, 3, pap_chain_sha256=r["stop_rule_run.json"]["pap_chain_sha256"]), "omits amendment"),
    ("bad status", lambda nb, r, l, h, d, v: _rewrite_ledger_line(l, 0, status="maybe"), "has status 'maybe'"),
    ("fetch line without cache_hit", lambda nb, r, l, h, d, v: l[0].pop("cache_hit"), "has no cache_hit"),
    ("reconstructed without a note", lambda nb, r, l, h, d, v: _rewrite_ledger_line(l, 0, reconstructed=True), "no note giving the source of its timestamp"),
    ("reconstructed after a contemporaneous line", lambda nb, r, l, h, d, v: _rewrite_ledger_line(l, 3, reconstructed=True, note="back-filled"), "follows a contemporaneous line"),
    ("ledger rewritten between commits", lambda nb, r, l, h, d, v: v.append(b'{"kind": "fetch", "fetcher": "old"}\n'), "not append-only"),
    ("limitations silent", lambda nb, r, l, h, d, v: nb["cells"][0].update(source=["## Limitations\n", "Nothing to say."]), "departed from the plan"),
]


@pytest.mark.parametrize(("label", "mutate", "expect"), PLANTED, ids=[p[0] for p in PLANTED])
def test_each_planted_violation_fails_and_names_its_rule(tmp_path: Path, label: str, mutate: Any, expect: str) -> None:
    text = _problems(tmp_path, mutate)
    assert expect in text, f"{label}: expected {expect!r} in\n{text}"


def test_live_lines_are_ordered_by_when_they_were_logged_not_by_the_data_time(tmp_path: Path) -> None:
    """A record line for data fetched a few seconds before the call returned is logged after the fetch line: retrieved_utc may go backwards."""
    def logged(nb: Any, r: Any, l: Any, h: Any, d: Any, v: Any) -> None:
        l[3].update(retrieved_utc="2026-10-04T00:00:01+00:00", logged_utc="2026-10-04T00:00:03+00:00")    # data time after the next line's
        l[4].update(retrieved_utc=R2, logged_utc="2026-10-04T00:00:04+00:00")
        r["final.json"]["retrieved_utc"] = R2
    assert _problems(tmp_path, logged) == ""


def test_a_line_logged_before_its_predecessor_is_out_of_order(tmp_path: Path) -> None:
    def backwards(nb: Any, r: Any, l: Any, h: Any, d: Any, v: Any) -> None:
        l[3].update(logged_utc="2026-10-04T00:00:05+00:00")
        l[4].update(logged_utc="2026-10-04T00:00:02+00:00")
    assert "out of time order" in _problems(tmp_path, backwards)


def test_the_ledger_may_extend_the_committed_versions(tmp_path: Path) -> None:
    def prior(nb: Any, r: Any, l: Any, h: Any, d: Any, v: list) -> None:
        v.append("".join(json.dumps(x) + "\n" for x in l[:2]).encode())   # an earlier commit of the ledger: its first two lines
    assert _problems(tmp_path, prior) == ""


def test_an_unrecorded_early_run_changes_the_relation(tmp_path: Path) -> None:
    """Amendment 2 is after_retrieval only because R1 is on the ledger; without R1, amendment 2 precedes the earliest retrieval."""
    def drop(nb: Any, r: Any, l: Any, h: Any, d: Any, v: Any) -> None:
        r.pop("stop_rule_run.json")
        del l[:3]
    assert "set it to before_retrieval" in _problems(tmp_path, drop)


def test_without_history_the_commit_rules_are_skipped_but_the_file_rules_still_run(tmp_path: Path) -> None:
    nb, _ = build(tmp_path, mutate=lambda nb_, r, l, h, d, v: (d / "pap" / "X1_plan.md").write_text("edited", encoding="utf-8"))
    assert "declared digest" in "\n".join(check_pap(nb, None))
    clean, _ = build(tmp_path / "clean")
    assert check_pap(clean, None) == []


# ------------------------------------------------------------- the legacy allowlist, scope, shallow history
def _legacy_notebook(tmp_path: Path, folder_name: str) -> Notebook:
    folder = tmp_path / folder_name
    (folder / "pap").mkdir(parents=True)
    (folder / "pap" / "P.md").write_text("plan", encoding="utf-8")
    doc = {"cells": [], "metadata": {"krl": {"identification": {"pap": "pap/P.md", "pap_sha256": _sha("plan")}}}, "nbformat": 4, "nbformat_minor": 5}
    (folder / f"{folder_name}.ipynb").write_text(json.dumps(doc), encoding="utf-8")
    return load_notebook(folder / f"{folder_name}.ipynb")


def test_a_listed_legacy_notebook_is_checked_for_its_file_and_digest(tmp_path: Path) -> None:
    nb = _legacy_notebook(tmp_path, "C01_medicaid_expansion_did")
    assert check_pap(nb, None) == []
    (nb.path.parent / "pap" / "P.md").write_text("edited", encoding="utf-8")
    assert "does not match the plan on disk" in "\n".join(check_pap(nb, None))


def test_a_new_notebook_cannot_opt_into_the_legacy_path(tmp_path: Path) -> None:
    nb = _legacy_notebook(tmp_path, "C07_new_study")
    assert "legacy digest-only path is an allowlist" in "\n".join(check_pap(nb, None))


def test_the_legacy_allowlist_is_exactly_c01_to_c06() -> None:
    assert sorted(n[:3] for n in LEGACY) == ["C01", "C02", "C03", "C04", "C05", "C06"]


def test_a_notebook_without_a_pap_folder_is_out_of_scope(tmp_path: Path) -> None:
    folder = tmp_path / "D1"
    folder.mkdir()
    (folder / "D1.ipynb").write_text(json.dumps({"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}), encoding="utf-8")
    assert not in_scope(load_notebook(folder / "D1.ipynb"))


def _git(cwd: Path, *args: str, env_extra: dict[str, str] | None = None) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull, **(env_extra or {})}
    done = subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True, env=env)
    return done.stdout.strip()


def _commit(repo: Path, rel: str, text: str, when: str, message: str) -> str:
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(text, encoding="utf-8")
    _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", message, env_extra={"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when})
    return _git(repo, "rev-parse", "HEAD")


def test_real_git_binds_by_content_and_author_time_and_survives_a_rebase(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, "base.txt", "x", "2026-09-01T00:00:00+00:00", "base")
    _git(repo, "checkout", "-q", "-b", "card")
    rel = "n/pap/X1_plan.md"
    _commit(repo, rel, PLAN, T0, "plan")
    facts = RepoFacts(repo)
    (commit, when, sha), = facts.file_history(rel)
    assert when == epoch(T0) and sha == _sha(PLAN)
    _git(repo, "checkout", "-q", "main")
    _commit(repo, "other.txt", "y", "2026-09-02T00:00:00+00:00", "moves main")
    _git(repo, "checkout", "-q", "card")
    _git(repo, "rebase", "-q", "main")
    (new_commit, new_when, new_sha), = RepoFacts(repo).file_history(rel)
    assert new_commit != commit and new_when == epoch(T0) and new_sha == _sha(PLAN)       # the id changed; the binding did not


def test_real_git_ignores_a_commit_that_is_not_in_heads_ancestry(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, "base.txt", "x", "2026-09-01T00:00:00+00:00", "base")
    rel = "n/pap/X1_plan_amendment_1.md"
    _git(repo, "checkout", "-q", "-b", "elsewhere")
    _commit(repo, rel, A1, T1, "amendment on another branch")
    _git(repo, "checkout", "-q", "main")
    assert RepoFacts(repo).file_history(rel) == []                      # exists in the object store; not in HEAD's ancestry
    _git(repo, "checkout", "-q", "-b", "dangling")
    _commit(repo, rel, A1, T1, "to be dropped")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "branch", "-q", "-D", "dangling")
    _git(repo, "branch", "-q", "-D", "elsewhere")
    assert RepoFacts(repo).file_history(rel) == []                      # dangling now: still never satisfies the rule


def test_real_git_reports_a_later_modification_and_committed_ledger_versions(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    rel, led = "n/pap/X1_plan.md", "n/provenance/_runs.jsonl"
    _commit(repo, rel, PLAN, T0, "plan")
    _commit(repo, rel, PLAN + " edited", T1, "edit")
    hist = RepoFacts(repo).file_history(rel)
    assert [h[2] for h in hist] == [_sha(PLAN), _sha(PLAN + " edited")]
    _commit(repo, led, "a\n", T1, "ledger 1")
    _commit(repo, led, "a\nb\n", T2, "ledger 2")
    assert RepoFacts(repo).ledger_versions(led) == [b"a\n", b"a\nb\n"]


def test_a_shallow_clone_fails_closed_in_ci_and_unless_allowed(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    _git(src, "init", "-q", "-b", "main")
    _commit(src, "a.txt", "1", "2026-09-01T00:00:00+00:00", "one")
    _commit(src, "a.txt", "2", "2026-09-02T00:00:00+00:00", "two")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{src}", str(clone)], check=True, capture_output=True)
    with pytest.raises(RuntimeError, match="shallow"):
        RepoFacts(clone)
    facts, problem = facts_or_problem(clone, env={})
    assert facts is None and "fails closed" in problem
    facts, problem = facts_or_problem(clone, env={"CI": "true", "KRL_ALLOW_SHALLOW": "1"})
    assert facts is None and "fails closed" in problem                     # never skipped in CI
    with pytest.warns(UserWarning, match="KRL_ALLOW_SHALLOW"):
        facts, problem = facts_or_problem(clone, env={"KRL_ALLOW_SHALLOW": "1"})
    assert facts is None and problem is None
