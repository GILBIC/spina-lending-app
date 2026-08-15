from __future__ import annotations

from collections.abc import Generator
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .account_repository import (
    AccountConflict,
    AccountDisabled,
    AccountNotFound,
    DeviceRevoked,
    PostgresAccountRepository,
)
from .auth_client import AuthSession, SupabaseAuthClient, SupabaseAuthError
from .config import Settings, get_settings
from .mobile_version_policy import (
    InvalidMobileVersionPolicy,
    UnsupportedMobileAppVersion,
    enforce_mobile_app_version,
)
from .request_auth import (
    active_device_context,
    authenticated_device_context,
    bearer_token,
)


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(StrictRequest):
    username: str = Field(min_length=3, max_length=80)
    email: str = Field(min_length=5, max_length=320)
    full_name: str = Field(min_length=2, max_length=200)
    client_code: str = Field(min_length=2, max_length=100)
    phone_number: str | None = Field(default=None, max_length=30)
    password: str = Field(min_length=8, max_length=200)

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

    @field_validator("client_code")
    @classmethod
    def normalize_client_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Client code is required.")
        return normalized

    @field_validator("phone_number")
    @classmethod
    def normalize_phone_number(cls, value: str | None) -> str | None:
        normalized = (value or "").strip()
        return normalized or None


class LoginRequest(StrictRequest):
    username: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=200)
    device_id: str | None = Field(default=None, max_length=300)
    platform: Literal["android", "ios", "web", "desktop"] | None = None
    app_version: str | None = Field(default=None, max_length=60)

    @field_validator("username")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        return value.strip()


class RefreshRequest(StrictRequest):
    refresh_token: str = Field(min_length=10, max_length=4096)


def auth_client_dependency() -> Generator[SupabaseAuthClient, None, None]:
    client = SupabaseAuthClient()
    try:
        yield client
    finally:
        client.close()


def account_repository_dependency() -> PostgresAccountRepository:
    return PostgresAccountRepository()


def _user_payload(context) -> dict[str, object]:
    return {
        "id": str(context.user_id),
        "username": context.username,
        "full_name": context.full_name,
        "email": context.email,
        "role": context.primary_role_name,
        "roles": list(context.roles),
        "permissions": list(context.permissions),
        "status": context.status,
        "device_registered": context.device_registered,
    }


def _session_payload(session: AuthSession, context) -> dict[str, object]:
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_at": session.expires_at.isoformat() if session.expires_at else None,
        "user": _user_payload(context),
        "permissions": list(context.permissions),
    }


def _auth_exception(exc: SupabaseAuthError, *, login: bool = False) -> HTTPException:
    if exc.status_code == 503:
        return HTTPException(status_code=503, detail="Authentication service is unavailable.")
    if login:
        return HTTPException(status_code=401, detail="Invalid username or password.")
    if exc.status_code in {400, 409, 422}:
        return HTTPException(status_code=409, detail="An account with these credentials already exists.")
    return HTTPException(status_code=502, detail="Authentication service could not complete the request.")


def _enforce_mobile_auth_version(
    http_request: Request,
    *,
    platform: str | None,
    app_version: str | None,
    settings: Settings,
) -> None:
    if not http_request.url.path.startswith("/api/mobile/"):
        return
    try:
        enforce_mobile_app_version(
            platform=platform,
            app_version=app_version,
            settings=settings,
        )
    except UnsupportedMobileAppVersion as exc:
        raise HTTPException(status_code=426, detail=str(exc)) from exc
    except InvalidMobileVersionPolicy as exc:
        raise HTTPException(
            status_code=503,
            detail="Mobile version policy is temporarily unavailable.",
        ) from exc


