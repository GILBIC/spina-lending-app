from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .contract_schedule_engine import (
    ContractInstallment,
    ContractScheduleError,
    PaymentFrequency,
    generate_contract_installments,
)
from .contract_schedule_registration_repository import (
    ContractScheduleLoanContext,
    ContractScheduleRegistrationConflict,
    ContractScheduleRegistrationError,
    ContractScheduleRegistrationNotFound,
    PostgresContractScheduleRegistrationRepository,
    VerifiedContractScheduleRegistration,
)
from .contract_schedule_registration_service import VerifiedScheduleInstallment
from .request_auth import authenticated_device_context
from .seven_by_seven_signed_schedule import (
    SevenBySevenSignedScheduleError,
    generate_signed_seven_by_seven_schedule,
)


class StrictContractScheduleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CustomContractInstallmentRequest(StrictContractScheduleRequest):
    due_date: date
    amount: Decimal = Field(gt=0)


class ContractScheduleTermsRequest(StrictContractScheduleRequest):
    loan_id: UUID
    payment_frequency: Literal[
        "daily",
        "weekly",
        "semi_monthly",
        "monthly",
        "balloon",
        "custom",
    ]
    contract_reference: str = Field(min_length=1, max_length=200)
    contract_signed_date: date
    effective_from: date
    grace_days: int = Field(default=0, ge=0, le=3650)
    contractual_total: Decimal | None = Field(default=None, gt=0)
    first_due_date: date | None = None
    installment_count: int | None = Field(default=None, ge=1, le=5000)
    regular_installment_amount: Decimal | None = Field(default=None, gt=0)
    agreed_daily_payment: Decimal | None = Field(default=None, gt=0)
    semi_monthly_days: tuple[int, int] = (15, 30)
    custom_installments: list[CustomContractInstallmentRequest] = Field(
        default_factory=list,
        max_length=5000,
    )

    @field_validator("contract_reference")
    @classmethod
    def normalize_contract_reference(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Contract reference cannot be blank.")
        return normalized

    @field_validator("semi_monthly_days")
    @classmethod
    def validate_semi_monthly_days(cls, value: tuple[int, int]) -> tuple[int, int]:
        if len(set(value)) != 2 or any(day < 1 or day > 31 for day in value):
            raise ValueError(
                "Semi-monthly terms require two distinct contractual day numbers from 1 to 31."
            )
        return value


class RegisterVerifiedContractScheduleRequest(ContractScheduleTermsRequest):
    evidence_basis: Literal[
        "signed_contract",
        "signed_renewal_contract",
        "signed_restructure_contract",
    ] = "signed_contract"
    evidence_reference: str = Field(min_length=1, max_length=500)
    verification_note: str = Field(min_length=1, max_length=1000)
    supersede_active: bool = False
    confirm_registration: bool = False

    @field_validator("evidence_reference", "verification_note")
    @classmethod
    def normalize_verification_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Verification evidence text cannot be blank.")
        return normalized


def contract_schedule_registration_repository_dependency() -> (
    PostgresContractScheduleRegistrationRepository
):
    return PostgresContractScheduleRegistrationRepository()


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _optional_decimal(value: Decimal | None) -> str | None:
    return _decimal(value) if value is not None else None


def _loan_context_payload(context: ContractScheduleLoanContext) -> dict[str, object]:
    return {
        "loan_id": str(context.loan_id),
        "loan_number": context.loan_number,
        "client_code": context.client_code,
        "client_name": context.client_name,
        "loan_type_name": context.loan_type_name,
        "calculation_mode": context.calculation_mode,
        "daily_interest_per_1000": _decimal(context.daily_interest_per_1000),
        "principal": _decimal(context.principal),
        "daily_amount": _decimal(context.daily_amount),
        "date_released": context.date_released.isoformat(),
        "due_date": context.due_date.isoformat(),
        "loan_status": context.loan_status,
        "active_schedule_id": (
            str(context.active_schedule_id) if context.active_schedule_id else None
        ),
        "active_schedule_version": context.active_schedule_version,
        "active_payment_frequency": context.active_payment_frequency,
        "active_contract_reference": context.active_contract_reference,
    }


def _installment_payload(installment: VerifiedScheduleInstallment) -> dict[str, object]:
    principal_component = getattr(installment, "principal_component", None)
    interest_component = getattr(installment, "interest_component", None)
    return {
        "installment_number": installment.installment_number,
        "due_date": installment.due_date.isoformat(),
        "contractual_amount": _decimal(installment.contractual_amount),
        "principal_component": _optional_decimal(principal_component),
        "interest_component": _optional_decimal(interest_component),
    }


def _registration_payload(
    registration: VerifiedContractScheduleRegistration,
) -> dict[str, object]:
    return {
        "schedule_id": str(registration.schedule_id),
        "loan_id": str(registration.loan_id),
        "schedule_version": registration.schedule_version,
        "status": registration.status,
        "payment_frequency": registration.payment_frequency,
        "contract_reference": registration.contract_reference,
        "contract_signed_date": registration.contract_signed_date.isoformat(),
        "effective_from": registration.effective_from.isoformat(),
        "grace_days": registration.grace_days,
        "installment_count": registration.installment_count,
        "contractual_total": _decimal(registration.contractual_total),
        "first_due_date": registration.first_due_date.isoformat(),
        "last_due_date": registration.last_due_date.isoformat(),
        "evidence_basis": registration.evidence_basis,
        "evidence_reference": registration.evidence_reference,
        "verification_note": registration.verification_note,
        "verified_by_user_id": str(registration.verified_by_user_id),
        "verified_at": registration.verified_at.isoformat(),
        "dpd_data_status": registration.dpd_data_status,
        "days_past_due": registration.days_past_due,
        "automatic_default_label_written": (
            registration.automatic_default_label_written
        ),
        "ecl_included": registration.ecl_included,
        "ecl_amount": _optional_decimal(registration.ecl_amount),
        "ready_to_post": registration.ready_to_post,
    }


def _invalid_terms(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={"code": code, "message": message},
    )


def _generate_verified_terms(
    body: ContractScheduleTermsRequest,
    context: ContractScheduleLoanContext,
) -> tuple[VerifiedScheduleInstallment, ...]:
    if context.calculation_mode == "seven_by_seven":
        if body.payment_frequency != "daily":
            raise _invalid_terms(
                "invalid_7x7_payment_frequency",
                "A signed 7x7 schedule must use daily contractual payment rows.",
            )
        if body.first_due_date is None:
            raise _invalid_terms(
                "missing_7x7_first_due_date",
                "The first signed 7x7 payment date is required.",
            )
        if body.agreed_daily_payment is None:
            raise _invalid_terms(
                "missing_7x7_agreed_daily_payment",
                "The borrower/Management-agreed 7x7 daily payment is required.",
            )
        if (
            body.installment_count is not None
            or body.regular_installment_amount is not None
            or body.custom_installments
        ):
            raise _invalid_terms(
                "conflicting_7x7_schedule_terms",
                "7x7 installment count and row amounts are derived from the signed agreed daily payment; do not also supply generic schedule rows.",
            )
        try:
            signed_rows = generate_signed_seven_by_seven_schedule(
                original_principal=context.principal,
                agreed_daily_payment=body.agreed_daily_payment,
                daily_interest_per_1000=context.daily_interest_per_1000,
                first_due_date=body.first_due_date,
            )
        except SevenBySevenSignedScheduleError as error:
            raise _invalid_terms("invalid_7x7_signed_schedule_terms", str(error)) from error

        derived_total = sum(
            (row.contractual_amount for row in signed_rows),
            Decimal("0.00"),
        )
        if body.contractual_total is not None and body.contractual_total != derived_total:
            raise _invalid_terms(
                "7x7_contractual_total_mismatch",
                "The supplied contractual total does not match the signed 7x7 daily-payment schedule derived from the authoritative loan principal and interest rate.",
            )
        installments: tuple[VerifiedScheduleInstallment, ...] = signed_rows
    else:
        if body.agreed_daily_payment is not None:
            raise _invalid_terms(
                "agreed_daily_payment_not_applicable",
                "agreed_daily_payment is only valid for seven_by_seven loans.",
            )
        if body.contractual_total is None:
            raise _invalid_terms(
                "missing_contractual_total",
                "Contractual total is required for this signed schedule.",
            )
        custom_rows = tuple(
            (item.due_date, item.amount) for item in body.custom_installments
        )
        try:
            generic_rows = generate_contract_installments(
                payment_frequency=body.payment_frequency,
                contractual_total=body.contractual_total,
                first_due_date=body.first_due_date,
                installment_count=body.installment_count,
                regular_installment_amount=body.regular_installment_amount,
                semi_monthly_days=body.semi_monthly_days,
                custom_installments=custom_rows,
            )
        except ContractScheduleError as error:
            raise _invalid_terms("invalid_contract_schedule_terms", str(error)) from error
        installments = generic_rows

    if installments[0].due_date < body.effective_from:
        raise _invalid_terms(
            "invalid_contract_schedule_effective_date",
            "The first contractual due date cannot be before the schedule effective date.",
        )
    return installments


def _registration_exception(error: ContractScheduleRegistrationError) -> HTTPException:
    if isinstance(error, ContractScheduleRegistrationNotFound):
        status_code = 404
    elif isinstance(error, ContractScheduleRegistrationConflict):
        status_code = 409
    else:
        status_code = 500
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    )


