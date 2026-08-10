from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .eir_cash_allocation import EirAllocationResult, EirCashAllocation
from .eir_cash_allocation_repository import (
    EirCashAllocationLoanNotFound,
    EirCashAllocationPack,
    PostgresEirCashAllocationRepository,
)
from .regular_accounting_sequence_preview import (
    RegularAccountingSequenceEntryPreview,
    RegularAccountingSequencePreview,
)
from .regular_collection_journal_preview import (
    RegularCollectionJournalLine,
    RegularCollectionJournalPreview,
)
from .regular_eir_accrual_journal_preview import (
    RegularEirAccrualJournalLine,
    RegularEirAccrualJournalPreview,
    RegularEirAccrualPeriodEvidence,
)
from .request_auth import authenticated_device_context


def eir_cash_allocation_repository_dependency() -> PostgresEirCashAllocationRepository:
    return PostgresEirCashAllocationRepository()


def _money(value: Decimal | None) -> str | None:
    return format(value, ".2f") if value is not None else None


def _exact_decimal(value: Decimal) -> str:
    return format(value, "f")


def _allocation_item_payload(item: EirCashAllocation) -> dict[str, object]:
    return {
        "transaction_id": str(item.transaction_id),
        "source_event_key": item.source_event_key,
        "collection_date": item.collection_date.isoformat(),
        "amount": _money(item.amount),
        "effective_interest_accrued_since_prior_event": _money(
            item.effective_interest_accrued_since_prior_event
        ),
        "gross_carrying_before": _money(item.gross_carrying_before),
        "accrued_interest_before": _money(item.accrued_interest_before),
        "loan_component_before": _money(item.loan_component_before),
        "cash_to_accrued_interest": _money(item.cash_to_accrued_interest),
        "cash_to_loan_component": _money(item.cash_to_loan_component),
        "gross_carrying_after": _money(item.gross_carrying_after),
        "accrued_interest_after": _money(item.accrued_interest_after),
        "loan_component_after": _money(item.loan_component_after),
        "posting_eligible": item.posting_eligible,
        "disposition": item.disposition,
        "message": item.message,
    }


def _result_payload(result: EirAllocationResult) -> dict[str, object]:
    return {
        "status": result.status,
        "message": result.message,
        "calculation_mode": result.calculation_mode,
        "cutover_date": result.cutover_date.isoformat(),
        "due_date": result.due_date.isoformat(),
        "daily_eir": str(result.daily_eir) if result.daily_eir is not None else None,
        "opening_gross_carrying_amount": _money(
            result.opening_gross_carrying_amount
        ),
        "opening_accrued_interest_component": _money(
            result.opening_accrued_interest_component
        ),
        "opening_loan_component": _money(result.opening_loan_component),
        "total_effective_interest_accrued": _money(
            result.total_effective_interest_accrued
        ),
        "closing_gross_carrying_amount": _money(
            result.closing_gross_carrying_amount
        ),
        "closing_accrued_interest_component": _money(
            result.closing_accrued_interest_component
        ),
        "closing_loan_component": _money(result.closing_loan_component),
        "posting_eligible": result.posting_eligible,
        "allocations": [
            _allocation_item_payload(item) for item in result.allocations
        ],
    }


def _journal_line_payload(line: RegularCollectionJournalLine) -> dict[str, object]:
    return {
        "account_system_key": line.account_system_key,
        "side": line.side,
        "amount": _money(line.amount),
        "label": line.label,
    }


def _journal_preview_payload(
    preview: RegularCollectionJournalPreview,
) -> dict[str, object]:
    return {
        "transaction_id": str(preview.transaction_id),
        "source_event_key": preview.source_event_key,
        "collection_date": preview.collection_date.isoformat(),
        "amount": _money(preview.amount),
        "required_eir_accrual_before_collection": _money(
            preview.required_eir_accrual_before_collection
        ),
        "disposition": preview.disposition,
        "posting_eligible": preview.posting_eligible,
        "message": preview.message,
        "proposed_lines": [
            _journal_line_payload(line) for line in preview.proposed_lines
        ],
        "total_debit": _money(preview.total_debit),
        "total_credit": _money(preview.total_credit),
        "balanced": preview.balanced,
    }


def _eir_accrual_line_payload(
    line: RegularEirAccrualJournalLine,
) -> dict[str, object]:
    return {
        "account_system_key": line.account_system_key,
        "side": line.side,
        "amount": _money(line.amount),
        "label": line.label,
    }


def _eir_accrual_period_evidence_payload(
    evidence: RegularEirAccrualPeriodEvidence,
) -> dict[str, object]:
    return {
        "fiscal_period_id": str(evidence.period_id),
        "fiscal_period_label": evidence.label,
        "fiscal_period_status": evidence.status,
        "period_start_date": evidence.period_start_date.isoformat(),
        "period_end_date": evidence.period_end_date.isoformat(),
        "accrual_start_date_inclusive": (
            evidence.accrual_start_date_inclusive.isoformat()
        ),
        "accrual_end_date_inclusive": (
            evidence.accrual_end_date_inclusive.isoformat()
        ),
        "day_count": evidence.day_count,
        "effective_interest_raw": _exact_decimal(
            evidence.effective_interest_raw
        ),
        "effective_interest_rounded": _money(
            evidence.effective_interest_rounded
        ),
    }


