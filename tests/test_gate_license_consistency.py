"""Gate 10 - one licence posture, stated the same way everywhere.

Every file this repository controls declares the same licence, and no document
describes permissions the licence withholds. The check covers SPDX banners and,
separately and more importantly, **prose**: a banner is a machine-readable claim
a lawyer reads, whereas "Yes! That's encouraged" is what a person acts on.

Prose is where this has failed twice. An identifier-driven sweep left four plain-
English grants standing because none of them contained an SPDX string. A later
sweep left five more inside a file that was excluded whole, and left ten of the
corpus's own notebooks advertising MIT and CC-BY-SA-4.0 in a markdown footer,
because the scan covered `.md`, `.rst` and `.txt` and notebooks are none of those.

So: notebooks are scanned, as markdown-cell source rather than whole-file, which
keeps vendored third-party banners in stored output from registering as grants
by this project. `DECISIONS/` and `docs/audits/` are exempt as classes, because
recording a finding is not making it. Nothing else is exempt. There is no
whole-file exclusion list, and `LICENCE_HISTORY_FILES` is empty: this repository
was never published, so no reader ever saw a retired declaration and no document
needs to explain one away. Prose states what is true; `DECISIONS/` records what
changed.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import re
import subprocess
import json
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT: Final = Path(__file__).resolve().parent.parent

#: No tree is excluded. The forensic corpus that used to sit here was removed
#: from the repository on 2026-09-18 (ADR 0007), which retired the only exclusion
#: this gate ever had.
EXCLUDED_TREES: Final[tuple[str, ...]] = ()

#: Files that quote a non-authoritative identifier as evidence.
EVIDENCE: Final[frozenset[str]] = frozenset({
    "DECISIONS/0001-dual-license-mit-code-cc-by-sa-content.md",
    #: README.md was on this list while it still quoted the old identifiers. The
    #: 2026-09-18 rewrite removed them, so it is checked like anything else --
    #: an exclusion that outlives its reason is just a blind spot.
    "tests/test_gate_license_consistency.py",
})

#: An SPDX banner anywhere it can appear: on its own line, behind a comment
#: marker, inside an rst directive, or mid-sentence in a notebook's markdown --
#: which is where two of them hid from an earlier, stricter version of this
#: pattern, one of them in a rebuilt notebook rather than the archive.
#: The identifier ends at whitespace, a closing comment marker, a quote or a
#: backslash -- the last two so that a generator script which writes the
#: banner into a string literal is read as declaring the identifier, not the
#: identifier plus an escape sequence.
BANNER: Final = re.compile(r"SPDX-License-Identifier:\s*(?P<id>[^\s>*\"'\\]+)")


def _tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT,
                         capture_output=True, text=True).stdout
    return [f for f in out.split("\n") if f and not f.startswith(EXCLUDED_TREES)]


def declared_license() -> str:
    """The authoritative identifier, read from pyproject rather than hardcoded."""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r"\[project\.license\]\s*\ntext\s*=\s*\"([^\"]+)\"", text)
    assert match, "pyproject.toml declares no [project.license] text"
    return match.group(1)


def test_the_authoritative_license_is_declared_once() -> None:
    assert declared_license() == "LicenseRef-Proprietary"


def test_no_file_declares_a_license_the_project_does_not() -> None:
    """The gate ADR 0001 asked for."""
    authoritative = declared_license()
    offenders: list[str] = []
    for name in _tracked():
        if name in EVIDENCE:
            continue
        path = REPO_ROOT / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for match in BANNER.finditer(text):
            found = match.group("id").rstrip(",.`\"'")
            if found != authoritative:
                offenders.append(f"{name}: {found}")
    assert not offenders, (
        f"{len(offenders)} SPDX banner(s) disagree with pyproject's "
        f"{authoritative!r}:\n  " + "\n  ".join(offenders[:20])
    )


def test_the_misleading_license_filenames_are_gone() -> None:
    """They were byte-identical proprietary text under names promising otherwise."""
    for name in ("LICENSE-CODE", "LICENSE-CONTENT"):
        assert not (REPO_ROOT / name).exists(), (
            f"{name} is back. It is a copy of the proprietary LICENSE under a "
            "filename that advertises an open one, which is how the drift in "
            "DECISIONS/0001 started."
        )
    assert (REPO_ROOT / "LICENSE").is_file()


def test_no_surface_still_offers_contributors_an_open_license() -> None:
    """The live misrepresentation: what CONTRIBUTING promised people."""
    text = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    section = text[text.index("## License"):]
    for promise in ("→ MIT License", "→ CC-BY-SA-4.0", "dual license:"):
        assert promise not in section, (
            f"CONTRIBUTING.md still offers contributors {promise!r}. The "
            "repository is proprietary; a contributor cannot be told otherwise."
        )
    assert "proprietary" in section.lower()


@pytest.mark.parametrize("name", sorted(EVIDENCE - {"tests/test_gate_license_consistency.py"}))
def test_the_evidence_files_still_exist(name: str) -> None:
    """The exclusions are a list of real files, not a way to skip the check."""
    assert (REPO_ROOT / name).is_file(), (
        f"{name} is on the evidence exclusion list but does not exist, so the "
        "exclusion silently widens the gate's blind spot."
    )


#: Prose that grants, or appears to grant, permissions this licence withholds.
#: These matter more than SPDX banners: a banner is a machine-readable claim a
#: lawyer reads, whereas "Yes! That's encouraged" is what a person acts on.
#:
#: All four of the misstatements this catches survived the SPDX sweep of
#: 2026-09-18, because none of them contained an identifier -- including
#: the operating brief every agent session read before touching the repository.
PERMISSION_LANGUAGE: Final = (
    "dual license",
    "dual licensed",
    "dual-licensed",
    "dual licensing",
    "MIT for code",
    "MIT License (permissive)",
    "licensed under the apache",
    "licensed under the mit",
    #: Added 2026-09-18. The list shipped with no Creative Commons entry at all,
    #: while ADR 0005's own table names "CC-BY-SA 4.0" as retired. Five live
    #: `Licensed under CC-BY-4.0` grants sat in notebook markdown cells and in
    #: docs index, and the gate that exists to catch exactly that could not see
    #: them. A retired identifier absent from the detector is not a detector.
    "cc-by-4.0",
    "cc-by-sa-4.0",
    "cc-by-sa 4.0",
    "creative commons",
)
#: Deliberately NOT in that list: "open-source software". Both the README and the
#: docs index say "this is **not** open-source software", and a substring match
#: cannot tell a denial from a grant. A check that fires on the correct sentence
#: teaches people to suppress it.

#: Files allowed to contain that language because they quote it as history.
PERMISSION_EVIDENCE: Final[frozenset[str]] = frozenset({
    "LICENSE",
    "CONTRIBUTING.md",
    "tests/test_gate_license_consistency.py",
}) | EVIDENCE

#: Files permitted to name a retired identifier, inside a fence and nowhere else.
#:
#: `docs/wiki/FAQ.md` is why this mechanism exists. It was excluded whole-file so
#: that one historical answer could quote "MIT + CC-BY-SA-4.0". Under that
#: exclusion the 2026-09-18 rewrite corrected four answers and left five live
#: grants in the same file, twenty lines below "There is no permissive or
#: share-alike grant of any kind":
#:
#:   - a permission table: "MIT (Code): Use freely, even commercially"
#:   - "Can I include these tutorials in a book? Yes, with attribution and
#:     sharing under CC-BY-SA."
#:   - an attribution recipe, and "modified content must also be CC-BY-SA"
#:
#: A whole-file exclusion is a promise about a file that nobody re-checks. A
#: fence is a promise about six lines, and the rest of the file stays scanned.
#: Empty by decision (ADR 0007). This repository was never published, so no
#: reader ever saw the retired declarations and no document needs to explain them
#: away. Reader-facing prose states what is true now; DECISIONS/ records what
#: changed. An empty set means the fence exists but nothing may use it -- which
#: `test_only_the_declared_files_carry_a_licence_history_fence` enforces.
LICENCE_HISTORY_FILES: Final[frozenset[str]] = frozenset()

#: Group 1 is the prose *between* the tags. The denial check must read that and
#: not the opening tag, whose own wording ("the retired identifiers are named
#: below on purpose") otherwise satisfies the check for any content at all --
#: which it silently did until a mutation test rewrote a fence into a grant and
#: the gate stayed green.
_FENCE = re.compile(
    r"<!--\s*licence-history\b.*?-->(.*?)<!--\s*/licence-history\s*-->",
    re.DOTALL | re.IGNORECASE,
)

#: A fence may not be large enough to hide a section, and its text must read as a
#: denial -- a grant that also says "never authorized" contradicts itself.
FENCE_MAX_CHARS: Final = 900
DENIAL_MARKERS: Final = ("never", "not authorized", "no longer", "formerly",
                         "retired", "used to", "neither", " no.")


def test_only_the_declared_files_carry_a_licence_history_fence() -> None:
    """A fence is a decision, so adding one has to be a decision."""
    fenced = {n for n in _tracked()
              if (REPO_ROOT / n).is_file()
              and n.endswith((".md", ".rst", ".txt"))
              and not n.startswith(("notebooks/", "DECISIONS/", "docs/audits/"))
              and "licence-history" in (REPO_ROOT / n).read_text(encoding="utf-8")}
    assert fenced == LICENCE_HISTORY_FILES, (
        f"licence-history fences appear in {sorted(fenced)}, not "
        f"{sorted(LICENCE_HISTORY_FILES)}. A new fence silently exempts prose."
    )


@pytest.mark.parametrize("name", sorted(LICENCE_HISTORY_FILES))
def test_every_fence_is_small_and_reads_as_a_denial(name: str) -> None:
    """The two properties that stop a fence becoming the old blind spot."""
    regions = _FENCE.findall((REPO_ROOT / name).read_text(encoding="utf-8"))
    assert regions, f"{name} is declared as fenced but carries no fence"
    for r in regions:  # `r` is the prose inside the tags, never the tags
        assert len(r) <= FENCE_MAX_CHARS, (
            f"a fence in {name} is {len(r)} chars; a fence covers a sentence "
            "about history, not a section"
        )
        assert any(m in r.lower() for m in DENIAL_MARKERS), (
            f"a fence in {name} names a retired identifier without denying it:\n{r}"
        )


def test_the_readme_still_denies_the_open_license() -> None:
    """The one place a reader looks first has to say it outright."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "not** open-source software" in readme
    assert "Proprietary." in readme
    assert "service mark" in readme



