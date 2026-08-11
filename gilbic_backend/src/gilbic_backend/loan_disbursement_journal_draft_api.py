from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .loan_disbursement_journal_draft_repository import (
    LoanDisbursementJournalDraftConflict,
    LoanDisbursementJournalDraftError,
    LoanDisbursementJournalDraftNotFound,
    LoanDisbursementJournalDraftReview,
    LoanDisbursementJournalDraftStatus,
    LoanDisbursementJournalDraftValidation,
    PostgresLoanDisbursementJournalDraftRepository,
)
from .request_auth import authenticated_device_context


class PrepareLoanDisbursementJournalDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = False
    review_token: str = Field(min_length=64, max_length=64)
    source_event_key: str = Field(min_length=1, max_length=200)
    posting_date: date
    amount: Decimal = Field(gt=0, decimal_places=2)
    debit_account_system_key: str = Field(min_length=1, max_length=100)
    credit_account_system_key: str = Field(min_length=1, max_length=100)
    total_debit: Decimal = Field(gt=0, decimal_places=2)
    total_credit: Decimal = Field(gt=0, decimal_places=2)


def loan_disbursement_journal_draft_repository_dependency() -> (
    PostgresLoanDisbursementJournalDraftRepository
):
    return PostgresLoanDisbursementJournalDraftRepository()


def _money(value: Decimal) -> str:
    return format(value, ".2f")


def _review_payload(item: LoanDisbursementJournalDraftReview) -> dict[str, object]:
    return {
        "disbursement_event_id": str(item.disbursement_event_id),
        "loan_id": str(item.loan_id),
        "loan_number": item.loan_number,
        "client_id": str(item.client_id),
        "client_code": item.client_code,
        "client_name": item.client_name,
        "external_reference": item.external_reference,
        "source_event_key": item.source_event_key,
        "posting_date": item.posting_date.isoformat(),
        "fiscal_period_id": str(item.fiscal_period_id),
        "debit_account_system_key": item.debit_account_system_key,
        "debit_amount": _money(item.debit_amount),
        "credit_account_system_key": item.credit_account_system_key,
        "credit_amount": _money(item.credit_amount),
        "total_debit": _money(item.debit_amount),
        "total_credit": _money(item.credit_amount),
        "initial_measurement_basis": item.initial_measurement_basis,
        "coordinate_policy_version": item.coordinate_policy_version,
        "draft_policy_version": item.draft_policy_version,
        "review_token": item.review_token,
        "posting_enabled": item.posting_enabled,
        "automatic_source_posting_enabled": item.automatic_source_posting_enabled,
        "notice": (
            "Confirm this exact source event, posting date, amount, debit account, "
            "funding cash account and balanced totals before creating a protected "
            "draft. The review token binds this exact current coordinate. Stage "
            "5D.21 creates a draft only and grants no posting permission."
        ),
    }


def _status_payload(item: LoanDisbursementJournalDraftStatus) -> dict[str, object]:
    return {
        "preparation_id": str(item.preparation_id),
        "disbursement_event_id": str(item.disbursement_event_id),
        "loan_id": str(item.loan_id),
        "client_id": str(item.client_id),
        "journal_entry_id": str(item.journal_entry_id),
        "journal_status": item.journal_status,
        "entry_number": item.entry_number,
        "source_event_key": item.source_event_key,
        "review_token": item.review_token,
        "coordinate_policy_version": item.coordinate_policy_version,
        "draft_policy_version": item.draft_policy_version,
        "posting_date": item.posting_date.isoformat(),
        "fiscal_period_id": str(item.fiscal_period_id),
        "fiscal_period_label": item.fiscal_period_label,
        "fiscal_period_status": item.fiscal_period_status,
        "amount": _money(item.amount),
        "debit_account_system_key": item.debit_account_system_key,
        "credit_account_system_key": item.credit_account_system_key,
        "line_count": item.line_count,
        "total_debit": _money(item.total_debit),
        "total_credit": _money(item.total_credit),
        "draft_integrity_ready": item.draft_integrity_ready,
        "prepared_by_user_id": str(item.prepared_by_user_id),
        "prepared_at": item.prepared_at.isoformat(),
        "posting_enabled": item.posting_enabled,
        "automatic_source_posting_enabled": item.automatic_source_posting_enabled,
        "notice": (
            "This is a protected system-generated Stage 5D.21 draft. It cannot "
            "be edited, deleted or posted through the manual General Journal. "
            "Protected disbursement posting remains a later stage."
        ),
    }


def _exception(error: LoanDisbursementJournalDraftError) -> HTTPException:
    if isinstance(error, LoanDisbursementJournalDraftNotFound):
        status_code = 404
    elif isinstance(error, LoanDisbursementJournalDraftConflict):
        status_code = 409
    elif isinstance(error, LoanDisbursementJournalDraftValidation):
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
            "code": "loan_disbursement_journal_draft_confirmation_mismatch",
            "message": message,
        },
    )


