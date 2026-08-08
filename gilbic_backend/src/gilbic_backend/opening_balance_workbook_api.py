from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .opening_balance_workbook_repository import (
    LoanMeasurement,
    LoanMeasurementSummary,
    OpeningBalanceWorkbook,
    OpeningBalanceWorkbookConflict,
    OpeningBalanceWorkbookError,
    OpeningBalanceWorkbookLine,
    OpeningBalanceWorkbookNotFound,
    OpeningBalanceWorkbookSummary,
    OpeningBalanceWorkbookValidation,
    PostgresOpeningBalanceWorkbookRepository,
)
from .request_auth import authenticated_device_context


class StrictOpeningBalanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateOpeningBalanceWorkbookRequest(StrictOpeningBalanceRequest):
    cutover_date: date


class UpdateOpeningBalanceLineRequest(StrictOpeningBalanceRequest):
    debit: Decimal | None = Field(default=None, ge=0)
    credit: Decimal | None = Field(default=None, ge=0)
    verification_status: Literal["pending", "verified"] = "pending"
    evidence_note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_line(self):
        debit = self.debit or Decimal("0")
        credit = self.credit or Decimal("0")
        if debit > 0 and credit > 0:
            raise ValueError("An opening-balance line cannot contain both debit and credit.")
        if self.verification_status == "verified":
            if self.debit is None and self.credit is None:
                raise ValueError(
                    "A verified opening-balance line requires an explicit amount."
                )
            if len((self.evidence_note or "").strip()) < 3:
                raise ValueError(
                    "A verified opening-balance line requires an evidence note."
                )
        return self


class UpdateOpeningBalancePolicyRequest(StrictOpeningBalanceRequest):
    confirmed: bool
    policy_note: str | None = Field(default=None, max_length=1000)


class ChangeOpeningBalanceWorkbookStatusRequest(StrictOpeningBalanceRequest):
    status: Literal["draft", "review_ready"]


def opening_balance_workbook_repository_dependency() -> (
    PostgresOpeningBalanceWorkbookRepository
):
    return PostgresOpeningBalanceWorkbookRepository()


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _optional_decimal(value: Decimal | None) -> str | None:
    return _decimal(value) if value is not None else None


def _summary_payload(summary: OpeningBalanceWorkbookSummary) -> dict[str, object]:
    return {
        "workbook_id": str(summary.workbook_id) if summary.workbook_id else None,
        "cutover_date": summary.cutover_date.isoformat() if summary.cutover_date else None,
        "status": summary.status,
        "line_count": summary.line_count,
        "source_reference_count": summary.source_reference_count,
        "verified_line_count": summary.verified_line_count,
        "pending_line_count": summary.pending_line_count,
        "profit_loss_policy_confirmed": summary.profit_loss_policy_confirmed,
        "profit_loss_policy_note": summary.profit_loss_policy_note,
        "total_debit": _decimal(summary.total_debit),
        "total_credit": _decimal(summary.total_credit),
        "balance_variance": _decimal(summary.balance_variance),
        "worksheet_balanced": summary.worksheet_balanced,
        "ready_for_review": summary.ready_for_review,
        "ready_to_post": summary.ready_to_post,
        "opening_balance_posting_enabled": summary.opening_balance_posting_enabled,
        "automatic_source_posting_enabled": summary.automatic_source_posting_enabled,
    }


def _line_payload(line: OpeningBalanceWorkbookLine) -> dict[str, object]:
    return {
        "workbook_id": str(line.workbook_id) if line.workbook_id else None,
        "account_code": line.account_code,
        "system_key": line.system_key,
        "account_name": line.account_name,
        "account_type": line.account_type,
        "normal_balance": line.normal_balance,
        "source_reference_amount": _optional_decimal(line.source_reference_amount),
        "source_basis": line.source_basis,
        "requirement_type": line.requirement_type,
        "guidance": line.guidance,
        "proposed_debit": _optional_decimal(line.proposed_debit),
        "proposed_credit": _optional_decimal(line.proposed_credit),
        "verification_status": line.verification_status,
        "evidence_note": line.evidence_note,
        "measurement_reference_amount": _optional_decimal(
            line.measurement_reference_amount
        ),
        "measurement_status": line.measurement_status,
        "measurement_note": line.measurement_note,
    }


