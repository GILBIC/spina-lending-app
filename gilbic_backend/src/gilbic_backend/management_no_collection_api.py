from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .management_no_collection_preview import preview_no_collection_shift
from .management_no_collection_query_repository import (
    NoCollectionLoanState,
    PostgresManagementNoCollectionQueryRepository,
)
from .management_no_collection_repository import (
    ManagementNoCollectionConflict,
    ManagementNoCollectionError,
    ManagementNoCollectionInvalid,
    ManagementNoCollectionNotFound,
    NoCollectionAdjustmentRecord,
    NoCollectionSelection,
    PostgresManagementNoCollectionRepository,
)
from .request_auth import authenticated_device_context


class NoCollectionLoanBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    loan_id: UUID
    expected_operational_version: int = Field(ge=0)


class NoCollectionPreviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    loan_id: UUID
    expected_operational_version: int = Field(ge=0)
    no_collection_date: date


class NoCollectionDeclarationBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    no_collection_date: date
    reason: str = Field(min_length=1, max_length=500)
    loans: list[NoCollectionLoanBody] = Field(min_length=1, max_length=100)


class NoCollectionReversalBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expected_operational_version: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=500)


def management_no_collection_repository_dependency() -> (
    PostgresManagementNoCollectionRepository
):
    return PostgresManagementNoCollectionRepository()


def management_no_collection_query_repository_dependency() -> (
    PostgresManagementNoCollectionQueryRepository
):
    return PostgresManagementNoCollectionQueryRepository()


def _record_payload(record: NoCollectionAdjustmentRecord) -> dict[str, object]:
    return {
        "adjustment_id": str(record.adjustment_id),
        "loan_id": str(record.loan_id),
        "schedule_id": str(record.schedule_id),
        "schedule_version": record.schedule_version,
        "payment_frequency": record.payment_frequency,
        "adjustment_type": record.adjustment_type,
        "no_collection_date": record.no_collection_date.isoformat(),
        "reason": record.reason,
        "expected_operational_version": record.expected_operational_version,
        "resulting_operational_version": record.resulting_operational_version,
        "reverses_adjustment_id": (
            str(record.reverses_adjustment_id)
            if record.reverses_adjustment_id
            else None
        ),
        "created_at": record.created_at.isoformat(),
        "shifts": [
            {
                "installment_id": shift.installment_id,
                "installment_number": shift.installment_number,
                "contractual_due_date": shift.contractual_due_date.isoformat(),
                "prior_effective_due_date": shift.prior_effective_due_date.isoformat(),
                "new_effective_due_date": shift.new_effective_due_date.isoformat(),
                "contractual_amount": format(shift.contractual_amount, "f"),
            }
            for shift in record.shifts
        ],
    }


def _loan_state_payload(state: NoCollectionLoanState) -> dict[str, object]:
    return {
        "loan_id": str(state.loan_id),
        "loan_number": state.loan_number,
        "client_id": str(state.client_id),
        "client_name": state.client_name,
        "loan_type": state.loan_type,
        "schedule_id": str(state.schedule_id),
        "schedule_version": state.schedule_version,
        "payment_frequency": state.payment_frequency,
        "contract_reference": state.contract_reference,
        "operational_version": state.operational_version,
        "semi_monthly_days": list(state.semi_monthly_days),
        "installments": [
            {
                "installment_id": installment.installment_id,
                "installment_number": installment.installment_number,
                "contractual_due_date": installment.contractual_due_date.isoformat(),
                "effective_due_date": installment.effective_due_date.isoformat(),
                "contractual_amount": format(installment.contractual_amount, "f"),
                "allocated_amount": format(installment.allocated_amount, "f"),
                "remaining_amount": format(installment.remaining_amount, "f"),
                "is_paid": installment.remaining_amount == 0,
                "is_partly_paid": (
                    installment.allocated_amount > 0
                    and installment.remaining_amount > 0
                ),
                "last_adjustment_id": (
                    str(installment.last_adjustment_id)
                    if installment.last_adjustment_id
                    else None
                ),
            }
            for installment in state.installments
        ],
        "active_no_collection": [
            {
                "adjustment_id": str(item.adjustment_id),
                "no_collection_date": item.no_collection_date.isoformat(),
                "reason": item.reason,
                "resulting_operational_version": item.resulting_operational_version,
                "actor_name": item.actor_name,
                "created_at": item.created_at.isoformat(),
            }
            for item in state.active_no_collection
        ],
    }


