"""The provenance note says what the ACS product it describes measures.

A 1-year record once carried the sentence about 5-year estimates; the note now follows the product.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from krl_tutorials_data import sources


class _Session:  # pylint: disable=too-few-public-methods
    """Answers every request with a one-row ACS table."""

    def get(self, url: str, **kwargs: Any) -> Any:  # pylint: disable=unused-argument
        """Answer."""
        rows = [["NAME", "B01001_001E", "state"], ["Alabama", "100", "01"]]

        class _Response:  # pylint: disable=too-few-public-methods
            status_code = 200
            headers = {"content-type": "application/json"}
            content = json.dumps(rows).encode()
            text = content.decode()

            @staticmethod
            def json() -> Any:
                """Body as JSON."""
                return rows

        return _Response()


@pytest.fixture(autouse=True)
def _stub_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub the key lookup."""
    monkeypatch.setattr(sources, "load_key", lambda name, **_: "stub-not-a-credential")


@pytest.mark.parametrize(
    ("dataset", "must_contain", "must_not_contain"),
    [
        ("acs/acs5", "5-year estimates are period estimates", "1-year"),
        ("acs/acs1", "1-year estimates describe a single calendar year", "5-year"),
    ],
)
def test_the_note_follows_the_product(
    dataset: str, must_contain: str, must_not_contain: str
) -> None:
    """A 1-year record does not describe itself as a 5-year one, and the reverse."""
    _, prov = sources.fetch_acs(
        year=2019, variables={"B01001_001E": "Total"}, dataset=dataset, session=_Session()
    )
    text = " ".join(prov.notes)
    assert must_contain in text and must_not_contain not in text


def test_an_unknown_product_makes_no_claim_about_its_period() -> None:
    """Anything else gets a neutral sentence, not a guess."""
    assert "defined by the product" in sources.acs_period_note("acs/acsse")
