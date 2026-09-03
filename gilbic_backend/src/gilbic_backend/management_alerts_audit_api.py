from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from psycopg import Error as PsycopgError

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .management_alerts_audit_repository import (
    ManagementAlert,
    ManagementAlertsAuditError,
    ManagementAlertsAuditSnapshot,
    ManagementAuditEvent,
    PostgresManagementAlertsAuditRepository,
)
from .request_auth import authenticated_device_context


def management_alerts_audit_repository_dependency() -> (
    PostgresManagementAlertsAuditRepository
):
    return PostgresManagementAlertsAuditRepository()


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _alert_payload(alert: ManagementAlert) -> dict[str, object]:
    payload: dict[str, object] = {
        "code": alert.code,
        "domain": alert.domain,
        "title": alert.title,
        "count": alert.count,
        "severity": alert.severity,
        "navigation_code": alert.navigation_code,
    }
    if alert.amount is not None:
        payload["amount"] = _money(alert.amount)
    return payload


def _event_payload(event: ManagementAuditEvent) -> dict[str, object | None]:
    return {
        "event_key": event.event_key,
        "domain": event.domain,
        "action_code": event.action_code,
        "title": event.title,
        "severity": event.severity,
        "navigation_code": event.navigation_code,
        "occurred_at": event.occurred_at.isoformat(),
        "business_date": event.business_date.isoformat(),
        "record_id": str(event.record_id),
        "reference": event.reference,
        "current_state": event.current_state,
        "actor_name": event.actor_name,
        "checker_name": event.checker_name,
        "source_type": event.source_type,
        "source_label": event.source_label,
        "reason": event.reason,
    }


def _snapshot_payload(snapshot: ManagementAlertsAuditSnapshot) -> dict[str, object]:
    return {
        "generated_at": snapshot.generated_at.isoformat(),
        "window_days": snapshot.window_days,
        "limit": snapshot.limit,
        "currency": "PHP",
        "visible_domains": list(snapshot.visible_domains),
        "alerts": [_alert_payload(alert) for alert in snapshot.alerts],
        "events": [_event_payload(event) for event in snapshot.events],
        "event_total_count": snapshot.event_total_count,
        "notice": (
            "Read-only visibility. Complete approvals, corrections, and postings "
            "in their owning Management workflows."
        ),
    }


def create_management_alerts_audit_router() -> APIRouter:
    router = APIRouter(tags=["management alerts and audit"])

    @router.get("/api/v1/management/alerts-audit")
    @router.get(
        "/api/mobile/v1/management/alerts-audit",
        include_in_schema=False,
    )
    def management_alerts_audit(
        auth: Annotated[SupabaseAuthClient, Depends(auth_client_dependency)],
        accounts: Annotated[
            PostgresAccountRepository,
            Depends(account_repository_dependency),
        ],
        repository: Annotated[
            PostgresManagementAlertsAuditRepository,
            Depends(management_alerts_audit_repository_dependency),
        ],
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        window_days: int = Query(default=30, ge=1, le=90),
        limit: int = Query(default=100, ge=1, le=200),
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
                    "message": "Management access is required.",
                },
            )
        if "management.dashboard.view" not in actor.permissions:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "management_dashboard_permission_required",
                    "message": "Management dashboard permission is required.",
                },
            )

        permissions = actor.permissions
        try:
            snapshot = repository.load_snapshot(
                actor_user_id=actor.user_id,
                include_accounts="account.manage" in permissions,
                include_devices="device.manage" in permissions,
                include_renewals="renewal.manage" in permissions,
                include_support="support.manage" in permissions,
                include_remittances="remittance.view" in permissions,
                include_financial="accounting.view" in permissions,
                window_days=window_days,
                limit=limit,
            )
        except (ManagementAlertsAuditError, PsycopgError):
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "management_alerts_audit_unavailable",
                    "message": (
                        "Management alerts and audit activity are temporarily "
                        "unavailable."
                    ),
                },
            ) from None

        return {"success": True, "data": _snapshot_payload(snapshot)}

    return router
