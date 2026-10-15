# HUD CHAS — pinned county extract

Retrieved **2026-09-14** from the HUD USER CHAS API, not from a bulk download.

Publisher: U.S. Department of Housing and Urban Development, Office of Policy Development and
Research. Endpoint: `https://www.huduser.gov/hudapi/public/chas` (`type=3`, county summary
level), one request per county, `HUD_API_KEY` required.

## What CHAS is

Each year the Census Bureau produces a **custom tabulation** of American Community Survey
microdata to HUD's specification, cross-cutting household income — measured against HUD's Area
Median Family Income (HAMFI) — with housing problems and tenure. Local governments use it to
plan how HUD funds are spent.

## Files

| File | Rows | Bytes | SHA-256 |
|---|---|---|---|
| `VA_2018-2022_county.csv` | 133 | 99,339 | `2ea228f3bdcbb32b2df1fc48f98cb307ee08a9e6d5a60e9958ed3dc7b17383b5` |
| `VA_2018-2022_no_rows.txt` | 1 id | — | entity ids HUD lists and serves no rows for |

133 rows is every Virginia county-equivalent (95 counties + 38 independent cities).

## Why this is pinned rather than fetched in-notebook

HUD paces the API at 60 requests per minute and a county sweep is one request per county, so a
full state takes minutes. That is a property of the source, not of the network, and it is the
same reason the FMR files next door are pinned. The notebook makes a handful of live calls for
the API-behaviour findings and reads this extract for the county statistics.

## Vintage — and the reason it is stated, not defaulted

`year=2018-2022`, named explicitly. The API's default is "the latest range", which moves. Note
that HUD's own API documentation lists year ranges only up to `2014-2018` while `2016-2020`,
`2017-2021` and `2018-2022` are all served: **the documentation is not the authority on which
vintages exist.** `2019-2023` returns HTTP 200 with no rows, so as of this retrieval CHAS is
one full ACS release behind — ACS 2023 5-year is published and CHAS has not been rebuilt on it.

## Known hazards, all verified on this extract

- **No margins of error.** 129 coded columns, none of them a margin, although every count
  descends from a survey that publishes one.
- **Twenty columns are empty in every county, and this is NOT suppression.** 2,660 of 17,157
  coded cells (15.5%) are empty, and every one is accounted for by 20 columns that are empty in
  all 133 counties; **zero columns vary between counties**. Disclosure suppression responds to
  cell size and must therefore vary. All 20 are the "cost burden not available, no other
  problems" family, which HUD's own release note says was **combined** into the neighbouring
  category for the 2018+ tables rather than suppressed. The category was retired; the column,
  the dictionary entry and the empty field all remain. Kept as `NaN`, never `0`, which is what
  makes it visible.

  *An earlier revision of this file called it disclosure avoidance, on the strength of HUD's
  release note mentioning suppression elsewhere. The data contradicts that and the correction
  is recorded rather than rewritten.*
- **Six documented columns are never served**: `G21`, `G22`, `G23`, `H17`, `I17`, `J17`.
- **Three dictionary entries are wrong.** HUD documents `H14`, `I14` and `J14` identically to
  `H13`, `I13` and `J13`. The data contradicts this: the second of each pair is never larger and
  usually smaller, consistent with it being the ">50%" cut rather than a repeat of ">30%".
  The dictionary also carries a stray comma in the property name `A3,`.
- **The county index repeats itself**: 267 served rows for 134 distinct counties, every id
  twice. Iterating it as served double-counts every household in the state.
- **A zero-padded entity id returns nothing.** `entityId=59` is Fairfax County; `entityId=059`
  returns HTTP 200 and `[]`. The same publisher's FMR API requires the *padded* ten-character
  form. Two APIs, one publisher, one county, incompatible spellings, neither refusing the wrong
  one.
- **The index lists a jurisdiction that no longer exists.** Entity id `515` (Bedford city,
  which reverted to a town within Bedford County in 2013) is listed and serves no rows.

## Terms

HUD USER data are U.S. Government works, in the public domain within the United States.
<https://www.huduser.gov/portal/about/pdr_data_license.html>
