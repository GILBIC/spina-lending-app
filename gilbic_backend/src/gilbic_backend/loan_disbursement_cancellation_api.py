from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .loan_disbursement_cancellation_repository import (
    LoanDisbursementCancellationConflict,
    LoanDisbursementCancellationError,
    LoanDisbursementCancellationNotFound,
    LoanDisbursementCancellationStatus,
    LoanDisbursementCancellationValidation,
    PostgresLoanDisbursementCancellationRepository,
)
from .request_auth import authenticated_device_context


class CancelLoanDisbursementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = False
    cancellation_review_token: str = Field(min_length=64, max_length=64)
    posting_id: UUID
    original_journal_entry_id: UUID
    original_entry_number: str = Field(min_length=1, max_length=100)
    original_source_event_key: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(gt=0, decimal_places=2)
    original_debit_account_system_key: str = Field(min_length=1, max_length=100)
    original_credit_account_system_key: str = Field(min_length=1, max_length=100)
    reversal_posting_date: date
    reason: str = Field(min_length=3, max_length=500)


def loan_disbursement_cancellation_repository_dependency() -> (
    PostgresLoanDisbursementCancellationRepository
):
    return PostgresLoanDisbursementCancellationRepository()


def _money(value: Decimal) -> str:
    return format(value, ".2f")


def _payload(item: LoanDisbursementCancellationStatus) -> dict[str, object]:
    return {
        "posting_id": str(item.posting_id),
        "preparation_id": str(item.preparation_id),
        "disbursement_event_id": str(item.disbursement_event_id),
        "loan_id": str(item.loan_id),
        "client_id": str(item.client_id),
        "original_journal_entry_id": str(item.original_journal_entry_id),
        "original_entry_number": item.original_entry_number,
        "original_source_event_key": item.original_source_event_key,
        "posting_review_token": item.posting_review_token,
        "amount": _money(item.amount),
        "original_debit_account_system_key": item.original_debit_account_system_key,
        "original_credit_account_system_key": item.original_credit_account_system_key,
        "original_journal_status": item.original_journal_status,
        "cancellation_review_token": item.cancellation_review_token,
        "cancellation_ready": item.cancellation_ready,
        "cancellation_id": None if item.cancellation_id is None else str(item.cancellation_id),
        "cancellation_source_key": item.cancellation_source_key,
        "reversal_posting_date": (
            None
            if item.reversal_posting_date is None
            else item.reversal_posting_date.isoformat()
        ),
        "cancellation_reason": item.cancellation_reason,
        "cancelled_by_user_id": (
            None
            if item.cancelled_by_user_id is None
            else str(item.cancelled_by_user_id)
        ),
        "cancelled_at": None if item.cancelled_at is None else item.cancelled_at.isoformat(),
        "reversal_id": None if item.reversal_id is None else str(item.reversal_id),
        "reversal_journal_entry_id": (
            None
            if item.reversal_journal_entry_id is None
            else str(item.reversal_journal_entry_id)
        ),
        "reversal_entry_number": item.reversal_entry_number,
        "reversal_source_event_key": item.reversal_source_event_key,
        "reversal_journal_status": item.reversal_journal_status,
        "cancelled": item.cancelled,
        "cancelled_reversal_audit_exact": item.cancelled_reversal_audit_exact,
        "protected_reversal_enabled": item.protected_reversal_enabled,
        "automatic_source_posting_enabled": item.automatic_source_posting_enabled,
        "notice": (
            "This new-loan disbursement was cancelled through the protected Stage 5D.23 workflow. The original posted journal and Stage 5D.22 posting audit remain immutable; the separate posted reversing journal is the accounting correction."
            if item.cancelled
            else "Cancellation is an explicit Management action. Confirm the exact posted disbursement identity and choose an open reversal posting date with a clear reason. The protected workflow preserves original history and posts a separate exact reversing journal; automatic source posting remains disabled."
        ),
    }


def _exception(error: LoanDisbursementCancellationError) -> HTTPException:
    if isinstance(error, LoanDisbursementCancellationNotFound):
        status_code = 404
    elif isinstance(error, LoanDisbursementCancellationConflict):
        status_code = 409
    elif isinstance(error, LoanDisbursementCancellationValidation):
        status_code = 422
    else:
        status_code = 500
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    )


