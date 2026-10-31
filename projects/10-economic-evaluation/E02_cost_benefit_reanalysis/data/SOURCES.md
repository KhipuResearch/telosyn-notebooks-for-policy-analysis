<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# Sources for E02

All values are U.S. Environmental Protection Agency figures, reproduced as data with their exhibit and PDF page. **The source document is not committed.**

## The document

| Item | Value |
|---|---|
| Title | *Economic Analysis for the Final Lead and Copper Rule Improvements*, U.S. EPA, October 2024 (774 PDF pages) |
| URL | `https://www.epa.gov/system/files/documents/2024-10/508_lcri_final_ea_10-21-2024.pdf` |
| Size | 9,589,288 bytes (the size approved by the owner; checked by a HEAD request before the body was fetched) |
| Last-Modified | Thu, 24 Oct 2024 18:07:44 GMT |
| Retrieved | 2026-10-30 (UTC), once, by `sources.fetch_epa_ria_pdf`; the retrieval record and the run ledger are kept beside the notebook and are committed with it |
| SHA-256 | `057c531f5bf14910f321a653bcdf341317676325b0d3dafeef4e874054bca350` |
| Cached | in a local cache directory outside any repository, never committed |

## The extracted tables

Produced by `scripts/extract_epa_lcri_tables.py <pdf> <dir>` (the script stops unless the PDF has the digest above, every year 2024 to 2058 is present for both
scenarios, each row's net equals benefits minus costs within 0.1, and the undiscounted net totals match the printed "$479 billion to $918 billion").

| File | SHA-256 | Content | Exhibit and PDF page |
|---|---|---|---|
| `epa_lcri_yearly_streams.csv` | `b1e361af472cf20707ac2310f3b6282ebac4c6cfd4928d44a8af459d410f8799` | yearly undiscounted incremental costs, benefits and net benefits, 2024 to 2058, millions of 2022 dollars; low and high scenarios | Exhibit 6-4 (low), PDF pages 709 and 710; Exhibit 6-5 (high), PDF pages 710 and 711 (document pages 6-8 to 6-10) |
| `epa_lcri_printed_annualized_2pct.csv` | `521ce3c50560b9b0f21bbe0d17d96be0d805167bcdeac74012ef67869d876d7c` | EPA's printed annualised incremental costs, benefits and net benefits at 2 percent; low and high | Exhibit 6-6, PDF page 711 (document page 6-10); the same values are printed in Exhibit ES-3 (PDF page 35) |

Check against EPA's printed totals: the sum of each scenario's yearly net benefits is $479,206.3 million (low) and $918,481.8 million (high); EPA's text on PDF page 708
(document page 6-7) says "Total undiscounted net benefits range from $479 billion to $918 billion".
