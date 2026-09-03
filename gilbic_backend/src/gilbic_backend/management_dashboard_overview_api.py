from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from psycopg import Error as PsycopgError

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .management_dashboard_overview_repository import (
    ManagementDashboardMetric,
    ManagementDashboardOverview,
    ManagementDashboardOverviewError,
    PostgresManagementDashboardOverviewRepository,
)
from .request_auth import authenticated_device_context


def management_dashboard_overview_repository_dependency() -> (
    PostgresManagementDashboardOverviewRepository
):
    return PostgresManagementDashboardOverviewRepository()


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _metric_payload(metric: ManagementDashboardMetric) -> dict[str, object]:
    payload: dict[str, object] = {"key": metric.key}
    if metric.count is not None:
        payload["count"] = metric.count
    if metric.amount is not None:
        payload["amount"] = _money(metric.amount)
    if metric.as_of_date is not None:
        payload["as_of_date"] = metric.as_of_date.isoformat()
    return payload


def _overview_payload(overview: ManagementDashboardOverview) -> dict[str, object]:
    return {
        "generated_at": overview.generated_at.isoformat(),
        "currency": "PHP",
        "metrics": [_metric_payload(metric) for metric in overview.metrics],
    }


def create_management_dashboard_overview_router() -> APIRouter:
    router = APIRouter(tags=["management dashboard"])

    @router.get("/api/v1/management/dashboard-overview")
    @router.get(
        "/api/mobile/v1/management/dashboard-overview",
        include_in_schema=False,
    )
    def management_dashboard_overview(
        auth: Annotated[SupabaseAuthClient, Depends(auth_client_dependency)],
        accounts: Annotated[
            PostgresAccountRepository,
            Depends(account_repository_dependency),
        ],
        overview_repository: Annotated[
            PostgresManagementDashboardOverviewRepository,
            Depends(management_dashboard_overview_repository_dependency),
        ],
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
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
                    "message": "Management access is required for the live overview.",
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
            overview = overview_repository.load_overview(
                actor_user_id=actor.user_id,
                include_remittances="remittance.receive" in permissions,
                include_renewals="renewal.manage" in permissions,
                include_accounts="account.manage" in permissions,
                include_devices="device.manage" in permissions,
                include_support="support.manage" in permissions,
            )
        except (ManagementDashboardOverviewError, PsycopgError):
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "management_overview_unavailable",
                    "message": (
                        "The live Management overview is temporarily unavailable."
                    ),
                },
            ) from None

        return {"success": True, "data": _overview_payload(overview)}

    return router
