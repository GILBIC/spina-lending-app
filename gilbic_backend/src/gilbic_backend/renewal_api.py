from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .renewal_repository import (
    ClientRenewalPortal,
    PostgresRenewalRepository,
    RenewalBorrowerNotLinked,
    RenewalConflict,
    RenewalError,
    RenewalLoanNotEligible,
    RenewalRequestNotFound,
    RenewalRequestRecord,
    RenewalStatus,
)
from .request_auth import authenticated_device_context


class StrictRenewalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SubmitRenewalRequest(StrictRenewalRequest):
    loan_id: UUID
    requested_amount: str = Field(min_length=1, max_length=30)
    message: str = Field(default="", max_length=1000)

    @field_validator("requested_amount")
    @classmethod
    def validate_amount(cls, value: str) -> str:
        normalized = value.strip().replace(",", "")
        try:
            amount = Decimal(normalized)
        except InvalidOperation as exc:
            raise ValueError("Enter a valid requested amount.") from exc
        if amount <= 0 or amount > Decimal("10000000"):
            raise ValueError("Requested amount must be greater than zero.")
        return format(amount.quantize(Decimal("0.01")), "f")

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        return " ".join(value.split())


class ReviewRenewalRequest(StrictRenewalRequest):
    decision: Literal["approved", "rejected"]
    review_note: str = Field(default="", max_length=1000)

    @field_validator("review_note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        return " ".join(value.split())


def renewal_repository_dependency() -> PostgresRenewalRepository:
    return PostgresRenewalRepository()


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _loan_payload(record) -> dict[str, object]:
    return {
        "loan_id": str(record.loan_id),
        "loan_number": record.loan_number,
        "loan_type_name": record.loan_type_name,
        "calculation_mode": record.calculation_mode,
        "principal": _decimal(record.principal),
        "contractual_total": _decimal(record.contractual_total),
        "remaining_balance": _decimal(record.remaining_balance),
        "paid_amount": _decimal(record.paid_amount),
        "paid_percent": _decimal(record.paid_percent),
        "daily_amount": _decimal(record.daily_amount),
        "date_released": record.date_released.isoformat(),
        "due_date": record.due_date.isoformat(),
        "status": record.status,
        "eligible": record.eligible,
        "eligibility_message": record.eligibility_message,
        "pending_request_id": (
            str(record.pending_request_id) if record.pending_request_id else None
        ),
        "blocking_request_status": record.blocking_request_status,
    }


def _request_payload(record: RenewalRequestRecord) -> dict[str, object]:
    return {
        "request_id": str(record.request_id),
        "client_id": str(record.client_id),
        "client_code": record.client_code,
        "client_name": record.client_name,
        "loan_id": str(record.loan_id),
        "loan_number": record.loan_number,
        "loan_type_name": record.loan_type_name,
        "current_principal": _decimal(record.current_principal),
        "remaining_balance": _decimal(record.remaining_balance),
        "requested_amount": _decimal(record.requested_amount),
        "client_message": record.client_message,
        "status": record.status,
        "submitted_at": record.submitted_at.isoformat(),
        "reviewed_at": (
            record.reviewed_at.isoformat() if record.reviewed_at else None
        ),
        "reviewed_by_name": record.reviewed_by_name,
        "review_note": record.review_note,
        "cancelled_at": (
            record.cancelled_at.isoformat() if record.cancelled_at else None
        ),
    }


def _portal_payload(portal: ClientRenewalPortal) -> dict[str, object]:
    return {
        "client": {
            "client_id": str(portal.client_id),
            "client_code": portal.client_code,
            "client_name": portal.client_name,
        },
        "loans": [_loan_payload(item) for item in portal.loans],
        "requests": [_request_payload(item) for item in portal.requests],
        "notice": (
            "Regular renewal normally becomes requestable after 50% of that loan's "
            "total contractual balance is paid. A 7x7 renewal may be requested for "
            "consideration at any paid percentage, but every 7x7 renewal requires "
            "Management approval. A request does not create or release a new loan."
        ),
    }


def _renewal_exception(error: RenewalError) -> HTTPException:
    if isinstance(error, RenewalBorrowerNotLinked):
        status_code = 404
    elif isinstance(error, RenewalRequestNotFound):
        status_code = 404
    elif isinstance(error, (RenewalConflict, RenewalLoanNotEligible)):
        status_code = 409
    else:
        status_code = 500
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    )


