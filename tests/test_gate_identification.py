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
3. ``pap`` resolves inside the notebook's own folder, and the digest the
   notebook declares equals the SHA-256 of that file **and** the ``pap_sha256``
   carried by every provenance record beside it -- a record is written at
   retrieval, so the digest it holds says which plan was in force then;
4. at least one provenance record exists;
5. the Limitations section says whether the analysis departed from the plan.

Precedence of the plan over the data is proven by that digest equality, not by
commit time (DECISIONS/0009, amendment of 2026-10-15). Commit dates are still
compared, but only as a *warning*: a squash or rebase can move a date without
the plan having changed, and a date cannot say what the plan said.

``RepoGit`` reads real history for that warning; where history is unavailable
the warning says the ordering could not be checked, and the gate's verdict does
not depend on it.

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
import warnings
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
        self.root = root
        shallow = self._git("rev-parse", "--is-shallow-repository").strip()
        if shallow != "false":
            raise RuntimeError(
                "identification gate: git history is shallow or unreadable "
                f"(is-shallow={shallow!r}). The pre-analysis-plan ordering cannot be "
                "verified; fetch full history. The gate fails closed by design "
                f"({ADR} section 3.2)."
            )

    @classmethod
    def containing(cls, folder: Path) -> "RepoGit":
        """The repository that holds ``folder``; raises if there is none.

        A notebook root can be pointed outside this checkout (KRL_NOTEBOOK_ROOT),
        so the repository is found from the notebook, not assumed.
        """
        done = subprocess.run(
            ["git", "-C", str(folder), "rev-parse", "--show-toplevel"],
            check=False, capture_output=True, text=True,
        )
        if done.returncode != 0:
            raise RuntimeError(
                f"identification gate: {folder} is not inside a git repository, so the "
                f"plan-before-retrieval ordering cannot be verified ({ADR} section 3.2)."
            )
        return cls(Path(done.stdout.strip()))

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


def check_identification(nb: Notebook) -> list[str]:
    """Return every violation of the contract, each stating rule and remedy.

    Identifying assumption: none; this checks form and binding, not truth.
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

    _check_plan(nb, block, fail)
    limits = LIMITATIONS.search(nb.markdown_source)
    if limits is None or not re.search(r"pre-analysis plan", limits.group(0), re.I) \
            or not re.search(r"depart", limits.group(0), re.I):
        fail("Limitations does not say whether the analysis departed from the pre-analysis plan",
             "state the departure, or that there was none")
    return found


def _check_plan(nb: Notebook, block: dict[str, Any], fail: Any) -> None:
    """Check the plan's digest against the notebook block and every record."""
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
    records = _records(folder)
    if not records:
        fail("no provenance record beside the notebook",
             "call DataProvenance.write for every retrieval; the plan digest is proven "
             "by the record")
        return
    for path, doc in records:
        held = doc.get("pap_sha256")
        if held is None:
            fail(f"provenance record {path.name} carries no `pap_sha256` for plan {pap!r}",
                 "bind the record with DataProvenance.with_pap before writing it")
        elif held != digest:
            fail(f"provenance record {path.name} was written under a plan with digest "
                 f"{str(held)[:12]}..., but {pap!r} hashes to {digest[:12]}...",
                 "the plan changed after retrieval; restore it or declare the departure "
                 "and re-retrieve")