def _raise_no_collection_error(error: ManagementNoCollectionError) -> None:
    if isinstance(error, ManagementNoCollectionNotFound):
        status = 404
    elif isinstance(error, ManagementNoCollectionInvalid):
        status = 422
    elif isinstance(error, ManagementNoCollectionConflict):
        status = 409
    else:
        status = 409
    raise HTTPException(
        status_code=status,
        detail={"code": error.code, "message": str(error)},
    ) from error


def _require_management(
    *,
    authorization: str | None,
    x_device_id: str | None,
    auth: SupabaseAuthClient,
    accounts: PostgresAccountRepository,
):
    actor = authenticated_device_context(
        authorization=authorization,
        device_identifier=x_device_id,
        auth=auth,
        accounts=accounts,
        permission="lending.no_collection.manage",
        permission_error="Management No Collection permission is required.",
    )
    if "management" not in actor.roles:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "management_role_required",
                "message": "Only Management may manage No Collection schedules.",
            },
        )
    return actor


def create_management_no_collection_router() -> APIRouter:
    router = APIRouter(tags=["management no collection"])

    @router.get("/api/v1/management/no-collection/loans/{loan_id}")
    @router.get(
        "/api/mobile/v1/management/no-collection/loans/{loan_id}",
        include_in_schema=False,
    )
    def get_no_collection_loan_state(
        loan_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        query: PostgresManagementNoCollectionQueryRepository = Depends(
            management_no_collection_query_repository_dependency
        ),
    ) -> dict[str, object]:
        _require_management(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            state = query.get_loan_state(loan_id=loan_id)
        except ManagementNoCollectionError as error:
            _raise_no_collection_error(error)
        return {"success": True, "data": _loan_state_payload(state)}

    @router.post("/api/v1/management/no-collection/preview")
    @router.post(
        "/api/mobile/v1/management/no-collection/preview",
        include_in_schema=False,
    )
    def preview_no_collection(
        body: NoCollectionPreviewBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        query: PostgresManagementNoCollectionQueryRepository = Depends(
            management_no_collection_query_repository_dependency
        ),
    ) -> dict[str, object]:
        _require_management(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            state = query.get_loan_state(loan_id=body.loan_id)
            if state.operational_version != body.expected_operational_version:
                raise ManagementNoCollectionConflict(
                    "The operational schedule changed. Refresh before previewing No Collection."
                )
            preview = preview_no_collection_shift(
                state=state,
                no_collection_date=body.no_collection_date,
            )
        except ManagementNoCollectionError as error:
            _raise_no_collection_error(error)
        return {
            "success": True,
            "data": {
                "loan_id": preview.loan_id,
                "operational_version": preview.operational_version,
                "no_collection_date": preview.no_collection_date.isoformat(),
                "payment_frequency": preview.payment_frequency,
                "shifts": [
                    {
                        "installment_id": shift.installment_id,
                        "installment_number": shift.installment_number,
                        "contractual_due_date": shift.contractual_due_date.isoformat(),
                        "prior_effective_due_date": shift.prior_effective_due_date.isoformat(),
                        "new_effective_due_date": shift.new_effective_due_date.isoformat(),
                        "contractual_amount": format(shift.contractual_amount, "f"),
                    }
                    for shift in preview.shifts
                ],
            },
        }

    @router.post("/api/v1/management/no-collection")
    @router.post(
        "/api/mobile/v1/management/no-collection",
        include_in_schema=False,
    )
    def declare_no_collection(
        body: NoCollectionDeclarationBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresManagementNoCollectionRepository = Depends(
            management_no_collection_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_management(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            records = repository.declare_many(
                actor_user_id=actor.user_id,
                selections=tuple(
                    NoCollectionSelection(
                        loan_id=item.loan_id,
                        expected_operational_version=item.expected_operational_version,
                    )
                    for item in body.loans
                ),
                no_collection_date=body.no_collection_date,
                reason=body.reason,
            )
        except ManagementNoCollectionError as error:
            _raise_no_collection_error(error)
        return {
            "success": True,
            "data": {
                "no_collection_date": body.no_collection_date.isoformat(),
                "loans": [_record_payload(record) for record in records],
            },
        }

    @router.post("/api/v1/management/no-collection/{adjustment_id}/reverse")
    @router.post(
        "/api/mobile/v1/management/no-collection/{adjustment_id}/reverse",
        include_in_schema=False,
    )
    def reverse_no_collection(
        adjustment_id: UUID,
        body: NoCollectionReversalBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresManagementNoCollectionRepository = Depends(
            management_no_collection_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_management(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = repository.reverse(
                actor_user_id=actor.user_id,
                adjustment_id=adjustment_id,
                expected_operational_version=body.expected_operational_version,
                reason=body.reason,
            )
        except ManagementNoCollectionError as error:
            _raise_no_collection_error(error)
        return {"success": True, "data": _record_payload(record)}

    return router
