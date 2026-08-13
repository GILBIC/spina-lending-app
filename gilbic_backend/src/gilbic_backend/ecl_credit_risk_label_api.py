from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .ecl_credit_risk_label_repository import (
    EclCreditRiskLabelBlocked,
    EclCreditRiskLabelError,
    EclCreditRiskLabelLoan,
    EclCreditRiskLabelNotFound,
    EclCreditRiskLabelSummary,
    EclQuantitativeInputReadinessLoan,
    EclQuantitativeInputReadinessSummary,
    PostgresEclCreditRiskLabelRepository,
)
from .request_auth import authenticated_device_context


StageLabel = Literal[
    "stage_1_12_month",
    "stage_2_lifetime",
    "stage_3_credit_impaired",
]
WriteOffLabel = Literal[
    "none",
    "supported_no_reasonable_expectation_of_recovery",
]
RecoveryLabel = Literal["none", "cash_recovery_observed", "cured"]
EvidenceBasis = Literal[
    "contractual_dpd",
    "protected_collection_history",
    "verified_source_document",
    "verified_qualitative_credit_event",
    "authoritative_external_evidence",
]


class StrictEclCreditRiskLabelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReviewEclCreditRiskLabelsRequest(StrictEclCreditRiskLabelRequest):
    stage_label: StageLabel
    default_label: bool
    write_off_label: WriteOffLabel = "none"
    recovery_label: RecoveryLabel = "none"
    primary_evidence_basis: EvidenceBasis
    evidence_reference: str = Field(min_length=1, max_length=300)
    review_note: str = Field(min_length=1, max_length=1200)
    sicr_backstop_rebutted: bool = False
    default_backstop_rebutted: bool = False
    rebuttal_evidence_reference: str | None = Field(default=None, max_length=300)
    rebuttal_note: str | None = Field(default=None, max_length=1200)
    write_off_evidence_reference: str | None = Field(default=None, max_length=300)
    write_off_note: str | None = Field(default=None, max_length=1200)
    recovery_transaction_id: UUID | None = None

    @field_validator(
        "evidence_reference",
        "review_note",
        "rebuttal_evidence_reference",
        "rebuttal_note",
        "write_off_evidence_reference",
        "write_off_note",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None

    @model_validator(mode="after")
    def validate_structural_evidence(self):
        if not self.evidence_reference or not self.review_note:
            raise ValueError("Primary evidence reference and review note are required.")
        if self.sicr_backstop_rebutted or self.default_backstop_rebutted:
            if not self.rebuttal_evidence_reference or not self.rebuttal_note:
                raise ValueError("Backstop rebuttal requires separate evidence and rationale.")
        elif self.rebuttal_evidence_reference or self.rebuttal_note:
            raise ValueError("Rebuttal evidence requires an explicit backstop-rebuttal flag.")
        if self.write_off_label == "supported_no_reasonable_expectation_of_recovery":
            if not self.write_off_evidence_reference or not self.write_off_note:
                raise ValueError("Write-off support requires separate evidence and rationale.")
        elif self.write_off_evidence_reference or self.write_off_note:
            raise ValueError("Write-off evidence requires the write-off-support label.")
        if self.recovery_label == "cash_recovery_observed":
            if self.recovery_transaction_id is None:
                raise ValueError("Cash recovery requires the exact protected collection transaction id.")
        elif self.recovery_transaction_id is not None:
            raise ValueError("A recovery transaction id is allowed only for cash recovery observed.")
        return self


def ecl_credit_risk_label_repository_dependency() -> PostgresEclCreditRiskLabelRepository:
    return PostgresEclCreditRiskLabelRepository()


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _optional_decimal(value: Decimal | None) -> str | None:
    return _decimal(value) if value is not None else None


def _summary_payload(summary: EclCreditRiskLabelSummary) -> dict[str, object]:
    return {
        "loan_count": summary.loan_count,
        "dpd_ready_count": summary.dpd_ready_count,
        "dpd_data_required_count": summary.dpd_data_required_count,
        "label_review_required_count": summary.label_review_required_count,
        "label_refresh_required_count": summary.label_refresh_required_count,
        "current_label_ready_count": summary.current_label_ready_count,
        "stage_1_count": summary.stage_1_count,
        "stage_2_count": summary.stage_2_count,
        "stage_3_count": summary.stage_3_count,
        "default_count": summary.default_count,
        "write_off_supported_count": summary.write_off_supported_count,
        "cash_recovery_observed_count": summary.cash_recovery_observed_count,
        "cured_count": summary.cured_count,
        "quantitative_ecl_ready": summary.quantitative_ecl_ready,
        "ecl_amount": _optional_decimal(summary.ecl_amount),
        "ecl_calculation_enabled": summary.ecl_calculation_enabled,
        "account_1190_posting_enabled": summary.account_1190_posting_enabled,
        "automatic_source_posting": summary.automatic_source_posting,
    }


def _loan_payload(loan: EclCreditRiskLabelLoan) -> dict[str, object]:
    return {
        "loan_id": str(loan.loan_id),
        "loan_number": loan.loan_number,
        "loan_status": loan.loan_status,
        "schedule_id": str(loan.schedule_id) if loan.schedule_id else None,
        "schedule_version": loan.schedule_version,
        "contract_reference": loan.contract_reference,
        "dpd_data_status": loan.dpd_data_status,
        "days_past_due": loan.days_past_due,
        "due_unpaid_amount": _decimal(loan.due_unpaid_amount),
        "thirty_day_sicr_backstop_reached": loan.thirty_day_sicr_backstop_reached,
        "ninety_day_default_backstop_reached": loan.ninety_day_default_backstop_reached,
        "current_dpd_risk_band": loan.current_dpd_risk_band,
        "review_id": loan.review_id,
        "review_version": loan.review_version,
        "stage_label": loan.stage_label,
        "default_label": loan.default_label,
        "write_off_label": loan.write_off_label,
        "recovery_label": loan.recovery_label,
        "primary_evidence_basis": loan.primary_evidence_basis,
        "evidence_reference": loan.evidence_reference,
        "review_note": loan.review_note,
        "sicr_backstop_rebutted": loan.sicr_backstop_rebutted,
        "default_backstop_rebutted": loan.default_backstop_rebutted,
        "rebuttal_evidence_reference": loan.rebuttal_evidence_reference,
        "rebuttal_note": loan.rebuttal_note,
        "write_off_evidence_reference": loan.write_off_evidence_reference,
        "write_off_note": loan.write_off_note,
        "recovery_transaction_id": (
            str(loan.recovery_transaction_id) if loan.recovery_transaction_id else None
        ),
        "reviewer_name": loan.reviewer_name,
        "reviewed_at": loan.reviewed_at.isoformat() if loan.reviewed_at else None,
        "current_label_ready": loan.current_label_ready,
        "label_review_status": loan.label_review_status,
        "quantitative_ecl_ready": loan.quantitative_ecl_ready,
        "ecl_calculation_enabled": loan.ecl_calculation_enabled,
        "account_1190_posting_enabled": loan.account_1190_posting_enabled,
        "automatic_source_posting": loan.automatic_source_posting,
    }


def _input_readiness_summary_payload(
    summary: EclQuantitativeInputReadinessSummary,
) -> dict[str, object]:
    return {
        "loan_count": summary.loan_count,
        "quantitative_input_ready_count": summary.quantitative_input_ready_count,
        "contractual_schedule_dpd_blocked_count": summary.contractual_schedule_dpd_blocked_count,
        "credit_risk_label_blocked_count": summary.credit_risk_label_blocked_count,
        "original_eir_initial_carrying_blocked_count": summary.original_eir_initial_carrying_blocked_count,
        "protected_history_blocked_count": summary.protected_history_blocked_count,
        "current_carrying_blocked_count": summary.current_carrying_blocked_count,
        "outcome_evidence_blocked_count": summary.outcome_evidence_blocked_count,
        "forward_looking_evidence_blocked_count": summary.forward_looking_evidence_blocked_count,
        "quantitative_ecl_ready": summary.quantitative_ecl_ready,
        "ecl_amount": _optional_decimal(summary.ecl_amount),
        "ecl_calculation_enabled": summary.ecl_calculation_enabled,
        "account_1190_posting_enabled": summary.account_1190_posting_enabled,
        "automatic_source_posting": summary.automatic_source_posting,
    }


def _input_readiness_loan_payload(
    loan: EclQuantitativeInputReadinessLoan,
) -> dict[str, object]:
    return {
        "loan_id": str(loan.loan_id),
        "loan_number": loan.loan_number,
        "loan_status": loan.loan_status,
        "loan_type_code": loan.loan_type_code,
        "loan_type_name": loan.loan_type_name,
        "calculation_mode": loan.calculation_mode,
        "schedule_id": str(loan.schedule_id) if loan.schedule_id else None,
        "schedule_version": loan.schedule_version,
        "contract_reference": loan.contract_reference,
        "dpd_data_status": loan.dpd_data_status,
        "days_past_due": loan.days_past_due,
        "current_dpd_risk_band": loan.current_dpd_risk_band,
        "review_id": loan.review_id,
        "review_version": loan.review_version,
        "stage_label": loan.stage_label,
        "default_label": loan.default_label,
        "write_off_label": loan.write_off_label,
        "recovery_label": loan.recovery_label,
        "label_review_status": loan.label_review_status,
        "contractual_schedule_dpd_ready": loan.contractual_schedule_dpd_ready,
        "current_credit_risk_label_ready": loan.current_credit_risk_label_ready,
        "original_eir_initial_carrying_ready": loan.original_eir_initial_carrying_ready,
        "protected_collection_posting_reversal_history_ready": loan.protected_collection_posting_reversal_history_ready,
        "authoritative_current_carrying_ready": loan.authoritative_current_carrying_ready,
        "required_loss_recovery_writeoff_outcome_evidence_ready": loan.required_loss_recovery_writeoff_outcome_evidence_ready,
        "approved_forward_looking_evidence_ready": loan.approved_forward_looking_evidence_ready,
        "blocker_codes": list(loan.blocker_codes),
        "blockers": list(loan.blockers),
        "quantitative_input_ready": loan.quantitative_input_ready,
        "ecl_amount": _optional_decimal(loan.ecl_amount),
        "ecl_calculation_enabled": loan.ecl_calculation_enabled,
        "account_1190_posting_enabled": loan.account_1190_posting_enabled,
        "automatic_source_posting": loan.automatic_source_posting,
    }


def _review_exception(error: EclCreditRiskLabelError) -> HTTPException:
    if isinstance(error, EclCreditRiskLabelNotFound):
        status_code = 404
    elif isinstance(error, EclCreditRiskLabelBlocked):
        status_code = 409
    else:
        status_code = 500
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    )


