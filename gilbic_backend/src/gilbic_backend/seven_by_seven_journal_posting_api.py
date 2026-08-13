from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .request_auth import authenticated_device_context
from .seven_by_seven_journal_posting_repository import (
    PostgresSevenBySevenJournalPostingRepository,
    SevenBySevenJournalPostingConflict,
    SevenBySevenJournalPostingError,
    SevenBySevenJournalPostingNotFound,
    SevenBySevenJournalPostingStatus,
    SevenBySevenJournalPostingValidation,
)


class PostSevenBySevenJournalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = False
    posting_review_token: str = Field(min_length=64, max_length=64)
    preparation_id: UUID
    journal_entry_id: UUID
    source_event_key: str = Field(min_length=1, max_length=200)
    source_event_review_token: str = Field(min_length=64, max_length=64)
    coordinate_digest: str = Field(min_length=64, max_length=64)
    posting_date: date
    fiscal_period_id: UUID
    source_cash_amount: Decimal = Field(gt=0, decimal_places=2)
    eir_interest_accrual: Decimal = Field(ge=0, decimal_places=2)
    accounting_eir_interest_received: Decimal = Field(ge=0, decimal_places=2)
    accounting_7x7_principal_received: Decimal = Field(ge=0, decimal_places=2)
    coordinate_line_count: int = Field(gt=0)
    total_debit: Decimal = Field(gt=0, decimal_places=2)
    total_credit: Decimal = Field(gt=0, decimal_places=2)


def seven_by_seven_journal_posting_repository_dependency() -> (
    PostgresSevenBySevenJournalPostingRepository
):
    return PostgresSevenBySevenJournalPostingRepository()


def _money(value: Decimal) -> str:
    return format(value, ".2f")


def _payload(item: SevenBySevenJournalPostingStatus) -> dict[str, object]:
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
        "posting_review_token": item.posting_review_token,
        "posting_policy_version": item.posting_policy_version,
        "posting_date": item.posting_date.isoformat(),
        "fiscal_period_id": str(item.fiscal_period_id),
        "fiscal_period_label": item.fiscal_period_label,
        "fiscal_period_status": item.fiscal_period_status,
        "source_cash_amount": _money(item.source_cash_amount),
        "eir_interest_accrual": _money(item.eir_interest_accrual),
        "accounting_eir_interest_received": _money(item.accounting_eir_interest_received),
        "accounting_7x7_principal_received": _money(item.accounting_7x7_principal_received),
        "coordinate_line_count": item.coordinate_line_count,
        "total_debit": _money(item.prepared_total_debit),
        "total_credit": _money(item.prepared_total_credit),
        "journal_status": item.journal_status,
        "entry_number": item.entry_number,
        "line_count": item.line_count,
        "posting_id": None if item.posting_id is None else str(item.posting_id),
        "posted": item.posted,
        "posted_audit_exact": item.posted_audit_exact,
        "posted_by_user_id": (
            None if item.posted_by_user_id is None else str(item.posted_by_user_id)
        ),
        "posted_at": None if item.posted_at is None else item.posted_at.isoformat(),
        "posting_ready": item.posting_ready,
        "protected_posting_enabled": item.protected_posting_enabled,
        "reversal_enabled": item.reversal_enabled,
        "automatic_source_posting_enabled": item.automatic_source_posting_enabled,
        "notice": (
            "This protected 7x7 journal is posted and bound to immutable source-token, coordinate and line-snapshot audit evidence. Reversal remains disabled until the next controlled 7x7 reversal sub-slice; automatic source posting remains off."
            if item.posted
            else "Posting is an explicit Management action. Confirm the exact preparation, journal/source identity, source-event review token, coordinate digest, fiscal period, EIR/cash components and balanced totals shown here. The server revalidates current 0064 source evidence, exact EIR coordinates, the immutable 0065 draft, open period and journal integrity immediately before posting."
        ),
    }


def _exception(error: SevenBySevenJournalPostingError) -> HTTPException:
    if isinstance(error, SevenBySevenJournalPostingNotFound):
        status_code = 404
    elif isinstance(error, SevenBySevenJournalPostingConflict):
        status_code = 409
    elif isinstance(error, SevenBySevenJournalPostingValidation):
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
            "code": "seven_by_seven_journal_post_confirmation_mismatch",
            "message": message,
        },
    )


