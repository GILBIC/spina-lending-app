from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from gilbic_backend.renewal_treatment_accounting_target import (
    RenewalTreatmentAccountingEvidence,
    build_renewal_treatment_accounting_target,
)


DECISION_ID = UUID("11111111-1111-4111-8111-111111111111")
EXECUTION_ID = UUID("22222222-2222-4222-8222-222222222222")
OLD_LOAN_ID = UUID("33333333-3333-4333-8333-333333333333")
NEW_LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
CLIENT_ID = UUID("55555555-5555-4555-8555-555555555555")


def _evidence(
    *,
    decision: str = "modification_no_derecognition",
    active: bool = True,
    carrying: str = "2000.00",
    revised: str = "1800.00",
    change: str = "-200.00",
) -> RenewalTreatmentAccountingEvidence:
    return RenewalTreatmentAccountingEvidence(
        decision_id=DECISION_ID,
        renewal_execution_event_id=EXECUTION_ID,
        old_loan_id=OLD_LOAN_ID,
        new_loan_id=NEW_LOAN_ID,
        client_id=CLIENT_ID,
        decision=decision,
        decision_active=active,
        old_gross_carrying_amount=Decimal(carrying),
        original_daily_eir=Decimal("0.001"),
        present_value_at_original_eir=Decimal(revised),
        present_value_change_amount=Decimal(change),
    )


def test_modification_loss_preserves_old_financial_asset_identity() -> None:
    target = build_renewal_treatment_accounting_target(_evidence())

    assert target.disposition == "renewal_modification_measurement_ready"
    assert target.accounting_asset_loan_id == OLD_LOAN_ID
    assert target.operational_renewal_loan_id == NEW_LOAN_ID
    assert target.revised_gross_carrying_amount == Decimal("1800.00")
    assert target.modification_adjustment_amount == Decimal("200.00")
    assert target.modification_signed_adjustment_amount == Decimal("-200.00")
    assert target.modification_profit_or_loss == "loss"
    assert target.accounting_asset_continues is True
    assert target.treatment_journal_coordinates_ready is False
    assert target.journal_lines_enabled is False
    assert target.automatic_source_posting is False


def test_modification_gain_is_measured_without_assigning_gl_coordinates() -> None:
    target = build_renewal_treatment_accounting_target(
        _evidence(revised="2200.00", change="200.00")
    )

    assert target.disposition == "renewal_modification_measurement_ready"
    assert target.revised_gross_carrying_amount == Decimal("2200.00")
    assert target.modification_adjustment_amount == Decimal("200.00")
    assert target.modification_signed_adjustment_amount == Decimal("200.00")
    assert target.modification_profit_or_loss == "gain"
    assert target.treatment_journal_coordinates_ready is False


def test_zero_modification_adjustment_is_explicit() -> None:
    target = build_renewal_treatment_accounting_target(
        _evidence(revised="2000.00", change="0.00")
    )

    assert target.modification_adjustment_amount == Decimal("0.00")
    assert target.modification_signed_adjustment_amount == Decimal("0.00")
    assert target.modification_profit_or_loss == "none"


def test_reviewed_change_mismatch_fails_closed() -> None:
    target = build_renewal_treatment_accounting_target(
        _evidence(revised="1800.00", change="-199.99")
    )

    assert target.disposition == "renewal_treatment_accounting_blocked"
    assert target.blocker_code == "reviewed_measurement_snapshot_mismatch"
    assert target.revised_gross_carrying_amount is None
    assert target.modification_signed_adjustment_amount is None
    assert target.accounting_asset_continues is True
    assert target.treatment_journal_coordinates_ready is False


def test_derecognition_waits_for_authoritative_new_asset_initial_measurement() -> None:
    target = build_renewal_treatment_accounting_target(
        _evidence(decision="derecognition")
    )

    assert target.disposition == "renewal_treatment_accounting_blocked"
    assert target.blocker_code == "new_financial_asset_initial_measurement_required"
    assert target.accounting_asset_continues is False
    assert target.new_financial_asset_recognition_required is True
    assert target.new_financial_asset_measurement_required is True
    assert target.modification_signed_adjustment_amount is None
    assert target.treatment_journal_coordinates_ready is False


def test_inactive_reviewed_decision_fails_closed_without_implying_derecognition() -> None:
    target = build_renewal_treatment_accounting_target(_evidence(active=False))

    assert target.disposition == "renewal_treatment_accounting_blocked"
    assert target.blocker_code == "active_reviewed_treatment_decision_required"
    assert target.accounting_asset_continues is None
    assert target.modification_signed_adjustment_amount is None
    assert target.journal_lines_enabled is False
    assert target.automatic_source_posting is False


def test_unsupported_reviewed_decision_does_not_imply_asset_discontinuation() -> None:
    target = build_renewal_treatment_accounting_target(
        _evidence(decision="future_policy_value")
    )

    assert target.disposition == "renewal_treatment_accounting_blocked"
    assert target.blocker_code == "unsupported_reviewed_treatment_decision"
    assert target.accounting_asset_continues is None
    assert target.new_financial_asset_recognition_required is False
    assert target.treatment_journal_coordinates_ready is False
