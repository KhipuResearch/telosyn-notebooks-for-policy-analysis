<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# Census Bureau CPS ASEC 2024 — person replicate weights (not committed)

Publisher: U.S. Census Bureau. Page: <https://www.census.gov/data/datasets/time-series/demo/cps/cps-asec.2024.html>
(the replicate-weight section). Owner approval 2026-10-28 for exactly these three files and no others.

## Files

All under `https://www2.census.gov/programs-surveys/cps/datasets/2024/march/`:

| File | Bytes | SHA-256 |
|---|---|---|
| `CPS_ASEC_ASCII_REPWGT_2024.ZIP` | 73,050,090 | `ddb5cbf3c0d4ff6c56e3928a3d7fb78f079ba4c7d0e52c709282294fe5e48ac3` |
| `CPS_ASEC_ASCII_REPWGT_2024.SAS` | 10,093 | `3e5d1de838701cdde10352abc382a846ed0086e25c914234850c7a95c2fb4856` |
| `2024_ASEC_Replicate_Weight_Usage_Instructions.docx` | 79,166 | `a842240dc56e1bf73d9fb0aac1d2578427af2d3e8338e410f79c1e4a730f36a8` |

The `.DAT.GZ` of the same weights and the public-use person file are **not** used.

## Where they live

`fetch_cps_asec(replicates=True)` downloads them itself, for any reader, into a cache outside the repository
(`~/.cache/telosyn-notebooks/cps_asec_2024`, or under `$TELOSYN_CACHE_DIR`), refuses a cache inside the repository or
under a synced folder, checks every file's size and SHA-256 against the table above and removes and refuses a file that
differs. They are never committed. Each file is recorded in the notebook's provenance with its URL, size and digest.

## What the files say

- **Layout (from the `.SAS` file).** 161 weights `pwwgt0`–`pwwgt160`, each a nine-character field with four implied decimals,
  then the match keys `h_seq` (five digits, matched to `PH_SEQ`) and `pppos` (two characters); record length 1,456 plus a newline.
  The file has 144,265 records, the number of person records the API returns. The SAS file's 161 published column sums are reproduced
  by this layout to within 0.0000002.
- **A discrepancy in the Bureau's own documents.** The usage instructions (section "File Creation") describe ten-digit weights, keys at
  columns 1,611–1,617 and a record length of 1,617. That does not match the `.SAS` file or the data file. The `.SAS` layout is
  the one used because it reproduces the published sums and the record count.
- **Variance (usage instructions, formula 1, read from the formula in the document).** `var(theta_0) = (4/160) * sum_{i=1..160} (theta_i - theta_0)^2`,
  with `theta_0` the estimate on the full-sample weight (`PWWGT0`, which is `MARSUPWT` in the API) and `theta_i` the same estimate on
  replicate weight `i`. The instructions say the replicate weights are for variance estimation only, not for point estimates.
