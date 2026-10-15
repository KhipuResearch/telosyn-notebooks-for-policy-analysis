# Zillow Research - pinned bulk sources

**Vintage `2026-08` - the August 2026 release, series through July 2026.**

Acquired 2026-09-13 for the D05/D27 gentrification work. The CSVs are **not committed**
(see `.gitignore`); this manifest is what reproduces the acquisition. Load them through
`krl_tutorials_data.connectors.BulkFileSource`, which fails closed if the bytes differ.

Publisher terms of use: <https://www.zillow.com/corporate/terms-of-use/>

## Files

| Dataset | File | Bytes | Rows | Series | SHA-256 |
|---|---|---|---|---|---|
| ZHVI, All Homes (SFR/Condo), smoothed & seasonally adjusted, county | `County_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv` | 13,520,396 | 3,071 | 2000-01-31 to 2026-07-31 | `8ea53a5461073e62b1d7f0eb216290954246f56ba344a227956665ab19c2b271` |
| ZORI, All Homes Plus Multifamily, smoothed, county | `County_zori_uc_sfrcondomfr_sm_month.csv` | 1,923,888 | 1,392 | 2015-01-31 to 2026-07-31 | `302a5f5b5f594ea978079cbc4111bf4c33baa8677ddf368792f2e18f143f46d4` |

## Source URLs

```
https://files.zillowstatic.com/research/public_csvs/zhvi/County_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv
https://files.zillowstatic.com/research/public_csvs/zori/County_zori_uc_sfrcondomfr_sm_month.csv
```

Confirmed by driving the dropdowns on <https://www.zillow.com/research/data/> rather than
by guessing the URL pattern. Note the ZHVI User Guide link on that page 404s as of this date.

## Coverage - read this before designing a measure

| | Counties | Matched to ACS 2023 (3,222) |
|---|---|---|
| ZHVI | 3,071 | 3,063 (95.1%) |
| ZORI | 1,392 | 1,384 (**43.0%**) |

**ZORI is the binding constraint on any rent-side measure.** It covers 43% of counties, and
not at random: ZORI needs listing volume, so the covered counties are the larger and denser
ones - a selection on precisely the variable a gentrification analysis is about. A rent-side
measure restricted to ZORI counties is not a national measure and must not be shown as one.

Eight Zillow counties have no ACS 2023 match, consistent with FIPS reorganisation
(Connecticut planning regions, Alaska renames). Reconcile before joining.

## Re-acquiring

Zillow overwrites these files in place each release, so re-downloading yields a **different**
vintage whose digest will not match these pins. That is the guard working. Create a new
`data/zillow/<release>/` folder with its own manifest rather than updating the pins here.
