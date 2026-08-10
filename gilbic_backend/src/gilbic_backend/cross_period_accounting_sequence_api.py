from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .eir_cash_allocation_repository import (
    EirCashAllocationLoanNotFound,
    EirCashAllocationPack,
)
from .eir_period_journal_api import (
    PostgresEirPeriodJournalProposalRepository,
    build_regular_eir_period_journal_api_result,
    eir_period_journal_repository_dependency,
)
from .regular_cross_period_accounting_sequence_preview import (
    RegularCrossPeriodAccountingSequenceEntryPreview,
    RegularCrossPeriodAccountingSequencePreview,
    build_regular_cross_period_accounting_sequence_preview,
)
from .regular_eir_accrual_journal_preview import AccountingFiscalPeriodReference
from .request_auth import authenticated_device_context


@dataclass(frozen=True, slots=True)
class RegularCrossPeriodAccountingSequenceApiResult:
    status: str
    blocker_code: str | None
    blocker_message: str | None
    previews: tuple[RegularCrossPeriodAccountingSequencePreview, ...]
    posting_eligible: bool = False
    automatic_source_posting_enabled: bool = False


def _blocked_result(
    *,
    blocker_code: str,
    blocker_message: str,
) -> RegularCrossPeriodAccountingSequenceApiResult:
    return RegularCrossPeriodAccountingSequenceApiResult(
        status="cross_period_accounting_sequence_preview_blocked",
        blocker_code=blocker_code,
        blocker_message=blocker_message,
        previews=(),
    )


def build_regular_cross_period_accounting_sequence_api_result(
    pack: EirCashAllocationPack,
    *,
    protected_fiscal_periods: tuple[AccountingFiscalPeriodReference, ...],
) -> RegularCrossPeriodAccountingSequenceApiResult:
    """Expose only exact Stage 5D.10 sequence evidence; never create a journal."""

    period_result = build_regular_eir_period_journal_api_result(
        pack,
        protected_fiscal_periods=protected_fiscal_periods,
    )
    if period_result.posting_eligible or period_result.automatic_source_posting_enabled:
        return _blocked_result(
            blocker_code="cross_period_sequence_api_posting_control_review",
            blocker_message=(
                "The protected per-period API result unexpectedly enables posting. "
                "Cross-period sequence exposure remains blocked."
            ),
        )
    if period_result.blocker_code is not None:
        return _blocked_result(
            blocker_code=period_result.blocker_code,
            blocker_message=(
                period_result.blocker_message
                or "The protected per-period EIR journal evidence is blocked."
            ),
        )
    if period_result.status == "no_cross_period_eir_journal_required":
        return RegularCrossPeriodAccountingSequenceApiResult(
            status="no_cross_period_accounting_sequence_required",
            blocker_code=None,
            blocker_message=None,
            previews=(),
        )
    if period_result.status != "eir_period_journal_preview_ready":
        return _blocked_result(
            blocker_code="cross_period_sequence_period_api_state_review",
            blocker_message=(
                "The protected per-period EIR API returned an unexpected state. "
                "No cross-period sequence is exposed."
            ),
        )

    if pack.allocation is None:
        return _blocked_result(
            blocker_code="cross_period_sequence_allocation_required",
            blocker_message="Protected EIR allocation evidence is required.",
        )

    allocations = pack.allocation.allocations
    collections = pack.collection_journal_previews
    legacy_sequences = pack.accounting_sequence_previews
    allocation_ids = tuple(item.transaction_id for item in allocations)
    collection_ids = tuple(item.transaction_id for item in collections)
    legacy_ids = tuple(item.transaction_id for item in legacy_sequences)
    if (
        len(collections) != len(allocations)
        or len(legacy_sequences) != len(allocations)
        or len(set(allocation_ids)) != len(allocation_ids)
        or len(set(collection_ids)) != len(collection_ids)
        or len(set(legacy_ids)) != len(legacy_ids)
        or set(collection_ids) != set(allocation_ids)
        or set(legacy_ids) != set(allocation_ids)
    ):
        return _blocked_result(
            blocker_code="cross_period_sequence_source_preview_set_not_exact",
            blocker_message=(
                "Protected allocations, collection previews, and existing accounting "
                "sequence previews do not form one complete unique transaction set."
            ),
        )

    collection_by_transaction = {item.transaction_id: item for item in collections}
    legacy_by_transaction = {item.transaction_id: item for item in legacy_sequences}
    results: list[RegularCrossPeriodAccountingSequencePreview] = []
    for period_preview in period_result.previews:
        transaction_id = period_preview.transaction_id
        collection = collection_by_transaction.get(transaction_id)
        legacy = legacy_by_transaction.get(transaction_id)
        if collection is None or legacy is None:
            return _blocked_result(
                blocker_code="cross_period_sequence_protected_preview_missing",
                blocker_message=(
                    "A cross-period transaction is missing its exact protected "
                    "collection or existing sequence preview."
                ),
            )
        if (
            legacy.posting_eligible
            or legacy.disposition != "regular_accounting_sequence_preview_blocked"
            or legacy.blocker_code != "fiscal_period_split_allocation_preview_ready"
            or legacy.ordered_entries != ()
        ):
            return _blocked_result(
                blocker_code="cross_period_sequence_legacy_boundary_not_closed",
                blocker_message=(
                    "The existing accounting-sequence path is not still fail-closed "
                    "for this cross-period transaction. Stage 5D.11 will not expose "
                    "a parallel sequence."
                ),
            )

        sequence = build_regular_cross_period_accounting_sequence_preview(
            period_preview,
            collection,
        )
        if (
            sequence.disposition
            != "regular_cross_period_accounting_sequence_preview_ready"
            or sequence.blocker_code is not None
            or sequence.posting_eligible
            or sequence.automatic_source_posting_enabled
            or not sequence.ordered_entries
            or sequence.ordered_entries[-1].entry_type != "collection"
            or any(entry.posting_eligible for entry in sequence.ordered_entries)
        ):
            return _blocked_result(
                blocker_code=(
                    sequence.blocker_code
                    or "cross_period_accounting_sequence_preview_not_exact"
                ),
                blocker_message=sequence.message,
            )
        results.append(sequence)

    if len({preview.transaction_id for preview in results}) != len(results):
        return _blocked_result(
            blocker_code="cross_period_sequence_api_identity_conflict",
            blocker_message="Cross-period sequence transaction identities must be unique.",
        )

    return RegularCrossPeriodAccountingSequenceApiResult(
        status="cross_period_accounting_sequence_preview_ready",
        blocker_code=None,
        blocker_message=None,
        previews=tuple(results),
    )


