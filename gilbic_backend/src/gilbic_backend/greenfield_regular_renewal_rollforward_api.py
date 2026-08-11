from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .greenfield_regular_renewal_rollforward_repository import (
    GreenfieldRegularRenewalRollForwardError,
    GreenfieldRegularRenewalRollForwardPreview,
    PostgresGreenfieldRegularRenewalRollForwardRepository,
)
from .request_auth import authenticated_device_context


def greenfield_regular_renewal_rollforward_repository_dependency(
) -> PostgresGreenfieldRegularRenewalRollForwardRepository:
    return PostgresGreenfieldRegularRenewalRollForwardRepository()


def _decimal(value):
    return format(value, "f") if value is not None else None


def _rollforward_payload(record: GreenfieldRegularRenewalRollForwardPreview):
    preview = record.rollforward
    if preview is None:
        return None
    return {
        "disposition": preview.disposition,
        "blocker_code": preview.blocker_code,
        "message": preview.message,
        "policy_version": preview.policy_version,
        "source_event_count": preview.source_event_count,
        "allocation_count": preview.allocation_count,
        "daily_eir": _decimal(preview.daily_eir),
        "initial_gross_carrying_amount": _decimal(
            preview.initial_gross_carrying_amount
        ),
        "initial_accrued_interest_component": _decimal(
            preview.initial_accrued_interest_component
        ),
        "initial_loan_component": _decimal(preview.initial_loan_component),
        "total_effective_interest_accrued": _decimal(
            preview.total_effective_interest_accrued
        ),
        "tail_effective_interest_accrued": _decimal(
            preview.tail_effective_interest_accrued
        ),
        "gross_carrying_amount_at_target": _decimal(
            preview.gross_carrying_amount_at_target
        ),
        "accrued_interest_component_at_target": _decimal(
            preview.accrued_interest_component_at_target
        ),
        "loan_component_at_target": _decimal(
            preview.loan_component_at_target
        ),
        "tail_accrual_day_count": len(preview.tail_daily_accruals),
        "measurement_preview_ready": preview.measurement_preview_ready,
        "accounting_carrying_amount_ready": preview.accounting_carrying_amount_ready,
        "journal_lines_enabled": preview.journal_lines_enabled,
        "automatic_source_posting": preview.automatic_source_posting,
        "allocations": [
            {
                "transaction_id": str(item.transaction_id),
                "source_event_key": item.source_event_key,
                "collection_date": item.collection_date.isoformat(),
                "amount": _decimal(item.amount),
                "effective_interest_accrued_since_prior_event": _decimal(
                    item.effective_interest_accrued_since_prior_event
                ),
                "gross_carrying_before": _decimal(item.gross_carrying_before),
                "accrued_interest_before": _decimal(item.accrued_interest_before),
                "loan_component_before": _decimal(item.loan_component_before),
                "cash_to_accrued_interest": _decimal(
                    item.cash_to_accrued_interest
                ),
                "cash_to_loan_component": _decimal(item.cash_to_loan_component),
                "gross_carrying_after": _decimal(item.gross_carrying_after),
                "accrued_interest_after": _decimal(item.accrued_interest_after),
                "loan_component_after": _decimal(item.loan_component_after),
                "disposition": item.disposition,
                "posting_eligible": item.posting_eligible,
            }
            for item in preview.allocations
        ],
    }


def _payload(record: GreenfieldRegularRenewalRollForwardPreview) -> dict[str, object]:
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
        "execution_external_reference": record.execution_external_reference,
        "renewal_source_readiness_status": record.renewal_source_readiness_status,
        "renewal_source_event_key": record.renewal_source_event_key,
        "anchor_posting_id": (
            str(record.anchor_posting_id) if record.anchor_posting_id else None
        ),
        "anchor_disbursement_event_id": (
            str(record.anchor_disbursement_event_id)
            if record.anchor_disbursement_event_id
            else None
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
        "daily_eir_percent": _decimal(record.daily_eir_percent),
        "contractual_due_date": (
            record.contractual_due_date.isoformat()
            if record.contractual_due_date
            else None
        ),
        "schedule_id": str(record.schedule_id) if record.schedule_id else None,
        "contract_reference": record.contract_reference,
        "contract_evidence_reference": record.contract_evidence_reference,
        "anchor_readiness_status": record.anchor_readiness_status,
        "anchor_source_key": record.anchor_source_key,
        "source_event_count_before_target": record.source_event_count_before_target,
        "same_day_target_collection_count": record.same_day_target_collection_count,
        "readiness_status": record.readiness_status,
        "target_source_key": record.target_source_key,
        "rollforward_policy_version": record.rollforward_policy_version,
        "measurement_preview_enabled": record.measurement_preview_enabled,
        "accounting_carrying_amount_ready": record.accounting_carrying_amount_ready,
        "journal_lines_enabled": record.journal_lines_enabled,
        "automatic_source_posting": record.automatic_source_posting,
        "rollforward": _rollforward_payload(record),
    }


def create_greenfield_regular_renewal_rollforward_router() -> APIRouter:
    router = APIRouter(tags=["management greenfield Regular renewal roll-forward"])

    @router.get(
        "/api/v1/management/accounting/renewals/regular-greenfield-rollforward/preview"
    )
    def list_greenfield_regular_renewal_rollforward_preview(
        readiness_status: str | None = Query(default=None, max_length=120),
        renewal_execution_event_id: UUID | None = Query(default=None),
        old_loan_id: UUID | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=250),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresGreenfieldRegularRenewalRollForwardRepository = Depends(
            greenfield_regular_renewal_rollforward_repository_dependency
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
                readiness_status=readiness_status,
                renewal_execution_event_id=renewal_execution_event_id,
                old_loan_id=old_loan_id,
                limit=limit,
            )
        except GreenfieldRegularRenewalRollForwardError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": error.code, "message": str(error)},
            ) from error
        return {
            "success": True,
            "data": {
                "rollforward_policy_version": (
                    "greenfield_regular_renewal_rollforward_v1"
                ),
                "measurement_preview_only": True,
                "accounting_carrying_amount_ready": False,
                "journal_lines_enabled": False,
                "automatic_source_posting": False,
                "renewal_targets": [_payload(record) for record in records],
            },
        }

    return router
