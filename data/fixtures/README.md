<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# Fixtures

The suite runs without network or keys because every client is exercised
against recorded responses. Those fixtures live with the tests rather than
here — `tests/fixtures/` holds `mock_census_acs.py`, `mock_bls_qcew.py`,
`mock_hud_chas.py` and `mock_irs990.py` — so that a change to a client and a
change to its fixture are reviewed together.

Nothing synthetic is used to produce a result in any notebook. The one
notebook that simulates, D30, is marked `data_mode: illustrative` and exists
to score an analysis against a truth known by construction; it does not stand
in for a retrieval.

```bash
pytest tests/          # exercises every client against its fixture
```
