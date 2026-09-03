from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection
from .management_employee_activity import (
    EmployeeActivityCode,
    EmployeeActivityDomain,
    EmployeeActivityItem,
    EmployeeActivityNavigationCode,
    EmployeeActivityPage,
    EmployeeActivityRow,
    EmployeeActivityStatus,
    EmployeeActivityTimeline,
)
from .management_employee_activity_registry import EmployeeActivityDomainSpec


class ManagementEmployeeActivityError(RuntimeError):
    code = "management_employee_activity_unavailable"


class EmployeeActivityNotFound(ManagementEmployeeActivityError):
    code = "employee_activity_not_found"


class EmployeeActivityDomainForbidden(ManagementEmployeeActivityError):
    code = "employee_activity_domain_forbidden"


_EVENTS_CTE = """
employee_users as (
    select
        user_account.id,
        user_account.username,
        user_account.full_name
    from core.users user_account
    join core.user_roles user_role
      on user_role.user_id = user_account.id
    join core.roles role
      on role.id = user_role.role_id
     and role.code = 'employee'
    where user_account.status = 'active'
    group by user_account.id
),
employee_events as (
    select
        journal.created_by_user_id as employee_user_id,
        'accounting.journal.prepared'::text as activity_code,
        'accounting'::text as domain,
        journal.created_at as occurred_at,
        journal.posting_date as business_date,
        'journal_entry'::text as record_type,
        journal.id as record_id,
        coalesce(
            journal.entry_number,
            journal.source_reference,
            'Journal draft'
        )::text as display_reference,
        'Prepared journal entry'::text as summary,
        journal.status::text as workflow_state,
        case
            when journal.status = 'draft' then 'in_progress'
            else 'completed'
        end::text as activity_status,
        maker.full_name::text as maker_name,
        checker.full_name::text as checker_name,
        'management.general_journals'::text as navigation_code
    from accounting.journal_entries journal
    join employee_users employee
      on employee.id = journal.created_by_user_id
    join core.users maker
      on maker.id = journal.created_by_user_id
    left join core.users checker
      on checker.id = journal.posted_by_user_id
    where %s
      and journal.posting_date between %s and %s

    union all

    select
        audit.actor_user_id as employee_user_id,
        audit.action::text as activity_code,
        'crm_support'::text as domain,
        audit.created_at as occurred_at,
        (audit.created_at at time zone 'Asia/Manila')::date as business_date,
        'client_support_request'::text as record_type,
        request.id as record_id,
        'Support request'::text as display_reference,
        case
            when audit.action = 'support.resolved'
                then 'Resolved support request'
            else 'Answered support request'
        end::text as summary,
        request.status::text as workflow_state,
        'completed'::text as activity_status,
        employee.full_name::text as maker_name,
        null::text as checker_name,
        'management.support_requests'::text as navigation_code
    from core.audit_logs audit
    join employee_users employee
      on employee.id = audit.actor_user_id
    join lending.client_support_requests request
      on request.id = audit.target_id
     and audit.target_type = 'client_support_request'
    where %s
      and audit.action in ('support.answered', 'support.resolved')
      and (audit.created_at at time zone 'Asia/Manila')::date
          between %s and %s

    union all

    select
        audit.actor_user_id as employee_user_id,
        'remittance.submitted'::text as activity_code,
        'remittance_operations'::text as domain,
        audit.created_at as occurred_at,
        remittance.collection_date as business_date,
        'collection_remittance'::text as record_type,
        remittance.id as record_id,
        remittance.remittance_number::text as display_reference,
        'Submitted remittance'::text as summary,
        case
            when rejection.remittance_id is not null then 'rejected'
            else remittance.status
        end::text as workflow_state,
        case
            when rejection.remittance_id is not null then 'needs_attention'
            when remittance.status = 'received' then 'completed'
            else 'awaiting_review'
        end::text as activity_status,
        employee.full_name::text as maker_name,
        checker.full_name::text as checker_name,
        'management.remittance_review'::text as navigation_code
    from core.audit_logs audit
    join employee_users employee
      on employee.id = audit.actor_user_id
    join lending.collection_remittances remittance
      on remittance.id = audit.target_id
     and audit.target_type = 'collection_remittance'
    left join lending.collection_remittance_rejections rejection
      on rejection.remittance_id = remittance.id
    left join core.users checker
      on checker.id = coalesce(
          rejection.rejected_by_user_id,
          remittance.received_by_user_id
      )
    where %s
      and audit.action = 'remittance.submitted'
      and remittance.collection_date between %s and %s
)
"""


