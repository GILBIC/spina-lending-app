from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .opening_balance_journal_repository import (
    OpeningBalanceJournalConflict,
    OpeningBalanceJournalError,
    OpeningBalanceJournalNotFound,
    OpeningBalanceJournalPreparation,
    OpeningBalanceJournalValidation,
    PostgresOpeningBalanceJournalRepository,
)
from .request_auth import authenticated_device_context


class PrepareOpeningBalanceJournalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = False


class PostOpeningBalanceJournalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = False
    journal_entry_id: UUID
    total_debit: Decimal
    total_credit: Decimal


def opening_balance_journal_repository_dependency() -> (
    PostgresOpeningBalanceJournalRepository
):
    return PostgresOpeningBalanceJournalRepository()


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _payload(item: OpeningBalanceJournalPreparation) -> dict[str, object]:
    posted = item.journal_status == "posted" and item.posted_at is not None
    return {
        "workbook_id": str(item.workbook_id),
        "cutover_date": item.cutover_date.isoformat(),
        "workbook_status": item.workbook_status,
        "journal_entry_id": (
            str(item.journal_entry_id) if item.journal_entry_id is not None else None
        ),
        "journal_status": item.journal_status,
        "entry_number": item.entry_number,
        "journal_created_at": (
            item.journal_created_at.isoformat()
            if item.journal_created_at is not None
            else None
        ),
        "prepared_by_user_id": (
            str(item.prepared_by_user_id)
            if item.prepared_by_user_id is not None
            else None
        ),
        "prepared_at": (
            item.prepared_at.isoformat() if item.prepared_at is not None else None
        ),
        "journal_line_count": item.journal_line_count,
        "total_debit": _decimal(item.total_debit),
        "total_credit": _decimal(item.total_credit),
        "draft_prepared": item.draft_prepared,
        "preparation_ready": item.preparation_ready,
        "preparation_blocker": item.preparation_blocker,
        "opening_balance_posting_enabled": item.opening_balance_posting_enabled,
        "automatic_source_posting_enabled": item.automatic_source_posting_enabled,
        "posting_ready": item.posting_ready,
        "posting_blocker": item.posting_blocker,
        "posted_by_user_id": (
            str(item.posted_by_user_id)
            if item.posted_by_user_id is not None
            else None
        ),
        "posted_at": item.posted_at.isoformat() if item.posted_at is not None else None,
        "notice": (
            "Opening balances are posted to the General Ledger and are immutable; corrections require a controlled reversal. Automatic source posting remains disabled."
            if posted
            else "This is a protected system-generated opening-balance journal. Posting requires a separate explicit Management confirmation after all controls are revalidated; automatic source posting remains disabled."
        ),
    }


def _exception(error: OpeningBalanceJournalError) -> HTTPException:
    if isinstance(error, OpeningBalanceJournalNotFound):
        status_code = 404
    elif isinstance(error, OpeningBalanceJournalConflict):
        status_code = 409
    elif isinstance(error, OpeningBalanceJournalValidation):
        status_code = 422
    else:
        status_code = 500
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    )


def create_opening_balance_journal_router() -> APIRouter:
    router = APIRouter(tags=["management opening balance journal"])

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
                    "message": "Management access is required for opening-balance journal controls.",
                },
            )
        return actor

    @router.get(
        "/api/v1/management/financial-accounting/opening-balance-workbook/{workbook_id}/journal-draft"
    )
    @router.get(
        "/api/mobile/v1/management/financial-accounting/opening-balance-workbook/{workbook_id}/journal-draft",
        include_in_schema=False,
    )
    def get_journal_draft_status(
        workbook_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresOpeningBalanceJournalRepository = Depends(
            opening_balance_journal_repository_dependency
        ),
    ) -> dict[str, object]:
        actor_context(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.view",
            permission_error="Accounting view permission is required.",
        )
        try:
            item = repository.load_status(workbook_id=workbook_id)
        except OpeningBalanceJournalError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"journal_draft": _payload(item)}}

    @router.post(
        "/api/v1/management/financial-accounting/opening-balance-workbook/{workbook_id}/journal-draft",
        status_code=status.HTTP_201_CREATED,
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/opening-balance-workbook/{workbook_id}/journal-draft",
        status_code=status.HTTP_201_CREATED,
        include_in_schema=False,
    )
    def prepare_journal_draft(
        workbook_id: UUID,
        body: PrepareOpeningBalanceJournalRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresOpeningBalanceJournalRepository = Depends(
            opening_balance_journal_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = actor_context(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.opening_balance.prepare",
            permission_error="Opening-balance journal preparation permission is required.",
        )
        if body.confirm is not True:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "opening_balance_journal_confirmation_required",
                    "message": (
                        "Explicit confirmation is required before preparing the protected "
                        "opening-balance journal draft."
                    ),
                },
            )
        try:
            item = repository.prepare_draft(
                actor_user_id=actor.user_id,
                workbook_id=workbook_id,
            )
        except OpeningBalanceJournalError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"journal_draft": _payload(item)}}

    @router.post(
        "/api/v1/management/financial-accounting/opening-balance-workbook/{workbook_id}/journal-draft/post"
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/opening-balance-workbook/{workbook_id}/journal-draft/post",
        include_in_schema=False,
    )
    def post_journal_draft(
        workbook_id: UUID,
        body: PostOpeningBalanceJournalRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresOpeningBalanceJournalRepository = Depends(
            opening_balance_journal_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = actor_context(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.opening_balance.post",
            permission_error="Opening-balance journal posting permission is required.",
        )
        if body.confirm is not True:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "opening_balance_post_confirmation_required",
                    "message": "Explicit confirmation is required before posting opening balances to the General Ledger.",
                },
            )
        try:
            current = repository.load_status(workbook_id=workbook_id)
            if (
                current.journal_entry_id != body.journal_entry_id
                or current.total_debit != body.total_debit
                or current.total_credit != body.total_credit
            ):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "opening_balance_post_confirmation_stale",
                        "message": "Opening-balance journal identity or totals changed. Refresh and review before posting.",
                    },
                )
            if not current.posting_ready and current.journal_status != "posted":
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "opening_balance_post_not_ready",
                        "message": current.posting_blocker
                        or "Opening-balance journal is not ready for protected posting.",
                    },
                )
            item = repository.post(
                actor_user_id=actor.user_id,
                workbook_id=workbook_id,
            )
        except OpeningBalanceJournalError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"journal_draft": _payload(item)}}

    return router
