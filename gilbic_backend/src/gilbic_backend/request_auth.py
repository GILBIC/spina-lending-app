from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException

from .account_repository import (
    AccountContext,
    AccountDisabled,
    AccountNotFound,
    DeviceApprovalRequired,
    DeviceNotRegistered,
    DeviceRequired,
    DeviceRevoked,
    PostgresAccountRepository,
)
from .auth_client import SupabaseAuthClient, SupabaseAuthError


def bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Authentication required.")
    return token.strip()


def active_device_context(
    *,
    auth_user_id: UUID,
    device_identifier: str | None,
    accounts: PostgresAccountRepository,
) -> AccountContext:
    normalized_device = (device_identifier or "").strip()
    if not normalized_device:
        raise HTTPException(status_code=400, detail="X-Device-Id is required.")
    if len(normalized_device) > 300:
        raise HTTPException(status_code=400, detail="X-Device-Id is invalid.")

    try:
        return accounts.get_context_for_device(
            auth_user_id=auth_user_id,
            device_identifier=normalized_device,
        )
    except DeviceRequired as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (DeviceApprovalRequired, DeviceNotRegistered, DeviceRevoked) as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except AccountDisabled as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except AccountNotFound as exc:
        raise HTTPException(status_code=401, detail="Account is no longer available.") from exc


def authenticated_device_context(
    *,
    authorization: str | None,
    device_identifier: str | None,
    auth: SupabaseAuthClient,
    accounts: PostgresAccountRepository,
    permission: str | None = None,
    permission_error: str = "Permission is required.",
) -> AccountContext:
    token = bearer_token(authorization)
    try:
        identity = auth.get_user(access_token=token)
    except SupabaseAuthError as exc:
        if exc.status_code == 503:
            raise HTTPException(
                status_code=503,
                detail="Authentication service is unavailable.",
            ) from exc
        raise HTTPException(status_code=401, detail="Authentication required.") from exc

    context = active_device_context(
        auth_user_id=identity.auth_user_id,
        device_identifier=device_identifier,
        accounts=accounts,
    )
    if permission is not None and permission not in context.permissions:
        raise HTTPException(status_code=403, detail=permission_error)
    return context
