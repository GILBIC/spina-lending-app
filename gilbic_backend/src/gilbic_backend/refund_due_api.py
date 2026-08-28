from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .refund_due_repository import (
    PostgresRefundDueRepository,
    RefundDueApprovalIdempotencyMismatch,
    RefundDueApprovalRecord,
    RefundDueError,
    RefundDueInvalid,
    RefundDueNotFound,
    RefundDueReleaseCashUnavailable,
    RefundDueReleaseCollectorMismatch,
    RefundDueReleaseExceedsOutstanding,
    RefundDueReleaseIdempotencyMismatch,
    RefundDueReleaseNotApproved,
    RefundDueReleaseRecord,
)
from .request_auth import authenticated_device_context


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RefundDueApprovalBody(_StrictModel):
    approved_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    reason: str = Field(min_length=3, max_length=500)
    authority_reference: str = Field(min_length=1, max_length=500)


class RefundDueReleaseBody(_StrictModel):
    released_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    released_at: datetime
    evidence_reference: str = Field(min_length=1, max_length=500)
    evidence_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")

    @field_validator("released_at")
    @classmethod
    def released_at_requires_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("released_at must include a timezone")
        return value


def refund_due_repository_dependency() -> PostgresRefundDueRepository:
    return PostgresRefundDueRepository()


def _approval_payload(record: RefundDueApprovalRecord) -> dict[str, object]:
    return {
        "approval_id": str(record.approval_id),
        "idempotency_key": str(record.idempotency_key),
        "adjustment_id": str(record.adjustment_id),
        "loan_id": str(record.loan_id),
        "client_id": str(record.client_id),
        "approved_amount": format(record.approved_amount, "f"),
        "released_amount": format(record.released_amount, "f"),
        "remaining_approved_amount": format(record.remaining_approved_amount, "f"),
        "approved_by_user_id": str(record.approved_by_user_id),
        "reason": record.reason,
        "authority_reference": record.authority_reference,
        "approved_at": record.approved_at.isoformat(),
    }


def _release_payload(record: RefundDueReleaseRecord) -> dict[str, object]:
    return {
        "release_id": str(record.release_id),
        "idempotency_key": str(record.idempotency_key),
        "approval_id": str(record.approval_id),
        "adjustment_id": str(record.adjustment_id),
        "loan_id": str(record.loan_id),
        "client_id": str(record.client_id),
        "assigned_collector_user_id": str(record.assigned_collector_user_id),
        "released_amount": format(record.released_amount, "f"),
        "approval_released_amount": format(record.approval_released_amount, "f"),
        "approval_remaining_amount": format(record.approval_remaining_amount, "f"),
        "adjustment_outstanding_refund_due": format(
            record.adjustment_outstanding_refund_due,
            "f",
        ),
        "released_by_user_id": str(record.released_by_user_id),
        "released_at": record.released_at.isoformat(),
        "evidence_reference": record.evidence_reference,
        "evidence_digest": record.evidence_digest,
    }


def _raise_refund_error(error: RefundDueError) -> None:
    if isinstance(error, (RefundDueNotFound, RefundDueReleaseNotApproved)):
        status_code = 404
    elif isinstance(
        error,
        (
            RefundDueApprovalIdempotencyMismatch,
            RefundDueReleaseIdempotencyMismatch,
            RefundDueReleaseCollectorMismatch,
            RefundDueReleaseCashUnavailable,
            RefundDueReleaseExceedsOutstanding,
        ),
    ):
        status_code = 409
    elif isinstance(error, RefundDueInvalid):
        status_code = 422
    else:
        status_code = 409
    raise HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    ) from error


def create_refund_due_router() -> APIRouter:
    router = APIRouter(tags=["refund due"])

    @router.post(
        "/api/v1/management/refund-dues/{adjustment_id}/approve",
        status_code=201,
    )
    @router.post(
        "/api/mobile/v1/management/refund-dues/{adjustment_id}/approve",
        status_code=201,
        include_in_schema=False,
    )
    def approve_refund_due(
        adjustment_id: UUID,
        body: RefundDueApprovalBody,
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        refunds: PostgresRefundDueRepository = Depends(
            refund_due_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="lending.refund_due.approve",
            permission_error="Management Refund Due approval permission is required.",
        )
        try:
            record = refunds.approve(
                idempotency_key=idempotency_key,
                actor_user_id=actor.user_id,
                adjustment_id=adjustment_id,
                approved_amount=body.approved_amount,
                reason=body.reason,
                authority_reference=body.authority_reference,
            )
        except RefundDueError as error:
            _raise_refund_error(error)
        return {"success": True, "data": _approval_payload(record)}

    @router.post(
        "/api/v1/collector/refund-due-approvals/{approval_id}/release",
        status_code=201,
    )
    @router.post(
        "/api/mobile/v1/collector/refund-due-approvals/{approval_id}/release",
        status_code=201,
        include_in_schema=False,
    )
    def release_refund_due(
        approval_id: UUID,
        body: RefundDueReleaseBody,
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        refunds: PostgresRefundDueRepository = Depends(
            refund_due_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="lending.refund_due.release",
            permission_error="Assigned Collector Refund Due release permission is required.",
        )
        try:
            record = refunds.release(
                idempotency_key=idempotency_key,
                actor_user_id=actor.user_id,
                approval_id=approval_id,
                released_amount=body.released_amount,
                released_at=body.released_at,
                evidence_reference=body.evidence_reference,
                evidence_digest=body.evidence_digest,
            )
        except RefundDueError as error:
            _raise_refund_error(error)
        return {"success": True, "data": _release_payload(record)}

    return router
