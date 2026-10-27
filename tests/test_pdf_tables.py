"""Known-answer tests for ``krl_tutorials_data.pdf_tables`` and the PDF round trip.

Hand-written text stands in for what a PDF reader extracts. The round-trip test builds a real PDF with
matplotlib, reads it back with ``pypdf`` (DECISIONS/0010) and parses the result, so the declared
dependency is exercised and not only listed.

© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
"""
from __future__ import annotations

import io
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pytest  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from pypdf import PdfReader  # noqa: E402

from krl_tutorials_data import pdf_tables  # noqa: E402

NAMES = ["Alabama", "Virginia", "West Virginia", "New York", "District of Columbia"]


def test_a_row_is_a_name_and_its_numbers() -> None:
    t = pdf_tables.parse_jurisdiction_rows(["Alabama 62 (±5.1)", "Virginia 71.5%"], NAMES)
    assert [(r.name, r.values) for r in t.rows] == [("Alabama", (62.0, 5.1)), ("Virginia", (71.5,))]
    assert t.rejected == []


def test_the_longest_name_wins() -> None:
    t = pdf_tables.parse_jurisdiction_rows(["West Virginia 80", "Virginia 70", "District of Columbia 100.0"], NAMES)
    assert [r.name for r in t.rows] == ["West Virginia", "Virginia", "District of Columbia"]


def test_punctuation_footnotes_and_missing_markers() -> None:
    t = pdf_tables.parse_jurisdiction_rows(
        ["New York 1,234.5* $9 †", "Alabama n/a 40", "Virginia -- 3"], NAMES)
    assert t.rows[0].values == (1234.5, 9.0)
    assert math.isnan(t.rows[1].values[0]) and t.rows[1].values[1] == 40.0
    assert math.isnan(t.rows[2].values[0]) and t.rows[2].values[1] == 3.0


def test_headings_and_prose_are_not_rows_but_a_broken_row_is_reported() -> None:
    lines = ["Table 3. State rates", "Alabama's rate rose", "Alabama 62 abc", "Virginia"]
    t = pdf_tables.parse_jurisdiction_rows(lines, NAMES)
    assert t.rows == []
    assert [(r.line_no, r.reason) for r in t.rejected] == [(3, "unparseable value 'abc'"), (4, "no values after the name")]


def test_a_name_inside_another_word_is_not_a_row() -> None:
    assert pdf_tables.parse_jurisdiction_rows(["Alabamans 5", "Virginian 6"], NAMES).rows == []


def test_line_numbers_are_one_based_and_names_repeat_without_merging() -> None:
    t = pdf_tables.parse_jurisdiction_rows(["x", "Alabama 1", "Alabama 2"], NAMES)
    assert [(r.line_no, r.values) for r in t.rows] == [(2, (1.0,)), (3, (2.0,))]


def test_aliases_map_to_the_canonical_name() -> None:
    t = pdf_tables.parse_jurisdiction_rows(["Washington, D.C. 5"], NAMES, aliases={"Washington, D.C.": "District of Columbia"})
    assert t.rows[0].name == "District of Columbia"


def test_find_pages_by_heading_ignores_case_and_all_whitespace() -> None:
    pages = ["intro", "TABLE  3.\nState   rates", "more", "T able 3. State rates"]
    assert pdf_tables.find_pages(pages, "table 3. state rates") == [1, 3]
    assert pdf_tables.find_pages(pages, "absent") == []


def test_check_coverage_names_what_is_missing_and_what_repeats() -> None:
    rows = pdf_tables.parse_jurisdiction_rows(["Alabama 1", "Virginia 2", "Virginia 3"], NAMES).rows
    cov = pdf_tables.check_coverage(rows, NAMES)
    assert cov.missing == ["West Virginia", "New York", "District of Columbia"]
    assert cov.repeated == ["Virginia"]
    assert not cov.complete


def test_round_trip_through_a_real_pdf() -> None:
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        fig = plt.figure(figsize=(8.5, 11))
        fig.text(0.1, 0.9, "Table 3. State rates")
        for i, line in enumerate(["Alabama 62.5 (4.1)", "West Virginia 80.0 (3.3)", "New York 71.2 (2.0)"]):
            fig.text(0.1, 0.85 - 0.04 * i, line)
        pdf.savefig(fig)
        plt.close(fig)
    pages = [p.extract_text() for p in PdfReader(io.BytesIO(buf.getvalue())).pages]
    assert pdf_tables.find_pages(pages, "Table 3. State rates") == [0]
    rows = pdf_tables.parse_jurisdiction_rows(pages[0].splitlines(), NAMES).rows
    assert [(r.name, r.values) for r in rows] == [
        ("Alabama", (62.5, 4.1)), ("West Virginia", (80.0, 3.3)), ("New York", (71.2, 2.0))]


def test_the_package_does_not_import_pypdf() -> None:
    import inspect
    assert "pypdf" not in inspect.getsource(pdf_tables)


