from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .financial_accounting_repository import (
    FinancialAccountingOverview,
    FinancialAccountingSummary,
    LoanAccountingPolicy,
    PostgresFinancialAccountingRepository,
)
from .request_auth import authenticated_device_context


def financial_accounting_repository_dependency() -> (
    PostgresFinancialAccountingRepository
):
    return PostgresFinancialAccountingRepository()


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _summary_payload(summary: FinancialAccountingSummary) -> dict[str, object]:
    return {
        "active_loan_count": summary.active_loan_count,
        "active_principal": _decimal(summary.active_principal),
        "operational_outstanding": _decimal(summary.operational_outstanding),
        "regular_outstanding": _decimal(summary.regular_outstanding),
        "seven_by_seven_outstanding": _decimal(summary.seven_by_seven_outstanding),
        "unremitted_cash": _decimal(summary.unremitted_cash),
        "received_remittance_total": _decimal(summary.received_remittance_total),
        "valid_collection_count": summary.valid_collection_count,
        "correction_count": summary.correction_count,
        "void_count": summary.void_count,
    }


def _policy_payload(policy: LoanAccountingPolicy) -> dict[str, object]:
    return {
        "code": policy.code,
        "name": policy.name,
        "term_days": policy.term_days,
        "calculation_mode": policy.calculation_mode,
        "daily_interest_per_1000": _decimal(policy.daily_interest_per_1000),
        "mobile_collections_enabled": policy.mobile_collections_enabled,
        "operational_rule": policy.operational_rule,
        "accounting_rule": policy.accounting_rule,
        "renewal_rule": policy.renewal_rule,
    }


def _overview_payload(overview: FinancialAccountingOverview) -> dict[str, object]:
    return {
        "summary": _summary_payload(overview.summary),
        "policies": [_policy_payload(item) for item in overview.policies],
        "journal_status": "not_started",
        "trial_balance_status": "unavailable",
        "notice": (
            "Financial Accounting is currently a read-only control center. It reads "
            "existing lending and cash-custody sources but does not create, post, "
            "edit, reverse, or close accounting journal entries."
        ),
    }


def create_financial_accounting_router() -> APIRouter:
    router = APIRouter(tags=["management financial accounting"])

    @router.get("/api/v1/management/financial-accounting")
    @router.get(
        "/api/mobile/v1/management/financial-accounting",
        include_in_schema=False,
    )
    def financial_accounting_overview(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        accounting: PostgresFinancialAccountingRepository = Depends(
            financial_accounting_repository_dependency
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
                    "message": "Management access is required for Financial Accounting.",
                },
            )
        return {
            "success": True,
            "data": _overview_payload(accounting.load_overview()),
        }

    return router
