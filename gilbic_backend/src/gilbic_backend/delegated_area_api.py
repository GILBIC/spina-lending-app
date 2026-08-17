from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .delegated_area_repository import (
    DelegatedAreaConflict,
    DelegatedAreaError,
    DelegatedAreaForbidden,
    DelegatedAreaGrantRecord,
    DelegatedAreaInvalid,
    DelegatedAreaNotFound,
    DelegatedAreaRequestRecord,
    DelegatedAreaScopeRecord,
    PostgresDelegatedAreaRepository,
)
from .request_auth import authenticated_device_context


class DelegatedAreaScopeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignment_id: UUID
    include_descendants: bool = False


class DelegatedAreaRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    requested_owner_user_id: UUID
    scope_mode: Literal["selected_paths", "all_owner_areas"] = "selected_paths"
    scopes: list[DelegatedAreaScopeBody] = Field(default_factory=list, max_length=100)
    reason: str = Field(min_length=1, max_length=500)
    requested_expires_at: datetime


class DelegatedAreaDecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(default="", max_length=500)


class DelegatedAreaRevokeBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=1, max_length=500)


def delegated_area_repository_dependency() -> PostgresDelegatedAreaRepository:
    return PostgresDelegatedAreaRepository()


def _require_collector(
    *,
    permission: str,
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
        permission=permission,
        permission_error="Delegated Collector area access permission is required.",
    )
    if "collector" not in actor.roles:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "collector_role_required",
                "message": "Only an active Collector may use delegated area access.",
            },
        )
    return actor


def _raise_error(error: DelegatedAreaError) -> None:
    if isinstance(error, DelegatedAreaNotFound):
        status = 404
    elif isinstance(error, DelegatedAreaForbidden):
        status = 403
    elif isinstance(error, DelegatedAreaInvalid):
        status = 422
    elif isinstance(error, DelegatedAreaConflict):
        status = 409
    else:
        status = 409
    raise HTTPException(
        status_code=status,
        detail={"code": error.code, "message": str(error)},
    ) from error


def _scope_payload(scope: DelegatedAreaScopeRecord) -> dict[str, object]:
    return {
        "assignment_id": str(scope.assignment_id),
        "owner_user_id": str(scope.owner_user_id),
        "owner_name": scope.owner_name,
        "area_path": scope.area_path,
        "sort_order": scope.sort_order,
        "include_descendants": scope.include_descendants,
    }


def _request_payload(record: DelegatedAreaRequestRecord) -> dict[str, object]:
    return {
        "request_id": str(record.request_id),
        "requester_user_id": str(record.requester_user_id),
        "requester_name": record.requester_name,
        "requested_owner_user_id": str(record.requested_owner_user_id),
        "requested_owner_name": record.requested_owner_name,
        "scope_mode": record.scope_mode,
        "reason": record.reason,
        "requested_expires_at": record.requested_expires_at.isoformat(),
        "status": record.status,
        "decision_reason": record.decision_reason,
        "created_at": record.created_at.isoformat(),
        "scopes": [_scope_payload(scope) for scope in record.scopes],
    }


def _grant_payload(record: DelegatedAreaGrantRecord) -> dict[str, object]:
    return {
        "grant_id": str(record.grant_id),
        "source_request_id": (
            str(record.source_request_id) if record.source_request_id else None
        ),
        "grantor_user_id": str(record.grantor_user_id),
        "grantor_name": record.grantor_name,
        "visiting_collector_user_id": str(record.visiting_collector_user_id),
        "visiting_collector_name": record.visiting_collector_name,
        "effective_at": record.effective_at.isoformat(),
        "expires_at": record.expires_at.isoformat(),
        "revoked_at": record.revoked_at.isoformat() if record.revoked_at else None,
        "revocation_reason": record.revocation_reason,
        "scopes": [_scope_payload(scope) for scope in record.scopes],
    }


