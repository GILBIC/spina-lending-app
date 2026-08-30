from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection

PROTECTED_FINANCIAL_SOURCE_LABELS = {
    "collection": "Collection",
    "ecl_allowance": "ECL allowance",
    "ecl_post_writeoff_recovery": "ECL post-write-off recovery",
    "ecl_writeoff": "ECL write-off",
    "initial_capital_funding": "Initial capital funding",
    "loan_disbursement": "Loan disbursement",
    "loan_disbursement_cancellation_reversal": (
        "Loan disbursement cancellation reversal"
    ),
    "loan_renewal_execution": "Loan renewal execution",
    "manual": "Manual journal",
    "no_collection": "No-collection accounting",
    "opening_balance": "Opening balance",
    "period_close": "Period close",
    "regular_collection_void_reversal": "Regular collection void reversal",
    "regular_eir_accrual": "Regular EIR accrual",
    "regular_renewal_eir_accrual": "Regular renewal EIR accrual",
    "remittance_transfer": "Remittance transfer",
    "remittance_transfer_reversal": "Remittance transfer reversal",
    "reversal": "Journal reversal",
    "seven_by_seven_collection": "7x7 collection",
    "seven_by_seven_collection_reversal": "7x7 collection reversal",
    "v1_tax_additional_liability": "Tax additional liability",
    "v1_tax_additional_settlement": "Tax additional settlement",
    "v1_tax_adjustment": "Tax adjustment",
    "v1_tax_liability": "Tax liability",
    "v1_tax_recoverable_credit_application": "Tax Recoverable credit application",
    "v1_tax_recoverable_refund": "Tax Recoverable refund",
    "v1_tax_settlement": "Tax settlement",
}
PROTECTED_FINANCIAL_SOURCE_TYPES = tuple(PROTECTED_FINANCIAL_SOURCE_LABELS)


@dataclass(frozen=True, slots=True)
class _AlertSpec:
    domain: str
    title: str
    severity: str
    navigation_code: str
    permission_group: str
    supports_amount: bool = False


ALERT_SPECS = {
    "payment_updates_unread": _AlertSpec(
        "payment_updates",
        "Unread payment updates",
        "info",
        "payment_updates",
        "payment_updates",
    ),
    "assigned_remittances": _AlertSpec(
        "remittance_custody",
        "Remittances assigned for review",
        "review",
        "remittance_review",
        "remittances",
        supports_amount=True,
    ),
    "unresolved_rejected_remittances": _AlertSpec(
        "remittance_custody",
        "Rejected remittances awaiting correction",
        "attention",
        "remittance_review",
        "remittances",
    ),
    "renewal_requests": _AlertSpec(
        "approvals",
        "Renewal requests awaiting review",
        "review",
        "renewals",
        "renewals",
    ),
    "staff_registrations": _AlertSpec(
        "approvals",
        "Staff registrations awaiting review",
        "review",
        "staff_devices",
        "accounts",
    ),
    "client_registrations": _AlertSpec(
        "approvals",
        "Client registrations awaiting review",
        "review",
        "client_registrations",
        "accounts",
    ),
    "staff_devices": _AlertSpec(
        "approvals",
        "Staff devices awaiting review",
        "review",
        "staff_devices",
        "devices",
    ),
    "support_requests": _AlertSpec(
        "approvals",
        "Client support awaiting review",
        "review",
        "support",
        "support",
    ),
    "protected_financial_audit_gaps": _AlertSpec(
        "financial",
        "Posted journals missing required audit evidence",
        "critical",
        "financial_accounting",
        "financial",
    ),
}


@dataclass(frozen=True, slots=True)
class _EventSpec:
    domain: str
    title: str
    severity: str
    navigation_code: str
    permission_group: str
    financial: bool = False


