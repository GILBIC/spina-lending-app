from __future__ import annotations

from collections.abc import Generator
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

from .account_repository import AccountNotFound, PostgresAccountRepository
from .account_self_repository import AccountDeviceRecord, PostgresSelfAccountRepository
from .auth_client import SupabaseAuthClient
from .request_auth import authenticated_device_context


def account_auth_client_dependency() -> Generator[SupabaseAuthClient, None, None]:
    client = SupabaseAuthClient()
    try:
        yield client
    finally:
        client.close()


def account_repository_dependency() -> PostgresAccountRepository:
    return PostgresAccountRepository()


def self_account_repository_dependency() -> PostgresSelfAccountRepository:
    return PostgresSelfAccountRepository()


def _device_payload(
    record: AccountDeviceRecord,
    *,
    current_device_id: UUID | None,
) -> dict[str, object]:
    return {
        "id": str(record.id),
        "platform": record.platform,
        "app_version": record.app_version,
        "status": record.status,
        "registered_at": record.registered_at.isoformat(),
        "last_seen_at": record.last_seen_at.isoformat() if record.last_seen_at else None,
        "is_current": current_device_id == record.id,
    }


def _profile_payload(context) -> dict[str, object]:
    return {
        "id": str(context.user_id),
        "username": context.username,
        "email": context.email,
        "full_name": context.full_name,
        "role": context.primary_role_name,
        "roles": list(context.roles),
        "permissions": list(context.permissions),
        "status": context.status,
    }


def create_account_router() -> APIRouter:
    router = APIRouter(tags=["account"])

    @router.get("/api/v1/account")
    @router.get("/api/mobile/v1/account", include_in_schema=False)
    def get_account(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(account_auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        account_state: PostgresSelfAccountRepository = Depends(
            self_account_repository_dependency
        ),
    ) -> dict[str, object]:
        context = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        devices = account_state.list_devices(user_id=context.user_id)
        return {
            "success": True,
            "data": {
                "profile": _profile_payload(context),
                "devices": [
                    _device_payload(
                        item,
                        current_device_id=context.registered_device_id,
                    )
                    for item in devices
                ],
            },
        }

    @router.post("/api/v1/account/devices/{device_id}/revoke")
    @router.post(
        "/api/mobile/v1/account/devices/{device_id}/revoke",
        include_in_schema=False,
    )
    def revoke_device(
        device_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(account_auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        account_state: PostgresSelfAccountRepository = Depends(
            self_account_repository_dependency
        ),
    ) -> dict[str, object]:
        context = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        if context.registered_device_id == device_id:
            raise HTTPException(
                status_code=409,
                detail="Use Sign out to end the session on this device.",
            )
        try:
            record = account_state.revoke_device(
                user_id=context.user_id,
                device_id=device_id,
            )
        except AccountNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "success": True,
            "data": {
                "device": _device_payload(
                    record,
                    current_device_id=context.registered_device_id,
                )
            },
        }

    return router
