from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx

from .config import Settings, get_settings


class SupabaseAuthError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 502,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


@dataclass(frozen=True, slots=True)
class AuthSession:
    auth_user_id: UUID
    email: str | None
    access_token: str | None
    refresh_token: str | None
    expires_at: datetime | None
    email_confirmed: bool


class SupabaseAuthClient:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        if not self._settings.supabase_auth_configured:
            raise SupabaseAuthError(
                "Supabase Auth is not configured.",
                status_code=503,
                code="auth_not_configured",
            )
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self._settings.supabase_url.rstrip("/"),
            timeout=10.0,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _headers(self, *, access_token: str | None = None) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "apikey": self._settings.supabase_publishable_key,
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers

    def _raise_for_error(self, response: httpx.Response) -> None:
        if 200 <= response.status_code < 300:
            return
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        message = (
            payload.get("msg")
            or payload.get("message")
            or payload.get("error_description")
            or payload.get("error")
            or "Authentication request failed."
        )
        code = payload.get("code") or payload.get("error_code")
        raise SupabaseAuthError(
            str(message),
            status_code=response.status_code,
            code=str(code) if code else None,
        )

    @staticmethod
    def _session_from_payload(payload: dict[str, Any]) -> AuthSession:
        user_payload = payload.get("user") if isinstance(payload.get("user"), dict) else payload
        raw_id = user_payload.get("id")
        if not raw_id:
            raise SupabaseAuthError(
                "Supabase Auth did not return a user ID.",
                status_code=502,
                code="invalid_auth_response",
            )
        try:
            auth_user_id = UUID(str(raw_id))
        except ValueError as exc:
            raise SupabaseAuthError(
                "Supabase Auth returned an invalid user ID.",
                status_code=502,
                code="invalid_auth_response",
            ) from exc

        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        expires_at: datetime | None = None
        expires_in = payload.get("expires_in")
        if isinstance(expires_in, (int, float)):
            expires_at = datetime.now(UTC) + timedelta(seconds=float(expires_in))

        email = user_payload.get("email")
        email_confirmed = bool(
            user_payload.get("email_confirmed_at")
            or user_payload.get("confirmed_at")
        )
        return AuthSession(
            auth_user_id=auth_user_id,
            email=str(email) if email else None,
            access_token=str(access_token) if access_token else None,
            refresh_token=str(refresh_token) if refresh_token else None,
            expires_at=expires_at,
            email_confirmed=email_confirmed,
        )

    def sign_up(self, *, email: str, password: str) -> AuthSession:
        try:
            response = self._client.post(
                "/auth/v1/signup",
                headers=self._headers(),
                json={"email": email, "password": password},
            )
        except httpx.HTTPError as exc:
            raise SupabaseAuthError(
                "Authentication service is unavailable.",
                status_code=503,
                code="auth_unavailable",
            ) from exc
        self._raise_for_error(response)
        return self._session_from_payload(response.json())

    def sign_in(self, *, email: str, password: str) -> AuthSession:
        try:
            response = self._client.post(
                "/auth/v1/token",
                params={"grant_type": "password"},
                headers=self._headers(),
                json={"email": email, "password": password},
            )
        except httpx.HTTPError as exc:
            raise SupabaseAuthError(
                "Authentication service is unavailable.",
                status_code=503,
                code="auth_unavailable",
            ) from exc
        self._raise_for_error(response)
        session = self._session_from_payload(response.json())
        if not session.access_token:
            raise SupabaseAuthError(
                "Authentication service did not return an access token.",
                status_code=502,
                code="invalid_auth_response",
            )
        return session

    def get_user(self, *, access_token: str) -> AuthSession:
        try:
            response = self._client.get(
                "/auth/v1/user",
                headers=self._headers(access_token=access_token),
            )
        except httpx.HTTPError as exc:
            raise SupabaseAuthError(
                "Authentication service is unavailable.",
                status_code=503,
                code="auth_unavailable",
            ) from exc
        self._raise_for_error(response)
        return self._session_from_payload(response.json())

    def refresh(self, *, refresh_token: str) -> AuthSession:
        try:
            response = self._client.post(
                "/auth/v1/token",
                params={"grant_type": "refresh_token"},
                headers=self._headers(),
                json={"refresh_token": refresh_token},
            )
        except httpx.HTTPError as exc:
            raise SupabaseAuthError(
                "Authentication service is unavailable.",
                status_code=503,
                code="auth_unavailable",
            ) from exc
        self._raise_for_error(response)
        return self._session_from_payload(response.json())

    def sign_out(self, *, access_token: str) -> None:
        try:
            response = self._client.post(
                "/auth/v1/logout",
                headers=self._headers(access_token=access_token),
            )
        except httpx.HTTPError as exc:
            raise SupabaseAuthError(
                "Authentication service is unavailable.",
                status_code=503,
                code="auth_unavailable",
            ) from exc
        self._raise_for_error(response)