def _records(folder: Path) -> list[tuple[Path, dict[str, Any]]]:
    """Every provenance record beside the notebook, as ``(path, document)``."""
    found: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted((folder / "provenance").glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for item in doc if isinstance(doc, list) else [doc]:
            if isinstance(item, dict):
                found.append((path, item))
    return found


def ordering_warnings(nb: Notebook, git: GitEvidence) -> list[str]:
    """Warnings about commit-date ordering of the plan and the first retrieval.

    Advisory: the verdict is the digest binding. Returns a warning, never
    raises, when history is unavailable, so that a shallow clone costs the
    reader a warning and not the gate its verdict.
    """
    pap = nb.pap
    if pap is None:
        return []
    folder = nb.path.parent.resolve()
    target = (folder / pap).resolve()
    records = sorted((folder / "provenance").glob("*.json"))
    if not target.is_file() or not records:
        return []
    name = nb.path.name
    try:
        plan_at = git.first_commit_epoch(target)
        first_retrieval = git.earliest_record_epoch(records)
    except (RuntimeError, ValueError, OSError) as exc:
        return [f"{name}: plan-before-retrieval commit order could not be checked ({exc})"]
    message = ""
    if plan_at is None:
        message = f"pre-analysis plan {pap!r} is not committed yet"
    elif first_retrieval is None:
        message = "no provenance record is committed yet"
    elif plan_at >= first_retrieval:
        message = (f"the plan {pap!r} was first committed at {plan_at}, not before the "
                   f"first retrieval at {first_retrieval}; the digest binding is the proof, "
                   "but the history does not show the order")
    return [f"{name}: {message}"] if message else []


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


def _mutated(mutate: Any, tmp_path: Path, mutate_record: Any = None) -> Notebook:
    """Copy the compliant fixture into ``tmp_path``; apply ``mutate`` to the notebook JSON
    and ``mutate_record`` to its provenance record."""
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
    if mutate_record is not None:
        record = dst / "provenance" / "fixture.json"
        doc = json.loads(record.read_text(encoding="utf-8"))
        mutate_record(doc)
        record.write_text(json.dumps(doc), encoding="utf-8")
    return load_notebook(dst / "C_demo.ipynb")


def test_identification_contract_holds(notebook: Notebook) -> None:
    """Every in-scope corpus notebook meets the contract; others are not asked."""
    repo = Path(__file__).resolve().parents[1]
    root = Path(os.environ.get("KRL_NOTEBOOK_ROOT", str(repo / "projects")))
    if not in_scope(notebook, root):
        return
    problems = check_identification(notebook)
    assert not problems, "\n  ".join(problems)
    try:
        git: GitEvidence = RepoGit.containing(notebook.path.parent)
    except RuntimeError as exc:
        warnings.warn(f"{notebook.path.name}: commit order not checked ({exc})", stacklevel=1)
        return
    for message in ordering_warnings(notebook, git):
        warnings.warn(message, stacklevel=1)


def test_the_compliant_fixture_passes() -> None:
    """The compliant fixture passes."""
    assert not check_identification(_compliant())


def test_the_planted_fixture_fails_every_rule_it_plants() -> None:
    """The planted fixture fails every rule it plants."""
    nb = load_notebook(FIXTURES / "planted" / "C_demo" / "C_demo.ipynb")
    text = "\n".join(check_identification(nb))
    assert "prints no `FALSIFICATION:` line" in text
    assert "`pap_sha256` does not match" in text
    assert "departed from the pre-analysis plan" in text


def test_a_record_written_under_a_different_plan_fails_and_names_the_plan() -> None:
    """The notebook declares the right digest; the record holds another: binding fails."""
    nb = load_notebook(FIXTURES / "planted_digest" / "C_demo" / "C_demo.ipynb")
    problems = check_identification(nb)
    assert len(problems) == 1, problems
    assert "pap/C_demo_pap.md" in problems[0]
    assert "provenance record fixture.json" in problems[0]
    assert "111111111111" in problems[0]


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
    problems = check_identification(_mutated(mutate, tmp_path))
    assert any(expect in p for p in problems), f"{label}: expected {expect!r} in {problems}"


def test_a_verdict_of_fail_is_a_finding_not_a_violation(tmp_path: Path) -> None:
    """A verdict of fail is a finding not a violation."""
    def to_fail(raw: dict[str, Any]) -> None:
        """To fail."""
        line = "FALSIFICATION: placebo | statistic=3.1 | verdict=FAIL\n"
        raw["cells"][2]["outputs"][0]["text"] = [line]
    assert not check_identification(_mutated(to_fail, tmp_path))


@pytest.mark.parametrize(
    ("plan", "retrieval", "expect"),
    [(LATE, EARLY, "not before the first retrieval"),
     (EARLY, EARLY, "not before the first retrieval"),
     (None, LATE, "is not committed yet"),
     (EARLY, None, "no provenance record is committed yet")],
)
def test_commit_order_is_a_warning_and_never_a_verdict(
    plan: int | None, retrieval: int | None, expect: str
) -> None:
    """Out-of-order or missing history warns; the digest-bound verdict is unchanged."""
    nb = _compliant()
    assert not check_identification(nb)
    warned = ordering_warnings(nb, FakeGit(plan, retrieval))
    assert any(expect in w for w in warned), warned
    assert not ordering_warnings(nb, FakeGit(EARLY, LATE))


def test_unreadable_history_warns_instead_of_raising() -> None:
    """A shallow clone or missing git costs a warning, not the gate's verdict."""
    class Broken:
        """History that cannot be read."""

        def first_commit_epoch(self, path: Path) -> int | None:
            """Raise."""
            raise RuntimeError("history is shallow")

        def earliest_record_epoch(self, records: list[Path]) -> int | None:
            """Raise."""
            raise RuntimeError("history is shallow")

    warned = ordering_warnings(_compliant(), Broken())
    assert len(warned) == 1 and "could not be checked" in warned[0]


def test_a_record_without_the_plan_digest_fails(tmp_path: Path) -> None:
    """A record that never named a plan cannot prove the plan preceded it."""
    nb = _mutated(lambda r: None, tmp_path, lambda d: d.pop("pap_sha256"))
    problems = check_identification(nb)
    assert any("carries no `pap_sha256`" in p and "pap/C_demo_pap.md" in p for p in problems)


def test_a_changed_plan_breaks_both_bindings(tmp_path: Path) -> None:
    """Editing the plan after retrieval fails the notebook digest and the record digest."""
    nb = _mutated(lambda r: None, tmp_path)
    (nb.path.parent / "pap" / "C_demo_pap.md").write_text("changed after the data\n")
    problems = check_identification(nb)
    assert any("`pap_sha256` does not match" in p for p in problems)
    assert any("provenance record fixture.json was written under a plan" in p for p in problems)


def test_a_missing_provenance_record_is_a_failure(tmp_path: Path) -> None:
    """A missing provenance record is a failure."""
    nb = _mutated(lambda r: None, tmp_path)
    for record in (nb.path.parent / "provenance").glob("*.json"):
        record.unlink()
    problems = check_identification(nb)
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


def _commit_fixture(repo: Path, plan_when: str, record_when: str) -> Notebook:
    """Commit the compliant fixture into ``repo`` with the plan and record dated as given."""
    src = FIXTURES / "compliant" / "C_demo"
    base = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.test",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.test"}

    def commit(paths: list[str], when: str) -> None:
        env = {**os.environ, **base, "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
        subprocess.run(["git", "-C", str(repo), "add", *paths], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "c"],
                       check=True, capture_output=True, env=env)

    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True, capture_output=True)
    dst = repo / "09-causal-identification" / "C_demo"
    for path in src.rglob("*"):
        if path.is_file():
            out = dst / path.relative_to(src)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(path.read_bytes())
    rel = "09-causal-identification/C_demo"
    commit([f"{rel}/pap/C_demo_pap.md"], plan_when)
    commit([f"{rel}/provenance/fixture.json", f"{rel}/C_demo.ipynb"], record_when)
    return load_notebook(dst / "C_demo.ipynb")


def test_end_to_end_on_a_repository_outside_this_checkout(tmp_path: Path) -> None:
    """A plan committed first passes with no warning, repository found from the notebook."""
    nb = _commit_fixture(tmp_path, "2026-10-01T00:00:00+00:00", "2026-10-02T00:00:00+00:00")
    assert not check_identification(nb)
    assert not ordering_warnings(nb, RepoGit.containing(nb.path.parent))


def test_end_to_end_a_plan_committed_late_warns_and_still_passes(tmp_path: Path) -> None:
    """History dated after the record's retrieved_utc (2026-10-15) warns; digests still bind."""
    nb = _commit_fixture(tmp_path, "2026-10-20T00:00:00+00:00", "2026-10-21T00:00:00+00:00")
    assert not check_identification(nb)
    warned = ordering_warnings(nb, RepoGit.containing(nb.path.parent))
    assert any("not before the first retrieval" in w for w in warned), warned


def test_a_notebook_outside_any_repository_fails_closed(tmp_path: Path) -> None:
    """No repository: locating one raises, and the caller turns that into a warning."""
    with pytest.raises(RuntimeError, match="not inside a git repository"):
        RepoGit.containing(tmp_path)
