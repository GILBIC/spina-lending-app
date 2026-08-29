from __future__ import annotations

from datetime import date, datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from psycopg import Error as PsycopgError

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .management_employee_activity import (
    EmployeeActivityDomain,
    EmployeeActivityItem,
    EmployeeActivityPage,
    EmployeeActivityRow,
    EmployeeActivityStatus,
    EmployeeActivityTimeline,
)
from .management_employee_activity_registry import (
    EmployeeActivityDomainSpec,
    visible_employee_activity_domains,
)
from .management_employee_activity_repository import (
    EmployeeActivityDomainForbidden,
    EmployeeActivityNotFound,
    ManagementEmployeeActivityError,
    PostgresManagementEmployeeActivityRepository,
)
from .request_auth import authenticated_device_context

_MANILA = ZoneInfo("Asia/Manila")
_MAX_RANGE_DAYS = 31
_MAX_QUERY_LENGTH = 100


def management_employee_activity_repository_dependency() -> (
    PostgresManagementEmployeeActivityRepository
):
    return PostgresManagementEmployeeActivityRepository()


def _row_payload(row: EmployeeActivityRow) -> dict[str, object]:
    return {
        "employee_user_id": str(row.employee_user_id),
        "employee_name": row.employee_name,
        "function_labels": list(row.function_labels),
        "completed_count": row.completed_count,
        "in_progress_count": row.in_progress_count,
        "awaiting_review_count": row.awaiting_review_count,
        "needs_attention_count": row.needs_attention_count,
        "total_visible_count": row.total_visible_count,
        "last_activity_at": (
            row.last_activity_at.isoformat() if row.last_activity_at else None
        ),
        "last_activity_domain": (
            row.last_activity_domain.value if row.last_activity_domain else None
        ),
        "status": row.status.value,
        "status_message": row.status_message,
    }


def _item_payload(item: EmployeeActivityItem) -> dict[str, object]:
    return {
        "activity_code": item.activity_code.value,
        "domain": item.domain.value,
        "occurred_at": item.occurred_at.isoformat(),
        "business_date": item.business_date.isoformat(),
        "record_type": item.record_type,
        "record_id": str(item.record_id),
        "display_reference": item.display_reference,
        "summary": item.summary,
        "workflow_state": item.workflow_state,
        "status": item.status.value,
        "maker_name": item.maker_name,
        "checker_name": item.checker_name,
        "navigation_code": (
            item.navigation_code.value if item.navigation_code else None
        ),
    }


def _page_payload(page: EmployeeActivityPage) -> dict[str, object]:
    return {
        "date_from": page.date_from.isoformat(),
        "date_to": page.date_to.isoformat(),
        "generated_at": page.generated_at.isoformat(),
        "available_domains": [domain.value for domain in page.available_domains],
        "total_count": page.total_count,
        "rows": [_row_payload(row) for row in page.rows],
    }


def _timeline_payload(timeline: EmployeeActivityTimeline) -> dict[str, object]:
    return {
        "employee_user_id": str(timeline.employee_user_id),
        "employee_name": timeline.employee_name,
        "function_labels": list(timeline.function_labels),
        "date_from": timeline.date_from.isoformat(),
        "date_to": timeline.date_to.isoformat(),
        "generated_at": timeline.generated_at.isoformat(),
        "available_domains": [domain.value for domain in timeline.available_domains],
        "total_count": timeline.total_count,
        "items": [_item_payload(item) for item in timeline.items],
    }


