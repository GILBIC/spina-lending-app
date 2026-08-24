from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PastDueEventKind(str, Enum):
    UNABLE_TO_PAY = "unable_to_pay"
    PARTIAL_PAYMENT = "partial_payment"


class PastDueReasonCode(str, Enum):
    NO_CASH = "no_cash"
    CLIENT_ABSENT = "client_absent"
    BUSINESS_SLOW = "business_slow"
    SICK_HOSPITAL = "sick_hospital"
    EMERGENCY = "emergency"
    PROMISED_TO_PAY_LATER = "promised_to_pay_later"
    OTHER = "other"


class PaymentPromiseStatus(str, Enum):
    PENDING = "pending"
    KEPT = "kept"
    PARTIALLY_KEPT = "partially_kept"
    NOT_KEPT = "not_kept"


class PastDueReasonBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason_code: PastDueReasonCode
    note: str = Field(default="", max_length=500)
    promised_payment_date: date | None = None
    promised_amount: Decimal | None = Field(
        default=None,
        gt=Decimal("0.00"),
        max_digits=18,
        decimal_places=2,
    )

    @model_validator(mode="after")
    def validate_reason_details(self) -> "PastDueReasonBody":
        note = self.note.strip()
        if self.reason_code is PastDueReasonCode.OTHER and not note:
            raise ValueError("Other Past Due reason requires a short explanation.")

        is_promise = self.reason_code is PastDueReasonCode.PROMISED_TO_PAY_LATER
        if is_promise:
            if self.promised_payment_date is None:
                raise ValueError(
                    "Promised to pay later requires a promised payment date."
                )
            if self.promised_amount is None:
                raise ValueError(
                    "Promised to pay later requires a promised amount."
                )
        elif self.promised_payment_date is not None or self.promised_amount is not None:
            raise ValueError(
                "Promise date and amount are only valid for Promised to pay later."
            )
        return self


class PastDueFollowupCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_transaction_id: UUID
    installment_id: int | None = Field(default=None, gt=0)
    obligation_date: date
    past_due_amount: Decimal = Field(
        gt=Decimal("0.00"),
        max_digits=18,
        decimal_places=2,
    )
    event_kind: PastDueEventKind
    reason: PastDueReasonBody


class PastDueReasonCorrectionBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: PastDueReasonBody
    correction_reason: str = Field(min_length=1, max_length=500)


class PaymentPromiseUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    promised_payment_date: date
    promised_amount: Decimal = Field(
        gt=Decimal("0.00"),
        max_digits=18,
        decimal_places=2,
    )
    expected_version: int = Field(gt=0)


class PaymentPromiseView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    promised_payment_date: date
    initial_promised_amount: Decimal
    promised_amount: Decimal
    remaining_promised_amount: Decimal
    status: PaymentPromiseStatus
    version: int


class PastDueFollowupView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    client_id: UUID
    loan_id: UUID
    installment_id: int | None
    obligation_date: date
    original_past_due_amount: Decimal
    remaining_past_due_amount: Decimal
    event_kind: PastDueEventKind
    reason_code: PastDueReasonCode
    reason_note: str
    status: str
    promise: PaymentPromiseView | None = None
