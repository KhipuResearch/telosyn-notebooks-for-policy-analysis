<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# ADR 0010 — `pypdf` for reading state tables published only as PDF

- **Status:** Accepted
- **Deciders:** Telosyn, Inc. (owner)
- **Date:** 2026-10-27
- **Amends:** ADR 0009 section 3.6 (dependency policy)

## 1. Context

Card I01 (benefit take-up and administrative burden) needs the USDA Food and Nutrition Service's
state SNAP participation rates and its State Options Report. Both are published as typeset PDF
tables; neither has an API, a spreadsheet or a CSV. ADR 0009 section 3.6 allows the `notebooks`
extra to gain only the packages that section lists. Reading the tables needs a PDF text reader.

## 2. Decision

Add `pypdf>=6.0.0` to the `notebooks` extra. A notebook imports it to extract each page's text; a
pure, I/O-free function in the package (`krl_tutorials_data.pdf_tables`) parses the extracted lines
into rows and is covered by known-answer tests. The package itself does not import `pypdf`, so the
runtime dependency list is unchanged.

**Existence and age, verified on PyPI on 2026-10-27.** Project `pypdf`, BSD-3-Clause, requires
Python 3.9 or later, no required dependency on Python 3.11 or later. The lower bound is release
6.0.0 (uploaded 2025-08-11); the newest release at the time of writing (6.21.3) was uploaded the same
day and is not used as the bound.

## 3. Cost and benefit

*Benefit.* The state tables become data a cell can read and a test can check, with the page and line
of any row that fails to parse reported, instead of numbers typed in by hand from a PDF, which cannot
be audited and drifts silently. *Cost.* One pure-Python package in the extra a reader installs to
open the corpus (install size well under a megabyte of wheel; no compiler, no system library); a
parse of typeset text is a heuristic, so the notebook checks coverage, range and a double read and
stops when they fail (I01 plan, sections 3 and 7).

**Alternatives rejected.** *`pdfplumber`*: better at table geometry, but pulls in `pdfminer.six`,
`Pillow` and `pypdfium2`, a much larger surface for a text-line parse. *System `pdftotext`
(poppler)*: not on the CI runners, differs by operating system, and cannot be declared in
`pyproject.toml`. *Hand transcription*: unauditable. *Skipping the card*: loses the one
implementation-side take-up measure in the track.

## 4. Gates affected

`tests/test_src_imports_declared.py` gains a test that the `notebooks` extra declares `pypdf` with a
lower bound and that a notebook imports it (nothing declared that nothing imports), and that the
package does not import it.

## 5. Failure modes

A PDF whose text layer is an image yields no rows; the notebook stops on its coverage rule. A layout
change between editions yields a wrong column; the range check and the double read catch some cases
and not all, so the notebook prints an excerpt of the parsed page beside each table for a reader to
check. `pypdf` releases frequently; the lower bound is not an upper bound, and a later release that
changes text extraction would change the parse and be caught by the same checks.
