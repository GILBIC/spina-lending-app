from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .renewal_treatment_accounting_target_repository import (
    PostgresRenewalTreatmentAccountingTargetRepository,
    RenewalTreatmentAccountingTargetError,
    RenewalTreatmentAccountingTargetNotFound,
)
from .request_auth import authenticated_device_context


def renewal_treatment_accounting_target_repository_dependency() -> (
    PostgresRenewalTreatmentAccountingTargetRepository
):
    return PostgresRenewalTreatmentAccountingTargetRepository()


def _money(value):
    return None if value is None else format(value, ".2f")


def _decimal(value):
    return None if value is None else format(value, "f")


def create_renewal_treatment_accounting_target_router() -> APIRouter:
    router = APIRouter(tags=["management renewal treatment accounting target"])

    @router.get(
        "/api/v1/management/accounting/renewals/{renewal_execution_event_id}/treatment-accounting-target"
    )
    def treatment_accounting_target(
        renewal_execution_event_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresRenewalTreatmentAccountingTargetRepository = Depends(
            renewal_treatment_accounting_target_repository_dependency
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
                    "message": "Management access is required for renewal treatment accounting review.",
                },
            )

        try:
            record = repository.load(
                renewal_execution_event_id=renewal_execution_event_id,
            )
        except RenewalTreatmentAccountingTargetNotFound as error:
            raise HTTPException(
                status_code=404,
                detail={"code": error.code, "message": str(error)},
            ) from error
        except RenewalTreatmentAccountingTargetError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": error.code, "message": str(error)},
            ) from error

        decision = record.decision
        target = record.target
        return {
            "success": True,
            "data": {
                "renewal_execution_event_id": str(decision.renewal_execution_event_id),
                "decision_id": str(decision.decision_id),
                "decision": decision.decision,
                "decision_policy_version": decision.decision_policy_version,
                "decision_reviewed_at": decision.reviewed_at.isoformat(),
                "old_loan_id": str(decision.old_loan_id),
                "old_loan_number": decision.old_loan_number,
                "new_loan_id": str(decision.new_loan_id),
                "new_loan_number": decision.new_loan_number,
                "client_id": str(decision.client_id),
                "client_code": decision.client_code,
                "client_name": decision.client_name,
                "renewal_business_date": decision.renewal_business_date.isoformat(),
                "disposition": target.disposition,
                "blocker_code": target.blocker_code,
                "message": target.message,
                "policy_version": target.policy_version,
                "accounting_asset_loan_id": (
                    None
                    if target.accounting_asset_loan_id is None
                    else str(target.accounting_asset_loan_id)
                ),
                "operational_renewal_loan_id": str(
                    target.operational_renewal_loan_id
                ),
                "old_gross_carrying_amount": _money(
                    target.old_gross_carrying_amount
                ),
                "revised_gross_carrying_amount": _money(
                    target.revised_gross_carrying_amount
                ),
                "original_daily_eir": _decimal(target.original_daily_eir),
                "modification_adjustment_amount": _money(
                    target.modification_adjustment_amount
                ),
                "modification_profit_or_loss": target.modification_profit_or_loss,
                "accounting_asset_continues": target.accounting_asset_continues,
                "new_financial_asset_recognition_required": (
                    target.new_financial_asset_recognition_required
                ),
                "new_financial_asset_measurement_required": (
                    target.new_financial_asset_measurement_required
                ),
                "treatment_journal_coordinates_ready": (
                    target.treatment_journal_coordinates_ready
                ),
                "journal_lines_enabled": target.journal_lines_enabled,
                "automatic_source_posting": target.automatic_source_posting,
                "read_only": True,
                "notice": (
                    "This endpoint consumes an immutable reviewed renewal treatment decision and exposes a read-only accounting measurement target only. It does not choose the treatment, does not assign final General Ledger gain/loss accounts, creates no journal lines, and keeps automatic source posting disabled. Derecognition remains blocked until authoritative new-financial-asset initial measurement evidence exists."
                ),
            },
        }

    return router
