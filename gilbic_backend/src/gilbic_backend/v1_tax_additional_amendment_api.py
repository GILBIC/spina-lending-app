from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .request_auth import authenticated_device_context
from .v1_tax_additional_amendment_repository import (
    PostgresV1TaxAdditionalAmendmentRepository,
    V1TaxAdditionalAmendmentBlocked,
    V1TaxAdditionalAmendmentError,
    V1TaxAdditionalAmendmentItem,
)


AMENDMENT_EVIDENCE_PERMISSION = "accounting.tax.additional_amendment_evidence.record"
AMENDMENT_PREPARE_PERMISSION = "accounting.tax.additional_amendment.prepare"
AMENDMENT_POST_PERMISSION = "accounting.tax.additional_amendment.post"
PAYMENT_EVIDENCE_PERMISSION = "accounting.tax.additional_payment_evidence.record"
SETTLEMENT_PREPARE_PERMISSION = "accounting.tax.additional_settlement.prepare"
SETTLEMENT_POST_PERMISSION = "accounting.tax.additional_settlement.post"
AmendmentBasis = Literal["amended_return", "additional_assessment"]
CashAccountKey = Literal["cash_office", "cash_bank_gcash"]


class StrictV1TaxAdditionalAmendmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecordV1TaxAdditionalAmendmentEvidenceRequest(
    StrictV1TaxAdditionalAmendmentRequest
):
    idempotency_key: UUID
    tax_return_id: UUID
    tax_liability_posting_id: UUID
    replacement_evidence_id: UUID
    amendment_basis: AmendmentBasis
    amendment_date: date
    recognition_date: date
    amendment_reference: str = Field(min_length=1, max_length=240)
    evidence_reference: str = Field(min_length=1, max_length=500)
    evidence_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    evidence_note: str = Field(min_length=20, max_length=4000)

    @field_validator("amendment_reference", "evidence_reference", "evidence_note")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Required additional-tax amendment evidence text cannot be blank.")
        return normalized


class PrepareV1TaxAdditionalLiabilityRequest(StrictV1TaxAdditionalAmendmentRequest):
    confirm: bool = False


