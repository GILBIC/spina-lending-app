from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .cross_period_accounting_sequence_api import (
    build_regular_cross_period_accounting_sequence_api_result,
)
from .eir_cash_allocation_repository import EirCashAllocationLoanNotFound, EirCashAllocationPack
from .eir_period_journal_api import (
    PostgresEirPeriodJournalProposalRepository,
    build_regular_eir_period_journal_api_result,
    eir_period_journal_repository_dependency,
)
from .regular_cross_period_posting_coordinate_preview import (
    build_regular_cross_period_posting_coordinate_preview,
)
from .regular_cross_period_posting_identity_preview import (
    build_regular_cross_period_posting_identity_preview,
)
from .regular_cross_period_posting_ready_evidence import (
    RegularCrossPeriodPostingReadyEntryEvidence,
    RegularCrossPeriodPostingReadyEvidenceBundle,
    RegularCrossPeriodPostingReadyJournalLineEvidence,
    build_regular_cross_period_posting_ready_evidence_bundle,
)
from .regular_eir_accrual_journal_preview import AccountingFiscalPeriodReference
from .request_auth import authenticated_device_context


@dataclass(frozen=True, slots=True)
class RegularPostingReadyEvidenceReviewApiResult:
    status: str
    blocker_code: str | None
    blocker_message: str | None
    bundles: tuple[RegularCrossPeriodPostingReadyEvidenceBundle, ...]
    posting_eligible: bool = False
    automatic_source_posting_enabled: bool = False
    review_only: bool = True


def _blocked_result(
    *,
    blocker_code: str,
    blocker_message: str,
) -> RegularPostingReadyEvidenceReviewApiResult:
    return RegularPostingReadyEvidenceReviewApiResult(
        status="regular_posting_ready_evidence_review_blocked",
        blocker_code=blocker_code,
        blocker_message=blocker_message,
        bundles=(),
    )