_LIST_SQL = (
    "with "
    + _EVENTS_CTE
    + """,
filtered_events as (
    select *
    from employee_events event
    where (%s::text is null or event.domain = %s::text)
),
employee_rollup as (
    select
        employee.id as employee_user_id,
        employee.full_name as employee_name,
        array[]::text[] as function_labels,
        count(event.record_id) filter (
            where event.activity_status = 'completed'
        )::integer as completed_count,
        count(event.record_id) filter (
            where event.activity_status = 'in_progress'
        )::integer as in_progress_count,
        count(event.record_id) filter (
            where event.activity_status = 'awaiting_review'
        )::integer as awaiting_review_count,
        count(event.record_id) filter (
            where event.activity_status = 'needs_attention'
        )::integer as needs_attention_count,
        count(event.record_id)::integer as total_visible_count,
        max(event.occurred_at) as last_activity_at,
        (array_agg(
            event.domain
            order by event.occurred_at desc, event.record_id desc
        ) filter (where event.record_id is not null))[1]
            as last_activity_domain
    from employee_users employee
    left join filtered_events event
      on event.employee_user_id = employee.id
    where (
        %s::text is null
        or lower(employee.full_name) like %s::text
        or lower(employee.username) like %s::text
    )
    group by employee.id, employee.full_name
),
employee_rows as (
    select
        rollup.*,
        case
            when needs_attention_count > 0 then 'needs_attention'
            when awaiting_review_count > 0 then 'awaiting_review'
            when in_progress_count > 0 then 'in_progress'
            when completed_count > 0 then 'completed'
            else 'no_activity'
        end::text as status
    from employee_rollup rollup
)
select
    employee_rows.*,
    statement_timestamp() as generated_at,
    count(*) over ()::integer as total_count
from employee_rows
where (%s::text is null or status = %s::text)
order by employee_name, employee_user_id
limit %s offset %s
"""
)


_TIMELINE_SQL = (
    "with "
    + _EVENTS_CTE
    + """,
filtered_events as (
    select *
    from employee_events event
    where event.employee_user_id = %s
      and (%s::text is null or event.domain = %s::text)
),
paged_events as (
    select *
    from filtered_events
    order by occurred_at desc, record_id desc
    limit %s offset %s
)
select
    employee.id as employee_user_id,
    employee.full_name as employee_name,
    array[]::text[] as function_labels,
    event.activity_code,
    event.domain,
    event.occurred_at,
    event.business_date,
    event.record_type,
    event.record_id,
    event.display_reference,
    event.summary,
    event.workflow_state,
    event.activity_status as status,
    event.maker_name,
    event.checker_name,
    event.navigation_code,
    statement_timestamp() as generated_at,
    (select count(*)::integer from filtered_events) as total_count
from employee_users employee
left join paged_events event on true
where employee.id = %s
order by event.occurred_at desc nulls last, event.record_id desc nulls last
"""
)


def _visible_codes(
    domains: tuple[EmployeeActivityDomainSpec, ...],
) -> tuple[EmployeeActivityDomain, ...]:
    return tuple(domain.code for domain in domains)


def _domain_enabled(
    domains: tuple[EmployeeActivityDomainSpec, ...],
    domain: EmployeeActivityDomain,
) -> bool:
    return domain in _visible_codes(domains)


def _validate_requested_domain(
    domain: EmployeeActivityDomain | None,
    visible_domains: tuple[EmployeeActivityDomainSpec, ...],
) -> None:
    if domain is not None and not _domain_enabled(visible_domains, domain):
        raise EmployeeActivityDomainForbidden(
            "The requested Employee Activity domain is not permitted."
        )


def _required_count(row, key: str) -> int:
    value = row[key]
    if type(value) is not int or value < 0:
        raise ManagementEmployeeActivityError("The Employee Activity data is invalid.")
    return value


def _required_text(row, key: str, *, maximum: int) -> str:
    value = row[key]
    if not isinstance(value, str):
        raise ManagementEmployeeActivityError("The Employee Activity data is invalid.")
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > maximum:
        raise ManagementEmployeeActivityError("The Employee Activity data is invalid.")
    return normalized


def _optional_text(row, key: str, *, maximum: int) -> str | None:
    if row[key] is None:
        return None
    return _required_text(row, key, maximum=maximum)


def _required_uuid(row, key: str) -> UUID:
    value = row[key]
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise ManagementEmployeeActivityError(
            "The Employee Activity data is invalid."
        ) from error


def _required_datetime(row, key: str) -> datetime:
    value = row[key]
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ManagementEmployeeActivityError("The Employee Activity data is invalid.")
    try:
        offset = value.utcoffset()
    except (OverflowError, ValueError):
        offset = None
    if offset is None:
        raise ManagementEmployeeActivityError("The Employee Activity data is invalid.")
    return value.astimezone(timezone.utc)


def _optional_datetime(row, key: str) -> datetime | None:
    if row[key] is None:
        return None
    return _required_datetime(row, key)


def _required_date(row, key: str) -> date:
    value = row[key]
    if type(value) is not date:
        raise ManagementEmployeeActivityError("The Employee Activity data is invalid.")
    return value


