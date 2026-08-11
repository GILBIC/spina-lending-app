from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .loan_renewal_execution_evidence_repository import (
    LoanRenewalExecutionEvidenceConflict,
    LoanRenewalExecutionEvidenceError,
    LoanRenewalExecutionEvidenceInvalid,
    LoanRenewalExecutionEvidenceNotFound,
    LoanRenewalExecutionEvidenceRecord,
    LoanRenewalExecutionReadinessRecord,
    PostgresLoanRenewalExecutionEvidenceRepository,
)
from .request_auth import authenticated_device_context


class LoanRenewalExecutionEvidenceBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    old_loan_id: UUID
    new_loan_id: UUID
    disbursement_event_id: UUID
    business_date: date
    executed_at: datetime
    old_loan_settlement_amount: Decimal = Field(ge=0)
    external_reference: str = Field(min_length=1, max_length=200)
    evidence_note: str = Field(default="", max_length=1000)
    renewal_request_id: UUID | None = None


class LoanRenewalExecutionEvidenceVoidBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=3, max_length=500)


def loan_renewal_execution_evidence_repository_dependency(
) -> PostgresLoanRenewalExecutionEvidenceRepository:
    return PostgresLoanRenewalExecutionEvidenceRepository()


def _management_actor(
    *,
    authorization: str | None,
    device_identifier: str | None,
    auth: SupabaseAuthClient,
    accounts: PostgresAccountRepository,
    permission: str,
    permission_error: str,
):
    return authenticated_device_context(
        authorization=authorization,
        device_identifier=device_identifier,
        auth=auth,
        accounts=accounts,
        permission=permission,
        permission_error=permission_error,
    )


def _raise_evidence_error(error: LoanRenewalExecutionEvidenceError) -> None:
    if isinstance(error, LoanRenewalExecutionEvidenceNotFound):
        status_code = 404
    elif isinstance(error, LoanRenewalExecutionEvidenceConflict):
        status_code = 409
    elif isinstance(error, LoanRenewalExecutionEvidenceInvalid):
        status_code = 422
    else:
        status_code = 409
    raise HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    ) from error


def _event_payload(record: LoanRenewalExecutionEvidenceRecord) -> dict[str, object]:
    return {
        "event_id": str(record.event_id),
        "old_loan_id": str(record.old_loan_id),
        "old_loan_number": record.old_loan_number,
        "new_loan_id": str(record.new_loan_id),
        "new_loan_number": record.new_loan_number,
        "disbursement_event_id": str(record.disbursement_event_id),
        "client_id": str(record.client_id),
        "client_code": record.client_code,
        "client_name": record.client_name,
        "renewal_request_id": (
            str(record.renewal_request_id) if record.renewal_request_id else None
        ),
        "business_date": record.business_date.isoformat(),
        "executed_at": record.executed_at.isoformat(),
        "old_loan_settlement_amount": format(record.old_loan_settlement_amount, "f"),
        "external_reference": record.external_reference,
        "evidence_note": record.evidence_note,
        "old_loan_principal_snapshot": format(record.old_loan_principal_snapshot, "f"),
        "old_loan_date_released_snapshot": record.old_loan_date_released_snapshot.isoformat(),
        "old_loan_status_snapshot": record.old_loan_status_snapshot,
        "new_loan_principal_snapshot": format(record.new_loan_principal_snapshot, "f"),
        "new_loan_date_released_snapshot": record.new_loan_date_released_snapshot.isoformat(),
        "new_loan_status_snapshot": record.new_loan_status_snapshot,
        "recorded_by_user_id": str(record.recorded_by_user_id),
        "recorded_at": record.recorded_at.isoformat(),
        "is_voided": record.is_voided,
        "voided_by_user_id": (
            str(record.voided_by_user_id) if record.voided_by_user_id else None
        ),
        "voided_at": record.voided_at.isoformat() if record.voided_at else None,
        "void_reason": record.void_reason,
        "journal_lines_enabled": False,
        "automatic_source_posting": False,
    }


