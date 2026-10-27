"""Gate 9 — the vintage policy, made enforceable.

Handbook §5.2 says, in prose: *every notebook records, in `metadata.krl`, the
flag `vintage_pinned`*, and *`vintage_pinned: false` is permitted only with a
one-sentence justification in the notebook naming which exemption applies*.

It was prose, so nothing enforced it, and **twenty of thirty-three notebooks had
no such flag at all** by the time the corpus was complete. Every notebook built
after the policy was written omitted it, and §5.4 went on stating that no
notebook violated the policy. A rule with no gate is a preference.

This gate is that rule.

**What `vintage_pinned: true` is allowed to mean.** It was originally read as
"the call names a year", which is the wrong test and would pass QCEW, CBP, BDS,
BEA and HUD CHAS -- all of which handbook §5.5 measures as serving no prior
vintage. Naming a reference period is not pinning a vintage. The flag now means
what §5.1 clause 1 needs it to mean: **a re-run returns the same numbers, and the
publisher's own contract is what guarantees it** -- either prior vintages are
served on request, or each vintage is a separately addressed immutable asset.

The per-source judgement lives in `tests/test_provenance_pinning.py`; this gate
checks the notebook's declaration is present, is consistent with the fetchers it
actually calls, and carries a justification when it is false.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import re
from typing import Final

from gate_support import Notebook

#: Mirrors `test_provenance_pinning.PINNED_FETCHERS`. Duplicated rather than
#: imported because that module and this one are collected from different roots
#: in CI; `test_the_two_lists_agree` below keeps them honest.
PINNED_FETCHERS: Final[frozenset[str]] = frozenset({
    "fetch_acs", "fetch_acs_wide", "fetch_acs_pums", "fetch_cps_asec", "fetch_fred", "fetch_places_county",
    "fetch_opportunity_atlas", "fetch_social_capital_atlas",
    "fetch_dataverse_file", "fetch_mit_president",
})

FETCHER_CALL: Final = re.compile(r"\b(fetch_[a-z0-9_]+)\s*\(")

#: Accepted values.
#:
#: ``True``            the publisher will serve these numbers again -- prior
#:                     vintages on request, or each vintage a separately
#:                     addressed immutable asset.
#: ``"digest"``        the publisher will not, and the retrieval is held to a
#:                     digest recorded in the notebook, so a change raises
#:                     rather than passing unnoticed. A weaker guarantee and a
#:                     different kind of one, which is why it is not ``True``.
#: ``False``           neither.
#: ``"not_applicable"`` the artifact retrieves nothing.
VALID: Final = (True, False, "digest", "not_applicable")

#: The justification must name the reason, not merely exist. These are the
#: shapes §5.1 and §5.5 license.
JUSTIFICATION_MARKERS: Final = (
    "exemption", "reference period", "serves no", "no prior vintage",
    "retrieval is the vintage", "live", "undated", "no external source",
    "growth rate", "difference", "deflator",
)


def _krl(notebook: Notebook) -> dict:
    return notebook.metadata.get("krl", {}) or {}


def test_the_flag_is_present(notebook: Notebook) -> None:
    """§5.2's first sentence. Twenty notebooks failed this when it was written."""
    krl = _krl(notebook)
    assert "vintage_pinned" in krl, (
        f"{notebook.path.name} records no `vintage_pinned` in metadata.krl. "
        "Handbook §5.2 requires it on every notebook, and the value is a claim "
        "about whether a re-run returns the same numbers -- not a formality."
    )
    assert krl["vintage_pinned"] in VALID, (
        f"{notebook.path.name} has vintage_pinned={krl['vintage_pinned']!r}; "
        f"permitted values are {VALID}."
    )


def test_false_or_not_applicable_carries_a_justification(notebook: Notebook) -> None:
    """§5.2's second sentence, which was the part nothing could check."""
    krl = _krl(notebook)
    value = krl.get("vintage_pinned")
    if value is True:
        return
    note = (krl.get("vintage_note") or "").strip()
    assert note, (
        f"{notebook.path.name} declares vintage_pinned={value!r} with no "
        "`vintage_note`. §5.2 permits a non-true value only with a one-sentence "
        "justification naming which exemption applies."
    )
    assert any(marker in note.lower() for marker in JUSTIFICATION_MARKERS), (
        f"{notebook.path.name}'s vintage_note names no recognised reason: {note!r}. "
        f"Say which of §5.1's exemptions or §5.5's conditions applies."
    )


def test_the_justification_reaches_the_reader(notebook: Notebook) -> None:
    """A note only a gate can see is not a justification *in the notebook*.

    §5.2 says the justification is in the notebook. Metadata is where a machine
    can check it; prose is where a reader meets it. Both, or neither counts.
    """
    krl = _krl(notebook)
    if krl.get("vintage_pinned") is True:
        return
    prose = notebook.markdown_source.lower()
    assert "vintage" in prose, (
        f"{notebook.path.name} declares a vintage exemption in metadata and never "
        "mentions vintage in its prose. The reader of the notebook has to be told."
    )


def test_a_digest_claim_is_backed_by_a_pin_in_the_notebook(notebook: Notebook) -> None:
    """`"digest"` is a claim about the code, so the code has to carry it."""
    if _krl(notebook).get("vintage_pinned") != "digest":
        return
    code = notebook.code_source
    assert "verify_digest(" in code, (
        f"{notebook.path.name} declares vintage_pinned='digest' but calls no "
        "verify_digest(). The flag would then assert a guarantee nothing enforces."
    )
    #: A scalar pin or a dict of them -- D09 and D15 pin every area they fetch,
    #: which is the better shape and which an earlier version of this check
    #: rejected for not being a single constant.
    assert re.search(r"\bPINNED_\w+\b", code) and re.search(r'"[0-9a-f]{32,}"', code), (
        f"{notebook.path.name} calls verify_digest() with no pinned digest "
        "constant, so there is nothing for it to verify against."
    )


def test_a_notebook_calling_an_unpinnable_source_does_not_claim_otherwise(
    notebook: Notebook,
) -> None:
    """The check the original reading of the flag would have failed.

    A notebook built on QCEW, CBP, BDS, BEA, HUD CHAS/FMR, the FBI CDE, TRI or an
    undated bulk extract cannot claim a pinned vintage, however explicit its
    `year=` argument is.
    """
    krl = _krl(notebook)
    if krl.get("vintage_pinned") is not True:
        return
    called = {m.group(1) for m in FETCHER_CALL.finditer(notebook.code_source)}
    unpinnable = sorted(f for f in called if f.startswith("fetch_") and f not in PINNED_FETCHERS)
    assert not unpinnable, (
        f"{notebook.path.name} declares vintage_pinned=True but calls {unpinnable}, "
        "which revise and serve no prior vintage (handbook §5.5). Naming a "
        "reference period is not pinning a vintage. Set the flag to false and say "
        "in `vintage_note` that this retrieval is the only vintage that will exist."
    )


def test_the_two_lists_agree() -> None:
    """Keep this gate's copy of the allowlist in step with the source of truth."""
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "_pinning", Path(__file__).resolve().parent / "test_provenance_pinning.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.PINNED_FETCHERS == PINNED_FETCHERS, (
        "tests/test_provenance_pinning.py and this gate disagree about which "
        "fetchers are pinnable. They must not."
    )
