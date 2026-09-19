"""Exact approval inputs; schedule arithmetic stays in the existing engines."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contract_schedule_engine import (
    PaymentFrequency,
    generate_contract_installments,
    prepare_regular_contract_components,
)
from .seven_by_seven_operational_allocator import (
    fixed_daily_interest_for_original_principal,
)
from .seven_by_seven_signed_schedule import generate_signed_seven_by_seven_schedule

Money = Annotated[
    Decimal, Field(ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False)
]


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("*", mode="before")
    @classmethod
    def reject_inexact_numbers(cls, value):
        if isinstance(value, float):
            raise ValueError("Use exact decimal text, not floating point numbers.")
        return value


class UpfrontDeduction(StrictInput):
    code: str = Field(min_length=1, max_length=80)
    amount: Money
    authority_reference: str = Field(min_length=1, max_length=250)

    @field_validator("code", "authority_reference")
    @classmethod
    def clean(cls, value):
        if not value.strip():
            raise ValueError(
                "An explicit deduction and authority reference are required."
            )
        return value.strip()


class CustomInstallment(StrictInput):
    due_date: date
    amount: Money


class FirstLoanTerms(StrictInput):
    loan_type_id: UUID
    product_code: Literal["regular", "seven_by_seven"]
    principal: Money
    contractual_interest: Money | None = None
    interest_rate_percent: (
        Annotated[Decimal, Field(ge=0, max_digits=9, decimal_places=4)] | None
    ) = None
    daily_interest_per_1000: Money | None = None
    payment_frequency: PaymentFrequency
    schedule_basis_date: date
    first_due_date: date
    installment_count: Annotated[int, Field(strict=True, ge=1, le=3660)] | None = None
    installment_amount: Money
    semi_monthly_days: tuple[int, int] = (15, 30)
    custom_installments: tuple[CustomInstallment, ...] = Field(
        default=(), max_length=3660
    )
    grace_days: Annotated[int, Field(strict=True, ge=0, le=365)] = 0
    account_email: str = Field(min_length=3, max_length=320)
    deductions: tuple[UpfrontDeduction, ...] = Field(default=(), max_length=30)
    pricing_review_reference: str = Field(min_length=1, max_length=250)

    @field_validator("account_email")
    @classmethod
    def email(cls, value):
        value = value.strip().lower()
        if value.count("@") != 1 or any(c.isspace() for c in value):
            raise ValueError("A selected account email is required.")
        local, domain = value.split("@")
        if (
            not local
            or "." not in domain
            or domain.startswith(".")
            or domain.endswith(".")
        ):
            raise ValueError("A selected account email is required.")
        return value

    @field_validator("pricing_review_reference")
    @classmethod
    def review_reference(cls, value):
        if not value.strip():
            raise ValueError("An explicit pricing review reference is required.")
        return value.strip()

    @model_validator(mode="after")
    def reconcile(self):
        if self.principal <= 0 or self.installment_amount <= 0 or self.net_cash <= 0:
            raise ValueError(
                "Principal, installment amount and net cash must be positive."
            )
        if len({item.code.casefold() for item in self.deductions}) != len(
            self.deductions
        ):
            raise ValueError("Each upfront deduction must appear once.")
        if self.first_due_date <= self.schedule_basis_date:
            raise ValueError(
                "The first payment must follow the approved release-date basis."
            )
        if self.product_code == "regular":
            if (
                self.contractual_interest is None
                or self.interest_rate_percent is None
                or self.daily_interest_per_1000 is not None
            ):
                raise ValueError(
                    "Regular approval requires exact total interest and rate."
                )
            expected = (self.principal * self.interest_rate_percent / 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if expected != self.contractual_interest:
                raise ValueError(
                    "Regular interest does not reconcile to the approved rate."
                )
            if self.installment_count is None and self.payment_frequency != "custom":
                raise ValueError("The exact installment count is required.")
        else:
            if (
                self.payment_frequency != "daily"
                or self.daily_interest_per_1000 is None
                or self.contractual_interest is not None
                or self.interest_rate_percent is not None
                or self.custom_installments
            ):
                raise ValueError(
                    "7x7 requires its existing exact daily signed-schedule basis."
                )
            interest = fixed_daily_interest_for_original_principal(
                original_principal=self.principal,
                daily_interest_per_1000=self.daily_interest_per_1000,
            )
            if (
                self.installment_amount <= interest
                or self.principal / (self.installment_amount - interest) > 3660
            ):
                raise ValueError(
                    "7x7 approved payment cannot produce a supported finite schedule."
                )
        return self

    @property
    def total_deductions(self) -> Decimal:
        return sum((item.amount for item in self.deductions), Decimal("0.00"))

    @property
    def net_cash(self) -> Decimal:
        return self.principal - self.total_deductions


def generate_first_loan_schedule(terms: FirstLoanTerms):
    if terms.product_code == "seven_by_seven":
        rows = generate_signed_seven_by_seven_schedule(
            original_principal=terms.principal,
            agreed_daily_payment=terms.installment_amount,
            daily_interest_per_1000=terms.daily_interest_per_1000,
            first_due_date=terms.first_due_date,
        )
        if terms.installment_count is not None and terms.installment_count != len(rows):
            raise ValueError(
                "7x7 count must match the authoritative generated maturity."
            )
        return rows
    rows = generate_contract_installments(
        payment_frequency=terms.payment_frequency,
        contractual_total=terms.principal + terms.contractual_interest,
        first_due_date=terms.first_due_date,
        installment_count=terms.installment_count,
        regular_installment_amount=terms.installment_amount,
        semi_monthly_days=terms.semi_monthly_days,
        custom_installments=tuple(
            (item.due_date, item.amount) for item in terms.custom_installments
        ),
    )
    if rows[0].due_date != terms.first_due_date or any(
        row.due_date <= terms.schedule_basis_date for row in rows
    ):
        raise ValueError(
            "Custom dates must match the approved first-payment and release-date basis."
        )
    return prepare_regular_contract_components(
        installments=rows,
        original_principal=terms.principal,
        contractual_interest=terms.contractual_interest,
    )


def snapshot_digest(snapshot: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()


def schedule_payload(rows) -> list[dict]:
    return [
        {
            "installment_number": r.installment_number,
            "due_date": r.due_date.isoformat(),
            "contractual_amount": str(r.contractual_amount),
            "principal_component": str(r.principal_component),
            "interest_component": str(r.interest_component),
        }
        for r in rows
    ]
