from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .renewal_treatment_decision_repository import (
    PostgresRenewalTreatmentDecisionRepository,
    RenewalTreatmentDecisionConflict,
    RenewalTreatmentDecisionError,
    RenewalTreatmentDecisionNotFound,
    RenewalTreatmentDecisionRecord,
)
from .request_auth import authenticated_device_context


class RenewalTreatmentDecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expected_review_token: str = Field(min_length=64, max_length=64)
    decision: Literal["modification_no_derecognition", "derecognition"]
    accounting_policy_reference: str = Field(min_length=1, max_length=500)
    qualitative_assessment: dict[str, Any]
    decision_rationale: str = Field(min_length=20, max_length=4000)
    supporting_evidence_reference: str = Field(min_length=1, max_length=1000)
    confirm: bool = False


class RenewalTreatmentDecisionVoidBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=3, max_length=1000)
    confirm: bool = False


def renewal_treatment_decision_repository_dependency() -> (
    PostgresRenewalTreatmentDecisionRepository
):
    return PostgresRenewalTreatmentDecisionRepository()


def _management_actor(
    *,
    authorization: str | None,
    device_identifier: str | None,
    auth: SupabaseAuthClient,
    accounts: PostgresAccountRepository,
    permission: str,
    permission_error: str,
):
    actor = authenticated_device_context(
        authorization=authorization,
        device_identifier=device_identifier,
        auth=auth,
        accounts=accounts,
        permission=permission,
        permission_error=permission_error,
    )
    if "management" not in actor.roles:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "management_role_required",
                "message": "Management access is required for renewal accounting treatment decisions.",
            },
        )
    return actor


def _raise_decision_error(error: RenewalTreatmentDecisionError) -> None:
    if isinstance(error, RenewalTreatmentDecisionNotFound):
        status_code = 404
    elif isinstance(error, RenewalTreatmentDecisionConflict):
        status_code = 409
    else:
        status_code = 409
    raise HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    ) from error


def _payload(record: RenewalTreatmentDecisionRecord) -> dict[str, object]:
    return {
        "decision_id": str(record.decision_id),
        "renewal_execution_event_id": str(record.renewal_execution_event_id),
        "old_loan_id": str(record.old_loan_id),
        "old_loan_number": record.old_loan_number,
        "new_loan_id": str(record.new_loan_id),
        "new_loan_number": record.new_loan_number,
        "client_id": str(record.client_id),
        "client_code": record.client_code,
        "client_name": record.client_name,
        "renewal_business_date": record.renewal_business_date.isoformat(),
        "readiness_review_token": record.readiness_review_token,
        "readiness_policy_version": record.readiness_policy_version,
        "decision": record.decision,
        "decision_policy_version": record.decision_policy_version,
        "accounting_policy_reference": record.accounting_policy_reference,
        "qualitative_assessment": record.qualitative_assessment,
        "decision_rationale": record.decision_rationale,
        "supporting_evidence_reference": record.supporting_evidence_reference,
        "old_gross_carrying_amount": format(record.old_gross_carrying_amount, ".2f"),
        "original_daily_eir": format(record.original_daily_eir, "f"),
        "renewal_cash_disbursed_amount": format(
            record.renewal_cash_disbursed_amount, ".2f"
        ),
        "renewal_settlement_amount": format(record.renewal_settlement_amount, ".2f"),
        "renewal_other_deduction_amount": format(
            record.renewal_other_deduction_amount, ".2f"
        ),
        "schedule_id": str(record.schedule_id),
        "schedule_version": record.schedule_version,
        "contract_reference": record.contract_reference,
        "contract_evidence_reference": record.contract_evidence_reference,
        "installment_count": record.installment_count,
        "contractual_cash_total": format(record.contractual_cash_total, ".2f"),
        "present_value_at_original_eir": format(
            record.present_value_at_original_eir, ".2f"
        ),
        "present_value_change_amount": format(
            record.present_value_change_amount, ".2f"
        ),
        "present_value_change_percent": format(
            record.present_value_change_percent, "f"
        ),
        "reviewed_by_user_id": str(record.reviewed_by_user_id),
        "reviewed_at": record.reviewed_at.isoformat(),
        "void_id": None if record.void_id is None else str(record.void_id),
        "void_reason": record.void_reason,
        "voided_by_user_id": (
            None if record.voided_by_user_id is None else str(record.voided_by_user_id)
        ),
        "voided_at": None if record.voided_at is None else record.voided_at.isoformat(),
        "is_active": record.is_active,
        "automatic_classification_enabled": record.automatic_classification_enabled,
        "quantitative_threshold_decisive": record.quantitative_threshold_decisive,
        "journal_lines_enabled": record.journal_lines_enabled,
        "automatic_source_posting": record.automatic_source_posting,
        "evidence_only": True,
        "treatment_journal_coordinates_enabled": False,
    }