def _function_labels(row) -> tuple[str, ...]:
    value = row["function_labels"]
    if not isinstance(value, (list, tuple)):
        raise ManagementEmployeeActivityError("The Employee Activity data is invalid.")
    labels: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ManagementEmployeeActivityError(
                "The Employee Activity data is invalid."
            )
        normalized = " ".join(item.split())
        if not normalized or len(normalized) > 80:
            raise ManagementEmployeeActivityError(
                "The Employee Activity data is invalid."
            )
        labels.append(normalized)
    return tuple(labels)


def _enum_value(enum_type, value, *, optional: bool = False):
    if value is None and optional:
        return None
    try:
        return enum_type(value)
    except (TypeError, ValueError) as error:
        raise ManagementEmployeeActivityError(
            "The Employee Activity data is invalid."
        ) from error


def _derived_status(
    *,
    completed: int,
    in_progress: int,
    awaiting_review: int,
    needs_attention: int,
) -> EmployeeActivityStatus:
    if needs_attention:
        return EmployeeActivityStatus.NEEDS_ATTENTION
    if awaiting_review:
        return EmployeeActivityStatus.AWAITING_REVIEW
    if in_progress:
        return EmployeeActivityStatus.IN_PROGRESS
    if completed:
        return EmployeeActivityStatus.COMPLETED
    return EmployeeActivityStatus.NO_ACTIVITY


def _status_message(
    status: EmployeeActivityStatus,
    *,
    completed: int,
    in_progress: int,
    awaiting_review: int,
    needs_attention: int,
) -> str:
    if status is EmployeeActivityStatus.NEEDS_ATTENTION:
        return f"{needs_attention} item{'s' if needs_attention != 1 else ''} need attention."
    if status is EmployeeActivityStatus.AWAITING_REVIEW:
        return f"{awaiting_review} item{'s' if awaiting_review != 1 else ''} await Management review."
    if status is EmployeeActivityStatus.IN_PROGRESS:
        return (
            f"{in_progress} item{'s' if in_progress != 1 else ''} remain in progress."
        )
    if status is EmployeeActivityStatus.COMPLETED:
        return f"{completed} visible item{'s' if completed != 1 else ''} completed."
    return "No permitted activity in this range."


def _row_from_record(row) -> EmployeeActivityRow:
    completed = _required_count(row, "completed_count")
    in_progress = _required_count(row, "in_progress_count")
    awaiting_review = _required_count(row, "awaiting_review_count")
    needs_attention = _required_count(row, "needs_attention_count")
    total_visible = _required_count(row, "total_visible_count")
    if total_visible != completed + in_progress + awaiting_review + needs_attention:
        raise ManagementEmployeeActivityError("The Employee Activity data is invalid.")
    status = _enum_value(EmployeeActivityStatus, row["status"])
    derived = _derived_status(
        completed=completed,
        in_progress=in_progress,
        awaiting_review=awaiting_review,
        needs_attention=needs_attention,
    )
    if status is not derived:
        raise ManagementEmployeeActivityError("The Employee Activity data is invalid.")
    last_activity_at = _optional_datetime(row, "last_activity_at")
    last_activity_domain = _enum_value(
        EmployeeActivityDomain,
        row["last_activity_domain"],
        optional=True,
    )
    if (last_activity_at is None) != (last_activity_domain is None):
        raise ManagementEmployeeActivityError("The Employee Activity data is invalid.")
    return EmployeeActivityRow(
        employee_user_id=_required_uuid(row, "employee_user_id"),
        employee_name=_required_text(row, "employee_name", maximum=200),
        function_labels=_function_labels(row),
        completed_count=completed,
        in_progress_count=in_progress,
        awaiting_review_count=awaiting_review,
        needs_attention_count=needs_attention,
        total_visible_count=total_visible,
        last_activity_at=last_activity_at,
        last_activity_domain=last_activity_domain,
        status=status,
        status_message=_status_message(
            status,
            completed=completed,
            in_progress=in_progress,
            awaiting_review=awaiting_review,
            needs_attention=needs_attention,
        ),
    )


def _item_from_record(row) -> EmployeeActivityItem:
    return EmployeeActivityItem(
        employee_user_id=_required_uuid(row, "employee_user_id"),
        activity_code=_enum_value(EmployeeActivityCode, row["activity_code"]),
        domain=_enum_value(EmployeeActivityDomain, row["domain"]),
        occurred_at=_required_datetime(row, "occurred_at"),
        business_date=_required_date(row, "business_date"),
        record_type=_required_text(row, "record_type", maximum=80),
        record_id=_required_uuid(row, "record_id"),
        display_reference=_required_text(row, "display_reference", maximum=200),
        summary=_required_text(row, "summary", maximum=500),
        workflow_state=_required_text(row, "workflow_state", maximum=80),
        status=_enum_value(EmployeeActivityStatus, row["status"]),
        maker_name=_optional_text(row, "maker_name", maximum=200),
        checker_name=_optional_text(row, "checker_name", maximum=200),
        navigation_code=_enum_value(
            EmployeeActivityNavigationCode,
            row["navigation_code"],
            optional=True,
        ),
    )


