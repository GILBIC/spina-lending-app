from __future__ import annotations

from collections.abc import Generator
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .account_repository import (
    AccountConflict,
    AccountDisabled,
    AccountNotFound,
    PostgresAccountRepository,
)
from .auth_admin_client import SupabaseAuthAdminClient
from .auth_client import SupabaseAuthClient, SupabaseAuthError
from .management_repository import (
    AccountAdminRecord,
    DeviceAdminRecord,
    PostgresManagementRepository,
)


class StrictManagementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InviteStaffRequest(StrictManagementRequest):
    username: str = Field(min_length=3, max_length=80)
    email: str = Field(min_length=5, max_length=320)
    full_name: str = Field(min_length=2, max_length=200)
    role: Literal["collector", "employee", "management"]

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or any(ch.isspace() for ch in normalized):
            raise ValueError("Username cannot contain spaces.")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("Enter a valid email address.")
        return normalized

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        return " ".join(value.split())


class RoleChangeRequest(StrictManagementRequest):
    role: Literal["collector", "employee", "management"]


class AccountStatusRequest(StrictManagementRequest):
    status: Literal["active", "inactive", "locked"]


class DeviceStatusRequest(StrictManagementRequest):
    status: Literal["active", "revoked"]


def management_auth_client_dependency() -> Generator[SupabaseAuthClient, None, None]:
    client = SupabaseAuthClient()
    try:
        yield client
    finally:
        client.close()


def management_auth_admin_dependency() -> Generator[SupabaseAuthAdminClient, None, None]:
    client = SupabaseAuthAdminClient()
    try:
        yield client
    finally:
        client.close()


def management_account_repository_dependency() -> PostgresAccountRepository:
    return PostgresAccountRepository()


def management_repository_dependency() -> PostgresManagementRepository:
    return PostgresManagementRepository()


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Authentication required.")
    return token.strip()


def _management_actor(
    *,
    authorization: str | None,
    permission: str,
    auth: SupabaseAuthClient,
    accounts: PostgresAccountRepository,
):
    token = _bearer_token(authorization)
    try:
        identity = auth.get_user(access_token=token)
        context = accounts.get_context(identity.auth_user_id)
    except SupabaseAuthError as exc:
        if exc.status_code == 503:
            raise HTTPException(status_code=503, detail="Authentication service is unavailable.") from exc
        raise HTTPException(status_code=401, detail="Authentication required.") from exc
    except AccountNotFound as exc:
        raise HTTPException(status_code=401, detail="Account is no longer available.") from exc

    if context.status != "active":
        raise HTTPException(status_code=403, detail="This Gilbic account is not active.")
    if permission not in context.permissions:
        raise HTTPException(status_code=403, detail="Management permission is required.")
    return context


def _account_payload(record: AccountAdminRecord) -> dict[str, object]:
    return {
        "id": str(record.id),
        "auth_user_id": str(record.auth_user_id) if record.auth_user_id else None,
        "username": record.username,
        "email": record.email,
        "full_name": record.full_name,
        "status": record.status,
        "roles": list(record.roles),
        "device_count": record.device_count,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _device_payload(record: DeviceAdminRecord) -> dict[str, object]:
    return {
        "id": str(record.id),
        "user_id": str(record.user_id),
        "platform": record.platform,
        "app_version": record.app_version,
        "status": record.status,
        "registered_at": record.registered_at.isoformat(),
        "last_seen_at": record.last_seen_at.isoformat() if record.last_seen_at else None,
    }


def _repository_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, AccountNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (AccountConflict, AccountDisabled)):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail="Account administration could not be completed.")


