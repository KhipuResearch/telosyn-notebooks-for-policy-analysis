"""The retirement argument, made load-bearing.

`docs/migration.md` retires three archived artifacts on the ground that
their code is byte-identical to D01's. That claim decides whether three domains
get a rebuild or a line in a table, so it should not live only in prose.

It already went wrong once. An earlier revision of the register said the three
were "SHA-256 identical to D01". At the file level they are not -- four
different digests and four different byte counts -- and an auditor who checked
the stated basis would have found it false. The true claim is about the *code*,
and these tests pin it.

They read only from `notebooks/`, the forensic corpus, which is retained
unmodified as audit evidence.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
MIGRATION: Final = REPO_ROOT / "docs" / "migration.md"


def _archive_root() -> Path | None:
    """Where the retired corpus lives, now that it is not in this repository.

    The archive was removed from the tree on 2026-09-18 (ADR 0007): it was 1,003
    files and 56.7 MB of material no current notebook imports, and it carried
    truncated key prefixes and operator home paths into a repository intended to
    be publicly readable. The manifest never verified the in-repo copy anyway --
    it verifies the copy under ``KRL/backups/``, from which the in-repo one had
    drifted in ten notebooks.

    So these digest assertions now run against the external corpus when it is
    mounted and skip when it is not. A skip is honest here: the claim is about an
    artifact this repository no longer contains, and pretending otherwise would
    be a test that passes because it checks nothing.
    """
    if (env := os.environ.get("KRL_ARCHIVE_ROOT")):
        root = Path(env).expanduser().resolve()
        return root if root.is_dir() else None
    default = REPO_ROOT.parents[1] / "backups" / "backup_20251210_235356" / "the private source repository"
    return default if default.is_dir() else None


ARCHIVE_ROOT: Final = _archive_root()

pytestmark = pytest.mark.skipif(
    ARCHIVE_ROOT is None,
    reason=("the retired corpus is not mounted; set KRL_ARCHIVE_ROOT to the "
            "archive root to run the retirement-digest checks (ADR 0007)"),
)

ARCHIVED: Final[dict[str, str]] = {
    "D01": "notebooks/01_fundamentals/D01_income_and_poverty/D01_D01_income_and_poverty.ipynb",
    "D31": "notebooks/09_planned/D31_civic_trust/D31_D31_civic_trust.ipynb",
    "D32": "notebooks/09_planned/D32_freedom_civil/D32_D32_freedom_civil.ipynb",
    "D33": "notebooks/09_planned/D33_gender_equality/D33_D33_gender_equality.ipynb",
}

#: The measured code digest the register cites. Short, because the register
#: quotes it short; an accidental match at 12 hex characters is not a concern
#: beside four files that are actually the same bytes.
CODE_SHA1_PREFIX: Final = "9a5a5afdf75b"
CODE_BYTES: Final = 37_835
CODE_CELLS: Final = 11


def _cells(tag: str) -> list[dict]:
    return json.loads((ARCHIVE_ROOT / ARCHIVED[tag]).read_text(encoding="utf-8"))["cells"]


def _code(tag: str) -> str:
    return "\n".join(
        "".join(c.get("source", [])) for c in _cells(tag) if c["cell_type"] == "code"
    )


def _markdown(tag: str) -> list[str]:
    return ["".join(c.get("source", [])) for c in _cells(tag) if c["cell_type"] == "markdown"]


@pytest.mark.parametrize("tag", sorted(ARCHIVED))
def test_the_four_artifacts_share_one_code_body(tag: str) -> None:
    """The retirement argument in one assertion."""
    source = _code(tag)
    assert hashlib.sha1(source.encode()).hexdigest().startswith(CODE_SHA1_PREFIX), (
        f"{tag}'s code no longer matches the digest MIGRATION.md cites. Either the "
        "forensic corpus was modified -- it must not be -- or the register is stale."
    )
    assert len(source) == CODE_BYTES
    assert sum(1 for c in _cells(tag) if c["cell_type"] == "code") == CODE_CELLS


def test_the_files_are_not_identical_which_is_why_the_claim_is_about_code() -> None:
    """Guard the correction itself, so the weaker claim cannot creep back in."""
    digests = {
        tag: hashlib.sha256((ARCHIVE_ROOT / path).read_bytes()).hexdigest()
        for tag, path in ARCHIVED.items()
    }
    assert len(set(digests.values())) == len(digests), (
        "the four files now share a digest, which would make MIGRATION.md's "
        "correction wrong in the other direction"
    )


def test_only_the_references_cell_differs() -> None:
    """Three notebooks differentiated by a bibliography and nothing else."""
    baseline = _markdown("D01")
    for tag in ("D31", "D32", "D33"):
        other = _markdown(tag)
        assert len(other) == len(baseline)
        differing = [i for i, (a, b) in enumerate(zip(baseline, other)) if a != b]
        assert len(differing) == 1, (
            f"{tag} differs from D01 in {len(differing)} markdown cells, not 1. The "
            "register's claim that the References cell is the entire differentiation "
            "no longer holds."
        )
        assert "References" in other[differing[0]]


@pytest.mark.parametrize(
    "tag,named_source",
    [("D31", "gssdataexplorer.norc.org"), ("D32", "freedomhouse.org"), ("D33", "weforum.org")],
)
def test_the_references_name_sources_the_code_never_calls(tag: str, named_source: str) -> None:
    """The one differentiating cell cites data the notebook does not retrieve."""
    assert named_source in "\n".join(_markdown(tag))
    assert named_source not in _code(tag), (
        f"{tag}'s code now reaches {named_source}; the retirement basis would need rewriting"
    )


def test_the_shared_code_retrieves_income_and_poverty_variables() -> None:
    """Name what the code actually does, so "identical to D01" means something."""
    source = _code("D31")
    for variable in ("B19013_001E", "B17001_002E", "B19083_001E"):
        assert variable in source, (
            f"{variable} is gone from the shared code body; MIGRATION.md names it as "
            "evidence that a civic-trust notebook runs income-and-poverty code"
        )


# Removed 2026-09-18. Three tests here asserted properties of D31/D32 *stored
# outputs*: that D31's output names itself as D01, that both announce a synthetic
# fallback and then report a Census retrieval, and that they differ only in two
# RNG-derived scores. The audited artifacts carry no stored outputs at all --
# `stored_outputs=0` for all four in audit_manifest_2026-09-13.jsonl, which the
# external corpus matches byte for byte. Those observations came from working-tree
# copies executed after the audit, MIGRATION.md now retracts them, and a test that
# asserts a retracted claim is worse than no test. The retirement argument does not
# depend on them: it rests on the code digest, which is checked above.

def test_the_register_states_the_corrected_basis() -> None:
    """The prose and these tests must not drift apart."""
    text = MIGRATION.read_text(encoding="utf-8")
    assert "SHA-256 identical to D01" not in text.split("Correction (2026-09-15)")[0], (
        "the retired claim is back in the register above its own correction"
    )
    assert CODE_SHA1_PREFIX in text
    assert f"{CODE_BYTES:,}" in text


# --------------------------------------------------------------------------- D25
#
# D25 is retired on a different basis from D31/D32/D33 and therefore needs its
# own evidence. Those three were retired because their code is D01's. D25's code
# is a template too, but the decisive facts are about its *declared sources*:
# every one is either already built in this corpus, already measured as
# unreachable by the route it names, or measured as a grain that does not exist.
#
# `SOURCE_MAP.md` and `MIGRATION.md` state that. These tests pin the parts of it
# that live in the archived file, so the register cannot go stale against the
# forensic corpus the way the D31/D32/D33 claim did.

D25_ARCHIVED: Final = (
    "notebooks/08_culture_society/D25_food_and_nutrition/"
    "D25_D25_food_and_nutrition.ipynb"
)


def _d25_code() -> str:
    cells = json.loads((ARCHIVE_ROOT / D25_ARCHIVED).read_text(encoding="utf-8"))["cells"]
    return "\n".join(
        "".join(c.get("source", [])) for c in cells if c["cell_type"] == "code"
    )


def test_d25_declares_the_atlas_that_d17_is_built_on() -> None:
    """Declared source 1 is the file D17 already covers."""
    source = _d25_code()
    assert "USDA Food Environment Atlas" in source
    assert "ers.usda.gov/data-products/food-environment-atlas" in source
    assert (REPO_ROOT / "projects" / "02-health-housing" / "D17_food_security"
            / "D17_food_security.ipynb").exists()


def test_d25_declares_wonder_which_refuses_automated_query() -> None:
    """Declared source 2 is the route D28 measured as refusing this client."""
    source = _d25_code()
    assert "wonder.cdc.gov" in source
    assert "DIABETES_RATE" in source
    assert (REPO_ROOT / "projects" / "02-health-housing" / "D28_mental_health"
            / "D28_mental_health.ipynb").exists()


@pytest.mark.parametrize("variable", ["FOOD_INSECURITY", "OBESITY_RATE", "GROCERY_STORES"])
def test_d25_declares_a_tract_or_county_grain_for_each_headline_variable(
    variable: str,
) -> None:
    """The declarations the measurements below contradict."""
    assert variable in _d25_code()


def test_d25_declares_tract_level_for_variables_in_a_county_only_file() -> None:
    """`levels: ['county', 'tract']` against a workbook with no tract sheet.

    The Atlas's nine data sheets are each keyed on county FIPS; D17 reads all
    nine. No tract grain exists in the file, so two of D25's three Atlas
    variables are declared at a geography the source does not publish.
    """
    source = _d25_code()
    assert "'tract'" in source or '"tract"' in source
    from krl_tutorials_data.sources import FEA_DATA_SHEETS

    assert len(FEA_DATA_SHEETS) == 9
    assert not any("tract" in sheet.lower() for sheet in FEA_DATA_SHEETS)


def test_d25_loader_is_a_stub() -> None:
    """Its own comment. Recorded because it decides what "rebuild" would mean."""
    assert "Simulate data loading" in _d25_code()
