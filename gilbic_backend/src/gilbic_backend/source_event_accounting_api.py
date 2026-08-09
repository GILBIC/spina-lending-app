from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .request_auth import authenticated_device_context
from .source_event_accounting_preview import AccountingPreviewLine, CollectionAccountingPreview
from .source_event_accounting_repository import (
    PostgresSourceEventAccountingRepository,
    SourceEventAccountingPreviewPack,
)


def source_event_accounting_repository_dependency() -> PostgresSourceEventAccountingRepository:
    return PostgresSourceEventAccountingRepository()


def _money(value: Decimal) -> str:
    return format(value, ".2f")


def _line_payload(line: AccountingPreviewLine) -> dict[str, object]:
    return {
        "account_system_key": line.account_system_key,
        "side": line.side,
        "amount": _money(line.amount),
        "label": line.label,
    }


def _event_payload(event: CollectionAccountingPreview) -> dict[str, object]:
    return {
        "transaction_id": str(event.transaction_id),
        "source_event_key": event.source_event_key,
        "receipt_number": event.receipt_number,
        "client_id": str(event.client_id),
        "client_code": event.client_code,
        "client_name": event.client_name,
        "loan_id": str(event.loan_id),
        "loan_number": event.loan_number,
        "loan_type_code": event.loan_type_code,
        "loan_type_name": event.loan_type_name,
        "collection_date": event.collection_date.isoformat(),
        "accepted_at": event.accepted_at.isoformat(),
        "entry_type": event.entry_type,
        "amount": _money(event.amount),
        "is_voided": event.is_voided,
        "voided_at": event.voided_at.isoformat() if event.voided_at else None,
        "disposition": event.disposition,
        "posting_eligible": event.posting_eligible,
        "message": event.message,
        "proposed_lines": [_line_payload(line) for line in event.proposed_lines],
        "existing_journal_entry_id": (
            str(event.existing_journal_entry_id)
            if event.existing_journal_entry_id is not None
            else None
        ),
        "existing_journal_status": event.existing_journal_status,
        "existing_journal_entry_number": event.existing_journal_entry_number,
        "reversal_entry_id": (
            str(event.reversal_entry_id) if event.reversal_entry_id is not None else None
        ),
        "reversal_status": event.reversal_status,
        "reversal_entry_number": event.reversal_entry_number,
    }


def _pack_payload(pack: SourceEventAccountingPreviewPack) -> dict[str, object]:
    return {
        "cutover": {
            "cutover_date": pack.cutover_date.isoformat() if pack.cutover_date else None,
            "workbook_status": pack.workbook_status,
            "opening_balance_posted": pack.opening_balance_posted,
            "opening_balance_entry_number": pack.opening_balance_entry_number,
        },
        "account_configuration_ready": pack.account_configuration_ready,
        "account_configuration_blocker": pack.account_configuration_blocker,
        "automatic_source_posting_enabled": pack.automatic_source_posting_enabled,
        "eir_income_included_in_collection_mapping": (
            pack.eir_income_included_in_collection_mapping
        ),
        "has_more": pack.has_more,
        "next_cursor": pack.next_cursor,
        "events": [_event_payload(event) for event in pack.events],
        "notice": (
            "Read-only source-event accounting classification. No journal draft or posted entry is created. "
            "PAYMENT and ADV identify authoritative cash sources, but journal lines remain blocked until "
            "event-date EIR allocation can split cash between accrued effective interest and the loan component. "
            "PASS is non-cash. Voided collections require no entry when never accounted, or a controlled reversal "
            "when a source journal had already posted. Automatic source posting remains disabled."
        ),
    }


def create_source_event_accounting_router() -> APIRouter:
    router = APIRouter(tags=["management source event accounting preview"])

    @router.get("/api/v1/management/financial-accounting/source-events/collections")
    @router.get(
        "/api/mobile/v1/management/financial-accounting/source-events/collections",
        include_in_schema=False,
    )
    def collection_source_events(
        start_date: date | None = Query(default=None),
        end_date: date | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=250),
        cursor: str | None = Query(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresSourceEventAccountingRepository = Depends(
            source_event_accounting_repository_dependency
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
                    "message": "Management access is required for source-event accounting preview.",
                },
            )
        if start_date is not None and end_date is not None and end_date < start_date:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_source_event_date_range",
                    "message": "End date cannot be before start date.",
                },
            )
        try:
            pack = repository.load_collection_preview(
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                cursor=cursor,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_source_event_cursor",
                    "message": str(error),
                },
            ) from error
        return {
            "success": True,
            "data": {"collection_source_events": _pack_payload(pack)},
        }

    return router