def _measurement_summary_payload(
    summary: LoanMeasurementSummary,
) -> dict[str, object]:
    return {
        "active_loan_count": summary.active_loan_count,
        "measured_loan_count": summary.measured_loan_count,
        "review_required_count": summary.review_required_count,
        "actual_cash_received": _decimal(summary.actual_cash_received),
        "effective_interest_income": _decimal(summary.effective_interest_income),
        "regular_loan_component": _decimal(summary.regular_loan_component),
        "seven_by_seven_loan_component": _decimal(
            summary.seven_by_seven_loan_component
        ),
        "accrued_interest_component": _decimal(summary.accrued_interest_component),
        "gross_carrying_amount": _decimal(summary.gross_carrying_amount),
        "measurement_status": summary.measurement_status,
        "measurement_policy_version": summary.measurement_policy_version,
        "ecl_included": summary.ecl_included,
        "ready_to_post": summary.ready_to_post,
    }


def _measurement_payload(item: LoanMeasurement) -> dict[str, object]:
    return {
        "loan_id": str(item.loan_id),
        "loan_number": item.loan_number,
        "client_name": item.client_name,
        "calculation_mode": item.calculation_mode,
        "policy_version": item.policy_version,
        "date_released": item.date_released.isoformat(),
        "due_date": item.due_date.isoformat(),
        "cutover_date": item.cutover_date.isoformat() if item.cutover_date else None,
        "days_elapsed": item.days_elapsed,
        "principal": _decimal(item.principal),
        "operational_balance": _decimal(item.operational_balance),
        "daily_eir": _optional_decimal(item.daily_eir),
        "daily_eir_percent": _optional_decimal(item.daily_eir_percent),
        "contractual_cash_due": _optional_decimal(item.contractual_cash_due),
        "actual_cash_received": _optional_decimal(item.actual_cash_received),
        "effective_interest_income": _optional_decimal(
            item.effective_interest_income
        ),
        "loan_component": _optional_decimal(item.loan_component),
        "accrued_interest_component": _optional_decimal(
            item.accrued_interest_component
        ),
        "gross_carrying_amount": _optional_decimal(item.gross_carrying_amount),
        "contractual_unpaid_interest": _optional_decimal(
            item.contractual_unpaid_interest
        ),
        "measurement_status": item.measurement_status,
        "measurement_note": item.measurement_note,
    }


def _workbook_payload(
    workbook: OpeningBalanceWorkbook,
    *,
    can_manage: bool,
) -> dict[str, object]:
    return {
        "summary": _summary_payload(workbook.summary),
        "lines": [_line_payload(line) for line in workbook.lines],
        "measurement": {
            "summary": _measurement_summary_payload(workbook.measurement_summary),
            "loans": [
                _measurement_payload(item) for item in workbook.loan_measurements
            ],
            "notice": (
                "Stage 5D measurements are accounting references only. Daily EIR is "
                "derived from contractual cash flows and actual non-voided cash timing. "
                "ECL is excluded. Measurements do not verify workbook lines and do not "
                "post a journal."
            ),
        },
        "management_enabled": can_manage,
        "notice": (
            "Stage 5D keeps workbook values outside the General Ledger. Saving, "
            "verifying, measurement review, and moving the workbook to review ready "
            "do not post an opening journal. Opening-balance posting and automatic "
            "source posting remain disabled."
        ),
    }


def _exception(error: OpeningBalanceWorkbookError) -> HTTPException:
    if isinstance(error, OpeningBalanceWorkbookNotFound):
        status_code = 404
    elif isinstance(error, OpeningBalanceWorkbookConflict):
        status_code = 409
    elif isinstance(error, OpeningBalanceWorkbookValidation):
        status_code = 422
    else:
        status_code = 500
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    )


