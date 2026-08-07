from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .request_auth import authenticated_device_context
from .support_repository import (
    ClientSupportPortal,
    PostgresSupportRepository,
    SupportBorrowerNotLinked,
    SupportCategory,
    SupportConflict,
    SupportError,
    SupportRequestNotFound,
    SupportRequestRecord,
    SupportStatus,
)


class StrictSupportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SubmitSupportRequest(StrictSupportRequest):
    category: SupportCategory
    subject: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=3, max_length=2000)
    reference_text: str = Field(default="", max_length=120)

    @field_validator("subject", "message")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 3:
            raise ValueError("Enter at least 3 characters.")
        return normalized

    @field_validator("reference_text")
    @classmethod
    def normalize_reference(cls, value: str) -> str:
        return " ".join(value.split())


class ReviewSupportRequest(StrictSupportRequest):
    action: Literal["answered", "resolved"]
    response: str = Field(min_length=3, max_length=2000)

    @field_validator("response")
    @classmethod
    def normalize_response(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 3:
            raise ValueError("Enter at least 3 characters.")
        return normalized


def support_repository_dependency() -> PostgresSupportRepository:
    return PostgresSupportRepository()


def _request_payload(record: SupportRequestRecord) -> dict[str, object]:
    return {
        "request_id": str(record.request_id),
        "client_id": str(record.client_id),
        "client_code": record.client_code,
        "client_name": record.client_name,
        "category": record.category,
        "subject": record.subject,
        "message": record.message,
        "reference_text": record.reference_text,
        "status": record.status,
        "created_at": record.created_at.isoformat(),
        "managed_by_name": record.managed_by_name,
        "management_response": record.management_response,
        "responded_at": (
            record.responded_at.isoformat() if record.responded_at else None
        ),
        "resolved_at": (
            record.resolved_at.isoformat() if record.resolved_at else None
        ),
        "cancelled_at": (
            record.cancelled_at.isoformat() if record.cancelled_at else None
        ),
    }


def _portal_payload(portal: ClientSupportPortal) -> dict[str, object]:
    return {
        "client": {
            "client_id": str(portal.client_id),
            "client_code": portal.client_code,
            "client_name": portal.client_name,
        },
        "requests": [_request_payload(item) for item in portal.requests],
        "notice": (
            "Support requests do not change balances, payments, or loan records. "
            "SPINA staff will review the concern and reply here."
        ),
    }


def _support_exception(error: SupportError) -> HTTPException:
    if isinstance(error, (SupportBorrowerNotLinked, SupportRequestNotFound)):
        status_code = 404
    elif isinstance(error, SupportConflict):
        status_code = 409
    else:
        status_code = 500
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    )


def create_support_router() -> APIRouter:
    router = APIRouter(tags=["support"])

    @router.get("/api/v1/client/support")
    @router.get("/api/mobile/v1/client/support", include_in_schema=False)
    def client_portal(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        support: PostgresSupportRepository = Depends(support_repository_dependency),
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
                    "message": "Only a linked client account can use Support.",
                },
            )
        try:
            portal = support.portal_for_user(user_id=actor.user_id)
        except SupportError as error:
            raise _support_exception(error) from error
        return {"success": True, "data": _portal_payload(portal)}

    @router.post(
        "/api/v1/client/support",
        status_code=status.HTTP_201_CREATED,
    )
    @router.post(
        "/api/mobile/v1/client/support",
        status_code=status.HTTP_201_CREATED,
        include_in_schema=False,
    )
    def submit_client_support(
        body: SubmitSupportRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        support: PostgresSupportRepository = Depends(support_repository_dependency),
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
                    "message": "Only a linked client account can request support.",
                },
            )
        try:
            record = support.submit_for_user(
                user_id=actor.user_id,
                category=body.category,
                subject=body.subject,
                message=body.message,
                reference_text=body.reference_text,
            )
        except SupportError as error:
            raise _support_exception(error) from error
        return {"success": True, "data": {"request": _request_payload(record)}}

    @router.post("/api/v1/client/support/{request_id}/cancel")
    @router.post(
        "/api/mobile/v1/client/support/{request_id}/cancel",
        include_in_schema=False,
    )
    def cancel_client_support(
        request_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        support: PostgresSupportRepository = Depends(support_repository_dependency),
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
                    "message": "Only a linked client account can cancel support.",
                },
            )
        try:
            record = support.cancel_for_user(
                user_id=actor.user_id,
                request_id=request_id,
            )
        except SupportError as error:
            raise _support_exception(error) from error
        return {"success": True, "data": {"request": _request_payload(record)}}

    @router.get("/api/v1/management/support")
    @router.get(
        "/api/mobile/v1/management/support",
        include_in_schema=False,
    )
    def management_list(
        support_status: SupportStatus = Query(default="open", alias="status"),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        support: PostgresSupportRepository = Depends(support_repository_dependency),
    ) -> dict[str, object]:
        authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="support.manage",
            permission_error="Management support permission is required.",
        )
        records = support.list_for_management(
            status=support_status,
            limit=limit,
            offset=offset,
        )
        return {
            "success": True,
            "data": {"requests": [_request_payload(item) for item in records]},
        }

    @router.post("/api/v1/management/support/{request_id}/review")
    @router.post(
        "/api/mobile/v1/management/support/{request_id}/review",
        include_in_schema=False,
    )
    def management_review(
        request_id: UUID,
        body: ReviewSupportRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        support: PostgresSupportRepository = Depends(support_repository_dependency),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="support.manage",
            permission_error="Management support permission is required.",
        )
        try:
            record = support.review(
                actor_user_id=actor.user_id,
                request_id=request_id,
                action=body.action,
                response=body.response,
            )
        except SupportError as error:
            raise _support_exception(error) from error
        return {"success": True, "data": {"request": _request_payload(record)}}

    return router
