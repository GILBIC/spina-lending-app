from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .regular_journal_posting_repository import (
    PostgresRegularJournalPostingRepository,
    RegularJournalPostingConflict,
    RegularJournalPostingError,
    RegularJournalPostingNotFound,
    RegularJournalPostingStatus,
    RegularJournalPostingValidation,
)
from .request_auth import authenticated_device_context


class PostRegularJournalReviewSetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = False
    expected_transaction_count: int = Field(gt=0)
    expected_entry_count: int = Field(gt=0)
    total_debit: Decimal
    total_credit: Decimal


def regular_journal_posting_repository_dependency() -> (
    PostgresRegularJournalPostingRepository
):
    return PostgresRegularJournalPostingRepository()


def _money(value: Decimal) -> str:
    return format(value, ".2f")


def _payload(item: RegularJournalPostingStatus) -> dict[str, object]:
    return {
        "loan_id": str(item.loan_id),
        "review_token": item.review_set_fingerprint,
        "expected_transaction_count": item.expected_transaction_count,
        "preparation_count": item.preparation_count,
        "expected_entry_count": item.expected_entry_count,
        "actual_entry_count": item.actual_entry_count,
        "draft_entry_count": item.draft_entry_count,
        "posted_entry_count": item.posted_entry_count,
        "total_debit": _money(item.total_debit),
        "total_credit": _money(item.total_credit),
        "posting_ready": item.posting_ready,
        "posting_blocker": item.posting_blocker,
        "posting_set_id": (
            str(item.posting_set_id) if item.posting_set_id is not None else None
        ),
        "audit_entry_count": item.audit_entry_count,
        "posted": item.posted,
        "posted_by_user_id": (
            str(item.posted_by_user_id)
            if item.posted_by_user_id is not None
            else None
        ),
        "posted_at": item.posted_at.isoformat() if item.posted_at is not None else None,
        "entry_numbers": list(item.entry_numbers),
        "regular_journal_posting_enabled": item.regular_journal_posting_enabled,
        "automatic_source_posting_enabled": item.automatic_source_posting_enabled,
        "notice": (
            "This complete protected Regular review set has been posted atomically to the General Ledger. Corrections require the later controlled reversal workflow; automatic source posting remains disabled."
            if item.posted
            else "Posting is an explicit Management action for the complete protected review set. The server revalidates source transactions, immutable draft identity, open fiscal periods, accounts, balance, and approved journal patterns inside one transaction. Automatic source posting remains disabled."
        ),
    }


def _exception(error: RegularJournalPostingError) -> HTTPException:
    if isinstance(error, RegularJournalPostingNotFound):
        status_code = 404
    elif isinstance(error, RegularJournalPostingConflict):
        status_code = 409
    elif isinstance(error, RegularJournalPostingValidation):
        status_code = 422
    else:
        status_code = 500
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    )


def create_regular_journal_posting_router() -> APIRouter:
    router = APIRouter(tags=["management protected Regular journal posting"])

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
                    "message": (
                        "Management access is required for protected Regular journal posting."
                    ),
                },
            )
        return actor

    @router.get(
        "/api/v1/management/financial-accounting/regular-journal-posting/{loan_id}/{review_token}"
    )
    @router.get(
        "/api/mobile/v1/management/financial-accounting/regular-journal-posting/{loan_id}/{review_token}",
        include_in_schema=False,
    )
    def regular_journal_posting_status(
        loan_id: UUID,
        review_token: str,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRegularJournalPostingRepository = Depends(
            regular_journal_posting_repository_dependency
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
            item = repository.load_status(
                loan_id=loan_id,
                review_set_fingerprint=review_token,
            )
        except RegularJournalPostingError as error:
            raise _exception(error) from error
        return {
            "success": True,
            "data": {"regular_journal_posting": _payload(item)},
        }

    @router.post(
        "/api/v1/management/financial-accounting/regular-journal-posting/{loan_id}/{review_token}"
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/regular-journal-posting/{loan_id}/{review_token}",
        include_in_schema=False,
    )
    def post_regular_journal_review_set(
        loan_id: UUID,
        review_token: str,
        body: PostRegularJournalReviewSetRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRegularJournalPostingRepository = Depends(
            regular_journal_posting_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = actor_context(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.regular_journal.post",
            permission_error="Protected Regular journal posting permission is required.",
        )
        if body.confirm is not True:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "regular_journal_post_confirmation_required",
                    "message": (
                        "Explicit confirmation is required before posting the complete protected Regular review set."
                    ),
                },
            )

        try:
            current = repository.load_status(
                loan_id=loan_id,
                review_set_fingerprint=review_token,
            )
            if (
                current.expected_transaction_count != body.expected_transaction_count
                or current.expected_entry_count != body.expected_entry_count
                or current.total_debit != body.total_debit
                or current.total_credit != body.total_credit
            ):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "regular_journal_post_confirmation_stale",
                        "message": (
                            "Protected Regular review-set counts or totals changed. Refresh and review before posting."
                        ),
                    },
                )
            if not current.posting_ready and not current.posted:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "regular_journal_post_not_ready",
                        "message": current.posting_blocker
                        or "Protected Regular review set is not ready for posting.",
                    },
                )
            item = repository.post(
                actor_user_id=actor.user_id,
                loan_id=loan_id,
                expected_review_set_fingerprint=review_token,
            )
        except RegularJournalPostingError as error:
            raise _exception(error) from error

        return {
            "success": True,
            "data": {"regular_journal_posting": _payload(item)},
        }

    return router
