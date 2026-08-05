from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .client_payment_repository import (
    ClientPaymentBorrowerNotLinked,
    ClientPaymentRecord,
    ClientPaymentTimeline,
    PostgresClientPaymentRepository,
)
from .request_auth import authenticated_device_context


def client_payment_repository_dependency() -> PostgresClientPaymentRepository:
    return PostgresClientPaymentRepository()


def _decimal(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def _payment_payload(record: ClientPaymentRecord) -> dict[str, object]:
    return {
        "transaction_id": str(record.transaction_id),
        "receipt_number": record.receipt_number,
        "loan_id": str(record.loan_id),
        "loan_number": record.loan_number,
        "loan_type_name": record.loan_type_name,
        "collector_name": record.collector_name,
        "collection_date": record.collection_date.isoformat(),
        "recorded_at": record.recorded_at.isoformat(),
        "entry_type": record.entry_type,
        "amount": _decimal(record.amount),
        "covered_dates": [value.isoformat() for value in record.covered_dates],
        "previous_balance": _decimal(record.previous_balance),
        "official_balance": _decimal(record.official_balance),
        "note": record.note,
        "collection_origin": record.collection_origin,
        "status": record.status,
        "is_voided": record.is_voided,
        "voided_at": (
            record.voided_at.isoformat() if record.voided_at else None
        ),
        "void_reason": record.void_reason,
        "edit_version": record.edit_version,
        "remittance_number": record.remittance_number,
        "remittance_status": record.remittance_status,
        "remittance_submitted_at": (
            record.remittance_submitted_at.isoformat()
            if record.remittance_submitted_at
            else None
        ),
        "remittance_received_at": (
            record.remittance_received_at.isoformat()
            if record.remittance_received_at
            else None
        ),
    }


def _timeline_payload(timeline: ClientPaymentTimeline) -> dict[str, object]:
    return {
        "client": {
            "client_id": str(timeline.client_id),
            "client_code": timeline.client_code,
            "client_name": timeline.client_name,
        },
        "payments": [_payment_payload(record) for record in timeline.payments],
        "payment_proof": {
            "upload_available": False,
            "message": (
                "Collector-recorded payments use official SPINA receipts. "
                "Client payment-proof upload is not connected to mobile yet."
            ),
        },
    }


def create_client_payment_router() -> APIRouter:
    router = APIRouter(tags=["client payments"])

    @router.get("/api/v1/client/payments")
    @router.get("/api/mobile/v1/client/payments", include_in_schema=False)
    def list_client_payments(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        payments: PostgresClientPaymentRepository = Depends(
            client_payment_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        if "client" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "client_role_required",
                    "message": "Only a linked client account can view Payments.",
                },
            )
        try:
            timeline = payments.list_for_user(user_id=actor.user_id)
        except ClientPaymentBorrowerNotLinked as error:
            raise HTTPException(
                status_code=404,
                detail={"code": error.code, "message": str(error)},
            ) from error
        return {"success": True, "data": _timeline_payload(timeline)}

    return router
