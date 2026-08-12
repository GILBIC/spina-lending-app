from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from .renewal_treatment_readiness import (
    RenewalTreatmentEvidence,
    RenewalTreatmentReadiness,
)


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def build_renewal_treatment_review_token(
    evidence: RenewalTreatmentEvidence,
    readiness: RenewalTreatmentReadiness,
) -> str | None:
    if readiness.disposition != "renewal_accounting_treatment_review_ready":
        return None

    payload = {
        "policy_version": readiness.policy_version,
        "renewal_execution_event_id": str(evidence.renewal_execution_event_id),
        "old_loan_id": str(evidence.old_loan_id),
        "new_loan_id": str(evidence.new_loan_id),
        "client_id": str(evidence.client_id),
        "business_date": evidence.business_date.isoformat(),
        "execution_active": evidence.execution_active,
        "release_event_kind": evidence.release_event_kind,
        "release_business_date": evidence.release_business_date.isoformat(),
        "release_active": evidence.release_active,
        "cash_disbursed_amount": _decimal(evidence.cash_disbursed_amount),
        "settlement_amount": _decimal(evidence.settlement_amount),
        "other_deduction_amount": _decimal(evidence.other_deduction_amount),
        "new_loan_calculation_mode": evidence.new_loan_calculation_mode,
        "accounting_carrying_amount_ready": evidence.accounting_carrying_amount_ready,
        "old_gross_carrying_amount": _decimal(readiness.old_gross_carrying_amount),
        "original_daily_eir": _decimal(readiness.original_daily_eir),
        "schedule_id": None if evidence.schedule_id is None else str(evidence.schedule_id),
        "schedule_version": evidence.schedule_version,
        "schedule_status": evidence.schedule_status,
        "schedule_effective_from": (
            None
            if evidence.schedule_effective_from is None
            else evidence.schedule_effective_from.isoformat()
        ),
        "payment_frequency": evidence.payment_frequency,
        "contract_reference": evidence.contract_reference,
        "contract_signed_date": (
            None
            if evidence.contract_signed_date is None
            else evidence.contract_signed_date.isoformat()
        ),
        "registration_id": (
            None if evidence.registration_id is None else str(evidence.registration_id)
        ),
        "evidence_basis": evidence.evidence_basis,
        "evidence_reference": evidence.evidence_reference,
        "installments": [
            {
                "installment_number": installment.installment_number,
                "due_date": installment.due_date.isoformat(),
                "contractual_amount": _decimal(installment.contractual_amount),
            }
            for installment in evidence.installments
        ],
        "contractual_cash_total": _decimal(readiness.contractual_cash_total),
        "present_value_at_original_eir": _decimal(
            readiness.present_value_at_original_eir
        ),
        "present_value_change_amount": _decimal(
            readiness.present_value_change_amount
        ),
        "present_value_change_percent": _decimal(
            readiness.present_value_change_percent
        ),
        "automatic_classification_enabled": readiness.automatic_classification_enabled,
        "quantitative_threshold_decisive": readiness.quantitative_threshold_decisive,
        "journal_lines_enabled": readiness.journal_lines_enabled,
        "automatic_source_posting": readiness.automatic_source_posting,
    }
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()