def _money(value: Decimal) -> str:
    return format(value, ".2f")


def _entry_payload(
    entry: RegularCrossPeriodAccountingSequenceEntryPreview,
) -> dict[str, object]:
    return {
        "sequence_order": entry.sequence_order,
        "entry_type": entry.entry_type,
        "preview_entry_key": entry.preview_entry_key,
        "related_source_event_key": entry.related_source_event_key,
        "recognition_date": entry.recognition_date.isoformat(),
        "amount": _money(entry.amount),
        "fiscal_period_id": (
            str(entry.fiscal_period_id) if entry.fiscal_period_id is not None else None
        ),
        "disposition": entry.disposition,
        "posting_eligible": entry.posting_eligible,
    }


def _sequence_payload(
    preview: RegularCrossPeriodAccountingSequencePreview,
) -> dict[str, object]:
    return {
        "transaction_id": str(preview.transaction_id),
        "sequence_key": preview.sequence_key,
        "collection_source_event_key": preview.collection_source_event_key,
        "collection_date": preview.collection_date.isoformat(),
        "required_eir_accrual_before_collection": _money(
            preview.required_eir_accrual_before_collection
        ),
        "sequence_policy_version": preview.sequence_policy_version,
        "disposition": preview.disposition,
        "blocker_code": preview.blocker_code,
        "posting_eligible": preview.posting_eligible,
        "automatic_source_posting_enabled": (
            preview.automatic_source_posting_enabled
        ),
        "ordered_entries": [
            _entry_payload(entry) for entry in preview.ordered_entries
        ],
        "zero_cent_fiscal_period_ids": [
            str(period_id) for period_id in preview.zero_cent_fiscal_period_ids
        ],
    }


def _api_payload(
    pack: EirCashAllocationPack,
    result: RegularCrossPeriodAccountingSequenceApiResult,
) -> dict[str, object]:
    return {
        "loan_id": str(pack.loan_id),
        "loan_number": pack.loan_number,
        "client_name": pack.client_name,
        "cutover_date": (
            pack.cutover_date.isoformat() if pack.cutover_date is not None else None
        ),
        "source_event_count": pack.source_event_count,
        "source_history_complete": pack.source_history_complete,
        "status": result.status,
        "blocker_code": result.blocker_code,
        "blocker_message": result.blocker_message,
        "posting_eligible": result.posting_eligible,
        "automatic_source_posting_enabled": (
            result.automatic_source_posting_enabled
        ),
        "sequence_previews": [
            _sequence_payload(preview) for preview in result.previews
        ],
        "notice": (
            "Stage 5D.11 Management-only read-only exposure of the protected Stage "
            "5D.10 cross-period Regular accounting sequence. `recognition_date` is "
            "audit/order evidence only and is not a journal posting date. Preview "
            "keys are not posting source identities. This endpoint creates no "
            "journal draft, database write, posting identity, posted entry, lending "
            "mutation, or automatic source posting."
        ),
    }


def create_cross_period_accounting_sequence_router() -> APIRouter:
    router = APIRouter(tags=["management cross-period accounting sequence preview"])

    @router.get(
        "/api/v1/management/financial-accounting/cross-period-accounting-sequences/{loan_id}"
    )
    @router.get(
        "/api/mobile/v1/management/financial-accounting/cross-period-accounting-sequences/{loan_id}",
        include_in_schema=False,
    )
    def cross_period_accounting_sequences(
        loan_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresEirPeriodJournalProposalRepository = Depends(
            eir_period_journal_repository_dependency
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
                    "message": (
                        "Management access is required for protected cross-period "
                        "accounting sequence previews."
                    ),
                },
            )

        try:
            pack, protected_fiscal_periods = repository.load_loan_context(
                loan_id=loan_id
            )
        except EirCashAllocationLoanNotFound as error:
            raise HTTPException(
                status_code=404,
                detail={"code": error.code, "message": str(error)},
            ) from error

        result = build_regular_cross_period_accounting_sequence_api_result(
            pack,
            protected_fiscal_periods=protected_fiscal_periods,
        )
        return {
            "success": True,
            "data": {
                "cross_period_accounting_sequences": _api_payload(pack, result)
            },
        }

    return router
