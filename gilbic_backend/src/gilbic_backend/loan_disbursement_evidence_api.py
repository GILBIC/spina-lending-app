from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .loan_disbursement_evidence_repository import (
    LoanDisbursementEvidenceConflict,
    LoanDisbursementEvidenceError,
    LoanDisbursementEvidenceInvalid,
    LoanDisbursementEvidenceNotFound,
    LoanDisbursementEvidenceRecord,
    LoanDisbursementReadinessRecord,
    PostgresLoanDisbursementEvidenceRepository,
)
from .request_auth import authenticated_device_context


class LoanDisbursementEvidenceBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    loan_id: UUID
    event_kind: Literal[
        "new_loan_release",
        "renewal_release",
        "restructure_release",
    ]
    business_date: date
    disbursed_at: datetime
    cash_disbursed_amount: Decimal = Field(ge=0)
    settlement_amount: Decimal = Field(default=Decimal("0"), ge=0)
    other_deduction_amount: Decimal = Field(default=Decimal("0"), ge=0)
    funding_account_system_key: Literal[
        "cash_office",
        "cash_collector_custody",
        "cash_bank_gcash",
    ]
    external_reference: str = Field(min_length=1, max_length=200)
    evidence_note: str = Field(default="", max_length=1000)


class LoanDisbursementEvidenceVoidBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=3, max_length=500)


def loan_disbursement_evidence_repository_dependency(
) -> PostgresLoanDisbursementEvidenceRepository:
    return PostgresLoanDisbursementEvidenceRepository()


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


def _raise_evidence_error(error: LoanDisbursementEvidenceError) -> None:
    if isinstance(error, LoanDisbursementEvidenceNotFound):
        status_code = 404
    elif isinstance(error, LoanDisbursementEvidenceConflict):
        status_code = 409
    elif isinstance(error, LoanDisbursementEvidenceInvalid):
        status_code = 422
    else:
        status_code = 409
    raise HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    ) from error


def _event_payload(record: LoanDisbursementEvidenceRecord) -> dict[str, object]:
    return {
        "event_id": str(record.event_id),
        "loan_id": str(record.loan_id),
        "loan_number": record.loan_number,
        "client_id": str(record.client_id),
        "client_code": record.client_code,
        "client_name": record.client_name,
        "event_kind": record.event_kind,
        "business_date": record.business_date.isoformat(),
        "disbursed_at": record.disbursed_at.isoformat(),
        "cash_disbursed_amount": format(record.cash_disbursed_amount, "f"),
        "settlement_amount": format(record.settlement_amount, "f"),
        "other_deduction_amount": format(record.other_deduction_amount, "f"),
        "funding_account_system_key": record.funding_account_system_key,
        "external_reference": record.external_reference,
        "evidence_note": record.evidence_note,
        "principal_snapshot": format(record.principal_snapshot, "f"),
        "date_released_snapshot": record.date_released_snapshot.isoformat(),
        "loan_status_snapshot": record.loan_status_snapshot,
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


def _readiness_payload(record: LoanDisbursementReadinessRecord) -> dict[str, object]:
    return {
        "loan_id": str(record.loan_id),
        "loan_number": record.loan_number,
        "client_id": str(record.client_id),
        "client_code": record.client_code,
        "client_name": record.client_name,
        "loan_type_code": record.loan_type_code,
        "loan_type_name": record.loan_type_name,
        "calculation_mode": record.calculation_mode,
        "principal": format(record.principal, "f"),
        "date_released": record.date_released.isoformat(),
        "loan_status": record.loan_status,
        "disbursement_event_id": (
            str(record.disbursement_event_id)
            if record.disbursement_event_id
            else None
        ),
        "event_kind": record.event_kind,
        "business_date": (
            record.business_date.isoformat() if record.business_date else None
        ),
        "disbursed_at": (
            record.disbursed_at.isoformat() if record.disbursed_at else None
        ),
        "cash_disbursed_amount": (
            format(record.cash_disbursed_amount, "f")
            if record.cash_disbursed_amount is not None
            else None
        ),
        "settlement_amount": (
            format(record.settlement_amount, "f")
            if record.settlement_amount is not None
            else None
        ),
        "other_deduction_amount": (
            format(record.other_deduction_amount, "f")
            if record.other_deduction_amount is not None
            else None
        ),
        "funding_account_system_key": record.funding_account_system_key,
        "external_reference": record.external_reference,
        "readiness_status": record.readiness_status,
        "source_event_key": record.source_event_key,
        "journal_lines_enabled": record.journal_lines_enabled,
        "automatic_source_posting": record.automatic_source_posting,
    }


def create_loan_disbursement_evidence_router() -> APIRouter:
    router = APIRouter(tags=["management loan disbursement evidence"])

    @router.get("/api/v1/management/accounting/loan-disbursements/readiness")
    def list_loan_disbursement_readiness(
        readiness_status: str | None = Query(default=None, max_length=80),
        limit: int = Query(default=100, ge=1, le=250),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresLoanDisbursementEvidenceRepository = Depends(
            loan_disbursement_evidence_repository_dependency
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
        except LoanDisbursementEvidenceError as error:
            _raise_evidence_error(error)
        return {
            "success": True,
            "data": {
                "journal_lines_enabled": False,
                "automatic_source_posting": False,
                "events": [_readiness_payload(record) for record in records],
            },
        }

    @router.post("/api/v1/management/accounting/loan-disbursements")
    def record_loan_disbursement_evidence(
        body: LoanDisbursementEvidenceBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresLoanDisbursementEvidenceRepository = Depends(
            loan_disbursement_evidence_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _management_actor(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.loan_disbursement.evidence.manage",
            permission_error="Management loan-disbursement evidence permission is required.",
        )
        try:
            record = repository.record(
                actor_user_id=actor.user_id,
                loan_id=body.loan_id,
                event_kind=body.event_kind,
                business_date=body.business_date,
                disbursed_at=body.disbursed_at,
                cash_disbursed_amount=body.cash_disbursed_amount,
                settlement_amount=body.settlement_amount,
                other_deduction_amount=body.other_deduction_amount,
                funding_account_system_key=body.funding_account_system_key,
                external_reference=body.external_reference,
                evidence_note=body.evidence_note,
            )
        except LoanDisbursementEvidenceError as error:
            _raise_evidence_error(error)
        return {"success": True, "data": _event_payload(record)}

    @router.post(
        "/api/v1/management/accounting/loan-disbursements/{event_id}/void"
    )
    def void_loan_disbursement_evidence(
        event_id: UUID,
        body: LoanDisbursementEvidenceVoidBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresLoanDisbursementEvidenceRepository = Depends(
            loan_disbursement_evidence_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _management_actor(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.loan_disbursement.evidence.manage",
            permission_error="Management loan-disbursement evidence permission is required.",
        )
        try:
            record = repository.void(
                actor_user_id=actor.user_id,
                event_id=event_id,
                reason=body.reason,
            )
        except LoanDisbursementEvidenceError as error:
            _raise_evidence_error(error)
        return {"success": True, "data": _event_payload(record)}

    return router