def _eir_accrual_preview_payload(
    preview: RegularEirAccrualJournalPreview,
) -> dict[str, object]:
    return {
        "transaction_id": str(preview.transaction_id),
        "related_collection_source_event_key": (
            preview.related_collection_source_event_key
        ),
        "source_event_key": preview.source_event_key,
        "accrual_start_date_exclusive": (
            preview.accrual_start_date_exclusive.isoformat()
        ),
        "accrual_end_date_inclusive": (
            preview.accrual_end_date_inclusive.isoformat()
        ),
        "posting_date": preview.posting_date.isoformat(),
        "fiscal_period_id": (
            str(preview.fiscal_period_id)
            if preview.fiscal_period_id is not None
            else None
        ),
        "fiscal_period_label": preview.fiscal_period_label,
        "fiscal_period_status": preview.fiscal_period_status,
        "amount": _money(preview.amount),
        "disposition": preview.disposition,
        "posting_eligible": preview.posting_eligible,
        "message": preview.message,
        "proposed_lines": [
            _eir_accrual_line_payload(line) for line in preview.proposed_lines
        ],
        "total_debit": _money(preview.total_debit),
        "total_credit": _money(preview.total_credit),
        "balanced": preview.balanced,
        "period_split_evidence": [
            _eir_accrual_period_evidence_payload(evidence)
            for evidence in preview.period_split_evidence
        ],
        "period_rounded_total": _money(preview.period_rounded_total),
        "rounding_residual": _money(preview.rounding_residual),
        "split_policy_required": preview.split_policy_required,
    }


def _accounting_sequence_entry_payload(
    entry: RegularAccountingSequenceEntryPreview,
) -> dict[str, object]:
    return {
        "sequence_order": entry.sequence_order,
        "entry_type": entry.entry_type,
        "source_event_key": entry.source_event_key,
        "posting_date": entry.posting_date.isoformat(),
        "amount": _money(entry.amount),
        "disposition": entry.disposition,
    }


def _accounting_sequence_preview_payload(
    preview: RegularAccountingSequencePreview,
) -> dict[str, object]:
    return {
        "transaction_id": str(preview.transaction_id),
        "sequence_key": preview.sequence_key,
        "collection_source_event_key": preview.collection_source_event_key,
        "collection_date": preview.collection_date.isoformat(),
        "required_eir_accrual_before_collection": _money(
            preview.required_eir_accrual_before_collection
        ),
        "disposition": preview.disposition,
        "blocker_code": preview.blocker_code,
        "posting_eligible": preview.posting_eligible,
        "message": preview.message,
        "ordered_entries": [
            _accounting_sequence_entry_payload(entry)
            for entry in preview.ordered_entries
        ],
    }


def _pack_payload(pack: EirCashAllocationPack) -> dict[str, object]:
    return {
        "loan_id": str(pack.loan_id),
        "loan_number": pack.loan_number,
        "client_name": pack.client_name,
        "cutover_date": (
            pack.cutover_date.isoformat() if pack.cutover_date is not None else None
        ),
        "opening_balance_prepared": pack.opening_balance_prepared,
        "opening_balance_posted": pack.opening_balance_posted,
        "opening_balance_entry_number": pack.opening_balance_entry_number,
        "protected_snapshot_available": pack.protected_snapshot_available,
        "protected_snapshot_reconciled": pack.protected_snapshot_reconciled,
        "protected_snapshot_blocker": pack.protected_snapshot_blocker,
        "source_event_count": pack.source_event_count,
        "source_history_complete": pack.source_history_complete,
        "blocker_code": pack.blocker_code,
        "blocker_message": pack.blocker_message,
        "automatic_source_posting_enabled": pack.automatic_source_posting_enabled,
        "account_configuration_ready": pack.account_configuration_ready,
        "account_configuration_blocker": pack.account_configuration_blocker,
        "eir_accrual_account_configuration_ready": (
            pack.eir_accrual_account_configuration_ready
        ),
        "eir_accrual_account_configuration_blocker": (
            pack.eir_accrual_account_configuration_blocker
        ),
        "eir_accrual_previews": [
            _eir_accrual_preview_payload(preview)
            for preview in pack.eir_accrual_previews
        ],
        "collection_journal_previews": [
            _journal_preview_payload(preview)
            for preview in pack.collection_journal_previews
        ],
        "accounting_sequence_previews": [
            _accounting_sequence_preview_payload(preview)
            for preview in pack.accounting_sequence_previews
        ],
        "allocation": (
            _result_payload(pack.allocation) if pack.allocation is not None else None
        ),
        "notice": (
            "Read-only event-date EIR cash allocation plus fiscal-period-aware "
            "Regular EIR accrual and collection journal-line previews. Accrual "
            "lines appear only when one open fiscal period covers the full "
            "recognized interval. Cross-period intervals expose exact raw and "
            "independently rounded period evidence but remain fail-closed until "
            "Management approves how any residual cent is allocated. Exact ready "
            "previews are also paired into an all-or-none sequence in which the "
            "required EIR accrual precedes its matching collection. No journal "
            "draft, posted entry, lending mutation, or automatic source posting "
            "is created by this endpoint."
        ),
    }


def create_eir_cash_allocation_router() -> APIRouter:
    router = APIRouter(tags=["management EIR cash allocation"])

    @router.get(
        "/api/v1/management/financial-accounting/eir-cash-allocation/{loan_id}"
    )
    @router.get(
        "/api/mobile/v1/management/financial-accounting/eir-cash-allocation/{loan_id}",
        include_in_schema=False,
    )
    def eir_cash_allocation(
        loan_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresEirCashAllocationRepository = Depends(
            eir_cash_allocation_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.view",
            permission_error="Financial Accounting view permission is required.",
        )
        if "management" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "management_role_required",
                    "message": "Management access is required for EIR cash allocation.",
                },
            )
        try:
            pack = repository.load_loan_allocation(loan_id=loan_id)
        except EirCashAllocationLoanNotFound as error:
            raise HTTPException(
                status_code=404,
                detail={"code": error.code, "message": str(error)},
            ) from error
        return {"success": True, "data": {"eir_cash_allocation": _pack_payload(pack)}}

    return router
