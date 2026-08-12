from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .remittance_transfer_journal_repository import (
    PostgresRemittanceTransferJournalRepository,
    RemittanceTransferJournalConflict,
    RemittanceTransferJournalError,
    RemittanceTransferJournalInvalid,
    RemittanceTransferJournalNotFound,
    RemittanceTransferJournalStatusRecord,
)
from .request_auth import authenticated_device_context


class RemittanceTransferJournalPrepareBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    remittance_id: UUID
    review_token: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    transfer_evidence_id: UUID
    source_event_key: str = Field(min_length=1, max_length=200)
    posting_date: date
    debit_account_system_key: Literal["cash_office", "cash_bank_gcash"]
    credit_account_system_key: Literal["cash_collector_custody"] = "cash_collector_custody"
    amount: Decimal = Field(gt=0)
    coordinate_policy_version: Literal["remittance_transfer_coordinates_v1"] = (
        "remittance_transfer_coordinates_v1"
    )
    draft_policy_version: Literal["remittance_transfer_journal_draft_v1"] = (
        "remittance_transfer_journal_draft_v1"
    )


class RemittanceTransferJournalPostBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    posting_review_token: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_journal_entry_id: UUID
    expected_source_event_key: str = Field(min_length=1, max_length=200)
    expected_draft_review_token: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_amount: Decimal = Field(gt=0)
    posting_policy_version: Literal["remittance_transfer_journal_posting_v1"] = (
        "remittance_transfer_journal_posting_v1"
    )


class RemittanceTransferJournalReverseBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reversal_posting_date: date
    reason: str = Field(min_length=3, max_length=500)


def remittance_transfer_journal_repository_dependency(
) -> PostgresRemittanceTransferJournalRepository:
    return PostgresRemittanceTransferJournalRepository()


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


def _raise_journal_error(error: RemittanceTransferJournalError) -> None:
    if isinstance(error, RemittanceTransferJournalNotFound):
        status_code = 404
    elif isinstance(error, RemittanceTransferJournalConflict):
        status_code = 409
    elif isinstance(error, RemittanceTransferJournalInvalid):
        status_code = 422
    else:
        status_code = 409
    raise HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    ) from error


def _payload(record: RemittanceTransferJournalStatusRecord) -> dict[str, object]:
    return {
        "preparation_id": str(record.preparation_id),
        "remittance_id": str(record.remittance_id),
        "transfer_evidence_id": str(record.transfer_evidence_id),
        "journal_entry_id": str(record.journal_entry_id),
        "source_event_key": record.source_event_key,
        "draft_review_token": record.draft_review_token,
        "posting_date": record.posting_date.isoformat(),
        "fiscal_period_id": str(record.fiscal_period_id),
        "debit_account_id": str(record.debit_account_id),
        "debit_account_system_key": record.debit_account_system_key,
        "credit_account_id": str(record.credit_account_id),
        "credit_account_system_key": record.credit_account_system_key,
        "amount": format(record.amount, "f"),
        "journal_status": record.journal_status,
        "entry_number": record.entry_number,
        "posting_id": str(record.posting_id) if record.posting_id else None,
        "posting_review_token": record.posting_review_token,
        "posted_by_user_id": (
            str(record.posted_by_user_id) if record.posted_by_user_id else None
        ),
        "posted_at": record.posted_at.isoformat() if record.posted_at else None,
        "reversal_id": str(record.reversal_id) if record.reversal_id else None,
        "reversal_journal_entry_id": (
            str(record.reversal_journal_entry_id)
            if record.reversal_journal_entry_id
            else None
        ),
        "reversal_entry_number": record.reversal_entry_number,
        "reversal_posting_date": (
            record.reversal_posting_date.isoformat()
            if record.reversal_posting_date
            else None
        ),
        "reversal_reason": record.reversal_reason,
        "posting_ready": record.posting_ready,
        "posted_audit_exact": record.posted_audit_exact,
        "reversal_audit_exact": record.reversal_audit_exact,
        "lifecycle_status": record.lifecycle_status,
        "income_recognition": record.income_recognition,
        "explicit_management_posting": record.explicit_management_posting,
        "automatic_source_posting": record.automatic_source_posting,
    }


def create_remittance_transfer_journal_router() -> APIRouter:
    router = APIRouter(tags=["management remittance transfer journals"])

    @router.get("/api/v1/management/accounting/remittance-transfers/journals/status")
    def list_status(
        limit: int = Query(default=100, ge=1, le=250),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRemittanceTransferJournalRepository = Depends(
            remittance_transfer_journal_repository_dependency
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
            records = repository.list_status(limit=limit)
        except RemittanceTransferJournalError as error:
            _raise_journal_error(error)
        return {
            "success": True,
            "data": {
                "income_recognition": False,
                "explicit_management_posting": True,
                "automatic_source_posting": False,
                "journals": [_payload(record) for record in records],
            },
        }

    @router.post("/api/v1/management/accounting/remittance-transfers/journals/prepare")
    def prepare(
        body: RemittanceTransferJournalPrepareBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRemittanceTransferJournalRepository = Depends(
            remittance_transfer_journal_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.remittance_transfer.journal.prepare",
            permission_error="Management remittance-transfer journal preparation permission is required.",
        )
        try:
            record = repository.prepare(
                actor_user_id=actor.user_id,
                remittance_id=body.remittance_id,
                review_token=body.review_token.lower(),
                transfer_evidence_id=body.transfer_evidence_id,
                source_event_key=body.source_event_key,
                posting_date=body.posting_date,
                debit_account_system_key=body.debit_account_system_key,
                credit_account_system_key=body.credit_account_system_key,
                amount=body.amount,
                coordinate_policy_version=body.coordinate_policy_version,
                draft_policy_version=body.draft_policy_version,
            )
        except RemittanceTransferJournalError as error:
            _raise_journal_error(error)
        return {"success": True, "data": _payload(record)}

    @router.post(
        "/api/v1/management/accounting/remittance-transfers/journals/{preparation_id}/post"
    )
    def post(
        preparation_id: UUID,
        body: RemittanceTransferJournalPostBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRemittanceTransferJournalRepository = Depends(
            remittance_transfer_journal_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.remittance_transfer.journal.post",
            permission_error="Management remittance-transfer journal posting permission is required.",
        )
        try:
            record = repository.post(
                actor_user_id=actor.user_id,
                preparation_id=preparation_id,
                posting_review_token=body.posting_review_token.lower(),
                expected_journal_entry_id=body.expected_journal_entry_id,
                expected_source_event_key=body.expected_source_event_key,
                expected_draft_review_token=body.expected_draft_review_token.lower(),
                expected_amount=body.expected_amount,
                posting_policy_version=body.posting_policy_version,
            )
        except RemittanceTransferJournalError as error:
            _raise_journal_error(error)
        return {"success": True, "data": _payload(record)}

    @router.post(
        "/api/v1/management/accounting/remittance-transfers/journals/postings/{posting_id}/reverse"
    )
    def reverse(
        posting_id: UUID,
        body: RemittanceTransferJournalReverseBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRemittanceTransferJournalRepository = Depends(
            remittance_transfer_journal_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.remittance_transfer.journal.reverse",
            permission_error="Management remittance-transfer journal reversal permission is required.",
        )
        try:
            record = repository.reverse(
                actor_user_id=actor.user_id,
                posting_id=posting_id,
                reversal_posting_date=body.reversal_posting_date,
                reason=body.reason,
            )
        except RemittanceTransferJournalError as error:
            _raise_journal_error(error)
        return {"success": True, "data": _payload(record)}

    return router