from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .general_journal_repository import (
    GeneralJournalError,
    JournalConflict,
    JournalEntry,
    JournalNotFound,
    JournalValidationError,
    PostgresGeneralJournalRepository,
    TrialBalance,
)
from .request_auth import authenticated_device_context


class StrictJournalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JournalLineRequest(StrictJournalRequest):
    account_code: str = Field(min_length=1, max_length=20)
    description: str = Field(default="", max_length=240)
    debit: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    credit: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)

    @field_validator("account_code")
    @classmethod
    def normalize_account_code(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_side(self) -> "JournalLineRequest":
        if not ((self.debit > 0 and self.credit == 0) or (self.credit > 0 and self.debit == 0)):
            raise ValueError("Each journal line must contain either a debit or a credit amount.")
        return self


class ManualJournalRequest(StrictJournalRequest):
    posting_date: date
    description: str = Field(min_length=3, max_length=240)
    lines: list[JournalLineRequest] = Field(min_length=2, max_length=30)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 3:
            raise ValueError("Journal description is too short.")
        return normalized

    @model_validator(mode="after")
    def validate_balanced(self) -> "ManualJournalRequest":
        debit = sum((line.debit for line in self.lines), Decimal("0"))
        credit = sum((line.credit for line in self.lines), Decimal("0"))
        if debit <= 0 or debit != credit:
            raise ValueError("Manual journal entry must be balanced before it can be saved.")
        return self


class ConfirmJournalActionRequest(StrictJournalRequest):
    confirm: bool = False


class ReverseJournalRequest(StrictJournalRequest):
    posting_date: date
    description: str = Field(min_length=3, max_length=240)


def general_journal_repository_dependency() -> PostgresGeneralJournalRepository:
    return PostgresGeneralJournalRepository()


def _decimal(value: Decimal) -> str:
    return format(value, ".2f")


def _entry_payload(entry: JournalEntry) -> dict[str, object]:
    return {
        "entry_id": str(entry.entry_id),
        "entry_number": entry.entry_number,
        "period_id": str(entry.period_id),
        "period_label": entry.period_label,
        "posting_date": entry.posting_date.isoformat(),
        "description": entry.description,
        "status": entry.status,
        "source_type": entry.source_type,
        "source_reference": entry.source_reference,
        "reversal_of_entry_id": (
            str(entry.reversal_of_entry_id) if entry.reversal_of_entry_id else None
        ),
        "created_by_name": entry.created_by_name,
        "posted_by_name": entry.posted_by_name,
        "created_at": entry.created_at.isoformat(),
        "posted_at": entry.posted_at.isoformat() if entry.posted_at else None,
        "total_debit": _decimal(entry.total_debit),
        "total_credit": _decimal(entry.total_credit),
        "lines": [
            {
                "line_number": line.line_number,
                "account_code": line.account_code,
                "account_name": line.account_name,
                "description": line.description,
                "debit": _decimal(line.debit),
                "credit": _decimal(line.credit),
            }
            for line in entry.lines
        ],
    }


def _trial_balance_payload(trial: TrialBalance) -> dict[str, object]:
    return {
        "period_id": str(trial.period_id) if trial.period_id else None,
        "period_label": trial.period_label,
        "total_debits": _decimal(trial.total_debits),
        "total_credits": _decimal(trial.total_credits),
        "balanced": trial.balanced,
        "lines": [
            {
                "account_code": line.account_code,
                "account_name": line.account_name,
                "account_type": line.account_type,
                "normal_balance": line.normal_balance,
                "total_debit": _decimal(line.total_debit),
                "total_credit": _decimal(line.total_credit),
                "debit_balance": _decimal(line.debit_balance),
                "credit_balance": _decimal(line.credit_balance),
            }
            for line in trial.lines
        ],
    }


def _journal_exception(error: GeneralJournalError) -> HTTPException:
    if isinstance(error, JournalNotFound):
        status_code = 404
    elif isinstance(error, JournalConflict):
        status_code = 409
    elif isinstance(error, JournalValidationError):
        status_code = 422
    else:
        status_code = 500
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    )


def _actor(
    *,
    authorization: str | None,
    x_device_id: str | None,
    auth: SupabaseAuthClient,
    accounts: PostgresAccountRepository,
    manage: bool,
):
    actor = authenticated_device_context(
        authorization=authorization,
        device_identifier=x_device_id,
        auth=auth,
        accounts=accounts,
        permission="accounting.journal.manage" if manage else "accounting.view",
        permission_error=(
            "General Journal management permission is required."
            if manage
            else "Financial Accounting view permission is required."
        ),
    )
    if "management" not in actor.roles:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "management_role_required",
                "message": "Management access is required for General Journal.",
            },
        )
    return actor


def _line_dicts(body: ManualJournalRequest) -> list[dict[str, object]]:
    return [
        {
            "account_code": line.account_code,
            "description": line.description.strip(),
            "debit": _decimal(line.debit),
            "credit": _decimal(line.credit),
        }
        for line in body.lines
    ]


