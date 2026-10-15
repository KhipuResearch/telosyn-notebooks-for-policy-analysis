"""Gate 4 — statistical invariants.

Catches F-3 (target selected by column position, constant target), F-12
(preprocessing fitted before the split; target among the predictors).

These are structural checks on notebook source. They cannot prove a model is
correct; they reject constructions that are known to be wrong.

SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import re

from gate_support import Notebook

# The exact defect from F-3: the estimand inferred from dataframe column order.
TARGET_BY_POSITION = re.compile(
    r"(?:target\w*|y)\s*=\s*\w*(?:df|data|frame)\w*\[\s*\w*(?:numeric_)?cols\w*\[\s*-?\d+\s*\]\s*\]"
    r"|target_col\s*=\s*\w*cols\w*\[\s*-?\d+\s*\]",
    re.I,
)

# Fitting a transformer on everything, then splitting.
FIT_TRANSFORM = re.compile(r"\b(\w+)\.fit_transform\s*\(", re.I)
SPLIT_CALL = re.compile(r"\btrain_test_split\s*\(|\.split\s*\(", re.I)

REQUIRED_ASSERTIONS = (
    ("target is explicitly named", re.compile(r"TARGET\s*[:=]|target_column\s*[:=]", re.I)),
    ("target variance is asserted non-zero", re.compile(r"\.var\(\)|nunique\(\)|assert_target", re.I)),
)


def test_target_is_not_selected_by_column_position(notebook: Notebook) -> None:
    hits = [
        f"cell {c.index}: {m.group(0).strip()!r}"
        for c in notebook.code
        for m in TARGET_BY_POSITION.finditer(c.source)
    ]
    assert not hits, (
        f"{notebook.path.name} infers the estimand from dataframe column order. "
        f"This produced R2=1.000 against a constant `year` column in the audited "
        f"corpus (F-3). Name the target explicitly:\n  " + "\n  ".join(hits)
    )


#: A real model fit, not any token that happens to contain "OLS".
#: The bare substring matched MEASURE_COLS and fired this gate on a notebook
#: that fits nothing.
MODEL_FIT = re.compile(
    r"\b(?:sm\.OLS|smf\.ols|sm\.GLM|sm\.Logit|OLS)\s*\(|"
    r"\.fit\s*\(|\bLinearRegression\s*\(|\bRidge\s*\(|"
    r"\bRandomForest\w*\s*\(|\bLogisticRegression\s*\("
)


def test_target_is_named_and_validated(notebook: Notebook) -> None:
    src = notebook.code_source
    if not MODEL_FIT.search(src):
        return  # not a modelling notebook
    missing = [label for label, rx in REQUIRED_ASSERTIONS if not rx.search(src)]
    assert not missing, (
        f"{notebook.path.name} fits a model without: {', '.join(missing)}. "
        f"A constant or implicit target is the F-3 defect."
    )


def test_preprocessing_is_not_fitted_before_the_split(notebook: Notebook) -> None:
    """A transformer fitted on the full frame before splitting leaks the test set."""
    cells = notebook.code
    first_fit_transform = next(
        (c.index for c in cells if FIT_TRANSFORM.search(c.source)), None
    )
    first_split = next((c.index for c in cells if SPLIT_CALL.search(c.source)), None)
    if first_fit_transform is None or first_split is None:
        return
    assert first_fit_transform > first_split, (
        f"{notebook.path.name} calls .fit_transform() in cell {first_fit_transform}, "
        f"before the split in cell {first_split}. Statistics from the held-out data "
        f"are baked into training (F-12). Fit inside the training fold, or use a "
        f"Pipeline passed to the cross-validator."
    )
