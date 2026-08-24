from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .past_due_followup_contracts import PastDueFollowupCreateBody
from .past_due_followup_repository import (
    PastDueFollowupConflict,
    PastDueFollowupError,
    PastDueFollowupForbidden,
    PastDueFollowupInvalid,
    PastDueFollowupNotFound,
    PastDueFollowupRecord,
    PostgresPastDueFollowupRepository,
)
from .request_auth import authenticated_device_context


def past_due_followup_repository_dependency() -> PostgresPastDueFollowupRepository:
    return PostgresPastDueFollowupRepository()


def _record_payload(record: PastDueFollowupRecord) -> dict[str, object]:
    promise: dict[str, object] | None = None
    if record.promise_id is not None:
        promise = {
            "id": str(record.promise_id),
            "promised_payment_date": (
                record.promised_payment_date.isoformat()
                if record.promised_payment_date is not None
                else None
            ),
            "initial_promised_amount": (
                format(record.initial_promised_amount, "f")
                if record.initial_promised_amount is not None
                else None
            ),
            "promised_amount": (
                format(record.promised_amount, "f")
                if record.promised_amount is not None
                else None
            ),
            "remaining_promised_amount": (
                format(record.remaining_promised_amount, "f")
                if record.remaining_promised_amount is not None
                else None
            ),
            "status": record.promise_status,
            "version": record.promise_version,
        }

    return {
        "id": str(record.id),
        "client_id": str(record.client_id),
        "loan_id": str(record.loan_id),
        "installment_id": record.installment_id,
        "obligation_date": record.obligation_date.isoformat(),
        "original_past_due_amount": format(record.original_past_due_amount, "f"),
        "remaining_past_due_amount": format(record.remaining_past_due_amount, "f"),
        "event_kind": record.event_kind,
        "reason_code": record.reason_code,
        "reason_note": record.reason_note,
        "status": record.status,
        "promise": promise,
    }


def _raise_followup_error(error: PastDueFollowupError) -> None:
    if isinstance(error, PastDueFollowupNotFound):
        status = 404
    elif isinstance(error, PastDueFollowupForbidden):
        status = 403
    elif isinstance(error, PastDueFollowupInvalid):
        status = 422
    elif isinstance(error, PastDueFollowupConflict):
        status = 409
    else:
        status = 409
    raise HTTPException(
        status_code=status,
        detail={"code": error.code, "message": str(error)},
    ) from error


def create_past_due_followup_router() -> APIRouter:
    router = APIRouter(tags=["past due follow-up"])

    @router.post("/api/v1/collector/past-due-followups")
    @router.post(
        "/api/mobile/v1/collector/past-due-followups",
        include_in_schema=False,
    )
    def create_followup(
        body: PastDueFollowupCreateBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        followups: PostgresPastDueFollowupRepository = Depends(
            past_due_followup_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="collection.create",
            permission_error="Collection permission is required.",
        )
        try:
            record = followups.create_for_collection(
                actor_user_id=actor.user_id,
                source_transaction_id=body.source_transaction_id,
                installment_id=body.installment_id,
                obligation_date=body.obligation_date,
                past_due_amount=body.past_due_amount,
                event_kind=body.event_kind,
                reason=body.reason,
            )
        except PastDueFollowupError as error:
            _raise_followup_error(error)
        return {"success": True, "data": _record_payload(record)}

    return router