class PostV1TaxAdditionalLiabilityRequest(StrictV1TaxAdditionalAmendmentRequest):
    confirm: bool = False
    confirmation_token: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_evidence_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_original_declared_tax_due: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    expected_revised_declared_tax_due: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    expected_original_item_tax_due: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    expected_replacement_item_tax_due: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    expected_additional_tax_due: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    expected_expense_account_code: str = Field(min_length=1, max_length=20)
    expected_tax_payable_account_code: str = Field(min_length=1, max_length=20)
    expected_posting_date: date
    expected_fiscal_period_id: UUID

    @field_validator(
        "expected_original_declared_tax_due",
        "expected_revised_declared_tax_due",
        "expected_original_item_tax_due",
        "expected_replacement_item_tax_due",
        "expected_additional_tax_due",
    )
    @classmethod
    def exact_currency_cents(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("Expected additional-tax amounts must use exact currency-cent precision.")
        return value

    @field_validator("expected_expense_account_code", "expected_tax_payable_account_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Expected additional-tax account code cannot be blank.")
        return normalized


class RecordV1TaxAdditionalPaymentEvidenceRequest(
    StrictV1TaxAdditionalAmendmentRequest
):
    idempotency_key: UUID
    payment_date: date
    payment_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    cash_account_system_key: CashAccountKey
    payment_reference: str = Field(min_length=1, max_length=240)
    evidence_reference: str = Field(min_length=1, max_length=500)
    evidence_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    evidence_note: str = Field(min_length=20, max_length=4000)

    @field_validator("payment_amount")
    @classmethod
    def exact_payment_cents(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("Additional-tax payment amount must use exact currency-cent precision.")
        return value

    @field_validator("payment_reference", "evidence_reference", "evidence_note")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Required additional-tax payment evidence text cannot be blank.")
        return normalized


class PrepareV1TaxAdditionalSettlementRequest(StrictV1TaxAdditionalAmendmentRequest):
    confirm: bool = False


class PostV1TaxAdditionalSettlementRequest(StrictV1TaxAdditionalAmendmentRequest):
    confirm: bool = False
    confirmation_token: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_amendment_evidence_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_additional_liability_confirmation_digest: str = Field(
        pattern=r"^[0-9a-fA-F]{64}$"
    )
    expected_payment_evidence_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_payment_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    expected_tax_payable_account_code: str = Field(min_length=1, max_length=20)
    expected_cash_account_code: str = Field(min_length=1, max_length=20)
    expected_posting_date: date
    expected_fiscal_period_id: UUID

    @field_validator("expected_payment_amount")
    @classmethod
    def exact_payment_cents(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("Expected additional-tax settlement amount must use exact currency-cent precision.")
        return value

    @field_validator("expected_tax_payable_account_code", "expected_cash_account_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Expected additional-tax settlement account code cannot be blank.")
        return normalized


def v1_tax_additional_amendment_repository_dependency() -> PostgresV1TaxAdditionalAmendmentRepository:
    return PostgresV1TaxAdditionalAmendmentRepository()


def _serialize(value):
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return format(value, ".2f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_serialize(item) for item in value]
    return value


def _item_payload(item: V1TaxAdditionalAmendmentItem) -> dict[str, object]:
    return _serialize(asdict(item))


def _summary_payload(summary: dict[str, object]) -> dict[str, object]:
    return _serialize(summary)


def _exception(error: V1TaxAdditionalAmendmentError) -> HTTPException:
    return HTTPException(
        status_code=409 if isinstance(error, V1TaxAdditionalAmendmentBlocked) else 500,
        detail={"code": error.code, "message": str(error)},
    )


def _actor(
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
    if "management" not in actor.roles:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "management_role_required",
                "message": "Management access is required for protected V1 additional-tax amendment accounting.",
            },
        )
    return actor


def _require_permission(actor, permission: str) -> None:
    if permission not in actor.permissions:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "v1_tax_additional_amendment_permission_required",
                "message": f"Protected V1 additional-tax amendment permission {permission} is required.",
            },
        )


def _require_confirmation(confirm: bool, action: str) -> None:
    if not confirm:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "v1_tax_additional_amendment_confirmation_required",
                "message": f"Explicit Management confirmation is required before {action}.",
            },
        )


