from __future__ import annotations

from spina_mobile_collections.service import CollectionSubmissionService

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .database import connect_database
from .request_auth import authenticated_device_context
from .seven_by_seven_multi_receipt_posting import (
    MultiReceiptSevenBySevenCollectionPostingBridge,
)

from fastapi import Depends, Header, HTTPException
from spina_mobile_collections.contracts import ActorContext
from spina_mobile_collections.postgres import PostgresCollectionExecutor
from spina_mobile_collections.router import create_collection_router


def collection_actor_dependency(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    auth: SupabaseAuthClient = Depends(auth_client_dependency),
    accounts: PostgresAccountRepository = Depends(account_repository_dependency),
) -> ActorContext:
    context = authenticated_device_context(
        authorization=authorization,
        device_identifier=x_device_id,
        auth=auth,
        accounts=accounts,
        permission="collection.create",
        permission_error="Collection permission is required.",
    )
    if context.registered_device_id is None:
        raise HTTPException(
            status_code=403,
            detail="This device is not registered. Sign in again on this device.",
        )
    return ActorContext(
        account_id=str(context.user_id),
        device_id=(x_device_id or "").strip(),
        registered_device_id=str(context.registered_device_id),
        permissions=frozenset(context.permissions),
    )


def collection_service_dependency() -> CollectionSubmissionService:
    executor = PostgresCollectionExecutor(
        connection_factory=connect_database,
        posting_bridge=MultiReceiptSevenBySevenCollectionPostingBridge(),
    )
    return CollectionSubmissionService(executor)


def create_collection_api_router():
    return create_collection_router(
        get_actor=collection_actor_dependency,
        get_service=collection_service_dependency,
    )
