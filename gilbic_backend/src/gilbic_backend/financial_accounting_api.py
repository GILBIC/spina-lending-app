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
from .financial_accounting_repository import (
    AccountingAccount,
    AccountingCutoverLoan,
    AccountingCutoverReadinessSummary,
    AccountingFiscalPeriod,
    AccountingFoundationSummary,
    AccountingPeriodConflict,
    AccountingPeriodError,
    AccountingPeriodInvalidTransition,
    AccountingPeriodNotFound,
    FinancialAccountingOverview,
    FinancialAccountingSummary,
    LoanAccountingPolicy,
    OpeningBalanceCutoverLine,
    OpeningBalanceCutoverSummary,
    PostgresFinancialAccountingRepository,
)
from .request_auth import authenticated_device_context


class StrictAccountingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateFiscalPeriodRequest(StrictAccountingRequest):
    label: str = Field(min_length=3, max_length=80)
    start_date: date
    end_date: date

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 3:
            raise ValueError("Accounting period label is too short.")
        return normalized


class ChangeFiscalPeriodStatusRequest(StrictAccountingRequest):
    status: Literal["open", "review", "closed"]
    confirm_close: bool = False


def financial_accounting_repository_dependency() -> (
    PostgresFinancialAccountingRepository
):
    return PostgresFinancialAccountingRepository()


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _optional_decimal(value: Decimal | None) -> str | None:
    return _decimal(value) if value is not None else None


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


def _fiscal_period_payload(period: AccountingFiscalPeriod) -> dict[str, object]:
    return {
        "period_id": str(period.period_id),
        "label": period.label,
        "start_date": period.start_date.isoformat(),
        "end_date": period.end_date.isoformat(),
        "status": period.status,
        "journal_count": period.journal_count,
        "draft_journal_count": period.draft_journal_count,
        "posted_journal_count": period.posted_journal_count,
        "closed_by_name": period.closed_by_name,
        "closed_at": period.closed_at.isoformat() if period.closed_at else None,
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


def _cutover_summary_payload(
    summary: AccountingCutoverReadinessSummary,
) -> dict[str, object]:
    return {
        "active_loan_count": summary.active_loan_count,
        "source_ready_count": summary.source_ready_count,
        "contract_validation_count": summary.contract_validation_count,
        "blocked_count": summary.blocked_count,
        "opening_balances_configured": summary.opening_balances_configured,
        "automatic_source_posting_enabled": summary.automatic_source_posting_enabled,
        "overall_status": summary.overall_status,
    }


def _cutover_loan_payload(loan: AccountingCutoverLoan) -> dict[str, object]:
    return {
        "loan_number": loan.loan_number,
        "client_code": loan.client_code,
        "client_name": loan.client_name,
        "loan_type_name": loan.loan_type_name,
        "calculation_mode": loan.calculation_mode,
        "term_days": loan.term_days,
        "principal": _decimal(loan.principal),
        "daily_amount": _decimal(loan.daily_amount),
        "interest_rate": _optional_decimal(loan.interest_rate),
        "date_released": loan.date_released.isoformat(),
        "due_date": loan.due_date.isoformat(),
        "operational_balance": _decimal(loan.operational_balance),
        "regular_contract_total": _optional_decimal(loan.regular_contract_total),
        "regular_scheduled_total": _optional_decimal(loan.regular_scheduled_total),
        "seven_by_seven_expected_daily_interest": _optional_decimal(
            loan.seven_by_seven_expected_daily_interest
        ),
        "seven_by_seven_contract_interest_total": _optional_decimal(
            loan.seven_by_seven_contract_interest_total
        ),
        "seven_by_seven_contract_total_if_principal_at_maturity": _optional_decimal(
            loan.seven_by_seven_contract_total_if_principal_at_maturity
        ),
        "seven_by_seven_base_daily_rate_percent": _optional_decimal(
            loan.seven_by_seven_base_daily_rate_percent
        ),
        "readiness_status": loan.readiness_status,
        "blockers": list(loan.blockers),
    }


def _opening_balance_summary_payload(
    summary: OpeningBalanceCutoverSummary,
) -> dict[str, object]:
    return {
        "cutover_date": summary.cutover_date.isoformat() if summary.cutover_date else None,
        "worksheet_status": summary.worksheet_status,
        "worksheet_line_count": summary.worksheet_line_count,
        "source_reference_count": summary.source_reference_count,
        "manual_required_count": summary.manual_required_count,
        "reconciliation_required_count": summary.reconciliation_required_count,
        "calculation_required_count": summary.calculation_required_count,
        "assessment_required_count": summary.assessment_required_count,
        "profit_loss_migration_policy_required": (
            summary.profit_loss_migration_policy_required
        ),
        "worksheet_balanced": summary.worksheet_balanced,
        "ready_to_post": summary.ready_to_post,
        "opening_balance_posting_enabled": summary.opening_balance_posting_enabled,
        "automatic_source_posting_enabled": summary.automatic_source_posting_enabled,
    }


def _opening_balance_line_payload(
    line: OpeningBalanceCutoverLine,
) -> dict[str, object]:
    return {
        "account_code": line.account_code,
        "system_key": line.system_key,
        "account_name": line.account_name,
        "account_type": line.account_type,
        "normal_balance": line.normal_balance,
        "source_reference_amount": _optional_decimal(line.source_reference_amount),
        "source_basis": line.source_basis,
        "readiness_status": line.readiness_status,
        "guidance": line.guidance,
    }


def _overview_payload(
    overview: FinancialAccountingOverview,
    *,
    can_manage_periods: bool,
) -> dict[str, object]:
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
        "fiscal_periods": [
            _fiscal_period_payload(item) for item in overview.fiscal_periods
        ],
        "policies": [_policy_payload(item) for item in overview.policies],
        "cutover": {
            "summary": _cutover_summary_payload(overview.cutover_summary),
            "loans": [_cutover_loan_payload(item) for item in overview.cutover_loans],
        },
        "opening_balance_worksheet": {
            "summary": _opening_balance_summary_payload(
                overview.opening_balance_summary
            ),
            "lines": [
                _opening_balance_line_payload(item)
                for item in overview.opening_balance_lines
            ],
        },
        "foundation_status": (
            "ready" if foundation.account_count > 0 else "not_started"
        ),
        "fiscal_period_status": fiscal_period_status,
        "period_management_enabled": can_manage_periods,
        "journal_status": "manual_ready",
        "trial_balance_status": "available",
        "notice": (
            "Financial Accounting now includes Stage 5B cutover-readiness controls: "
            "the 7x7 base contractual cash-flow schedule is validated and an opening-"
            "balance source worksheet is available for review. The worksheet is not "
            "a journal and cannot post. Automatic loan posting, opening-balance "
            "conversion, final EIR carrying amounts, ECL posting, and tax posting "
            "remain disabled until later controlled stages."
        ),
    }


