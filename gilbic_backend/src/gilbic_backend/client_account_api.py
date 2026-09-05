from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .account_repository import AccountConflict, AccountNotFound, PostgresAccountRepository
from .auth_admin_client import SupabaseAuthAdminClient
from .auth_client import SupabaseAuthClient, SupabaseAuthError
from .client_account_repository import PostgresClientAccountRepository
from .client_credentials import generate_password
from .credential_mailer import CredentialDeliveryResult, SmtpCredentialMailer
from .management_api import (
    _account_payload,
    _management_actor,
    _management_actor_with_any_permission,
    _repository_exception,
    management_account_repository_dependency,
    management_auth_admin_dependency,
    management_auth_client_dependency,
)


class StrictClientAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateClientAccountRequest(StrictClientAccountRequest):
    client_id: UUID
    email: str = Field(min_length=5, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("Enter a valid email address.")
        return normalized


def client_account_repository_dependency() -> PostgresClientAccountRepository:
    return PostgresClientAccountRepository()


def client_credential_mailer_dependency() -> SmtpCredentialMailer:
    return SmtpCredentialMailer()


def _delivery_payload(result: CredentialDeliveryResult) -> dict[str, object]:
    return {"sent": result.sent, "detail": result.detail}


def _auth_admin_exception(exc: SupabaseAuthError, *, action: str) -> HTTPException:
    if exc.status_code == 503:
        return HTTPException(
            status_code=503,
            detail=f"Client {action} service is unavailable.",
        )
    if exc.status_code in {400, 409, 422}:
        return HTTPException(
            status_code=409,
            detail=(
                "That email already has an authentication account."
                if action == "account creation"
                else "The account password could not be replaced."
            ),
        )
    if exc.status_code == 404:
        return HTTPException(status_code=404, detail="Authentication account was not found.")
    return HTTPException(
        status_code=502,
        detail=f"Client {action} could not be completed.",
    )


def create_client_account_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/management", tags=["management"])

    @router.post("/client-accounts", status_code=status.HTTP_201_CREATED)
    def create_client_account(
        request: CreateClientAccountRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(management_auth_client_dependency),
        auth_admin: SupabaseAuthAdminClient = Depends(management_auth_admin_dependency),
        accounts: PostgresAccountRepository = Depends(management_account_repository_dependency),
        repository: PostgresClientAccountRepository = Depends(
            client_account_repository_dependency
        ),
        mailer: SmtpCredentialMailer = Depends(client_credential_mailer_dependency),
    ) -> dict[str, object]:
        actor = _management_actor(
            authorization=authorization,
            device_identifier=x_device_id,
            permission="account.manage",
            auth=auth,
            accounts=accounts,
        )
        if "management" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail="Management role is required to create Client accounts.",
            )

        try:
            username = repository.next_client_username(client_id=request.client_id)
        except (AccountConflict, AccountNotFound) as exc:
            raise _repository_exception(exc) from exc

        password = generate_password()
        auth_user_id: UUID | None = None
        try:
            auth_user_id = auth_admin.create_user(
                email=request.email,
                password=password,
                email_confirm=True,
            )
            record = repository.create_client_account_profile(
                actor_user_id=actor.user_id,
                auth_user_id=auth_user_id,
                username=username,
                email=request.email,
                client_id=request.client_id,
            )
        except SupabaseAuthError as exc:
            raise _auth_admin_exception(exc, action="account creation") from exc
        except (AccountConflict, AccountNotFound) as exc:
            if auth_user_id is not None:
                try:
                    auth_admin.delete_user(auth_user_id=auth_user_id)
                except SupabaseAuthError:
                    pass
            raise _repository_exception(exc) from exc

        try:
            delivery = mailer.send_client_credentials(
                email=request.email,
                full_name=record.full_name,
                username=username,
                password=password,
            )
        except Exception:
            delivery = CredentialDeliveryResult(
                sent=False,
                detail=(
                    "SPINA could not send the credential email. Provide the displayed "
                    "credentials to the borrower manually."
                ),
            )

        return {
            "success": True,
            "data": {
                "account": _account_payload(record),
                "credentials": {
                    "username": username,
                    "password": password,
                },
                "delivery": _delivery_payload(delivery),
            },
        }

    @router.post("/accounts/{target_user_id}/password/reset")
    def reset_account_password(
        target_user_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(management_auth_client_dependency),
        auth_admin: SupabaseAuthAdminClient = Depends(management_auth_admin_dependency),
        accounts: PostgresAccountRepository = Depends(management_account_repository_dependency),
        repository: PostgresClientAccountRepository = Depends(
            client_account_repository_dependency
        ),
        mailer: SmtpCredentialMailer = Depends(client_credential_mailer_dependency),
    ) -> dict[str, object]:
        actor = _management_actor_with_any_permission(
            authorization=authorization,
            device_identifier=x_device_id,
            permissions=("account.manage", "client.credential.manage"),
            auth=auth,
            accounts=accounts,
        )
        try:
            target = repository.get_account(target_user_id=target_user_id)
        except (AccountConflict, AccountNotFound) as exc:
            raise _repository_exception(exc) from exc

        is_management = (
            "management" in actor.roles and "account.manage" in actor.permissions
        )
        may_reset_client = (
            "client.credential.manage" in actor.permissions
            and "client" in target.roles
        )
        if not (is_management or may_reset_client):
            raise HTTPException(
                status_code=403,
                detail="This account password reset is not permitted.",
            )
        if target.auth_user_id is None:
            raise HTTPException(
                status_code=409,
                detail="The selected SPINA account has no authentication identity.",
            )

        password = generate_password()
        try:
            auth_admin.update_user_password(
                auth_user_id=target.auth_user_id,
                password=password,
            )
        except SupabaseAuthError as exc:
            raise _auth_admin_exception(exc, action="password reset") from exc

        if "client" in target.roles and target.email:
            try:
                delivery = mailer.send_client_credentials(
                    email=target.email,
                    full_name=target.full_name,
                    username=target.username,
                    password=password,
                )
            except Exception:
                delivery = CredentialDeliveryResult(
                    sent=False,
                    detail=(
                        "SPINA could not send the replacement credential email. "
                        "Provide the displayed password to the borrower manually."
                    ),
                )
        else:
            delivery = CredentialDeliveryResult(
                sent=False,
                detail="Credential delivery is manual for staff account password resets.",
            )

        audit_recorded = True
        try:
            repository.record_password_reset(
                actor_user_id=actor.user_id,
                target_user_id=target_user_id,
                delivery_sent=delivery.sent,
            )
        except Exception:
            # Supabase already accepted the new password. Never hide that now-active
            # credential from Management merely because the secondary audit write failed.
            audit_recorded = False

        return {
            "success": True,
            "data": {
                "account": _account_payload(target),
                "credentials": {
                    "username": target.username,
                    "password": password,
                },
                "delivery": _delivery_payload(delivery),
                "audit_recorded": audit_recorded,
            },
        }

    return router
