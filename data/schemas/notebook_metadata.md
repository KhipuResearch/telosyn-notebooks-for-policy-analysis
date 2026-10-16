<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# Notebook metadata

Every notebook carries a `krl` block in its notebook-level `metadata`. The release
gates read it; nothing in it is decorative. This page documents the fields the
gates act on. The retrieval record a notebook writes is documented separately in
[`README.md`](README.md).

## Fields in use

| Field | Type | Meaning | Checked by |
|---|---|---|---|
| `artifact_class` | string | One of `demo`, `simulation`, `tutorial`, `exploratory`, `predictive_study`, `causal_analysis`, `external_facing` | pedagogy gate |
| `data_mode` | string | One of `empirical`, `estimated`, `illustrative`, `hypothetical`. See *Reserved* below | pedagogy gate; no-synthetic gate; `test_gate_data_mode_reserved` |
| `data_sources` | array of string | The sources retrieved | evidence gate |
| `unit_of_analysis` | string | What one row is | evidence gate |
| `vintage_pinned` | `true`, `"digest"`, `false` or `"not_applicable"` | Whether a re-run is held to the same numbers, and by what | vintage gate |
| `synthetic_fallback` | boolean | Always `false` | no-synthetic gate |
| `identification` | object | The identification contract, below. Required in projects 09 and 13 and on causal notebooks in project 11 | identification gate (card F03) |

## `identification`

Introduced by [ADR 0009](../../DECISIONS/0009-expansion-architecture.md) §3.2.
Absent from every notebook in projects 01–08, which make no causal claim.

| Key | Type | Meaning |
|---|---|---|
| `design` | string | The research design, in words |
| `estimand` | string | What is estimated, for whom, and over what period |
| `assumption` | string | The identifying assumption, stated as an assumption |
| `falsification` | array of object | Each `{test, cell, result}`: a test that could have failed, the code cell that ran it, and `"stored"` |
| `inference` | string | How uncertainty is computed, and what is reported when the usual method is unreliable |
| `pap` | string | Repository-relative path of the pre-analysis plan, which lives beside the notebook |
| `pap_sha256` | string | SHA-256 of that file, recorded before the first retrieval |

The pre-analysis plan is declared **inside** this block (`identification.pap`),
not beside it, so that a plan and the contract it belongs to cannot be declared
apart. `tests/gate_support.py` exposes both through `Notebook.identification`
and `Notebook.pap`.

A falsification cell prints one line the gate reads:

```
FALSIFICATION: <test> | statistic=<number> | verdict=PASS
```

`verdict` is `PASS` or `FAIL`; a `FAIL` is a finding and is reported as one.

## Reserved: `data_mode: model` and `krl.model`

A third data mode, `model`, and a `krl.model` block (seed, calibration sources) are
**designed and not accepted in this release**. They are reserved for project 12,
which is held to the next release; see ADR 0009 §3.1.

A notebook that declares `data_mode: model` fails
`tests/test_gate_data_mode_reserved.py` with a message that names the ADR. The
mode is not a member of `DataMode` in `provenance.py`, and the provenance
record's `mode` field still takes only `empirical` or `illustrative`.
