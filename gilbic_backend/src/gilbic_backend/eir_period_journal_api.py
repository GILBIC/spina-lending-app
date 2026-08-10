from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from psycopg.rows import dict_row

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .database import open_connection
from .eir_cash_allocation_repository import (
    EirCashAllocationLoanNotFound,
    EirCashAllocationPack,
    PostgresEirCashAllocationRepository,
)
from .regular_eir_accrual_journal_preview import AccountingFiscalPeriodReference
from .regular_eir_period_journal_preview import (
    RegularEirFiscalPeriodJournalProposal,
    RegularEirPeriodJournalProposalPreview,
    build_regular_eir_period_journal_proposal_preview,
)
from .request_auth import authenticated_device_context


@dataclass(frozen=True, slots=True)
class RegularEirPeriodJournalApiResult:
    status: str
    blocker_code: str | None
    blocker_message: str | None
    previews: tuple[RegularEirPeriodJournalProposalPreview, ...]
    posting_eligible: bool = False
    automatic_source_posting_enabled: bool = False


class PostgresEirPeriodJournalProposalRepository:
    """Read-only Stage 5D.9 context loader.

    The existing EIR allocation repository remains the source of protected cash,
    daily-EIR, accrual-preview, cutover, account, and source-history controls.
    This adapter independently reloads only the protected fiscal-period references
    needed by the already-proven Stage 5D.8 mapper. It performs no write.
    """

    def __init__(
        self,
        *,
        allocation_repository: PostgresEirCashAllocationRepository | None = None,
    ) -> None:
        self._allocation_repository = (
            allocation_repository or PostgresEirCashAllocationRepository()
        )

    def load_loan_context(
        self,
        *,
        loan_id: UUID,
    ) -> tuple[EirCashAllocationPack, tuple[AccountingFiscalPeriodReference, ...]]:
        pack = self._allocation_repository.load_loan_allocation(loan_id=loan_id)
        if pack.cutover_date is None or pack.blocker_code is not None:
            return pack, ()

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select id, label, start_date, end_date, status
                    from accounting.fiscal_periods
                    where end_date > %s
                    order by start_date, end_date, id
                    """,
                    (pack.cutover_date,),
                )
                periods = tuple(
                    AccountingFiscalPeriodReference(
                        period_id=UUID(str(row["id"])),
                        label=str(row["label"]),
                        start_date=row["start_date"],
                        end_date=row["end_date"],
                        status=str(row["status"]),
                    )
                    for row in cursor.fetchall()
                )
        return pack, periods


def eir_period_journal_repository_dependency() -> PostgresEirPeriodJournalProposalRepository:
    return PostgresEirPeriodJournalProposalRepository()


def _blocked_result(
    *,
    blocker_code: str,
    blocker_message: str,
) -> RegularEirPeriodJournalApiResult:
    return RegularEirPeriodJournalApiResult(
        status="eir_period_journal_preview_blocked",
        blocker_code=blocker_code,
        blocker_message=blocker_message,
        previews=(),
    )


def build_regular_eir_period_journal_api_result(
    pack: EirCashAllocationPack,
    *,
    protected_fiscal_periods: tuple[AccountingFiscalPeriodReference, ...],
) -> RegularEirPeriodJournalApiResult:
    """Expose Stage 5D.8 evidence as one fail-closed read-only API result."""

    if pack.automatic_source_posting_enabled:
        return _blocked_result(
            blocker_code="eir_period_journal_automatic_posting_control_review",
            blocker_message=(
                "The source allocation pack unexpectedly enables automatic source "
                "posting. Per-period journal proposals remain blocked."
            ),
        )
    if pack.blocker_code is not None:
        return _blocked_result(
            blocker_code=pack.blocker_code,
            blocker_message=(
                pack.blocker_message
                or "The protected EIR cash-allocation source is blocked."
            ),
        )
    if not pack.source_history_complete:
        return _blocked_result(
            blocker_code="source_history_incomplete",
            blocker_message=(
                "Complete protected source history is required before per-period "
                "Regular EIR journal proposals can be exposed."
            ),
        )
    if pack.allocation is None:
        return _blocked_result(
            blocker_code="eir_cash_allocation_required",
            blocker_message=(
                "A protected read-only EIR cash allocation is required before "
                "per-period journal proposals can be exposed."
            ),
        )
    if pack.allocation.posting_eligible:
        return _blocked_result(
            blocker_code="eir_period_journal_source_posting_control_review",
            blocker_message=(
                "The protected EIR allocation unexpectedly claims posting "
                "eligibility. Per-period proposals remain blocked."
            ),
        )

    allocations = pack.allocation.allocations
    accrual_previews = pack.eir_accrual_previews
    allocation_ids = tuple(item.transaction_id for item in allocations)
    preview_ids = tuple(preview.transaction_id for preview in accrual_previews)
    if (
        len(accrual_previews) != len(allocations)
        or len(set(allocation_ids)) != len(allocation_ids)
        or len(set(preview_ids)) != len(preview_ids)
        or set(preview_ids) != set(allocation_ids)
    ):
        return _blocked_result(
            blocker_code="eir_period_source_preview_set_not_exact",
            blocker_message=(
                "Protected EIR allocations and accrual previews do not form one "
                "complete unique transaction set. No per-period proposals are "
                "exposed."
            ),
        )

    permitted_source_dispositions = {
        "eir_accrual_journal_lines_preview_ready",
        "no_eir_accrual_required",
        "fiscal_period_split_allocation_preview_ready",
    }
    unexpected_source = next(
        (
            preview
            for preview in accrual_previews
            if preview.disposition not in permitted_source_dispositions
        ),
        None,
    )
    if unexpected_source is not None:
        return _blocked_result(
            blocker_code=unexpected_source.disposition,
            blocker_message=(
                "An upstream Regular EIR accrual preview is not in a permitted "
                "read-only state. No per-period proposals are exposed."
            ),
        )

    candidates = tuple(
        preview
        for preview in accrual_previews
        if preview.disposition == "fiscal_period_split_allocation_preview_ready"
    )
    if not candidates:
        return RegularEirPeriodJournalApiResult(
            status="no_cross_period_eir_journal_required",
            blocker_code=None,
            blocker_message=None,
            previews=(),
        )

    allocation_by_transaction = {
        item.transaction_id: item
        for item in allocations
    }
    results: list[RegularEirPeriodJournalProposalPreview] = []
    for preview in candidates:
        protected_allocation = allocation_by_transaction.get(preview.transaction_id)
        if protected_allocation is None:
            return _blocked_result(
                blocker_code="eir_period_protected_allocation_missing",
                blocker_message=(
                    "A cross-period EIR preview is missing its exact protected "
                    "source allocation. No per-period proposals are exposed."
                ),
            )
        result = build_regular_eir_period_journal_proposal_preview(
            preview,
            protected_allocation=protected_allocation,
            protected_fiscal_periods=protected_fiscal_periods,
        )
        if (
            result.disposition != "eir_period_journal_lines_preview_ready"
            or result.blocker_code is not None
            or not result.balanced
            or result.posting_eligible
            or result.automatic_source_posting_enabled
        ):
            return _blocked_result(
                blocker_code=(
                    result.blocker_code
                    or "eir_period_journal_preview_not_exact"
                ),
                blocker_message=result.message,
            )
        results.append(result)

    return RegularEirPeriodJournalApiResult(
        status="eir_period_journal_preview_ready",
        blocker_code=None,
        blocker_message=None,
        previews=tuple(results),
    )


def _money(value: Decimal) -> str:
    return format(value, ".2f")


def _line_payload(line) -> dict[str, object]:
    return {
        "account_system_key": line.account_system_key,
        "side": line.side,
        "amount": _money(line.amount),
        "label": line.label,
    }


def _period_proposal_payload(
    proposal: RegularEirFiscalPeriodJournalProposal,
) -> dict[str, object]:
    return {
        "fiscal_period_id": str(proposal.fiscal_period_id),
        "fiscal_period_label": proposal.fiscal_period_label,
        "period_start_date": proposal.period_start_date.isoformat(),
        "period_end_date": proposal.period_end_date.isoformat(),
        "accrual_start_date_inclusive": (
            proposal.accrual_start_date_inclusive.isoformat()
        ),
        "accrual_end_date_inclusive": proposal.accrual_end_date_inclusive.isoformat(),
        "allocated_amount": _money(proposal.allocated_amount),
        "disposition": proposal.disposition,
        "proposed_lines": [_line_payload(line) for line in proposal.proposed_lines],
        "total_debit": _money(proposal.total_debit),
        "total_credit": _money(proposal.total_credit),
        "balanced": proposal.balanced,
        "posting_eligible": proposal.posting_eligible,
    }


def _preview_payload(
    preview: RegularEirPeriodJournalProposalPreview,
) -> dict[str, object]:
    return {
        "transaction_id": str(preview.transaction_id),
        "related_collection_source_event_key": (
            preview.related_collection_source_event_key
        ),
        "source_event_key": preview.source_event_key,
        "amount": _money(preview.amount),
        "period_split_policy_version": preview.period_split_policy_version,
        "journal_preview_policy_version": preview.journal_preview_policy_version,
        "period_allocated_total": _money(preview.period_allocated_total),
        "unallocated_residual": _money(preview.unallocated_residual),
        "disposition": preview.disposition,
        "blocker_code": preview.blocker_code,
        "message": preview.message,
        "period_proposals": [
            _period_proposal_payload(proposal)
            for proposal in preview.period_proposals
        ],
        "total_debit": _money(preview.total_debit),
        "total_credit": _money(preview.total_credit),
        "balanced": preview.balanced,
        "posting_eligible": preview.posting_eligible,
        "automatic_source_posting_enabled": (
            preview.automatic_source_posting_enabled
        ),
    }


def _api_payload(
    pack: EirCashAllocationPack,
    result: RegularEirPeriodJournalApiResult,
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
        "period_journal_previews": [
            _preview_payload(preview) for preview in result.previews
        ],
        "notice": (
            "Stage 5D.9 read-only Management exposure of the protected Stage "
            "5D.8 per-fiscal-period Regular EIR journal-line proposals. This "
            "endpoint creates no journal draft, posting date, posting identity, "
            "posted entry, lending mutation, or automatic source posting. The "
            "existing cross-period Regular accounting-sequence composer remains "
            "unchanged and fail-closed."
        ),
    }


def create_eir_period_journal_router() -> APIRouter:
    router = APIRouter(tags=["management EIR period journal preview"])

    @router.get(
        "/api/v1/management/financial-accounting/eir-period-journal-proposals/{loan_id}"
    )
    @router.get(
        "/api/mobile/v1/management/financial-accounting/eir-period-journal-proposals/{loan_id}",
        include_in_schema=False,
    )
    def eir_period_journal_proposals(
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
                        "Management access is required for per-period EIR journal "
                        "proposals."
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

        result = build_regular_eir_period_journal_api_result(
            pack,
            protected_fiscal_periods=protected_fiscal_periods,
        )
        return {
            "success": True,
            "data": {
                "eir_period_journal_proposals": _api_payload(pack, result)
            },
        }

    return router
