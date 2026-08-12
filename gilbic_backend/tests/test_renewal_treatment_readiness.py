from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import UUID

from gilbic_backend.renewal_treatment_readiness import (
    RenewalTreatmentEvidence,
    RenewalTreatmentInstallment,
    build_renewal_treatment_readiness,
)


EXECUTION_ID = UUID("11111111-1111-4111-8111-111111111111")
OLD_LOAN_ID = UUID("22222222-2222-4222-8222-222222222222")
NEW_LOAN_ID = UUID("33333333-3333-4333-8333-333333333333")
CLIENT_ID = UUID("44444444-4444-4444-8444-444444444444")
SCHEDULE_ID = UUID("55555555-5555-4555-8555-555555555555")
REGISTRATION_ID = UUID("66666666-6666-4666-8666-666666666666")
RENEWAL_DATE = date(2026, 8, 31)


def _evidence() -> RenewalTreatmentEvidence:
    return RenewalTreatmentEvidence(
        renewal_execution_event_id=EXECUTION_ID,
        old_loan_id=OLD_LOAN_ID,
        new_loan_id=NEW_LOAN_ID,
        client_id=CLIENT_ID,
        business_date=RENEWAL_DATE,
        execution_active=True,
        release_event_kind="renewal_release",
        release_business_date=RENEWAL_DATE,
        release_active=True,
        cash_disbursed_amount=Decimal("1000.00"),
        settlement_amount=Decimal("1000.00"),
        other_deduction_amount=Decimal("0.00"),
        new_loan_calculation_mode="fixed_daily",
        accounting_carrying_amount_ready=True,
        old_gross_carrying_amount=Decimal("2000.00"),
        original_daily_eir=Decimal("0.001"),
        schedule_id=SCHEDULE_ID,
        schedule_version=1,
        schedule_status="active",
        schedule_effective_from=RENEWAL_DATE,
        payment_frequency="daily",
        contract_reference="SIGNED-RENEWAL-001",
        contract_signed_date=RENEWAL_DATE,
        registration_id=REGISTRATION_ID,
        evidence_basis="signed_renewal_contract",
        evidence_reference="SIGNED-RENEWAL-001",
        installments=(
            RenewalTreatmentInstallment(
                installment_number=1,
                due_date=date(2026, 9, 30),
                contractual_amount=Decimal("600.00"),
            ),
            RenewalTreatmentInstallment(
                installment_number=2,
                due_date=date(2026, 10, 30),
                contractual_amount=Decimal("600.00"),
            ),
            RenewalTreatmentInstallment(
                installment_number=3,
                due_date=date(2026, 11, 29),
                contractual_amount=Decimal("600.00"),
            ),
            RenewalTreatmentInstallment(
                installment_number=4,
                due_date=date(2026, 12, 29),
                contractual_amount=Decimal("600.00"),
            ),
        ),
    )


def test_ready_evidence_computes_original_eir_pv_without_classifying() -> None:
    result = build_renewal_treatment_readiness(_evidence())

    assert result.disposition == "renewal_accounting_treatment_review_ready"
    assert result.blocker_code is None
    assert result.contractual_cash_total == Decimal("2400.00")
    assert result.present_value_at_original_eir == Decimal("2227.92")
    assert result.present_value_change_amount == Decimal("227.92")
    assert result.present_value_change_percent == Decimal("11.3960")
    assert result.treatment_decision_required is True
    assert result.automatic_classification_enabled is False
    assert result.quantitative_threshold_decisive is False
    assert result.journal_lines_enabled is False
    assert result.automatic_source_posting is False
    assert "No quantitative threshold automatically decides" in result.message


def test_authoritative_old_carrying_amount_is_required() -> None:
    evidence = replace(
        _evidence(),
        accounting_carrying_amount_ready=False,
        old_gross_carrying_amount=None,
    )
    result = build_renewal_treatment_readiness(evidence)
    assert result.blocker_code == "authoritative_old_carrying_amount_required"
    assert result.present_value_at_original_eir is None
    assert result.automatic_classification_enabled is False


def test_signed_renewal_contract_evidence_is_required() -> None:
    evidence = replace(_evidence(), evidence_basis="signed_contract")
    result = build_renewal_treatment_readiness(evidence)
    assert result.blocker_code == "signed_renewal_contract_evidence_required"
    assert result.journal_lines_enabled is False


def test_same_day_contractual_cash_flow_fails_closed() -> None:
    evidence = replace(
        _evidence(),
        installments=(
            RenewalTreatmentInstallment(
                installment_number=1,
                due_date=RENEWAL_DATE,
                contractual_amount=Decimal("2400.00"),
            ),
        ),
    )
    result = build_renewal_treatment_readiness(evidence)
    assert result.blocker_code == "renewal_contract_cash_flow_ordering_invalid"
    assert result.present_value_at_original_eir is None


def test_renewal_deductions_fail_closed_for_separate_policy_review() -> None:
    evidence = replace(_evidence(), other_deduction_amount=Decimal("50.00"))
    result = build_renewal_treatment_readiness(evidence)
    assert result.blocker_code == "renewal_deductions_require_policy_review"
    assert result.treatment_decision_required is True
    assert result.automatic_source_posting is False
