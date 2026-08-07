from __future__ import annotations

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .management_operations_repository import (
    ManagementOperationAudit,
    ManagementOperationEntry,
    ManagementOperationsOverview,
    ManagementOperationsSummary,
    PostgresManagementOperationsRepository,
)
from .request_auth import authenticated_device_context


def management_operations_repository_dependency() -> (
    PostgresManagementOperationsRepository
):
    return PostgresManagementOperationsRepository()


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _summary_payload(summary: ManagementOperationsSummary) -> dict[str, object]:
    return {
        "latest_collection_date": (
            summary.latest_collection_date.isoformat()
            if summary.latest_collection_date
            else None
        ),
        "latest_day_amount": _decimal(summary.latest_day_amount),
        "latest_day_payment_count": summary.latest_day_payment_count,
        "latest_day_unable_to_pay_count": summary.latest_day_unable_to_pay_count,
        "unremitted_amount": _decimal(summary.unremitted_amount),
        "unremitted_entry_count": summary.unremitted_entry_count,
        "pending_remittance_amount": _decimal(summary.pending_remittance_amount),
        "pending_remittance_count": summary.pending_remittance_count,
        "received_remittance_amount": _decimal(summary.received_remittance_amount),
        "received_remittance_count": summary.received_remittance_count,
        "correction_count": summary.correction_count,
        "void_count": summary.void_count,
    }


def _entry_payload(entry: ManagementOperationEntry) -> dict[str, object]:
    return {
        "transaction_id": str(entry.transaction_id),
        "receipt_number": entry.receipt_number,
        "collection_date": entry.collection_date.isoformat(),
        "accepted_at": entry.accepted_at.isoformat(),
        "client_code": entry.client_code,
        "client_name": entry.client_name,
        "loan_number": entry.loan_number,
        "loan_type_name": entry.loan_type_name,
        "collector_name": entry.collector_name,
        "entry_type": entry.entry_type,
        "amount": _decimal(entry.amount),
        "official_balance": _decimal(entry.official_balance),
        "covered_dates": [value.isoformat() for value in entry.covered_dates],
        "edit_version": entry.edit_version,
        "status": entry.status,
        "remittance_number": entry.remittance_number,
        "void_reason": entry.void_reason,
    }


def _audit_payload(event: ManagementOperationAudit) -> dict[str, object]:
    return {
        "event_id": str(event.event_id),
        "event_type": event.event_type,
        "happened_at": event.happened_at.isoformat(),
        "transaction_id": str(event.transaction_id),
        "receipt_number": event.receipt_number,
        "client_name": event.client_name,
        "loan_number": event.loan_number,
        "actor_name": event.actor_name,
        "reason": event.reason,
    }


def _overview_payload(overview: ManagementOperationsOverview) -> dict[str, object]:
    return {
        "summary": _summary_payload(overview.summary),
        "entries": [_entry_payload(item) for item in overview.entries],
        "audits": [_audit_payload(item) for item in overview.audits],
        "notice": (
            "Loan Operations is a read-only monitoring view. Use the dedicated "
            "Direct Payment Entry, correction, remittance, and void workflows for "
            "authorized changes."
        ),
    }


def create_management_operations_router() -> APIRouter:
    router = APIRouter(tags=["management loan operations"])

    @router.get("/api/v1/management/loan-operations")
    @router.get(
        "/api/mobile/v1/management/loan-operations",
        include_in_schema=False,
    )
    def management_loan_operations(
        q: str = Query(default="", max_length=120),
        entry_status: Literal[
            "all", "unremitted", "submitted", "received", "voided"
        ] = Query(default="all", alias="status"),
        limit: int = Query(default=100, ge=1, le=200),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        operations: PostgresManagementOperationsRepository = Depends(
            management_operations_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        if "management" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "management_role_required",
                    "message": "Management access is required for Loan Operations.",
                },
            )
        overview = operations.load_overview(
            query=q,
            status=entry_status,
            limit=limit,
        )
        return {"success": True, "data": _overview_payload(overview)}

    return router
