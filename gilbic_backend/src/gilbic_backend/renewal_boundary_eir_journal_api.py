from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .renewal_boundary_eir_journal_repository import (
    PostgresRenewalBoundaryEirJournalRepository,
    RenewalBoundaryEirJournalConflict,
    RenewalBoundaryEirJournalError,
    RenewalBoundaryEirJournalNotFound,
    RenewalBoundaryEirJournalReview,
    RenewalBoundaryEirJournalStatus,
    RenewalBoundaryEirJournalValidation,
)
from .request_auth import authenticated_device_context


class PrepareRenewalBoundaryEirJournalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = False
    review_token: str = Field(min_length=64, max_length=64)


class PostRenewalBoundaryEirJournalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = False
    review_token: str = Field(min_length=64, max_length=64)
    expected_entry_count: int = Field(gt=0)
    total_debit: Decimal = Field(gt=0, decimal_places=2)
    total_credit: Decimal = Field(gt=0, decimal_places=2)


def renewal_boundary_eir_journal_repository_dependency() -> (
    PostgresRenewalBoundaryEirJournalRepository
):
    return PostgresRenewalBoundaryEirJournalRepository()


def _money(value: Decimal) -> str:
    return format(value, ".2f")


def _review_payload(item: RenewalBoundaryEirJournalReview) -> dict[str, object]:
    return {
        "renewal_execution_event_id": str(item.renewal_execution_event_id),
        "old_loan_id": str(item.old_loan_id),
        "old_loan_number": item.old_loan_number,
        "client_id": str(item.client_id),
        "client_code": item.client_code,
        "client_name": item.client_name,
        "target_date": item.target_date.isoformat(),
        "expected_entry_count": item.expected_entry_count,
        "total_debit": _money(item.total_debit),
        "total_credit": _money(item.total_credit),
        "protected_source_journal_count": item.protected_source_journal_count,
        "exact_protected_source_journal_count": (
            item.exact_protected_source_journal_count
        ),
        "ledger_loan_component_through_last_source": _money(
            item.ledger_loan_component_through_last_source
        ),
        "ledger_accrued_interest_through_last_source": _money(
            item.ledger_accrued_interest_through_last_source
        ),
        "ledger_gross_carrying_through_last_source": _money(
            item.ledger_gross_carrying_through_last_source
        ),
        "target_loan_component": _money(item.target_loan_component),
        "target_accrued_interest_component": _money(
            item.target_accrued_interest_component
        ),
        "target_gross_carrying_amount": _money(item.target_gross_carrying_amount),
        "tail_effective_interest_accrued": _money(
            item.tail_effective_interest_accrued
        ),
        "boundary_policy_version": item.boundary_policy_version,
        "draft_policy_version": item.draft_policy_version,
        "posting_policy_version": item.posting_policy_version,
        "review_token": item.review_token,
        "posting_enabled": item.posting_enabled,
        "automatic_source_posting": item.automatic_source_posting,
        "entries": [
            {
                "sequence_order": entry.sequence_order,
                "fiscal_period_id": str(entry.fiscal_period_id),
                "fiscal_period_label": entry.fiscal_period_label,
                "accrual_start_date_inclusive": (
                    entry.accrual_start_date_inclusive.isoformat()
                ),
                "accrual_end_date_inclusive": (
                    entry.accrual_end_date_inclusive.isoformat()
                ),
                "posting_date": entry.posting_date.isoformat(),
                "day_count": entry.day_count,
                "amount": _money(entry.amount),
                "source_type": entry.source_type,
                "source_reference": entry.source_reference,
                "source_event_key": entry.source_event_key,
                "debit_account_system_key": entry.debit_account_system_key,
                "credit_account_system_key": entry.credit_account_system_key,
            }
            for entry in item.entries
        ],
        "notice": (
            "This is an exact read-only Management review. Preparing creates only immutable protected drafts. Posting remains a separate explicit Management-confirmed action and automatic source posting remains disabled."
        ),
    }


def _status_payload(item: RenewalBoundaryEirJournalStatus | None) -> dict[str, object] | None:
    if item is None:
        return None
    return {
        "preparation_id": str(item.preparation_id),
        "renewal_execution_event_id": str(item.renewal_execution_event_id),
        "old_loan_id": str(item.old_loan_id),
        "client_id": str(item.client_id),
        "target_date": item.target_date.isoformat(),
        "review_token": item.review_token,
        "boundary_policy_version": item.boundary_policy_version,
        "draft_policy_version": item.draft_policy_version,
        "expected_entry_count": item.expected_entry_count,
        "total_amount": _money(item.total_amount),
        "prepared_by_user_id": str(item.prepared_by_user_id),
        "prepared_at": item.prepared_at.isoformat(),
        "posting_set_id": (
            None if item.posting_set_id is None else str(item.posting_set_id)
        ),
        "posting_policy_version": item.posting_policy_version,
        "posted_by_user_id": (
            None if item.posted_by_user_id is None else str(item.posted_by_user_id)
        ),
        "posted_at": None if item.posted_at is None else item.posted_at.isoformat(),
        "actual_entry_count": item.actual_entry_count,
        "draft_entry_count": item.draft_entry_count,
        "posted_entry_count": item.posted_entry_count,
        "total_debit": _money(item.total_debit),
        "total_credit": _money(item.total_credit),
        "posting_audit_entry_count": item.posting_audit_entry_count,
        "integrity_ready": item.integrity_ready,
        "protected_posting_complete": item.protected_posting_complete,
        "automatic_source_posting": item.automatic_source_posting,
        "entries": [
            {
                "sequence_order": entry.sequence_order,
                "journal_entry_id": str(entry.journal_entry_id),
                "fiscal_period_id": str(entry.fiscal_period_id),
                "posting_date": entry.posting_date.isoformat(),
                "amount": _money(entry.amount),
                "source_reference": entry.source_reference,
                "source_event_key": entry.source_event_key,
                "journal_status": entry.journal_status,
                "entry_number": entry.entry_number,
            }
            for entry in item.entries
        ],
    }


