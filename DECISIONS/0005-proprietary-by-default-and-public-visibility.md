<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# ADR 0005 — Proprietary by Default; Public Visibility Is Not a Grant

- **Status:** Accepted, standing policy
- **Deciders:** Telosyn, Inc. (owner)
- **Date:** 2026-09-18

## 1. Title

Everything in this repository and in the repositories of the same
GitHub organisation is proprietary. Nothing is authorized under MIT, Apache,
Creative Commons or any other public licence unless that authorization is explicit,
written, specific to the material, and recorded here. Where a repository is made
publicly readable, the purpose is marketing, showcase and transparency; nothing
further is implied or granted.

## 2. Context

`DECISIONS/0001` recorded three-way licence drift and settled that the proprietary
licence is authoritative. Its remediation, carried out 2026-09-18, aligned the
`LICENSE*` files, `pyproject.toml`, SPDX banners, `CONTRIBUTING.md` and the
`the showcase sub-project` sub-project.

That pass was driven by **SPDX identifiers**, and it therefore missed every
statement that granted permissions in prose without naming one:

| Location | What it said |
|---|---|
| Internal operating brief, line 45 | *"Dual license: MIT for code, CC-BY-SA 4.0 for educational content"* — the brief **every contributor reads** before touching the repository |
| `docs/wiki/FAQ.md` | *"Can I use these for teaching a class? **Yes! That's encouraged.** The dual licensing allows: … Modifying for your curriculum … Creating derivative materials"* |
| `docs/wiki/FAQ.md` | *"Who owns the copyright? [the project's then name] retains copyright. Content is dual-licensed"* |
| `docs/wiki/Home.md:89` | *"**License**: Dual Licensed (MIT + CC-BY-SA-4.0)"* |

These are worse than a wrong SPDX banner. A banner is a machine-readable claim that
a lawyer reads; *"Yes! That's encouraged"* is what a person acts on. The FAQ told
readers in plain language that they could modify the work and build derivatives
from it. They could not.

A second gap: the repository is intended to be **publicly visible** for marketing
and transparency while remaining proprietary. Publication ordinarily reads as
permission, and the licence said nothing about the distinction.

## 3. Decision

1. **Proprietary is the default and the only posture.** No file, page, badge,
   manifest or classifier may declare an open licence.
2. **An open licence requires express written authorization** from Telosyn, Inc.,
   naming the specific material, recorded as an ADR. Absent that, any such
   declaration appearing in the repository is void — stated in `LICENSE` under
   *NO OPEN-SOURCE LICENSE WITHOUT EXPRESS AUTHORIZATION*.
3. **Public visibility grants nothing.** `LICENSE` now carries a *PUBLIC VISIBILITY
   IS NOT A LICENSE* clause: visibility does not place the work in the public
   domain, does not make it open source, and creates no licence by implication,
   estoppel, course of conduct, or absence of objection. The restrictions apply in
   full to material anyone can read.
4. **Nothing is inferred from infrastructure.** A Binder config, a Dockerfile, a
   PyPI classifier or a docs site does not imply redistribution rights. Where such
   an artifact conflicts with the licence, the licence governs. This is not
   hypothetical: `the showcase sub-project` carried an OSI trove classifier, an Apache badge
   and Binder/Docker recipes while sitting inside a repository that forbids
   redistribution.
5. **Public repositories serve three purposes only** — marketing, showcase and
   transparency about method. They are not a distribution channel and not an
   invitation to reuse.
6. **The archive is not corrected.** `notebooks/` retains its MIT + CC-BY-SA-4.0
   banners because it is audit evidence, verified byte-identical against
   `docs/audits/audit_manifest_2026-09-13.jsonl`. `LICENSE` states that those
   historical declarations were never authorized and grant nothing.

## 4. Enforcement

`tests/test_gate_license_consistency.py`:

- every SPDX banner must equal the identifier in `pyproject.toml`, which is read
  rather than hardcoded;
- **no document may contain permission language** — "dual license", "MIT for code",
  "licensed under the Apache", and similar — outside a short list of files that
  quote it as history;
- `LICENSE` must carry both new clauses;
- the operating brief must state the posture, so no future contributor inherits the old one;
- `the showcase sub-project` must declare no open licence;
- the archived corpus must **still** carry its drift, so the exclusion protecting
  evidence cannot quietly become a sweep.

Mutation-tested: reverting the operating brief, re-advertising dual licensing on a
wiki page, and deleting the visibility clause are each caught.

One phrase was deliberately left out of the permission-language list:
*"open-source software"*. The README and the docs index both say *"this is **not**
open-source software"*, and a substring match cannot tell a denial from a grant. A
check that fires on the correct sentence teaches people to suppress it.

## 5. Consequences

Contributors and agents get one answer in every place they might look. A reader of
a public repository is told, in the licence itself, what visibility does and does
not give them. The cost is that genuine open-sourcing now requires an ADR — which
is the intent: the previous arrangement let an open-licence claim enter the
repository without anyone deciding anything.
