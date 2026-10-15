<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
CONFIDENTIAL AND PROPRIETARY. See LICENSE for terms.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/brand/telosyn-white.png">
    <img src="assets/brand/telosyn-color.png" alt="telosyn" width="320">
  </picture>
</p>

# Telosyn Notebooks for Policy Analysis

[![CI](https://github.com/KhipuResearch/telosyn-notebooks-for-policy-analysis/actions/workflows/test.yml/badge.svg)](https://github.com/KhipuResearch/telosyn-notebooks-for-policy-analysis/actions/workflows/test.yml)
![Python 3.11 | 3.12](https://img.shields.io/badge/python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)
![License: Proprietary](https://img.shields.io/badge/license-Proprietary-7f1d1d)

**A reproducible portfolio of public-data case studies in Python: for each of
eighteen U.S. federal and institutional sources, what it measures, what it
withholds, and the specific conclusion it cannot carry.**

Thirty-three executable notebooks across eight projects, every retrieval pinned
by digest, every figure in the prose checked against stored output, and the
defects found during the build published alongside the results. Maintained by
**Telosyn, Inc.** as the methods foundation behind **Khipu**, our analyst
workspace for socioeconomic planning and public policy.

---

## Why this exists

Most published socioeconomic analysis is not wrong in its arithmetic. It is wrong
about what the arithmetic is entitled to claim — a modelled estimate ranked as
though it were measured, a county figure that is a state value copied down, a
margin of error dropped somewhere between the API and the chart.

These are not exotic failures. They are the ordinary result of treating a public
dataset as a table of numbers rather than as a published instrument with a
documented method and stated limits. This corpus is the counter-practice.

## Projects

| # | Project | Notebooks | Sources | The lesson |
|---|---|---|---|---|
| 01 | [Fundamentals](projects/01-fundamentals/) | 4 | Census ACS, BLS LAUS, FRED | Margins of error carried through derived figures; a rate that falls for two opposite reasons; a revised series is not the series you acted on |
| 02 | [Health and Housing](projects/02-health-housing/) | 7 | CDC PLACES and NCHS, HUD FMR and CHAS, USDA ERS, Census ACS | A modelled small-area estimate is not a measurement; a published number can be an administrative decision; a county column that is a state value |
| 03 | [Inequality and Demographics](projects/03-inequality-demographics/) | 3 | Census ACS | Which inequality measure, and why it matters; crude rates are weighted averages; one question, three published answers |
| 04 | [Economy and Industry](projects/04-economy-industry/) | 2 | BLS QCEW, Census CBP | Data withheld on purpose and published as zero; two agencies, opposite ways to hide the same cell |
| 05 | [Social Systems](projects/05-social-systems/) | 6 | Opportunity Atlas, Social Capital Atlas, Census BDS, Census ACS | A measurement of a place that no longer exists; a cross-tab that disproves its own inference; parts that do not sum |
| 06 | [Infrastructure and Environment](projects/06-infrastructure-environment/) | 3 | EPA TRI, Census ACS | When every number says how it was made; the universe that walked away; two ways to publish a number that is not there |
| 07 | [Justice and Equity](projects/07-justice-equity/) | 4 | FBI CDE, MIT Election Lab, Census ACS | When the coverage is the variable; a file with no sampling error at all; a series that is not a partition |
| 08 | [Culture and Society](projects/08-culture-society/) | 4 | BEA, IRS BMF, Zillow, FRED, Census ACS | The number is the boundary; a sector you cannot size; a concept the data cannot resolve |

Every notebook is listed with its thesis in [`docs/project-index.md`](docs/project-index.md).
Each project's README is generated from its notebooks and states, per notebook,
what it shows, which sources it draws on and where it stops.

## The rules the corpus holds itself to

**Real data only.** There is no synthetic fallback anywhere. If a source is
unreachable, or a key is missing, or a value falls outside its declared plausible
range, the notebook *stops* rather than substituting a number so the cells below
can keep running. A gate enforces this. One artifact is permitted to simulate —
D30, which exists to score an analysis against a truth known by construction — and
it is marked `data_mode: illustrative` and excluded by name.

**Nothing is reported that was not computed.** Every figure in a notebook's prose
must appear in that notebook's stored output. The methodology handbook's own
claims are tagged to the notebook that produced them, and a gate re-checks each
number against it, so the documentation cannot drift from the code while still
reading as authoritative.

**A vintage is declared or its absence is justified.** Each notebook records
whether a re-run returns the same numbers, and why: the publisher serves prior
vintages, or it does not and the retrieval is pinned to a verified digest so a
change raises instead of passing silently, or neither, with the reason stated.

**The failures are published.** The handbook carries a self-audit — 37 recorded
defects found in this work, what each one was, what caught it, and what changed.
Several were caught only because a check was written to catch them and then
deliberately attacked. It is the section we would point a sceptical reader to
first.

## Reproduce

```bash
git clone https://github.com/KhipuResearch/telosyn-notebooks-for-policy-analysis.git
cd telosyn-notebooks-for-policy-analysis
pip install -e '.[notebooks,test]'
pytest tests/                                  # 1,500+ tests; no network, no keys
jupyter lab projects/                          # the notebooks need your own free API keys
```

What a re-run does and does not reproduce — and why — is stated plainly in
[`docs/reproducibility.md`](docs/reproducibility.md). The short version: every
result is committed and readable without running anything; 35 of 40 retrievals
replay byte-for-byte; the exceptions are named, not hidden.

## Methodology

Each notebook states its question, names the source and vintage, records every
retrieval with a digest, carries uncertainty through every derived figure, and
ends by stating what its source cannot support. [`docs/methodology.md`](docs/methodology.md)
is the handbook behind that — 2,270 lines on the fourteen data regimes the corpus
has met (§1), the vintage policy (§5), what a ranking may claim (§7), and the
self-audit (§11).

## Built with

`pandas` · `numpy` · `scipy` · `statsmodels` · `scikit-learn` · `matplotlib` · `requests` · `pytest`

The package itself depends only on the first three and `requests`. Nothing here
requires any private package.

## Where to start

| You want | Read |
|---|---|
| The shortest honest tour | `projects/01-fundamentals/D01_income_and_poverty/` — ACS income and poverty, margins of error handled properly |
| The methodological spine | `docs/methodology.md` — §1 for the regimes, §5 for vintage policy, §7 for what a ranking may claim |
| Evidence of self-scrutiny | Handbook §11, the self-audit |
| A source that cannot answer the question asked of it | `projects/08-culture-society/D22_nonprofit_arts/` — the sector cannot be sized from the IRS file, and the notebook says so with the bound |
| What the release gates check | `tests/test_gate_*.py` |

## Repository layout

| Path | What it is |
|---|---|
| `projects/` | Eight numbered projects; each notebook sits with its provenance records and each project has a generated README |
| `src/krl_tutorials_data/` | Fail-closed clients for each source, with provenance, uncertainty, bracket and tabulation helpers |
| `data/` | Provenance documentation and the two HUD schedules the API does not serve |
| `docs/` | The methodology handbook, reproducibility statement, project index, source map, migration record and the audit of record |
| `tests/` | The suite, including the nine release gates that run against every notebook |
| `scripts/` | Verification and generation tools |
| `DECISIONS/` | Architecture decision records |

## License

**Proprietary.** © 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved. The Software is the
exclusive property of Deloatch, Williams, Faison & Parker, LLLP and is licensed
exclusively to Telosyn, Inc. See [LICENSE](LICENSE).

Khipu℠ is a service mark of Telosyn, Inc.

This is **not** open-source software. It may not be copied, modified,
redistributed, or used to create derivative works without prior written consent.
Public visibility grants nothing.

## Contact

contact@telosyn.co

---

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Khipu℠ is a service mark of Telosyn, Inc.