def create_renewal_treatment_decision_router() -> APIRouter:
    router = APIRouter(tags=["management renewal accounting treatment decisions"])

    @router.get(
        "/api/v1/management/accounting/renewals/{renewal_execution_event_id}/treatment-decisions"
    )
    def list_decisions(
        renewal_execution_event_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRenewalTreatmentDecisionRepository = Depends(
            renewal_treatment_decision_repository_dependency
        ),
    ) -> dict[str, object]:
        _management_actor(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.view",
            permission_error="Financial Accounting view permission is required.",
        )
        try:
            records = repository.get_for_execution(
                renewal_execution_event_id=renewal_execution_event_id,
            )
        except RenewalTreatmentDecisionError as error:
            _raise_decision_error(error)
        return {
            "success": True,
            "data": {
                "renewal_execution_event_id": str(renewal_execution_event_id),
                "decisions": [_payload(record) for record in records],
                "automatic_classification_enabled": False,
                "quantitative_threshold_decisive": False,
                "journal_lines_enabled": False,
                "automatic_source_posting": False,
            },
        }

    @router.post(
        "/api/v1/management/accounting/renewals/{renewal_execution_event_id}/treatment-decisions"
    )
    def record_decision(
        renewal_execution_event_id: UUID,
        body: RenewalTreatmentDecisionBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRenewalTreatmentDecisionRepository = Depends(
            renewal_treatment_decision_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _management_actor(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.renewal_treatment_decision.manage",
            permission_error="Management renewal treatment decision permission is required.",
        )
        if not body.confirm:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "renewal_treatment_decision_confirmation_required",
                    "message": "Explicit Management confirmation is required before recording immutable renewal treatment decision evidence.",
                },
            )
        try:
            record = repository.record(
                renewal_execution_event_id=renewal_execution_event_id,
                actor_user_id=actor.user_id,
                expected_review_token=body.expected_review_token,
                decision=body.decision,
                accounting_policy_reference=body.accounting_policy_reference,
                qualitative_assessment=body.qualitative_assessment,
                decision_rationale=body.decision_rationale,
                supporting_evidence_reference=body.supporting_evidence_reference,
            )
        except RenewalTreatmentDecisionError as error:
            _raise_decision_error(error)
        return {
            "success": True,
            "data": _payload(record),
            "notice": (
                "The reviewed accounting-policy decision was recorded as immutable evidence only. "
                "No treatment journal coordinates were created and automatic source posting remains disabled."
            ),
        }

    @router.post(
        "/api/v1/management/accounting/renewal-treatment-decisions/{decision_id}/void"
    )
    def void_decision(
        decision_id: UUID,
        body: RenewalTreatmentDecisionVoidBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRenewalTreatmentDecisionRepository = Depends(
            renewal_treatment_decision_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _management_actor(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.renewal_treatment_decision.manage",
            permission_error="Management renewal treatment decision permission is required.",
        )
        if not body.confirm:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "renewal_treatment_decision_void_confirmation_required",
                    "message": "Explicit Management confirmation is required before voiding renewal treatment decision evidence.",
                },
            )
        try:
            record = repository.void(
                decision_id=decision_id,
                actor_user_id=actor.user_id,
                reason=body.reason,
            )
        except RenewalTreatmentDecisionError as error:
            _raise_decision_error(error)
        return {
            "success": True,
            "data": _payload(record),
            "notice": (
                "The original reviewed decision remains immutable; separate void evidence was recorded. "
                "No accounting journal history was deleted or created."
            ),
        }

    return router
