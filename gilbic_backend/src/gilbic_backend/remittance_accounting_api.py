from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .remittance_accounting_repository import (
    PostgresRemittanceAccountingEvidenceRepository,
    RemittanceAccountingEvidenceConflict,
    RemittanceAccountingEvidenceError,
    RemittanceAccountingEvidenceInvalid,
    RemittanceAccountingEvidenceNotFound,
    RemittanceTransferEvidenceRecord,
    RemittanceTransferReadinessRecord,
)
from .request_auth import authenticated_device_context


class RemittanceTransferEvidenceBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    remittance_id: UUID
    destination_account_system_key: Literal["cash_office", "cash_bank_gcash"]
    business_date: date
    transferred_at: datetime
    external_reference: str = Field(min_length=1, max_length=200)
    evidence_note: str = Field(default="", max_length=1000)


class RemittanceTransferEvidenceVoidBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=3, max_length=500)


def remittance_accounting_evidence_repository_dependency(
) -> PostgresRemittanceAccountingEvidenceRepository:
    return PostgresRemittanceAccountingEvidenceRepository()


def _actor(
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


def _raise_evidence_error(error: RemittanceAccountingEvidenceError) -> None:
    if isinstance(error, RemittanceAccountingEvidenceNotFound):
        status_code = 404
    elif isinstance(error, RemittanceAccountingEvidenceConflict):
        status_code = 409
    elif isinstance(error, RemittanceAccountingEvidenceInvalid):
        status_code = 422
    else:
        status_code = 409
    raise HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    ) from error


def _evidence_payload(record: RemittanceTransferEvidenceRecord) -> dict[str, object]:
    return {
        "evidence_id": str(record.evidence_id),
        "remittance_id": str(record.remittance_id),
        "remittance_number": record.remittance_number,
        "destination_account_system_key": record.destination_account_system_key,
        "business_date": record.business_date.isoformat(),
        "transferred_at": record.transferred_at.isoformat(),
        "external_reference": record.external_reference,
        "evidence_note": record.evidence_note,
        "total_amount_snapshot": format(record.total_amount_snapshot, "f"),
        "custody_user_id_snapshot": str(record.custody_user_id_snapshot),
        "custody_transferred_at_snapshot": record.custody_transferred_at_snapshot.isoformat(),
        "recorded_by_user_id": str(record.recorded_by_user_id),
        "recorded_at": record.recorded_at.isoformat(),
        "is_voided": record.is_voided,
        "voided_by_user_id": (
            str(record.voided_by_user_id) if record.voided_by_user_id else None
        ),
        "voided_at": record.voided_at.isoformat() if record.voided_at else None,
        "void_reason": record.void_reason,
        "income_recognition": False,
        "journal_lines_enabled": False,
        "automatic_source_posting": False,
    }


def _readiness_payload(record: RemittanceTransferReadinessRecord) -> dict[str, object]:
    return {
        "remittance_id": str(record.remittance_id),
        "remittance_number": record.remittance_number,
        "collector_user_id": str(record.collector_user_id),
        "collector_name": record.collector_name,
        "recipient_user_id": str(record.recipient_user_id),
        "recipient_name": record.recipient_name,
        "custody_user_id": str(record.custody_user_id) if record.custody_user_id else None,
        "custody_name": record.custody_name,
        "collection_date": record.collection_date.isoformat(),
        "remittance_status": record.remittance_status,
        "total_amount": format(record.total_amount, "f"),
        "received_at": record.received_at.isoformat() if record.received_at else None,
        "custody_transferred_at": (
            record.custody_transferred_at.isoformat()
            if record.custody_transferred_at
            else None
        ),
        "transfer_evidence_id": (
            str(record.transfer_evidence_id) if record.transfer_evidence_id else None
        ),
        "destination_account_system_key": record.destination_account_system_key,
        "business_date": record.business_date.isoformat() if record.business_date else None,
        "transferred_at": record.transferred_at.isoformat() if record.transferred_at else None,
        "external_reference": record.external_reference,
        "readiness_status": record.readiness_status,
        "source_event_key": record.source_event_key,
        "debit_account_system_key": record.debit_account_system_key,
        "credit_account_system_key": record.credit_account_system_key,
        "debit_amount": format(record.debit_amount, "f") if record.debit_amount is not None else None,
        "credit_amount": format(record.credit_amount, "f") if record.credit_amount is not None else None,
        "income_recognition": record.income_recognition,
        "journal_lines_enabled": record.journal_lines_enabled,
        "automatic_source_posting": record.automatic_source_posting,
    }


def create_remittance_accounting_router() -> APIRouter:
    router = APIRouter(tags=["management remittance accounting evidence"])

    @router.get("/api/v1/management/accounting/remittance-transfers/readiness")
    def list_remittance_transfer_readiness(
        readiness_status: str | None = Query(default=None, max_length=80),
        limit: int = Query(default=100, ge=1, le=250),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRemittanceAccountingEvidenceRepository = Depends(
            remittance_accounting_evidence_repository_dependency
        ),
    ) -> dict[str, object]:
        _actor(
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
        except RemittanceAccountingEvidenceError as error:
            _raise_evidence_error(error)
        return {
            "success": True,
            "data": {
                "income_recognition": False,
                "journal_lines_enabled": False,
                "automatic_source_posting": False,
                "notice": (
                    "A remittance is an asset-to-asset custody transfer. Recipient acceptance does not choose the accounting destination. Only explicit protected Office or Bank/GCash destination evidence can make Dr destination cash / Cr Cash - Collector Custody coordinates ready."
                ),
                "remittances": [_readiness_payload(record) for record in records],
            },
        }

    @router.post("/api/v1/management/accounting/remittance-transfers/evidence")
    def record_remittance_transfer_evidence(
        body: RemittanceTransferEvidenceBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRemittanceAccountingEvidenceRepository = Depends(
            remittance_accounting_evidence_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.remittance_transfer.evidence.manage",
            permission_error="Management remittance-transfer evidence permission is required.",
        )
        try:
            record = repository.record(
                actor_user_id=actor.user_id,
                remittance_id=body.remittance_id,
                destination_account_system_key=body.destination_account_system_key,
                business_date=body.business_date,
                transferred_at=body.transferred_at,
                external_reference=body.external_reference,
                evidence_note=body.evidence_note,
            )
        except RemittanceAccountingEvidenceError as error:
            _raise_evidence_error(error)
        return {"success": True, "data": _evidence_payload(record)}

    @router.post(
        "/api/v1/management/accounting/remittance-transfers/evidence/{evidence_id}/void"
    )
    def void_remittance_transfer_evidence(
        evidence_id: UUID,
        body: RemittanceTransferEvidenceVoidBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRemittanceAccountingEvidenceRepository = Depends(
            remittance_accounting_evidence_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.remittance_transfer.evidence.manage",
            permission_error="Management remittance-transfer evidence permission is required.",
        )
        try:
            record = repository.void(
                actor_user_id=actor.user_id,
                evidence_id=evidence_id,
                reason=body.reason,
            )
        except RemittanceAccountingEvidenceError as error:
            _raise_evidence_error(error)
        return {"success": True, "data": _evidence_payload(record)}

    return router
