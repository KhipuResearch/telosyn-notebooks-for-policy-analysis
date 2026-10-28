"""The ACS provenance note says whether margins of error were retrieved.

The note used to say margins of error "are not retrieved here" whenever it was written, including when a notebook
asked for the margin-of-error variables (codes ending in M) and used them. It now follows the request.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import pytest

from krl_tutorials_data import sources
import json
from typing import Any


class _Session:  # pylint: disable=too-few-public-methods
    """Answers every request with a one-row ACS table holding an estimate and its margin of error."""

    def get(self, url: str, **kwargs: Any) -> Any:  # pylint: disable=unused-argument
        rows = [["NAME", "B01001_001E", "B01001_001M", "state"], ["Alabama", "100", "5", "01"]]

        class _Response:  # pylint: disable=too-few-public-methods
            status_code = 200
            headers = {"content-type": "application/json"}
            content = json.dumps(rows).encode()
            text = content.decode()

            @staticmethod
            def json() -> Any:
                return rows

        return _Response()


@pytest.fixture(autouse=True)
def _stub_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sources, "load_key", lambda name, **_: "stub-not-a-credential")


def test_estimates_only_say_margins_were_not_retrieved() -> None:
    _, prov = sources.fetch_acs(year=2019, variables={"B01001_001E": "Total"}, dataset="acs/acs1", session=_Session())
    assert "not retrieved here" in " ".join(prov.notes)


def test_a_request_that_includes_margins_of_error_says_they_were_retrieved() -> None:
    labels = {"B01001_001E": "Total", "B01001_001M": "Total, margin of error"}
    session = _Session()
    _, prov = sources.fetch_acs(year=2019, variables=labels, dataset="acs/acs1", session=session)
    text = " ".join(prov.notes)
    assert "not retrieved here" not in text
    assert "margins of error were requested with the estimates" in text


def test_the_helper_names_the_margin_variables_it_saw() -> None:
    assert "B01001_001M" in sources.acs_moe_note({"B01001_001E": "x", "B01001_001M": "y"})
    assert "not retrieved here" in sources.acs_moe_note({"B01001_001E": "x"})
