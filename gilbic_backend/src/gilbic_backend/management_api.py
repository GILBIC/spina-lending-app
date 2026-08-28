from __future__ import annotations

from collections.abc import Generator
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .account_repository import (
    AccountConflict,
    AccountContext,
    AccountNotFound,
    PostgresAccountRepository,
)
from .auth_admin_client import SupabaseAuthAdminClient
from .auth_client import SupabaseAuthClient, SupabaseAuthError
from .management_repository import (
    AccountAdminRecord,
    ClientLinkCandidate,
    ClientRegistrationRecord,
    DeviceAdminRecord,
    PostgresManagementRepository,
)
from .request_auth import authenticated_device_context


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


class ApproveClientRegistrationRequest(StrictManagementRequest):
    client_id: UUID
    review_note: str = Field(default="", max_length=500)

    @field_validator("review_note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        return " ".join(value.split())


class RejectClientRegistrationRequest(StrictManagementRequest):
    review_note: str = Field(min_length=3, max_length=500)

    @field_validator("review_note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        return " ".join(value.split())


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


def _management_actor(
    *,
    authorization: str | None,
    device_identifier: str | None,
    permission: str,
    auth: SupabaseAuthClient,
    accounts: PostgresAccountRepository,
):
    return authenticated_device_context(
        authorization=authorization,
        device_identifier=device_identifier,
        auth=auth,
        accounts=accounts,
        permission=permission,
        permission_error="Management permission is required.",
    )


def _management_actor_with_any_permission(
    *,
    authorization: str | None,
    device_identifier: str | None,
    permissions: tuple[str, ...],
    auth: SupabaseAuthClient,
    accounts: PostgresAccountRepository,
) -> AccountContext:
    actor = authenticated_device_context(
        authorization=authorization,
        device_identifier=device_identifier,
        auth=auth,
        accounts=accounts,
    )
    if not any(permission in actor.permissions for permission in permissions):
        raise HTTPException(status_code=403, detail="This action is not permitted for your account.")
    return actor


def _account_payload(record: AccountAdminRecord) -> dict[str, object]:
    return {
        "id": str(record.id),
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


def _client_registration_payload(
    record: ClientRegistrationRecord,
) -> dict[str, object]:
    return {
        "user_id": str(record.user_id),
        "username": record.username,
        "email": record.email,
        "full_name": record.full_name,
        "account_status": record.account_status,
        "claimed_client_code": record.claimed_client_code,
        "claimed_phone_number": record.claimed_phone_number,
        "registration_status": record.registration_status,
        "linked_client_id": (
            str(record.linked_client_id) if record.linked_client_id else None
        ),
        "linked_client_code": record.linked_client_code,
        "linked_client_name": record.linked_client_name,
        "review_note": record.review_note,
        "submitted_at": record.submitted_at.isoformat(),
        "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
    }


def _client_candidate_payload(record: ClientLinkCandidate) -> dict[str, object]:
    return {
        "id": str(record.id),
        "client_code": record.client_code,
        "full_name": record.full_name,
        "phone_number": record.phone_number,
        "area": record.area,
        "status": record.status,
    }


def _repository_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, AccountNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, AccountConflict):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail="Account administration could not be completed.")


def create_management_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/management", tags=["management"])

    @router.get("/accounts")
    def list_accounts(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        q: str | None = Query(default=None, max_length=200),
        role_code: Literal["collector", "employee", "management"] | None = Query(
            default=None,
            alias="role",
        ),
        account_status: Literal["active", "inactive", "locked", "pending"] | None = Query(
            default=None,
            alias="status",
        ),
        staff_only: bool = Query(default=False),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        auth: SupabaseAuthClient = Depends(management_auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(management_account_repository_dependency),
        management: PostgresManagementRepository = Depends(management_repository_dependency),
    ) -> dict[str, object]:
        _management_actor_with_any_permission(
            authorization=authorization,
            device_identifier=x_device_id,
            permissions=("account.manage", "device.manage"),
            auth=auth,
            accounts=accounts,
        )
        records = management.list_accounts(
            query=(q or "").strip() or None,
            role_code=role_code,
            account_status=account_status,
            staff_only=staff_only,
            limit=limit,
            offset=offset,
        )
        return {"success": True, "data": {"accounts": [_account_payload(item) for item in records]}}

    @router.get("/client-registrations")
    def list_client_registrations(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        registration_status: Literal["pending", "approved", "rejected"] = Query(
            default="pending",
            alias="status",
        ),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        auth: SupabaseAuthClient = Depends(management_auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(management_account_repository_dependency),
        management: PostgresManagementRepository = Depends(management_repository_dependency),
    ) -> dict[str, object]:
        _management_actor(
            authorization=authorization,
            device_identifier=x_device_id,
            permission="account.manage",
            auth=auth,
            accounts=accounts,
        )
        try:
            records = management.list_client_registrations(
                registration_status=registration_status,
                limit=limit,
                offset=offset,
            )
        except AccountConflict as exc:
            raise _repository_exception(exc) from exc
        return {
            "success": True,
            "data": {
                "registrations": [
                    _client_registration_payload(item) for item in records
                ]
            },
        }

    @router.get("/client-link-candidates")
    def search_client_link_candidates(
        q: str = Query(min_length=2, max_length=200),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        limit: int = Query(default=25, ge=1, le=50),
        auth: SupabaseAuthClient = Depends(management_auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(management_account_repository_dependency),
        management: PostgresManagementRepository = Depends(management_repository_dependency),
    ) -> dict[str, object]:
        _management_actor(
            authorization=authorization,
            device_identifier=x_device_id,
            permission="account.manage",
            auth=auth,
            accounts=accounts,
        )
        records = management.search_client_link_candidates(query=q, limit=limit)
        return {
            "success": True,
            "data": {
                "clients": [_client_candidate_payload(item) for item in records]
            },
        }

    @router.post("/client-registrations/{target_user_id}/approve")
    def approve_client_registration(
        target_user_id: UUID,
        request: ApproveClientRegistrationRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(management_auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(management_account_repository_dependency),
        management: PostgresManagementRepository = Depends(management_repository_dependency),
    ) -> dict[str, object]:
        actor = _management_actor(
            authorization=authorization,
            device_identifier=x_device_id,
            permission="account.manage",
            auth=auth,
            accounts=accounts,
        )
        try:
            record = management.approve_client_registration(
                actor_user_id=actor.user_id,
                target_user_id=target_user_id,
                client_id=request.client_id,
                review_note=request.review_note,
            )
        except (AccountConflict, AccountNotFound) as exc:
            raise _repository_exception(exc) from exc
        return {
            "success": True,
            "data": {
                "message": "Client account approved and linked.",
                "registration": _client_registration_payload(record),
            },
        }

    @router.post("/client-registrations/{target_user_id}/reject")
    def reject_client_registration(
        target_user_id: UUID,
        request: RejectClientRegistrationRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(management_auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(management_account_repository_dependency),
        management: PostgresManagementRepository = Depends(management_repository_dependency),
    ) -> dict[str, object]:
        actor = _management_actor(
            authorization=authorization,
            device_identifier=x_device_id,
            permission="account.manage",
            auth=auth,
            accounts=accounts,
        )
        try:
            record = management.reject_client_registration(
                actor_user_id=actor.user_id,
                target_user_id=target_user_id,
                review_note=request.review_note,
            )
        except (AccountConflict, AccountNotFound) as exc:
            raise _repository_exception(exc) from exc
        return {
            "success": True,
            "data": {
                "message": "Client registration rejected.",
                "registration": _client_registration_payload(record),
            },
        }

    @router.post("/accounts/invite", status_code=status.HTTP_201_CREATED)
    def invite_account(
        request: InviteStaffRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(management_auth_client_dependency),
        auth_admin: SupabaseAuthAdminClient = Depends(management_auth_admin_dependency),
        accounts: PostgresAccountRepository = Depends(management_account_repository_dependency),
        management: PostgresManagementRepository = Depends(management_repository_dependency),
    ) -> dict[str, object]:
        actor = _management_actor(
            authorization=authorization,
            device_identifier=x_device_id,
            permission="account.manage",
            auth=auth,
            accounts=accounts,
        )
        if accounts.username_exists(request.username):
            raise HTTPException(status_code=409, detail="Username is already in use.")

        auth_user_id: UUID | None = None
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
            if auth_user_id is not None:
                try:
                    auth_admin.delete_user(auth_user_id=auth_user_id)
                except SupabaseAuthError:
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
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(management_auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(management_account_repository_dependency),
        management: PostgresManagementRepository = Depends(management_repository_dependency),
    ) -> dict[str, object]:
        actor = _management_actor(
            authorization=authorization,
            device_identifier=x_device_id,
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
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(management_auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(management_account_repository_dependency),
        management: PostgresManagementRepository = Depends(management_repository_dependency),
    ) -> dict[str, object]:
        actor = _management_actor(
            authorization=authorization,
            device_identifier=x_device_id,
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
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(management_auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(management_account_repository_dependency),
        management: PostgresManagementRepository = Depends(management_repository_dependency),
    ) -> dict[str, object]:
        _management_actor(
            authorization=authorization,
            device_identifier=x_device_id,
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
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(management_auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(management_account_repository_dependency),
        management: PostgresManagementRepository = Depends(management_repository_dependency),
    ) -> dict[str, object]:
        actor = _management_actor(
            authorization=authorization,
            device_identifier=x_device_id,
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