# --- amendment 1 (I01): split names, split numbers, profile pages ---------------------------------
def test_a_lone_letter_line_is_joined_to_the_name_it_starts() -> None:
    lines = ["Kentucky 74 75 75", "L", "ouisiana 82 86 83", "Maine 85", "O", "regon 100", "x", "y"]
    names = [*NAMES, "Louisiana", "Oregon", "Kentucky", "Maine"]
    fixed, joins = pdf_tables.repair_split_names(lines, names)
    assert fixed == ["Kentucky 74 75 75", "Louisiana 82 86 83", "Maine 85", "Oregon 100", "x", "y"]
    assert joins == [(2, "L", "ouisiana 82 86 83"), (5, "O", "regon 100")]


def test_a_lone_letter_that_does_not_make_a_name_is_left_alone() -> None:
    lines = ["Z", "ebra 5", "A", "labama 4"]
    fixed, joins = pdf_tables.repair_split_names(lines, NAMES)
    assert fixed == ["Z", "ebra 5", "Alabama 4"] and len(joins) == 1


def test_a_row_with_one_extra_value_is_merged_only_when_exactly_one_merge_fits() -> None:
    row = pdf_tables.parse_jurisdiction_rows(["Alabama 80 83 85 71 7 6 78"], NAMES).rows[0]
    assert pdf_tables.reconcile_row(row, expected=6, max_value=100.0) == (80.0, 83.0, 85.0, 71.0, 76.0, 78.0)
    ambiguous = pdf_tables.parse_jurisdiction_rows(["Alabama 80 83 85 7 6 5 4"], NAMES).rows[0]
    assert pdf_tables.reconcile_row(ambiguous, expected=6, max_value=100.0) is None
    toofar = pdf_tables.parse_jurisdiction_rows(["Alabama 80 83 8 5 71 78 70"], NAMES).rows[0]
    assert pdf_tables.reconcile_row(toofar, expected=6, max_value=100.0) is None  # a split inside the first three


def test_reconcile_passes_a_row_of_the_right_length_and_refuses_other_lengths() -> None:
    ok = pdf_tables.parse_jurisdiction_rows(["Alabama 1 2 3"], NAMES).rows[0]
    assert pdf_tables.reconcile_row(ok, expected=3, max_value=100.0) == (1.0, 2.0, 3.0)
    assert pdf_tables.reconcile_row(ok, expected=5, max_value=100.0) is None
    short = pdf_tables.parse_jurisdiction_rows(["Alabama 1"], NAMES).rows[0]
    assert pdf_tables.reconcile_row(short, expected=2, max_value=100.0) is None


PAGE_14 = """
Alabama—Food Assistance Program
Program Administration State-administered
Simplified Reporting—Certification Length 4 & 12 months
Online Application Apply & recertify
Online Case Management View case information
"""
PAGE_12 = """
State Options Report • 26
SNAP State Agency Profiles
Virginia
SNAP Name Food Assistance Program
Simplified Reporting - Certification Length 12 & 24 months only
Online Application No online application
"""
PAGE_PROSE = """
Online Application is described in this section. Alabama is one of many states.
Online Application Apply
"""


def test_profile_pages_are_read_by_label_in_both_layouts() -> None:
    labels = {"online": r"Online\s+Application", "length": r"Certification\s+Length"}
    t = pdf_tables.parse_profiles([PAGE_14, PAGE_12, PAGE_PROSE, "nothing"], NAMES, labels)
    assert [(p.name, p.page, p.fields) for p in t] == [
        ("Alabama", 0, {"online": "Apply & recertify", "length": "4 & 12 months"}),
        ("Virginia", 1, {"online": "No online application", "length": "12 & 24 months only"}),
    ]


def test_a_page_without_the_label_is_not_a_profile_and_a_missing_second_label_is_none() -> None:
    labels = {"online": r"Online\s+Application", "length": r"Certification\s+Length"}
    page = "Alabama—Program\nOnline Application Apply only\n"
    (p,) = pdf_tables.parse_profiles([page, "Alabama—Program\nnothing\n"], NAMES, labels)
    assert p.fields == {"online": "Apply only", "length": None}


@pytest.mark.parametrize(("value", "offered"), [
    ("Apply & recertify", 1), ("Apply only", 1), ("Apply", 1), ("No online application", 0), ("Recertify", 0)])
def test_online_application_coding(value: str, offered: int) -> None:
    assert pdf_tables.online_offered(value) == offered


@pytest.mark.parametrize(("value", "months"), [
    ("12 & 24 months only", 24.0), ("4, 6, & 12 months", 12.0), ("4,5,6, & 24 Months", 24.0),
    ("12 &, 24 months", 24.0), ("6 months only", 6.0), ("Change reporting only", None), (None, None)])
def test_longest_certification_period(value: str | None, months: float | None) -> None:
    assert pdf_tables.longest_months(value) == months