def create_opening_balance_workbook_router() -> APIRouter:
    router = APIRouter(tags=["management opening balance workbook"])

    def actor_context(
        *,
        authorization: str | None,
        x_device_id: str | None,
        auth: SupabaseAuthClient,
        accounts: PostgresAccountRepository,
        require_manage: bool,
    ):
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.cutover.manage" if require_manage else None,
            permission_error=(
                "Accounting cutover management permission is required."
                if require_manage
                else None
            ),
        )
        if "management" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "management_role_required",
                    "message": "Management access is required for the opening-balance workbook.",
                },
            )
        return actor

    @router.get("/api/v1/management/financial-accounting/opening-balance-workbook")
    @router.get(
        "/api/mobile/v1/management/financial-accounting/opening-balance-workbook",
        include_in_schema=False,
    )
    def get_workbook(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresOpeningBalanceWorkbookRepository = Depends(
            opening_balance_workbook_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = actor_context(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            require_manage=False,
        )
        return {
            "success": True,
            "data": _workbook_payload(
                repository.load_workbook(),
                can_manage="accounting.cutover.manage" in actor.permissions,
            ),
        }

    @router.post(
        "/api/v1/management/financial-accounting/opening-balance-workbook",
        status_code=status.HTTP_201_CREATED,
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/opening-balance-workbook",
        status_code=status.HTTP_201_CREATED,
        include_in_schema=False,
    )
    def create_workbook(
        body: CreateOpeningBalanceWorkbookRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresOpeningBalanceWorkbookRepository = Depends(
            opening_balance_workbook_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = actor_context(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            require_manage=True,
        )
        try:
            workbook = repository.create_workbook(
                actor_user_id=actor.user_id,
                cutover_date=body.cutover_date,
            )
        except OpeningBalanceWorkbookError as error:
            raise _exception(error) from error
        return {"success": True, "data": _workbook_payload(workbook, can_manage=True)}

    @router.put(
        "/api/v1/management/financial-accounting/opening-balance-workbook/{workbook_id}/lines/{account_code}"
    )
    @router.put(
        "/api/mobile/v1/management/financial-accounting/opening-balance-workbook/{workbook_id}/lines/{account_code}",
        include_in_schema=False,
    )
    def update_line(
        workbook_id: UUID,
        account_code: str,
        body: UpdateOpeningBalanceLineRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresOpeningBalanceWorkbookRepository = Depends(
            opening_balance_workbook_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = actor_context(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            require_manage=True,
        )
        try:
            workbook = repository.update_line(
                actor_user_id=actor.user_id,
                workbook_id=workbook_id,
                account_code=account_code,
                proposed_debit=body.debit,
                proposed_credit=body.credit,
                verification_status=body.verification_status,
                evidence_note=body.evidence_note,
            )
        except OpeningBalanceWorkbookError as error:
            raise _exception(error) from error
        return {"success": True, "data": _workbook_payload(workbook, can_manage=True)}

    @router.put(
        "/api/v1/management/financial-accounting/opening-balance-workbook/{workbook_id}/policy"
    )
    @router.put(
        "/api/mobile/v1/management/financial-accounting/opening-balance-workbook/{workbook_id}/policy",
        include_in_schema=False,
    )
    def update_policy(
        workbook_id: UUID,
        body: UpdateOpeningBalancePolicyRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresOpeningBalanceWorkbookRepository = Depends(
            opening_balance_workbook_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = actor_context(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            require_manage=True,
        )
        try:
            workbook = repository.update_policy(
                actor_user_id=actor.user_id,
                workbook_id=workbook_id,
                confirmed=body.confirmed,
                policy_note=body.policy_note,
            )
        except OpeningBalanceWorkbookError as error:
            raise _exception(error) from error
        return {"success": True, "data": _workbook_payload(workbook, can_manage=True)}

    @router.post(
        "/api/v1/management/financial-accounting/opening-balance-workbook/{workbook_id}/status"
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/opening-balance-workbook/{workbook_id}/status",
        include_in_schema=False,
    )
    def change_status(
        workbook_id: UUID,
        body: ChangeOpeningBalanceWorkbookStatusRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        repository: PostgresOpeningBalanceWorkbookRepository = Depends(
            opening_balance_workbook_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = actor_context(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            require_manage=True,
        )
        try:
            workbook = repository.set_status(
                actor_user_id=actor.user_id,
                workbook_id=workbook_id,
                status=body.status,
            )
        except OpeningBalanceWorkbookError as error:
            raise _exception(error) from error
        return {"success": True, "data": _workbook_payload(workbook, can_manage=True)}

    return router