def create_contract_schedule_registration_router() -> APIRouter:
    router = APIRouter(tags=["management financial accounting"])

    @router.post(
        "/api/v1/management/financial-accounting/contract-schedules/preview"
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/contract-schedules/preview",
        include_in_schema=False,
    )
    def preview_contract_schedule(
        body: ContractScheduleTermsRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        registrations: PostgresContractScheduleRegistrationRepository = Depends(
            contract_schedule_registration_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        if "management" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "management_role_required",
                    "message": "Management access is required for contract schedule preview.",
                },
            )

        try:
            context = registrations.load_loan_context(loan_id=body.loan_id)
        except ContractScheduleRegistrationError as error:
            raise _registration_exception(error) from error
        installments = _generate_verified_terms(body, context)
        contractual_total = sum(
            (item.contractual_amount for item in installments),
            Decimal("0.00"),
        )
        return {
            "success": True,
            "data": {
                "loan": _loan_context_payload(context),
                "preview": {
                    "payment_frequency": body.payment_frequency,
                    "contract_reference": body.contract_reference,
                    "contract_signed_date": body.contract_signed_date.isoformat(),
                    "effective_from": body.effective_from.isoformat(),
                    "grace_days": body.grace_days,
                    "agreed_daily_payment": _optional_decimal(body.agreed_daily_payment),
                    "installment_count": len(installments),
                    "contractual_total": _decimal(contractual_total),
                    "first_due_date": installments[0].due_date.isoformat(),
                    "last_due_date": installments[-1].due_date.isoformat(),
                    "installments": [
                        _installment_payload(item) for item in installments
                    ],
                },
                "active_schedule_exists": context.active_schedule_id is not None,
                "registration_permission": (
                    "lending.contract_schedule.manage" in actor.permissions
                ),
                "notice": (
                    "Preview only. No contract schedule, payment allocation, DPD label, "
                    "ECL amount, loan status, or General Ledger entry was written."
                ),
            },
        }

    @router.post(
        "/api/v1/management/financial-accounting/contract-schedules/register",
        status_code=status.HTTP_201_CREATED,
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/contract-schedules/register",
        status_code=status.HTTP_201_CREATED,
        include_in_schema=False,
    )
    def register_contract_schedule(
        body: RegisterVerifiedContractScheduleRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        registrations: PostgresContractScheduleRegistrationRepository = Depends(
            contract_schedule_registration_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="lending.contract_schedule.manage",
            permission_error="Verified contract schedule management permission is required.",
        )
        if not body.confirm_registration:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "contract_schedule_registration_confirmation_required",
                    "message": (
                        "Confirm that the preview matches the signed contract before registration."
                    ),
                },
            )

        try:
            context = registrations.load_loan_context(loan_id=body.loan_id)
        except ContractScheduleRegistrationError as error:
            raise _registration_exception(error) from error
        installments = _generate_verified_terms(body, context)
        try:
            registration = registrations.register_schedule(
                loan_id=body.loan_id,
                payment_frequency=body.payment_frequency,
                contract_reference=body.contract_reference,
                contract_signed_date=body.contract_signed_date,
                effective_from=body.effective_from,
                grace_days=body.grace_days,
                installments=installments,
                evidence_basis=body.evidence_basis,
                evidence_reference=body.evidence_reference,
                verification_note=body.verification_note,
                verified_by_user_id=actor.user_id,
                confirmed=body.confirm_registration,
                supersede_active=body.supersede_active,
            )
        except ContractScheduleRegistrationError as error:
            raise _registration_exception(error) from error

        return {
            "success": True,
            "data": _registration_payload(registration),
            "notice": (
                "Verified contractual schedule registered with immutable evidence. "
                "Existing payment allocations were not invented or rewritten; Default, "
                "ECL, loan status, and General Ledger posting remain unchanged."
            ),
        }

    return router