def create_delegated_area_router() -> APIRouter:
    router = APIRouter(tags=["delegated collector area access"])

    @router.get("/api/v1/collector/delegated-area/available-scopes")
    @router.get(
        "/api/mobile/v1/collector/delegated-area/available-scopes",
        include_in_schema=False,
    )
    def available_scopes(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresDelegatedAreaRepository = Depends(
            delegated_area_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_collector(
            permission="delegated_area.request",
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        records = repository.list_available_owner_scopes(
            requester_user_id=actor.user_id
        )
        return {"success": True, "data": [_scope_payload(item) for item in records]}

    @router.get("/api/v1/collector/delegated-area/owned-scopes")
    @router.get(
        "/api/mobile/v1/collector/delegated-area/owned-scopes",
        include_in_schema=False,
    )
    def owned_scopes(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresDelegatedAreaRepository = Depends(
            delegated_area_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_collector(
            permission="delegated_area.grant",
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        records = repository.list_owned_scopes(owner_user_id=actor.user_id)
        return {"success": True, "data": [_scope_payload(item) for item in records]}

    @router.post("/api/v1/collector/delegated-area/requests")
    @router.post(
        "/api/mobile/v1/collector/delegated-area/requests",
        include_in_schema=False,
    )
    def create_request(
        body: DelegatedAreaRequestBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresDelegatedAreaRepository = Depends(
            delegated_area_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_collector(
            permission="delegated_area.request",
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        if body.scope_mode == "selected_paths" and not body.scopes:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "delegated_area_scope_required",
                    "message": "Select at least one area or choose All my assigned areas.",
                },
            )
        try:
            record = repository.create_request(
                requester_user_id=actor.user_id,
                requested_owner_user_id=body.requested_owner_user_id,
                assignment_scopes=tuple(
                    (scope.assignment_id, scope.include_descendants)
                    for scope in body.scopes
                ),
                scope_mode=body.scope_mode,
                reason=body.reason,
                requested_expires_at=body.requested_expires_at,
            )
        except DelegatedAreaError as error:
            _raise_error(error)
        return {"success": True, "data": _request_payload(record)}

    @router.get("/api/v1/collector/delegated-area/requests/incoming")
    @router.get(
        "/api/mobile/v1/collector/delegated-area/requests/incoming",
        include_in_schema=False,
    )
    def incoming_requests(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresDelegatedAreaRepository = Depends(
            delegated_area_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_collector(
            permission="delegated_area.grant",
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        records = repository.list_incoming_requests(owner_user_id=actor.user_id)
        return {"success": True, "data": [_request_payload(item) for item in records]}

    @router.get("/api/v1/collector/delegated-area/requests/outgoing")
    @router.get(
        "/api/mobile/v1/collector/delegated-area/requests/outgoing",
        include_in_schema=False,
    )
    def outgoing_requests(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresDelegatedAreaRepository = Depends(
            delegated_area_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_collector(
            permission="delegated_area.view",
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        records = repository.list_outgoing_requests(requester_user_id=actor.user_id)
        return {"success": True, "data": [_request_payload(item) for item in records]}

    @router.post("/api/v1/collector/delegated-area/requests/{request_id}/approve")
    @router.post(
        "/api/mobile/v1/collector/delegated-area/requests/{request_id}/approve",
        include_in_schema=False,
    )
    def approve_request(
        request_id: UUID,
        body: DelegatedAreaDecisionBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresDelegatedAreaRepository = Depends(
            delegated_area_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_collector(
            permission="delegated_area.grant",
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = repository.approve_request(
                owner_user_id=actor.user_id,
                request_id=request_id,
                decision_reason=body.reason,
            )
        except DelegatedAreaError as error:
            _raise_error(error)
        return {"success": True, "data": _grant_payload(record)}

    @router.post("/api/v1/collector/delegated-area/requests/{request_id}/decline")
    @router.post(
        "/api/mobile/v1/collector/delegated-area/requests/{request_id}/decline",
        include_in_schema=False,
    )
    def decline_request(
        request_id: UUID,
        body: DelegatedAreaDecisionBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresDelegatedAreaRepository = Depends(
            delegated_area_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_collector(
            permission="delegated_area.grant",
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = repository.decline_request(
                owner_user_id=actor.user_id,
                request_id=request_id,
                decision_reason=body.reason,
            )
        except DelegatedAreaError as error:
            _raise_error(error)
        return {"success": True, "data": _request_payload(record)}

    @router.post("/api/v1/collector/delegated-area/requests/{request_id}/cancel")
    @router.post(
        "/api/mobile/v1/collector/delegated-area/requests/{request_id}/cancel",
        include_in_schema=False,
    )
    def cancel_request(
        request_id: UUID,
        body: DelegatedAreaDecisionBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresDelegatedAreaRepository = Depends(
            delegated_area_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_collector(
            permission="delegated_area.request",
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = repository.cancel_request(
                requester_user_id=actor.user_id,
                request_id=request_id,
                decision_reason=body.reason,
            )
        except DelegatedAreaError as error:
            _raise_error(error)
        return {"success": True, "data": _request_payload(record)}

    @router.get("/api/v1/collector/delegated-area/grants/active")
    @router.get(
        "/api/mobile/v1/collector/delegated-area/grants/active",
        include_in_schema=False,
    )
    def active_grants(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresDelegatedAreaRepository = Depends(
            delegated_area_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_collector(
            permission="delegated_area.view",
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        records = repository.list_active_grants(actor_user_id=actor.user_id)
        return {"success": True, "data": [_grant_payload(item) for item in records]}

    @router.post("/api/v1/collector/delegated-area/grants/{grant_id}/revoke")
    @router.post(
        "/api/mobile/v1/collector/delegated-area/grants/{grant_id}/revoke",
        include_in_schema=False,
    )
    def revoke_grant(
        grant_id: UUID,
        body: DelegatedAreaRevokeBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresDelegatedAreaRepository = Depends(
            delegated_area_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_collector(
            permission="delegated_area.grant",
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = repository.revoke_grant(
                grantor_user_id=actor.user_id,
                grant_id=grant_id,
                reason=body.reason,
            )
        except DelegatedAreaError as error:
            _raise_error(error)
        return {"success": True, "data": _grant_payload(record)}

    return router
