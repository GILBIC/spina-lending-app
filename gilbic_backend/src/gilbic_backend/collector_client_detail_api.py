from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .collector_client_detail_repository import (
    CollectorClientDetailRecord,
    PostgresCollectorClientDetailRepository,
)
from .request_auth import authenticated_device_context


def collector_client_detail_repository_dependency() -> PostgresCollectorClientDetailRepository:
    return PostgresCollectorClientDetailRepository()


def _location_payload(location: CollectorClientDetailRecord) -> dict[str, object]:
    verified = location.collection_location_status == "verified"
    return {
        "client_id": str(location.client_id),
        "collection_location_status": "verified" if verified else "not_verified",
        "display_address": location.display_address if verified else None,
        "landmark": location.landmark if verified else None,
        "photo_url": location.photo_url if verified else None,
        "verified_at": (
            location.verified_at.isoformat()
            if verified and location.verified_at is not None
            else None
        ),
    }


def create_collector_client_detail_router() -> APIRouter:
    router = APIRouter(tags=["collector client details"])

    @router.get("/api/v1/collector/clients/{client_id}/collection-location")
    @router.get(
        "/api/mobile/v1/collector/clients/{client_id}/collection-location",
        include_in_schema=False,
    )
    def view_collection_location(
        client_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        details: PostgresCollectorClientDetailRepository = Depends(
            collector_client_detail_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="route.view",
            permission_error="Collector route permission is required.",
        )
        if "collector" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail="Collector route permission is required.",
            )
        location = details.get_collection_location(
            collector_user_id=actor.user_id,
            client_id=client_id,
        )
        if location is None:
            raise HTTPException(
                status_code=404,
                detail="Collection location is not available for this route.",
            )
        return {"success": True, "data": _location_payload(location)}

    return router
