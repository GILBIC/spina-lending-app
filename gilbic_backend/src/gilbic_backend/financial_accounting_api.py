from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .financial_accounting_repository import (
    AccountingAccount,
    AccountingFoundationSummary,
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


def _foundation_payload(
    foundation: AccountingFoundationSummary,
) -> dict[str, object]:
    return {
        "account_count": foundation.account_count,
        "posting_account_count": foundation.posting_account_count,
        "fiscal_period_count": foundation.fiscal_period_count,
        "open_period_count": foundation.open_period_count,
        "journal_entry_count": foundation.journal_entry_count,
        "draft_journal_count": foundation.draft_journal_count,
        "posted_journal_count": foundation.posted_journal_count,
        "reversal_draft_count": foundation.reversal_draft_count,
    }


def _account_payload(account: AccountingAccount) -> dict[str, object]:
    return {
        "code": account.code,
        "system_key": account.system_key,
        "name": account.name,
        "account_type": account.account_type,
        "normal_balance": account.normal_balance,
        "is_posting": account.is_posting,
        "is_active": account.is_active,
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
    foundation = overview.foundation
    fiscal_period_status = (
        "open"
        if foundation.open_period_count > 0
        else "configured"
        if foundation.fiscal_period_count > 0
        else "not_configured"
    )
    return {
        "summary": _summary_payload(overview.summary),
        "foundation": _foundation_payload(foundation),
        "accounts": [_account_payload(item) for item in overview.accounts],
        "policies": [_policy_payload(item) for item in overview.policies],
        "foundation_status": (
            "ready" if foundation.account_count > 0 else "not_started"
        ),
        "fiscal_period_status": fiscal_period_status,
        "journal_status": "foundation_ready",
        "trial_balance_status": "unavailable",
        "notice": (
            "Financial Accounting now has a protected database foundation and chart "
            "of accounts. This mobile view remains read-only: no automatic loan "
            "posting, opening-balance conversion, period closing, or financial "
            "statement posting is enabled yet."
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