def build_regular_posting_ready_evidence_review_api_result(
    pack: EirCashAllocationPack,
    *,
    protected_fiscal_periods: tuple[AccountingFiscalPeriodReference, ...],
) -> RegularPostingReadyEvidenceReviewApiResult:
    """Expose Stage 5D.14 only after exact all-or-none protected replay.

    This Stage 5D.15 adapter is intentionally read-only. It rebuilds the protected
    Stage 5D.10 sequence and Stage 5D.8 period-journal evidence, then derives the
    Stage 5D.12 coordinates, Stage 5D.13 posting identities, and Stage 5D.14 fused
    evidence bundle. No journal draft, persistence row, posting action, or automatic
    source-posting permission is created here.
    """

    sequence_result = build_regular_cross_period_accounting_sequence_api_result(
        pack,
        protected_fiscal_periods=protected_fiscal_periods,
    )
    if sequence_result.posting_eligible or sequence_result.automatic_source_posting_enabled:
        return _blocked_result(
            blocker_code="posting_ready_review_sequence_posting_control_review",
            blocker_message=(
                "The protected cross-period sequence API unexpectedly enables posting. "
                "Posting-ready Management review remains blocked."
            ),
        )
    if sequence_result.blocker_code is not None:
        return _blocked_result(
            blocker_code=sequence_result.blocker_code,
            blocker_message=(
                sequence_result.blocker_message
                or "The protected cross-period accounting sequence is blocked."
            ),
        )
    if sequence_result.status == "no_cross_period_accounting_sequence_required":
        return RegularPostingReadyEvidenceReviewApiResult(
            status="no_cross_period_posting_ready_evidence_required",
            blocker_code=None,
            blocker_message=None,
            bundles=(),
        )
    if sequence_result.status != "cross_period_accounting_sequence_preview_ready":
        return _blocked_result(
            blocker_code="posting_ready_review_sequence_state_review",
            blocker_message=(
                "The protected cross-period sequence API returned an unexpected state. "
                "No posting-ready evidence is exposed."
            ),
        )

    period_result = build_regular_eir_period_journal_api_result(
        pack,
        protected_fiscal_periods=protected_fiscal_periods,
    )
    if period_result.posting_eligible or period_result.automatic_source_posting_enabled:
        return _blocked_result(
            blocker_code="posting_ready_review_period_posting_control_review",
            blocker_message=(
                "The protected per-period journal API unexpectedly enables posting. "
                "Posting-ready Management review remains blocked."
            ),
        )
    if period_result.blocker_code is not None:
        return _blocked_result(
            blocker_code=period_result.blocker_code,
            blocker_message=(
                period_result.blocker_message
                or "The protected per-period journal evidence is blocked."
            ),
        )
    if period_result.status != "eir_period_journal_preview_ready":
        return _blocked_result(
            blocker_code="posting_ready_review_period_state_review",
            blocker_message=(
                "Cross-period sequence evidence exists without matching protected "
                "per-period journal evidence. No review bundle is exposed."
            ),
        )

    sequences = sequence_result.previews
    period_journals = period_result.previews
    sequence_ids = tuple(item.transaction_id for item in sequences)
    period_ids = tuple(item.transaction_id for item in period_journals)
    collection_ids = tuple(item.transaction_id for item in pack.collection_journal_previews)
    if (
        not sequences
        or len(period_journals) != len(sequences)
        or len(set(sequence_ids)) != len(sequence_ids)
        or len(set(period_ids)) != len(period_ids)
        or len(set(collection_ids)) != len(collection_ids)
        or set(period_ids) != set(sequence_ids)
        or not set(sequence_ids).issubset(set(collection_ids))
    ):
        return _blocked_result(
            blocker_code="posting_ready_review_source_set_not_exact",
            blocker_message=(
                "Protected cross-period sequences, per-period journals, and collection "
                "previews do not form one complete unique review set."
            ),
        )

    period_by_transaction = {
        item.transaction_id: item for item in period_journals
    }
    collection_by_transaction = {
        item.transaction_id: item for item in pack.collection_journal_previews
    }

    bundles: list[RegularCrossPeriodPostingReadyEvidenceBundle] = []
    for sequence in sequences:
        period_journal = period_by_transaction.get(sequence.transaction_id)
        collection = collection_by_transaction.get(sequence.transaction_id)
        if period_journal is None or collection is None:
            return _blocked_result(
                blocker_code="posting_ready_review_protected_source_missing",
                blocker_message=(
                    "A cross-period transaction is missing its exact protected "
                    "period-journal or collection evidence."
                ),
            )

        coordinates = build_regular_cross_period_posting_coordinate_preview(
            sequence,
            protected_period_journal=period_journal,
            protected_collection=collection,
            protected_fiscal_periods=protected_fiscal_periods,
        )
        if (
            coordinates.disposition
            != "regular_cross_period_posting_coordinate_preview_ready"
            or coordinates.blocker_code is not None
            or coordinates.posting_eligible
            or coordinates.automatic_source_posting_enabled
            or coordinates.posting_identity_ready
            or not coordinates.ordered_coordinates
        ):
            return _blocked_result(
                blocker_code=(
                    coordinates.blocker_code
                    or "posting_ready_review_coordinate_not_exact"
                ),
                blocker_message=coordinates.message,
            )

        identity = build_regular_cross_period_posting_identity_preview(
            coordinates,
            protected_sequence=sequence,
            protected_period_journal=period_journal,
            protected_collection=collection,
            protected_fiscal_periods=protected_fiscal_periods,
        )
        if (
            identity.disposition
            != "regular_cross_period_posting_identity_preview_ready"
            or identity.blocker_code is not None
            or identity.posting_eligible
            or identity.automatic_source_posting_enabled
            or not identity.posting_identity_ready
            or not identity.ordered_identities
        ):
            return _blocked_result(
                blocker_code=(
                    identity.blocker_code
                    or "posting_ready_review_identity_not_exact"
                ),
                blocker_message=identity.message,
            )

        bundle = build_regular_cross_period_posting_ready_evidence_bundle(
            sequence,
            coordinates,
            identity,
            protected_period_journal=period_journal,
            protected_collection=collection,
            protected_fiscal_periods=protected_fiscal_periods,
        )
        if (
            bundle.transaction_id != sequence.transaction_id
            or bundle.disposition
            != "regular_cross_period_posting_ready_evidence_complete"
            or bundle.blocker_code is not None
            or bundle.posting_eligible
            or bundle.automatic_source_posting_enabled
            or not bundle.posting_coordinate_ready
            or not bundle.posting_identity_ready
            or not bundle.posting_ready_evidence_complete
            or not bundle.ordered_entries
            or bundle.ordered_entries[-1].entry_type != "collection"
            or any(entry.posting_eligible for entry in bundle.ordered_entries)
            or any(not entry.balanced for entry in bundle.ordered_entries)
        ):
            return _blocked_result(
                blocker_code=(
                    bundle.blocker_code
                    or "posting_ready_review_bundle_not_exact"
                ),
                blocker_message=bundle.message,
            )
        bundles.append(bundle)

    transaction_ids = [bundle.transaction_id for bundle in bundles]
    source_event_keys = [
        entry.source_event_key
        for bundle in bundles
        for entry in bundle.ordered_entries
    ]
    bundle_entry_keys = [
        entry.bundle_entry_key
        for bundle in bundles
        for entry in bundle.ordered_entries
    ]
    if (
        len(set(transaction_ids)) != len(transaction_ids)
        or len(set(source_event_keys)) != len(source_event_keys)
        or len(set(bundle_entry_keys)) != len(bundle_entry_keys)
    ):
        return _blocked_result(
            blocker_code="posting_ready_review_identity_conflict",
            blocker_message=(
                "Posting-ready review evidence must retain unique transaction, source "
                "event, and bundle-entry identities across the entire loan result."
            ),
        )

    return RegularPostingReadyEvidenceReviewApiResult(
        status="regular_posting_ready_evidence_review_ready",
        blocker_code=None,
        blocker_message=None,
        bundles=tuple(bundles),
    )


