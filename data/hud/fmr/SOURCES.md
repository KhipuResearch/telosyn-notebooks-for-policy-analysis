# HUD Fair Market Rents — pinned bulk files

Retrieved **2026-09-14**. Publisher: U.S. Department of Housing and Urban Development,
Office of Policy Development and Research (HUD USER).

Landing page: <https://www.huduser.gov/portal/datasets/fmr.html> (Revised Date 09/01/2026)

## What an FMR is

> "Fair Market Rents, as defined in 24 CFR 888.113 are estimates of 40th percentile gross
> rents for standard quality units within a metropolitan area or nonmetropolitan county."
> — HUD USER, FMR landing page

FMRs set payment standards for the Housing Choice Voucher program, renewal rents for some
expiring project-based Section 8 contracts, rent ceilings in HOME and the Emergency
Solutions Grants program, Continuum of Care maximums, and Public Housing flat rents.
42 USC 1437f requires them to be posted at least 30 days before they take effect, at the
start of the federal fiscal year. **The number is legally operative, not merely published.**

## Files

| Committed file | Upstream | Upstream bytes | Upstream SHA-256 |
|---|---|---|---|
| `FY27_FMRs.csv` | `/portal/datasets/fmr/fmr2027/FY27_FMRs.xlsx` | 375,708 | `423d1c6f8ef285a0fec63526768245396ec6fca0c9a086f21f709cc0ac89d1b7` |
| `FY26_FMRs.csv` | `/portal/datasets/fmr/fmr2026/FY26_FMRs.xlsx` | 376,572 | `ed9f59a601f47451ee3e7e6c466fba1c606b0f54d5807c89698594710616332d` |
| `FY26_FMRs_revised.csv` | `/portal/datasets/fmr/fmr2026/FY26_FMRs_revised.xlsx` | 367,248 | `0b130fd046c7bedbee5d206ab55654d390d27da423ff22e307e0698fbb56ad9c` |
| `FY27_Unadjusted.csv` | `/portal/datasets/fmr/fmr2027/FY27-Unadjusted-Rents.xlsx` | 65,815 | `abe7d3142d14b62a22e164a90e4fc692aede37fa8c1cb62561db8cc21518d2f7` |

### Derived-file digests (what is actually committed)

| File | Rows | Bytes on disk | SHA-256 |
|---|---|---|---|
| `FY27_FMRs.csv` | 4,764 | 551,121 | `a52b9f9a6cd7e8f227c270a70acefba1ffde35dd78d5fba6813037d0db6f68dc` |
| `FY26_FMRs.csv` | 4,764 | 164,539 | `63bab212511808e2ef6351b9e85e46eb87b024e5c4ddcc50d7f515c4f42afa12` |
| `FY26_FMRs_revised.csv` | 4,764 | 164,541 | `fe2162d980c506aebe6f6872ac1fbdb33448ddf66b2ec19d3342cf79fd78e5f8` |
| `FY27_Unadjusted.csv` | 1,057 | 61,340 | `5b447ab9551143b83203d4a7f9a092a7c8e6f1c6aba41142d50d4e4777522d42` |

## Derivation — stated exactly, because these are not the publisher's bytes

The committed CSVs are **derived** from the upstream `.xlsx` files. Three transformations
were applied, and nothing else:

1. **Sheet 1 → CSV.** Each workbook's first sheet only (`FY27_FMRs`, `FY26_FMRs`,
   `FY26_FMRs_revised`, `FY27-Unadjusted-Rents`). The `Field_Descriptions` sheet present in
   the three FMR workbooks is **not** committed.
2. **Trailing empty rows dropped.** Excel pads each sheet to its 1,048,576-row maximum; every
   row that is empty after removing commas was dropped. Data-row counts above are post-trim
   and were cross-checked against the row count computed at retrieval.
3. **Column subset, `FY26_FMRs` and `FY26_FMRs_revised` only.** Those two retain
   `fips, fmr_0, fmr_1, fmr_2, fmr_3, fmr_4`. Their remaining columns duplicate `FY27_FMRs`
   except where an FMR area changed between fiscal years; **do not join them on anything but
   `fips`.** `FY27_FMRs.csv` and `FY27_Unadjusted.csv` retain every column.

The upstream SHA-256 is of the publisher's `.xlsx` as fetched, computed before any
transformation. It is the digest to re-verify against HUD; the derived digest pins what this
repository holds.

## Retrieval path — and a correction

**An earlier revision of this file said `huduser.gov` is refused by the egress allowlist.
That was wrong**, and the error is left on the record rather than quietly rewritten.

What is actually true, from the response headers:

- `https://www.huduser.gov/portal/...` — where the bulk files live — answers a non-browser
  client with **HTTP 202, a zero-length body, and `x-amzn-waf-action: challenge`**. That is
  **HUD's own AWS WAF**, not the egress proxy and not an unreachable host. 202 is a success
  code, which is why it was misread: a client testing `status_code < 400` accepts it.
- `https://www.huduser.gov/hudapi/public/...` — the FMR API — is **not challenged** and
  works normally with a Bearer token (`HUD_API_KEY`), returning
  `x-ratelimit-limit: 60` per minute.

So these files were retrieved through a browser because the browser satisfies the WAF
challenge, not because the host was blocked. The diagnosis was corrected on 2026-09-14 after
reading the headers rather than the status code.

**What this means for reproducibility.** The API *can* re-fetch these values:
`krl_tutorials_data.sources.fetch_hud_fmr_county` does so, and D05 uses it to cross-check
these files against HUD directly. The pins below remain the right mechanism for the bulk
files — the API serves one entity at a time under a 60/minute limit, and it serves **only
the current value**, so the FY2026-as-first-published file has no API equivalent at all.

## Known hazards

- **The machine-readable copy on HUD's open-data portal is a fiscal year behind.** The
  ArcGIS layer `Fair_Market_Rents` (`services.arcgis.com/VTyQ9soqVukalItT`) carries **no
  fiscal-year field**, and its values match **FY2026**, not the FY2027 schedule in force.
  Verified on Abilene, TX MSA: ArcGIS 0BR 1010 / 2BR 1276 / 4BR 1987 = FY2026 exactly;
  FY2027 is 958 / 1310 / 2013.
- **FY2026 was revised after publication.** `FY26_FMRs_revised.xlsx` differs from
  `FY26_FMRs.xlsx` in **9 county rows across 7 FMR areas** (Los Angeles, Napa, San Luis
  Obispo, Asheville ×3, Transylvania, Corvallis, Albany OR), by +6.3% to +19.5%. HUD
  publishes no revision series: the change is visible only by differencing two files, and
  only if you know the second exists.
- **The geography changes between years.** 2,622 FMR areas in FY2026, 2,606 in FY2027.
- **Rows are county *and* town.** 4,764 rows, not 3,222 — New England town-level FMR areas
  are listed separately. `fips` is a 10-character county code (`SSCCC` + `99999`).

## Terms

HUD USER data are U.S. Government works, in the public domain within the United States.
<https://www.huduser.gov/portal/about/pdr_data_license.html>
