# © 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
# SPDX-License-Identifier: LicenseRef-Proprietary
"""Gate 11 — a document may only point at things that exist.

This gate began as a check on `docs/index.rst`, whose twelve-entry Sphinx
toctree listed twelve pages, **none of which existed**. Nothing caught it,
because nothing built the docs in CI and a missing toctree entry is a warning
rather than an error unless Sphinx runs with `-W`. A reader would have found out
by clicking.

`docs/index.rst` was removed with the rest of the unbuilt Sphinx scaffolding
(ADR 0007) -- at which point this gate skipped every test and reported green.
A gate whose subject disappears and which then passes is a false green, which is
the failure class this corpus exists to refuse. So it was rewritten against the
surface that is actually here: every relative link and inline path reference in
every tracked Markdown file.

That is the check worth having. The 2026-09-18 reduction left dangling references
to `SPEC.md`, `CALIBRATION_REQUIRED.md`, `policy/` and `the showcase sub-project/` scattered
across prose, and they were found by hand. This finds the next ones.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT: Final = Path(__file__).resolve().parent.parent

#: `[text](target)` where the target is not a URL, a mail link or a bare anchor.
MD_LINK: Final = re.compile(r"\[[^\]]*\]\(\s*(?!https?://|mailto:|#)([^)\s]+)")

#: A repo-relative path named in backticks, e.g. `projects/…` or `tests/x.py`.
#: Deliberately narrow: a real path segment plus a known extension, or a directory
#: with a trailing slash. Prose like `--cov` or `B19013_001E` must not match.
INLINE_PATH: Final = re.compile(
    r"`((?:[\w.-]+/)+[\w.-]*(?:\.(?:py|md|ipynb|toml|ini|yml|yaml|json|jsonl|cfg|txt|rst|csv))|"
    r"(?:[\w.-]+/){2,})`"
)


#: Root files that are prose without an extension. LICENSE referred to a
#: `notebooks/` tree for four weeks after that tree was removed, because this
#: gate scanned `*.md` and LICENSE is not one.
EXTENSIONLESS_PROSE: Final = ("LICENSE", "CITATION", "NOTICE")


def _tracked_markdown() -> list[Path]:
    out = subprocess.check_output(["git", "ls-files", "*.md", *EXTENSIONLESS_PROSE],
                                  cwd=REPO_ROOT, text=True)
    return [REPO_ROOT / p for p in out.split("\n") if p]


def _resolves(doc: Path, target: str) -> bool:
    target = target.split("#", 1)[0].strip()
    if not target:
        return True
    for base in (doc.parent, REPO_ROOT):
        p = (base / target)
        if p.exists():
            return True
        # a wiki-style link with no extension
        if any((base / f"{target}{ext}").exists() for ext in (".md", ".rst", ".txt")):
            return True
    return False


def test_there_is_something_to_check() -> None:
    """A gate that passes because it found no input is the bug it replaced.

    Pinned to a link that is certainly there rather than to a count, because a
    count is a fact about documentation style: this corpus links sparsely and
    names paths in backticks instead, so a count floor set from one day's prose
    would fail the next time a document is tightened. What must hold is that both
    extractors still find what is in front of them.
    """
    docs = _tracked_markdown()
    assert len(docs) >= 8, f"only {len(docs)} tracked markdown files found; parser broken?"

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "LICENSE" in MD_LINK.findall(readme), (
        "the relative-link parser no longer finds README.md's link to LICENSE, "
        "which is present; the pattern is broken and every link test is vacuous"
    )
    paths = sum(len(INLINE_PATH.findall(d.read_text(encoding="utf-8"))) for d in docs)
    assert paths >= 20, (
        f"the inline-path parser found only {paths} backticked paths across "
        f"{len(docs)} documents; it is matching nothing and the check is vacuous"
    )


@pytest.mark.parametrize("doc", _tracked_markdown(), ids=lambda p: str(p.name))
def test_every_relative_link_resolves(doc: Path) -> None:
    text = doc.read_text(encoding="utf-8")
    broken = sorted({t for t in MD_LINK.findall(text) if not _resolves(doc, t)})
    rel = doc.relative_to(REPO_ROOT)
    assert not broken, f"{rel} links to targets that do not exist: {broken}"


#: Records may name paths that no longer exist -- that is what a record is for.
#: Same rule the licence gate uses, and for the same reason.
RECORD_TREES: Final = ("DECISIONS/", "docs/audits/")
RECORD_FILES: Final = ("docs/migration.md", "docs/source-map.md")


@pytest.mark.parametrize("doc", _tracked_markdown(), ids=lambda p: str(p.name))
def test_every_backticked_path_exists(doc: Path) -> None:
    """Prose that names a file is a claim about the repository like any other."""
    rel_s = str(doc.relative_to(REPO_ROOT))
    if rel_s.startswith(RECORD_TREES) or rel_s in RECORD_FILES:
        pytest.skip(f"{rel_s} is a record; naming a retired path is its job")
    text = doc.read_text(encoding="utf-8")
    broken = sorted({
        t for t in INLINE_PATH.findall(text)
        if "..." not in t                       # an elided path, not a real one
        and not re.match(r"^[\w-]+\.(?:gov|com|org|edu|net|io|dev)/", t)  # a host
        and not _resolves(doc, t)
    })
    rel = doc.relative_to(REPO_ROOT)
    assert not broken, (
        f"{rel} refers to paths that do not exist: {broken}. Either the path is "
        "stale or the prose describes a repository other than this one."
    )