def create_renewal_router() -> APIRouter:
    router = APIRouter(tags=["renewals"])

    @router.get("/api/v1/client/renewals")
    @router.get("/api/mobile/v1/client/renewals", include_in_schema=False)
    def client_portal(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        renewals: PostgresRenewalRepository = Depends(
            renewal_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        if "client" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "client_role_required",
                    "message": "Only a linked client account can view Renewal.",
                },
            )
        try:
            portal = renewals.portal_for_user(user_id=actor.user_id)
        except RenewalError as error:
            raise _renewal_exception(error) from error
        return {"success": True, "data": _portal_payload(portal)}

    @router.post(
        "/api/v1/client/renewals",
        status_code=status.HTTP_201_CREATED,
    )
    @router.post(
        "/api/mobile/v1/client/renewals",
        status_code=status.HTTP_201_CREATED,
        include_in_schema=False,
    )
    def submit_client_renewal(
        body: SubmitRenewalRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        renewals: PostgresRenewalRepository = Depends(
            renewal_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        if "client" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "client_role_required",
                    "message": "Only a linked client account can request renewal.",
                },
            )
        try:
            record = renewals.submit_for_user(
                user_id=actor.user_id,
                loan_id=body.loan_id,
                requested_amount=Decimal(body.requested_amount),
                client_message=body.message,
            )
        except RenewalError as error:
            raise _renewal_exception(error) from error
        return {"success": True, "data": {"request": _request_payload(record)}}

    @router.post("/api/v1/client/renewals/{request_id}/cancel")
    @router.post(
        "/api/mobile/v1/client/renewals/{request_id}/cancel",
        include_in_schema=False,
    )
    def cancel_client_renewal(
        request_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        renewals: PostgresRenewalRepository = Depends(
            renewal_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        if "client" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "client_role_required",
                    "message": "Only a linked client account can cancel renewal.",
                },
            )
        try:
            record = renewals.cancel_for_user(
                user_id=actor.user_id,
                request_id=request_id,
            )
        except RenewalError as error:
            raise _renewal_exception(error) from error
        return {"success": True, "data": {"request": _request_payload(record)}}

    @router.get("/api/v1/management/renewals")
    @router.get(
        "/api/mobile/v1/management/renewals",
        include_in_schema=False,
    )
    def management_list(
        renewal_status: RenewalStatus = Query(default="pending", alias="status"),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        renewals: PostgresRenewalRepository = Depends(
            renewal_repository_dependency
        ),
    ) -> dict[str, object]:
        authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="renewal.manage",
            permission_error="Management renewal permission is required.",
        )
        records = renewals.list_for_management(
            status=renewal_status,
            limit=limit,
            offset=offset,
        )
        return {
            "success": True,
            "data": {"requests": [_request_payload(item) for item in records]},
        }

    @router.post("/api/v1/management/renewals/{request_id}/review")
    @router.post(
        "/api/mobile/v1/management/renewals/{request_id}/review",
        include_in_schema=False,
    )
    def management_review(
        request_id: UUID,
        body: ReviewRenewalRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        renewals: PostgresRenewalRepository = Depends(
            renewal_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="renewal.manage",
            permission_error="Management renewal permission is required.",
        )
        if body.decision == "rejected" and len(body.review_note) < 3:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "renewal_review_note_required",
                    "message": "A rejection reason is required.",
                },
            )
        try:
            record = renewals.review(
                actor_user_id=actor.user_id,
                request_id=request_id,
                decision=body.decision,
                review_note=body.review_note,
            )
        except RenewalError as error:
            raise _renewal_exception(error) from error
        return {"success": True, "data": {"request": _request_payload(record)}}

    return router