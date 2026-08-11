from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .regular_journal_draft_repository import (
    PostgresRegularJournalDraftRepository,
    RegularJournalDraftConflict,
    RegularJournalDraftError,
    RegularJournalDraftNotFound,
    RegularJournalDraftReview,
    RegularJournalDraftReviewSetStatus,
    RegularJournalDraftValidation,
)
from .request_auth import authenticated_device_context


class PrepareRegularJournalDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = False
    review_token: str = Field(min_length=64, max_length=64)


def regular_journal_draft_repository_dependency() -> (
    PostgresRegularJournalDraftRepository
):
    return PostgresRegularJournalDraftRepository()


def _money(value: Decimal) -> str:
    return format(value, ".2f")


def _entry_payload(entry) -> dict[str, object]:
    return {
        "transaction_id": str(entry.transaction_id),
        "sequence_order": entry.sequence_order,
        "entry_type": entry.entry_type,
        "journal_entry_id": str(entry.journal_entry_id),
        "journal_status": entry.journal_status,
        "source_type": entry.source_type,
        "source_reference": entry.source_reference,
        "source_event_key": entry.source_event_key,
        "posting_date": entry.posting_date.isoformat(),
        "fiscal_period_id": str(entry.fiscal_period_id),
        "fiscal_period_label": entry.fiscal_period_label,
        "fiscal_period_status": entry.fiscal_period_status,
        "line_count": entry.line_count,
        "total_debit": _money(entry.total_debit),
        "total_credit": _money(entry.total_credit),
        "balanced": entry.balanced,
        "posting_enabled": False,
    }


def _preparation_payload(item) -> dict[str, object]:
    return {
        "preparation_id": str(item.preparation_id),
        "transaction_id": str(item.transaction_id),
        "bundle_fingerprint": item.bundle_fingerprint,
        "evidence_policy_version": item.evidence_policy_version,
        "draft_policy_version": item.draft_policy_version,
        "expected_entry_count": item.expected_entry_count,
        "actual_entry_count": item.actual_entry_count,
        "draft_entry_count": item.draft_entry_count,
        "posted_entry_count": item.posted_entry_count,
        "prepared_by_user_id": str(item.prepared_by_user_id),
        "prepared_at": item.prepared_at.isoformat(),
        "total_debit": _money(item.total_debit),
        "total_credit": _money(item.total_credit),
        "draft_integrity_ready": item.draft_integrity_ready,
        "draft_integrity_blocker": item.draft_integrity_blocker,
        "regular_journal_posting_enabled": item.regular_journal_posting_enabled,
        "automatic_source_posting_enabled": (
            item.automatic_source_posting_enabled
        ),
        "entries": [_entry_payload(entry) for entry in item.entries],
    }


def _review_payload(item: RegularJournalDraftReview) -> dict[str, object]:
    return {
        "loan_id": str(item.loan_id),
        "review_token": item.review_set_fingerprint,
        "evidence_policy_version": item.evidence_policy_version,
        "draft_policy_version": item.draft_policy_version,
        "transaction_count": item.transaction_count,
        "transactions": [
            {
                "transaction_id": str(bundle.transaction_id),
                "bundle_fingerprint": bundle.bundle_fingerprint,
                "expected_entry_count": bundle.expected_entry_count,
            }
            for bundle in item.bundles
        ],
        "posting_eligible": item.posting_eligible,
        "automatic_source_posting_enabled": (
            item.automatic_source_posting_enabled
        ),
        "notice": (
            "Review the Stage 5D.15 posting-ready evidence first. This token "
            "cryptographically binds the exact current all-or-none evidence set "
            "that Stage 5D.16 will replay again under source locks before creating "
            "any journal draft. The token grants no posting permission."
        ),
    }