def create_ecl_credit_risk_label_router() -> APIRouter:
    router = APIRouter(tags=["management financial accounting"])

    @router.get("/api/v1/management/financial-accounting/ecl-credit-risk-labels")
    @router.get(
        "/api/mobile/v1/management/financial-accounting/ecl-credit-risk-labels",
        include_in_schema=False,
    )
    def list_ecl_credit_risk_labels(
        review_status: Literal["pending", "stale", "dpd_blocked", "reviewed", "all"] = Query(default="pending"),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        labels: PostgresEclCreditRiskLabelRepository = Depends(
            ecl_credit_risk_label_repository_dependency
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
                    "message": "Management access is required for ECL credit-risk label review.",
                },
            )
        summary, loans = labels.load_queue(
            review_status=review_status,
            limit=limit,
            offset=offset,
        )
        return {
            "success": True,
            "data": {
                "summary": _summary_payload(summary),
                "loans": [_loan_payload(item) for item in loans],
                "filter": review_status,
                "limit": limit,
                "offset": offset,
                "review_permission": "accounting.ecl.credit_risk_label.review" in actor.permissions,
                "notice": (
                    "ECL stage/default/write-off-support/recovery/cure labels require explicit "
                    "evidence-backed Management review. DPD backstops are rebuttable; no ECL "
                    "amount, account 1190 posting, or write-off execution occurs here."
                ),
            },
        }

    @router.get(
        "/api/v1/management/financial-accounting/ecl-quantitative-input-readiness"
    )
    @router.get(
        "/api/mobile/v1/management/financial-accounting/ecl-quantitative-input-readiness",
        include_in_schema=False,
    )
    def list_ecl_quantitative_input_readiness(
        readiness_status: Literal["blocked", "ready", "all"] = Query(default="blocked"),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        labels: PostgresEclCreditRiskLabelRepository = Depends(
            ecl_credit_risk_label_repository_dependency
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
                    "message": "Management access is required for quantitative ECL input-readiness review.",
                },
            )
        summary, loans = labels.load_quantitative_input_readiness(
            readiness_status=readiness_status,
            limit=limit,
            offset=offset,
        )
        return {
            "success": True,
            "data": {
                "summary": _input_readiness_summary_payload(summary),
                "loans": [_input_readiness_loan_payload(item) for item in loans],
                "filter": readiness_status,
                "limit": limit,
                "offset": offset,
                "notice": (
                    "This is a read-only evidence gate. Each blocker names a protected input "
                    "that is missing or stale. Free-text notes do not satisfy blockers. "
                    "Forward-looking evidence remains blocked until A2 governance is installed; "
                    "no ECL amount or account 1190 posting is enabled here."
                ),
            },
        }

    @router.post(
        "/api/v1/management/financial-accounting/ecl-credit-risk-labels/{loan_id}"
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/ecl-credit-risk-labels/{loan_id}",
        include_in_schema=False,
    )
    def review_ecl_credit_risk_labels(
        loan_id: UUID,
        body: ReviewEclCreditRiskLabelsRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        labels: PostgresEclCreditRiskLabelRepository = Depends(
            ecl_credit_risk_label_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.ecl.credit_risk_label.review",
            permission_error="ECL credit-risk label review permission is required.",
        )
        try:
            reviewed = labels.review_labels(
                loan_id=loan_id,
                stage_label=body.stage_label,
                default_label=body.default_label,
                write_off_label=body.write_off_label,
                recovery_label=body.recovery_label,
                primary_evidence_basis=body.primary_evidence_basis,
                evidence_reference=body.evidence_reference,
                review_note=body.review_note,
                sicr_backstop_rebutted=body.sicr_backstop_rebutted,
                default_backstop_rebutted=body.default_backstop_rebutted,
                rebuttal_evidence_reference=body.rebuttal_evidence_reference,
                rebuttal_note=body.rebuttal_note,
                write_off_evidence_reference=body.write_off_evidence_reference,
                write_off_note=body.write_off_note,
                recovery_transaction_id=body.recovery_transaction_id,
                actor_user_id=actor.user_id,
            )
        except EclCreditRiskLabelError as error:
            raise _review_exception(error) from error

        return {
            "success": True,
            "data": _loan_payload(reviewed),
            "notice": (
                "Protected ECL credit-risk labels recorded with immutable review history. "
                "No quantitative ECL, account 1190 posting, write-off journal, or automatic "
                "source posting was created."
            ),
        }

    return router