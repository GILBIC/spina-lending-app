from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid5

from fastapi import APIRouter, Depends, Header, HTTPException
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, field_validator

from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
)
from spina_mobile_collections.service import (
    CONTRACT_VERSION,
    CollectionConflict,
    CollectionRejected,
)

from .collection_api import collection_actor_dependency
from .concurrent_receipt_collection_posting import (
    ConcurrentReceiptSafeCollectionPostingBridge,
)
from .database import connect_database


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CombinedPaymentLeg(_StrictModel):
    route_entry_id: UUID
    loan_id: UUID
    route_revision: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)


class CombinedPaymentRequest(_StrictModel):
    client_transaction_id: UUID
    client_id: UUID
    collection_date: date
    recorded_at: datetime
    device_id: str = Field(min_length=1, max_length=500)
    device_sequence: int = Field(ge=1)
    legs: list[CombinedPaymentLeg] = Field(min_length=2, max_length=2)

    @field_validator("recorded_at")
    @classmethod
    def recorded_at_requires_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("recorded_at must include a timezone")
        return value

    @field_validator("legs")
    @classmethod
    def legs_must_be_unique(cls, value: list[CombinedPaymentLeg]):
        loan_ids = [item.loan_id for item in value]
        if len(set(loan_ids)) != len(loan_ids):
            raise ValueError("Combined payment legs must reference different loans.")
        return value


def _canonical_payload(body: CombinedPaymentRequest) -> dict[str, Any]:
    return {
        "client_transaction_id": str(body.client_transaction_id),
        "client_id": str(body.client_id),
        "collection_date": body.collection_date.isoformat(),
        "recorded_at": body.recorded_at.isoformat(),
        "device_id": body.device_id,
        "device_sequence": body.device_sequence,
        "legs": [
            {
                "route_entry_id": str(leg.route_entry_id),
                "loan_id": str(leg.loan_id),
                "route_revision": leg.route_revision.strip(),
                "amount": format(leg.amount, "f"),
            }
            for leg in body.legs
        ],
    }


