from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID


MONEY = Decimal("0.01")
POLICY_VERSION = "renewal_treatment_accounting_target_v2"


@dataclass(frozen=True, slots=True)
class RenewalTreatmentAccountingEvidence:
    decision_id: UUID
    renewal_execution_event_id: UUID
    old_loan_id: UUID
    new_loan_id: UUID
    client_id: UUID
    decision: str
    decision_active: bool
    old_gross_carrying_amount: Decimal
    original_daily_eir: Decimal
    present_value_at_original_eir: Decimal
    present_value_change_amount: Decimal


@dataclass(frozen=True, slots=True)
class RenewalTreatmentAccountingTarget:
    disposition: str
    blocker_code: str | None
    message: str
    policy_version: str
    accounting_asset_loan_id: UUID | None
    operational_renewal_loan_id: UUID
    old_gross_carrying_amount: Decimal
    revised_gross_carrying_amount: Decimal | None
    original_daily_eir: Decimal
    modification_adjustment_amount: Decimal | None
    modification_signed_adjustment_amount: Decimal | None
    modification_profit_or_loss: str | None
    accounting_asset_continues: bool | None
    new_financial_asset_recognition_required: bool
    new_financial_asset_measurement_required: bool
    treatment_journal_coordinates_ready: bool
    journal_lines_enabled: bool
    automatic_source_posting: bool


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def build_renewal_treatment_accounting_target(
    evidence: RenewalTreatmentAccountingEvidence,
) -> RenewalTreatmentAccountingTarget:
    old_carrying = _money(evidence.old_gross_carrying_amount)
    revised_carrying = _money(evidence.present_value_at_original_eir)
    change = _money(evidence.present_value_change_amount)

    if not evidence.decision_active:
        return RenewalTreatmentAccountingTarget(
            disposition="renewal_treatment_accounting_blocked",
            blocker_code="active_reviewed_treatment_decision_required",
            message="An active immutable reviewed renewal treatment decision is required.",
            policy_version=POLICY_VERSION,
            accounting_asset_loan_id=None,
            operational_renewal_loan_id=evidence.new_loan_id,
            old_gross_carrying_amount=old_carrying,
            revised_gross_carrying_amount=None,
            original_daily_eir=evidence.original_daily_eir,
            modification_adjustment_amount=None,
            modification_signed_adjustment_amount=None,
            modification_profit_or_loss=None,
            accounting_asset_continues=None,
            new_financial_asset_recognition_required=False,
            new_financial_asset_measurement_required=False,
            treatment_journal_coordinates_ready=False,
            journal_lines_enabled=False,
            automatic_source_posting=False,
        )

    if evidence.decision == "derecognition":
        return RenewalTreatmentAccountingTarget(
            disposition="renewal_treatment_accounting_blocked",
            blocker_code="new_financial_asset_initial_measurement_required",
            message=(
                "The reviewed decision requires derecognition. Authoritative initial "
                "measurement evidence for the new financial asset is required before "
                "recognition or derecognition coordinates can be produced. Do not infer "
                "fair value from principal, cash disbursed, settlement, contract totals, "
                "or the original-EIR present-value comparison."
            ),
            policy_version=POLICY_VERSION,
            accounting_asset_loan_id=evidence.old_loan_id,
            operational_renewal_loan_id=evidence.new_loan_id,
            old_gross_carrying_amount=old_carrying,
            revised_gross_carrying_amount=None,
            original_daily_eir=evidence.original_daily_eir,
            modification_adjustment_amount=None,
            modification_signed_adjustment_amount=None,
            modification_profit_or_loss=None,
            accounting_asset_continues=False,
            new_financial_asset_recognition_required=True,
            new_financial_asset_measurement_required=True,
            treatment_journal_coordinates_ready=False,
            journal_lines_enabled=False,
            automatic_source_posting=False,
        )

    if evidence.decision != "modification_no_derecognition":
        return RenewalTreatmentAccountingTarget(
            disposition="renewal_treatment_accounting_blocked",
            blocker_code="unsupported_reviewed_treatment_decision",
            message="The reviewed renewal treatment decision is not supported by this accounting target.",
            policy_version=POLICY_VERSION,
            accounting_asset_loan_id=None,
            operational_renewal_loan_id=evidence.new_loan_id,
            old_gross_carrying_amount=old_carrying,
            revised_gross_carrying_amount=None,
            original_daily_eir=evidence.original_daily_eir,
            modification_adjustment_amount=None,
            modification_signed_adjustment_amount=None,
            modification_profit_or_loss=None,
            accounting_asset_continues=None,
            new_financial_asset_recognition_required=False,
            new_financial_asset_measurement_required=False,
            treatment_journal_coordinates_ready=False,
            journal_lines_enabled=False,
            automatic_source_posting=False,
        )

    if old_carrying <= 0 or revised_carrying <= 0 or evidence.original_daily_eir <= 0:
        return RenewalTreatmentAccountingTarget(
            disposition="renewal_treatment_accounting_blocked",
            blocker_code="reviewed_measurement_snapshot_invalid",
            message="The reviewed treatment evidence contains an invalid carrying amount or original EIR snapshot.",
            policy_version=POLICY_VERSION,
            accounting_asset_loan_id=evidence.old_loan_id,
            operational_renewal_loan_id=evidence.new_loan_id,
            old_gross_carrying_amount=old_carrying,
            revised_gross_carrying_amount=None,
            original_daily_eir=evidence.original_daily_eir,
            modification_adjustment_amount=None,
            modification_signed_adjustment_amount=None,
            modification_profit_or_loss=None,
            accounting_asset_continues=True,
            new_financial_asset_recognition_required=False,
            new_financial_asset_measurement_required=False,
            treatment_journal_coordinates_ready=False,
            journal_lines_enabled=False,
            automatic_source_posting=False,
        )

    expected_change = _money(revised_carrying - old_carrying)
    if expected_change != change:
        return RenewalTreatmentAccountingTarget(
            disposition="renewal_treatment_accounting_blocked",
            blocker_code="reviewed_measurement_snapshot_mismatch",
            message="The reviewed present-value change no longer matches the reviewed carrying-amount snapshots.",
            policy_version=POLICY_VERSION,
            accounting_asset_loan_id=evidence.old_loan_id,
            operational_renewal_loan_id=evidence.new_loan_id,
            old_gross_carrying_amount=old_carrying,
            revised_gross_carrying_amount=None,
            original_daily_eir=evidence.original_daily_eir,
            modification_adjustment_amount=None,
            modification_signed_adjustment_amount=None,
            modification_profit_or_loss=None,
            accounting_asset_continues=True,
            new_financial_asset_recognition_required=False,
            new_financial_asset_measurement_required=False,
            treatment_journal_coordinates_ready=False,
            journal_lines_enabled=False,
            automatic_source_posting=False,
        )

    profit_or_loss = "none"
    if change > 0:
        profit_or_loss = "gain"
    elif change < 0:
        profit_or_loss = "loss"

    return RenewalTreatmentAccountingTarget(
        disposition="renewal_modification_measurement_ready",
        blocker_code=None,
        message=(
            "The reviewed modification-without-derecognition decision preserves the "
            "old financial-asset accounting identity. The revised gross carrying amount "
            "is the reviewed modified contractual cash flows discounted at the original "
            "EIR, with the difference identified as modification profit or loss. GL "
            "account mapping and posting remain separate protected work."
        ),
        policy_version=POLICY_VERSION,
        accounting_asset_loan_id=evidence.old_loan_id,
        operational_renewal_loan_id=evidence.new_loan_id,
        old_gross_carrying_amount=old_carrying,
        revised_gross_carrying_amount=revised_carrying,
        original_daily_eir=evidence.original_daily_eir,
        modification_adjustment_amount=abs(change),
        modification_signed_adjustment_amount=change,
        modification_profit_or_loss=profit_or_loss,
        accounting_asset_continues=True,
        new_financial_asset_recognition_required=False,
        new_financial_asset_measurement_required=False,
        treatment_journal_coordinates_ready=False,
        journal_lines_enabled=False,
        automatic_source_posting=False,
    )
