<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# CBO — The Distribution of Household Income, 2023 (supplemental data) — pinned bulk file

Publisher: Congressional Budget Office. Publication: <https://www.cbo.gov/publication/62761>
(*The Distribution of Household Income, 2023*, September 2026). A work of the U.S. Government.

## File

| File | Bytes | SHA-256 |
|---|---|---|
| `62761-supp-data.xlsx` | 263,423 | `e91c2e8e5012628d8e884e5ad4fc86f2f004cad9113708bbc1038d7ab7b4acbd` |

Source URL: `https://www.cbo.gov/system/files/2026-09/62761-supp-data.xlsx` — listed on the
publication page as "Supplemental Data", 263,423 bytes.

## How it was obtained

By the owner, in a browser, on 2026-10-27; the byte count was checked against the size the publisher's server
reports for that URL. A scripted
client gets HTTP 403 from the publisher's bot protection (DataDome), including `curl` with this
repository's neutral User-Agent, so there is no fetcher for it and none will disguise itself to
get past that. Load the file through `connectors.BulkFileSource` and `frame_from_bulk_file`, which
fail closed if the bytes differ from the digest above.

## What is in it

Twelve tables, 1979 to 2023, by income quintile and by the top of the distribution, in 2023
dollars rounded to the nearest hundred (shares to a tenth). Income groups rank households by income
before transfers and taxes, adjusted for household size (the minimum for a household of size *n* is
the size-1 minimum times the square root of *n*); each quintile holds about the same number of
people. A household with negative income is left out of the lowest group but kept in the totals.
*Income before transfers and taxes* is market income plus social insurance benefits; *means-tested
transfers* and *federal taxes* are what the household receives and owes. The notes on the first
sheet state the definitions.

## Re-acquiring

CBO posts each edition under a dated path and may revise a table in place. A different digest means a
different vintage: create a new folder with its own manifest rather than updating the pin here.