def _hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_regular_plus_7x7(connection, body: CombinedPaymentRequest) -> None:
    loan_ids = [leg.loan_id for leg in body.legs]
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            select
                loan.id,
                loan.client_id,
                loan.status,
                loan_type.calculation_mode
            from lending.loans loan
            join lending.loan_types loan_type on loan_type.id = loan.loan_type_id
            where loan.id = any(%s)
            order by loan.id
            for update of loan
            """,
            (loan_ids,),
        )
        rows = cursor.fetchall()
    if len(rows) != 2:
        raise CollectionRejected(
            "Both loans must still exist before a combined payment can be saved.",
            code="combined_loan_not_found",
        )
    if any(row["client_id"] != body.client_id for row in rows):
        raise CollectionRejected(
            "Combined payment loans must belong to the same client.",
            code="combined_client_mismatch",
        )

    modes = sorted(str(row["calculation_mode"] or "").strip().lower() for row in rows)
    if modes != ["fixed_daily", "seven_by_seven"]:
        raise CollectionRejected(
            "One-tap combined Pay is limited to exactly one Regular loan and one 7x7 loan.",
            code="combined_regular_7x7_required",
        )


def _replay_or_conflict(
    row: dict[str, Any],
    *,
    actor: ActorContext,
    request_hash: str,
) -> dict[str, Any]:
    same_owner = (
        str(row["collector_account_id"]) == actor.account_id
        and str(row["registered_device_id"]) == actor.storage_device_id
    )
    if not same_owner or str(row["canonical_request_hash"]) != request_hash:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "combined_idempotency_mismatch",
                "message": (
                    "This combined collection number was already used for different data. "
                    "Refresh the route and review the client."
                ),
            },
        )
    payload = dict(row["result_payload"] or {})
    payload["status"] = "duplicate"
    payload["duplicate"] = True
    payload["message"] = "Already recorded. No duplicate Regular or 7x7 payment was created."
    return payload


def create_combined_collection_router() -> APIRouter:
    router = APIRouter(tags=["collector-collections"])

    @router.post("/api/v1/collector/collections/combined")
    @router.post(
        "/api/mobile/v1/collector/collections/combined",
        include_in_schema=False,
    )
    def submit_combined_payment(
        body: CombinedPaymentRequest,
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
        client_transaction_id: UUID = Header(alias="X-Client-Transaction-Id"),
        contract_version: str = Header(alias="X-Gilbic-Contract-Version"),
        actor: ActorContext = Depends(collection_actor_dependency),
    ) -> dict[str, object]:
        if idempotency_key != client_transaction_id or idempotency_key != body.client_transaction_id:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "idempotency_key_mismatch",
                    "message": "Combined collection transaction identifiers must match.",
                },
            )
        if contract_version != CONTRACT_VERSION:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "unsupported_contract_version",
                    "message": "The Gilbic collection contract version is not supported.",
                },
            )
        if body.device_id.strip() != actor.device_id:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "device_not_registered",
                    "message": "The registered device does not match this combined collection.",
                },
            )

        canonical = _canonical_payload(body)
        request_hash = _hash(canonical)
        bridge = ConcurrentReceiptSafeCollectionPostingBridge()
        try:
            with connect_database() as connection:
                with connection.transaction():
                    with connection.cursor(row_factory=dict_row) as cursor:
                        cursor.execute(
                            "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                            (f"gilbic-combined:{idempotency_key}",),
                        )
                        cursor.execute(
                            """
                            select collector_account_id, registered_device_id,
                                   canonical_request_hash, result_payload
                            from mobile.gilbic_combined_collection_idempotency
                            where idempotency_key = %s
                            for update
                            """,
                            (idempotency_key,),
                        )
                        existing = cursor.fetchone()
                        if existing is not None:
                            return {
                                "success": True,
                                "data": _replay_or_conflict(
                                    existing,
                                    actor=actor,
                                    request_hash=request_hash,
                                ),
                            }

                    _validate_regular_plus_7x7(connection, body)
                    posted_legs: list[dict[str, object]] = []
                    total = Decimal("0.00")
                    for index, leg in enumerate(body.legs):
                        child_key = uuid5(idempotency_key, f"{index}:{leg.loan_id}")
                        amount = leg.amount.quantize(Decimal("0.01"))
                        command = CollectionCommand(
                            idempotency_key=child_key,
                            route_entry_id=str(leg.route_entry_id),
                            client_id=str(body.client_id),
                            loan_id=str(leg.loan_id),
                            collection_date=body.collection_date,
                            entry_type=CollectionEntryType.PAYMENT,
                            amount=amount,
                            covered_dates=(body.collection_date,),
                            recorded_at=body.recorded_at,
                            device_id=body.device_id,
                            device_sequence=body.device_sequence + index,
                            note="Atomic Regular + 7x7 one-tap Pay",
                            route_revision=leg.route_revision.strip(),
                        )
                        posted = bridge.post_collection(connection, actor, command)
                        total += amount
                        posted_legs.append(
                            {
                                "loan_id": str(leg.loan_id),
                                "transaction_id": posted.server_transaction_id,
                                "receipt_number": posted.receipt_number,
                                "official_balance": format(posted.official_balance, "f"),
                                "route_revision": posted.route_revision,
                            }
                        )

                    result_payload: dict[str, object] = {
                        "status": "accepted",
                        "duplicate": False,
                        "client_transaction_id": str(idempotency_key),
                        "client_id": str(body.client_id),
                        "total_amount": format(total.quantize(Decimal("0.01")), "f"),
                        "legs": posted_legs,
                        "message": "Regular + 7x7 payments saved atomically.",
                    }
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            insert into mobile.gilbic_combined_collection_idempotency (
                                idempotency_key,
                                collector_account_id,
                                registered_device_id,
                                canonical_request_hash,
                                request_payload,
                                result_payload
                            ) values (%s, %s, %s, %s, %s, %s)
                            """,
                            (
                                idempotency_key,
                                UUID(actor.account_id),
                                UUID(actor.storage_device_id),
                                request_hash,
                                Jsonb({k: v for k, v in canonical.items() if k != "device_id"}),
                                Jsonb(result_payload),
                            ),
                        )
                    return {"success": True, "data": result_payload}
        except CollectionConflict as error:
            raise HTTPException(
                status_code=409,
                detail={"code": error.code, "message": error.message},
            ) from error
        except CollectionRejected as error:
            raise HTTPException(
                status_code=422,
                detail={"code": error.code, "message": error.message},
            ) from error

    return router
