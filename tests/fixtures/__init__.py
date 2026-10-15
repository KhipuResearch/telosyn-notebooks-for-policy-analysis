# © 2026 Telosyn, Inc. All rights reserved.
# Exclusively licensed to Deloatch, Williams, Faison & Parker, LLLP.
#
# CONFIDENTIAL AND PROPRIETARY. Unauthorized use, reproduction, or
# distribution is strictly prohibited. See LICENSE for terms.

"""Mock-fixture infrastructure for L15 cardinality regression tests.

D-S4-010 W3-039 Block 3 deliverable per architect ratification 2026-04-30.

Public API
----------
- :class:`MockBLSQcew` — BLS QCEW connector mock (D02 dependency)
- :class:`MockCensusACS` — Census ACS public connector mock (D02/D06/D07/D27 shared)
- :class:`MockIRS990` — ProPublica IRS 990 connector mock (D06/D27 dependency)
- :class:`MockHUDCHAS` — HUD CHAS connector mock (D27 dependency)

Each fixture provides a context manager activating ``responses`` URL
matchers that return cardinality-matching synthetic data so per-tutorial
papermill invocations execute deterministically without LIVE upstream
calls (per D-S4-010 §4 boundary clause).

Pattern reference: W3-040 PR #50 G2-MINOR-10 NEW-tests precedent.
"""

from fixtures.mock_bls_qcew import MockBLSQcew
from fixtures.mock_census_acs import MockCensusACS
from fixtures.mock_hud_chas import MockHUDCHAS
from fixtures.mock_irs990 import MockIRS990

__all__ = ["MockBLSQcew", "MockCensusACS", "MockHUDCHAS", "MockIRS990"]