def _prose(path: Path) -> str:
    """The text a reader is shown, excluding anything a third party wrote.

    For a notebook this is **markdown-cell source only**. Stored output carries
    vendored library headers -- a notebook that embeds a plotting bundle carries
    its banner, e.g. "Licensed under the MIT License" -- and a
    third party's notice about its own library is not a grant by Telosyn. Reading
    whole-file would flag those, and the only way to silence them would be a
    per-file exclusion, which is a blind spot. Scoping to markdown source removes
    the whole class structurally and keeps every notebook checked.
    """
    if path.suffix != ".ipynb":
        return _FENCE.sub(" ", path.read_text(encoding="utf-8"))
    nb = json.loads(path.read_text(encoding="utf-8"))
    return "\n".join(
        "".join(c.get("source", []))
        for c in nb.get("cells", [])
        if c.get("cell_type") == "markdown"
    )


def test_no_document_grants_permissions_the_license_withholds() -> None:
    """The four misstatements an identifier-only sweep could not see."""
    offenders: list[str] = []
    for name in _tracked():
        # DECISIONS/ is exempt as a class. An ADR's job is to record what was
        # decided and what the prior state was, which means quoting the language
        # being retired. ADR 0005 quotes "Dual license: MIT for code" in the table
        # of misstatements it exists to correct, and tripped this gate the moment
        # it was committed.
        if name.startswith("DECISIONS/"):
            continue
        # `docs/audits/` is exempt for the same reason as `DECISIONS/`: an audit
        # records the language it found, and quoting a finding is not making it.
        if name.startswith(("notebooks/", "docs/audits/")):
            continue
        if name in PERMISSION_EVIDENCE:
            continue
        if not name.endswith((".md", ".rst", ".txt", ".ipynb")):
            continue
        path = REPO_ROOT / name
        if not path.is_file():
            continue
        try:
            lowered = _prose(path).lower()
        except (UnicodeDecodeError, OSError, json.JSONDecodeError):
            continue
        for phrase in PERMISSION_LANGUAGE:
            if phrase.lower() in lowered:
                offenders.append(f"{name}: {phrase!r}")
                break
    assert not offenders, (
        "documents describe permissions this repository does not grant:\n  "
        + "\n  ".join(offenders)
        + "\n\nThe licence is proprietary. Nothing is authorized as MIT, Apache or "
        "Creative Commons unless it is authorized in writing for that specific "
        "material and recorded in DECISIONS/."
    )


def test_the_license_states_that_visibility_is_not_a_grant() -> None:
    """Public repos are for marketing, showcase and transparency. Nothing else.

    A reader who can see the source needs to be told, in the licence itself, that
    seeing it grants nothing -- otherwise the publication argues the opposite.
    """
    text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
    for clause in ("PUBLIC VISIBILITY IS NOT A LICENSE",
                   "NO OPEN-SOURCE LICENSE WITHOUT EXPRESS AUTHORIZATION"):
        assert clause in text, f"LICENSE no longer carries the {clause!r} clause"
    assert "implication, estoppel" in text



