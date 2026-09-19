"""Read-only document amounts for the approved DST/GRT collection timing.

Synthetic amounts are supplied, not tax rates or a new gross-up calculation.
This boundary checks arithmetic and matching version references only. It must
not certify source ownership, tax legality, approval, signing, payment or BIR
remittance. Authorized source binding and T02/T03 rendering are later gates.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
from decimal import Decimal
from importlib import import_module

import pytest


D = Decimal


def _module():
    # Import inside test bodies so an absent implementation is a focused test
    # failure, not a collection failure that hides unrelated application tests.
    return import_module("gilbic_backend.loan_document_tax_breakdown")


def _source(**overrides):
    # Deliberately synthetic precomputed amounts; do not derive a legal rate.
    values = {
        "loan_version_reference": "SYN-LOAN-V1",
        "tax_loan_version_reference": "SYN-LOAN-V1",
        "tax_rule_snapshot_reference": "SYN-TAX-RULE-SNAPSHOT-V1",
        "tax_calculation_reference": "SYN-APPROVED-CALCULATION-V1",
        "principal": D("5000.00"),
        "contractual_interest": D("1000.00"),
        "dst_upfront": D("12.34"),
        "grt_in_repayments": D("40.00"),
        "renewal_offset": D("0.00"),
        "other_upfront_deductions": D("0.00"),
        "other_scheduled_charges": D("0.00"),
        "expected_total_upfront_deductions": D("12.34"),
        "expected_net_proceeds": D("4987.66"),
        "expected_total_scheduled": D("6040.00"),
    }
    values.update(overrides)
    return values


def test_names_both_taxes_and_keeps_their_collection_timing_separate():
    result = _module().project_loan_document_tax_breakdown(**_source())
    assert [
        (line.code, line.label, line.amount, line.collection_timing)
        for line in result.tax_lines
    ] == [
        ("dst", "Documentary Stamp Tax (DST)", D("12.34"), "upfront"),
        (
            "grt_recovery",
            "Passed-on Gross Receipts Tax (GRT)",
            D("40.00"),
            "repayments",
        ),
    ]
    assert result.total_upfront_deductions == D("12.34")
    assert result.net_proceeds == D("4987.66")
    assert result.total_scheduled_payable == D("6040.00")
    assert result.principal == D("5000.00")
    assert result.contractual_interest == D("1000.00")


def test_preserves_references_without_claiming_to_verify_their_provenance():
    source = _source()
    result = _module().project_loan_document_tax_breakdown(**source)
    for field in (
        "loan_version_reference",
        "tax_rule_snapshot_reference",
        "tax_calculation_reference",
    ):
        assert getattr(result, field) == source[field]


def test_renewal_offset_and_non_tax_charges_reconcile_without_becoming_taxes():
    result = _module().project_loan_document_tax_breakdown(
        **_source(
            renewal_offset=D("1000.00"),
            other_upfront_deductions=D("25.00"),
            other_scheduled_charges=D("10.00"),
            expected_total_upfront_deductions=D("1037.34"),
            expected_net_proceeds=D("3962.66"),
            expected_total_scheduled=D("6050.00"),
        )
    )
    assert result.total_upfront_deductions == D("1037.34")
    assert result.net_proceeds == D("3962.66")
    assert result.total_scheduled_payable == D("6050.00")
    assert [(line.code, line.amount) for line in result.tax_lines] == [
        ("dst", D("12.34")), ("grt_recovery", D("40.00"))
    ]


def test_explicit_zero_recovery_preserves_existing_120_by_50_example():
    result = _module().project_loan_document_tax_breakdown(
        **_source(grt_in_repayments=D("0.00"), expected_total_scheduled=D("6000.00"))
    )
    assert result.principal == D("5000.00")
    assert result.contractual_interest == D("1000.00")
    assert result.total_scheduled_payable == D("50.00") * 120
    assert result.tax_lines[1].amount == D("0.00")


def test_explicit_zero_tax_amounts_are_not_guessed_from_missing_information():
    result = _module().project_loan_document_tax_breakdown(
        **_source(
            dst_upfront=D("0.00"), grt_in_repayments=D("0.00"),
            expected_total_upfront_deductions=D("0.00"),
            expected_net_proceeds=D("5000.00"),
            expected_total_scheduled=D("6000.00"),
        )
    )
    assert len(result.tax_lines) == 2
    assert all(line.amount == D("0.00") for line in result.tax_lines)
    assert result.net_proceeds == D("5000.00")


@pytest.mark.parametrize(
    "overrides",
    [
        {"expected_total_upfront_deductions": D("52.34"),
         "expected_net_proceeds": D("4947.66")},  # GRT also taken upfront.
        {"expected_total_scheduled": D("6052.34")},  # DST charged again in schedule.
        {"expected_total_scheduled": D("6080.00")},  # GRT counted twice.
        {"expected_total_scheduled": D("6000.00")},  # Extra recovery cannot fit 120x50.
        {"expected_total_upfront_deductions": D("12.35")},
        {"expected_net_proceeds": D("4987.65")},
        {"expected_total_scheduled": D("6040.01")},
    ],
)
def test_rejects_mismatches_instead_of_repricing_or_silently_double_counting(overrides):
    module = _module()
    source = _source(**overrides)
    before = deepcopy(source)
    with pytest.raises(module.LoanDocumentTaxBreakdownError):
        module.project_loan_document_tax_breakdown(**source)
    assert source == before


@pytest.mark.parametrize(
    "field",
    [
        "loan_version_reference", "tax_loan_version_reference",
        "tax_rule_snapshot_reference", "tax_calculation_reference",
    ],
)
@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_version_or_calculation_reference_fails_closed(field, value):
    module = _module()
    with pytest.raises(module.LoanDocumentTaxBreakdownError):
        module.project_loan_document_tax_breakdown(**_source(**{field: value}))


def test_tax_values_from_another_loan_version_are_rejected():
    module = _module()
    with pytest.raises(module.LoanDocumentTaxBreakdownError):
        module.project_loan_document_tax_breakdown(
            **_source(tax_loan_version_reference="SYN-LOAN-V2")
        )


@pytest.mark.parametrize(
    "field",
    [
        "principal", "contractual_interest", "dst_upfront", "grt_in_repayments",
        "renewal_offset", "other_upfront_deductions", "other_scheduled_charges",
        "expected_total_upfront_deductions", "expected_net_proceeds",
        "expected_total_scheduled",
    ],
)
def test_negative_amounts_are_not_clamped_to_zero(field):
    module = _module()
    with pytest.raises(module.LoanDocumentTaxBreakdownError):
        module.project_loan_document_tax_breakdown(**_source(**{field: D("-0.01")}))


@pytest.mark.parametrize("value", [None, 40, 40.0, "40.00", True,
                                  D("NaN"), D("Infinity"), D("0.001")])
def test_tax_amount_requires_finite_exact_cent_decimal_without_rounding(value):
    module = _module()
    with pytest.raises(module.LoanDocumentTaxBreakdownError):
        module.project_loan_document_tax_breakdown(**_source(grt_in_repayments=value))


def test_zero_principal_is_rejected_even_when_totals_reconcile():
    module = _module()
    with pytest.raises(module.LoanDocumentTaxBreakdownError):
        module.project_loan_document_tax_breakdown(
            **_source(principal=D("0.00"), contractual_interest=D("0.00"),
                      dst_upfront=D("0.00"), grt_in_repayments=D("0.00"),
                      expected_total_upfront_deductions=D("0.00"),
                      expected_net_proceeds=D("0.00"), expected_total_scheduled=D("0.00"))
        )


def test_deductions_exceeding_principal_are_rejected_not_silently_clamped():
    module = _module()
    with pytest.raises(module.LoanDocumentTaxBreakdownError):
        module.project_loan_document_tax_breakdown(
            **_source(renewal_offset=D("5000.00"),
                      expected_total_upfront_deductions=D("5012.34"),
                      expected_net_proceeds=D("0.00"))
        )


def test_repeated_projection_for_agreement_and_disclosure_has_no_extra_charge():
    module = _module()
    source = _source()
    before = deepcopy(source)
    agreement = module.project_loan_document_tax_breakdown(**source)
    disclosure = module.project_loan_document_tax_breakdown(**source)
    assert agreement == disclosure
    assert source == before
    assert isinstance(agreement.tax_lines, tuple)
    with pytest.raises(FrozenInstanceError):
        agreement.net_proceeds = D("0.00")
    with pytest.raises(FrozenInstanceError):
        agreement.tax_lines[0].amount = D("0.00")