EVENT_SPECS = {
    "account.invite": _EventSpec(
        "approvals", "Staff account invited", "info", "staff_devices", "accounts"
    ),
    "account.role_change": _EventSpec(
        "approvals",
        "Account permissions changed",
        "attention",
        "staff_devices",
        "accounts",
    ),
    "account.status_change": _EventSpec(
        "approvals", "Account status changed", "attention", "staff_devices", "accounts"
    ),
    "client_registration.approve": _EventSpec(
        "approvals",
        "Client registration approved",
        "review",
        "client_registrations",
        "accounts",
    ),
    "client_registration.reject": _EventSpec(
        "approvals",
        "Client registration rejected",
        "attention",
        "client_registrations",
        "accounts",
    ),
    "device.replacement_auto_revoke": _EventSpec(
        "approvals", "Replaced device revoked", "attention", "staff_devices", "devices"
    ),
    "device.status_change": _EventSpec(
        "approvals", "Device status changed", "attention", "staff_devices", "devices"
    ),
    "renewal.rejected": _EventSpec(
        "approvals", "Renewal rejected", "attention", "renewals", "renewals"
    ),
    "renewal.management.approved": _EventSpec(
        "approvals", "Renewal approved by Management", "review", "renewals", "renewals"
    ),
    "renewal.management.rejected": _EventSpec(
        "approvals",
        "Renewal rejected by Management",
        "attention",
        "renewals",
        "renewals",
    ),
    "renewal.activation.completed": _EventSpec(
        "approvals", "Renewal activation completed", "info", "renewals", "renewals"
    ),
    "support.answered": _EventSpec(
        "approvals", "Support request answered", "info", "support", "support"
    ),
    "support.resolved": _EventSpec(
        "approvals", "Support request resolved", "info", "support", "support"
    ),
    "remittance.submitted": _EventSpec(
        "remittance_custody",
        "Remittance submitted",
        "review",
        "remittance_review",
        "remittances",
    ),
    "remittance.received": _EventSpec(
        "remittance_custody",
        "Remittance received",
        "info",
        "remittance_review",
        "remittances",
    ),
    "remittance.rejected": _EventSpec(
        "remittance_custody",
        "Remittance rejected",
        "attention",
        "remittance_review",
        "remittances",
    ),
    "financial.draft_created": _EventSpec(
        "financial",
        "Protected journal draft created",
        "review",
        "financial_accounting",
        "financial",
        True,
    ),
    "financial.draft_updated": _EventSpec(
        "financial",
        "Protected journal draft updated",
        "review",
        "financial_accounting",
        "financial",
        True,
    ),
    "financial.posted": _EventSpec(
        "financial",
        "Protected journal posted",
        "attention",
        "financial_accounting",
        "financial",
        True,
    ),
    "financial.reversal_created": _EventSpec(
        "financial",
        "Protected journal reversal created",
        "attention",
        "financial_accounting",
        "financial",
        True,
    ),
}


class ManagementAlertsAuditError(RuntimeError):
    code = "management_alerts_audit_unavailable"


def _invalid() -> ManagementAlertsAuditError:
    return ManagementAlertsAuditError(
        "The Management alerts and audit data is invalid."
    )


def _required_count(row, key: str) -> int:
    value = row[key]
    if type(value) is not int or value < 0:
        raise _invalid()
    return value


def _required_amount(row, key: str) -> Decimal:
    value = row[key]
    if not isinstance(value, Decimal) or isinstance(value, bool) or value < 0:
        raise _invalid()
    return value


