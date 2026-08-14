from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .request_auth import authenticated_device_context
from .v1_tax_evidence_repository import (
    PostgresV1TaxEvidenceRepository,
    V1DstReadiness,
    V1PercentageTaxReadiness,
    V1TaxEvidenceBlocked,
    V1TaxEvidenceError,
    V1TaxRuleEvidence,
)


RULE_PERMISSION = "accounting.tax.rule_evidence.record"
DST_PERMISSION = "accounting.tax.dst_evidence.record"
PERCENTAGE_PERMISSION = "accounting.tax.percentage_evidence.record"


class StrictV1TaxEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecordV1TaxRuleRequest(StrictV1TaxEvidenceRequest):
    confirm: bool = False
    idempotency_key: UUID
    tax_type: Literal["documentary_stamp_tax", "percentage_tax_lending"]
    rule_key: str = Field(min_length=1, max_length=120)
    effective_from: date
    effective_to: date | None = None
    treatment: Literal["taxable", "exempt"]
    rate: Decimal = Field(ge=0, le=1, max_digits=14, decimal_places=10)
    maturity_max_days: int | None = Field(default=None, gt=0)
    legal_source: str = Field(min_length=1, max_length=240)
    legal_reference: str = Field(min_length=1, max_length=500)
    retained_source_reference: str = Field(min_length=1, max_length=500)
    evidence_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    management_rationale: str = Field(min_length=20, max_length=4000)
    supersedes_rule_id: UUID | None = None

    @field_validator(
        "rule_key",
        "legal_source",
        "legal_reference",
        "retained_source_reference",
        "management_rationale",
    )
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Required V1 tax rule evidence text cannot be blank.")
        return normalized

    @field_validator("rate")
    @classmethod
    def exact_rate_precision(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.0000000001")):
            raise ValueError("Tax rule rate supports at most 10 decimal places.")
        return value

    @model_validator(mode="after")
    def validate_treatment_and_dates(self) -> "RecordV1TaxRuleRequest":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("Tax rule effective_to cannot precede effective_from.")
        if self.treatment == "taxable" and self.rate <= 0:
            raise ValueError("A taxable V1 tax rule requires a positive exact rate.")
        if self.treatment == "exempt" and self.rate != 0:
            raise ValueError("An exempt V1 tax rule must use rate 0.")
        return self


class RecordV1DstEvidenceRequest(StrictV1TaxEvidenceRequest):
    confirm: bool = False
    idempotency_key: UUID
    loan_id: UUID
    disbursement_event_id: UUID
    rule_evidence_id: UUID
    expected_issue_price: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    expected_term_days: int = Field(gt=0)
    expected_tax_due: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    instrument_reference: str = Field(min_length=1, max_length=500)
    instrument_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    calculation_reference: str = Field(min_length=1, max_length=500)
    calculation_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    management_rationale: str = Field(min_length=20, max_length=4000)
    supersedes_evidence_id: UUID | None = None

    @field_validator("expected_issue_price", "expected_tax_due")
    @classmethod
    def exact_currency_cents(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("DST amounts must use exact currency-cent precision.")
        return value

    @field_validator("instrument_reference", "calculation_reference", "management_rationale")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Required DST evidence text cannot be blank.")
        return normalized


class RecordV1PercentageTaxEvidenceRequest(StrictV1TaxEvidenceRequest):
    confirm: bool = False
    idempotency_key: UUID
    transaction_id: UUID
    rule_evidence_id: UUID
    expected_source_cash_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    taxable_lending_receipt_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    principal_receipt_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    expected_tax_due: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    allocation_reference: str = Field(min_length=1, max_length=500)
    allocation_digest: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    management_rationale: str = Field(min_length=20, max_length=4000)
    supersedes_evidence_id: UUID | None = None

    @field_validator(
        "expected_source_cash_amount",
        "taxable_lending_receipt_amount",
        "principal_receipt_amount",
        "expected_tax_due",
    )
    @classmethod
    def exact_currency_cents(cls, value: Decimal) -> Decimal:
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("Percentage-tax amounts must use exact currency-cent precision.")
        return value

    @field_validator("allocation_reference", "management_rationale")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Required percentage-tax evidence text cannot be blank.")
        return normalized

    @model_validator(mode="after")
    def exact_cash_reconciliation(self) -> "RecordV1PercentageTaxEvidenceRequest":
        if self.expected_source_cash_amount != (
            self.taxable_lending_receipt_amount + self.principal_receipt_amount
        ):
            raise ValueError(
                "Taxable lending receipt plus principal must exactly reconcile to protected source cash."
            )
        return self


def v1_tax_repository_dependency() -> PostgresV1TaxEvidenceRepository:
    return PostgresV1TaxEvidenceRepository()


def _rule_payload(item: V1TaxRuleEvidence) -> dict[str, object]:
    return {
        "id": str(item.id),
        "tax_type": item.tax_type,
        "rule_key": item.rule_key,
        "rule_version": item.rule_version,
        "effective_from": item.effective_from.isoformat(),
        "effective_to": item.effective_to.isoformat() if item.effective_to else None,
        "treatment": item.treatment,
        "rate": format(item.rate, "f"),
        "maturity_max_days": item.maturity_max_days,
        "legal_source": item.legal_source,
        "legal_reference": item.legal_reference,
        "retained_source_reference": item.retained_source_reference,
        "evidence_digest": item.evidence_digest,
        "management_rationale": item.management_rationale,
        "supersedes_rule_id": str(item.supersedes_rule_id) if item.supersedes_rule_id else None,
        "recorded_by_user_id": str(item.recorded_by_user_id),
        "recorded_at": item.recorded_at.isoformat(),
    }


def _dst_payload(item: V1DstReadiness) -> dict[str, object]:
    return {
        "loan_id": str(item.loan_id),
        "client_id": str(item.client_id),
        "disbursement_event_id": str(item.disbursement_event_id),
        "issue_date": item.issue_date.isoformat(),
        "protected_issue_price": format(item.protected_issue_price, ".2f"),
        "protected_term_days": item.protected_term_days,
        "evidence_id": str(item.evidence_id) if item.evidence_id else None,
        "evidence_version": item.evidence_version,
        "rule_evidence_id": str(item.rule_evidence_id) if item.rule_evidence_id else None,
        "tax_due": format(item.tax_due, ".2f") if item.tax_due is not None else None,
        "calculation_digest": item.calculation_digest,
        "tax_status": item.tax_status,
        "tax_blocker": item.tax_blocker,
        "tax_posting_enabled": item.tax_posting_enabled,
        "automatic_source_posting": item.automatic_source_posting,
    }


def _percentage_payload(item: V1PercentageTaxReadiness) -> dict[str, object]:
    return {
        "transaction_id": str(item.transaction_id),
        "loan_id": str(item.loan_id),
        "client_id": str(item.client_id),
        "collection_date": item.collection_date.isoformat(),
        "entry_type": item.entry_type,
        "source_cash_amount": format(item.source_cash_amount, ".2f"),
        "is_voided": item.is_voided,
        "evidence_id": str(item.evidence_id) if item.evidence_id else None,
        "evidence_version": item.evidence_version,
        "rule_evidence_id": str(item.rule_evidence_id) if item.rule_evidence_id else None,
        "taxable_lending_receipt_amount": (
            format(item.taxable_lending_receipt_amount, ".2f")
            if item.taxable_lending_receipt_amount is not None
            else None
        ),
        "principal_receipt_amount": (
            format(item.principal_receipt_amount, ".2f")
            if item.principal_receipt_amount is not None
            else None
        ),
        "tax_due": format(item.tax_due, ".2f") if item.tax_due is not None else None,
        "allocation_digest": item.allocation_digest,
        "tax_status": item.tax_status,
        "tax_blocker": item.tax_blocker,
        "tax_posting_enabled": item.tax_posting_enabled,
        "automatic_source_posting": item.automatic_source_posting,
    }


def _summary_payload(summary: dict[str, object]) -> dict[str, object]:
    return {
        key: format(value, "f") if isinstance(value, Decimal) else value
        for key, value in summary.items()
    }


def _exception(error: V1TaxEvidenceError) -> HTTPException:
    return HTTPException(
        status_code=409 if isinstance(error, V1TaxEvidenceBlocked) else 500,
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
                "message": "Management access is required for protected V1 tax evidence.",
            },
        )
    return actor


def _require_permission(actor, permission: str) -> None:
    if permission not in actor.permissions:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "v1_tax_permission_required",
                "message": f"Protected V1 tax evidence permission {permission} is required.",
            },
        )


