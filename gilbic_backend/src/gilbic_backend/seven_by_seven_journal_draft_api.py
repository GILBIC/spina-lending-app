from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .request_auth import authenticated_device_context
from .seven_by_seven_journal_draft_repository import (
    PostgresSevenBySevenJournalDraftRepository,
    SevenBySevenJournalDraftConflict,
    SevenBySevenJournalDraftError,
    SevenBySevenJournalDraftNotFound,
    SevenBySevenJournalDraftReview,
    SevenBySevenJournalDraftStatus,
    SevenBySevenJournalDraftValidation,
)


class PrepareSevenBySevenJournalDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = False
    source_event_review_token: str = Field(min_length=64, max_length=64)
    coordinate_digest: str = Field(min_length=64, max_length=64)
    source_event_key: str = Field(min_length=1, max_length=200)
    posting_date: date
    source_cash_amount: Decimal = Field(gt=0, decimal_places=2)
    total_debit: Decimal = Field(gt=0, decimal_places=2)
    total_credit: Decimal = Field(gt=0, decimal_places=2)


def seven_by_seven_journal_draft_repository_dependency() -> PostgresSevenBySevenJournalDraftRepository:
    return PostgresSevenBySevenJournalDraftRepository()


def _money(value: Decimal) -> str:
    return format(value, ".2f")


def _review_payload(item: SevenBySevenJournalDraftReview) -> dict[str, object]:
    return {
        "transaction_id": str(item.transaction_id),
        "loan_id": str(item.loan_id),
        "loan_number": item.loan_number,
        "client_id": str(item.client_id),
        "client_code": item.client_code,
        "client_name": item.client_name,
        "posting_date": item.posting_date.isoformat(),
        "fiscal_period_id": str(item.fiscal_period_id),
        "source_event_key": item.source_event_key,
        "source_event_review_token": item.source_event_review_token,
        "coordinate_digest": item.coordinate_digest,
        "source_cash_amount": _money(item.source_cash_amount),
        "eir_interest_accrual": _money(item.eir_interest_accrual),
        "accounting_eir_interest_received": _money(item.accounting_eir_interest_received),
        "accounting_7x7_principal_received": _money(item.accounting_7x7_principal_received),
        "coordinate_line_count": item.coordinate_line_count,
        "total_debit": _money(item.total_debit),
        "total_credit": _money(item.total_credit),
        "draft_policy_version": item.draft_policy_version,
        "coordinates": [
            {
                "line_number": line.line_number,
                "journal_component": line.journal_component,
                "account_id": str(line.account_id),
                "account_code": line.account_code,
                "account_system_key": line.account_system_key,
                "account_name": line.account_name,
                "debit": _money(line.debit),
                "credit": _money(line.credit),
            }
            for line in item.coordinates
        ],
        "draft_review_ready": item.draft_review_ready,
        "posting_enabled": item.posting_enabled,
        "automatic_source_posting_enabled": item.automatic_source_posting_enabled,
        "notice": (
            "Management must confirm this exact 0064 source-event review token, source key, "
            "posting date, cash amount, coordinate digest and balanced totals. This creates "
            "an immutable protected draft only. Posting and reversal remain disabled."
        ),
    }


def _status_payload(item: SevenBySevenJournalDraftStatus) -> dict[str, object]:
    return {
        "preparation_id": str(item.preparation_id),
        "transaction_id": str(item.transaction_id),
        "loan_id": str(item.loan_id),
        "client_id": str(item.client_id),
        "journal_entry_id": str(item.journal_entry_id),
        "source_event_key": item.source_event_key,
        "source_event_review_token": item.source_event_review_token,
        "coordinate_digest": item.coordinate_digest,
        "draft_policy_version": item.draft_policy_version,
        "posting_date": item.posting_date.isoformat(),
        "fiscal_period_id": str(item.fiscal_period_id),
        "fiscal_period_label": item.fiscal_period_label,
        "fiscal_period_status": item.fiscal_period_status,
        "source_cash_amount": _money(item.source_cash_amount),
        "eir_interest_accrual": _money(item.eir_interest_accrual),
        "accounting_eir_interest_received": _money(item.accounting_eir_interest_received),
        "accounting_7x7_principal_received": _money(item.accounting_7x7_principal_received),
        "coordinate_line_count": item.coordinate_line_count,
        "prepared_total_debit": _money(item.prepared_total_debit),
        "prepared_total_credit": _money(item.prepared_total_credit),
        "prepared_by_user_id": str(item.prepared_by_user_id),
        "prepared_at": item.prepared_at.isoformat(),
        "journal_status": item.journal_status,
        "entry_number": item.entry_number,
        "line_count": item.line_count,
        "total_debit": _money(item.total_debit),
        "total_credit": _money(item.total_credit),
        "draft_integrity_ready": item.draft_integrity_ready,
        "posting_enabled": item.posting_enabled,
        "automatic_source_posting_enabled": item.automatic_source_posting_enabled,
        "notice": (
            "This protected 7x7 draft is system generated and cannot be edited, deleted or "
            "posted through the manual General Journal. Future protected posting must revalidate "
            "the exact current source token, coordinates, period and draft integrity."
        ),
    }


def _exception(error: SevenBySevenJournalDraftError) -> HTTPException:
    if isinstance(error, SevenBySevenJournalDraftNotFound):
        status_code = 404
    elif isinstance(error, SevenBySevenJournalDraftConflict):
        status_code = 409
    elif isinstance(error, SevenBySevenJournalDraftValidation):
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
            "code": "seven_by_seven_journal_draft_confirmation_mismatch",
            "message": message,
        },
    )


