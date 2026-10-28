#!/usr/bin/env python3
"""Refuse anything that must not reach a public, proprietary repository.

This is the engagement's public-surface rule as code. It checks:

* ``path``      absolute or sandbox paths (``/home/runner`` is a CI path and allowed);
* the **named** rules  -- which names count, and what an attribution trailer looks
                like, are *not in this repository*. They are read from a private
                denylist (below), because a public file listing what must never be
                published would publish it;
* ``trailer``   attribution trailers in a commit message: a generic rule always, and the
                owner's own pattern from the denylist when there is one;
* ``author``    any author address other than the owner's noreply address;
* ``header``    a new file without the licence header;
* ``cache``     a file under a tool-cache directory, which holds local paths;
* ``ignore``    a tool-cache directory missing from ``.gitignore``;
* ``allowlist`` an allowlist entry that no longer matches any line.

The denylist is a JSON file named by the environment variable ``KRL_SURFACE_DENYLIST``.
It is the reader's own file; there is no default location and this repository stores no
copy. **If it is absent or unusable the check exits with status 2 and checks nothing**: a
missing denylist is never read as a pass.

``--public-rules`` is the one way to run without it, and exists for CI, which holds no
secret and no private list. It checks only what needs no private knowledge -- paths, cache
directories, licence headers, authors, and a generic attribution-trailer rule (a
``Co-Authored-By:`` line or a ``Generated with`` line) -- and says in its output that the
private rules were not run. It is never a substitute for the local run before publishing.
Findings name a rule and a ``file:line``; they never print the text that matched, so a
log cannot become a copy of the list.

Modes (combine freely; at least one is required)::

    --tree              every tracked file; hits must be on the allowlist
    --range BASE        what BASE..HEAD adds: lines, files, commit messages, authors
    --staged            what is staged now (a pre-commit hook)
    --suggest-allowlist print, for every unallowlisted tree hit, an entry to complete
    --public-rules      with the above: run only the rules that need no private list

The allowlist (``scripts/public_surface_allowlist.json``) holds one entry per line that
legitimately matches, keyed by rule, file and the SHA-256 of the stripped line, with a
reason. It is verified, not trusted: an entry whose line has gone is itself a finding,
and entries marked ``pending_owner_ruling`` are counted in the output every run.

Exit status: 0 clean, 1 findings, 2 usage error, unusable denylist, or an unusable git
ref (fail closed: an unknown base is never read as "nothing changed").

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = REPO_ROOT / "scripts" / "public_surface_allowlist.json"
DENYLIST_ENV = "KRL_SURFACE_DENYLIST"
NOREPLY = "186650653+bcdelodx@users.noreply.github.com"

#: Tool caches hold absolute local paths and must be git-ignored and never committed.
IGNORED_DIRS = (".hypothesis/", ".pytest_cache/", ".mypy_cache/", ".ruff_cache/", "__pycache__/")
IGNORED_DIRS_NAMES = frozenset(d.rstrip("/") for d in IGNORED_DIRS)
_CACHE_PATH = re.compile(
    r"(^|/)(" + "|".join(re.escape(n) for n in sorted(IGNORED_DIRS_NAMES)) + r")/"
)

#: A file-sync tool names its conflict copies "name 2.ext"; they are stale copies, never content.
SYNC_DUPLICATE = re.compile(r" [0-9]+(\.[A-Za-z0-9]+)?$")

#: The path rule is about *shape*, not names, so it lives here. The checker and its test
#: plant such paths on purpose, and are exempt from this one rule by exact path.
PATH_RULE = re.compile(r"/Users/|/home/(?!runner)|/sessions/|/mnt/")
PATH_RULE_EXEMPT = frozenset(
    {"scripts/check_public_surface.py", "tests/test_check_public_surface.py"}
)
ALLOWLIST_FILE_EXEMPT = frozenset({"scripts/public_surface_allowlist.json"})

#: A trailer anyone can recognise without a private list: a Co-Authored-By line, or a line
#: saying the commit was generated with something.
GENERIC_TRAILER = re.compile(r"^\s*co-authored-by:|\bgenerated with\b", re.I | re.M)
PRIVATE_RULES_NOTE = (
    "private rules were NOT run (--public-rules): name patterns and the private trailer "
    "pattern were not checked; run without it, with KRL_SURFACE_DENYLIST set, before publishing"
)

HEADER_SUFFIXES = frozenset({".py", ".md", ".sh", ".yml", ".yaml", ".toml", ".ini", ".cfg"})
HEADER_LINES = (
    "© 2026 Deloatch, Williams, Faison & Parker, LLLP",
    "exclusively licensed to Telosyn, Inc.",
    "SPDX-License-Identifier: LicenseRef-Proprietary",
)
HEADER_WINDOW = 6000
NOTEBOOK_MARK = "SPDX-License-Identifier: LicenseRef-Proprietary"


class SurfaceError(RuntimeError):
    """The check could not be run (no denylist, bad ref, not a repository); never a pass."""


@dataclass(frozen=True)
class Finding:
    """One thing that must not be committed. ``detail`` never contains matched text."""

    rule: str
    where: str
    detail: str = ""

    def __str__(self) -> str:
        return f"{self.rule}: {self.where}" + (f": {self.detail}" if self.detail else "")


@dataclass(frozen=True)
class NamedRule:
    """A denylist rule: a pattern plus the structural exemptions the owner attached."""

    name: str
    pattern: re.Pattern[str]
    exempt_paths: frozenset[str] = frozenset()
    exempt_suffixes: tuple[str, ...] = ()
    ordinary: re.Pattern[str] | None = None


@dataclass(frozen=True)
class Denylist:
    """The private list: named rules and the attribution-trailer pattern."""

    rules: tuple[NamedRule, ...]
    trailer: re.Pattern[str]


@dataclass(frozen=True)
class AllowEntry:
    """One legitimately matching line, keyed by rule, file and the hash of the line."""

    rule: str
    file: str
    line_sha256: str
    reason: str
    pending: bool = False

    @property
    def key(self) -> tuple[str, str, str]:
        """Identity of the entry: rule, file and the hash of the line."""
        return (self.rule, self.file, self.line_sha256)


@dataclass
class Allowlist:
    """Parsed allowlist, with a record of which entries were used."""

    entries: dict[tuple[str, str, str], AllowEntry] = field(default_factory=dict)


# ---------------------------------------------------------------------- loading
def _compile(raw: str, flags: str, what: str) -> re.Pattern[str]:
    if flags not in ("", "i"):
        raise SurfaceError(f"denylist: {what} has unsupported flags")
    try:
        return re.compile(raw, re.I if flags == "i" else 0)
    except re.error:
        raise SurfaceError(f"denylist: {what} is not a valid pattern") from None


def parse_denylist(doc: Any) -> Denylist:
    """Validate and compile a denylist document. Error text never echoes a pattern."""
    if not isinstance(doc, dict) or doc.get("version") != 1:
        raise SurfaceError("denylist: expected a JSON object with version 1")
    rules_doc = doc.get("rules")
    if not isinstance(rules_doc, dict) or not rules_doc:
        raise SurfaceError("denylist: 'rules' must be a non-empty object")
    rules: list[NamedRule] = []
    for name, body in rules_doc.items():
        if not isinstance(body, dict) or not isinstance(body.get("pattern"), str):
            raise SurfaceError(f"denylist: rule {name!r} needs a string 'pattern'")
        ordinary = body.get("ordinary_phrases")
        rules.append(
            NamedRule(
                name=name,
                pattern=_compile(body["pattern"], body.get("flags", ""), f"rule {name!r}"),
                exempt_paths=frozenset(body.get("exempt_paths", [])),
                exempt_suffixes=tuple(body.get("exempt_suffixes", [])),
                ordinary=_compile(ordinary, "i", f"rule {name!r} ordinary_phrases")
                if ordinary
                else None,
            )
        )
    trailer = doc.get("trailer")
    if not isinstance(trailer, dict) or not isinstance(trailer.get("pattern"), str):
        raise SurfaceError("denylist: 'trailer' needs a string 'pattern'")
    return Denylist(tuple(rules), _compile(trailer["pattern"], trailer.get("flags", ""), "trailer"))


def load_denylist(path: str | os.PathLike[str] | None = None) -> Denylist:
    """Read the private denylist from ``path`` or ``$KRL_SURFACE_DENYLIST``; raise if absent."""
    chosen = str(path) if path else os.environ.get(DENYLIST_ENV, "")
    if not chosen:
        raise SurfaceError(
            f"no denylist: {DENYLIST_ENV} is not set. The name patterns are private and are not "
            "in this repository; without them nothing can be checked, so this is an error."
        )
    file = Path(chosen).expanduser()
    if not file.is_file():
        raise SurfaceError(f"no denylist: {DENYLIST_ENV} points at a file that does not exist")
    try:
        doc = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise SurfaceError("denylist: the file is not readable JSON") from None
    return parse_denylist(doc)


def load_allowlist(path: Path) -> Allowlist:
    """Read the allowlist; a missing file is an empty list, a malformed entry is an error."""
    allow = Allowlist()
    if not path.exists():
        return allow
    doc = json.loads(path.read_text(encoding="utf-8"))
    for raw in doc.get("entries", []):
        reason = str(raw.get("reason", "")).strip()
        if not reason:
            raise SurfaceError(f"allowlist: an entry for {raw.get('file')!r} has no reason")
        if not re.fullmatch(r"[0-9a-f]{64}", str(raw.get("line_sha256", ""))):
            raise SurfaceError(f"allowlist: an entry for {raw.get('file')!r} has no line hash")
        entry = AllowEntry(
            raw["rule"],
            raw["file"],
            raw["line_sha256"],
            reason,
            bool(raw.get("pending_owner_ruling", False)),
        )
        if entry.key in allow.entries:
            raise SurfaceError(f"allowlist: duplicate entry for {entry.file!r}")
        allow.entries[entry.key] = entry
    return allow


def line_hash(line: str) -> str:
    """SHA-256 of a line with surrounding whitespace removed (what the allowlist keys on)."""
    return hashlib.sha256(line.strip().encode("utf-8")).hexdigest()


# --------------------------------------------------------------------- scanning
def scan_text(path: str, text: str, deny: Denylist | None) -> list[tuple[str, int, str]]:
    """``(rule, line number, line hash)`` for each line of ``text`` that breaks a content rule.

    With ``deny=None`` only the path rule runs (the public rules).
    """
    hits: list[tuple[str, int, str]] = []
    for number, line in enumerate(text.splitlines(), 1):
        if path not in PATH_RULE_EXEMPT and PATH_RULE.search(line):
            hits.append(("path", number, line_hash(line)))
        for rule in deny.rules if deny else ():
            if path in rule.exempt_paths or path.endswith(rule.exempt_suffixes):
                continue
            if rule.pattern.search(line) and not (rule.ordinary and rule.ordinary.search(line)):
                hits.append((rule.name, number, line_hash(line)))
    return hits


def _apply_allowlist(
    path: str, hits: list[tuple[str, int, str]], allow: Allowlist, used: set[tuple[str, str, str]]
) -> list[Finding]:
    found: list[Finding] = []
    for rule, number, digest in hits:
        key = (rule, path, digest)
        if key in allow.entries:
            used.add(key)
        else:
            found.append(Finding(rule, f"{path}:{number}"))
    return found


# -------------------------------------------------------------------------- git
ARCHIVE_SUFFIXES = (".xlsx", ".docx", ".pptx", ".xlsm", ".zip")


def _git_bytes(root: Path, *args: str) -> bytes:
    try:
        done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    except OSError as exc:
        raise SurfaceError(f"git could not be run: {exc.strerror}") from None
    return done.stdout if done.returncode == 0 else b""


def archive_hits(name: str, data: bytes, deny: Denylist | None) -> dict[str, list[tuple[str, int, str]]]:
    """Content-rule hits in the text parts of a zip-based file (a workbook, document or archive).

    Each text member (XML, text, CSV, JSON) is scanned as ``<file>!<member>``; a member that is not valid
    text, or an archive that will not open, is skipped here and left to the path and size rules.
    """
    out: dict[str, list[tuple[str, int, str]]] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for member in z.namelist():
                if not member.lower().endswith((".xml", ".txt", ".csv", ".json", ".rels", ".md")):
                    continue
                hits = scan_text(f"{name}!{member}", z.read(member).decode("utf-8", "replace"), deny)
                if hits:
                    out[f"{name}!{member}"] = hits
    except (zipfile.BadZipFile, OSError):
        return {}
    return out


def _git(root: Path, *args: str, check: bool = True) -> str:
    try:
        done = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",  # a staged workbook or image is bytes, not text; do not crash on it
            check=False,
        )
    except OSError as exc:
        raise SurfaceError(f"git could not be run: {exc.strerror}") from None
    if check and done.returncode != 0:
        raise SurfaceError(f"git {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout


def _require_ref(root: Path, ref: str) -> None:
    done = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        raise SurfaceError(
            f"{ref!r} is not a known commit in this repository; the range cannot be checked "
            "(fetch it, or fix the name). An unknown base is never read as 'no changes'."
        )


def _added_lines(diff: str) -> list[tuple[str, int, str]]:
    """``(path, line number, text)`` for every added line of a ``-U0`` unified diff."""
    out: list[tuple[str, int, str]] = []
    path = ""
    number = 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else ""
        elif line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            number = int(match.group(1)) if match else 0
        elif line.startswith("+") and path:
            out.append((path, number, line[1:]))
            number += 1
    return out


def _content_findings(diff: str, deny: Denylist | None, allow: Allowlist) -> list[Finding]:
    by_file: dict[str, list[tuple[int, str]]] = {}
    for path, number, text in _added_lines(diff):
        by_file.setdefault(path, []).append((number, text))
    found: list[Finding] = []
    for path, lines in by_file.items():
        for number, text in lines:
            hits = [(r, number, h) for r, _, h in scan_text(path, text + "\n", deny)]
            found += _apply_allowlist(path, hits, allow, set())
    return found


def _blob(root: Path, rev: str, path: str) -> str:
    return _git(root, "show", f"{rev}:{path}", check=False)


def _header_findings(root: Path, paths: list[str], rev: str) -> list[Finding]:
    found: list[Finding] = []
    for path in sorted(paths):
        if path.startswith("tests/fixtures/") or path in ALLOWLIST_FILE_EXEMPT:
            continue  # fixtures are data; their bytes are often digest-pinned
        text = _blob(root, rev, path)
        if not text:
            continue  # empty marker files (py.typed) carry nothing to header
        suffix = PurePosixPath(path).suffix
        if suffix == ".ipynb":
            if NOTEBOOK_MARK not in text:
                found.append(Finding("header", path, f"missing {NOTEBOOK_MARK!r}"))
        elif suffix in HEADER_SUFFIXES:
            window = text[:HEADER_WINDOW]
            missing = [line for line in HEADER_LINES if line not in window]
            if missing:
                found.append(Finding("header", path, "missing " + "; ".join(missing)))
    return found


def _path_findings(names: list[str]) -> list[Finding]:
    found = [
        Finding("cache", n, "a tool cache holds local paths and must not be committed")
        for n in names
        if _CACHE_PATH.search(n)
    ]
    found += [
        Finding("sync-duplicate", n, "a name ending in a space and a number is a file-sync copy")
        for n in names
        if SYNC_DUPLICATE.search(n)
    ]
    return found


def check_range(root: Path, base: str, deny: Denylist | None, allow: Allowlist) -> list[Finding]:
    """What ``base..HEAD`` adds: content, files, headers, messages and authors."""
    _require_ref(root, base)
    span = f"{base}..HEAD"
    diff = _git(root, "diff", "-U0", "--no-color", "--no-ext-diff", span)
    findings = _content_findings(diff, deny, allow)
    names = [
        n
        for n in _git(root, "diff", "--name-only", "--diff-filter=ACMR", "-z", span).split("\0")
        if n
    ]
    added = [
        n for n in _git(root, "diff", "--name-only", "--diff-filter=A", "-z", span).split("\0") if n
    ]
    findings += _path_findings(names)
    findings += _header_findings(root, added, "HEAD")
    for name in names:
        if name.lower().endswith(ARCHIVE_SUFFIXES):
            for member, hits in archive_hits(name, _git_bytes(root, "show", f"HEAD:{name}"), deny).items():
                findings += _apply_allowlist(member, hits, allow, set())
    log = _git(root, "log", "--format=%H%x00%ae%x00%B%x01", span)
    for record in (r.strip("\n") for r in log.split("\x01")):
        if not record:
            continue
        sha, email, message = record.split("\x00", 2)
        if GENERIC_TRAILER.search(message) or (deny and deny.trailer.search(message)):
            findings.append(Finding("trailer", sha[:12], "attribution trailer in the message"))
        if email != NOREPLY:
            findings.append(
                Finding("author", sha[:12], f"author {email!r} is not the noreply address")
            )
    return findings


def check_staged(root: Path, deny: Denylist | None, allow: Allowlist) -> list[Finding]:
    """What is staged right now: content, files and headers (no messages yet)."""
    diff = _git(root, "diff", "--cached", "-U0", "--no-color", "--no-ext-diff")
    findings = _content_findings(diff, deny, allow)
    names = [
        n
        for n in _git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split(
            "\0"
        )
        if n
    ]
    added = [
        n
        for n in _git(root, "diff", "--cached", "--name-only", "--diff-filter=A", "-z").split("\0")
        if n
    ]
    findings += _path_findings(names)
    findings += _header_findings(root, added, "")
    for name in names:
        if name.lower().endswith(ARCHIVE_SUFFIXES):
            for member, hits in archive_hits(name, _git_bytes(root, "show", f":{name}"), deny).items():
                findings += _apply_allowlist(member, hits, allow, set())
    return findings


def check_ignores(root: Path) -> list[Finding]:
    """``.gitignore`` must list every tool-cache directory."""
    path = root / ".gitignore"
    listed = set(path.read_text(encoding="utf-8").split()) if path.exists() else set()
    return [
        Finding("ignore", d, "not listed in .gitignore") for d in IGNORED_DIRS if d not in listed
    ]


# ------------------------------------------------------------------------- tree
def tree_hits(root: Path, deny: Denylist | None) -> dict[str, list[tuple[str, int, str]]]:
    """``{file: [(rule, line, line hash)]}`` over every tracked text file."""
    out: dict[str, list[tuple[str, int, str]]] = {}
    for name in filter(None, _git(root, "ls-files", "-z").split("\0")):
        file = root / name
        if not file.is_file():
            continue
        data = file.read_bytes()
        if name.lower().endswith(ARCHIVE_SUFFIXES):
            out.update(archive_hits(name, data, deny))
            continue
        if b"\x00" in data[:8000]:
            continue
        hits = scan_text(name, data.decode("utf-8", "replace"), deny)
        if hits:
            out[name] = hits
    return out


def check_tree(
    root: Path, deny: Denylist | None, allow: Allowlist
) -> tuple[list[Finding], list[str]]:
    """Unallowlisted hits and stale allowlist entries, plus a one-line summary of the allowlist."""
    findings: list[Finding] = _path_findings(
        [n for n in _git(root, "ls-files", "-z").split("\0") if n]
    )
    used: set[tuple[str, str, str]] = set()
    for name, hits in sorted(tree_hits(root, deny).items()):
        findings += _apply_allowlist(name, hits, allow, used)
    rules_run = {"path"} | ({r.name for r in deny.rules} if deny else set())
    for key, entry in sorted(allow.entries.items()):
        if key not in used and entry.rule in rules_run:  # an unrun rule cannot call its entry stale
            findings.append(
                Finding(
                    "allowlist",
                    entry.file,
                    f"entry for rule {entry.rule!r} matches no line (stale)",
                )
            )
    pending = sum(1 for e in allow.entries.values() if e.pending)
    notes = (
        [
            f"allowlist: {len(used)} entr{'y' if len(used) == 1 else 'ies'} used, each with a "
            f"reason; {pending} pending an owner ruling"
        ]
        if allow.entries
        else []
    )
    return findings, notes


def suggest_allowlist(root: Path, deny: Denylist | None, allow: Allowlist) -> list[dict[str, Any]]:
    """Entries to complete for every tree hit not yet allowed (reason left empty)."""
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for name, hits in sorted(tree_hits(root, deny).items()):
        for rule, number, digest in hits:
            key = (rule, name, digest)  # identical lines in one file share one entry
            if key not in allow.entries and key not in seen:
                seen.add(key)
                out.append(
                    {
                        "rule": rule,
                        "file": name,
                        "line_sha256": digest,
                        "reason": "",
                        "_line": number,
                    }
                )
    return out


# -------------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    ap.add_argument("--root", type=Path, default=REPO_ROOT)
    ap.add_argument("--denylist", type=Path, help=f"override ${DENYLIST_ENV}")
    ap.add_argument("--allowlist", type=Path, default=ALLOWLIST)
    ap.add_argument("--tree", action="store_true")
    ap.add_argument("--range", dest="base", metavar="BASE")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--suggest-allowlist", action="store_true")
    ap.add_argument("--public-rules", action="store_true", help="skip the private rules (CI)")
    args = ap.parse_args(argv)
    if not (args.tree or args.base or args.staged or args.suggest_allowlist):
        print(
            "choose at least one of --tree, --range BASE, --staged, --suggest-allowlist",
            file=sys.stderr,
        )
        return 2
    try:
        deny = None if args.public_rules else load_denylist(args.denylist)
        allow = load_allowlist(args.allowlist)
        if args.suggest_allowlist:
            print(json.dumps(suggest_allowlist(args.root, deny, allow), indent=1))
            return 0
        findings: list[Finding] = []
        notes: list[str] = []
        if args.tree:
            tree, notes = check_tree(args.root, deny, allow)
            findings += tree + check_ignores(args.root)
        if args.base:
            findings += check_range(args.root, args.base, deny, allow)
        if args.staged:
            findings += check_staged(args.root, deny, allow)
    except SurfaceError as exc:
        print(f"public-surface check could not run: {exc}", file=sys.stderr)
        return 2
    if args.public_rules:
        notes = [PRIVATE_RULES_NOTE, *notes]
    for note in notes:
        print(f"note: {note}")
    for finding in findings:
        print(finding)
    if findings:
        print(f"public-surface check: {len(findings)} finding(s)")
        return 1
    print("public-surface check: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