def _assert_confirmation(
    body: PostSevenBySevenJournalRequest,
    current: SevenBySevenJournalPostingStatus,
) -> None:
    checks = (
        (body.posting_review_token == current.posting_review_token, "posting review token"),
        (body.preparation_id == current.preparation_id, "preparation identity"),
        (body.journal_entry_id == current.journal_entry_id, "journal identity"),
        (body.source_event_key == current.source_event_key, "source-event identity"),
        (
            body.source_event_review_token == current.source_event_review_token,
            "source-event review token",
        ),
        (body.coordinate_digest == current.coordinate_digest, "coordinate digest"),
        (body.posting_date == current.posting_date, "posting date"),
        (body.fiscal_period_id == current.fiscal_period_id, "fiscal period"),
        (body.source_cash_amount == current.source_cash_amount, "source cash amount"),
        (body.eir_interest_accrual == current.eir_interest_accrual, "EIR accrual"),
        (
            body.accounting_eir_interest_received
            == current.accounting_eir_interest_received,
            "accounting EIR interest received",
        ),
        (
            body.accounting_7x7_principal_received
            == current.accounting_7x7_principal_received,
            "accounting 7x7 principal received",
        ),
        (body.coordinate_line_count == current.coordinate_line_count, "coordinate line count"),
        (body.total_debit == current.prepared_total_debit, "total debit"),
        (body.total_credit == current.prepared_total_credit, "total credit"),
    )
    mismatch = next((label for ok, label in checks if not ok), None)
    if mismatch is not None:
        raise _confirmation_error(
            f"The confirmed {mismatch} does not match the protected 7x7 posting review. Refresh before posting."
        )


def create_seven_by_seven_journal_posting_router() -> APIRouter:
    router = APIRouter(tags=["management protected 7x7 journal posting"])

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
                    "message": "Management access is required for protected 7x7 journal posting.",
                },
            )
        return actor

    paths = (
        "/api/v1/management/accounting/seven-by-seven/collections/{transaction_id}/journal-posting",
        "/api/mobile/v1/management/accounting/seven-by-seven/collections/{transaction_id}/journal-posting",
    )

    @router.get(paths[0])
    def seven_by_seven_journal_posting_status(
        transaction_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresSevenBySevenJournalPostingRepository = Depends(
            seven_by_seven_journal_posting_repository_dependency
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
        except SevenBySevenJournalPostingError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"seven_by_seven_journal_posting": _payload(item)}}

    router.add_api_route(
        paths[1],
        seven_by_seven_journal_posting_status,
        methods=["GET"],
        include_in_schema=False,
    )

    @router.post(paths[0])
    def post_seven_by_seven_journal(
        transaction_id: UUID,
        body: PostSevenBySevenJournalRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresSevenBySevenJournalPostingRepository = Depends(
            seven_by_seven_journal_posting_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = actor_context(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.seven_by_seven.journal.post",
            permission_error="Protected 7x7 journal posting permission is required.",
        )
        if body.confirm is not True:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "seven_by_seven_journal_post_confirmation_required",
                    "message": "Explicit Management confirmation is required before posting a protected 7x7 journal.",
                },
            )

        try:
            current = repository.load_status(transaction_id=transaction_id)
            _assert_confirmation(body, current)
            if not current.posting_ready and not current.posted:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "seven_by_seven_journal_post_not_ready",
                        "message": "Protected 7x7 journal is not integrity-ready for posting.",
                    },
                )
            item = repository.post(
                actor_user_id=actor.user_id,
                transaction_id=transaction_id,
                expected_posting_review_token=body.posting_review_token,
            )
        except SevenBySevenJournalPostingError as error:
            raise _exception(error) from error

        return {"success": True, "data": {"seven_by_seven_journal_posting": _payload(item)}}

    router.add_api_route(
        paths[1],
        post_seven_by_seven_journal,
        methods=["POST"],
        include_in_schema=False,
    )

    return router
