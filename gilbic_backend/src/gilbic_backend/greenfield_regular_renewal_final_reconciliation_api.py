from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .greenfield_regular_renewal_final_reconciliation_repository import (
    GreenfieldRegularRenewalFinalReconciliationError,
    GreenfieldRegularRenewalFinalReconciliationNotFound,
    PostgresGreenfieldRegularRenewalFinalReconciliationRepository,
)
from .request_auth import authenticated_device_context


def greenfield_regular_renewal_final_reconciliation_repository_dependency() -> (
    PostgresGreenfieldRegularRenewalFinalReconciliationRepository
):
    return PostgresGreenfieldRegularRenewalFinalReconciliationRepository()


def _money(value):
    return None if value is None else format(value, ".2f")


def create_greenfield_regular_renewal_final_reconciliation_router() -> APIRouter:
    router = APIRouter(tags=["management final protected Regular renewal reconciliation"])

    @router.get(
        "/api/v1/management/accounting/renewals/{renewal_execution_event_id}/final-ledger-reconciliation"
    )
    def final_renewal_ledger_reconciliation(
        renewal_execution_event_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresGreenfieldRegularRenewalFinalReconciliationRepository = Depends(
            greenfield_regular_renewal_final_reconciliation_repository_dependency
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
                    "message": "Management access is required for final protected Regular renewal reconciliation.",
                },
            )
        try:
            record = repository.load(
                renewal_execution_event_id=renewal_execution_event_id
            )
        except GreenfieldRegularRenewalFinalReconciliationNotFound as error:
            raise HTTPException(
                status_code=404,
                detail={"code": error.code, "message": str(error)},
            ) from error
        except GreenfieldRegularRenewalFinalReconciliationError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": error.code, "message": str(error)},
            ) from error

        source = record.source
        result = record.final
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
                "target_date": source.target_date.isoformat(),
                "disposition": result.disposition,
                "blocker_code": result.blocker_code,
                "message": result.message,
                "policy_version": result.policy_version,
                "protected_source_journals_reconciled": (
                    result.protected_source_journals_reconciled
                ),
                "expected_boundary_journal_count": (
                    result.expected_boundary_journal_count
                ),
                "exact_posted_boundary_journal_count": (
                    result.exact_posted_boundary_journal_count
                ),
                "boundary_effective_interest_amount": _money(
                    result.boundary_effective_interest_amount
                ),
                "ledger_loan_component_before_boundary": _money(
                    result.ledger_loan_component_before_boundary
                ),
                "ledger_accrued_interest_before_boundary": _money(
                    result.ledger_accrued_interest_before_boundary
                ),
                "ledger_gross_carrying_before_boundary": _money(
                    result.ledger_gross_carrying_before_boundary
                ),
                "final_ledger_loan_component": _money(
                    result.final_ledger_loan_component
                ),
                "final_ledger_accrued_interest_component": _money(
                    result.final_ledger_accrued_interest_component
                ),
                "final_ledger_gross_carrying_amount": _money(
                    result.final_ledger_gross_carrying_amount
                ),
                "target_loan_component": _money(result.target_loan_component),
                "target_accrued_interest_component": _money(
                    result.target_accrued_interest_component
                ),
                "target_gross_carrying_amount": _money(
                    result.target_gross_carrying_amount
                ),
                "target_ledger_reconciled": result.target_ledger_reconciled,
                "accounting_carrying_amount_ready": (
                    result.accounting_carrying_amount_ready
                ),
                "journal_lines_enabled": result.journal_lines_enabled,
                "automatic_source_posting": result.automatic_source_posting,
                "notice": (
                    "A ready result means the old-loan accounting carrying amount is authoritative evidence for the next renewal modification/derecognition decision only. It does not itself create renewal treatment journals, and automatic source posting remains disabled."
                ),
            },
        }

    return router