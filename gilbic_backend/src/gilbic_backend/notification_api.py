from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .notification_repository import (
    NotificationError,
    NotificationForbidden,
    NotificationNotFound,
    PostgresNotificationRepository,
    RemittanceNotificationRecord,
)
from .remittance_repository import (
    PostgresRemittanceRepository,
    RemittanceAlreadyReceived,
    RemittanceError,
    RemittanceNotFound,
    RemittanceRecipientInvalid,
)
from .request_auth import authenticated_device_context


def notification_repository_dependency() -> PostgresNotificationRepository:
    return PostgresNotificationRepository()


def notification_remittance_repository_dependency() -> PostgresRemittanceRepository:
    return PostgresRemittanceRepository()


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _notification_payload(
    notification: RemittanceNotificationRecord,
) -> dict[str, object]:
    photo_url = (
        f"/api/mobile/v1/remittances/{notification.remittance_id}/handover-photo"
        if notification.has_handover_photo
        else None
    )
    return {
        "notification_id": str(notification.notification_id),
        "notification_type": "remittance_acceptance",
        "recipient_user_id": str(notification.recipient_user_id),
        "sender_user_id": str(notification.sender_user_id),
        "remittance_id": str(notification.remittance_id),
        "remittance_number": notification.remittance_number,
        "title": notification.title,
        "message": notification.message,
        "action_code": "accept_remittance",
        "status": notification.status,
        "is_pending": notification.is_pending,
        "collector_name": notification.collector_name,
        "total_amount": _money(notification.total_amount),
        "client_count": notification.client_count,
        "transaction_count": notification.transaction_count,
        "collection_date": notification.collection_date.isoformat(),
        "created_at": notification.created_at.isoformat(),
        "read_at": notification.read_at.isoformat() if notification.read_at else None,
        "accepted_at": (
            notification.accepted_at.isoformat()
            if notification.accepted_at
            else None
        ),
        "has_handover_photo": notification.has_handover_photo,
        "handover_photo_version": notification.handover_photo_version,
        "handover_photo_content_type": notification.handover_photo_content_type,
        "handover_photo_uploaded_at": (
            notification.handover_photo_uploaded_at.isoformat()
            if notification.handover_photo_uploaded_at
            else None
        ),
        "handover_photo_url": photo_url,
        "custody_message": (
            "Money is now under your custody."
            if not notification.is_pending
            else "Accept only after you physically receive the cash."
        ),
    }


def _raise_notification_error(error: NotificationError) -> None:
    status = 403 if isinstance(error, NotificationForbidden) else 404
    raise HTTPException(
        status_code=status,
        detail={"code": error.code, "message": str(error)},
    ) from error


def _raise_remittance_error(error: RemittanceError) -> None:
    if isinstance(error, RemittanceNotFound):
        status = 404
    elif isinstance(error, RemittanceRecipientInvalid):
        status = 403
    elif isinstance(error, RemittanceAlreadyReceived):
        status = 409
    else:
        status = 409
    raise HTTPException(
        status_code=status,
        detail={"code": error.code, "message": str(error)},
    ) from error


def create_notification_router() -> APIRouter:
    router = APIRouter(tags=["notifications"])

    @router.get("/api/v1/notifications")
    @router.get("/api/mobile/v1/notifications", include_in_schema=False)
    def list_notifications(
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        notifications: PostgresNotificationRepository = Depends(
            notification_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="remittance.view",
            permission_error="Notification view permission is required.",
        )
        records = notifications.list_for_user(recipient_user_id=actor.user_id)
        return {
            "success": True,
            "data": [_notification_payload(record) for record in records],
        }

    @router.post("/api/v1/notifications/{notification_id}/read")
    @router.post(
        "/api/mobile/v1/notifications/{notification_id}/read",
        include_in_schema=False,
    )
    def mark_read(
        notification_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        notifications: PostgresNotificationRepository = Depends(
            notification_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="remittance.view",
            permission_error="Notification view permission is required.",
        )
        try:
            record = notifications.mark_read(
                notification_id=notification_id,
                recipient_user_id=actor.user_id,
            )
        except NotificationError as error:
            _raise_notification_error(error)
        return {"success": True, "data": _notification_payload(record)}

    @router.post(
        "/api/v1/notifications/{notification_id}/accept-remittance"
    )
    @router.post(
        "/api/mobile/v1/notifications/{notification_id}/accept-remittance",
        include_in_schema=False,
    )
    def accept_remittance(
        notification_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        notifications: PostgresNotificationRepository = Depends(
            notification_repository_dependency
        ),
        remittances: PostgresRemittanceRepository = Depends(
            notification_remittance_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="remittance.receive",
            permission_error="Remittance receiving permission is required.",
        )
        try:
            notification = notifications.get_for_user(
                notification_id=notification_id,
                recipient_user_id=actor.user_id,
            )
            remittance = remittances.confirm_received(
                remittance_id=notification.remittance_id,
                recipient_user_id=actor.user_id,
            )
            updated = notifications.get_for_user(
                notification_id=notification_id,
                recipient_user_id=actor.user_id,
            )
        except NotificationError as error:
            _raise_notification_error(error)
        except RemittanceError as error:
            _raise_remittance_error(error)
        return {
            "success": True,
            "message": "Remittance accepted. The money is now under your custody.",
            "data": {
                "notification": _notification_payload(updated),
                "remittance_id": str(remittance.remittance_id),
                "remittance_number": remittance.remittance_number,
                "status": remittance.status,
                "received_at": (
                    remittance.received_at.isoformat()
                    if remittance.received_at
                    else None
                ),
                "custody_user_id": str(actor.user_id),
                "custody_message": "Money is now under your custody.",
            },
        }

    return router
