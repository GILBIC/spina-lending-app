from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

import httpx

from .config import Settings, get_settings


class GcashGatewayError(RuntimeError):
    code = "gcash_gateway_error"


class GcashGatewayUnavailable(GcashGatewayError):
    code = "gcash_gateway_unavailable"


class GcashGatewayRejected(GcashGatewayError):
    code = "gcash_gateway_rejected"


@dataclass(frozen=True, slots=True)
class GcashCapability:
    provider: str
    mode: str
    checkout_available: bool
    settlement_verification_ready: bool
    message: str


@dataclass(frozen=True, slots=True)
class GcashCheckoutRequest:
    merchant_reference: str
    amount: Decimal
    description: str
    return_url: str | None
    metadata: dict[str, str]


@dataclass(frozen=True, slots=True)
class GcashCheckoutSession:
    provider_reference: str
    status: str
    checkout_url: str | None
    qr_value: str | None
    expires_at: str | None
    raw_payload: dict[str, Any]


class GcashGateway(Protocol):
    def capability(self) -> GcashCapability: ...

    def create_checkout(self, request: GcashCheckoutRequest) -> GcashCheckoutSession: ...


class DisabledGcashGateway:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def capability(self) -> GcashCapability:
        return GcashCapability(
            provider=self._settings.gcash_provider.strip() or "unconfigured",
            mode="disabled",
            checkout_available=False,
            settlement_verification_ready=False,
            message=(
                "Direct GCash payment is prepared in SPINA, but a business payment "
                "provider has not been connected yet."
            ),
        )

    def create_checkout(self, request: GcashCheckoutRequest) -> GcashCheckoutSession:
        del request
        raise GcashGatewayUnavailable(self.capability().message)


class GenericHttpGcashGateway:
    """Thin provider adapter boundary for a future business GCash API.

    The mobile app never sees provider secrets. The backend sends one normalized
    checkout request and accepts a small normalized response shape. When the real
    business/provider API is obtained, only this adapter (or another implementation
    of ``GcashGateway``) needs provider-specific field/signature changes.

    This adapter intentionally does *not* declare settlement verification ready.
    A provider-specific signed webhook/status-verification implementation is required
    before a live provider success may become an official SPINA payment.
    """

    def __init__(self, settings: Settings, *, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client

    def capability(self) -> GcashCapability:
        configured = bool(
            self._settings.gcash_api_base_url.strip()
            and self._settings.gcash_api_key.strip()
        )
        if not configured:
            return GcashCapability(
                provider=self._settings.gcash_provider.strip() or "generic_http",
                mode=self._settings.gcash_mode,
                checkout_available=False,
                settlement_verification_ready=False,
                message=(
                    "GCash checkout is not connected. Add the business provider API "
                    "URL and server-side credential when they are issued."
                ),
            )
        return GcashCapability(
            provider=self._settings.gcash_provider.strip() or "generic_http",
            mode=self._settings.gcash_mode,
            checkout_available=True,
            settlement_verification_ready=False,
            message=(
                "GCash checkout connection is configured. Provider-specific verified "
                "settlement handling is still required before live payments can post."
            ),
        )

    def create_checkout(self, request: GcashCheckoutRequest) -> GcashCheckoutSession:
        capability = self.capability()
        if not capability.checkout_available:
            raise GcashGatewayUnavailable(capability.message)

        base = self._settings.gcash_api_base_url.rstrip("/")
        path = self._settings.gcash_checkout_path.strip() or "/payment-intents"
        endpoint = f"{base}/{path.lstrip('/')}"
        payload: dict[str, object] = {
            "merchant_reference": request.merchant_reference,
            "amount": format(request.amount, "f"),
            "currency": "PHP",
            "payment_method": "gcash",
            "description": request.description,
            "metadata": request.metadata,
        }
        if request.return_url:
            payload["return_url"] = request.return_url

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._settings.gcash_api_key}",
            "Idempotency-Key": request.merchant_reference,
        }
        owns_client = self._client is None
        client = self._client or httpx.Client(
            timeout=self._settings.gcash_timeout_seconds,
        )
        try:
            response = client.post(endpoint, json=payload, headers=headers)
        except httpx.HTTPError as error:
            raise GcashGatewayUnavailable(
                "The GCash payment provider could not be reached. Try again later."
            ) from error
        finally:
            if owns_client:
                client.close()

        try:
            body = response.json()
        except ValueError as error:
            raise GcashGatewayRejected(
                "The GCash provider returned an unreadable checkout response."
            ) from error
        if not isinstance(body, dict):
            raise GcashGatewayRejected(
                "The GCash provider returned an invalid checkout response."
            )
        if response.status_code < 200 or response.status_code >= 300:
            message = _first_text(
                body.get("message"),
                body.get("detail"),
                body.get("error"),
            ) or "The GCash provider rejected the checkout request."
            raise GcashGatewayRejected(message)

        provider_reference = _first_text(
            body.get("id"),
            body.get("reference"),
            body.get("payment_intent_id"),
            body.get("checkout_id"),
        )
        if not provider_reference:
            raise GcashGatewayRejected(
                "The GCash provider response did not include a payment reference."
            )

        return GcashCheckoutSession(
            provider_reference=provider_reference,
            status=_first_text(body.get("status")) or "provider_pending",
            checkout_url=_first_text(
                body.get("checkout_url"),
                body.get("redirect_url"),
                body.get("payment_url"),
            ),
            qr_value=_first_text(body.get("qr_value"), body.get("qr_code")),
            expires_at=_first_text(body.get("expires_at")),
            raw_payload=body,
        )


def create_gcash_gateway(settings: Settings | None = None) -> GcashGateway:
    active = settings or get_settings()
    mode = active.gcash_mode.strip().lower()
    if mode == "disabled":
        return DisabledGcashGateway(active)
    if mode not in {"sandbox", "live"}:
        raise GcashGatewayUnavailable(
            "GCash mode must be disabled, sandbox, or live."
        )
    return GenericHttpGcashGateway(active)


def _first_text(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = _first_text(value.get("message"), value.get("detail"))
            if nested:
                return nested
    return None