def create_management_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/management", tags=["management"])

    @router.get("/accounts")
    def list_accounts(
        authorization: str | None = Header(default=None, alias="Authorization"),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        auth: SupabaseAuthClient = Depends(management_auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(management_account_repository_dependency),
        management: PostgresManagementRepository = Depends(management_repository_dependency),
    ) -> dict[str, object]:
        _management_actor(
            authorization=authorization,
            permission="account.manage",
            auth=auth,
            accounts=accounts,
        )
        records = management.list_accounts(limit=limit, offset=offset)
        return {"success": True, "data": {"accounts": [_account_payload(item) for item in records]}}

    @router.post("/accounts/invite", status_code=status.HTTP_201_CREATED)
    def invite_account(
        request: InviteStaffRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        auth: SupabaseAuthClient = Depends(management_auth_client_dependency),
        auth_admin: SupabaseAuthAdminClient = Depends(management_auth_admin_dependency),
        accounts: PostgresAccountRepository = Depends(management_account_repository_dependency),
        management: PostgresManagementRepository = Depends(management_repository_dependency),
    ) -> dict[str, object]:
        actor = _management_actor(
            authorization=authorization,
            permission="account.manage",
            auth=auth,
            accounts=accounts,
        )
        if accounts.username_exists(request.username):
            raise HTTPException(status_code=409, detail="Username is already in use.")

        try:
            auth_user_id = auth_admin.invite_user(email=request.email)
            record = management.create_staff_profile(
                actor_user_id=actor.user_id,
                auth_user_id=auth_user_id,
                username=request.username,
                email=request.email,
                full_name=request.full_name,
                role_code=request.role,
            )
        except SupabaseAuthError as exc:
            if exc.status_code == 503:
                raise HTTPException(status_code=503, detail="Staff invitation service is unavailable.") from exc
            if exc.status_code in {400, 409, 422}:
                raise HTTPException(status_code=409, detail="That email already has an authentication account.") from exc
            raise HTTPException(status_code=502, detail="Staff invitation could not be created.") from exc
        except (AccountConflict, AccountNotFound) as exc:
            try:
                auth_admin.delete_user(auth_user_id=auth_user_id)
            except (SupabaseAuthError, UnboundLocalError):
                pass
            raise _repository_exception(exc) from exc

        return {
            "success": True,
            "data": {
                "invitation_sent": True,
                "account": _account_payload(record),
            },
        }

    @router.patch("/accounts/{target_user_id}/role")
    def change_role(
        target_user_id: UUID,
        request: RoleChangeRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        auth: SupabaseAuthClient = Depends(management_auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(management_account_repository_dependency),
        management: PostgresManagementRepository = Depends(management_repository_dependency),
    ) -> dict[str, object]:
        actor = _management_actor(
            authorization=authorization,
            permission="account.manage",
            auth=auth,
            accounts=accounts,
        )
        try:
            record = management.set_role(
                actor_user_id=actor.user_id,
                target_user_id=target_user_id,
                role_code=request.role,
            )
        except (AccountConflict, AccountNotFound) as exc:
            raise _repository_exception(exc) from exc
        return {"success": True, "data": {"account": _account_payload(record)}}

    @router.patch("/accounts/{target_user_id}/status")
    def change_account_status(
        target_user_id: UUID,
        request: AccountStatusRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        auth: SupabaseAuthClient = Depends(management_auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(management_account_repository_dependency),
        management: PostgresManagementRepository = Depends(management_repository_dependency),
    ) -> dict[str, object]:
        actor = _management_actor(
            authorization=authorization,
            permission="account.manage",
            auth=auth,
            accounts=accounts,
        )
        try:
            record = management.set_status(
                actor_user_id=actor.user_id,
                target_user_id=target_user_id,
                account_status=request.status,
            )
        except (AccountConflict, AccountNotFound) as exc:
            raise _repository_exception(exc) from exc
        return {"success": True, "data": {"account": _account_payload(record)}}

    @router.get("/accounts/{target_user_id}/devices")
    def list_devices(
        target_user_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        auth: SupabaseAuthClient = Depends(management_auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(management_account_repository_dependency),
        management: PostgresManagementRepository = Depends(management_repository_dependency),
    ) -> dict[str, object]:
        _management_actor(
            authorization=authorization,
            permission="device.manage",
            auth=auth,
            accounts=accounts,
        )
        try:
            records = management.list_devices(target_user_id=target_user_id)
        except AccountNotFound as exc:
            raise _repository_exception(exc) from exc
        return {"success": True, "data": {"devices": [_device_payload(item) for item in records]}}

    @router.patch("/devices/{device_id}/status")
    def change_device_status(
        device_id: UUID,
        request: DeviceStatusRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        auth: SupabaseAuthClient = Depends(management_auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(management_account_repository_dependency),
        management: PostgresManagementRepository = Depends(management_repository_dependency),
    ) -> dict[str, object]:
        actor = _management_actor(
            authorization=authorization,
            permission="device.manage",
            auth=auth,
            accounts=accounts,
        )
        try:
            record = management.set_device_status(
                actor_user_id=actor.user_id,
                device_id=device_id,
                device_status=request.status,
            )
        except (AccountConflict, AccountNotFound) as exc:
            raise _repository_exception(exc) from exc
        return {"success": True, "data": {"device": _device_payload(record)}}

    return router