def _assert_review_confirmation(
    body: PrepareSevenBySevenJournalDraftRequest,
    review: SevenBySevenJournalDraftReview,
) -> None:
    if body.source_event_review_token != review.source_event_review_token:
        raise _confirmation_error("The confirmed 7x7 source-event review token does not match the current review.")
    if body.coordinate_digest != review.coordinate_digest:
        raise _confirmation_error("The confirmed 7x7 coordinate digest does not match the current review.")
    if body.source_event_key != review.source_event_key:
        raise _confirmation_error("The confirmed 7x7 source-event identity does not match the current review.")
    if body.posting_date != review.posting_date:
        raise _confirmation_error("The confirmed 7x7 posting date does not match the current review.")
    if body.source_cash_amount != review.source_cash_amount:
        raise _confirmation_error("The confirmed 7x7 source cash amount does not match the current review.")
    if body.total_debit != review.total_debit or body.total_credit != review.total_credit:
        raise _confirmation_error("The confirmed 7x7 balanced totals do not match the current coordinate review.")


def _assert_existing_confirmation(
    body: PrepareSevenBySevenJournalDraftRequest,
    item: SevenBySevenJournalDraftStatus,
) -> None:
    if body.source_event_review_token != item.source_event_review_token:
        raise _confirmation_error("The existing protected 7x7 draft has a different source-event review token.")
    if body.coordinate_digest != item.coordinate_digest:
        raise _confirmation_error("The existing protected 7x7 draft has a different coordinate digest.")
    if body.source_event_key != item.source_event_key:
        raise _confirmation_error("The existing protected 7x7 draft has a different source-event identity.")
    if body.posting_date != item.posting_date:
        raise _confirmation_error("The existing protected 7x7 draft has a different posting date.")
    if body.source_cash_amount != item.source_cash_amount:
        raise _confirmation_error("The existing protected 7x7 draft has a different source cash amount.")
    if body.total_debit != item.prepared_total_debit or body.total_credit != item.prepared_total_credit:
        raise _confirmation_error("The existing protected 7x7 draft has different balanced totals.")


def create_seven_by_seven_journal_draft_router() -> APIRouter:
    router = APIRouter(tags=["management protected 7x7 journal drafts"])

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
                    "message": "Management access is required for protected 7x7 journal-draft controls.",
                },
            )
        return actor

    review_paths = (
        "/api/v1/management/accounting/seven-by-seven/collections/{transaction_id}/journal-draft/review",
        "/api/mobile/v1/management/accounting/seven-by-seven/collections/{transaction_id}/journal-draft/review",
    )
    status_paths = (
        "/api/v1/management/accounting/seven-by-seven/collections/{transaction_id}/journal-draft",
        "/api/mobile/v1/management/accounting/seven-by-seven/collections/{transaction_id}/journal-draft",
    )

    def review_handler(
        transaction_id: UUID,
        authorization: str | None,
        x_device_id: str | None,
        auth: SupabaseAuthClient,
        accounts: PostgresAccountRepository,
        repository: PostgresSevenBySevenJournalDraftRepository,
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
            review = repository.load_review(transaction_id=transaction_id)
        except SevenBySevenJournalDraftError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"seven_by_seven_journal_draft_review": _review_payload(review)}}

    @router.get(review_paths[0])
    def review_seven_by_seven_journal_draft(
        transaction_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresSevenBySevenJournalDraftRepository = Depends(
            seven_by_seven_journal_draft_repository_dependency
        ),
    ) -> dict[str, object]:
        return review_handler(transaction_id, authorization, x_device_id, auth, accounts, repository)

    router.add_api_route(
        review_paths[1],
        review_seven_by_seven_journal_draft,
        methods=["GET"],
        include_in_schema=False,
    )

    @router.get(status_paths[0])
    def seven_by_seven_journal_draft_status(
        transaction_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresSevenBySevenJournalDraftRepository = Depends(
            seven_by_seven_journal_draft_repository_dependency
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
            item = repository.load_status(transaction_id=transaction_id)
        except SevenBySevenJournalDraftError as error:
            raise _exception(error) from error
        return {
            "success": True,
            "data": {
                "seven_by_seven_journal_draft": None if item is None else _status_payload(item),
                "posting_enabled": False,
                "automatic_source_posting_enabled": False,
            },
        }

    router.add_api_route(
        status_paths[1],
        seven_by_seven_journal_draft_status,
        methods=["GET"],
        include_in_schema=False,
    )

    @router.post(status_paths[0], status_code=status.HTTP_201_CREATED)
    def prepare_seven_by_seven_journal_draft(
        transaction_id: UUID,
        body: PrepareSevenBySevenJournalDraftRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresSevenBySevenJournalDraftRepository = Depends(
            seven_by_seven_journal_draft_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = actor_context(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.seven_by_seven.journal.prepare",
            permission_error="Protected 7x7 journal-draft preparation permission is required.",
        )
        if body.confirm is not True:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "seven_by_seven_journal_draft_confirmation_required",
                    "message": "Explicit Management confirmation is required before creating a protected 7x7 journal draft.",
                },
            )

        try:
            existing = repository.load_status(transaction_id=transaction_id)
            if existing is not None:
                _assert_existing_confirmation(body, existing)
            else:
                review = repository.load_review(transaction_id=transaction_id)
                _assert_review_confirmation(body, review)
            item = repository.prepare(
                actor_user_id=actor.user_id,
                transaction_id=transaction_id,
                expected_review_token=body.source_event_review_token,
                expected_coordinate_digest=body.coordinate_digest,
            )
        except SevenBySevenJournalDraftError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"seven_by_seven_journal_draft": _status_payload(item)}}

    router.add_api_route(
        status_paths[1],
        prepare_seven_by_seven_journal_draft,
        methods=["POST"],
        status_code=status.HTTP_201_CREATED,
        include_in_schema=False,
    )

    return router
