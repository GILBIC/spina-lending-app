from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .collection_void_repository import (
    CollectionVoidCandidate,
    CollectionVoidConflict,
    CollectionVoidError,
    CollectionVoidInvalid,
    CollectionVoidLocked,
    CollectionVoidNotFound,
    CollectionVoidRecord,
    PostgresCollectionVoidRepository,
)
from .request_auth import authenticated_device_context


class CollectionVoidBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=3, max_length=500)


def collection_void_repository_dependency() -> PostgresCollectionVoidRepository:
    return PostgresCollectionVoidRepository()


def _candidate_payload(record: CollectionVoidCandidate) -> dict[str, object]:
    return {
        "transaction_id": str(record.transaction_id),
        "receipt_number": record.receipt_number,
        "client_id": str(record.client_id),
        "client_code": record.client_code,
        "client_name": record.client_name,
        "loan_id": str(record.loan_id),
        "loan_type": record.loan_type,
        "collector_name": record.collector_name,
        "collection_date": record.collection_date.isoformat(),
        "entry_type": record.entry_type,
        "amount": format(record.amount, "f"),
        "covered_dates": [value.isoformat() for value in record.covered_dates],
        "previous_balance": format(record.previous_balance, "f"),
        "official_balance": format(record.official_balance, "f"),
        "is_locked": record.is_locked,
        "is_voided": record.is_voided,
    }


def _void_payload(record: CollectionVoidRecord) -> dict[str, object]:
    return {
        "transaction_id": str(record.transaction_id),
        "receipt_number": record.receipt_number,
        "client_id": str(record.client_id),
        "client_code": record.client_code,
        "client_name": record.client_name,
        "loan_id": str(record.loan_id),
        "collector_user_id": str(record.collector_user_id),
        "collector_name": record.collector_name,
        "collection_date": record.collection_date.isoformat(),
        "entry_type": record.entry_type,
        "amount": format(record.amount, "f"),
        "covered_dates": [value.isoformat() for value in record.covered_dates],
        "restored_balance": format(record.restored_balance, "f"),
        "state_version": record.state_version,
        "reason": record.reason,
        "voided_at": record.voided_at.isoformat(),
    }


def _raise_void_error(error: CollectionVoidError) -> None:
    if isinstance(error, CollectionVoidNotFound):
        status_code = 404
    elif isinstance(error, CollectionVoidLocked):
        status_code = 409
    elif isinstance(error, CollectionVoidConflict):
        status_code = 409
    elif isinstance(error, CollectionVoidInvalid):
        status_code = 422
    else:
        status_code = 409
    raise HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    ) from error


def _management_actor(
    *,
    authorization: str | None,
    device_identifier: str | None,
    auth: SupabaseAuthClient,
    accounts: PostgresAccountRepository,
):
    return authenticated_device_context(
        authorization=authorization,
        device_identifier=device_identifier,
        auth=auth,
        accounts=accounts,
        permission="collection.void.unremitted",
        permission_error="Management collection-void permission is required.",
    )


def create_collection_void_router() -> APIRouter:
    router = APIRouter(tags=["management collection voids"])

    @router.get("/api/v1/management/collections/by-receipt/{receipt_number}")
    @router.get(
        "/api/mobile/v1/management/collections/by-receipt/{receipt_number}",
        include_in_schema=False,
    )
    def find_collection_by_receipt(
        receipt_number: str,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        voids: PostgresCollectionVoidRepository = Depends(
            collection_void_repository_dependency
        ),
    ) -> dict[str, object]:
        _management_actor(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = voids.find_by_receipt(receipt_number=receipt_number)
        except CollectionVoidError as error:
            _raise_void_error(error)
        return {"success": True, "data": _candidate_payload(record)}

    @router.post("/api/v1/management/collections/{transaction_id}/void")
    @router.post(
        "/api/mobile/v1/management/collections/{transaction_id}/void",
        include_in_schema=False,
    )
    def void_collection(
        transaction_id: UUID,
        body: CollectionVoidBody,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        voids: PostgresCollectionVoidRepository = Depends(
            collection_void_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _management_actor(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = voids.void_unremitted(
                actor_user_id=actor.user_id,
                transaction_id=transaction_id,
                reason=body.reason,
            )
        except CollectionVoidError as error:
            _raise_void_error(error)
        return {"success": True, "data": _void_payload(record)}

    return router