def create_general_journal_router() -> APIRouter:
    router = APIRouter(tags=["management general journal"])

    @router.get("/api/v1/management/financial-accounting/journals")
    @router.get(
        "/api/mobile/v1/management/financial-accounting/journals",
        include_in_schema=False,
    )
    def list_journals(
        limit: int = Query(default=100, ge=1, le=250),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        journal: PostgresGeneralJournalRepository = Depends(
            general_journal_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            manage=False,
        )
        return {
            "success": True,
            "data": {
                "entries": [_entry_payload(item) for item in journal.list_journals(limit=limit)],
                "can_manage": "accounting.journal.manage" in actor.permissions,
                "automatic_loan_posting_enabled": False,
            },
        }

    @router.post(
        "/api/v1/management/financial-accounting/journals",
        status_code=status.HTTP_201_CREATED,
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/journals",
        status_code=status.HTTP_201_CREATED,
        include_in_schema=False,
    )
    def create_manual_journal(
        body: ManualJournalRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        journal: PostgresGeneralJournalRepository = Depends(
            general_journal_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            manage=True,
        )
        try:
            entry = journal.create_manual_draft(
                actor_user_id=actor.user_id,
                posting_date=body.posting_date,
                description=body.description,
                lines=_line_dicts(body),
            )
        except GeneralJournalError as error:
            raise _journal_exception(error) from error
        return {"success": True, "data": {"entry": _entry_payload(entry)}}

    @router.put("/api/v1/management/financial-accounting/journals/{entry_id}")
    @router.put(
        "/api/mobile/v1/management/financial-accounting/journals/{entry_id}",
        include_in_schema=False,
    )
    def update_manual_journal(
        entry_id: UUID,
        body: ManualJournalRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        journal: PostgresGeneralJournalRepository = Depends(
            general_journal_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            manage=True,
        )
        try:
            entry = journal.update_manual_draft(
                entry_id=entry_id,
                actor_user_id=actor.user_id,
                posting_date=body.posting_date,
                description=body.description,
                lines=_line_dicts(body),
            )
        except GeneralJournalError as error:
            raise _journal_exception(error) from error
        return {"success": True, "data": {"entry": _entry_payload(entry)}}

    @router.delete("/api/v1/management/financial-accounting/journals/{entry_id}")
    @router.delete(
        "/api/mobile/v1/management/financial-accounting/journals/{entry_id}",
        include_in_schema=False,
    )
    def cancel_manual_journal(
        entry_id: UUID,
        body: ConfirmJournalActionRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        journal: PostgresGeneralJournalRepository = Depends(
            general_journal_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            manage=True,
        )
        if not body.confirm:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "journal_cancel_confirmation_required",
                    "message": "Confirm journal draft cancellation before continuing.",
                },
            )
        try:
            journal.cancel_manual_draft(entry_id=entry_id, actor_user_id=actor.user_id)
        except GeneralJournalError as error:
            raise _journal_exception(error) from error
        return {"success": True, "data": {"cancelled": True}}

    @router.post("/api/v1/management/financial-accounting/journals/{entry_id}/post")
    @router.post(
        "/api/mobile/v1/management/financial-accounting/journals/{entry_id}/post",
        include_in_schema=False,
    )
    def post_journal(
        entry_id: UUID,
        body: ConfirmJournalActionRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        journal: PostgresGeneralJournalRepository = Depends(
            general_journal_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            manage=True,
        )
        if not body.confirm:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "journal_post_confirmation_required",
                    "message": "Confirm journal posting before continuing. Posted journals are immutable.",
                },
            )
        try:
            entry = journal.post_journal(entry_id=entry_id, actor_user_id=actor.user_id)
        except GeneralJournalError as error:
            raise _journal_exception(error) from error
        return {"success": True, "data": {"entry": _entry_payload(entry)}}

    @router.post("/api/v1/management/financial-accounting/journals/{entry_id}/reverse")
    @router.post(
        "/api/mobile/v1/management/financial-accounting/journals/{entry_id}/reverse",
        include_in_schema=False,
    )
    def reverse_journal(
        entry_id: UUID,
        body: ReverseJournalRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        journal: PostgresGeneralJournalRepository = Depends(
            general_journal_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            manage=True,
        )
        try:
            reversal = journal.create_reversal_draft(
                entry_id=entry_id,
                actor_user_id=actor.user_id,
                posting_date=body.posting_date,
                description=body.description,
            )
        except GeneralJournalError as error:
            raise _journal_exception(error) from error
        return {"success": True, "data": {"entry": _entry_payload(reversal)}}

    @router.get("/api/v1/management/financial-accounting/trial-balance")
    @router.get(
        "/api/mobile/v1/management/financial-accounting/trial-balance",
        include_in_schema=False,
    )
    def trial_balance(
        period_id: UUID | None = Query(default=None),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        journal: PostgresGeneralJournalRepository = Depends(
            general_journal_repository_dependency
        ),
    ) -> dict[str, object]:
        _actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
            manage=False,
        )
        try:
            result = journal.trial_balance(period_id=period_id)
        except GeneralJournalError as error:
            raise _journal_exception(error) from error
        return {"success": True, "data": {"trial_balance": _trial_balance_payload(result)}}

    return router
