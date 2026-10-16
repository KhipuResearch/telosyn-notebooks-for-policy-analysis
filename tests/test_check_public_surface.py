"""Tests for ``scripts/check_public_surface.py``.

The checker's name patterns are private and are not in this repository, so every test
here runs against a **synthetic** denylist of made-up words. Whether the real list
finds anything in the real tree is the job of ``make surface`` and of CI, which hold the
private file; what is tested here is the machinery: that each kind of rule fires, that
exemptions are exact, that the allowlist is verified rather than trusted, that findings
never echo matched text, and that a missing or broken denylist is an error, not a pass.

This file plants paths on purpose, so the checker exempts it from the path rule alone.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[1]
NOREPLY = "186650653+bcdelodx@users.noreply.github.com"
HEADER = (
    "© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.\n"
    "Property of Deloatch, Williams, Faison & Parker, LLLP; "
    "exclusively licensed to Telosyn, Inc.\n"
    "SPDX-License-Identifier: LicenseRef-Proprietary\n"
)


def _load() -> ModuleType:
    """Load."""
    spec = importlib.util.spec_from_file_location(
        "check_surface", REPO / "scripts" / "check_public_surface.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolves annotations through sys.modules
    spec.loader.exec_module(module)
    return module


cps = _load()

#: A synthetic denylist: made-up words standing in for the private patterns.
SYNTHETIC = {
    "version": 1,
    "rules": {
        "apex": {"pattern": "zorblax|quuxcorp", "flags": "", "exempt_paths": ["LICENSE"]},
        "tooling": {
            "pattern": r"gizmobot|\bsidekick\b",
            "flags": "i",
            "exempt_suffixes": [".ipynb"],
            "ordinary_phrases": "side.kick bench",
        },
        "unpublished": {"pattern": r"frobnitz_\d+", "flags": ""},
    },
    "trailer": {"pattern": "Signed-Off-By-Bot|Made with bot"},
}


def _deny() -> object:
    """Deny."""
    return cps.parse_denylist(SYNTHETIC)


NO_ALLOW = cps.Allowlist()

PLANTED = [
    ("apex", "owned by zorblax limited"),
    ("apex", "see quuxcorp for details"),
    ("tooling", "written with GizmoBot"),
    ("tooling", "ask the sidekick"),
    ("unpublished", "import frobnitz_42"),
    ("path", "cd <operator-home>/work"),
    ("path", "see /home/someone/x"),
    ("path", "at /sessions/abc/data"),
    ("path", "mounted at /mnt/data"),
]


@pytest.mark.parametrize(("rule", "line"), PLANTED)
def test_every_rule_fires_on_a_planted_violation(rule: str, line: str) -> None:
    """Every rule fires on a planted violation."""
    hits = cps.scan_text("docs/example.md", line + "\n", _deny())
    assert [r for r, _, _ in hits] == [rule]


@pytest.mark.parametrize(
    "line",
    ["an ordinary sentence", "a side-kick bench", "/home/runner/work/repo", "the service mark"],
)
def test_compliant_and_documented_exceptions_are_quiet(line: str) -> None:
    """Compliant and documented exceptions are quiet."""
    assert cps.scan_text("docs/example.md", line + "\n", _deny()) == []


def test_line_numbers_are_reported_and_each_rule_counts_once_per_line() -> None:
    """Line numbers are reported and each rule counts once per line."""
    hits = cps.scan_text("x.md", "fine\nzorblax and quuxcorp\n/Users/a and /mnt/b\n", _deny())
    assert [(r, n) for r, n, _ in hits] == [("apex", 2), ("path", 3)]


def test_the_exemptions_are_exact() -> None:
    """The exemptions are exact."""
    deny = _deny()
    assert cps.scan_text("LICENSE", "zorblax\n", deny) == []
    assert cps.scan_text("LICENSE.md", "zorblax\n", deny) != []
    assert cps.scan_text("p/x.ipynb", "the sidekick wrote this\n", deny) == []
    assert cps.scan_text("p/x.ipynb", "zorblax\n", deny) != []
    assert cps.scan_text("scripts/check_public_surface.py", "/Users/ here\n", deny) == []
    assert cps.scan_text("tests/test_check_public_surface.py", "/mnt/\n", deny) == []
    assert cps.scan_text("scripts/other.py", "/Users/\n", deny) != []
    # the path exemption never covers the NAME rules: the checker itself must hold no names
    assert cps.scan_text("scripts/check_public_surface.py", "zorblax\n", deny) != []


# --------------------------------------------------------------------------- denylist
def test_a_missing_denylist_is_an_error_never_a_pass(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """A missing denylist is an error never a pass."""
    monkeypatch.delenv(cps.DENYLIST_ENV, raising=False)
    with pytest.raises(cps.SurfaceError, match="not set"):
        cps.load_denylist()
    assert cps.main(["--root", str(tmp_path), "--tree"]) == 2
    err = capsys.readouterr().err
    assert "could not run" in err and "private" in err
    monkeypatch.setenv(cps.DENYLIST_ENV, str(tmp_path / "nope.json"))
    with pytest.raises(cps.SurfaceError, match="does not exist"):
        cps.load_denylist()


@pytest.mark.parametrize(
    ("doc", "message"),
    [
        ("not json", "not readable JSON"),
        ({"version": 2, "rules": {}}, "version 1"),
        ({"version": 1, "rules": {}}, "non-empty"),
        (
            {"version": 1, "rules": {"a": {"pattern": 5}}, "trailer": {"pattern": "x"}},
            "string 'pattern'",
        ),
        (
            {"version": 1, "rules": {"a": {"pattern": "("}}, "trailer": {"pattern": "x"}},
            "not a valid pattern",
        ),
        (
            {
                "version": 1,
                "rules": {"a": {"pattern": "x", "flags": "m"}},
                "trailer": {"pattern": "x"},
            },
            "flags",
        ),
        ({"version": 1, "rules": {"a": {"pattern": "x"}}}, "'trailer'"),
    ],
)
def test_a_broken_denylist_is_refused_without_echoing_a_pattern(
    doc: object, message: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A broken denylist is refused without echoing a pattern."""
    file = tmp_path / "deny.json"
    file.write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="utf-8")
    monkeypatch.setenv(cps.DENYLIST_ENV, str(file))
    with pytest.raises(cps.SurfaceError, match=message) as exc:
        cps.load_denylist()
    assert "(" not in str(exc.value).replace("(", "", 0) or "pattern" in str(exc.value)


