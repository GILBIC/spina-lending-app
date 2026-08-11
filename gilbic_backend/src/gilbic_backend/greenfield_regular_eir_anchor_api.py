from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .greenfield_regular_eir_anchor_repository import (
    GreenfieldRegularEirAnchorError,
    GreenfieldRegularEirAnchorRecord,
    PostgresGreenfieldRegularEirAnchorRepository,
)
from .request_auth import authenticated_device_context


def greenfield_regular_eir_anchor_repository_dependency(
) -> PostgresGreenfieldRegularEirAnchorRepository:
    return PostgresGreenfieldRegularEirAnchorRepository()


def _payload(record: GreenfieldRegularEirAnchorRecord) -> dict[str, object]:
    return {
        "posting_id": str(record.posting_id),
        "disbursement_event_id": str(record.disbursement_event_id),
        "loan_id": str(record.loan_id),
        "loan_number": record.loan_number,
        "client_id": str(record.client_id),
        "client_code": record.client_code,
        "client_name": record.client_name,
        "journal_entry_id": str(record.journal_entry_id),
        "entry_number": record.entry_number,
        "release_source_event_key": record.release_source_event_key,
        "anchor_date": record.anchor_date.isoformat(),
        "disbursed_at": record.disbursed_at.isoformat(),
        "initial_gross_carrying_amount": format(
            record.initial_gross_carrying_amount, "f"
        ),
        "initial_loan_component": format(record.initial_loan_component, "f"),
        "initial_accrued_interest_component": format(
            record.initial_accrued_interest_component, "f"
        ),
        "schedule_id": str(record.schedule_id) if record.schedule_id else None,
        "schedule_version": record.schedule_version,
        "schedule_status": record.schedule_status,
        "payment_frequency": record.payment_frequency,
        "contract_reference": record.contract_reference,
        "contract_signed_date": (
            record.contract_signed_date.isoformat()
            if record.contract_signed_date
            else None
        ),
        "schedule_effective_from": (
            record.schedule_effective_from.isoformat()
            if record.schedule_effective_from
            else None
        ),
        "registration_id": record.registration_id,
        "evidence_basis": record.evidence_basis,
        "evidence_reference": record.evidence_reference,
        "installment_count": record.installment_count,
        "first_due_date": (
            record.first_due_date.isoformat() if record.first_due_date else None
        ),
        "contractual_due_date": (
            record.contractual_due_date.isoformat()
            if record.contractual_due_date
            else None
        ),
        "contractual_cash_total": (
            format(record.contractual_cash_total, "f")
            if record.contractual_cash_total is not None
            else None
        ),
        "daily_eir": format(record.daily_eir, "f") if record.daily_eir else None,
        "daily_eir_percent": (
            format(record.daily_eir_percent, "f")
            if record.daily_eir_percent is not None
            else None
        ),
        "pre_anchor_collection_count": record.pre_anchor_collection_count,
        "same_day_collection_count": record.same_day_collection_count,
        "readiness_status": record.readiness_status,
        "anchor_source_key": record.anchor_source_key,
        "anchor_policy_version": record.anchor_policy_version,
        "collection_journal_integration_enabled": (
            record.collection_journal_integration_enabled
        ),
        "journal_lines_enabled": record.journal_lines_enabled,
        "automatic_source_posting": record.automatic_source_posting,
    }


def create_greenfield_regular_eir_anchor_router() -> APIRouter:
    router = APIRouter(tags=["management greenfield Regular EIR anchor"])

    @router.get(
        "/api/v1/management/accounting/regular-greenfield-anchors/readiness"
    )
    def list_greenfield_regular_eir_anchor_readiness(
        readiness_status: str | None = Query(default=None, max_length=100),
        loan_id: UUID | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=250),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresGreenfieldRegularEirAnchorRepository = Depends(
            greenfield_regular_eir_anchor_repository_dependency
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
            records = repository.list_readiness(
                readiness_status=readiness_status,
                loan_id=loan_id,
                limit=limit,
            )
        except GreenfieldRegularEirAnchorError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": error.code, "message": str(error)},
            ) from error
        return {
            "success": True,
            "data": {
                "anchor_policy_version": "greenfield_regular_eir_anchor_v1",
                "collection_journal_integration_enabled": False,
                "journal_lines_enabled": False,
                "automatic_source_posting": False,
                "anchors": [_payload(record) for record in records],
            },
        }

    return router