def _assert_review_confirmation(
    body: PrepareLoanDisbursementJournalDraftRequest,
    review: LoanDisbursementJournalDraftReview,
) -> None:
    if body.review_token != review.review_token:
        raise _confirmation_error(
            "The reviewed coordinate token changed. Refresh before preparing the draft."
        )
    if body.source_event_key != review.source_event_key:
        raise _confirmation_error("The confirmed source-event identity does not match the review.")
    if body.posting_date != review.posting_date:
        raise _confirmation_error("The confirmed posting date does not match the review.")
    if body.amount != review.debit_amount or body.amount != review.credit_amount:
        raise _confirmation_error("The confirmed disbursement amount does not match the review.")
    if body.debit_account_system_key != review.debit_account_system_key:
        raise _confirmation_error("The confirmed debit account does not match the review.")
    if body.credit_account_system_key != review.credit_account_system_key:
        raise _confirmation_error("The confirmed funding cash account does not match the review.")
    if body.total_debit != review.debit_amount or body.total_credit != review.credit_amount:
        raise _confirmation_error("The confirmed debit/credit totals do not match the reviewed balanced coordinate.")


def _assert_existing_confirmation(
    body: PrepareLoanDisbursementJournalDraftRequest,
    item: LoanDisbursementJournalDraftStatus,
) -> None:
    if body.review_token != item.review_token:
        raise _confirmation_error("The existing protected draft has a different review token.")
    if body.source_event_key != item.source_event_key:
        raise _confirmation_error("The existing protected draft has a different source-event identity.")
    if body.posting_date != item.posting_date:
        raise _confirmation_error("The existing protected draft has a different posting date.")
    if body.amount != item.amount:
        raise _confirmation_error("The existing protected draft has a different amount.")
    if body.debit_account_system_key != item.debit_account_system_key:
        raise _confirmation_error("The existing protected draft has a different debit account.")
    if body.credit_account_system_key != item.credit_account_system_key:
        raise _confirmation_error("The existing protected draft has a different funding account.")
    if body.total_debit != item.total_debit or body.total_credit != item.total_credit:
        raise _confirmation_error("The existing protected draft has different balanced totals.")


def create_loan_disbursement_journal_draft_router() -> APIRouter:
    router = APIRouter(tags=["management protected loan-disbursement journal drafts"])

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
                    "message": "Management access is required for protected new-loan disbursement journal draft controls.",
                },
            )
        return actor

    @router.get(
        "/api/v1/management/accounting/loan-disbursements/{disbursement_event_id}/journal-draft/review"
    )
    @router.get(
        "/api/mobile/v1/management/accounting/loan-disbursements/{disbursement_event_id}/journal-draft/review",
        include_in_schema=False,
    )
    def review_new_loan_disbursement_journal_draft(
        disbursement_event_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresLoanDisbursementJournalDraftRepository = Depends(
            loan_disbursement_journal_draft_repository_dependency
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
            review = repository.load_review(disbursement_event_id=disbursement_event_id)
        except LoanDisbursementJournalDraftError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"loan_disbursement_journal_draft_review": _review_payload(review)}}

    @router.get(
        "/api/v1/management/accounting/loan-disbursements/{disbursement_event_id}/journal-draft"
    )
    @router.get(
        "/api/mobile/v1/management/accounting/loan-disbursements/{disbursement_event_id}/journal-draft",
        include_in_schema=False,
    )
    def new_loan_disbursement_journal_draft_status(
        disbursement_event_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresLoanDisbursementJournalDraftRepository = Depends(
            loan_disbursement_journal_draft_repository_dependency
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
        except LoanDisbursementJournalDraftError as error:
            raise _exception(error) from error
        return {
            "success": True,
            "data": {
                "loan_disbursement_journal_draft": None if item is None else _status_payload(item),
                "posting_enabled": False,
                "automatic_source_posting_enabled": False,
            },
        }

    @router.post(
        "/api/v1/management/accounting/loan-disbursements/{disbursement_event_id}/journal-draft",
        status_code=status.HTTP_201_CREATED,
    )
    @router.post(
        "/api/mobile/v1/management/accounting/loan-disbursements/{disbursement_event_id}/journal-draft",
        status_code=status.HTTP_201_CREATED,
        include_in_schema=False,
    )
    def prepare_new_loan_disbursement_journal_draft(
        disbursement_event_id: UUID,
        body: PrepareLoanDisbursementJournalDraftRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresLoanDisbursementJournalDraftRepository = Depends(
            loan_disbursement_journal_draft_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = actor_context(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.loan_disbursement.journal.prepare",
            permission_error="Protected new-loan disbursement journal draft preparation permission is required.",
        )
        if body.confirm is not True:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "loan_disbursement_journal_draft_confirmation_required",
                    "message": "Explicit Management confirmation is required before creating a protected new-loan disbursement journal draft.",
                },
            )

        try:
            existing = repository.load_status(disbursement_event_id=disbursement_event_id)
            if existing is not None:
                _assert_existing_confirmation(body, existing)
            else:
                review = repository.load_review(disbursement_event_id=disbursement_event_id)
                _assert_review_confirmation(body, review)

            item = repository.prepare(
                actor_user_id=actor.user_id,
                disbursement_event_id=disbursement_event_id,
                expected_review_token=body.review_token,
            )
        except LoanDisbursementJournalDraftError as error:
            raise _exception(error) from error

        return {"success": True, "data": {"loan_disbursement_journal_draft": _status_payload(item)}}

    return router