def test_the_denylist_is_read_from_the_environment_or_an_explicit_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The denylist is read from the environment or an explicit path."""
    file = tmp_path / "deny.json"
    file.write_text(json.dumps(SYNTHETIC), encoding="utf-8")
    monkeypatch.setenv(cps.DENYLIST_ENV, str(file))
    assert {r.name for r in cps.load_denylist().rules} == {"apex", "tooling", "unpublished"}
    monkeypatch.delenv(cps.DENYLIST_ENV)
    assert cps.load_denylist(file).trailer.search("Made with bot")


# ---------------------------------------------------------------------------- allowlist
def _write_allow(path: Path, entries: list[dict]) -> Path:
    """Write allow."""
    path.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    return path


def _entry(rule: str, file: str, line: str, reason: str = "because", **extra: object) -> dict:
    """Entry."""
    return {
        "rule": rule,
        "file": file,
        "line_sha256": hashlib.sha256(line.strip().encode()).hexdigest(),
        "reason": reason,
        **extra,
    }


def test_the_allowlist_requires_a_reason_a_hash_and_unique_entries(tmp_path: Path) -> None:
    """The allowlist requires a reason a hash and unique entries."""
    path = tmp_path / "allow.json"
    _write_allow(path, [_entry("path", "a.md", "x", reason="  ")])
    with pytest.raises(cps.SurfaceError, match="no reason"):
        cps.load_allowlist(path)
    _write_allow(path, [{"rule": "path", "file": "a.md", "line_sha256": "zz", "reason": "r"}])
    with pytest.raises(cps.SurfaceError, match="no line hash"):
        cps.load_allowlist(path)
    _write_allow(path, [_entry("path", "a.md", "x"), _entry("path", "a.md", "x ")])
    with pytest.raises(cps.SurfaceError, match="duplicate"):
        cps.load_allowlist(path)
    assert cps.load_allowlist(tmp_path / "absent.json").entries == {}
    assert cps.line_hash("  padded  ") == cps.line_hash("padded")


# ------------------------------------------------------------------------ throwaway repos
class Repo:
    """A real git repository in ``tmp_path`` with an ``origin/main`` to compare against."""

    def __init__(self, root: Path) -> None:
        """Init."""
        self.root = root
        self.env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": NOREPLY,
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": NOREPLY,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
        self.git("init", "-q", "-b", "main")
        self.write(".gitignore", "\n".join(cps.IGNORED_DIRS) + "\n")
        self.write("README.md", HEADER + "\nbody\n")
        self.git("add", ".gitignore", "README.md")
        self.git("commit", "-q", "-m", "base")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        (root.parent / "deny.json").write_text(json.dumps(SYNTHETIC), encoding="utf-8")
        self.deny_path = root.parent / "deny.json"

    def git(self, *args: str, env: dict[str, str] | None = None) -> str:
        """Git."""
        done = subprocess.run(
            ["git", "-C", str(self.root), *args],
            check=True,
            capture_output=True,
            text=True,
            env=env or self.env,
        )
        return done.stdout

    def write(self, rel: str, text: str) -> None:
        """Write."""
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, *paths: str, message: str = "change", email: str = NOREPLY) -> None:
        """Commit."""
        self.git("add", *paths)
        self.git("commit", "-q", "-m", message, env={**self.env, "GIT_AUTHOR_EMAIL": email})


@pytest.fixture(name="repo")
def _repo(tmp_path: Path) -> Repo:
    """Repo."""
    root = tmp_path / "work"
    root.mkdir()
    return Repo(root)


def _rules(findings: list) -> list[str]:
    """Rules."""
    return sorted({f.rule for f in findings})


def test_a_clean_range_has_no_findings(repo: Repo) -> None:
    """A clean range has no findings."""
    repo.write("docs/a.md", HEADER + "\nclean text\n")
    repo.commit("docs/a.md")
    assert cps.check_range(repo.root, "origin/main", _deny(), NO_ALLOW) == []


def test_range_reports_a_planted_line_with_file_and_line_number_but_not_the_text(
    repo: Repo,
) -> None:
    """Range reports a planted line with file and line number but not the text."""
    repo.write("docs/a.md", HEADER + "\nok\ncd zorblax-secret-place\n")
    repo.commit("docs/a.md")
    found = cps.check_range(repo.root, "origin/main", _deny(), NO_ALLOW)
    assert [(f.rule, f.where) for f in found] == [("apex", "docs/a.md:6")]
    assert "zorblax" not in str(found[0])


def test_range_only_judges_added_lines_not_old_ones(repo: Repo) -> None:
    """Range only judges added lines not old ones."""
    repo.write("old.md", HEADER + "\nzorblax\n")
    repo.git("add", "old.md")
    repo.git("commit", "-q", "-m", "pre-existing")
    repo.git("update-ref", "refs/remotes/origin/main", "HEAD")
    repo.write("old.md", HEADER + "\nzorblax\nand a new clean line\n")
    repo.commit("old.md")
    assert cps.check_range(repo.root, "origin/main", _deny(), NO_ALLOW) == []


def test_an_allowlisted_added_line_is_accepted(repo: Repo, tmp_path: Path) -> None:
    """An allowlisted added line is accepted."""
    repo.write("docs/a.md", HEADER + "\nzorblax is named here on purpose\n")
    repo.commit("docs/a.md")
    allow = cps.load_allowlist(
        _write_allow(
            tmp_path / "a.json", [_entry("apex", "docs/a.md", "zorblax is named here on purpose")]
        )
    )
    assert cps.check_range(repo.root, "origin/main", _deny(), allow) == []


def test_a_trailer_in_any_commit_is_reported_with_its_sha(repo: Repo) -> None:
    """A trailer in any commit is reported with its sha."""
    repo.write("a.txt", "x")
    repo.commit("a.txt", message="subject\n\nSigned-Off-By-Bot: x")
    repo.write("b.txt", "y")
    repo.commit("b.txt", message="other\n\nMade with bot")
    found = [
        f
        for f in cps.check_range(repo.root, "origin/main", _deny(), NO_ALLOW)
        if f.rule == "trailer"
    ]
    assert len(found) == 2 and all(len(f.where) >= 7 for f in found)


def test_an_author_other_than_the_noreply_address_is_reported(repo: Repo) -> None:
    """An author other than the noreply address is reported."""
    repo.write("a.txt", "x")
    repo.commit("a.txt", email="someone@example.test")
    found = cps.check_range(repo.root, "origin/main", _deny(), NO_ALLOW)
    assert _rules(found) == ["author"] and "someone@example.test" in found[0].detail


@pytest.mark.parametrize("directory", sorted(cps.IGNORED_DIRS_NAMES))
def test_a_file_under_a_cache_directory_is_refused_in_a_range(repo: Repo, directory: str) -> None:
    """A file under a cache directory is refused in a range."""
    repo.write(f"{directory}/x/leak.txt", "data")
    repo.git("add", "-f", f"{directory}/x/leak.txt")
    repo.git("commit", "-q", "-m", "oops")
    assert "cache" in _rules(cps.check_range(repo.root, "origin/main", _deny(), NO_ALLOW))


def test_new_files_need_the_licence_header_except_data_empty_and_fixture_files(repo: Repo) -> None:
    """New files need the licence header except data empty and fixture files."""
    repo.write("scripts/bare.py", "print(1)\n")
    repo.write("scripts/good.py", "# " + HEADER.replace("\n", "\n# ") + "\nprint(1)\n")
    repo.write("docs/bare.md", "no header\n")
    repo.write("data/x.csv", "a,b\n1,2\n")
    repo.write("data/x.json", "{}\n")
    repo.write("src/pkg/py.typed", "")
    repo.write("tests/fixtures/x/plan.md", "fixture without a header\n")
    repo.write("scripts/public_surface_allowlist.json", "{}\n")
    repo.write("n/bare.ipynb", json.dumps({"cells": [], "metadata": {}}))
    repo.write(
        "n/good.ipynb",
        json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "markdown",
                        "source": [
                            "*Proprietary. SPDX-License-Identifier: LicenseRef-Proprietary*"
                        ],
                    }
                ],
                "metadata": {},
            }
        ),
    )
    paths = [
        "scripts/bare.py",
        "scripts/good.py",
        "docs/bare.md",
        "data/x.csv",
        "data/x.json",
        "src/pkg/py.typed",
        "tests/fixtures/x/plan.md",
        "scripts/public_surface_allowlist.json",
        "n/bare.ipynb",
        "n/good.ipynb",
    ]
    repo.commit(*paths)
    found = cps.check_range(repo.root, "origin/main", _deny(), NO_ALLOW)
    assert sorted(f.where for f in found if f.rule == "header") == [
        "docs/bare.md",
        "n/bare.ipynb",
        "scripts/bare.py",
    ]


def test_a_header_missing_one_of_the_three_lines_is_flagged(repo: Repo) -> None:
    """A header missing one of the three lines is flagged."""
    repo.write(
        "a.py",
        "# © 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.\n"
        "# SPDX-License-Identifier: LicenseRef-Proprietary\n",
    )
    repo.commit("a.py")
    found = [
        f
        for f in cps.check_range(repo.root, "origin/main", _deny(), NO_ALLOW)
        if f.rule == "header"
    ]
    assert len(found) == 1 and "exclusively licensed" in found[0].detail


def test_an_unknown_base_ref_is_an_error_not_a_pass(repo: Repo) -> None:
    """An unknown base ref is an error not a pass."""
    with pytest.raises(cps.SurfaceError, match="not a known"):
        cps.check_range(repo.root, "origin/does-not-exist", _deny(), NO_ALLOW)


def test_git_failures_are_surface_errors(tmp_path: Path) -> None:
    """Git failures are surface errors."""
    with pytest.raises(cps.SurfaceError, match="failed"):
        cps.check_staged(tmp_path, _deny(), NO_ALLOW)


# --- staged mode -----------------------------------------------------------------
def test_staged_refuses_a_cache_file_and_a_planted_line_but_not_unstaged_ones(repo: Repo) -> None:
    """Staged refuses a cache file and a planted line but not unstaged ones."""
    repo.write(".hypothesis/constants/abc", "data")
    repo.write("docs/ok.md", HEADER + "\nzorblax\n")
    repo.write("docs/unstaged.md", "cd /Users/x\n")
    repo.git("add", "-f", ".hypothesis/constants/abc")
    repo.git("add", "docs/ok.md")
    found = cps.check_staged(repo.root, _deny(), NO_ALLOW)
    assert _rules(found) == ["apex", "cache"]
    assert all("unstaged" not in f.where for f in found)


def test_staged_with_nothing_staged_is_clean(repo: Repo) -> None:
    """Staged with nothing staged is clean."""
    assert cps.check_staged(repo.root, _deny(), NO_ALLOW) == []


# --- .gitignore ------------------------------------------------------------------
def test_gitignore_must_list_every_cache_directory(repo: Repo) -> None:
    """Gitignore must list every cache directory."""
    assert cps.check_ignores(repo.root) == []
    repo.write(".gitignore", ".hypothesis/\n")
    missing = cps.check_ignores(repo.root)
    assert {f.where for f in missing} == {d for d in cps.IGNORED_DIRS if d != ".hypothesis/"}
    (repo.root / ".gitignore").unlink()
    assert len(cps.check_ignores(repo.root)) == len(cps.IGNORED_DIRS)


# --- tree mode and the allowlist ----------------------------------------------------
def test_tree_with_no_allowlist_reports_every_hit(repo: Repo) -> None:
    """Tree with no allowlist reports every hit."""
    repo.write("docs/a.md", "zorblax\n/Users/x\n")
    repo.git("add", "docs/a.md")
    found, notes = cps.check_tree(repo.root, _deny(), NO_ALLOW)
    assert sorted((f.rule, f.where) for f in found) == [
        ("apex", "docs/a.md:1"),
        ("path", "docs/a.md:2"),
    ]
    assert notes == []


def test_an_allowlisted_line_is_accepted_and_counted_and_a_changed_line_is_not(
    repo: Repo, tmp_path: Path
) -> None:
    """An allowlisted line is accepted and counted and a changed line is not."""
    repo.write("docs/a.md", "zorblax is quoted here\n")
    repo.git("add", "docs/a.md")
    allow = cps.load_allowlist(
        _write_allow(
            tmp_path / "a.json",
            [_entry("apex", "docs/a.md", "zorblax is quoted here", pending_owner_ruling=True)],
        )
    )
    found, notes = cps.check_tree(repo.root, _deny(), allow)
    assert found == [] and notes == [
        "allowlist: 1 entry used, each with a reason; 1 pending an owner ruling"
    ]
    repo.write("docs/a.md", "zorblax is quoted here, edited\n")
    found, _ = cps.check_tree(repo.root, _deny(), allow)
    assert sorted((f.rule, f.where) for f in found) == [
        ("allowlist", "docs/a.md"),
        ("apex", "docs/a.md:1"),
    ]


def test_a_stale_allowlist_entry_is_itself_a_finding(repo: Repo, tmp_path: Path) -> None:
    """A stale allowlist entry is itself a finding."""
    allow = cps.load_allowlist(_write_allow(tmp_path / "a.json", [_entry("apex", "gone.md", "x")]))
    found, _ = cps.check_tree(repo.root, _deny(), allow)
    assert [(f.rule, f.where) for f in found] == [("allowlist", "gone.md")]


def test_the_allowlist_is_keyed_by_rule_so_one_rule_cannot_excuse_another(
    repo: Repo, tmp_path: Path
) -> None:
    """The allowlist is keyed by rule so one rule cannot excuse another."""
    repo.write("docs/a.md", "zorblax and /Users/x\n")
    repo.git("add", "docs/a.md")
    allow = cps.load_allowlist(
        _write_allow(tmp_path / "a.json", [_entry("apex", "docs/a.md", "zorblax and /Users/x")])
    )
    found, _ = cps.check_tree(repo.root, _deny(), allow)
    assert [f.rule for f in found] == ["path"]


def test_binary_and_deleted_files_are_skipped_not_crashed_on(repo: Repo) -> None:
    """Binary and deleted files are skipped not crashed on."""
    (repo.root / "blob.bin").write_bytes(b"\x00\x01zorblax\x00")
    repo.write("gone.md", "zorblax\n")
    repo.git("add", "blob.bin", "gone.md")
    (repo.root / "gone.md").unlink()
    assert cps.check_tree(repo.root, _deny(), NO_ALLOW)[0] == []


def test_suggestions_carry_the_hash_and_never_the_text(repo: Repo) -> None:
    """Suggestions carry the hash and never the text."""
    repo.write("docs/a.md", "zorblax is here\n")
    repo.git("add", "docs/a.md")
    out = cps.suggest_allowlist(repo.root, _deny(), NO_ALLOW)
    assert out[0]["line_sha256"] == cps.line_hash("zorblax is here") and out[0]["reason"] == ""
    assert "zorblax" not in json.dumps(out)


# --- command line ---------------------------------------------------------------------
def test_main_exit_codes_and_that_output_never_echoes_a_match(
    repo: Repo, capsys: pytest.CaptureFixture[str]
) -> None:
    """Main exit codes and that output never echoes a match."""
    base = [
        "--root",
        str(repo.root),
        "--denylist",
        str(repo.deny_path),
        "--allowlist",
        str(repo.root.parent / "allow.json"),
    ]
    assert cps.main([*base, "--tree"]) == 0
    repo.write("docs/a.md", HEADER + "\nzorblax\n")
    repo.commit("docs/a.md")
    capsys.readouterr()
    assert cps.main([*base, "--range", "origin/main"]) == 1
    out = capsys.readouterr().out
    assert "apex" in out and "zorblax" not in out
    assert cps.main([*base, "--range", "origin/nope"]) == 2
    assert "not a known" in capsys.readouterr().err
    assert cps.main(["--root", str(repo.root)]) == 2


def test_main_suggest_prints_json_and_exits_zero(
    repo: Repo, capsys: pytest.CaptureFixture[str]
) -> None:
    """Main suggest prints json and exits zero."""
    repo.write("docs/a.md", "zorblax\n")
    repo.git("add", "docs/a.md")
    base = ["--root", str(repo.root), "--denylist", str(repo.deny_path)]
    assert cps.main([*base, "--suggest-allowlist"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["rule"] == "apex"


def test_main_staged_and_remaining_edges(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    """Main staged and remaining edges."""
    base = [
        "--root",
        str(repo.root),
        "--denylist",
        str(repo.deny_path),
        "--allowlist",
        str(repo.root.parent / "none.json"),
    ]
    assert cps.main([*base, "--staged"]) == 0
    assert (
        cps.main(
            [
                "--root",
                str(repo.root / "missing-dir"),
                "--denylist",
                str(repo.deny_path),
                "--staged",
            ]
        )
        == 2
    )
    capsys.readouterr()
    assert cps.main([*base, "--tree"]) == 0
    assert "clean" in capsys.readouterr().out


# ---------------------------------------------------------------------------------------
# the real repository (no denylist needed)
# ---------------------------------------------------------------------------------------
def test_the_baseline_file_is_gone_and_no_name_pattern_remains_in_the_checker() -> None:
    """The baseline file is gone and no name pattern remains in the checker."""
    assert not (REPO / "scripts" / "public_surface_baseline.json").exists()
    source = (REPO / "scripts" / "check_public_surface.py").read_text(encoding="utf-8")
    assert "baseline" not in source.lower().replace("baseline.", "")
    assert "RULES" not in source and "TRAILER" not in source


def test_every_allowlist_entry_has_a_reason_and_matches_a_line_in_its_file() -> None:
    """Every allowlist entry has a reason and matches a line in its file."""
    allow = cps.load_allowlist(REPO / "scripts" / "public_surface_allowlist.json")
    assert allow.entries, (
        "the allowlist is empty; if nothing needs allowing, delete the file and this test"
    )
    for entry in allow.entries.values():
        assert len(entry.reason) > 20, f"{entry.file}: reason too thin to be a reason"
        lines = (REPO / entry.file).read_text(encoding="utf-8", errors="replace").splitlines()
        assert entry.line_sha256 in {cps.line_hash(line) for line in lines}, (
            f"{entry.file}: no line hashes to this entry; it is stale"
        )
    kinds = {e.rule for e in allow.entries.values()}
    assert kinds <= {"path", "tooling", "unpublished"}


def test_make_check_and_pre_commit_run_the_checker_and_ci_supplies_the_denylist() -> None:
    """Make check and pre commit run the checker and ci supplies the denylist."""
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    assert "check_public_surface.py" in makefile and cps.DENYLIST_ENV in makefile
    check_line = next(line for line in makefile.splitlines() if line.startswith("check:"))
    assert "surface" in check_line
    hooks = (REPO / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "check_public_surface.py --staged" in hooks
    workflow = (REPO / ".github" / "workflows" / "notebook-release-gates.yml").read_text(
        encoding="utf-8"
    )
    assert "KRL_SURFACE_DENYLIST_JSON" in workflow and "secrets." in workflow


def test_git_missing_from_the_machine_is_a_surface_error_not_a_crash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If git cannot be run at all, the check reports it and exits 2."""

    def boom(*_args: object, **_kwargs: object) -> None:
        """Boom."""
        raise FileNotFoundError(2, "No such file or directory")

    monkeypatch.setattr(cps.subprocess, "run", boom)
    with pytest.raises(cps.SurfaceError, match="git could not be run"):
        cps.check_staged(tmp_path, _deny(), NO_ALLOW)
