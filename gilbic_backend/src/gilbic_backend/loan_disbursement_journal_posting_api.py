from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .loan_disbursement_journal_posting_repository import (
    LoanDisbursementJournalPostingConflict,
    LoanDisbursementJournalPostingError,
    LoanDisbursementJournalPostingNotFound,
    LoanDisbursementJournalPostingStatus,
    LoanDisbursementJournalPostingValidation,
    PostgresLoanDisbursementJournalPostingRepository,
)
from .request_auth import authenticated_device_context


class PostLoanDisbursementJournalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = False
    posting_review_token: str = Field(min_length=64, max_length=64)
    preparation_id: UUID
    journal_entry_id: UUID
    source_event_key: str = Field(min_length=1, max_length=200)
    draft_review_token: str = Field(min_length=64, max_length=64)
    posting_date: date
    amount: Decimal = Field(gt=0, decimal_places=2)
    debit_account_system_key: str = Field(min_length=1, max_length=100)
    credit_account_system_key: str = Field(min_length=1, max_length=100)
    total_debit: Decimal = Field(gt=0, decimal_places=2)
    total_credit: Decimal = Field(gt=0, decimal_places=2)


def loan_disbursement_journal_posting_repository_dependency() -> (
    PostgresLoanDisbursementJournalPostingRepository
):
    return PostgresLoanDisbursementJournalPostingRepository()


def _money(value: Decimal) -> str:
    return format(value, ".2f")


def _payload(item: LoanDisbursementJournalPostingStatus) -> dict[str, object]:
    return {
        "preparation_id": str(item.preparation_id),
        "disbursement_event_id": str(item.disbursement_event_id),
        "loan_id": str(item.loan_id),
        "client_id": str(item.client_id),
        "journal_entry_id": str(item.journal_entry_id),
        "source_event_key": item.source_event_key,
        "draft_review_token": item.draft_review_token,
        "draft_policy_version": item.draft_policy_version,
        "posting_review_token": item.posting_review_token,
        "posting_policy_version": item.posting_policy_version,
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
        "journal_status": item.journal_status,
        "entry_number": item.entry_number,
        "posting_id": None if item.posting_id is None else str(item.posting_id),
        "posted": item.posted,
        "posted_audit_exact": item.posted_audit_exact,
        "posted_by_user_id": (
            None if item.posted_by_user_id is None else str(item.posted_by_user_id)
        ),
        "posted_at": None if item.posted_at is None else item.posted_at.isoformat(),
        "posting_ready": item.posting_ready,
        "protected_posting_enabled": item.protected_posting_enabled,
        "automatic_source_posting_enabled": item.automatic_source_posting_enabled,
        "notice": (
            "This protected new-Regular-loan disbursement journal is posted and bound to immutable Stage 5D.22 audit evidence. Corrections require the later controlled disbursement reversal/cancellation path; automatic source posting remains disabled."
            if item.posted
            else "Posting is an explicit Management action. Confirm the exact preparation, journal/source identity, posting date, amount, accounts and balanced totals shown here. The server revalidates authoritative funding evidence, the immutable Stage 5D.21 draft, open period, active accounts and exact Dr 1100 / Cr evidence-backed cash lines before posting."
        ),
    }


def _exception(error: LoanDisbursementJournalPostingError) -> HTTPException:
    if isinstance(error, LoanDisbursementJournalPostingNotFound):
        status_code = 404
    elif isinstance(error, LoanDisbursementJournalPostingConflict):
        status_code = 409
    elif isinstance(error, LoanDisbursementJournalPostingValidation):
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
            "code": "loan_disbursement_journal_post_confirmation_mismatch",
            "message": message,
        },
    )


def _assert_confirmation(
    body: PostLoanDisbursementJournalRequest,
    current: LoanDisbursementJournalPostingStatus,
) -> None:
    checks = (
        (body.posting_review_token == current.posting_review_token, "posting review token"),
        (body.preparation_id == current.preparation_id, "preparation identity"),
        (body.journal_entry_id == current.journal_entry_id, "journal identity"),
        (body.source_event_key == current.source_event_key, "source-event identity"),
        (body.draft_review_token == current.draft_review_token, "draft review token"),
        (body.posting_date == current.posting_date, "posting date"),
        (body.amount == current.amount, "amount"),
        (
            body.debit_account_system_key == current.debit_account_system_key,
            "debit account",
        ),
        (
            body.credit_account_system_key == current.credit_account_system_key,
            "funding cash account",
        ),
        (body.total_debit == current.total_debit, "total debit"),
        (body.total_credit == current.total_credit, "total credit"),
    )
    mismatch = next((label for ok, label in checks if not ok), None)
    if mismatch is not None:
        raise _confirmation_error(
            f"The confirmed {mismatch} does not match the protected posting review. Refresh before posting."
        )


def create_loan_disbursement_journal_posting_router() -> APIRouter:
    router = APIRouter(tags=["management protected loan-disbursement journal posting"])

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
                    "message": "Management access is required for protected new-loan disbursement journal posting.",
                },
            )
        return actor

    @router.get(
        "/api/v1/management/accounting/loan-disbursements/{disbursement_event_id}/journal-posting"
    )
    @router.get(
        "/api/mobile/v1/management/accounting/loan-disbursements/{disbursement_event_id}/journal-posting",
        include_in_schema=False,
    )
    def loan_disbursement_journal_posting_status(
        disbursement_event_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresLoanDisbursementJournalPostingRepository = Depends(
            loan_disbursement_journal_posting_repository_dependency
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
        except LoanDisbursementJournalPostingError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"loan_disbursement_journal_posting": _payload(item)}}

    @router.post(
        "/api/v1/management/accounting/loan-disbursements/{disbursement_event_id}/journal-posting"
    )
    @router.post(
        "/api/mobile/v1/management/accounting/loan-disbursements/{disbursement_event_id}/journal-posting",
        include_in_schema=False,
    )
    def post_loan_disbursement_journal(
        disbursement_event_id: UUID,
        body: PostLoanDisbursementJournalRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresLoanDisbursementJournalPostingRepository = Depends(
            loan_disbursement_journal_posting_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = actor_context(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.loan_disbursement.journal.post",
            permission_error="Protected new-loan disbursement journal posting permission is required.",
        )
        if body.confirm is not True:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "loan_disbursement_journal_post_confirmation_required",
                    "message": "Explicit Management confirmation is required before posting a protected new-loan disbursement journal.",
                },
            )

        try:
            current = repository.load_status(disbursement_event_id=disbursement_event_id)
            _assert_confirmation(body, current)
            if not current.posting_ready and not current.posted:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "loan_disbursement_journal_post_not_ready",
                        "message": "Protected new-loan disbursement journal is not integrity-ready for posting.",
                    },
                )
            item = repository.post(
                actor_user_id=actor.user_id,
                disbursement_event_id=disbursement_event_id,
                expected_posting_review_token=body.posting_review_token,
            )
        except LoanDisbursementJournalPostingError as error:
            raise _exception(error) from error

        return {"success": True, "data": {"loan_disbursement_journal_posting": _payload(item)}}

    return router