def _confirmation_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "code": "loan_disbursement_cancellation_confirmation_mismatch",
            "message": message,
        },
    )


def _assert_confirmation(
    body: CancelLoanDisbursementRequest,
    current: LoanDisbursementCancellationStatus,
) -> None:
    checks = (
        (
            body.cancellation_review_token == current.cancellation_review_token,
            "cancellation review token",
        ),
        (body.posting_id == current.posting_id, "posting identity"),
        (
            body.original_journal_entry_id == current.original_journal_entry_id,
            "original journal identity",
        ),
        (body.original_entry_number == current.original_entry_number, "original entry number"),
        (
            body.original_source_event_key == current.original_source_event_key,
            "original source-event identity",
        ),
        (body.amount == current.amount, "amount"),
        (
            body.original_debit_account_system_key
            == current.original_debit_account_system_key,
            "original debit account",
        ),
        (
            body.original_credit_account_system_key
            == current.original_credit_account_system_key,
            "original funding cash account",
        ),
    )
    mismatch = next((label for ok, label in checks if not ok), None)
    if mismatch is not None:
        raise _confirmation_error(
            f"The confirmed {mismatch} does not match the protected cancellation review. Refresh before continuing."
        )


def create_loan_disbursement_cancellation_router() -> APIRouter:
    router = APIRouter(tags=["management protected loan-disbursement cancellation"])

    def actor_context(
        *,
        authorization: str | None,
        x_device_id: str | None,
        auth: SupabaseAuthClient,
        accounts: PostgresAccountRepository,
        permission: str,
        permission_error: str,
    ):
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
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
                    "message": "Management access is required for protected new-loan disbursement cancellation/reversal.",
                },
            )
        return actor

    @router.get(
        "/api/v1/management/accounting/loan-disbursements/{disbursement_event_id}/journal-cancellation"
    )
    @router.get(
        "/api/mobile/v1/management/accounting/loan-disbursements/{disbursement_event_id}/journal-cancellation",
        include_in_schema=False,
    )
    def loan_disbursement_cancellation_status(
        disbursement_event_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresLoanDisbursementCancellationRepository = Depends(
            loan_disbursement_cancellation_repository_dependency
        ),
    ) -> dict[str, object]:
        actor_context(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.view",
            permission_error="Financial Accounting view permission is required.",
        )
        try:
            item = repository.load_status(disbursement_event_id=disbursement_event_id)
        except LoanDisbursementCancellationError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"loan_disbursement_cancellation": _payload(item)}}

    @router.post(
        "/api/v1/management/accounting/loan-disbursements/{disbursement_event_id}/journal-cancellation"
    )
    @router.post(
        "/api/mobile/v1/management/accounting/loan-disbursements/{disbursement_event_id}/journal-cancellation",
        include_in_schema=False,
    )
    def cancel_loan_disbursement(
        disbursement_event_id: UUID,
        body: CancelLoanDisbursementRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresLoanDisbursementCancellationRepository = Depends(
            loan_disbursement_cancellation_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = actor_context(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.loan_disbursement.journal.reverse",
            permission_error="Protected new-loan disbursement cancellation/reversal permission is required.",
        )
        if body.confirm is not True:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "loan_disbursement_cancellation_confirmation_required",
                    "message": "Explicit Management confirmation is required before cancelling and reversing a posted new-loan disbursement.",
                },
            )

        try:
            current = repository.load_status(disbursement_event_id=disbursement_event_id)
            _assert_confirmation(body, current)
            if not current.cancellation_ready and not current.cancelled:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "loan_disbursement_cancellation_not_ready",
                        "message": "Protected new-loan disbursement posting is not ready for controlled cancellation/reversal.",
                    },
                )
            item = repository.reverse(
                actor_user_id=actor.user_id,
                disbursement_event_id=disbursement_event_id,
                expected_cancellation_review_token=body.cancellation_review_token,
                reversal_posting_date=body.reversal_posting_date,
                reason=body.reason,
            )
        except LoanDisbursementCancellationError as error:
            raise _exception(error) from error

        return {"success": True, "data": {"loan_disbursement_cancellation": _payload(item)}}

    return router
