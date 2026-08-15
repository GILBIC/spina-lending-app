from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection
from .gcash_gateway import GcashCheckoutSession


class ClientGcashIntentError(RuntimeError):
    code = "client_gcash_intent_error"


class ClientGcashIntentNotFound(ClientGcashIntentError):
    code = "client_gcash_intent_not_found"


@dataclass(frozen=True, slots=True)
class ClientGcashAllocation:
    loan_id: UUID
    amount: Decimal


@dataclass(frozen=True, slots=True)
class ClientGcashIntentRecord:
    intent_id: UUID
    client_id: UUID
    created_by_user_id: UUID
    provider: str
    provider_mode: str
    provider_reference: str | None
    idempotency_key: str
    status: str
    currency: str
    amount: Decimal
    checkout_url: str | None
    qr_value: str | None
    expires_at: datetime | None
    verified_paid_at: datetime | None
    official_collection_transaction_id: UUID | None
    allocations: tuple[ClientGcashAllocation, ...]


class PostgresClientGcashPaymentIntentRepository:
    def find_by_idempotency(
        self,
        *,
        user_id: UUID,
        idempotency_key: str,
    ) -> ClientGcashIntentRecord | None:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select *
                    from lending.client_gcash_payment_intents
                    where created_by_user_id = %s
                      and idempotency_key = %s
                    limit 1
                    """,
                    (user_id, idempotency_key),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                allocations = self._load_allocations(cursor, row["id"])
        return self._from_row(row, allocations)

    def create(
        self,
        *,
        client_id: UUID,
        user_id: UUID,
        provider: str,
        provider_mode: str,
        idempotency_key: str,
        allocations: tuple[ClientGcashAllocation, ...],
    ) -> ClientGcashIntentRecord:
        total = sum((item.amount for item in allocations), Decimal("0.00"))
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    insert into lending.client_gcash_payment_intents (
                        client_id,
                        created_by_user_id,
                        provider,
                        provider_mode,
                        idempotency_key,
                        status,
                        currency,
                        amount
                    ) values (%s, %s, %s, %s, %s, 'created', 'PHP', %s)
                    returning *
                    """,
                    (
                        client_id,
                        user_id,
                        provider,
                        provider_mode,
                        idempotency_key,
                        total,
                    ),
                )
                row = cursor.fetchone()
                assert row is not None
                for item in allocations:
                    cursor.execute(
                        """
                        insert into lending.client_gcash_payment_intent_allocations (
                            intent_id,
                            loan_id,
                            amount
                        ) values (%s, %s, %s)
                        """,
                        (row["id"], item.loan_id, item.amount),
                    )
        return self._from_row(row, allocations)

    def mark_provider_pending(
        self,
        *,
        intent_id: UUID,
        checkout: GcashCheckoutSession,
    ) -> ClientGcashIntentRecord:
        payload_json = json.dumps(checkout.raw_payload, default=str)
        expires_at = self._parse_datetime(checkout.expires_at)
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    update lending.client_gcash_payment_intents
                    set provider_reference = %s,
                        status = 'provider_pending',
                        checkout_url = %s,
                        qr_value = %s,
                        provider_payload = %s::jsonb,
                        expires_at = %s,
                        updated_at = now()
                    where id = %s
                    returning *
                    """,
                    (
                        checkout.provider_reference,
                        checkout.checkout_url,
                        checkout.qr_value,
                        payload_json,
                        expires_at,
                        intent_id,
                    ),
                )
                row = cursor.fetchone()
                if row is None:
                    raise ClientGcashIntentNotFound("GCash payment intent was not found.")
                allocations = self._load_allocations(cursor, intent_id)
        return self._from_row(row, allocations)

    def mark_failed(self, *, intent_id: UUID, message: str) -> None:
        with open_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update lending.client_gcash_payment_intents
                    set status = 'failed',
                        provider_status_payload = jsonb_build_object('message', %s::text),
                        updated_at = now()
                    where id = %s
                    """,
                    (message, intent_id),
                )

    def get_for_user(
        self,
        *,
        user_id: UUID,
        intent_id: UUID,
    ) -> ClientGcashIntentRecord:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select *
                    from lending.client_gcash_payment_intents
                    where id = %s
                      and created_by_user_id = %s
                    limit 1
                    """,
                    (intent_id, user_id),
                )
                row = cursor.fetchone()
                if row is None:
                    raise ClientGcashIntentNotFound("GCash payment intent was not found.")
                allocations = self._load_allocations(cursor, intent_id)
        return self._from_row(row, allocations)

    @staticmethod
    def _load_allocations(cursor: Any, intent_id: UUID) -> tuple[ClientGcashAllocation, ...]:
        cursor.execute(
            """
            select loan_id, amount
            from lending.client_gcash_payment_intent_allocations
            where intent_id = %s
            order by loan_id
            """,
            (intent_id,),
        )
        return tuple(
            ClientGcashAllocation(
                loan_id=row["loan_id"],
                amount=Decimal(row["amount"]),
            )
            for row in cursor.fetchall()
        )

    @staticmethod
    def _from_row(
        row: dict[str, Any],
        allocations: tuple[ClientGcashAllocation, ...],
    ) -> ClientGcashIntentRecord:
        return ClientGcashIntentRecord(
            intent_id=row["id"],
            client_id=row["client_id"],
            created_by_user_id=row["created_by_user_id"],
            provider=str(row["provider"]),
            provider_mode=str(row["provider_mode"]),
            provider_reference=(
                str(row["provider_reference"]) if row["provider_reference"] else None
            ),
            idempotency_key=str(row["idempotency_key"]),
            status=str(row["status"]),
            currency=str(row["currency"]),
            amount=Decimal(row["amount"]),
            checkout_url=str(row["checkout_url"]) if row["checkout_url"] else None,
            qr_value=str(row["qr_value"]) if row["qr_value"] else None,
            expires_at=row["expires_at"],
            verified_paid_at=row["verified_paid_at"],
            official_collection_transaction_id=row["official_collection_transaction_id"],
            allocations=allocations,
        )

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
