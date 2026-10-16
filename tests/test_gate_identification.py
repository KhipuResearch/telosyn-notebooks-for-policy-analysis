"""Gate -- the identification contract (DECISIONS/0009 section 3.2).

Every causal notebook declares ``krl.identification`` and ships, beside it, a
pre-analysis plan committed before the first retrieval and a falsification that
was actually run. This gate makes that binding. A notebook is in scope when it

* declares ``krl.identification``; or
* sits under ``projects/09-*`` or ``projects/13-*``; or
* sits under ``projects/11-*`` with ``artifact_class: causal_analysis``.

The rules, each of which names the notebook, the rule and what to do:

1. the block is an object with ``design``, ``estimand``, ``assumption``,
   ``inference``, ``pap``, ``pap_sha256`` and a non-empty ``falsification`` list;
2. every falsification ``cell`` exists, is a code cell, has stored output, and
   that output holds a line ``FALSIFICATION: ... statistic=<number> ...
   verdict=PASS|FAIL`` -- a verdict is a finding, so ``FAIL`` is accepted and a
   bare string is not;
3. ``pap`` resolves inside the notebook's own folder and ``pap_sha256`` equals
   the digest of that file;
4. at least one provenance record exists, and the plan's first commit predates
   the earliest committed ``retrieved_utc``;
5. the Limitations section says whether the analysis departed from the plan.

The git evidence is injected, so the rules are tested on fixtures; ``RepoGit``
reads real history and **fails closed** on a shallow clone rather than skipping.

On real corpus notebooks this gate is vacuous until project 09 lands. That is
why the planted-violation tests below exist: a gate that cannot fail is counted
as coverage.

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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import pytest

from gate_support import Cell, Notebook, load_notebook

ADR = "DECISIONS/0009-expansion-architecture.md"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "identification"
REQUIRED_TEXT = ("design", "estimand", "assumption", "inference", "pap", "pap_sha256")
FALSIFICATION_LINE = re.compile(
    r"^FALSIFICATION:.*\bstatistic=-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\b.*\bverdict=(?:PASS|FAIL)\b",
    re.M,
)
LIMITATIONS = re.compile(r"^##\s*Limitations\b.*?(?=^##\s|\Z)", re.M | re.S | re.I)
SCOPED_PROJECTS = ("09-", "13-")


class GitEvidence(Protocol):
    """What the gate needs from version control; injected so rules are testable."""

    def first_commit_epoch(self, path: Path) -> int | None:
        """Author time of the first commit that added ``path``; ``None`` if uncommitted."""

    def earliest_record_epoch(self, records: list[Path]) -> int | None:
        """Earliest ``retrieved_utc`` across the committed first versions of ``records``."""


class RepoGit:
    """Real history. Raises, never skips, when history is unavailable."""

    def __init__(self, root: Path) -> None:
        """Init."""
        self.root = root
        shallow = self._git("rev-parse", "--is-shallow-repository").strip()
        if shallow != "false":
            raise RuntimeError(
                "identification gate: git history is shallow or unreadable "
                f"(is-shallow={shallow!r}). The pre-analysis-plan ordering cannot be "
                "verified; fetch full history. The gate fails closed by design "
                f"({ADR} section 3.2)."
            )

    def _git(self, *args: str) -> str:
        """Git."""
        done = subprocess.run(
            ["git", "-C", str(self.root), *args],
            check=False, capture_output=True, text=True,
        )
        if done.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {done.stderr.strip()}")
        return done.stdout

    def _first_add(self, path: Path) -> str | None:
        """First add."""
        rel = str(path.resolve().relative_to(self.root.resolve()))
        shas = self._git("log", "--diff-filter=A", "--format=%H", "--", rel).split()
        return shas[-1] if shas else None

    def first_commit_epoch(self, path: Path) -> int | None:
        """First commit epoch."""
        sha = self._first_add(path)
        return int(self._git("show", "-s", "--format=%at", sha).strip()) if sha else None

    def earliest_record_epoch(self, records: list[Path]) -> int | None:
        """Earliest record epoch."""
        epochs = []
        for record in records:
            sha = self._first_add(record)
            if sha is None:
                continue
            rel = str(record.resolve().relative_to(self.root.resolve()))
            doc = json.loads(self._git("show", f"{sha}:{rel}"))
            epochs.append(_epoch(doc["retrieved_utc"]))
        return min(epochs) if epochs else None


def _epoch(stamp: str) -> int:
    """Epoch."""
    parsed = datetime.fromisoformat(stamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


def in_scope(nb: Notebook, root: Path) -> bool:
    """Whether the identification contract applies to ``nb``."""
    if "identification" in nb.krl:
        return True
    try:
        parts = nb.path.resolve().relative_to(root.resolve()).parts
    except ValueError:
        return False
    top = parts[0] if parts else ""
    if top.startswith(SCOPED_PROJECTS):
        return True
    return top.startswith("11-") and nb.krl.get("artifact_class") == "causal_analysis"


def _output_text(cell: Cell) -> str:
    """Output text."""
    chunks: list[str] = []
    for out in cell.outputs:
        if "text" in out:
            text = out["text"]
            chunks.append("".join(text) if isinstance(text, list) else str(text))
        plain = out.get("data", {}).get("text/plain")
        if plain is not None:
            chunks.append("".join(plain) if isinstance(plain, list) else str(plain))
    return "\n".join(chunks)


def check_identification(nb: Notebook, git: GitEvidence) -> list[str]:
    """Return every violation of the contract, each stating rule and remedy.

    Identifying assumption: none; this checks form and ordering, not truth.
    Complexity O(cells + falsifications). Edge case a maintainer must not
    violate: an absent block and a malformed block are both failures.
    """
    name = nb.path.name
    found: list[str] = []

    def fail(rule: str, fix: str) -> None:
        """Fail."""
        found.append(f"{name}: {rule} -> {fix}")

    block = nb.identification
    if block is None:
        fail("in scope but `krl.identification` is absent or not an object",
             f"declare the block ({ADR} section 3.2)")
        return found
    for key in REQUIRED_TEXT:
        if not isinstance(block.get(key), str) or not block[key].strip():
            fail(f"`identification.{key}` is missing or empty", "state it as a non-empty string")
    falsifications = block.get("falsification")
    if not isinstance(falsifications, list) or not falsifications:
        fail("`identification.falsification` is missing or empty",
             "list at least one test that could have failed")
        falsifications = []

    by_index = {c.index: c for c in nb.cells}
    for i, item in enumerate(falsifications):
        label = f"falsification[{i}]"
        if not isinstance(item, dict) or not isinstance(item.get("cell"), int):
            fail(f"{label} has no integer `cell`", "give the index of the cell that ran it")
            continue
        if item.get("result") != "stored":
            fail(f"{label}.result is {item.get('result')!r}, not 'stored'", "store the output")
        cell = by_index.get(item["cell"])
        if cell is None or cell.kind != "code":
            fail(f"{label} names cell {item['cell']}, which is not a code cell",
                 "point `cell` at the code cell that runs the test")
        elif not cell.outputs:
            fail(f"{label} cell {cell.index} has no stored output", "execute the notebook")
        elif not FALSIFICATION_LINE.search(_output_text(cell)):
            fail(f"{label} cell {cell.index} prints no `FALSIFICATION:` line with "
                 "`statistic=<number>` and `verdict=PASS|FAIL`",
                 "print the line from the computed result, not a literal")

    _check_plan(nb, block, git, fail)
    limits = LIMITATIONS.search(nb.markdown_source)
    if limits is None or not re.search(r"pre-analysis plan", limits.group(0), re.I) \
            or not re.search(r"depart", limits.group(0), re.I):
        fail("Limitations does not say whether the analysis departed from the pre-analysis plan",
             "state the departure, or that there was none")
    return found


def _check_plan(nb: Notebook, block: dict[str, Any], git: GitEvidence, fail: Any) -> None:
    """Check plan."""
    pap = nb.pap
    if pap is None:
        return
    folder = nb.path.parent.resolve()
    target = (folder / pap).resolve()
    if folder not in target.parents:
        fail(f"`identification.pap` ({pap!r}) resolves outside the notebook's folder",
             "keep the plan beside the notebook")
        return
    if not target.is_file():
        fail(f"pre-analysis plan {pap!r} does not exist", "commit the plan before retrieval")
        return
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    if digest != block.get("pap_sha256"):
        fail(f"`pap_sha256` does not match {pap!r} (file digest {digest[:12]}...)",
             "the plan changed after it was recorded; restore it or declare the departure")
    records = sorted((folder / "provenance").glob("*.json"))
    if not records:
        fail("no provenance record beside the notebook",
             "call DataProvenance.write for every retrieval; "
             "ordering cannot be checked without one")
        return
    plan_at = git.first_commit_epoch(target)
    first_retrieval = git.earliest_record_epoch(records)
    if plan_at is None:
        fail(f"pre-analysis plan {pap!r} is not committed", "commit it before the first retrieval")
    elif first_retrieval is None:
        fail("no provenance record is committed", "commit the record the retrieval wrote")
    elif plan_at >= first_retrieval:
        fail(f"the plan's first commit ({plan_at}) is not before the first retrieval "
             f"({first_retrieval})", "the plan must land before the data are pulled")


class FakeGit:
    """Fixed evidence for fixture tests."""

    def __init__(self, plan: int | None, retrieval: int | None) -> None:
        """Init."""
        self.plan, self.retrieval = plan, retrieval

    def first_commit_epoch(self, path: Path) -> int | None:
        """First commit epoch."""
        del path
        return self.plan

    def earliest_record_epoch(self, records: list[Path]) -> int | None:
        """Earliest record epoch."""
        del records
        return self.retrieval


EARLY, LATE = 1_000, 2_000


def _compliant() -> Notebook:
    """Compliant."""
    return load_notebook(FIXTURES / "compliant" / "C_demo" / "C_demo.ipynb")


def _mutated(mutate: Any, tmp_path: Path) -> Notebook:
    """Copy the compliant fixture into ``tmp_path`` and apply ``mutate`` to its JSON."""
    src = FIXTURES / "compliant" / "C_demo"
    dst = tmp_path / "C_demo"
    for path in src.rglob("*"):
        if path.is_file():
            out = dst / path.relative_to(src)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(path.read_bytes())
    raw = json.loads((dst / "C_demo.ipynb").read_text(encoding="utf-8"))
    mutate(raw)
    (dst / "C_demo.ipynb").write_text(json.dumps(raw), encoding="utf-8")
    return load_notebook(dst / "C_demo.ipynb")


def test_identification_contract_holds(notebook: Notebook) -> None:
    """Every in-scope corpus notebook meets the contract; others are not asked."""
    repo = Path(__file__).resolve().parents[1]
    root = Path(os.environ.get("KRL_NOTEBOOK_ROOT", str(repo / "projects")))
    if not in_scope(notebook, root):
        return
    problems = check_identification(notebook, RepoGit(repo))
    assert not problems, "\n  ".join(problems)


def test_the_compliant_fixture_passes() -> None:
    """The compliant fixture passes."""
    assert not check_identification(_compliant(), FakeGit(EARLY, LATE))


def test_the_planted_fixture_fails_every_rule_it_plants() -> None:
    """The planted fixture fails every rule it plants."""
    nb = load_notebook(FIXTURES / "planted" / "C_demo" / "C_demo.ipynb")
    text = "\n".join(check_identification(nb, FakeGit(EARLY, LATE)))
    assert "prints no `FALSIFICATION:` line" in text
    assert "`pap_sha256` does not match" in text
    assert "departed from the pre-analysis plan" in text


@pytest.mark.parametrize(
    ("label", "mutate", "expect"),
    [
        ("block removed", lambda r: r["metadata"]["krl"].pop("identification"), "absent"),
        ("assumption blanked",
         lambda r: r["metadata"]["krl"]["identification"].update(assumption=""),
         "identification.assumption"),
        ("falsification emptied",
         lambda r: r["metadata"]["krl"]["identification"].update(falsification=[]),
         "falsification` is missing or empty"),
        ("falsification points at markdown",
         lambda r: r["metadata"]["krl"]["identification"]["falsification"][0].update(cell=0),
         "not a code cell"),
        ("falsification output dropped",
         lambda r: r["cells"][2].update(outputs=[]), "no stored output"),
        ("line has no verdict",
         lambda r: r["cells"][2]["outputs"][0].update(
             text=["FALSIFICATION: placebo | statistic=0.02\n"]),
         "prints no `FALSIFICATION:` line"),
        ("line has no statistic",
         lambda r: r["cells"][2]["outputs"][0].update(
             text=["FALSIFICATION: placebo | verdict=PASS\n"]),
         "prints no `FALSIFICATION:` line"),
        ("pap escapes the folder",
         lambda r: r["metadata"]["krl"]["identification"].update(pap="../../outside.md"),
         "outside the notebook's folder"),
        ("pap digest stale",
         lambda r: r["metadata"]["krl"]["identification"].update(pap_sha256="0" * 64),
         "`pap_sha256` does not match"),
        ("limitations silent",
         lambda r: r["cells"][3].update(source=["## Limitations\n", "\n", "None.\n"]),
         "departed from the pre-analysis plan"),
    ],
    ids=lambda v: v if isinstance(v, str) and " " in v else None,
)
def test_each_mutation_is_caught(label: str, mutate: Any, expect: str, tmp_path: Path) -> None:
    """Each mutation is caught."""
    problems = check_identification(_mutated(mutate, tmp_path), FakeGit(EARLY, LATE))
    assert any(expect in p for p in problems), f"{label}: expected {expect!r} in {problems}"


def test_a_verdict_of_fail_is_a_finding_not_a_violation(tmp_path: Path) -> None:
    """A verdict of fail is a finding not a violation."""
    def to_fail(raw: dict[str, Any]) -> None:
        """To fail."""
        line = "FALSIFICATION: placebo | statistic=3.1 | verdict=FAIL\n"
        raw["cells"][2]["outputs"][0]["text"] = [line]
    assert not check_identification(_mutated(to_fail, tmp_path), FakeGit(EARLY, LATE))


@pytest.mark.parametrize(
    ("plan", "retrieval", "expect"),
    [(LATE, EARLY, "not before the first retrieval"),
     (EARLY, EARLY, "not before the first retrieval"),
     (None, LATE, "is not committed"),
     (EARLY, None, "no provenance record is committed")],
)
def test_plan_ordering_is_enforced(plan: int | None, retrieval: int | None, expect: str) -> None:
    """Plan ordering is enforced."""
    problems = check_identification(_compliant(), FakeGit(plan, retrieval))
    assert any(expect in p for p in problems), problems


def test_a_missing_provenance_record_is_a_failure(tmp_path: Path) -> None:
    """A missing provenance record is a failure."""
    nb = _mutated(lambda r: None, tmp_path)
    for record in (nb.path.parent / "provenance").glob("*.json"):
        record.unlink()
    problems = check_identification(nb, FakeGit(EARLY, LATE))
    assert any("no provenance record beside the notebook" in p for p in problems)


def test_scope_is_by_declaration_by_project_and_by_class(tmp_path: Path) -> None:
    """Scope is by declaration by project and by class."""
    def nb_at(rel: str, krl: dict[str, Any]) -> Notebook:
        """Nb at."""
        path = tmp_path / rel
        return Notebook(path=path, metadata={"krl": krl}, cells=[])

    assert in_scope(nb_at("01-fundamentals/D1/D1.ipynb", {"identification": {}}), tmp_path)
    assert in_scope(nb_at("09-causal-identification/C1/C1.ipynb", {}), tmp_path)
    assert in_scope(nb_at("13-evidence-synthesis/M1/M1.ipynb", {}), tmp_path)
    assert in_scope(nb_at("11-x/Q1/Q1.ipynb", {"artifact_class": "causal_analysis"}), tmp_path)
    assert not in_scope(nb_at("11-x/Q1/Q1.ipynb", {"artifact_class": "tutorial"}), tmp_path)
    assert not in_scope(nb_at("01-fundamentals/D1/D1.ipynb", {}), tmp_path)


def _repo(tmp_path: Path) -> Path:
    """Repo."""
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.test",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.test"}

    def run(*args: str, when: str | None = None) -> None:
        """Run."""
        e = dict(env)
        if when:
            e.update(GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True, env=e)

    run("init", "-q")
    (tmp_path / "plan.md").write_text("plan\n")
    run("add", "plan.md")
    run("commit", "-q", "-m", "plan", when="2026-01-01T00:00:00+00:00")
    (tmp_path / "rec.json").write_text(json.dumps({"retrieved_utc": "2026-02-01T00:00:00+00:00"}))
    run("add", "rec.json")
    run("commit", "-q", "-m", "record", when="2026-02-02T00:00:00+00:00")
    return tmp_path


def test_repogit_reads_real_history(tmp_path: Path) -> None:
    """Repogit reads real history."""
    git = RepoGit(_repo(tmp_path))
    plan = git.first_commit_epoch(tmp_path / "plan.md")
    first = git.earliest_record_epoch([tmp_path / "rec.json"])
    assert plan == _epoch("2026-01-01T00:00:00+00:00")
    assert first == _epoch("2026-02-01T00:00:00+00:00")
    assert git.first_commit_epoch(tmp_path / "missing.md") is None


def test_repogit_fails_closed_on_a_shallow_clone(tmp_path: Path) -> None:
    """Repogit fails closed on a shallow clone."""
    (tmp_path / "origin").mkdir()
    origin = _repo(tmp_path / "origin")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{origin}", str(clone)],
                   check=True, capture_output=True)
    with pytest.raises(RuntimeError, match="shallow"):
        RepoGit(clone)


def test_a_notebook_not_in_git_history_is_never_silently_ordered(tmp_path: Path) -> None:
    """A notebook not in git history is never silently ordered."""
    folder = tmp_path / "repo"
    folder.mkdir()
    _repo(folder)
    git = RepoGit(folder)
    (folder / "late.json").write_text(json.dumps({"retrieved_utc": "2026-03-01T00:00:00+00:00"}))
    assert git.earliest_record_epoch([folder / "late.json"]) is None
    assert git.first_commit_epoch(folder / "plan.md") is not None