def create_auth_router() -> APIRouter:
    router = APIRouter(tags=["authentication"])

    @router.post("/api/v1/auth/register", status_code=status.HTTP_201_CREATED)
    @router.post(
        "/api/mobile/v1/auth/register",
        status_code=status.HTTP_201_CREATED,
        include_in_schema=False,
    )
    def register(
        request: RegisterRequest,
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
    ) -> dict[str, object]:
        if accounts.username_exists(request.username):
            raise HTTPException(status_code=409, detail="Username is already in use.")
        try:
            session = auth.sign_up(email=request.email, password=request.password)
            context = accounts.create_client_profile(
                auth_user_id=session.auth_user_id,
                username=request.username,
                email=request.email,
                full_name=request.full_name,
                claimed_client_code=request.client_code,
                claimed_phone_number=request.phone_number,
            )
        except SupabaseAuthError as exc:
            raise _auth_exception(exc) from exc
        except AccountConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return {
            "success": True,
            "data": {
                "requires_email_confirmation": session.access_token is None,
                "approval_status": "pending",
                "message": (
                    "Registration received. Management must approve and link "
                    "your account to your borrower record before you can sign in."
                ),
                "user": _user_payload(context),
            },
        }

    @router.post("/api/v1/auth/login")
    @router.post("/api/mobile/v1/auth/login", include_in_schema=False)
    def login(
        request: LoginRequest,
        http_request: Request,
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        settings: Settings = Depends(get_settings),
    ) -> dict[str, object]:
        _enforce_mobile_auth_version(
            http_request,
            platform=request.platform,
            app_version=request.app_version,
            settings=settings,
        )
        try:
            email = accounts.resolve_email(request.username)
            session = auth.sign_in(email=email, password=request.password)
            context = accounts.activate_and_register_device(
                auth_user_id=session.auth_user_id,
                device_identifier=request.device_id,
                platform=request.platform,
                app_version=request.app_version,
            )
        except (AccountNotFound, SupabaseAuthError) as exc:
            if isinstance(exc, SupabaseAuthError) and exc.status_code == 503:
                raise _auth_exception(exc, login=True) from exc
            raise HTTPException(status_code=401, detail="Invalid username or password.") from exc
        except AccountDisabled as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except DeviceRevoked as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AccountConflict as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return {"success": True, "data": _session_payload(session, context)}

    @router.post("/api/v1/auth/refresh")
    @router.post("/api/mobile/v1/auth/refresh", include_in_schema=False)
    def refresh(
        request: RefreshRequest,
        http_request: Request,
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        x_app_platform: str | None = Header(default=None, alias="X-App-Platform"),
        x_app_version: str | None = Header(default=None, alias="X-App-Version"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        settings: Settings = Depends(get_settings),
    ) -> dict[str, object]:
        _enforce_mobile_auth_version(
            http_request,
            platform=x_app_platform,
            app_version=x_app_version,
            settings=settings,
        )
        try:
            session = auth.refresh(refresh_token=request.refresh_token)
        except SupabaseAuthError as exc:
            raise _auth_exception(exc, login=True) from exc
        context = active_device_context(
            auth_user_id=session.auth_user_id,
            device_identifier=x_device_id,
            accounts=accounts,
        )
        return {"success": True, "data": _session_payload(session, context)}

    @router.get("/api/v1/auth/me")
    @router.get("/api/mobile/v1/auth/me", include_in_schema=False)
    def me(
        http_request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        x_app_platform: str | None = Header(default=None, alias="X-App-Platform"),
        x_app_version: str | None = Header(default=None, alias="X-App-Version"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        settings: Settings = Depends(get_settings),
    ) -> dict[str, object]:
        _enforce_mobile_auth_version(
            http_request,
            platform=x_app_platform,
            app_version=x_app_version,
            settings=settings,
        )
        context = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        return {"success": True, "data": {"user": _user_payload(context)}}

    @router.post("/api/v1/auth/logout")
    @router.post("/api/mobile/v1/auth/logout", include_in_schema=False)
    def logout(
        authorization: str | None = Header(default=None, alias="Authorization"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
    ) -> dict[str, bool]:
        token = bearer_token(authorization)
        try:
            auth.sign_out(access_token=token)
        except SupabaseAuthError as exc:
            if exc.status_code not in {401, 403}:
                raise _auth_exception(exc) from exc
        return {"success": True}

    return router
