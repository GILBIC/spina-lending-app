"""Draft loan-request facts, separate from reusable CIF and approved terms."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)


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


# Reuse value validation without inheriting any request or approval fields.
_RepaymentText = Annotated[
    str | None, BeforeValidator(LoanRequestInformation.normalize_request_text)
]
_RepaymentMoney = Annotated[
    Decimal,
    Field(decimal_places=2, allow_inf_nan=False),
    BeforeValidator(LoanRequestInformation.require_exact_amount_input),
    AfterValidator(LoanRequestInformation.require_exact_cents),
]


class LoanObligationInformation(BaseModel):
    """One declared debt row; missing information is not a zero balance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    creditor: _RepaymentText = None
    outstanding_balance: _RepaymentMoney | None = Field(default=None, ge=0)
    periodic_payment_amount: _RepaymentMoney | None = Field(default=None, ge=0)
    payment_frequency: _RepaymentText = None
    notes: _RepaymentText = None

    def missing_fields(self) -> tuple[str, ...]:
        return tuple(
            name
            for name in (
                "creditor", "outstanding_balance", "periodic_payment_amount",
                "payment_frequency",
            )
            if getattr(self, name) is None
        )


class LoanRepaymentInformation(BaseModel):
    """Declared repayment facts only, not verified ability or loan approval."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    repayment_source: _RepaymentText = None
    source_details: _RepaymentText = None
    monthly_gross_income: _RepaymentMoney | None = Field(default=None, ge=0)
    monthly_net_income: _RepaymentMoney | None = None
    has_existing_obligations: StrictBool | None = None
    obligations: tuple[LoanObligationInformation, ...] = ()

    @model_validator(mode="after")
    def reject_contradictory_declaration(self) -> LoanRepaymentInformation:
        if self.has_existing_obligations is False and self.obligations:
            raise ValueError("No-obligations declaration conflicts with entered debts.")
        return self

    def missing_fields(self) -> tuple[str, ...]:
        """Report this block's missing facts, never full application readiness."""
        missing = [
            name
            for name in (
                "repayment_source", "source_details", "monthly_gross_income",
                "monthly_net_income", "has_existing_obligations",
            )
            if getattr(self, name) is None
        ]
        if self.has_existing_obligations is True and not self.obligations:
            missing.append("obligations")
        for index, row in enumerate(self.obligations):
            missing.extend(
                f"obligations[{index}].{name}" for name in row.missing_fields()
            )
        return tuple(missing)
