<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# ADR 0004 — Retraction: the bulk-acquisition layer exists (`krl-data-connectors`)

- **Status:** Accepted — claim retracted, dependent statements corrected
- **Deciders:** B. (correction raised); rebuild author (claim withdrawn)
- **Date:** 2026-09-13

## 1. Title

`notebooks_v2/SOURCE_MAP.md`, `notebooks_v2/MIGRATION.md`, the D27 notebook metadata and
commit `8b16891` all asserted that a bulk-file acquisition layer "does not exist" and that
Tier B was blocked on building one. **That claim is false and is withdrawn.**

## 2. What was claimed

> "A bulk-file acquisition layer with checksums, vintage pinning and a retention policy —
> this is the actual long pole, and it is infrastructure, not content."
> — `SOURCE_MAP.md`, sequencing item 2

> "Gentrification … is NOT covered — it declared Zillow bulk files, and that acquisition
> layer does not exist."
> — commit `8b16891`, and the D27 `scope_note`

## 3. What is actually the case

`krl-data-connectors` exists, is substantial, and is a **hard dependency of this repository**:

| Evidence | Location |
|---|---|
| `krl-data-connectors>=1.0.0`, class **hard**, "Notebook imports fail" if absent | `pyproject.toml:36`, `ARCHITECTURE.md:84` |
| "Exercised through `krl-data-connectors` patterns, not direct HTTP here" | `ARCHITECTURE.md:108` |
| Zillow Research connector, 557 lines | `professional/housing/zillow_research.py` |
| Eviction Lab connector | `professional/housing/eviction_lab.py` |
| HUD CHAS connector — genuinely fetches ZIPs over HTTP | `professional/housing/hud_chas.py` |
| HUD Fair Market Rents connector | `professional/housing/hud_fair_market_rents.py` |
| `BaseConnector` with cache dir (`~/.krl_cache`), SHA-256 cache keying | `base_connector.py:121-415` |
| Rate limiter, connector registry, licensing mixin | `core/rate_limiter.py`, `core/connector_registry.py` |

The housing connectors cover **exactly** the sources Tier B was said to be blocked on.

## 4. The gap that does remain, stated precisely

Zillow Research and Eviction Lab publish **no API**; both publishers distribute CSV/bulk files.
Those two connectors therefore *parse, filter, license and cache* files that a human places on
disk — they do not fetch. `eviction_lab.py` raises explicitly instructing the caller to use the
bulk download.

So the outstanding work for a gentrification notebook is **manual file placement plus a
defensible vintage pin**, not infrastructure to be built. That is a materially smaller and
differently-shaped gap than the one claimed, and it changes Tier B sequencing.

## 5. How the error happened, and the rule it broke

The claim was made from the contents of `the private source repository` alone, without reading the sibling
repository that `the private source repository`' own `pyproject.toml` declares as a hard dependency.

This is the same failure mode the audit exists to catch, committed by the audit's author:
**absence of evidence in the corpus you happen to be holding is not evidence of absence.**
Edition 1.1 of the strategic record made this exact error about ancestry symbolism and was
corrected by opening a folder that had not been opened. It is preserved here for the same
reason: a record that hides its own corrections teaches nothing.

**Standing rule added:** before asserting that a capability does not exist, check the declared
dependencies of the repository under work. A hard dependency is not "elsewhere".

## 6. Separately raised, and NOT decided here

`krl_tutorials_data` (the rebuild's data layer) was written beside `krl-data-connectors`
rather than on top of it. Having now read the connector, the two are **not** redundant:

| | `CensusACSPublicConnector` (318 lines) | `krl_tutorials_data.sources` |
|---|---|---|
| ACS jam values (`-666666666` …) → NaN before arithmetic | absent | present |
| Margins of error at 90% (`Z=1.645`) | **no MOE concept at all** | the basis of D01/D03/D07/D16/D27 |
| HTTP 200 + `text/html` "Missing Key" rejection | absent (`raise_for_status()` only) | present |
| 50-name `get` ceiling + verified batch join | absent | present |
| Credential allowlist (least privilege) | absent | present |
| Per-fetch provenance record with payload hash | absent | present |
| Error handling | bare `except Exception` | typed `DataAccessError` hierarchy |

Every rebuilt notebook turns on margins of error and on jam values being removed before
arithmetic; the community connector has neither concept, so it could not have carried this work
unchanged.

**DECIDED by the architect, 2026-09-13:** *"do not change the data connectors you add your
layer/wrappers but dont change the connectors."*

`krl-data-connectors` is **upstream and read-only** for this repository. `krl_tutorials_data`
adapts it from above and does not modify it — no edits, no subclass overrides of its behaviour,
no monkey-patching, no writes into its tree. It is **not** refactored to inherit from
`BaseConnector`, because that would couple the tutorial contract to a class this repo does not
own and must not change.

Implemented as `krl_tutorials_data/connectors.py`:

| Concern | Where it lives |
|---|---|
| Fetching / parsing, caching, rate limiting, licensing | upstream connector, called through its public methods |
| Pinned vintage + SHA-256 of the bytes actually read | `BulkFileSource`, `verify_bulk_file` |
| Fail-closed on a missing package, missing file or failed pin | `ConnectorUnavailableError`, `BulkFilePinError` |
| `DataProvenance` record with publisher, terms URL, digest | `frame_from_bulk_file` |
| Typed errors the notebooks already handle | all three subclass `DataAccessError` |

Two properties are enforced by test rather than by convention
(`tests/test_connectors.py`):

* `test_this_package_never_writes_to_the_upstream_connector` — no adapter may patch or write
  into the upstream tree.
* `test_upstream_is_imported_lazily_not_at_module_scope` — the import is by string, inside a
  function. A module-scope import would break every Census-only notebook in an environment where
  the package is absent, which is precisely the environment this corpus was executed in.

**This is the layer that was actually missing for the bulk sources.** The connectors for Zillow
Research, Eviction Lab, HUD CHAS and HUD Fair Market Rents already existed. What a tutorial could
not previously do was state *which* download it used and prove the file had not changed
underneath it — because bulk publishers overwrite their files in place. `BulkFileSource` makes the
vintage label mandatory (there is no "latest"), and the first unpinned run reports the digest to
paste into the pin, after which every later run proves it read identical bytes.

Of note: `hud_chas.py:442` independently implements the same HTTP 200 + `text/html` masquerade
check that `krl_tutorials_data.sources._assert_json_payload` implements. Two independent
implementations of the same guard is corroboration that the trap is real.

## 7. Actions taken

1. `SOURCE_MAP.md` — Tier B preamble, sequencing item 2, and the D27 note corrected.
2. `MIGRATION.md` — the D27 gentrification note corrected.
3. D27 notebook `krl.scope_note` corrected.
4. This ADR recorded. Commit `8b16891`'s message stands as written; it is superseded by this
   record rather than rewritten, since the history is evidence.
5. `krl_tutorials_data/connectors.py` added, with 29 tests. The upstream repository was verified
   untouched: clean working tree at `7fc3211`, no file under `src/` modified.
