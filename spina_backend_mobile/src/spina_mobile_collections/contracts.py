from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID


class CollectionEntryType(str, Enum):
    PAYMENT = "payment"
    ADVANCE = "advance"
    PASS = "pass"


class PaymentAllocationIntent(str, Enum):
    SCHEDULED = "scheduled"
    EXTRA_AS_ADVANCE = "extra_as_advance"
    EXTRA_AS_PRINCIPAL_REDUCTION = "extra_as_principal_reduction"
    # Legacy ambiguous value kept parseable during the migration. Protected
    # posting must not silently interpret it as Principal Reduction.
    VOLUNTARY_EXTRA = "voluntary_extra"


class PastDueReasonCode(str, Enum):
    NO_CASH = "no_cash"
    CLIENT_ABSENT = "client_absent"
    BUSINESS_SLOW = "business_slow"
    SICK_HOSPITAL = "sick_hospital"
    EMERGENCY = "emergency"
    PROMISED_TO_PAY_LATER = "promised_to_pay_later"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class PastDueFollowupInput:
    reason_code: PastDueReasonCode
    note: str = ""
    promised_payment_date: date | None = None
    promised_amount: Decimal | None = None

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "reason_code": self.reason_code.value,
            "note": self.note.strip(),
            "promised_payment_date": (
                self.promised_payment_date.isoformat()
                if self.promised_payment_date is not None
                else None
            ),
            "promised_amount": _decimal_text(self.promised_amount),
        }


class CollectionStatus(str, Enum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ActorContext:
    account_id: str
    device_id: str
    permissions: frozenset[str]
    registered_device_id: str | None = None

    def can_create_collection(self) -> bool:
        return "collection.create" in self.permissions

    @property
    def storage_device_id(self) -> str:
        """Return the server-side device record ID when available.

        ``device_id`` is the raw installation identifier supplied by the app and
        is used only to bind the request to the authenticated installation.
        PostgreSQL persistence should use ``registered_device_id`` so the raw
        installation identifier is never written to the database.
        """

        return (self.registered_device_id or self.device_id).strip()


@dataclass(frozen=True, slots=True)
class CollectionCommand:
    idempotency_key: UUID
    route_entry_id: str
    client_id: str
    loan_id: str
    collection_date: date
    entry_type: CollectionEntryType
    recorded_at: datetime
    device_id: str
    device_sequence: int
    amount: Decimal | None = None
    advance_from: date | None = None
    advance_until: date | None = None
    covered_dates: tuple[date, ...] = ()
    note: str = ""
    route_revision: str | None = None
    payment_allocation_intent: PaymentAllocationIntent = PaymentAllocationIntent.SCHEDULED
    past_due_followup: PastDueFollowupInput | None = None

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "client_transaction_id": str(self.idempotency_key),
            "route_entry_id": self.route_entry_id,
            "client_id": self.client_id,
            "loan_id": self.loan_id,
            "collection_date": self.collection_date.isoformat(),
            "entry_type": self.entry_type.value,
            "amount": _decimal_text(self.amount),
            "advance_from": self.advance_from.isoformat()
            if self.advance_from
            else None,
            "advance_until": self.advance_until.isoformat()
            if self.advance_until
            else None,
            "covered_dates": [value.isoformat() for value in sorted(self.covered_dates)],
            "recorded_at": _utc_isoformat(self.recorded_at),
            "device_id": self.device_id,
            "device_sequence": self.device_sequence,
            "note": self.note.strip(),
            "route_revision": self.route_revision,
            "payment_allocation_intent": self.payment_allocation_intent.value,
            "past_due_followup": (
                self.past_due_followup.canonical_payload()
                if self.past_due_followup is not None
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class PostedCollection:
    server_transaction_id: str
    receipt_number: str
    official_balance: Decimal
    accepted_at: datetime
    route_revision: str | None = None
    message: str = "Payment saved."

    def response_payload(
        self,
        *,
        idempotency_key: UUID,
        duplicate: bool,
    ) -> dict[str, Any]:
        return {
            "status": (
                CollectionStatus.DUPLICATE.value
                if duplicate
                else CollectionStatus.ACCEPTED.value
            ),
            "duplicate": duplicate,
            "client_transaction_id": str(idempotency_key),
            "transaction_id": self.server_transaction_id,
            "receipt_number": self.receipt_number,
            "official_balance": _money_text(self.official_balance),
            "accepted_at": _utc_isoformat(self.accepted_at),
            "route_revision": self.route_revision,
            "message": (
                "Already recorded. No duplicate payment was created."
                if duplicate
                else self.message
            ),
        }


@dataclass(frozen=True, slots=True)
class CollectionOutcome:
    status: CollectionStatus
    idempotency_key: UUID
    message: str
    code: str | None = None
    posted: PostedCollection | None = None

    def response_payload(self) -> dict[str, Any]:
        if self.posted is not None:
            return self.posted.response_payload(
                idempotency_key=self.idempotency_key,
                duplicate=self.status is CollectionStatus.DUPLICATE,
            )
        return {
            "status": self.status.value,
            "client_transaction_id": str(self.idempotency_key),
            "message": self.message,
            "code": self.code,
        }


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    normalized = value.normalize()
    text = format(normalized, "f")
    return "0" if text in {"-0", ""} else text


def _money_text(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _utc_isoformat(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("datetime values must include a timezone")
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
