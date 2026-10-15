"""Gate 1 — the metadata and teaching contract.

Every notebook must state learning objectives and a summary,
and to include exercises. In the audited corpus 1 of 33 had objectives and 0 of
33 had exercises, because the CI step that checked carried
``continue-on-error: true`` (F-15).

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import re

from gate_support import Notebook

VALID_CLASSES = {
    "demo", "simulation", "tutorial", "exploratory",
    "predictive_study", "causal_analysis", "external_facing",
}
VALID_MODES = {"empirical", "estimated", "illustrative", "hypothetical"}

SECTIONS = (
    ("learning objectives", re.compile(r"##\s*learning objectives", re.I)),
    ("prerequisites", re.compile(r"##\s*prerequisites", re.I)),
    ("data sources", re.compile(r"##\s*data (?:sources|provenance)", re.I)),
    ("limitations", re.compile(r"##\s*limitations", re.I)),
    ("key takeaways", re.compile(r"##\s*key takeaways", re.I)),
    ("exercises", re.compile(r"##\s*exercises", re.I)),
    ("references", re.compile(r"##\s*references", re.I)),
)


def test_artifact_class_is_declared(notebook: Notebook) -> None:
    krl = notebook.metadata.get("krl")
    assert krl, f"{notebook.path.name} declares no `krl` metadata block."
    cls = krl.get("artifact_class")
    assert cls in VALID_CLASSES, (
        f"{notebook.path.name} has artifact_class={cls!r}; must be one of {sorted(VALID_CLASSES)}"
    )
    mode = krl.get("data_mode")
    assert mode in VALID_MODES, (
        f"{notebook.path.name} has data_mode={mode!r}; must be one of {sorted(VALID_MODES)}"
    )


def test_required_sections_present(notebook: Notebook) -> None:
    md = notebook.markdown_source
    missing = [name for name, rx in SECTIONS if not rx.search(md)]
    assert not missing, (
        f"{notebook.path.name} is missing required sections: {', '.join(missing)}"
    )