class PostgresManagementEmployeeActivityRepository:
    def list_employees(
        self,
        *,
        date_from: date,
        date_to: date,
        visible_domains: tuple[EmployeeActivityDomainSpec, ...],
        query: str | None,
        status: EmployeeActivityStatus | None,
        domain: EmployeeActivityDomain | None,
        limit: int,
        offset: int,
    ) -> EmployeeActivityPage:
        _validate_requested_domain(domain, visible_domains)
        search_pattern = f"%{query.strip().lower()}%" if query else None
        domain_value = domain.value if domain is not None else None
        status_value = status.value if status is not None else None
        parameters = (
            _domain_enabled(visible_domains, EmployeeActivityDomain.ACCOUNTING),
            date_from,
            date_to,
            _domain_enabled(visible_domains, EmployeeActivityDomain.CRM_SUPPORT),
            date_from,
            date_to,
            _domain_enabled(
                visible_domains,
                EmployeeActivityDomain.REMITTANCE_OPERATIONS,
            ),
            date_from,
            date_to,
            domain_value,
            domain_value,
            search_pattern,
            search_pattern,
            search_pattern,
            status_value,
            status_value,
            limit,
            offset,
        )
        with (
            open_connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            cursor.execute(_LIST_SQL, parameters)
            records = cursor.fetchall()
        rows = tuple(_row_from_record(record) for record in records)
        if records:
            generated_at = _required_datetime(records[0], "generated_at")
            total_count = _required_count(records[0], "total_count")
            if any(
                _required_count(record, "total_count") != total_count
                or _required_datetime(record, "generated_at") != generated_at
                for record in records[1:]
            ):
                raise ManagementEmployeeActivityError(
                    "The Employee Activity data is invalid."
                )
        else:
            generated_at = datetime.now(timezone.utc)
            total_count = 0
        return EmployeeActivityPage(
            date_from=date_from,
            date_to=date_to,
            generated_at=generated_at,
            available_domains=_visible_codes(visible_domains),
            rows=rows,
            total_count=total_count,
        )

    def load_timeline(
        self,
        *,
        employee_user_id: UUID,
        date_from: date,
        date_to: date,
        visible_domains: tuple[EmployeeActivityDomainSpec, ...],
        domain: EmployeeActivityDomain | None,
        limit: int,
        offset: int,
    ) -> EmployeeActivityTimeline:
        _validate_requested_domain(domain, visible_domains)
        domain_value = domain.value if domain is not None else None
        parameters = (
            _domain_enabled(visible_domains, EmployeeActivityDomain.ACCOUNTING),
            date_from,
            date_to,
            _domain_enabled(visible_domains, EmployeeActivityDomain.CRM_SUPPORT),
            date_from,
            date_to,
            _domain_enabled(
                visible_domains,
                EmployeeActivityDomain.REMITTANCE_OPERATIONS,
            ),
            date_from,
            date_to,
            employee_user_id,
            domain_value,
            domain_value,
            limit,
            offset,
            employee_user_id,
        )
        with (
            open_connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            cursor.execute(_TIMELINE_SQL, parameters)
            records = cursor.fetchall()
        if not records:
            raise EmployeeActivityNotFound("The Employee account was not found.")
        first = records[0]
        generated_at = _required_datetime(first, "generated_at")
        total_count = _required_count(first, "total_count")
        employee_id = _required_uuid(first, "employee_user_id")
        employee_name = _required_text(first, "employee_name", maximum=200)
        function_labels = _function_labels(first)
        items = tuple(
            _item_from_record(record)
            for record in records
            if record["activity_code"] is not None
        )
        if len(items) > total_count:
            raise ManagementEmployeeActivityError(
                "The Employee Activity data is invalid."
            )
        if any(
            _required_uuid(record, "employee_user_id") != employee_id
            or _required_text(record, "employee_name", maximum=200) != employee_name
            or _function_labels(record) != function_labels
            or _required_datetime(record, "generated_at") != generated_at
            or _required_count(record, "total_count") != total_count
            for record in records[1:]
        ):
            raise ManagementEmployeeActivityError(
                "The Employee Activity data is invalid."
            )
        return EmployeeActivityTimeline(
            employee_user_id=employee_id,
            employee_name=employee_name,
            function_labels=function_labels,
            date_from=date_from,
            date_to=date_to,
            generated_at=generated_at,
            available_domains=_visible_codes(visible_domains),
            items=items,
            total_count=total_count,
        )
