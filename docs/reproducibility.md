<!--
© 2026 Telosyn, Inc. All rights reserved.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# Reproducibility

Two different questions hide inside "can I reproduce this?", and they have
different answers. Both are stated here so that neither is overclaimed.

## 1. Can I see the results without running anything?

**Yes, completely.** Every notebook is committed with its output. Each figure,
table and stated number is in the file, and a release gate checks that every
figure in a notebook's prose appears in that notebook's stored output. Open any
notebook on GitHub and the evidence is there; no keys, no environment.

## 2. Can I re-run it and get the same numbers?

**Mostly, and the exceptions are stated rather than hidden.**

### What is held fixed

- **The code is deterministic.** Where randomness is used it is seeded; there is
  no unseeded `np.random` anywhere in the corpus. The one notebook that simulates
  (D30, `data_mode: illustrative`) seeds its generator and exists to score an
  analysis against a truth known by construction.
- **Every retrieval is pinned.** Each request a notebook makes is recorded in a
  provenance record with a SHA-256 of the payload, taken on a stated basis
  (`data/README.md` explains why the basis matters). A re-run that does not
  reproduce the digest raises. It does not substitute, estimate or fall back.
- **Replay was measured, not assumed.** `scripts/verify_provenance_reproducibility.py`
  replays every record. At last measurement: **35 `SAME`, 1 pinned locally,
  4 `NOT_REPLAYABLE`, 0 `DIFF`.**

### What a re-run cannot promise

| Case | What happens | Why |
|---|---|---|
| A publisher that serves no prior vintage | you get today's values; the digest pin raises | BLS, QCEW, CBP, CHAS, BDS, BEA regional, FBI CDE, TRI, the IRS BMF and Socrata endpoints publish only the current release |
| The two Zillow files (D27) | the notebook stops until you supply the file | not committed: Zillow overwrites in place and redistribution is not ours to grant; `data/zillow/2026-08/SOURCES.md` says where to get it, and the digest will not match a later download |
| 4 of 40 retrievals | not replayable | endpoint or parameter semantics changed after retrieval; listed by the verifier |
| Credentialed sources | you need your own keys | six, all free; see below |

None of this is a flaw in the notebooks. It is the honest situation with live
public data, and the design choice throughout is to **stop loudly rather than
continue quietly**.

## 3. Setting up

```bash
pip install -e '.[notebooks,test]'
pytest tests/                       # 1,500+ tests; no network, no keys
```

The notebooks fetch live data and need keys for the credentialed sources —
Census, FRED, BEA, BLS, HUD, and DATA.gov for the FBI CDE. All six are free to
register for. Put them in a file of your own:

```bash
cp .env.example <operator-path>/tutorials.env       # fill in your keys
export KRL_SECRETS_PATH=<operator-path>/tutorials.env
```

The names the corpus will read are a closed set of six. A secrets file that also
holds database URLs or admin tokens is never opened for them. Keys are never
logged, echoed or written into a notebook's output; one gate scans committed
output for key material and another checks that the client redacts credentials
from any error it surfaces.

## 4. Verifying

```bash
make test               # the suite
make gates              # the nine release gates only
make verify-provenance  # replay every provenance record against its digest
make readmes            # regenerate the derived READMEs and check nothing drifted
```

## 5. What the gates check

Nine release gates run against every notebook. A notebook is releasable only
if its executable state, data provenance, computational results, statistical
interpretation and narrative claims are mutually consistent:

| Gate | Refuses |
|---|---|
| executable | a notebook whose cells did not run in order, or with errors |
| claims | a number in the prose that does not appear in stored output |
| evidence | a conclusion not traceable to a computation |
| pedagogy | a notebook without stated objectives and a summary |
| no-synthetic | any synthetic fallback, except the one artifact declared illustrative |
| security | key material in committed output |
| statistical | an interpretation the computed statistic does not support |
| vintage | a retrieval without a declared vintage or a justified absence |
| license-consistency | any licence declaration other than the one `LICENSE` states |

Each gate was mutation-tested: the defect it exists to catch was deliberately
introduced and the gate confirmed to fail.
