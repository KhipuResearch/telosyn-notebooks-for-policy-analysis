"""Gate -- `data_mode: model` is reserved and not accepted in this release.

DECISIONS/0009 section 3.1 designs a third data mode, ``model``, for a structural
or stochastic model calibrated to pinned inputs, and holds it to the release that
ships project 12. Until then no notebook may declare it. The reservation is
enforced here, because a reservation nothing checks is a permission.

The planted-violation test proves the check can fail: a gate that cannot fail is
counted as coverage.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

from typing import Any

from gate_support import Notebook

ADR = "DECISIONS/0009-expansion-architecture.md"
RESERVED_MODE = "model"


def reserved_mode_message(name: str, krl: dict[str, Any]) -> str | None:
    """Return the failure message, or ``None`` when the block is acceptable.

    Complexity O(1). A ``krl.model`` block with no ``data_mode: model`` is also
    refused: declaring the block is declaring the mode by another route.
    """
    declares_mode = krl.get("data_mode") == RESERVED_MODE
    declares_block = "model" in krl
    if not (declares_mode or declares_block):
        return None
    what = "data_mode='model'" if declares_mode else "a `krl.model` block"
    return (
        f"{name} declares {what}. The `model` data mode is reserved and not "
        f"accepted in this release (project 12 is held to the next release); "
        f"see {ADR} section 3.1. Declare `empirical`, or remove the block."
    )


def test_model_data_mode_is_reserved(notebook: Notebook) -> None:
    """No notebook in the corpus declares the reserved mode or block."""
    message = reserved_mode_message(notebook.path.name, notebook.krl)
    assert message is None, message


def test_the_reservation_fails_a_planted_violation() -> None:
    """The check can fail: both routes to the reserved mode are refused."""
    planted = reserved_mode_message("planted.ipynb", {"data_mode": "model"})
    assert planted is not None and ADR in planted
    assert reserved_mode_message("planted.ipynb", {"model": {"seed": 1}}) is not None
    assert reserved_mode_message("ok.ipynb", {"data_mode": "empirical"}) is None
