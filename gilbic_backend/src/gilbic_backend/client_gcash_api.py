from __future__ import annotations

from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .client_gcash_repository import (
    ClientGcashAllocation,
    ClientGcashIntentNotFound,
    ClientGcashIntentRecord,
    PostgresClientGcashPaymentIntentRepository,
)
from .client_loan_repository import (
    ClientBorrowerNotLinked,
    PostgresClientLoanRepository,
)
from .config import get_settings
from .gcash_gateway import (
    GcashGateway,
    GcashGatewayError,
    GcashGatewayUnavailable,
    GcashCheckoutRequest,
    create_gcash_gateway,
)
from .request_auth import authenticated_device_context


class ClientGcashAllocationRequest(BaseModel):
    loan_id: UUID
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)


class ClientGcashIntentRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=120)
    allocations: list[ClientGcashAllocationRequest] = Field(min_length=1, max_length=8)


def client_gcash_intent_repository_dependency() -> PostgresClientGcashPaymentIntentRepository:
    return PostgresClientGcashPaymentIntentRepository()


def client_loan_repository_dependency() -> PostgresClientLoanRepository:
    return PostgresClientLoanRepository()


def gcash_gateway_dependency() -> GcashGateway:
    return create_gcash_gateway()


def _require_client_actor(
    *,
    authorization: str | None,
    x_device_id: str | None,
    auth: SupabaseAuthClient,
    accounts: PostgresAccountRepository,
):
    actor = authenticated_device_context(
        authorization=authorization,
        device_identifier=x_device_id,
        auth=auth,
        accounts=accounts,
    )
    if "client" not in actor.roles:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "client_role_required",
                "message": "Only a linked client account can use GCash payment.",
            },
        )
    return actor


def _capability_payload(gateway: GcashGateway) -> dict[str, object]:
    capability = gateway.capability()
    live_ready = (
        capability.checkout_available
        and capability.settlement_verification_ready
        and capability.mode == "live"
    )
    sandbox_ready = capability.checkout_available and capability.mode == "sandbox"
    return {
        "provider": capability.provider,
        "mode": capability.mode,
        "checkout_available": capability.checkout_available,
        "settlement_verification_ready": capability.settlement_verification_ready,
        "payment_available": live_ready or sandbox_ready,
        "message": capability.message,
        "official_payment_rule": (
            "Opening or completing provider checkout does not itself create an official "
            "SPINA loan payment. A verified provider event must pass the protected "
            "collection/accounting workflow first."
        ),
    }


def _intent_payload(record: ClientGcashIntentRecord) -> dict[str, object]:
    return {
        "intent_id": str(record.intent_id),
        "provider": record.provider,
        "mode": record.provider_mode,
        "provider_reference": record.provider_reference,
        "status": record.status,
        "currency": record.currency,
        "amount": format(record.amount, "f"),
        "checkout_url": record.checkout_url,
        "qr_value": record.qr_value,
        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        "verified_paid_at": (
            record.verified_paid_at.isoformat() if record.verified_paid_at else None
        ),
        "official_payment_posted": record.official_collection_transaction_id is not None,
        "official_collection_transaction_id": (
            str(record.official_collection_transaction_id)
            if record.official_collection_transaction_id
            else None
        ),
        "allocations": [
            {"loan_id": str(item.loan_id), "amount": format(item.amount, "f")}
            for item in record.allocations
        ],
    }


