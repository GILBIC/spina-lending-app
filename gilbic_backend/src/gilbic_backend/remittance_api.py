from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .remittance_repository import (
    PostgresRemittanceRepository,
    RemittanceAlreadyReceived,
    RemittanceEmpty,
    RemittanceError,
    RemittanceItemRecord,
    RemittanceNotFound,
    RemittanceRecipientInvalid,
    RemittanceRecord,
    RemittanceSummaryRecord,
)
from .request_auth import authenticated_device_context


class RemittanceSubmissionBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    recipient_user_id: UUID
    collection_date: date
    note: str = Field(default="", max_length=500)


def remittance_repository_dependency() -> PostgresRemittanceRepository:
    return PostgresRemittanceRepository()


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _item_payload(item: RemittanceItemRecord) -> dict[str, object]:
    return {
        "transaction_id": str(item.transaction_id),
        "client_id": str(item.client_id),
        "client_name": item.client_name,
        "loan_id": str(item.loan_id),
        "loan_type": item.loan_type,
        "collection_date": item.collection_date.isoformat(),
        "entry_type": item.entry_type,
        "amount": _money(item.amount),
        "receipt_number": item.receipt_number,
        "accepted_at": item.accepted_at.isoformat(),
        "note": item.note,
        "covered_dates": [value.isoformat() for value in item.covered_dates],
    }


def _summary_payload(summary: RemittanceSummaryRecord) -> dict[str, object]:
    return {
        "collection_date": summary.collection_date.isoformat(),
        "collector_user_id": str(summary.collector_user_id),
        "collector_name": summary.collector_name,
        "transaction_count": summary.transaction_count,
        "payment_count": summary.payment_count,
        "unable_to_pay_count": summary.unable_to_pay_count,
        "covered_payment_count": summary.covered_payment_count,
        "client_count": summary.client_count,
        "total_amount": _money(summary.total_amount),
        "items": [_item_payload(item) for item in summary.items],
    }


def _record_payload(record: RemittanceRecord) -> dict[str, object]:
    return {
        "remittance_id": str(record.remittance_id),
        "remittance_number": record.remittance_number,
        "collector_user_id": str(record.collector_user_id),
        "collector_name": record.collector_name,
        "recipient_user_id": str(record.recipient_user_id),
        "recipient_name": record.recipient_name,
        "collection_date": record.collection_date.isoformat(),
        "status": record.status,
        "transaction_count": record.transaction_count,
        "payment_count": record.payment_count,
        "unable_to_pay_count": record.unable_to_pay_count,
        "covered_payment_count": record.covered_payment_count,
        "client_count": record.client_count,
        "total_amount": _money(record.total_amount),
        "note": record.note,
        "submitted_at": record.submitted_at.isoformat(),
        "received_at": record.received_at.isoformat() if record.received_at else None,
        "items": [_item_payload(item) for item in record.items],
    }


def _raise_remittance_error(error: RemittanceError) -> None:
    if isinstance(error, RemittanceNotFound):
        status = 404
    elif isinstance(error, (RemittanceEmpty, RemittanceAlreadyReceived)):
        status = 409
    elif isinstance(error, RemittanceRecipientInvalid):
        status = 422
    else:
        status = 409
    raise HTTPException(
        status_code=status,
        detail={"code": error.code, "message": str(error)},
    ) from error


def create_remittance_router() -> APIRouter:
    router = APIRouter(tags=["collection remittances"])

    @router.get("/api/v1/collector/remittances/recipients")
    @router.get(
        "/api/mobile/v1/collector/remittances/recipients",
        include_in_schema=False,
    )
    def recipients(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        remittances: PostgresRemittanceRepository = Depends(
            remittance_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="remittance.create",
            permission_error="Remittance creation permission is required.",
        )
        records = remittances.list_recipients(actor_user_id=actor.user_id)
        return {
            "success": True,
            "data": [
                {
                    "user_id": str(record.user_id),
                    "full_name": record.full_name,
                    "role_name": record.role_name,
                }
                for record in records
            ],
        }

    @router.get("/api/v1/collector/remittances/preview")
    @router.get(
        "/api/mobile/v1/collector/remittances/preview",
        include_in_schema=False,
    )
    def preview(
        collection_date: date = Query(),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        remittances: PostgresRemittanceRepository = Depends(
            remittance_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="remittance.create",
            permission_error="Remittance creation permission is required.",
        )
        summary = remittances.preview(
            collector_user_id=actor.user_id,
            collection_date=collection_date,
        )
        return {"success": True, "data": _summary_payload(summary)}

    @router.post("/api/v1/collector/remittances", status_code=201)
    @router.post(
        "/api/mobile/v1/collector/remittances",
        status_code=201,
        include_in_schema=False,
    )
    def submit(
        body: RemittanceSubmissionBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        remittances: PostgresRemittanceRepository = Depends(
            remittance_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="remittance.create",
            permission_error="Remittance creation permission is required.",
        )
        try:
            record = remittances.submit(
                collector_user_id=actor.user_id,
                recipient_user_id=body.recipient_user_id,
                collection_date=body.collection_date,
                note=body.note,
            )
        except RemittanceError as error:
            _raise_remittance_error(error)
        return {"success": True, "data": _record_payload(record)}

    @router.get("/api/v1/remittances")
    @router.get("/api/mobile/v1/remittances", include_in_schema=False)
    def history(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        remittances: PostgresRemittanceRepository = Depends(
            remittance_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="remittance.view",
            permission_error="Remittance view permission is required.",
        )
        records = remittances.list_for_user(actor_user_id=actor.user_id)
        return {
            "success": True,
            "data": [_record_payload(record) for record in records],
        }

    @router.post("/api/v1/remittances/{remittance_id}/receive")
    @router.post(
        "/api/mobile/v1/remittances/{remittance_id}/receive",
        include_in_schema=False,
    )
    def receive(
        remittance_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        remittances: PostgresRemittanceRepository = Depends(
            remittance_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="remittance.receive",
            permission_error="Remittance receiving permission is required.",
        )
        try:
            record = remittances.confirm_received(
                remittance_id=remittance_id,
                recipient_user_id=actor.user_id,
            )
        except RemittanceError as error:
            _raise_remittance_error(error)
        return {"success": True, "data": _record_payload(record)}

    return router