def _require_confirmation(confirm: bool, action: str) -> None:
    if not confirm:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "v1_tax_evidence_confirmation_required",
                "message": f"Explicit Management confirmation is required before {action}.",
            },
        )


def create_v1_tax_evidence_router() -> APIRouter:
    router = APIRouter(tags=["management financial accounting"])

    @router.get("/api/v1/management/financial-accounting/tax")
    def list_v1_tax_readiness(
        readiness: Literal["all", "ready", "blocked"] = Query(default="all"),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxEvidenceRepository = Depends(v1_tax_repository_dependency),
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
                "rules": [_rule_payload(item) for item in tax.list_rules(limit=limit, offset=offset)],
                "dst": [
                    _dst_payload(item)
                    for item in tax.list_dst_readiness(
                        status=readiness, limit=limit, offset=offset
                    )
                ],
                "percentage_tax": [
                    _percentage_payload(item)
                    for item in tax.list_percentage_readiness(
                        status=readiness, limit=limit, offset=offset
                    )
                ],
                "permissions": {
                    "rule_evidence_record": RULE_PERMISSION in actor.permissions,
                    "dst_evidence_record": DST_PERMISSION in actor.permissions,
                    "percentage_evidence_record": PERCENTAGE_PERMISSION in actor.permissions,
                },
                "notice": (
                    "A6.2 tax readiness is evidence-backed and Management-only. "
                    "PFRS/EIR interest is not substituted for the tax base; tax posting remains disabled in this slice."
                ),
            },
        }

    @router.post(
        "/api/v1/management/financial-accounting/tax/rules",
        status_code=status.HTTP_201_CREATED,
    )
    def record_v1_tax_rule(
        body: RecordV1TaxRuleRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxEvidenceRepository = Depends(v1_tax_repository_dependency),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, RULE_PERMISSION)
        _require_confirmation(body.confirm, "recording approved tax rule evidence")
        try:
            evidence_id = tax.record_rule(
                actor_user_id=actor.user_id,
                idempotency_key=body.idempotency_key,
                tax_type=body.tax_type,
                rule_key=body.rule_key,
                effective_from=body.effective_from,
                effective_to=body.effective_to,
                treatment=body.treatment,
                rate=body.rate,
                maturity_max_days=body.maturity_max_days,
                legal_source=body.legal_source,
                legal_reference=body.legal_reference,
                retained_source_reference=body.retained_source_reference,
                evidence_digest=body.evidence_digest.lower(),
                management_rationale=body.management_rationale,
                supersedes_rule_id=body.supersedes_rule_id,
            )
        except V1TaxEvidenceError as error:
            raise _exception(error) from error
        return {
            "success": True,
            "data": {
                "rule_evidence_id": str(evidence_id),
                "tax_posting_enabled": False,
                "automatic_source_posting": False,
            },
        }

    @router.post(
        "/api/v1/management/financial-accounting/tax/dst-evidence",
        status_code=status.HTTP_201_CREATED,
    )
    def record_v1_dst_evidence(
        body: RecordV1DstEvidenceRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxEvidenceRepository = Depends(v1_tax_repository_dependency),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, DST_PERMISSION)
        _require_confirmation(body.confirm, "recording exact DST evidence")
        try:
            evidence_id = tax.record_dst(
                actor_user_id=actor.user_id,
                idempotency_key=body.idempotency_key,
                loan_id=body.loan_id,
                disbursement_event_id=body.disbursement_event_id,
                rule_evidence_id=body.rule_evidence_id,
                expected_issue_price=body.expected_issue_price,
                expected_term_days=body.expected_term_days,
                expected_tax_due=body.expected_tax_due,
                instrument_reference=body.instrument_reference,
                instrument_digest=body.instrument_digest.lower(),
                calculation_reference=body.calculation_reference,
                calculation_digest=body.calculation_digest.lower(),
                management_rationale=body.management_rationale,
                supersedes_evidence_id=body.supersedes_evidence_id,
            )
        except V1TaxEvidenceError as error:
            raise _exception(error) from error
        return {
            "success": True,
            "data": {
                "dst_evidence_id": str(evidence_id),
                "tax_posting_enabled": False,
                "automatic_source_posting": False,
            },
        }

    @router.post(
        "/api/v1/management/financial-accounting/tax/percentage-evidence",
        status_code=status.HTTP_201_CREATED,
    )
    def record_v1_percentage_tax_evidence(
        body: RecordV1PercentageTaxEvidenceRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        tax: PostgresV1TaxEvidenceRepository = Depends(v1_tax_repository_dependency),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        _require_permission(actor, PERCENTAGE_PERMISSION)
        _require_confirmation(body.confirm, "recording exact percentage-tax allocation evidence")
        try:
            evidence_id = tax.record_percentage(
                actor_user_id=actor.user_id,
                idempotency_key=body.idempotency_key,
                transaction_id=body.transaction_id,
                rule_evidence_id=body.rule_evidence_id,
                expected_source_cash_amount=body.expected_source_cash_amount,
                taxable_lending_receipt_amount=body.taxable_lending_receipt_amount,
                principal_receipt_amount=body.principal_receipt_amount,
                expected_tax_due=body.expected_tax_due,
                allocation_reference=body.allocation_reference,
                allocation_digest=body.allocation_digest.lower(),
                management_rationale=body.management_rationale,
                supersedes_evidence_id=body.supersedes_evidence_id,
            )
        except V1TaxEvidenceError as error:
            raise _exception(error) from error
        return {
            "success": True,
            "data": {
                "percentage_tax_evidence_id": str(evidence_id),
                "tax_posting_enabled": False,
                "automatic_source_posting": False,
            },
        }

    return router