def _readiness_payload(record: LoanRenewalExecutionReadinessRecord) -> dict[str, object]:
    return {
        "disbursement_event_id": str(record.disbursement_event_id),
        "new_loan_id": str(record.new_loan_id),
        "new_loan_number": record.new_loan_number,
        "renewal_execution_event_id": (
            str(record.renewal_execution_event_id)
            if record.renewal_execution_event_id
            else None
        ),
        "old_loan_id": str(record.old_loan_id) if record.old_loan_id else None,
        "old_loan_number": record.old_loan_number,
        "client_id": str(record.client_id),
        "client_code": record.client_code,
        "client_name": record.client_name,
        "renewal_request_id": (
            str(record.renewal_request_id) if record.renewal_request_id else None
        ),
        "renewal_request_status": record.renewal_request_status,
        "new_loan_type_code": record.new_loan_type_code,
        "new_loan_type_name": record.new_loan_type_name,
        "new_loan_calculation_mode": record.new_loan_calculation_mode,
        "new_loan_principal": format(record.new_loan_principal, "f"),
        "old_loan_principal": (
            format(record.old_loan_principal, "f")
            if record.old_loan_principal is not None
            else None
        ),
        "release_business_date": record.release_business_date.isoformat(),
        "disbursed_at": record.disbursed_at.isoformat(),
        "cash_disbursed_amount": format(record.cash_disbursed_amount, "f"),
        "settlement_amount": format(record.settlement_amount, "f"),
        "other_deduction_amount": format(record.other_deduction_amount, "f"),
        "funding_account_system_key": record.funding_account_system_key,
        "release_external_reference": record.release_external_reference,
        "execution_business_date": (
            record.execution_business_date.isoformat()
            if record.execution_business_date
            else None
        ),
        "executed_at": record.executed_at.isoformat() if record.executed_at else None,
        "old_loan_settlement_amount": (
            format(record.old_loan_settlement_amount, "f")
            if record.old_loan_settlement_amount is not None
            else None
        ),
        "execution_external_reference": record.execution_external_reference,
        "readiness_status": record.readiness_status,
        "source_event_key": record.source_event_key,
        "journal_lines_enabled": record.journal_lines_enabled,
        "automatic_source_posting": record.automatic_source_posting,
    }


def create_loan_renewal_execution_evidence_router() -> APIRouter:
    router = APIRouter(tags=["management loan renewal execution evidence"])

    @router.get("/api/v1/management/accounting/loan-renewals/readiness")
    def list_loan_renewal_execution_readiness(
        readiness_status: str | None = Query(default=None, max_length=80),
        limit: int = Query(default=100, ge=1, le=250),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresLoanRenewalExecutionEvidenceRepository = Depends(
            loan_renewal_execution_evidence_repository_dependency
        ),
    ) -> dict[str, object]:
        _management_actor(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.view",
            permission_error="Management accounting view permission is required.",
        )
        try:
            records = repository.list_readiness(
                readiness_status=readiness_status,
                limit=limit,
            )
        except LoanRenewalExecutionEvidenceError as error:
            _raise_evidence_error(error)
        return {
            "success": True,
            "data": {
                "journal_lines_enabled": False,
                "automatic_source_posting": False,
                "events": [_readiness_payload(record) for record in records],
            },
        }

    @router.post("/api/v1/management/accounting/loan-renewals")
    def record_loan_renewal_execution_evidence(
        body: LoanRenewalExecutionEvidenceBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresLoanRenewalExecutionEvidenceRepository = Depends(
            loan_renewal_execution_evidence_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _management_actor(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.loan_renewal_execution.evidence.manage",
            permission_error="Management loan-renewal execution evidence permission is required.",
        )
        try:
            record = repository.record(
                actor_user_id=actor.user_id,
                old_loan_id=body.old_loan_id,
                new_loan_id=body.new_loan_id,
                disbursement_event_id=body.disbursement_event_id,
                business_date=body.business_date,
                executed_at=body.executed_at,
                old_loan_settlement_amount=body.old_loan_settlement_amount,
                external_reference=body.external_reference,
                evidence_note=body.evidence_note,
                renewal_request_id=body.renewal_request_id,
            )
        except LoanRenewalExecutionEvidenceError as error:
            _raise_evidence_error(error)
        return {"success": True, "data": _event_payload(record)}

    @router.post(
        "/api/v1/management/accounting/loan-renewals/{event_id}/void"
    )
    def void_loan_renewal_execution_evidence(
        event_id: UUID,
        body: LoanRenewalExecutionEvidenceVoidBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresLoanRenewalExecutionEvidenceRepository = Depends(
            loan_renewal_execution_evidence_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _management_actor(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.loan_renewal_execution.evidence.manage",
            permission_error="Management loan-renewal execution evidence permission is required.",
        )
        try:
            record = repository.void(
                actor_user_id=actor.user_id,
                event_id=event_id,
                reason=body.reason,
            )
        except LoanRenewalExecutionEvidenceError as error:
            _raise_evidence_error(error)
        return {"success": True, "data": _event_payload(record)}

    return router
