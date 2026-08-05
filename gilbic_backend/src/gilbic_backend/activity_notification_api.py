from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from .account_repository import PostgresAccountRepository
from .activity_notification_repository import (
    ActivityNotificationError,
    ActivityNotificationRecord,
    PostgresActivityNotificationRepository,
)
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .request_auth import authenticated_device_context


def activity_notification_repository_dependency() -> PostgresActivityNotificationRepository:
    return PostgresActivityNotificationRepository()


def _payload(record: ActivityNotificationRecord) -> dict[str, object]:
    return {
        "notification_id": str(record.notification_id),
        "notification_type": record.notification_type,
        "recipient_user_id": str(record.recipient_user_id),
        "sender_user_id": str(record.sender_user_id),
        "sender_name": record.sender_name,
        "title": record.title,
        "message": record.message,
        "transaction_id": str(record.transaction_id) if record.transaction_id else None,
        "remittance_id": str(record.remittance_id) if record.remittance_id else None,
        "client_id": str(record.client_id) if record.client_id else None,
        "metadata": record.metadata,
        "is_read": record.is_read,
        "created_at": record.created_at.isoformat(),
        "read_at": record.read_at.isoformat() if record.read_at else None,
    }


def create_activity_notification_router() -> APIRouter:
    router = APIRouter(tags=["activity notifications"])

    @router.get("/api/v1/activity-notifications")
    @router.get(
        "/api/mobile/v1/activity-notifications",
        include_in_schema=False,
    )
    def list_notifications(
        limit: int = Query(default=100, ge=1, le=200),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        notifications: PostgresActivityNotificationRepository = Depends(
            activity_notification_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        records = notifications.list_for_user(
            recipient_user_id=actor.user_id,
            limit=limit,
        )
        return {
            "success": True,
            "data": [_payload(record) for record in records],
        }

    @router.post("/api/v1/activity-notifications/{notification_id}/read")
    @router.post(
        "/api/mobile/v1/activity-notifications/{notification_id}/read",
        include_in_schema=False,
    )
    def mark_read(
        notification_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        notifications: PostgresActivityNotificationRepository = Depends(
            activity_notification_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = notifications.mark_read(
                notification_id=notification_id,
                recipient_user_id=actor.user_id,
            )
        except ActivityNotificationError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": error.code, "message": str(error)},
            ) from error
        return {"success": True, "data": _payload(record)}

    return router
