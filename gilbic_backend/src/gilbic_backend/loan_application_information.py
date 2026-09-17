"""Draft loan-request facts, separate from reusable CIF and approved terms."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


_REQUIRED_REQUEST_FIELDS = (
    "requested_loan_type_id",
    "purpose",
    "requested_amount",
    "requested_payment_arrangement",
    "requested_term",
)


class LoanRequestInformation(BaseModel):
    """Validate supplied request values without approving or persisting a loan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    requested_loan_type_id: UUID | None = None
    purpose: str | None = None
    requested_amount: Decimal | None = Field(
        default=None, gt=0, decimal_places=2, allow_inf_nan=False
    )
    requested_payment_arrangement: str | None = None
    requested_term: str | None = None
    preferred_first_payment_date: date | None = None

    @field_validator(
        "purpose", "requested_payment_arrangement", "requested_term", mode="before"
    )
    @classmethod
    def normalize_request_text(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Requested information must be text.")
        return " ".join(value.split()) or None

    @field_validator("requested_amount", mode="before")
    @classmethod
    def require_exact_amount_input(cls, value: object) -> object:
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (str, int, Decimal))
        ):
            raise ValueError("Requested amount must be decimal text, Decimal or integer.")
        return value

    @field_validator("requested_amount")
    @classmethod
    def require_exact_cents(cls, value: Decimal | None) -> Decimal | None:
        if value is not None:
            # Inspect stored digits; normalization can round under Decimal context.
            _, digits, exponent = value.as_tuple()
            if (
                isinstance(exponent, int)
                and exponent < -2
                and any(digits[exponent + 2 :])
            ):
                raise ValueError("Requested amount must be exact to whole cents.")
        return value

    def missing_fields(self) -> tuple[str, ...]:
        """List missing request facts only, NOT full application readiness."""
        return tuple(
            name for name in _REQUIRED_REQUEST_FIELDS if getattr(self, name) is None
        )
