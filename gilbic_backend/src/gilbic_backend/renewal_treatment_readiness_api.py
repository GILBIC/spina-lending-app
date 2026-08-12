from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .renewal_treatment_readiness_repository import (
    PostgresRenewalTreatmentReadinessRepository,
    RenewalTreatmentReadinessError,
    RenewalTreatmentReadinessNotFound,
)
from .request_auth import authenticated_device_context


def renewal_treatment_readiness_repository_dependency() -> (
    PostgresRenewalTreatmentReadinessRepository
):
    return PostgresRenewalTreatmentReadinessRepository()


def _money(value):
    return None if value is None else format(value, ".2f")


def _decimal(value):
    return None if value is None else format(value, "f")


def create_renewal_treatment_readiness_router() -> APIRouter:
    router = APIRouter(tags=["management renewal accounting treatment readiness"])

    @router.get(
        "/api/v1/management/accounting/renewals/{renewal_execution_event_id}/treatment-readiness"
    )
    def treatment_readiness(
        renewal_execution_event_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRenewalTreatmentReadinessRepository = Depends(
            renewal_treatment_readiness_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.view",
            permission_error="Financial Accounting view permission is required.",
        )
        if "management" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "management_role_required",
                    "message": "Management access is required for renewal accounting treatment review.",
                },
            )

        try:
            record = repository.load(
                renewal_execution_event_id=renewal_execution_event_id,
            )
        except RenewalTreatmentReadinessNotFound as error:
            raise HTTPException(
                status_code=404,
                detail={"code": error.code, "message": str(error)},
            ) from error
        except RenewalTreatmentReadinessError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": error.code, "message": str(error)},
            ) from error

        source = record.source
        result = record.readiness
        return {
            "success": True,
            "data": {
                "renewal_execution_event_id": str(source.renewal_execution_event_id),
                "old_loan_id": str(source.old_loan_id),
                "old_loan_number": source.old_loan_number,
                "new_loan_id": str(source.new_loan_id),
                "new_loan_number": source.new_loan_number,
                "client_id": str(source.client_id),
                "client_code": source.client_code,
                "client_name": source.client_name,
                "renewal_business_date": source.target_date.isoformat(),
                "disposition": result.disposition,
                "blocker_code": result.blocker_code,
                "message": result.message,
                "policy_version": result.policy_version,
                "old_gross_carrying_amount": _money(
                    result.old_gross_carrying_amount
                ),
                "original_daily_eir": _decimal(result.original_daily_eir),
                "renewal_cash_disbursed_amount": _money(
                    result.renewal_cash_disbursed_amount
                ),
                "renewal_settlement_amount": _money(
                    result.renewal_settlement_amount
                ),
                "renewal_other_deduction_amount": _money(
                    result.renewal_other_deduction_amount
                ),
                "schedule_id": (
                    None if result.schedule_id is None else str(result.schedule_id)
                ),
                "schedule_version": result.schedule_version,
                "payment_frequency": result.payment_frequency,
                "contract_reference": result.contract_reference,
                "contract_signed_date": (
                    None
                    if result.contract_signed_date is None
                    else result.contract_signed_date.isoformat()
                ),
                "schedule_effective_from": (
                    None
                    if result.schedule_effective_from is None
                    else result.schedule_effective_from.isoformat()
                ),
                "evidence_basis": result.evidence_basis,
                "evidence_reference": result.evidence_reference,
                "installment_count": result.installment_count,
                "first_due_date": (
                    None
                    if result.first_due_date is None
                    else result.first_due_date.isoformat()
                ),
                "last_due_date": (
                    None
                    if result.last_due_date is None
                    else result.last_due_date.isoformat()
                ),
                "contractual_cash_total": _money(result.contractual_cash_total),
                "present_value_at_original_eir": _money(
                    result.present_value_at_original_eir
                ),
                "present_value_change_amount": _money(
                    result.present_value_change_amount
                ),
                "present_value_change_percent": _decimal(
                    result.present_value_change_percent
                ),
                "treatment_decision_required": result.treatment_decision_required,
                "automatic_classification_enabled": (
                    result.automatic_classification_enabled
                ),
                "quantitative_threshold_decisive": (
                    result.quantitative_threshold_decisive
                ),
                "journal_lines_enabled": result.journal_lines_enabled,
                "automatic_source_posting": result.automatic_source_posting,
                "read_only": True,
                "notice": (
                    "This endpoint assembles authoritative renewal treatment evidence and an informational present-value comparison only. It does not apply an automatic 10% derecognition rule, does not decide modification versus derecognition, creates no journal lines, and keeps automatic source posting disabled."
                ),
            },
        }

    return router