def _required_datetime_value(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _invalid()
    try:
        offset = value.utcoffset()
    except (OverflowError, ValueError):
        offset = None
    if offset is None:
        raise _invalid()
    return value.astimezone(timezone.utc)


def _required_date_value(value: object) -> date:
    if type(value) is not date:
        raise _invalid()
    return value


def _required_uuid_value(value: object) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise _invalid() from error


def _required_text_value(value: object, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise _invalid()
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > maximum:
        raise _invalid()
    return normalized


def _optional_text_value(value: object, *, maximum: int) -> str | None:
    if value is None:
        return None
    return _required_text_value(value, maximum=maximum)


@dataclass(frozen=True, slots=True)
class ManagementAlert:
    code: str
    domain: str
    title: str
    count: int
    amount: Decimal | None
    severity: str
    navigation_code: str

    @classmethod
    def from_code(
        cls,
        code: str,
        *,
        count: int,
        amount: Decimal | None = None,
    ) -> ManagementAlert:
        spec = ALERT_SPECS.get(code)
        if spec is None or type(count) is not int or count < 0:
            raise _invalid()
        if spec.supports_amount:
            if amount is None or not isinstance(amount, Decimal) or amount < 0:
                raise _invalid()
        elif amount is not None:
            raise _invalid()
        return cls(
            code=code,
            domain=spec.domain,
            title=spec.title,
            count=count,
            amount=amount,
            severity=spec.severity,
            navigation_code=spec.navigation_code,
        )


@dataclass(frozen=True, slots=True)
class ManagementAuditEvent:
    event_key: str
    domain: str
    action_code: str
    title: str
    severity: str
    navigation_code: str
    occurred_at: datetime
    business_date: date
    record_id: UUID
    reference: str
    current_state: str
    actor_name: str
    checker_name: str | None
    source_type: str | None
    source_label: str | None
    reason: str | None

    @classmethod
    def from_row_values(
        cls,
        *,
        event_key: object,
        action_code: object,
        occurred_at: object,
        business_date: object,
        record_id: object,
        reference: object,
        current_state: object,
        actor_name: object,
        checker_name: object,
        source_type: object,
        reason: object,
    ) -> ManagementAuditEvent:
        normalized_action = _required_text_value(action_code, maximum=80)
        spec = EVENT_SPECS.get(normalized_action)
        if spec is None:
            raise _invalid()
        normalized_source = _optional_text_value(source_type, maximum=80)
        source_label: str | None = None
        if spec.financial:
            if normalized_source not in PROTECTED_FINANCIAL_SOURCE_LABELS:
                raise _invalid()
            source_label = PROTECTED_FINANCIAL_SOURCE_LABELS[normalized_source]
        elif normalized_source is not None:
            raise _invalid()
        return cls(
            event_key=_required_text_value(event_key, maximum=300),
            domain=spec.domain,
            action_code=normalized_action,
            title=spec.title,
            severity=spec.severity,
            navigation_code=spec.navigation_code,
            occurred_at=_required_datetime_value(occurred_at),
            business_date=_required_date_value(business_date),
            record_id=_required_uuid_value(record_id),
            reference=_required_text_value(reference, maximum=200),
            current_state=_required_text_value(current_state, maximum=80),
            actor_name=_required_text_value(actor_name, maximum=200),
            checker_name=_optional_text_value(checker_name, maximum=200),
            source_type=normalized_source,
            source_label=source_label,
            reason=_optional_text_value(reason, maximum=500),
        )


@dataclass(frozen=True, slots=True)
class ManagementAlertsAuditSnapshot:
    generated_at: datetime
    window_days: int
    limit: int
    visible_domains: tuple[str, ...]
    alerts: tuple[ManagementAlert, ...]
    events: tuple[ManagementAuditEvent, ...]
    event_total_count: int


_SNAPSHOT_SQL = """
with settings as (
    select
        %s::uuid as actor_user_id,
        %s::boolean as include_accounts,
        %s::boolean as include_devices,
        %s::boolean as include_renewals,
        %s::boolean as include_support,
        %s::boolean as include_remittances,
        %s::boolean as include_financial,
        %s::integer as window_days,
        %s::integer as result_limit,
        %s::text[] as protected_source_types
),
queue_counts as (
    select
        statement_timestamp() as generated_at,
        (
            select count(*)::integer
            from core.activity_notifications notification
            where notification.recipient_user_id = settings.actor_user_id
              and notification.is_read = false
        ) as payment_updates_unread_count,
        case when settings.include_remittances then (
            select count(*)::integer
            from lending.collection_remittances remittance
            where remittance.recipient_user_id = settings.actor_user_id
              and remittance.status = 'submitted'
              and remittance.received_at is null
              and not exists (
                  select 1
                  from lending.collection_remittance_rejections rejection
                  where rejection.remittance_id = remittance.id
              )
        ) else null end as assigned_remittance_count,
        case when settings.include_remittances then (
            select coalesce(sum(remittance.total_amount), 0)::numeric(18,2)
            from lending.collection_remittances remittance
            where remittance.recipient_user_id = settings.actor_user_id
              and remittance.status = 'submitted'
              and remittance.received_at is null
              and not exists (
                  select 1
                  from lending.collection_remittance_rejections rejection
                  where rejection.remittance_id = remittance.id
              )
        ) else null end as assigned_remittance_amount,
        case when settings.include_remittances then (
            select count(*)::integer
            from lending.collection_remittance_rejections rejection
            join lending.collection_remittances remittance
              on remittance.id = rejection.remittance_id
            where remittance.recipient_user_id = settings.actor_user_id
              and exists (
                  select 1
                  from lending.collection_remittance_items item
                  join lending.collection_transactions transaction
                    on transaction.id = item.transaction_id
                  where item.remittance_id = remittance.id
                    and transaction.is_voided = false
                    and transaction.is_locked = false
                    and transaction.remittance_id is null
              )
        ) else null end as unresolved_rejected_remittance_count,
        case when settings.include_renewals then (
            select count(*)::integer
            from lending.client_renewal_requests request
            where request.status = 'pending'
        ) else null end as pending_renewal_count,
        case when settings.include_accounts then (
            select count(distinct account.id)::integer
            from core.users account
            join core.user_roles user_role on user_role.user_id = account.id
            join core.roles role on role.id = user_role.role_id
            where account.status = 'pending'
              and role.code in ('collector', 'employee', 'management')
        ) else null end as pending_staff_registration_count,
        case when settings.include_accounts then (
            select count(*)::integer
            from core.client_registration_requests request
            where request.status = 'pending'
        ) else null end as pending_client_registration_count,
        case when settings.include_devices then (
            select count(distinct device.id)::integer
            from core.devices device
            join core.user_roles user_role on user_role.user_id = device.user_id
            join core.roles role on role.id = user_role.role_id
            where device.status = 'pending'
              and role.code in ('collector', 'employee', 'management')
        ) else null end as pending_staff_device_count,
        case when settings.include_support then (
            select count(*)::integer
            from lending.client_support_requests request
            where request.status in ('open', 'answered')
        ) else null end as pending_support_count,
        case when settings.include_financial then (
            select count(*)::integer
            from accounting.journal_entries journal
            where journal.status = 'posted'
              and journal.source_type = any(settings.protected_source_types)
              and not exists (
                  select 1
                  from accounting.journal_events event
                  where event.journal_entry_id = journal.id
                    and event.event_type = 'posted'
              )
        ) else null end as protected_financial_audit_gap_count
    from settings
),
account_events as (
    select
        'audit:' || audit.id::text as event_key,
        audit.action::text as action_code,
        audit.created_at as occurred_at,
        (audit.created_at at time zone 'Asia/Manila')::date as business_date,
        account.id as record_id,
        account.username::text as reference,
        account.status::text as current_state,
        actor.full_name::text as actor_name,
        null::text as checker_name,
        null::text as source_type,
        null::text as reason
    from settings
    join core.audit_logs audit on settings.include_accounts
    join core.users account
      on account.id = audit.target_id
     and audit.target_type = 'user'
    join core.users actor on actor.id = audit.actor_user_id
    where audit.action in (
        'account.invite', 'account.role_change', 'account.status_change'
    )
),
client_registration_events as (
    select
        'audit:' || audit.id::text as event_key,
        audit.action::text as action_code,
        audit.created_at as occurred_at,
        (audit.created_at at time zone 'Asia/Manila')::date as business_date,
        request.user_id as record_id,
        account.username::text as reference,
        request.status::text as current_state,
        actor.full_name::text as actor_name,
        actor.full_name::text as checker_name,
        null::text as source_type,
        null::text as reason
    from settings
    join core.audit_logs audit on settings.include_accounts
    join core.client_registration_requests request
      on request.user_id = audit.target_id
     and audit.target_type = 'user'
    join core.users account on account.id = request.user_id
    join core.users actor on actor.id = audit.actor_user_id
    where audit.action in (
        'client_registration.approve', 'client_registration.reject'
    )
),
device_events as (
    select
        'audit:' || audit.id::text as event_key,
        audit.action::text as action_code,
        audit.created_at as occurred_at,
        (audit.created_at at time zone 'Asia/Manila')::date as business_date,
        device.id as record_id,
        account.username::text as reference,
        device.status::text as current_state,
        actor.full_name::text as actor_name,
        actor.full_name::text as checker_name,
        null::text as source_type,
        null::text as reason
    from settings
    join core.audit_logs audit on settings.include_devices
    join core.devices device
      on device.id = audit.target_id
     and audit.target_type = 'device'
    join core.users account on account.id = device.user_id
    join core.users actor on actor.id = audit.actor_user_id
    where audit.action in (
        'device.replacement_auto_revoke', 'device.status_change'
    )
),
renewal_events as (
    select
        'audit:' || audit.id::text as event_key,
        audit.action::text as action_code,
        audit.created_at as occurred_at,
        (audit.created_at at time zone 'Asia/Manila')::date as business_date,
        request.id as record_id,
        'Renewal request'::text as reference,
        request.status::text as current_state,
        actor.full_name::text as actor_name,
        actor.full_name::text as checker_name,
        null::text as source_type,
        null::text as reason
    from settings
    join core.audit_logs audit on settings.include_renewals
    join lending.client_renewal_requests request
      on request.id = audit.target_id
     and audit.target_type = 'client_renewal_request'
    join core.users actor on actor.id = audit.actor_user_id
    where audit.action in (
        'renewal.rejected',
        'renewal.management.approved',
        'renewal.management.rejected',
        'renewal.activation.completed'
    )
),
support_events as (
    select
        'audit:' || audit.id::text as event_key,
        audit.action::text as action_code,
        audit.created_at as occurred_at,
        (audit.created_at at time zone 'Asia/Manila')::date as business_date,
        request.id as record_id,
        'Support request'::text as reference,
        request.status::text as current_state,
        actor.full_name::text as actor_name,
        actor.full_name::text as checker_name,
        null::text as source_type,
        null::text as reason
    from settings
    join core.audit_logs audit on settings.include_support
    join lending.client_support_requests request
      on request.id = audit.target_id
     and audit.target_type = 'client_support_request'
    join core.users actor on actor.id = audit.actor_user_id
    where audit.action in ('support.answered', 'support.resolved')
),
remittance_events as (
    select
        'remittance-submitted:' || remittance.id::text as event_key,
        'remittance.submitted'::text as action_code,
        remittance.submitted_at as occurred_at,
        remittance.collection_date as business_date,
        remittance.id as record_id,
        remittance.remittance_number::text as reference,
        case when rejection.remittance_id is not null
            then 'rejected' else remittance.status end::text as current_state,
        collector.full_name::text as actor_name,
        null::text as checker_name,
        null::text as source_type,
        null::text as reason
    from settings
    join lending.collection_remittances remittance
      on settings.include_remittances
    join core.users collector on collector.id = remittance.collector_user_id
    left join lending.collection_remittance_rejections rejection
      on rejection.remittance_id = remittance.id

    union all

    select
        'remittance-received:' || remittance.id::text,
        'remittance.received'::text,
        remittance.received_at,
        remittance.collection_date,
        remittance.id,
        remittance.remittance_number::text,
        remittance.status::text,
        collector.full_name::text,
        checker.full_name::text,
        null::text,
        null::text
    from settings
    join lending.collection_remittances remittance
      on settings.include_remittances and remittance.received_at is not null
    join core.users collector on collector.id = remittance.collector_user_id
    join core.users checker on checker.id = remittance.received_by_user_id

    union all

    select
        'remittance-rejected:' || remittance.id::text,
        'remittance.rejected'::text,
        rejection.rejected_at,
        remittance.collection_date,
        remittance.id,
        remittance.remittance_number::text,
        'rejected'::text,
        collector.full_name::text,
        checker.full_name::text,
        null::text,
        rejection.reason::text
    from settings
    join lending.collection_remittance_rejections rejection
      on settings.include_remittances
    join lending.collection_remittances remittance
      on remittance.id = rejection.remittance_id
    join core.users collector on collector.id = remittance.collector_user_id
    join core.users checker on checker.id = rejection.rejected_by_user_id
),
financial_events as (
    select
        'financial:' || event.id::text as event_key,
        'financial.' || event.event_type::text as action_code,
        event.created_at as occurred_at,
        journal.posting_date as business_date,
        journal.id as record_id,
        coalesce(
            journal.entry_number,
            journal.source_reference,
            'Protected journal'
        )::text as reference,
        journal.status::text as current_state,
        actor.full_name::text as actor_name,
        checker.full_name::text as checker_name,
        journal.source_type::text as source_type,
        null::text as reason
    from settings
    join accounting.journal_entries journal
      on settings.include_financial
     and journal.source_type = any(settings.protected_source_types)
    join accounting.journal_events event on event.journal_entry_id = journal.id
    join core.users actor on actor.id = event.actor_user_id
    left join core.users checker on checker.id = journal.posted_by_user_id
    where event.event_type in (
        'draft_created', 'draft_updated', 'posted', 'reversal_created'
    )
),
all_events as (
    select * from account_events
    union all select * from client_registration_events
    union all select * from device_events
    union all select * from renewal_events
    union all select * from support_events
    union all select * from remittance_events
    union all select * from financial_events
),
recent_events as (
    select event.*
    from all_events event
    cross join settings
    where event.occurred_at between
        statement_timestamp() - make_interval(days => settings.window_days)
        and statement_timestamp()
),
paged_events as (
    select event.*
    from recent_events event
    cross join settings
    order by event.occurred_at desc, event.event_key desc
    limit (select result_limit from settings)
)
select
    queue_counts.*,
    event.*,
    (select count(*)::integer from recent_events) as event_total_count
from queue_counts
left join paged_events event on true
order by event.occurred_at desc nulls last, event.event_key desc nulls last
"""


def _permission_flags(
    *,
    include_accounts: bool,
    include_devices: bool,
    include_renewals: bool,
    include_support: bool,
    include_remittances: bool,
    include_financial: bool,
) -> dict[str, bool]:
    return {
        "payment_updates": True,
        "accounts": include_accounts,
        "devices": include_devices,
        "renewals": include_renewals,
        "support": include_support,
        "remittances": include_remittances,
        "financial": include_financial,
    }


class PostgresManagementAlertsAuditRepository:
    def load_snapshot(
        self,
        *,
        actor_user_id: UUID,
        include_accounts: bool,
        include_devices: bool,
        include_renewals: bool,
        include_support: bool,
        include_remittances: bool,
        include_financial: bool,
        window_days: int,
        limit: int,
    ) -> ManagementAlertsAuditSnapshot:
        parameters = (
            actor_user_id,
            include_accounts,
            include_devices,
            include_renewals,
            include_support,
            include_remittances,
            include_financial,
            window_days,
            limit,
            list(PROTECTED_FINANCIAL_SOURCE_TYPES),
        )
        with (
            open_connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            cursor.execute(_SNAPSHOT_SQL, parameters)
            rows = cursor.fetchall()
        if not rows:
            raise ManagementAlertsAuditError(
                "The Management alerts and audit data is unavailable."
            )

        flags = _permission_flags(
            include_accounts=include_accounts,
            include_devices=include_devices,
            include_renewals=include_renewals,
            include_support=include_support,
            include_remittances=include_remittances,
            include_financial=include_financial,
        )
        try:
            first = rows[0]
            generated_at = _required_datetime_value(first["generated_at"])
            event_total_count = _required_count(first, "event_total_count")
            alert_values = (
                ("payment_updates_unread", "payment_updates_unread_count", None),
                (
                    "assigned_remittances",
                    "assigned_remittance_count",
                    "assigned_remittance_amount",
                ),
                (
                    "unresolved_rejected_remittances",
                    "unresolved_rejected_remittance_count",
                    None,
                ),
                ("renewal_requests", "pending_renewal_count", None),
                ("staff_registrations", "pending_staff_registration_count", None),
                ("client_registrations", "pending_client_registration_count", None),
                ("staff_devices", "pending_staff_device_count", None),
                ("support_requests", "pending_support_count", None),
                (
                    "protected_financial_audit_gaps",
                    "protected_financial_audit_gap_count",
                    None,
                ),
            )
            alerts: list[ManagementAlert] = []
            for code, count_key, amount_key in alert_values:
                spec = ALERT_SPECS[code]
                if not flags[spec.permission_group]:
                    continue
                count = _required_count(first, count_key)
                amount = (
                    _required_amount(first, amount_key)
                    if amount_key is not None
                    else None
                )
                if count > 0:
                    alerts.append(
                        ManagementAlert.from_code(code, count=count, amount=amount)
                    )

            events: list[ManagementAuditEvent] = []
            for row in rows:
                if _required_datetime_value(row["generated_at"]) != generated_at:
                    raise _invalid()
                if _required_count(row, "event_total_count") != event_total_count:
                    raise _invalid()
                if row["event_key"] is None:
                    if any(
                        row[key] is not None
                        for key in (
                            "action_code",
                            "occurred_at",
                            "business_date",
                            "record_id",
                            "reference",
                            "current_state",
                            "actor_name",
                            "checker_name",
                            "source_type",
                            "reason",
                        )
                    ):
                        raise _invalid()
                    continue
                action = _required_text_value(row["action_code"], maximum=80)
                spec = EVENT_SPECS.get(action)
                if spec is None:
                    raise _invalid()
                if not flags[spec.permission_group]:
                    continue
                events.append(
                    ManagementAuditEvent.from_row_values(
                        event_key=row["event_key"],
                        action_code=action,
                        occurred_at=row["occurred_at"],
                        business_date=row["business_date"],
                        record_id=row["record_id"],
                        reference=row["reference"],
                        current_state=row["current_state"],
                        actor_name=row["actor_name"],
                        checker_name=row["checker_name"],
                        source_type=row["source_type"],
                        reason=row["reason"],
                    )
                )
            if len(events) > event_total_count:
                raise _invalid()
        except (KeyError, TypeError) as error:
            raise _invalid() from error

        visible_domains = ["payment_updates"]
        if include_accounts or include_devices or include_renewals or include_support:
            visible_domains.append("approvals")
        if include_remittances:
            visible_domains.append("remittance_custody")
        if include_financial:
            visible_domains.append("financial")
        return ManagementAlertsAuditSnapshot(
            generated_at=generated_at,
            window_days=window_days,
            limit=limit,
            visible_domains=tuple(visible_domains),
            alerts=tuple(alerts),
            events=tuple(events),
            event_total_count=event_total_count,
        )