def create_v1_tax_additional_amendment_router() -> APIRouter:
    router = APIRouter(tags=["management financial accounting"])

    @router.get("/api/v1/management/financial-accounting/tax/additional-amendments")
    def list_v1_tax_additional_amendments(
        amendment_status: Literal[
            "all",
            "ready",
            "liability_prepared",
            "awaiting_payment",
            "payment_ready",
            "settlement_prepared",
            "settled",
            "review",
            "blocked",
        ] = Query(default="all"),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxAdditionalAmendmentRepository = Depends(
            v1_tax_additional_amendment_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        return {
            "success": True,
            "data": {
                "summary": _summary_payload(tax.summary()),
                "items": [
                    _item_payload(item)
                    for item in tax.list_items(
                        status=amendment_status, limit=limit, offset=offset
                    )
                ],
                "permissions": {
                    "amendment_evidence_record": AMENDMENT_EVIDENCE_PERMISSION in actor.permissions,
                    "additional_liability_prepare": AMENDMENT_PREPARE_PERMISSION in actor.permissions,
                    "additional_liability_post": AMENDMENT_POST_PERMISSION in actor.permissions,
                    "additional_payment_evidence_record": PAYMENT_EVIDENCE_PERMISSION in actor.permissions,
                    "additional_settlement_prepare": SETTLEMENT_PREPARE_PERMISSION in actor.permissions,
                    "additional_settlement_post": SETTLEMENT_POST_PERMISSION in actor.permissions,
                },
                "notice": (
                    "This V1 path handles one evidence-backed upward correction for an exact filed return: "
                    "the additional liability is Dr the original dedicated tax expense / Cr 2100 Tax Payables, "
                    "then exact retained payment evidence settles Dr 2100 / Cr approved 1010 or 1030. "
                    "Original return/liability/settlement history remains immutable. Tax Recoverable refund/credit realization, "
                    "closed-period correction treatment and partial tax payments remain separate fail-closed controls; "
                    "automatic source posting remains disabled."
                ),
            },
        }

    @router.post(
        "/api/v1/management/financial-accounting/tax/additional-amendments/evidence",
        status_code=status.HTTP_201_CREATED,
    )
    def record_v1_tax_additional_amendment_evidence(
        body: RecordV1TaxAdditionalAmendmentEvidenceRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxAdditionalAmendmentRepository = Depends(
            v1_tax_additional_amendment_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, AMENDMENT_EVIDENCE_PERMISSION)
        try:
            amendment_id = tax.record_amendment_evidence(
                actor_user_id=actor.user_id,
                idempotency_key=body.idempotency_key,
                tax_return_id=body.tax_return_id,
                tax_liability_posting_id=body.tax_liability_posting_id,
                replacement_evidence_id=body.replacement_evidence_id,
                amendment_basis=body.amendment_basis,
                amendment_date=body.amendment_date,
                recognition_date=body.recognition_date,
                amendment_reference=body.amendment_reference,
                evidence_reference=body.evidence_reference,
                evidence_digest=body.evidence_digest.lower(),
                evidence_note=body.evidence_note,
            )
            item = tax.get_item(amendment_id)
        except V1TaxAdditionalAmendmentError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    @router.post(
        "/api/v1/management/financial-accounting/tax/additional-amendments/{amendment_evidence_id}/prepare-liability"
    )
    def prepare_v1_tax_additional_liability(
        amendment_evidence_id: UUID,
        body: PrepareV1TaxAdditionalLiabilityRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxAdditionalAmendmentRepository = Depends(
            v1_tax_additional_amendment_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, AMENDMENT_PREPARE_PERMISSION)
        _require_confirmation(body.confirm, "preparing a protected additional-tax liability journal")
        try:
            tax.prepare_liability(
                amendment_evidence_id=amendment_evidence_id,
                actor_user_id=actor.user_id,
            )
            item = tax.get_item(amendment_evidence_id)
        except V1TaxAdditionalAmendmentError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    @router.post(
        "/api/v1/management/financial-accounting/tax/additional-amendments/{amendment_evidence_id}/post-liability"
    )
    def post_v1_tax_additional_liability(
        amendment_evidence_id: UUID,
        body: PostV1TaxAdditionalLiabilityRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxAdditionalAmendmentRepository = Depends(
            v1_tax_additional_amendment_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, AMENDMENT_POST_PERMISSION)
        _require_confirmation(body.confirm, "posting a protected additional-tax liability journal")
        try:
            tax.post_liability(
                amendment_evidence_id=amendment_evidence_id,
                actor_user_id=actor.user_id,
                confirmation_token=body.confirmation_token.lower(),
                expected_evidence_digest=body.expected_evidence_digest.lower(),
                expected_original_declared_tax_due=body.expected_original_declared_tax_due,
                expected_revised_declared_tax_due=body.expected_revised_declared_tax_due,
                expected_original_item_tax_due=body.expected_original_item_tax_due,
                expected_replacement_item_tax_due=body.expected_replacement_item_tax_due,
                expected_additional_tax_due=body.expected_additional_tax_due,
                expected_expense_account_code=body.expected_expense_account_code,
                expected_tax_payable_account_code=body.expected_tax_payable_account_code,
                expected_posting_date=body.expected_posting_date,
                expected_fiscal_period_id=body.expected_fiscal_period_id,
            )
            item = tax.get_item(amendment_evidence_id)
        except V1TaxAdditionalAmendmentError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    @router.post(
        "/api/v1/management/financial-accounting/tax/additional-amendments/{amendment_evidence_id}/payment-evidence",
        status_code=status.HTTP_201_CREATED,
    )
    def record_v1_tax_additional_payment_evidence(
        amendment_evidence_id: UUID,
        body: RecordV1TaxAdditionalPaymentEvidenceRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxAdditionalAmendmentRepository = Depends(
            v1_tax_additional_amendment_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, PAYMENT_EVIDENCE_PERMISSION)
        try:
            tax.record_payment_evidence(
                actor_user_id=actor.user_id,
                idempotency_key=body.idempotency_key,
                amendment_evidence_id=amendment_evidence_id,
                payment_date=body.payment_date,
                payment_amount=body.payment_amount,
                cash_account_system_key=body.cash_account_system_key,
                payment_reference=body.payment_reference,
                evidence_reference=body.evidence_reference,
                evidence_digest=body.evidence_digest.lower(),
                evidence_note=body.evidence_note,
            )
            item = tax.get_item(amendment_evidence_id)
        except V1TaxAdditionalAmendmentError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    @router.post(
        "/api/v1/management/financial-accounting/tax/additional-amendments/{amendment_evidence_id}/prepare-settlement"
    )
    def prepare_v1_tax_additional_settlement(
        amendment_evidence_id: UUID,
        body: PrepareV1TaxAdditionalSettlementRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxAdditionalAmendmentRepository = Depends(
            v1_tax_additional_amendment_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, SETTLEMENT_PREPARE_PERMISSION)
        _require_confirmation(body.confirm, "preparing a protected additional-tax settlement journal")
        try:
            item = tax.get_item(amendment_evidence_id)
            if item.additional_payment_evidence_id is None:
                raise V1TaxAdditionalAmendmentBlocked(
                    "Exact additional-tax payment evidence is required before settlement preparation."
                )
            tax.prepare_settlement(
                payment_evidence_id=item.additional_payment_evidence_id,
                actor_user_id=actor.user_id,
            )
            item = tax.get_item(amendment_evidence_id)
        except V1TaxAdditionalAmendmentError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    @router.post(
        "/api/v1/management/financial-accounting/tax/additional-amendments/{amendment_evidence_id}/post-settlement"
    )
    def post_v1_tax_additional_settlement(
        amendment_evidence_id: UUID,
        body: PostV1TaxAdditionalSettlementRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxAdditionalAmendmentRepository = Depends(
            v1_tax_additional_amendment_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, SETTLEMENT_POST_PERMISSION)
        _require_confirmation(body.confirm, "posting a protected additional-tax settlement journal")
        try:
            item = tax.get_item(amendment_evidence_id)
            if item.additional_payment_evidence_id is None:
                raise V1TaxAdditionalAmendmentBlocked(
                    "Exact additional-tax payment evidence is required before settlement posting."
                )
            tax.post_settlement(
                payment_evidence_id=item.additional_payment_evidence_id,
                actor_user_id=actor.user_id,
                confirmation_token=body.confirmation_token.lower(),
                expected_amendment_evidence_digest=body.expected_amendment_evidence_digest.lower(),
                expected_additional_liability_confirmation_digest=(
                    body.expected_additional_liability_confirmation_digest.lower()
                ),
                expected_payment_evidence_digest=body.expected_payment_evidence_digest.lower(),
                expected_payment_amount=body.expected_payment_amount,
                expected_tax_payable_account_code=body.expected_tax_payable_account_code,
                expected_cash_account_code=body.expected_cash_account_code,
                expected_posting_date=body.expected_posting_date,
                expected_fiscal_period_id=body.expected_fiscal_period_id,
            )
            item = tax.get_item(amendment_evidence_id)
        except V1TaxAdditionalAmendmentError as error:
            raise _exception(error) from error
        return {"success": True, "data": {"item": _item_payload(item)}}

    return router
