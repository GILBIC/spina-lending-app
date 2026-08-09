from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .eir_cash_allocation import EirAllocationResult, EirCashAllocation
from .eir_cash_allocation_repository import (
    EirCashAllocationLoanNotFound,
    EirCashAllocationPack,
    PostgresEirCashAllocationRepository,
)
from .request_auth import authenticated_device_context


def eir_cash_allocation_repository_dependency() -> PostgresEirCashAllocationRepository:
    return PostgresEirCashAllocationRepository()


def _money(value: Decimal | None) -> str | None:
    return format(value, ".2f") if value is not None else None


def _allocation_item_payload(item: EirCashAllocation) -> dict[str, object]:
    return {
        "transaction_id": str(item.transaction_id),
        "source_event_key": item.source_event_key,
        "collection_date": item.collection_date.isoformat(),
        "amount": _money(item.amount),
        "effective_interest_accrued_since_prior_event": _money(
            item.effective_interest_accrued_since_prior_event
        ),
        "gross_carrying_before": _money(item.gross_carrying_before),
        "accrued_interest_before": _money(item.accrued_interest_before),
        "loan_component_before": _money(item.loan_component_before),
        "cash_to_accrued_interest": _money(item.cash_to_accrued_interest),
        "cash_to_loan_component": _money(item.cash_to_loan_component),
        "gross_carrying_after": _money(item.gross_carrying_after),
        "accrued_interest_after": _money(item.accrued_interest_after),
        "loan_component_after": _money(item.loan_component_after),
        "posting_eligible": item.posting_eligible,
        "disposition": item.disposition,
        "message": item.message,
    }


def _result_payload(result: EirAllocationResult) -> dict[str, object]:
    return {
        "status": result.status,
        "message": result.message,
        "calculation_mode": result.calculation_mode,
        "cutover_date": result.cutover_date.isoformat(),
        "due_date": result.due_date.isoformat(),
        "daily_eir": str(result.daily_eir) if result.daily_eir is not None else None,
        "opening_gross_carrying_amount": _money(
            result.opening_gross_carrying_amount
        ),
        "opening_accrued_interest_component": _money(
            result.opening_accrued_interest_component
        ),
        "opening_loan_component": _money(result.opening_loan_component),
        "total_effective_interest_accrued": _money(
            result.total_effective_interest_accrued
        ),
        "closing_gross_carrying_amount": _money(
            result.closing_gross_carrying_amount
        ),
        "closing_accrued_interest_component": _money(
            result.closing_accrued_interest_component
        ),
        "closing_loan_component": _money(result.closing_loan_component),
        "posting_eligible": result.posting_eligible,
        "allocations": [
            _allocation_item_payload(item) for item in result.allocations
        ],
    }


def _pack_payload(pack: EirCashAllocationPack) -> dict[str, object]:
    return {
        "loan_id": str(pack.loan_id),
        "loan_number": pack.loan_number,
        "client_name": pack.client_name,
        "cutover_date": (
            pack.cutover_date.isoformat() if pack.cutover_date is not None else None
        ),
        "opening_balance_posted": pack.opening_balance_posted,
        "opening_balance_entry_number": pack.opening_balance_entry_number,
        "source_event_count": pack.source_event_count,
        "source_history_complete": pack.source_history_complete,
        "blocker_code": pack.blocker_code,
        "blocker_message": pack.blocker_message,
        "automatic_source_posting_enabled": pack.automatic_source_posting_enabled,
        "allocation": (
            _result_payload(pack.allocation) if pack.allocation is not None else None
        ),
        "notice": (
            "Read-only event-date EIR cash allocation reference. Regular cash is split between accrued effective interest and the loan component using the measured cutover EIR roll-forward. No journal draft or posted entry is created. EIR accrual posting, 7x7 modification policy, post-maturity treatment, fiscal-period controls, and automatic source posting remain separate protected stages."
        ),
    }


def create_eir_cash_allocation_router() -> APIRouter:
    router = APIRouter(tags=["management EIR cash allocation"])

    @router.get(
        "/api/v1/management/financial-accounting/eir-cash-allocation/{loan_id}"
    )
    @router.get(
        "/api/mobile/v1/management/financial-accounting/eir-cash-allocation/{loan_id}",
        include_in_schema=False,
    )
    def eir_cash_allocation(
        loan_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresEirCashAllocationRepository = Depends(
            eir_cash_allocation_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.view",
            permission_error="Financial Accounting view permission is required.",
        )
        if "management" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "management_role_required",
                    "message": "Management access is required for EIR cash allocation.",
                },
            )
        try:
            pack = repository.load_loan_allocation(loan_id=loan_id)
        except EirCashAllocationLoanNotFound as error:
            raise HTTPException(
                status_code=404,
                detail={"code": error.code, "message": str(error)},
            ) from error
        return {"success": True, "data": {"eir_cash_allocation": _pack_payload(pack)}}

    return router
