from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .collection_correction_repository import (
    CollectionCorrectionConflict,
    CollectionCorrectionError,
    CollectionCorrectionForbidden,
    CollectionCorrectionInvalid,
    CollectionCorrectionLocked,
    CollectionCorrectionNotFound,
    CollectionCorrectionRecord,
    PostgresCollectionCorrectionRepository,
)
from .contract_collection_correction import ContractSafeCollectionCorrectionRepository
from .request_auth import authenticated_device_context


class CollectionCorrectionBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    entry_type: str = Field(min_length=1, max_length=20)
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    covered_dates: list[date] = Field(default_factory=list, max_length=366)
    note: str = Field(default="", max_length=500)
    reason: str = Field(min_length=1, max_length=500)
    expected_route_revision: str = Field(min_length=1, max_length=120)


def correction_repository_dependency() -> PostgresCollectionCorrectionRepository:
    return ContractSafeCollectionCorrectionRepository()


def _record_payload(record: CollectionCorrectionRecord) -> dict[str, object]:
    return {
        "transaction_id": str(record.transaction_id),
        "client_id": str(record.client_id),
        "loan_id": str(record.loan_id),
        "collection_date": record.collection_date.isoformat(),
        "entry_type": record.entry_type,
        "amount": format(record.amount, "f"),
        "covered_dates": [value.isoformat() for value in record.covered_dates],
        "note": record.note,
        "official_balance": format(record.official_balance, "f"),
        "pass_count_after": record.pass_count_after,
        "receipt_number": record.receipt_number,
        "edit_version": record.edit_version,
        "route_revision": record.route_revision,
        "edited_at": record.edited_at.isoformat(),
    }


def _raise_correction_error(error: CollectionCorrectionError) -> None:
    if isinstance(error, CollectionCorrectionNotFound):
        status = 404
    elif isinstance(error, CollectionCorrectionForbidden):
        status = 403
    elif isinstance(error, (CollectionCorrectionLocked, CollectionCorrectionConflict)):
        status = 409
    elif isinstance(error, CollectionCorrectionInvalid):
        status = 422
    else:
        status = 409
    raise HTTPException(
        status_code=status,
        detail={"code": error.code, "message": str(error)},
    ) from error


def create_collection_correction_router() -> APIRouter:
    router = APIRouter(tags=["collection corrections"])

    @router.patch("/api/v1/collector/collections/{transaction_id}")
    @router.patch(
        "/api/mobile/v1/collector/collections/{transaction_id}",
        include_in_schema=False,
    )
    def correct_collection(
        transaction_id: UUID,
        body: CollectionCorrectionBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        corrections: PostgresCollectionCorrectionRepository = Depends(
            correction_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="collection.correct.own_unremitted",
            permission_error="Collection correction permission is required.",
        )
        try:
            record = corrections.correct_own_unremitted(
                actor_user_id=actor.user_id,
                transaction_id=transaction_id,
                entry_type=body.entry_type,
                amount=body.amount,
                covered_dates=tuple(body.covered_dates),
                note=body.note,
                reason=body.reason,
                expected_route_revision=body.expected_route_revision,
            )
        except CollectionCorrectionError as error:
            _raise_correction_error(error)
        return {"success": True, "data": _record_payload(record)}

    return router
