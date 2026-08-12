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
from gilbic_backend.renewal_treatment_review_token import (
    build_renewal_treatment_review_token,
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
            RenewalTreatmentInstallment(1, date(2026, 9, 30), Decimal("600.00")),
            RenewalTreatmentInstallment(2, date(2026, 10, 30), Decimal("600.00")),
            RenewalTreatmentInstallment(3, date(2026, 11, 29), Decimal("600.00")),
            RenewalTreatmentInstallment(4, date(2026, 12, 29), Decimal("600.00")),
        ),
    )


def test_ready_review_token_is_stable_sha256() -> None:
    evidence = _evidence()
    readiness = build_renewal_treatment_readiness(evidence)
    first = build_renewal_treatment_review_token(evidence, readiness)
    second = build_renewal_treatment_review_token(evidence, readiness)

    assert first is not None
    assert len(first) == 64
    assert first == second
    assert all(character in "0123456789abcdef" for character in first)


def test_contractual_cash_flow_change_changes_review_token() -> None:
    evidence = _evidence()
    first = build_renewal_treatment_review_token(
        evidence,
        build_renewal_treatment_readiness(evidence),
    )
    changed = replace(
        evidence,
        installments=(
            RenewalTreatmentInstallment(1, date(2026, 9, 30), Decimal("601.00")),
            *evidence.installments[1:],
        ),
    )
    second = build_renewal_treatment_review_token(
        changed,
        build_renewal_treatment_readiness(changed),
    )

    assert first is not None
    assert second is not None
    assert first != second


def test_blocked_readiness_has_no_review_token() -> None:
    evidence = replace(
        _evidence(),
        accounting_carrying_amount_ready=False,
        old_gross_carrying_amount=None,
    )
    readiness = build_renewal_treatment_readiness(evidence)

    assert readiness.disposition == "renewal_accounting_treatment_review_blocked"
    assert build_renewal_treatment_review_token(evidence, readiness) is None
