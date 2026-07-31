from __future__ import annotations

from uuid import UUID

import httpx

from .auth_client import SupabaseAuthError
from .config import Settings, get_settings


class SupabaseAuthAdminClient:
    """Server-only Supabase Auth admin client.

    The secret key used here must never be sent to Flutter, browsers, or other
    untrusted clients. Gilbic application roles remain in core.* and are not
    stored in editable Auth user metadata.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        if not self._settings.supabase_admin_configured:
            raise SupabaseAuthError(
                "Supabase Auth administration is not configured.",
                status_code=503,
                code="auth_admin_not_configured",
            )
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self._settings.supabase_url.rstrip("/"),
            timeout=10.0,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _headers(self) -> dict[str, str]:
        secret = self._settings.supabase_secret_key
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "apikey": secret,
            "Authorization": f"Bearer {secret}",
        }

    @staticmethod
    def _raise_for_error(response: httpx.Response) -> None:
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
            or "Authentication administration request failed."
        )
        code = payload.get("code") or payload.get("error_code")
        raise SupabaseAuthError(
            str(message),
            status_code=response.status_code,
            code=str(code) if code else None,
        )

    def invite_user(self, *, email: str) -> UUID:
        params: dict[str, str] = {}
        redirect_to = self._settings.staff_invite_redirect_url.strip()
        if redirect_to:
            params["redirect_to"] = redirect_to
        try:
            response = self._client.post(
                "/auth/v1/invite",
                params=params,
                headers=self._headers(),
                json={"email": email.strip().lower()},
            )
        except httpx.HTTPError as exc:
            raise SupabaseAuthError(
                "Authentication administration service is unavailable.",
                status_code=503,
                code="auth_admin_unavailable",
            ) from exc
        self._raise_for_error(response)
        raw_id = response.json().get("id")
        try:
            return UUID(str(raw_id))
        except (TypeError, ValueError) as exc:
            raise SupabaseAuthError(
                "Supabase Auth did not return a valid invited user ID.",
                status_code=502,
                code="invalid_auth_admin_response",
            ) from exc

    def delete_user(self, *, auth_user_id: UUID) -> None:
        try:
            response = self._client.delete(
                f"/auth/v1/admin/users/{auth_user_id}",
                headers=self._headers(),
            )
        except httpx.HTTPError as exc:
            raise SupabaseAuthError(
                "Authentication administration service is unavailable.",
                status_code=503,
                code="auth_admin_unavailable",
            ) from exc
        self._raise_for_error(response)
