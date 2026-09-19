"""Shared amount-token projection for the controlled T02/T03 drafts.

Synthetic precomputed amounts only: no tax-rate policy, authenticated source
binding, document issuance, signature, or cash-release acceptance is asserted.
"""
from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal, Inexact, localcontext
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import pytest

from gilbic_backend.loan_document_tax_breakdown import project_loan_document_tax_breakdown


ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "docs/forms-documents/2026-09-16/assets"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
EXPECTED = {
    "{Approved Principal/Gross Loan Amount}": "5,000.00",
    "{Approved Gross Principal}": "5,000.00",
    "{DST Upfront Amount}": "12.34",
    "{Renewal Offset Amount}": "250.00",
    "{Authoritative total deductions}": "300.23",
    "{Total Approved Deductions}": "300.23",
    "{Authoritative net proceeds}": "4,699.77",
    "{Authorized Net Proceeds}": "4,699.77",
    "{Total Contractual Interest}": "1,000.00",
    "{GRT Recovery in Repayments}": "56.78",
    "{Other Scheduled Charges}": "10.11",
    "{Authoritative Scheduled Total}": "6,066.89",
}


def _project(**changes):
    values = {
        "loan_version_reference": "SYN-LOAN-V3",
        "tax_loan_version_reference": "SYN-LOAN-V3",
        "tax_rule_snapshot_reference": "SYN-RULE-V2",
        "tax_calculation_reference": "SYN-CALC-V4",
        "principal": Decimal("5000.00"),
        "contractual_interest": Decimal("1000.00"),
        "dst_upfront": Decimal("12.34"),
        "grt_in_repayments": Decimal("56.78"),
        "renewal_offset": Decimal("250.00"),
        "other_upfront_deductions": Decimal("37.89"),
        "other_scheduled_charges": Decimal("10.11"),
        "expected_total_upfront_deductions": Decimal("300.23"),
        "expected_net_proceeds": Decimal("4699.77"),
        "expected_total_scheduled": Decimal("6066.89"),
    }
    values.update(changes)
    return project_loan_document_tax_breakdown(**values)


def _amounts(breakdown):
    method = getattr(breakdown, "template_amounts", None)
    assert callable(method), "Shared T02/T03 amount-token mapping is not implemented"
    return method()


def _template_tokens(filename):
    with ZipFile(ASSETS / filename) as package:
        body = ET.fromstring(package.read("word/document.xml"))
    text = "\n".join(
        "".join(node.text or "" for node in paragraph.iter(W + "t"))
        for paragraph in body.iter(W + "p")
    )
    return re.findall(r"\{[^{}]+\}", text)


def test_exact_shared_map_uses_reconciled_totals_and_preserves_tax_timing():
    assert dict(_amounts(_project())) == EXPECTED


@pytest.mark.parametrize("left,right", [
    ("{Approved Principal/Gross Loan Amount}", "{Approved Gross Principal}"),
    ("{Authoritative total deductions}", "{Total Approved Deductions}"),
    ("{Authoritative net proceeds}", "{Authorized Net Proceeds}"),
])
def test_preserved_document_specific_aliases_cannot_diverge(left, right):
    values = _amounts(_project())
    assert values[left] == values[right] == EXPECTED[left]


@pytest.mark.parametrize("principal", [Decimal("5000"), Decimal("5E3"), Decimal("5000.000")])
def test_money_uses_grouped_two_decimal_display_without_changing_exact_value(principal):
    breakdown = _project(principal=principal)
    assert _amounts(breakdown)["{Approved Gross Principal}"] == "5,000.00"
    assert breakdown.principal.as_tuple() == principal.as_tuple()


def test_projection_does_not_recalculate_under_a_different_decimal_context():
    breakdown = _project()
    before = asdict(breakdown)
    with localcontext() as context:
        context.prec = 2
        context.traps[Inexact] = True
        context.clear_flags()
        assert dict(_amounts(breakdown)) == EXPECTED
        assert not any(context.flags.values())
        assert context.prec == 2 and context.traps[Inexact]
    assert asdict(breakdown) == before