def _safe_error(status_code: int, *, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def _authorize(
    *,
    authorization: str | None,
    x_device_id: str | None,
    auth: SupabaseAuthClient,
    accounts: PostgresAccountRepository,
):
    actor = authenticated_device_context(
        authorization=authorization,
        device_identifier=x_device_id,
        auth=auth,
        accounts=accounts,
    )
    if "management" not in actor.roles:
        raise _safe_error(
            403,
            code="management_role_required",
            message="Management access is required for Employee Activity.",
        )
    if "employee.activity.review" not in actor.permissions:
        raise _safe_error(
            403,
            code="employee_activity_permission_required",
            message="Employee Activity review permission is required.",
        )
    return actor


def _date_range(
    date_from: date | None,
    date_to: date | None,
) -> tuple[date, date]:
    today = datetime.now(_MANILA).date()
    start = date_from or today
    end = date_to or today
    if start > end:
        raise _safe_error(
            422,
            code="employee_activity_date_range_invalid",
            message="The start date must be on or before the end date.",
        )
    if (end - start).days >= _MAX_RANGE_DAYS:
        raise _safe_error(
            422,
            code="employee_activity_date_range_too_large",
            message="Employee Activity can be reviewed for at most 31 days.",
        )
    return start, end


def _normalized_query(query: str | None) -> str | None:
    normalized = " ".join((query or "").split())
    if not normalized:
        return None
    if len(normalized) > _MAX_QUERY_LENGTH:
        raise _safe_error(
            422,
            code="employee_activity_query_too_long",
            message="The Employee Activity search is too long.",
        )
    return normalized


def _visible_domains(
    permissions: tuple[str, ...],
) -> tuple[EmployeeActivityDomainSpec, ...]:
    return visible_employee_activity_domains(frozenset(permissions))


def _require_visible_domain(
    domain: EmployeeActivityDomain | None,
    visible_domains: tuple[EmployeeActivityDomainSpec, ...],
) -> None:
    if domain is not None and domain not in {
        visible_domain.code for visible_domain in visible_domains
    }:
        raise _safe_error(
            403,
            code="employee_activity_domain_forbidden",
            message="The requested Employee Activity domain is not permitted.",
        )


def _repository_error(error: Exception) -> HTTPException:
    if isinstance(error, EmployeeActivityNotFound):
        return _safe_error(
            404,
            code="employee_activity_not_found",
            message="The Employee account was not found.",
        )
    if isinstance(error, EmployeeActivityDomainForbidden):
        return _safe_error(
            403,
            code="employee_activity_domain_forbidden",
            message="The requested Employee Activity domain is not permitted.",
        )
    return _safe_error(
        503,
        code="management_employee_activity_unavailable",
        message="Employee Activity is temporarily unavailable.",
    )


def create_management_employee_activity_router() -> APIRouter:
    router = APIRouter(tags=["management employee activity"])

    @router.get("/api/v1/management/employee-activity")
    @router.get(
        "/api/mobile/v1/management/employee-activity",
        include_in_schema=False,
    )
    def list_employee_activity(
        auth: Annotated[SupabaseAuthClient, Depends(auth_client_dependency)],
        accounts: Annotated[
            PostgresAccountRepository,
            Depends(account_repository_dependency),
        ],
        repository: Annotated[
            PostgresManagementEmployeeActivityRepository,
            Depends(management_employee_activity_repository_dependency),
        ],
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        date_from: Annotated[date | None, Query()] = None,
        date_to: Annotated[date | None, Query()] = None,
        q: Annotated[str | None, Query(max_length=500)] = None,
        status: Annotated[EmployeeActivityStatus | None, Query()] = None,
        domain: Annotated[EmployeeActivityDomain | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict[str, object]:
        actor = _authorize(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        visible_domains = _visible_domains(actor.permissions)
        _require_visible_domain(domain, visible_domains)
        start, end = _date_range(date_from, date_to)
        query = _normalized_query(q)
        try:
            page = repository.list_employees(
                date_from=start,
                date_to=end,
                visible_domains=visible_domains,
                query=query,
                status=status,
                domain=domain,
                limit=limit,
                offset=offset,
            )
        except (ManagementEmployeeActivityError, PsycopgError) as error:
            raise _repository_error(error) from None
        return {"success": True, "data": _page_payload(page)}

    @router.get("/api/v1/management/employee-activity/{employee_user_id}")
    @router.get(
        "/api/mobile/v1/management/employee-activity/{employee_user_id}",
        include_in_schema=False,
    )
    def employee_activity_timeline(
        employee_user_id: UUID,
        auth: Annotated[SupabaseAuthClient, Depends(auth_client_dependency)],
        accounts: Annotated[
            PostgresAccountRepository,
            Depends(account_repository_dependency),
        ],
        repository: Annotated[
            PostgresManagementEmployeeActivityRepository,
            Depends(management_employee_activity_repository_dependency),
        ],
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        date_from: Annotated[date | None, Query()] = None,
        date_to: Annotated[date | None, Query()] = None,
        domain: Annotated[EmployeeActivityDomain | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict[str, object]:
        actor = _authorize(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        visible_domains = _visible_domains(actor.permissions)
        _require_visible_domain(domain, visible_domains)
        start, end = _date_range(date_from, date_to)
        try:
            timeline = repository.load_timeline(
                employee_user_id=employee_user_id,
                date_from=start,
                date_to=end,
                visible_domains=visible_domains,
                domain=domain,
                limit=limit,
                offset=offset,
            )
        except (ManagementEmployeeActivityError, PsycopgError) as error:
            raise _repository_error(error) from None
        return {"success": True, "data": _timeline_payload(timeline)}

    return router