def _period_exception(error: AccountingPeriodError) -> HTTPException:
    if isinstance(error, AccountingPeriodNotFound):
        status_code = 404
    elif isinstance(error, (AccountingPeriodConflict, AccountingPeriodInvalidTransition)):
        status_code = 409
    else:
        status_code = 500
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    )


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
            "data": _overview_payload(
                accounting.load_overview(),
                can_manage_periods="accounting.period.manage" in actor.permissions,
            ),
        }

    @router.post(
        "/api/v1/management/financial-accounting/fiscal-periods",
        status_code=status.HTTP_201_CREATED,
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/fiscal-periods",
        status_code=status.HTTP_201_CREATED,
        include_in_schema=False,
    )
    def create_fiscal_period(
        body: CreateFiscalPeriodRequest,
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
            permission="accounting.period.manage",
            permission_error="Accounting period management permission is required.",
        )
        if body.end_date < body.start_date:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_accounting_period_dates",
                    "message": "Accounting period end date cannot be before the start date.",
                },
            )
        try:
            period = accounting.create_fiscal_period(
                actor_user_id=actor.user_id,
                label=body.label,
                start_date=body.start_date,
                end_date=body.end_date,
            )
        except AccountingPeriodError as error:
            raise _period_exception(error) from error
        return {"success": True, "data": {"period": _fiscal_period_payload(period)}}

    @router.post(
        "/api/v1/management/financial-accounting/fiscal-periods/{period_id}/status"
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/fiscal-periods/{period_id}/status",
        include_in_schema=False,
    )
    def change_fiscal_period_status(
        period_id: UUID,
        body: ChangeFiscalPeriodStatusRequest,
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
            permission="accounting.period.manage",
            permission_error="Accounting period management permission is required.",
        )
        if body.status == "closed" and not body.confirm_close:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "accounting_period_close_confirmation_required",
                    "message": "Confirm the accounting period close before continuing.",
                },
            )
        try:
            period = accounting.set_fiscal_period_status(
                actor_user_id=actor.user_id,
                period_id=period_id,
                status=body.status,
            )
        except AccountingPeriodError as error:
            raise _period_exception(error) from error
        return {"success": True, "data": {"period": _fiscal_period_payload(period)}}

    return router