def test_mapping_is_read_only_and_repeated_preparation_preserves_source_references():
    breakdown = _project()
    before = asdict(breakdown)
    values = _amounts(breakdown)
    with pytest.raises(TypeError):
        values["{GRT Recovery in Repayments}"] = "0.00"
    assert dict(_amounts(breakdown)) == EXPECTED
    assert asdict(breakdown) == before
    assert breakdown.tax_calculation_reference == "SYN-CALC-V4"


@pytest.mark.parametrize("principal,interest,total", [
    ("5000.00", "1000.00", "6000.00"),
    ("3000.00", "1260.00", "4260.00"),
])
def test_explicit_zero_charge_examples_keep_existing_principal_and_interest(principal, interest, total):
    # These no-recovery fixtures are not tax exemptions or tax-inclusive offers.
    breakdown = _project(
        principal=Decimal(principal), contractual_interest=Decimal(interest),
        dst_upfront=Decimal("0.00"), grt_in_repayments=Decimal("0.00"),
        renewal_offset=Decimal("0.00"), other_upfront_deductions=Decimal("0.00"),
        other_scheduled_charges=Decimal("0.00"),
        expected_total_upfront_deductions=Decimal("0.00"),
        expected_net_proceeds=Decimal(principal), expected_total_scheduled=Decimal(total),
    )
    values = _amounts(breakdown)
    assert values["{Approved Gross Principal}"] == format(Decimal(principal), ",.2f")
    assert values["{Total Contractual Interest}"] == format(Decimal(interest), ",.2f")
    assert values["{Authoritative Scheduled Total}"] == format(Decimal(total), ",.2f")
    for token in ("{DST Upfront Amount}", "{GRT Recovery in Repayments}", "{Renewal Offset Amount}"):
        assert values[token] == "0.00"


@pytest.mark.parametrize("filename,principal_token,net_token", [
    ("T02_Cash_Loan_Agreement_R4_DST_GRT.docx", "{Approved Principal/Gross Loan Amount}", "{Authoritative net proceeds}"),
    ("T03_Loan_Disclosure_R3_DST_GRT.docx", "{Approved Gross Principal}", "{Authorized Net Proceeds}"),
])
def test_mapping_targets_the_existing_word_tokens_not_new_template_spellings(filename, principal_token, net_token):
    values = _amounts(_project())
    tokens = _template_tokens(filename)
    required = {principal_token, net_token, "{DST Upfront Amount}", "{GRT Recovery in Repayments}", "{Authoritative Scheduled Total}"}
    assert required <= set(tokens) & set(values)
    assert values[principal_token] == "5,000.00"
    assert values[net_token] == "4,699.77"


def test_repeated_disclosure_tax_tokens_refer_to_one_amount_without_multiplication():
    values = _amounts(_project())
    tokens = _template_tokens("T03_Loan_Disclosure_R3_DST_GRT.docx")
    for token, expected in (("{DST Upfront Amount}", "12.34"), ("{GRT Recovery in Repayments}", "56.78")):
        assert tokens.count(token) == 2
        assert values[token] == expected
    assert values["{Authoritative Scheduled Total}"] == "6,066.89"
    assert values["{Total Approved Deductions}"] == "300.23"


def test_only_explicit_amount_tokens_are_mapped_no_guessed_financed_eir_or_execution_fields():
    values = _amounts(_project())
    tokens = set(_template_tokens("T02_Cash_Loan_Agreement_R4_DST_GRT.docx"))
    tokens.update(_template_tokens("T03_Loan_Disclosure_R3_DST_GRT.docx"))
    assert set(values) == set(EXPECTED)
    assert set(values) <= tokens
    assert not any(token in values for token in (
        "{Amount}", "{Date}", "{Authoritative amount financed}",
        "{Authoritative Amount Financed}", "{Total Finance Charges}",
        "{Total Non-Finance Charges}", "{Required Calculated EIR}",
        "{Borrower Full Name}", "{Agreed Installment Amount}",
        "{Other Itemized Upfront Deductions / None}",
    ))