def create_client_gcash_router() -> APIRouter:
    router = APIRouter(tags=["client GCash"])

    @router.get("/api/v1/client/gcash/config")
    @router.get("/api/mobile/v1/client/gcash/config", include_in_schema=False)
    def get_gcash_config(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        gateway: GcashGateway = Depends(gcash_gateway_dependency),
    ) -> dict[str, object]:
        _require_client_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        return {"success": True, "data": _capability_payload(gateway)}

    @router.post("/api/v1/client/gcash/payment-intents")
    @router.post(
        "/api/mobile/v1/client/gcash/payment-intents",
        include_in_schema=False,
    )
    def create_payment_intent(
        request: ClientGcashIntentRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        loans: PostgresClientLoanRepository = Depends(client_loan_repository_dependency),
        intents: PostgresClientGcashPaymentIntentRepository = Depends(
            client_gcash_intent_repository_dependency
        ),
        gateway: GcashGateway = Depends(gcash_gateway_dependency),
    ) -> dict[str, object]:
        actor = _require_client_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        capability = gateway.capability()
        if not capability.checkout_available:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "gcash_not_connected",
                    "message": capability.message,
                },
            )
        if capability.mode == "live" and not capability.settlement_verification_ready:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "gcash_live_verification_not_ready",
                    "message": (
                        "Live GCash checkout is blocked until the provider-specific "
                        "signed settlement verification is connected."
                    ),
                },
            )

        try:
            portfolio = loans.list_for_user(user_id=actor.user_id)
        except ClientBorrowerNotLinked as error:
            raise HTTPException(
                status_code=404,
                detail={"code": error.code, "message": str(error)},
            ) from error

        requested: list[ClientGcashAllocation] = []
        seen: set[UUID] = set()
        available = {loan.loan_id: loan for loan in portfolio.loans}
        for allocation in request.allocations:
            if allocation.loan_id in seen:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "gcash_duplicate_loan_allocation",
                        "message": "Each loan may appear only once in a GCash payment.",
                    },
                )
            seen.add(allocation.loan_id)
            loan = available.get(allocation.loan_id)
            if loan is None or loan.status.strip().lower() != "active":
                raise HTTPException(
                    status_code=404,
                    detail={
                        "code": "gcash_loan_not_available",
                        "message": "One selected loan is not an active loan on this client account.",
                    },
                )
            try:
                amount = Decimal(allocation.amount).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError) as error:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "gcash_invalid_amount",
                        "message": "GCash payment amounts must be valid peso amounts.",
                    },
                ) from error
            if amount <= 0 or amount > loan.remaining_balance:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "gcash_amount_exceeds_loan_balance",
                        "message": (
                            "A GCash allocation must be above zero and cannot exceed "
                            "the selected loan's current official balance."
                        ),
                    },
                )
            requested.append(ClientGcashAllocation(loan_id=loan.loan_id, amount=amount))

        normalized_key = request.idempotency_key.strip()
        existing = intents.find_by_idempotency(
            user_id=actor.user_id,
            idempotency_key=normalized_key,
        )
        requested_tuple = tuple(sorted(requested, key=lambda item: str(item.loan_id)))
        if existing is not None:
            existing_tuple = tuple(
                sorted(existing.allocations, key=lambda item: str(item.loan_id))
            )
            if existing_tuple != requested_tuple:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "gcash_idempotency_conflict",
                        "message": (
                            "This GCash retry key already belongs to a different payment. "
                            "Refresh and start a new payment."
                        ),
                    },
                )
            return {"success": True, "data": _intent_payload(existing)}

        record = intents.create(
            client_id=portfolio.client_id,
            user_id=actor.user_id,
            provider=capability.provider,
            provider_mode=capability.mode,
            idempotency_key=normalized_key,
            allocations=requested_tuple,
        )
        try:
            checkout = gateway.create_checkout(
                GcashCheckoutRequest(
                    merchant_reference=f"spina-gcash-{record.intent_id}",
                    amount=record.amount,
                    description="SPINA loan payment",
                    return_url=get_settings().gcash_return_url.strip() or None,
                    metadata={
                        "spina_intent_id": str(record.intent_id),
                        "spina_client_id": str(record.client_id),
                    },
                )
            )
            record = intents.mark_provider_pending(
                intent_id=record.intent_id,
                checkout=checkout,
            )
        except GcashGatewayError as error:
            intents.mark_failed(intent_id=record.intent_id, message=str(error))
            status_code = 503 if isinstance(error, GcashGatewayUnavailable) else 502
            raise HTTPException(
                status_code=status_code,
                detail={"code": error.code, "message": str(error)},
            ) from error

        return {"success": True, "data": _intent_payload(record)}

    @router.get("/api/v1/client/gcash/payment-intents/{intent_id}")
    @router.get(
        "/api/mobile/v1/client/gcash/payment-intents/{intent_id}",
        include_in_schema=False,
    )
    def get_payment_intent(
        intent_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        intents: PostgresClientGcashPaymentIntentRepository = Depends(
            client_gcash_intent_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _require_client_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = intents.get_for_user(user_id=actor.user_id, intent_id=intent_id)
        except ClientGcashIntentNotFound as error:
            raise HTTPException(
                status_code=404,
                detail={"code": error.code, "message": str(error)},
            ) from error
        return {"success": True, "data": _intent_payload(record)}

    return router
