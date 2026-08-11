from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .greenfield_regular_ledger_reconciliation_repository import (
    GreenfieldRegularLedgerReconciliationError,
    GreenfieldRegularLedgerReconciliationPreview,
    PostgresGreenfieldRegularLedgerReconciliationRepository,
)
from .request_auth import authenticated_device_context


def greenfield_regular_ledger_reconciliation_repository_dependency(
) -> PostgresGreenfieldRegularLedgerReconciliationRepository:
    return PostgresGreenfieldRegularLedgerReconciliationRepository()


def _decimal(value):
    return format(value, "f") if value is not None else None


def _reconciliation_payload(record: GreenfieldRegularLedgerReconciliationPreview):
    result = record.reconciliation
    if result is None:
        return None
    return {
        "disposition": result.disposition,
        "blocker_code": result.blocker_code,
        "message": result.message,
        "policy_version": result.policy_version,
        "expected_active_transaction_count": result.expected_active_transaction_count,
        "expected_journal_count": result.expected_journal_count,
        "exact_posted_journal_count": result.exact_posted_journal_count,
        "ignored_voided_reversed_journal_count": (
            result.ignored_voided_reversed_journal_count
        ),
        "unprotected_posted_journal_count": result.unprotected_posted_journal_count,
        "expected_loan_component_through_last_source": _decimal(
            result.expected_loan_component_through_last_source
        ),
        "expected_accrued_interest_through_last_source": _decimal(
            result.expected_accrued_interest_through_last_source
        ),
        "ledger_loan_component_through_last_source": _decimal(
            result.ledger_loan_component_through_last_source
        ),
        "ledger_accrued_interest_through_last_source": _decimal(
            result.ledger_accrued_interest_through_last_source
        ),
        "ledger_gross_carrying_through_last_source": _decimal(
            result.ledger_gross_carrying_through_last_source
        ),
        "target_gross_carrying_amount": _decimal(
            result.target_gross_carrying_amount
        ),
        "target_accrued_interest_component": _decimal(
            result.target_accrued_interest_component
        ),
        "target_loan_component": _decimal(result.target_loan_component),
        "tail_effective_interest_accrued": _decimal(
            result.tail_effective_interest_accrued
        ),
        "protected_regular_journals_reconciled": (
            result.protected_regular_journals_reconciled
        ),
        "target_ledger_reconciled": result.target_ledger_reconciled,
        "accounting_carrying_amount_ready": result.accounting_carrying_amount_ready,
        "journal_lines_enabled": result.journal_lines_enabled,
        "automatic_source_posting": result.automatic_source_posting,
    }


def _payload(record: GreenfieldRegularLedgerReconciliationPreview) -> dict[str, object]:
    return {
        "renewal_execution_event_id": str(record.renewal_execution_event_id),
        "renewal_disbursement_event_id": str(record.renewal_disbursement_event_id),
        "old_loan_id": str(record.old_loan_id),
        "old_loan_number": record.old_loan_number,
        "new_loan_id": str(record.new_loan_id),
        "new_loan_number": record.new_loan_number,
        "client_id": str(record.client_id),
        "client_code": record.client_code,
        "client_name": record.client_name,
        "target_date": record.target_date.isoformat(),
        "executed_at": record.executed_at.isoformat(),
        "old_loan_settlement_amount": _decimal(record.old_loan_settlement_amount),
        "anchor_posting_id": (
            str(record.anchor_posting_id) if record.anchor_posting_id else None
        ),
        "anchor_journal_entry_id": (
            str(record.anchor_journal_entry_id)
            if record.anchor_journal_entry_id
            else None
        ),
        "anchor_entry_number": record.anchor_entry_number,
        "anchor_date": record.anchor_date.isoformat() if record.anchor_date else None,
        "initial_gross_carrying_amount": _decimal(
            record.initial_gross_carrying_amount
        ),
        "initial_loan_component": _decimal(record.initial_loan_component),
        "initial_accrued_interest_component": _decimal(
            record.initial_accrued_interest_component
        ),
        "daily_eir": _decimal(record.daily_eir),
        "contractual_due_date": (
            record.contractual_due_date.isoformat()
            if record.contractual_due_date
            else None
        ),
        "rollforward_readiness_status": record.rollforward_readiness_status,
        "active_source_count": record.active_source_count,
        "protected_complete_active_source_count": (
            record.protected_complete_active_source_count
        ),
        "voided_posted_source_count": record.voided_posted_source_count,
        "voided_unreversed_source_count": record.voided_unreversed_source_count,
        "unprotected_posted_journal_count": record.unprotected_posted_journal_count,
        "reconciliation_readiness_status": record.reconciliation_readiness_status,
        "exact_reconciliation_preview_enabled": (
            record.exact_reconciliation_preview_enabled
        ),
        "reconciliation_policy_version": record.reconciliation_policy_version,
        "accounting_carrying_amount_ready": record.accounting_carrying_amount_ready,
        "journal_lines_enabled": record.journal_lines_enabled,
        "automatic_source_posting": record.automatic_source_posting,
        "reconciliation": _reconciliation_payload(record),
    }


def create_greenfield_regular_ledger_reconciliation_router() -> APIRouter:
    router = APIRouter(tags=["management greenfield Regular ledger reconciliation"])

    @router.get(
        "/api/v1/management/accounting/renewals/regular-greenfield-ledger-reconciliation/preview"
    )
    def list_greenfield_regular_ledger_reconciliation_preview(
        reconciliation_readiness_status: str | None = Query(
            default=None, max_length=120
        ),
        renewal_execution_event_id: UUID | None = Query(default=None),
        old_loan_id: UUID | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=250),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresGreenfieldRegularLedgerReconciliationRepository = Depends(
            greenfield_regular_ledger_reconciliation_repository_dependency
        ),
    ) -> dict[str, object]:
        authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.view",
            permission_error="Management accounting view permission is required.",
        )
        try:
            records = repository.list_previews(
                reconciliation_readiness_status=reconciliation_readiness_status,
                renewal_execution_event_id=renewal_execution_event_id,
                old_loan_id=old_loan_id,
                limit=limit,
            )
        except GreenfieldRegularLedgerReconciliationError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": error.code, "message": str(error)},
            ) from error
        return {
            "success": True,
            "data": {
                "reconciliation_policy_version": (
                    "greenfield_regular_ledger_reconciliation_v1"
                ),
                "read_only": True,
                "journal_lines_enabled": False,
                "automatic_source_posting": False,
                "notice": (
                    "Stage 5D.27 only reconciles immutable protected Regular "
                    "journal history to the greenfield EIR measurement. A positive "
                    "no-cash EIR tail at the renewal boundary remains blocked until "
                    "a separate protected renewal-boundary accrual path exists."
                ),
                "renewal_targets": [_payload(record) for record in records],
            },
        }

    return router
