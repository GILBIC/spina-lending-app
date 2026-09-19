"""Controlled T02/T03 tax-itemization text revisions, not PDF issuance.

The original review mirrors and DOCX sources remain unchanged. These tests
require new, explicitly draft text candidates using the approved DST-upfront /
GRT-in-repayments treatment. They do not prove authenticated source binding,
legal applicability, EIR, per-installment allocation or rendered PDF acceptance.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
ORIGINALS = ROOT / "docs/forms-documents/2026-09-12/templates"
CANDIDATES = ROOT / "docs/forms-documents/2026-09-16/templates"
CASES = {
    "T02": (
        "T02-cash-loan-agreement-r3.md",
        "T02-cash-loan-agreement-r4-tax-itemization.md",
        "3ee476370bb1512f6b28db1cd702696d617947d4",
    ),
    "T03": (
        "T03-loan-disclosure-r2.md",
        "T03-loan-disclosure-r3-tax-itemization.md",
        "2c96c6be6759ae12b8a68843a7f083d9bbef6bef",
    ),
}
DST_ROW = "Documentary Stamp Tax (DST) - upfront | PHP {DST Upfront Amount}"
GRT_ROW = (
    "Passed-on Gross Receipts Tax (GRT) - within agreed repayments"
    " | PHP {GRT Recovery in Repayments}"
)
INTEREST_ROW = (
    "Total Contractual Interest (excluding GRT recovery)"
    " | PHP {Total Contractual Interest}"
)
OTHER_SCHEDULED_ROW = (
    "Other Scheduled Charges (excluding interest and GRT recovery)"
    " | PHP {Other Scheduled Charges}"
)
TOTAL_ROW = (
    "TOTAL PAYABLE UNDER ORIGINAL SCHEDULE | PHP {Authoritative Scheduled Total}"
)
TIMING_NOTE = (
    "Passed-on GRT is included within the agreed repayments, not deducted "
    "upfront and not added on top of the agreed installment. Repeated "
    "disclosure of the same DST or GRT amount does not create another charge."
)


def _candidate(document):
    path = CANDIDATES / CASES[document][1]
    assert path.is_file(), f"Controlled tax-itemization candidate is missing: {path.name}"
    return path.read_text(encoding="utf-8")


def _original(document):
    return (ORIGINALS / CASES[document][0]).read_text(encoding="utf-8")


def _body(text):
    assert text.count("```text\n") == 1, "One complete review-text body is required"
    return text.split("```text\n", 1)[1].rsplit("\n```", 1)[0]


def _section(body, start, end):
    assert body.count(start) == 1
    assert body.count(end) == 1
    return body.split(start, 1)[1].split(end, 1)[0]


@pytest.mark.parametrize("document", CASES)
def test_original_review_mirror_bytes_are_preserved(document):
    _candidate(document)
    data = (ORIGINALS / CASES[document][0]).read_bytes()
    # Git object identity, not a security/integrity algorithm for issued documents.
    blob = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    assert hashlib.sha1(blob, usedforsecurity=False).hexdigest() == CASES[document][2]


@pytest.mark.parametrize("document", CASES)
def test_candidate_is_explicitly_text_only_and_not_production_cleared(document):
    candidate = _candidate(document)
    metadata = candidate.split("```text\n", 1)[0]
    assert "tax-itemization" in metadata.lower()
    assert "text-only" in metadata.lower()
    assert "not production-cleared" in metadata.lower()
    assert CASES[document][0] in metadata
    assert "source binding is not implemented" in metadata.lower()
    for reference in (
        "loan_version_reference", "tax_rule_snapshot_reference",
        "tax_calculation_reference",
    ):
        assert reference in metadata


@pytest.mark.parametrize("document", CASES)
def test_non_tax_prose_and_sections_are_not_silently_rewritten(document):
    candidate = _body(_candidate(document))
    original = _body(_original(document))
    # Editing revision, not an issued packet version. All existing prose stays.
    if document == "T02":
        assert "Working revision R4:" in candidate
        candidate = candidate.replace("Working revision R4:", "Working revision R3:", 1)
        start = "3. GROSS LOAN AMOUNT, DEDUCTIONS AND NET PROCEEDS"
        end = "5. COMPLETE CONTRACTUAL SCHEDULE OF PAYMENTS"
    else:
        start = "B. Deductions from Loan Proceeds"
        end = "VII. PAYMENT TERMS"
    assert candidate.split(start, 1)[0] == original.split(start, 1)[0]
    assert candidate.split(end, 1)[1] == original.split(end, 1)[1]
    for paragraph in original.split("\n\n"):
        if paragraph and " | " not in paragraph:
            assert paragraph in candidate, f"Original prose was changed: {paragraph[:100]}"


def test_agreement_separates_upfront_deductions_from_scheduled_repayments():
    body = _body(_candidate("T02"))
    upfront = _section(
        body, "3. GROSS LOAN AMOUNT, DEDUCTIONS AND NET PROCEEDS",
        "4. INTEREST, FINANCE CHARGES AND OTHER CHARGES",
    )
    scheduled = _section(
        body, "4. INTEREST, FINANCE CHARGES AND OTHER CHARGES",
        "5. COMPLETE CONTRACTUAL SCHEDULE OF PAYMENTS",
    )
    assert DST_ROW in upfront
    assert "Renewal Offset (not a tax) | PHP {Renewal Offset Amount}" in upfront
    assert (
        "Other Itemized Lawful Upfront Deductions (excluding DST and renewal offset)"
        " | {Other Itemized Upfront Deductions / None}"
    ) in upfront
    assert "Total Approved Deductions | PHP {Authoritative total deductions}" in upfront
    assert "Amount Financed | PHP {Authoritative amount financed}" in upfront
    assert "Net Loan Proceeds Authorized | PHP {Authoritative net proceeds}" in upfront
    assert "{GRT Recovery in Repayments}" not in upfront
    for row in (INTEREST_ROW, GRT_ROW, OTHER_SCHEDULED_ROW, TOTAL_ROW):
        assert scheduled.count(row) == 1
    assert "{DST Upfront Amount}" not in scheduled


def test_disclosure_itemizes_dst_and_renewal_without_an_upfront_grt_recovery():
    body = _body(_candidate("T03"))
    upfront = _section(body, "B. Deductions from Loan Proceeds", "C. Net Proceeds")
    assert DST_ROW in upfront
    assert "Renewal Offset (not a tax) | PHP {Renewal Offset Amount}" in upfront
    assert "{GRT Recovery in Repayments}" not in upfront
    assert "TOTAL DEDUCTIONS | PHP {Total Approved Deductions}" in upfront
    net = _section(body, "C. Net Proceeds", "IV. INTEREST AND FINANCE CHARGES")
    assert "NET AMOUNT TO BE RELEASED | PHP {Authorized Net Proceeds}" in net


def test_disclosure_repeats_same_tax_tokens_for_classification_not_new_charges():
    body = _body(_candidate("T03"))
    finance = _section(body, "IV. INTEREST AND FINANCE CHARGES", "V. NON-FINANCE CHARGES")
    nonfinance = _section(body, "V. NON-FINANCE CHARGES", "VI. TOTAL AMOUNT PAYABLE")
    assert GRT_ROW in finance
    assert "TOTAL FINANCE CHARGES | PHP {Total Finance Charges}" in finance
    assert "Effective Interest Rate (EIR) | {Required Calculated EIR} % per {Stated Period}" in finance
    assert (
        "Documentary Stamp Tax (DST) - same upfront amount, not an additional charge"
        " | PHP {DST Upfront Amount}"
    ) in nonfinance
    assert body.count("{DST Upfront Amount}") == 2
    assert body.count("{GRT Recovery in Repayments}") == 2


def test_disclosure_scheduled_total_does_not_add_upfront_or_classification_totals_again():
    body = _body(_candidate("T03"))
    scheduled = _section(body, "VI. TOTAL AMOUNT PAYABLE", "VII. PAYMENT TERMS")
    rows = [line for line in scheduled.splitlines() if " | " in line]
    assert rows == [
        "Principal / Gross Loan Amount | PHP {Approved Gross Principal}",
        INTEREST_ROW, GRT_ROW, OTHER_SCHEDULED_ROW, TOTAL_ROW,
    ]
    # Amount Financed and EIR remain separately supplied disclosure values, not
    # aliases for net proceeds or numbers derived by this template layer.
    assert "Amount Financed | PHP {Authoritative Amount Financed}" in body


@pytest.mark.parametrize("document", CASES)
def test_shared_timing_note_forbids_an_extra_installment_charge(document):
    body = _body(_candidate(document))
    assert body.count(TIMING_NOTE) == 1