def _review_set_payload(
    item: RegularJournalDraftReviewSetStatus,
) -> dict[str, object]:
    return {
        "loan_id": str(item.loan_id),
        "review_token": item.review_set_fingerprint,
        "expected_transaction_count": item.expected_transaction_count,
        "preparation_count": item.preparation_count,
        "draft_integrity_ready": item.draft_integrity_ready,
        "draft_integrity_blocker": item.blocker,
        "regular_journal_posting_enabled": item.regular_journal_posting_enabled,
        "automatic_source_posting_enabled": (
            item.automatic_source_posting_enabled
        ),
        "preparations": [
            _preparation_payload(preparation)
            for preparation in item.preparations
        ],
        "notice": (
            "Stage 5D.16 creates protected system-generated Regular journal "
            "drafts only after an exact stale-safe replay of the reviewed "
            "posting-ready evidence. These drafts cannot be edited, cancelled, "
            "or posted through the manual General Journal. Actual Regular journal "
            "posting and automatic source posting remain disabled."
        ),
    }


def _exception(error: RegularJournalDraftError) -> HTTPException:
    if isinstance(error, RegularJournalDraftNotFound):
        status_code = 404
    elif isinstance(error, RegularJournalDraftConflict):
        status_code = 409
    elif isinstance(error, RegularJournalDraftValidation):
        status_code = 422
    else:
        status_code = 500
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    )


def create_regular_journal_draft_router() -> APIRouter:
    router = APIRouter(tags=["management protected Regular journal drafts"])

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
                        "Management access is required for protected Regular "
                        "journal draft controls."
                    ),
                },
            )
        return actor

    @router.get(
        "/api/v1/management/financial-accounting/regular-journal-drafts/{loan_id}/review"
    )
    @router.get(
        "/api/mobile/v1/management/financial-accounting/regular-journal-drafts/{loan_id}/review",
        include_in_schema=False,
    )
    def regular_journal_draft_review(
        loan_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRegularJournalDraftRepository = Depends(
            regular_journal_draft_repository_dependency
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
            review = repository.load_review(loan_id=loan_id)
        except RegularJournalDraftError as error:
            raise _exception(error) from error
        return {
            "success": True,
            "data": {
                "regular_journal_draft_review": _review_payload(review)
            },
        }

    @router.get(
        "/api/v1/management/financial-accounting/regular-journal-drafts/{loan_id}"
    )
    @router.get(
        "/api/mobile/v1/management/financial-accounting/regular-journal-drafts/{loan_id}",
        include_in_schema=False,
    )
    def regular_journal_draft_status(
        loan_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRegularJournalDraftRepository = Depends(
            regular_journal_draft_repository_dependency
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
            review_sets = repository.list_status(loan_id=loan_id)
        except RegularJournalDraftError as error:
            raise _exception(error) from error
        return {
            "success": True,
            "data": {
                "regular_journal_drafts": {
                    "loan_id": str(loan_id),
                    "review_sets": [
                        _review_set_payload(item) for item in review_sets
                    ],
                    "regular_journal_posting_enabled": False,
                    "automatic_source_posting_enabled": False,
                }
            },
        }

    @router.post(
        "/api/v1/management/financial-accounting/regular-journal-drafts/{loan_id}",
        status_code=status.HTTP_201_CREATED,
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/regular-journal-drafts/{loan_id}",
        status_code=status.HTTP_201_CREATED,
        include_in_schema=False,
    )
    def prepare_regular_journal_drafts(
        loan_id: UUID,
        body: PrepareRegularJournalDraftRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRegularJournalDraftRepository = Depends(
            regular_journal_draft_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = actor_context(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.regular_journal.prepare",
            permission_error=(
                "Protected Regular journal draft preparation permission is required."
            ),
        )
        if body.confirm is not True:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "regular_journal_draft_confirmation_required",
                    "message": (
                        "Explicit confirmation is required before creating "
                        "protected Regular journal drafts."
                    ),
                },
            )

        try:
            review_set = repository.prepare(
                actor_user_id=actor.user_id,
                loan_id=loan_id,
                expected_review_set_fingerprint=body.review_token,
            )
        except RegularJournalDraftError as error:
            raise _exception(error) from error

        return {
            "success": True,
            "data": {
                "regular_journal_draft_review_set": _review_set_payload(review_set)
            },
        }

    return router
