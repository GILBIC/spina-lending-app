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

    @staticmethod
    def _response_user_id(response: httpx.Response, *, operation: str) -> UUID:
        raw_id = response.json().get("id")
        try:
            return UUID(str(raw_id))
        except (TypeError, ValueError) as exc:
            raise SupabaseAuthError(
                f"Supabase Auth did not return a valid {operation} user ID.",
                status_code=502,
                code="invalid_auth_admin_response",
            ) from exc

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
        return self._response_user_id(response, operation="invited")

    def create_user(
        self,
        *,
        email: str,
        password: str,
        email_confirm: bool = True,
        auth_user_id: UUID | None = None,
        provisioning_intent_id: UUID | None = None,
    ) -> UUID:
        payload: dict[str, object] = {
            "email": email.strip().lower(),
            "password": password,
            "email_confirm": email_confirm,
        }
        if auth_user_id is not None:
            payload["id"] = str(auth_user_id)
        if provisioning_intent_id is not None:
            payload["app_metadata"] = {
                "spina_provisioning_intent_id": str(provisioning_intent_id)
            }
        try:
            response = self._client.post(
                "/auth/v1/admin/users",
                headers=self._headers(),
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise SupabaseAuthError(
                "Authentication administration service is unavailable.",
                status_code=503,
                code="auth_admin_unavailable",
            ) from exc
        self._raise_for_error(response)
        return self._response_user_id(response, operation="created")

    def get_provisioned_user(
        self,
        *,
        auth_user_id: UUID,
        email: str,
        provisioning_intent_id: UUID,
    ) -> bool:
        """Reconcile one reserved identity, never an email-only account match."""
        try:
            response = self._client.get(
                f"/auth/v1/admin/users/{auth_user_id}",
                headers=self._headers(),
            )
        except httpx.HTTPError as exc:
            raise SupabaseAuthError(
                "Authentication reconciliation is unavailable.",
                status_code=503,
                code="auth_admin_unavailable",
            ) from exc
        if response.status_code == 404:
            return False
        self._raise_for_error(response)
        try:
            payload = response.json()
            matches = (
                UUID(str(payload.get("id"))) == auth_user_id
                and str(payload.get("email", "")).strip().lower()
                == email.strip().lower()
                and isinstance(payload.get("app_metadata"), dict)
                and payload["app_metadata"].get("spina_provisioning_intent_id")
                == str(provisioning_intent_id)
                and payload.get("deleted_at") is None
            )
        except (TypeError, ValueError, AttributeError):
            matches = False
        if not matches:
            raise SupabaseAuthError(
                "Authentication identity does not match this release request.",
                status_code=409,
                code="provisioning_identity_mismatch",
            )
        return True

    def update_user_password(self, *, auth_user_id: UUID, password: str) -> None:
        try:
            response = self._client.put(
                f"/auth/v1/admin/users/{auth_user_id}",
                headers=self._headers(),
                json={"password": password},
            )
        except httpx.HTTPError as exc:
            raise SupabaseAuthError(
                "Authentication administration service is unavailable.",
                status_code=503,
                code="auth_admin_unavailable",
            ) from exc
        self._raise_for_error(response)

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
