from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .cross_collection_status_repository import (
    CrossCollectionStatusRecord,
    PostgresCrossCollectionStatusRepository,
)
from .cross_remittance_repository import (
    CrossRemittanceTargetRecord,
    PostgresCrossRemittanceRepository,
)
from .remittance_repository import (
    RemittanceEmpty,
    RemittanceError,
    RemittanceItemRecord,
    RemittanceRecipientInvalid,
    RemittanceRecord,
    RemittanceSummaryRecord,
)
from .request_auth import authenticated_device_context


class CrossRemittanceSubmissionBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    recipient_user_id: UUID
    collection_date: date
    note: str = Field(default="", max_length=500)


def cross_remittance_repository_dependency() -> PostgresCrossRemittanceRepository:
    return PostgresCrossRemittanceRepository()


def cross_collection_status_repository_dependency() -> PostgresCrossCollectionStatusRepository:
    return PostgresCrossCollectionStatusRepository()


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _target_payload(record: CrossRemittanceTargetRecord) -> dict[str, object]:
    return {
        "recipient_user_id": str(record.recipient_user_id),
        "recipient_name": record.recipient_name,
        "role_name": "Assigned Collector",
        "transaction_count": record.transaction_count,
        "client_count": record.client_count,
        "total_amount": _money(record.total_amount),
    }


def _cross_collection_status_payload(
    record: CrossCollectionStatusRecord,
) -> dict[str, object]:
    return {
        "transaction_id": str(record.transaction_id),
        "receipt_number": record.receipt_number,
        "client_id": str(record.client_id),
        "client_name": record.client_name,
        "loan_id": str(record.loan_id),
        "loan_type": record.loan_type,
        "area": record.area,
        "assigned_collector_user_id": (
            str(record.assigned_collector_user_id)
            if record.assigned_collector_user_id
            else None
        ),
        "assigned_collector_name": record.assigned_collector_name,
        "collection_date": record.collection_date.isoformat(),
        "entry_type": record.entry_type,
        "amount": _money(record.amount),
        "accepted_at": record.accepted_at.isoformat(),
        "is_locked": record.is_locked,
        "remittance_id": (
            str(record.remittance_id) if record.remittance_id else None
        ),
        "remittance_number": record.remittance_number,
        "custody_status": record.custody_status,
        "remittance_recipient_user_id": (
            str(record.remittance_recipient_user_id)
            if record.remittance_recipient_user_id
            else None
        ),
        "remittance_recipient_name": record.remittance_recipient_name,
        "submitted_at": (
            record.submitted_at.isoformat() if record.submitted_at else None
        ),
        "received_at": (
            record.received_at.isoformat() if record.received_at else None
        ),
    }


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
        "recipient_role": "Assigned Collector",
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
        "acceptance_message": (
            "The assigned collector must review and accept this remittance. "
            "Acceptance copies the payment into their route view without creating "
            "another transaction."
        ),
    }


def _raise_error(error: RemittanceError) -> None:
    status = 422 if isinstance(error, RemittanceRecipientInvalid) else 409
    if isinstance(error, RemittanceEmpty):
        status = 409
    raise HTTPException(
        status_code=status,
        detail={"code": error.code, "message": str(error)},
    ) from error


def create_cross_remittance_router() -> APIRouter:
    router = APIRouter(tags=["cross collector remittances"])

    @router.get("/api/v1/collector/cross-remittances/history")
    @router.get(
        "/api/mobile/v1/collector/cross-remittances/history",
        include_in_schema=False,
    )
    def collection_history(
        collection_date: date | None = Query(default=None),
        limit: int = Query(default=500, ge=1, le=1000),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        statuses: PostgresCrossCollectionStatusRepository = Depends(
            cross_collection_status_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="remittance.view",
            permission_error="Remittance viewing permission is required.",
        )
        if "collector" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail="Only an active Collector may view their other-area collections.",
            )
        records = statuses.list_for_collector(
            collector_user_id=actor.user_id,
            collection_date=collection_date,
            limit=limit,
        )
        return {
            "success": True,
            "data": [_cross_collection_status_payload(record) for record in records],
        }

    @router.get("/api/v1/collector/cross-remittances/targets")
    @router.get(
        "/api/mobile/v1/collector/cross-remittances/targets",
        include_in_schema=False,
    )
    def list_targets(
        collection_date: date = Query(),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        remittances: PostgresCrossRemittanceRepository = Depends(
            cross_remittance_repository_dependency
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
        records = remittances.list_targets(
            collector_user_id=actor.user_id,
            collection_date=collection_date,
        )
        return {
            "success": True,
            "data": [_target_payload(record) for record in records],
        }

    @router.get("/api/v1/collector/cross-remittances/preview")
    @router.get(
        "/api/mobile/v1/collector/cross-remittances/preview",
        include_in_schema=False,
    )
    def preview(
        recipient_user_id: UUID = Query(),
        collection_date: date = Query(),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        remittances: PostgresCrossRemittanceRepository = Depends(
            cross_remittance_repository_dependency
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
            summary = remittances.preview(
                collector_user_id=actor.user_id,
                recipient_user_id=recipient_user_id,
                collection_date=collection_date,
            )
        except RemittanceError as error:
            _raise_error(error)
        return {"success": True, "data": _summary_payload(summary)}

    @router.post("/api/v1/collector/cross-remittances", status_code=201)
    @router.post(
        "/api/mobile/v1/collector/cross-remittances",
        status_code=201,
        include_in_schema=False,
    )
    def submit(
        body: CrossRemittanceSubmissionBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        remittances: PostgresCrossRemittanceRepository = Depends(
            cross_remittance_repository_dependency
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
            _raise_error(error)
        return {"success": True, "data": _record_payload(record)}

    return router
