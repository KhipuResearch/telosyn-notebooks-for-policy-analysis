<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# Schemas

This corpus does not build one estimation-ready table per project; each notebook
retrieves the published table it needs and works on it directly, so the schema of
record for any analysis is the **publisher's own variable definitions**, and the
provenance record beside the notebook names exactly which variables were pulled.

## The provenance record

Every retrieval writes one JSON record to the notebook's `provenance/` directory.
All forty records carry the same fields; `request_method` is present on the
twenty-five written after it was added.

| Field | Type | Meaning |
|---|---|---|
| `source_name` | string | Publisher, as it names itself |
| `dataset` | string | The table or series, in the publisher's terms |
| `vintage` | string | Release, year or cohort the data belong to; the basis for reproducibility |
| `endpoint` | string | The URL requested |
| `variables` | object | Variable code → the publisher's label for it. This is the data dictionary for that retrieval |
| `request_params` | object | The request, with credential values replaced by `<redacted>`; structure preserved so the request is replayable |
| `request_method` | string | `GET` or `POST` |
| `retrieved_utc` | string | ISO-8601 timestamp of the retrieval |
| `row_count`, `column_count` | integer | Shape of the payload as read |
| `content_sha256` | string | Digest of the payload on the basis below |
| `hash_basis` | string | `response-bytes`, `canonical-rows`, `canonical-stable-json` or `composed-digests` — see [`data/README.md`](../README.md) |
| `pinned` | boolean | Whether a re-run is held to `content_sha256` |
| `mode` | string | `empirical`, or `illustrative` for the one simulated artifact |
| `notes` | array of string | Caveats the client attached at retrieval time: margins of error, suppression, controlled totals |

A machine-readable copy of this schema is in [`provenance_record.json`](provenance_record.json).

## Notebook metadata

The `krl` block each notebook carries, including the identification contract
used by the causal projects and the reserved `model` mode, is documented in
[`notebook_metadata.md`](notebook_metadata.md).

## Local files

The two HUD schedules under `data/hud/` have their column definitions in the
`SOURCES.md` beside them, which also records the download URL, the retrieval
date and the publisher's own documentation.