def _exception(error: RenewalBoundaryEirJournalError) -> HTTPException:
    if isinstance(error, RenewalBoundaryEirJournalNotFound):
        status_code = 404
    elif isinstance(error, RenewalBoundaryEirJournalConflict):
        status_code = 409
    elif isinstance(error, RenewalBoundaryEirJournalValidation):
        status_code = 422
    else:
        status_code = 500
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    )


def create_renewal_boundary_eir_journal_router() -> APIRouter:
    router = APIRouter(tags=["management protected renewal-boundary EIR journals"])

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
                    "message": "Management access is required for protected renewal-boundary EIR accounting.",
                },
            )
        return actor

    @router.get(
        "/api/v1/management/accounting/renewals/{renewal_execution_event_id}/boundary-eir-journal/review"
    )
    def review_renewal_boundary_eir_journal(
        renewal_execution_event_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRenewalBoundaryEirJournalRepository = Depends(
            renewal_boundary_eir_journal_repository_dependency
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
            item = repository.load_review(
                renewal_execution_event_id=renewal_execution_event_id
            )
        except RenewalBoundaryEirJournalError as error:
            raise _exception(error) from error
        return {
            "success": True,
            "data": {"renewal_boundary_eir_journal_review": _review_payload(item)},
        }

    @router.get(
        "/api/v1/management/accounting/renewals/{renewal_execution_event_id}/boundary-eir-journal/status"
    )
    def renewal_boundary_eir_journal_status(
        renewal_execution_event_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRenewalBoundaryEirJournalRepository = Depends(
            renewal_boundary_eir_journal_repository_dependency
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
                renewal_execution_event_id=renewal_execution_event_id
            )
        except RenewalBoundaryEirJournalError as error:
            raise _exception(error) from error
        return {
            "success": True,
            "data": {"renewal_boundary_eir_journal_status": _status_payload(item)},
        }

    @router.post(
        "/api/v1/management/accounting/renewals/{renewal_execution_event_id}/boundary-eir-journal/prepare"
    )
    def prepare_renewal_boundary_eir_journal(
        renewal_execution_event_id: UUID,
        body: PrepareRenewalBoundaryEirJournalRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRenewalBoundaryEirJournalRepository = Depends(
            renewal_boundary_eir_journal_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = actor_context(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.renewal_boundary_eir_journal.prepare",
            permission_error="Protected renewal-boundary EIR journal preparation permission is required.",
        )
        if body.confirm is not True:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "renewal_boundary_eir_journal_prepare_confirmation_required",
                    "message": "Explicit Management confirmation is required before creating protected renewal-boundary EIR journal drafts.",
                },
            )
        try:
            item = repository.prepare(
                actor_user_id=actor.user_id,
                renewal_execution_event_id=renewal_execution_event_id,
                expected_review_token=body.review_token,
            )
        except RenewalBoundaryEirJournalError as error:
            raise _exception(error) from error
        return {
            "success": True,
            "data": {"renewal_boundary_eir_journal_status": _status_payload(item)},
        }

    @router.post(
        "/api/v1/management/accounting/renewals/{renewal_execution_event_id}/boundary-eir-journal/post"
    )
    def post_renewal_boundary_eir_journal(
        renewal_execution_event_id: UUID,
        body: PostRenewalBoundaryEirJournalRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRenewalBoundaryEirJournalRepository = Depends(
            renewal_boundary_eir_journal_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = actor_context(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.renewal_boundary_eir_journal.post",
            permission_error="Protected renewal-boundary EIR journal posting permission is required.",
        )
        if body.confirm is not True:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "renewal_boundary_eir_journal_post_confirmation_required",
                    "message": "Explicit Management confirmation is required before posting protected renewal-boundary EIR journals.",
                },
            )
        if body.total_debit != body.total_credit:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "renewal_boundary_eir_journal_post_confirmation_mismatch",
                    "message": "Confirmed renewal-boundary EIR debit and credit totals must be equal.",
                },
            )
        try:
            item = repository.post(
                actor_user_id=actor.user_id,
                renewal_execution_event_id=renewal_execution_event_id,
                expected_review_token=body.review_token,
                expected_entry_count=body.expected_entry_count,
                expected_total_debit=body.total_debit,
                expected_total_credit=body.total_credit,
            )
        except RenewalBoundaryEirJournalError as error:
            raise _exception(error) from error
        return {
            "success": True,
            "data": {"renewal_boundary_eir_journal_status": _status_payload(item)},
        }

    return router