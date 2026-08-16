from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
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


def create_management_no_collection_router() -> APIRouter:
    router = APIRouter(tags=["management no collection"])

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
                    "message": "Only Management may declare No Collection.",
                },
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
                    "message": "Only Management may reverse No Collection.",
                },
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