def _money(value: Decimal) -> str:
    return format(value, ".2f")


def _line_payload(
    line: RegularCrossPeriodPostingReadyJournalLineEvidence,
) -> dict[str, object]:
    return {
        "line_order": line.line_order,
        "account_system_key": line.account_system_key,
        "side": line.side,
        "amount": _money(line.amount),
        "label": line.label,
    }


def _entry_payload(
    entry: RegularCrossPeriodPostingReadyEntryEvidence,
) -> dict[str, object]:
    return {
        "sequence_order": entry.sequence_order,
        "entry_type": entry.entry_type,
        "bundle_entry_key": entry.bundle_entry_key,
        "sequence_preview_entry_key": entry.sequence_preview_entry_key,
        "coordinate_preview_key": entry.coordinate_preview_key,
        "identity_preview_key": entry.identity_preview_key,
        "upstream_related_source_event_key": entry.upstream_related_source_event_key,
        "source_type": entry.source_type,
        "source_reference": entry.source_reference,
        "source_event_key": entry.source_event_key,
        "related_collection_source_event_key": (
            entry.related_collection_source_event_key
        ),
        "recognition_date": entry.recognition_date.isoformat(),
        "proposed_posting_date": entry.proposed_posting_date.isoformat(),
        "amount": _money(entry.amount),
        "fiscal_period_id": str(entry.fiscal_period_id),
        "fiscal_period_label": entry.fiscal_period_label,
        "fiscal_period_start_date": entry.fiscal_period_start_date.isoformat(),
        "fiscal_period_end_date": entry.fiscal_period_end_date.isoformat(),
        "fiscal_period_status": entry.fiscal_period_status,
        "journal_lines": [_line_payload(line) for line in entry.journal_lines],
        "total_debit": _money(entry.total_debit),
        "total_credit": _money(entry.total_credit),
        "balanced": entry.balanced,
        "posting_eligible": entry.posting_eligible,
    }


def _bundle_payload(
    bundle: RegularCrossPeriodPostingReadyEvidenceBundle,
) -> dict[str, object]:
    return {
        "transaction_id": str(bundle.transaction_id),
        "collection_source_event_key": bundle.collection_source_event_key,
        "sequence_policy_version": bundle.sequence_policy_version,
        "coordinate_policy_version": bundle.coordinate_policy_version,
        "identity_policy_version": bundle.identity_policy_version,
        "bundle_policy_version": bundle.bundle_policy_version,
        "disposition": bundle.disposition,
        "blocker_code": bundle.blocker_code,
        "posting_eligible": bundle.posting_eligible,
        "automatic_source_posting_enabled": (
            bundle.automatic_source_posting_enabled
        ),
        "posting_coordinate_ready": bundle.posting_coordinate_ready,
        "posting_identity_ready": bundle.posting_identity_ready,
        "posting_ready_evidence_complete": (
            bundle.posting_ready_evidence_complete
        ),
        "message": bundle.message,
        "ordered_entries": [_entry_payload(entry) for entry in bundle.ordered_entries],
        "zero_cent_fiscal_period_ids": [
            str(period_id) for period_id in bundle.zero_cent_fiscal_period_ids
        ],
    }


def _api_payload(
    pack: EirCashAllocationPack,
    result: RegularPostingReadyEvidenceReviewApiResult,
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
        "review_only": result.review_only,
        "posting_ready_evidence_bundles": [
            _bundle_payload(bundle) for bundle in result.bundles
        ],
        "notice": (
            "Stage 5D.15 Management-only read-only review of the protected Stage "
            "5D.14 posting-ready evidence bundle. `posting_ready_evidence_complete` "
            "means the evidence chain reconciles; it does not grant posting "
            "permission. This endpoint creates no journal draft, journal ID, entry "
            "number, persistence row, posted entry, lending mutation, or automatic "
            "source posting."
        ),
    }


def create_posting_ready_evidence_review_router() -> APIRouter:
    router = APIRouter(tags=["management posting-ready evidence review"])

    @router.get(
        "/api/v1/management/financial-accounting/posting-ready-evidence/{loan_id}"
    )
    @router.get(
        "/api/mobile/v1/management/financial-accounting/posting-ready-evidence/{loan_id}",
        include_in_schema=False,
    )
    def posting_ready_evidence_review(
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
                        "Management access is required for protected posting-ready "
                        "accounting evidence review."
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

        result = build_regular_posting_ready_evidence_review_api_result(
            pack,
            protected_fiscal_periods=protected_fiscal_periods,
        )
        return {
            "success": True,
            "data": {
                "posting_ready_evidence_review": _api_payload(pack, result)
            },
        }

    return router
