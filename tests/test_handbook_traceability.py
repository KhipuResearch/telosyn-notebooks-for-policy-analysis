"""Gate 8 — the handbook may not drift from the notebooks it cites.

``docs/methodology.md`` distils the corpus's guidance and
carries roughly 120 numeric claims, each tagged with the notebook that produced
it. A number in prose is exactly the artifact this corpus exists to distrust:
it looks like a result, it survives every structural gate, and nothing about the
file establishes that it was ever computed.

So the citation is made load-bearing. Every number appearing in a claim tagged
``[D09 F2]`` must appear literally in D09 — in its source or in its stored
output. Re-executing a notebook changes its numbers; this gate then fails, and
the handbook is corrected rather than quietly left stale.

**What this does and does not establish.** It proves each number is *present* in
the cited notebook. It does not prove the number means in the handbook what it
meant there.

Measured sensitivity, across five rounds of deliberate corruption of cited
figures: **48 of 51 caught**.

    round 1 (§1-§11)    8 mutations,  7 caught
    round 2 (§1.14)    10 mutations, 10 caught
    round 3 (§13)      10 mutations,  8 caught
    round 4 (§14)       5 mutations,  5 caught
    round 5 (§7.3, §17 — table cells)
                       18 mutations, 18 caught

Round 5 is the one that changed the gate rather than confirming it. Before it,
**every figure in every table in the handbook was unchecked**, and mutating
§7.3's precision-and-rank series -- the document's central quantitative claim --
failed to trip anything. Two rules combined to cause it: ``|`` was a claim
boundary, and the fragment is read *backwards* from the citation, while the
handbook's table convention puts the citation in the row's first cell. Every
figure in a row therefore sat on the unread side of both. ``_claim_row`` now
reads the whole row in both directions; checks went from 529 to 551, and 16
citations that vouched for nothing now vouch for their row.

Every miss has the same cause -- the corrupted value coincidentally exists
somewhere else in the cited notebook:

    88.9% -> 87.9%   D09: 87.9% is a real figure one row up in the same table
    8.60% -> 8.70%   D30: normalises to "8.7", which is that notebook's
                     false-discovery share -- a different statistic entirely
    1.06  -> 1.07    D30: 1.07 is the upper bound of the pure-noise spread

So a wrong figure that appears elsewhere in the same notebook passes, and a true
figure attached to a false sentence passes. Both are caught by reading the
notebook against the prose, which is how every defect in §11 of the handbook was
actually found. This gate is a floor under that reading, not a substitute for it,
and the three misses above are the size of the gap.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
HANDBOOK: Final = REPO_ROOT / "docs" / "methodology.md"

#: Citation tag -> notebook, relative to ``projects``.
CITED_NOTEBOOKS: Final[dict[str, str]] = {
    "D01": "01-fundamentals/D01_income_and_poverty/D01_income_and_poverty.ipynb",
    "D02": "01-fundamentals/D02_employment_and_labor/D02_employment_and_labor.ipynb",
    "D03": "01-fundamentals/D03_education/D03_education.ipynb",
    "D06": "03-inequality-demographics/D06_inequality_and_wealth/D06_inequality_and_wealth.ipynb",
    "D07": "03-inequality-demographics/D07_demographics_and_migration/D07_demographics_and_migration.ipynb",
    "D08": "01-fundamentals/D08_consumer_spending/D08_consumer_spending.ipynb",
    "D09": "04-economy-industry/D09_industry_structure/D09_industry_structure.ipynb",
    "D15": "04-economy-industry/D15_business_and_entrepreneurship/D15_business_and_entrepreneurship.ipynb",
    "D16": "06-infrastructure-environment/D16_internet_and_technology_access/D16_internet_and_technology_access.ipynb",
    "D27-rent": (
        "08-culture-society/D27_housing_affordability_and_gentrification/"
        "D27_rent_burden.ipynb"
    ),
    "D27-gent": (
        "08-culture-society/D27_housing_affordability_and_gentrification/"
        "D27_gentrification.ipynb"
    ),
    "D05": "02-health-housing/D05_housing_fair_market_rents/D05_fair_market_rents.ipynb",
    "D05-chas": "02-health-housing/D05_housing_needs_chas/D05_chas_custom_tabulation.ipynb",
    "D04": "02-health-housing/D04_health_prevalence/D04_health_prevalence.ipynb",
    "D10": "05-social-systems/D10_social_mobility/D10_social_mobility.ipynb",
    "D11": "08-culture-society/D11_cultural_economics/D11_cultural_economics.ipynb",
    "D21": "05-social-systems/D21_social_capital/D21_social_capital.ipynb",
    "D13": (
        "07-justice-equity/D13_crime_and_public_safety/"
        "D13_crime_and_public_safety.ipynb"
    ),
    "D29": (
        "05-social-systems/D29_innovation_and_entrepreneurship/"
        "D29_business_dynamics.ipynb"
    ),
    "D12": (
        "06-infrastructure-environment/D12_environmental_economics/"
        "D12_environmental_economics.ipynb"
    ),
    "D30": (
        "02-health-housing/D30_subjective_wellbeing/"
        "D30_subjective_wellbeing.ipynb"
    ),
    "D33": (
        "03-inequality-demographics/D33_gender_earnings_gap/"
        "D33_gender_earnings_gap.ipynb"
    ),
    "D19": (
        "07-justice-equity/D19_civic_engagement/"
        "D19_civic_engagement.ipynb"
    ),
    "D26": (
        "07-justice-equity/D26_crime_aggregates/"
        "D26_crime_aggregates.ipynb"
    ),
    "D18-snap": (
        "05-social-systems/D18_social_services/"
        "D18_social_services.ipynb"
    ),
    "D17": (
        "02-health-housing/D17_food_security/"
        "D17_food_security.ipynb"
    ),
    "D22": (
        "08-culture-society/D22_nonprofit_arts/"
        "D22_nonprofit_arts.ipynb"
    ),
    "D28": (
        "02-health-housing/D28_mental_health/"
        "D28_mental_health.ipynb"
    ),
    "D05-value": (
        "02-health-housing/D05_housing_home_values/"
        "D05_home_values.ipynb"
    ),
}

#: Longest tag first. Python's alternation is first-match, not longest-match, so with
#: "D05" listed before "D05-chas" every `[D05-chas F1]` matched as tag "D05" with the
#: leftover "-chas F1" as the suffix -- silently checking one notebook's figures
#: against another's. The gate caught this by failing when D05-chas was registered.
CITATION: Final = re.compile(
    r"\[(" + "|".join(map(re.escape, sorted(CITED_NOTEBOOKS, key=len, reverse=True))) + r")([^\]]*)\]"
)
NUMBER: Final = re.compile(r"\d[\d,]*\.?\d*")

#: Cross-references to this document's own sections (``§4.1``) and to external
#: numbered items. They are navigation, not claims, and are removed before a
#: fragment is read for figures.
_CROSS_REFERENCE: Final = re.compile(r"\u00a7\s?\d+(\.\d+)*")

#: Notebook references in prose (``D10``, ``D33's``, ``D05-chas``). Also
#: navigation, and also not claims -- but the digits in them were being read as
#: figures. Until D33 they passed only by coincidence: "about twenty times
#: tighter than D10" was checked by looking for "10" in the cited notebook,
#: which any notebook contains. Stripped for the same reason section
#: references are.
_NOTEBOOK_REFERENCE: Final = re.compile(r"\bD\d{2}(?:-\w+)?\b")

#: How far back from a citation a claim may reasonably begin. Generous, because
#: the span is bounded by the previous citation and by the paragraph anyway.
_CLAIM_LOOKBEHIND: Final[int] = 900

#: Paragraph boundaries — a claim does not cross one.
#:
#: Sentence boundaries are deliberately **not** included. The handbook states
#: compound claims across several sentences and cites once at the end; splitting
#: on ``.`` or ``;`` silently dropped every figure before the last break, so the
#: gate reported a hundred-odd checks while never seeing most of the numbers.
_CLAIM_BOUNDARY: Final = re.compile(r"\n\n")

#: A markdown table row containing a citation. Inside one, the claim is the
#: **whole row** — including the cells to the right of the citation.
#:
#: Two defects combined to leave every table figure in this handbook unchecked.
#: ``|`` was a boundary alongside ``\n\n``, so a fragment stopped at the cell
#: edge; and the fragment is a *lookbehind*, so anything after the citation was
#: never read at all. The handbook's own table convention (§7.3) puts the
#: citation in the row's **first** cell, which put every figure in the row on
#: the unread side of both rules.
#:
#: Found by mutation while registering §17: corrupting ``0.853`` in §7.3's
#: precision-and-rank table did not fail the gate. Four tables were affected.
#:
#: The row is the right unit of claim. A handbook table row cites one notebook
#: and its cells are that notebook's figures, so a citation anywhere in the row
#: vouches for the row and for nothing outside it.
_TABLE_ROW: Final = re.compile(r"^\|[^\n]*$", re.MULTILINE)


def _searchable_text(notebook_path: Path) -> str:
    """Every character a reader of the executed notebook can see."""
    nb = json.loads(notebook_path.read_text(encoding="utf-8"))
    parts: list[str] = []
    for cell in nb["cells"]:
        parts.append("".join(cell.get("source", [])))
        for output in cell.get("outputs", []):
            if output.get("output_type") == "stream":
                parts.append("".join(output.get("text", [])))
            plain = output.get("data", {}).get("text/plain")
            if plain:
                parts.append("".join(plain))
    return "\n".join(parts)


def _claim_before(text: str, citation_start: int) -> str:
    """The fragment a citation vouches for: back to the nearest boundary.

    A preceding citation ends the previous claim, so the fragment never reads
    across one — otherwise a ``[D16]`` claim would be checked against D27.
    """
    fragment = text[max(0, citation_start - _CLAIM_LOOKBEHIND):citation_start]
    previous = list(CITATION.finditer(fragment))
    if previous:
        fragment = fragment[previous[-1].end():]
    fragment = _CLAIM_BOUNDARY.split(fragment)[-1]
    return _NOTEBOOK_REFERENCE.sub("", _CROSS_REFERENCE.sub("", fragment))


def _claim_row(text: str, citation_start: int) -> str | None:
    """The whole table row a citation sits in, or ``None`` if it is not in one.

    Read forward as well as back, which the paragraph rule above deliberately
    does not do: a table row is a single claim and its citation is conventionally
    written in the first cell, so the figures are all to the right of it.
    """
    line_start = text.rfind("\n", 0, citation_start) + 1
    line_end = text.find("\n", citation_start)
    line = text[line_start:line_end if line_end != -1 else len(text)]
    if not _TABLE_ROW.fullmatch(line.strip()):
        return None
    return _NOTEBOOK_REFERENCE.sub("", _CROSS_REFERENCE.sub("", CITATION.sub("", line)))


def _is_checkable(literal: str) -> bool:
    """Skip counts too small to distinguish a real citation from a coincidence."""
    return len(literal.replace(",", "").rstrip("0").rstrip(".")) >= 2


def _normalise(literal: str) -> str:
    """Comma-insensitive, trailing-zero-insensitive form of a numeric token.

    ``1,201`` and ``1201`` are the same figure; so are ``1.00`` and ``1.0``.
    Formatting differs between a handbook sentence and an f-string in a notebook,
    and a gate that treated that as a mismatch would be turned off within a week.
    """
    bare = literal.replace(",", "")
    if "." in bare:
        bare = bare.rstrip("0").rstrip(".") or "0"
    return bare


def _numeric_tokens(text: str) -> frozenset[str]:
    """Every complete number in *text*.

    Whole tokens, never substrings. Matching ``in`` on the raw text would let
    ``94`` match inside ``294`` — which it does in D09 — and the gate would pass
    a corrupted figure. That is the defect class the corpus exists to catch, so
    it is not allowed to live in the gate that checks for it.
    """
    return frozenset(_normalise(m) for m in NUMBER.findall(text))


@pytest.fixture(scope="module")
def handbook_text() -> str:
    if not HANDBOOK.exists():  # pragma: no cover - the file is committed
        pytest.skip(f"{HANDBOOK.name} not present")
    return HANDBOOK.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def cited_numbers() -> dict[str, frozenset[str]]:
    root = REPO_ROOT / "projects"
    return {
        tag: _numeric_tokens(_searchable_text(root / rel))
        for tag, rel in CITED_NOTEBOOKS.items()
    }


def test_every_cited_notebook_exists() -> None:
    """A citation to a notebook that is not in the tree vouches for nothing."""
    root = REPO_ROOT / "projects"
    missing = [rel for rel in CITED_NOTEBOOKS.values() if not (root / rel).exists()]
    assert not missing, f"handbook cites notebooks that do not exist: {missing}"


def test_the_handbook_actually_cites_its_sources(handbook_text: str) -> None:
    """Guards the gate itself: a handbook stripped of tags would pass vacuously."""
    tags = {m.group(1) for m in CITATION.finditer(handbook_text)}
    assert len(tags) >= 9, (
        f"only {len(tags)} distinct notebooks cited ({sorted(tags)}). The handbook "
        f"summarises eleven; this gate is only meaningful while the claims carry tags."
    )


def audit_claims(
    handbook_text: str, cited_numbers: dict[str, frozenset[str]]
) -> tuple[int, list[str]]:
    """Return ``(claims checked, claims whose figure is absent from its notebook)``."""
    unmatched: list[str] = []
    checked = 0
    for citation in CITATION.finditer(handbook_text):
        tag = citation.group(1)
        claim = _claim_row(handbook_text, citation.start())
        if claim is None:
            claim = _claim_before(handbook_text, citation.start())
        published = cited_numbers[tag]
        for literal in NUMBER.findall(claim):
            if not _is_checkable(literal):
                continue
            checked += 1
            if _normalise(literal) not in published:
                unmatched.append(f"[{tag}] {literal!r} in: ...{claim.strip()[-130:]}")
    return checked, unmatched


def test_the_gate_rejects_a_corrupted_figure(
    handbook_text: str, cited_numbers: dict[str, frozenset[str]]
) -> None:
    """Proof that the check below is a true positive, not a vacuous pass.

    An earlier revision of this gate matched numbers as substrings, so ``94``
    matched inside ``294`` and a corrupted figure sailed through. A gate that
    cannot fail is worse than no gate, because it is reported as coverage.
    """
    corrupted = handbook_text.replace(
        "Suppression runs 95% for cells", "Suppression runs 94% for cells"
    )
    assert corrupted != handbook_text, "anchor text has moved; update this test"
    _, unmatched = audit_claims(corrupted, cited_numbers)
    assert any("'94'" in u for u in unmatched), (
        "the gate did not flag a figure corrupted from 95% to 94%. It is not "
        "detecting anything and must be repaired before it is trusted."
    )


def test_every_numeric_claim_appears_in_the_notebook_it_cites(
    handbook_text: str, cited_numbers: dict[str, frozenset[str]]
) -> None:
    """The load-bearing check. See the module docstring for its limits."""
    checked, unmatched = audit_claims(handbook_text, cited_numbers)

    assert checked >= 140, (
        f"only {checked} numeric claims checked; the handbook carried ~150. "
        f"Either it was gutted or the claim parser stopped matching."
    )
    assert not unmatched, (
        f"{len(unmatched)} of {checked} numeric claims are not present in the notebook "
        f"they cite. Re-executing a notebook changes its numbers; update the handbook "
        f"from the new output rather than relaxing this gate.\n  "
        + "\n  ".join(unmatched[:20])
    )
