from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection


@dataclass(frozen=True, slots=True)
class ManagementDashboardMetric:
    key: str
    count: int | None = None
    amount: Decimal | None = None
    as_of_date: date | None = None


@dataclass(frozen=True, slots=True)
class ManagementDashboardOverview:
    generated_at: datetime
    metrics: tuple[ManagementDashboardMetric, ...]


class ManagementDashboardOverviewError(RuntimeError):
    code = "management_overview_unavailable"


def _required_count(row, key: str) -> int:
    value = row[key]
    if type(value) is not int or value < 0:
        raise ManagementDashboardOverviewError(
            "The Management overview data is invalid."
        )
    return value


def _required_amount(row, key: str) -> Decimal:
    value = row[key]
    if not isinstance(value, Decimal) or value < 0:
        raise ManagementDashboardOverviewError(
            "The Management overview data is invalid."
        )
    return value


def _optional_date(row, key: str) -> date | None:
    value = row[key]
    if value is None:
        return None
    if type(value) is not date:
        raise ManagementDashboardOverviewError(
            "The Management overview data is invalid."
        )
    return value


def _generated_at(row) -> datetime:
    value = row["generated_at"]
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ManagementDashboardOverviewError(
            "The Management overview data is invalid."
        )
    try:
        offset = value.utcoffset()
    except (OverflowError, ValueError):
        offset = None
    if offset is None:
        raise ManagementDashboardOverviewError(
            "The Management overview data is invalid."
        )
    return value.astimezone(timezone.utc)


class PostgresManagementDashboardOverviewRepository:
    def load_overview(
        self,
        *,
        actor_user_id: UUID,
        include_remittances: bool,
        include_renewals: bool,
        include_accounts: bool,
        include_devices: bool,
        include_support: bool,
    ) -> ManagementDashboardOverview:
        # Keep the connection and cursor scopes visually separate like the
        # neighboring repositories; both still wrap one execute call.
        with open_connection() as connection:  # noqa: SIM117
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    with portfolio as (
                        select
                            count(*) filter (
                                where lower(loan.status) = 'active'
                            ) as active_loan_count,
                            count(distinct loan.client_id) filter (
                                where lower(loan.status) = 'active'
                            ) as active_client_count,
                            count(*) filter (
                                where lower(loan.status) = 'active'
                                  and loan.due_date < current_date
                                  and coalesce(
                                      state.remaining_balance,
                                      loan.principal
                                  ) > 0
                            ) as overdue_loan_count,
                            coalesce(sum(coalesce(
                                state.remaining_balance,
                                loan.principal
                            )) filter (
                                where lower(loan.status) = 'active'
                            ), 0)::numeric(18,2) as outstanding_balance
                        from lending.loans loan
                        left join lending.loan_collection_state state
                          on state.loan_id = loan.id
                    ),
                    latest_collection as (
                        select max(collection_date) as collection_date
                        from lending.collection_transactions
                        where is_voided = false
                    ),
                    collections as (
                        select
                            latest.collection_date as latest_collection_date,
                            count(*) filter (
                                where transaction.is_voided = false
                                  and transaction.entry_type <> 'pass'
                                  and transaction.collection_date =
                                      latest.collection_date
                            ) as latest_collection_count,
                            coalesce(sum(transaction.amount) filter (
                                where transaction.is_voided = false
                                  and transaction.entry_type <> 'pass'
                                  and transaction.collection_date =
                                      latest.collection_date
                            ), 0)::numeric(18,2) as latest_collection_amount,
                            count(*) filter (
                                where transaction.is_voided = false
                                  and transaction.is_locked = false
                                  and transaction.remittance_id is null
                            ) as unremitted_count,
                            coalesce(sum(transaction.amount) filter (
                                where transaction.is_voided = false
                                  and transaction.is_locked = false
                                  and transaction.remittance_id is null
                                  and transaction.entry_type <> 'pass'
                            ), 0)::numeric(18,2) as unremitted_amount
                        from latest_collection latest
                        left join lending.collection_transactions transaction
                          on true
                        group by latest.collection_date
                    ),
                    remittances as (
                        select
                            case when %s then count(*) else null end
                                as remittance_count,
                            case when %s then
                                coalesce(sum(remittance.total_amount), 0)
                            else null end::numeric(18,2)
                                as remittance_amount
                        from lending.collection_remittances remittance
                        where remittance.recipient_user_id = %s
                          and remittance.status = 'submitted'
                          and remittance.received_at is null
                          and not exists (
                              select 1
                              from lending.collection_remittance_rejections rejection
                              where rejection.remittance_id = remittance.id
                          )
                    ),
                    renewals as (
                        select case when %s then count(*) else null end
                            as renewal_count
                        from lending.client_renewal_requests request
                        where request.status = 'pending'
                    ),
                    registrations as (
                        select
                            case when %s then (
                                select count(distinct account.id)
                                from core.users account
                                join core.user_roles user_role
                                  on user_role.user_id = account.id
                                join core.roles role
                                  on role.id = user_role.role_id
                                where account.status = 'pending'
                                  and role.code in (
                                      'collector',
                                      'employee',
                                      'management'
                                  )
                            ) else null end as staff_registration_count,
                            case when %s then (
                                select count(*)
                                from core.client_registration_requests request
                                where request.status = 'pending'
                            ) else null end as client_registration_count
                    ),
                    collector_devices as (
                        select case when %s then count(distinct device.id)
                            else null end as collector_device_count
                        from core.devices device
                        join core.user_roles user_role
                          on user_role.user_id = device.user_id
                        join core.roles role on role.id = user_role.role_id
                        where role.code = 'collector'
                          and device.status = 'pending'
                          and lower(device.platform) in ('android', 'ios')
                    ),
                    support as (
                        select case when %s then count(*) else null end
                            as support_count
                        from lending.client_support_requests request
                        where request.status in ('open', 'answered')
                    ),
                    activity as (
                        select count(*) as unread_activity_count
                        from core.activity_notifications notification
                        where notification.recipient_user_id = %s
                          and notification.is_read = false
                    )
                    select
                        statement_timestamp() as generated_at,
                        portfolio.*,
                        collections.*,
                        remittances.*,
                        renewals.*,
                        registrations.*,
                        collector_devices.*,
                        support.*,
                        activity.*
                    from portfolio
                    cross join collections
                    cross join remittances
                    cross join renewals
                    cross join registrations
                    cross join collector_devices
                    cross join support
                    cross join activity
                    """,
                    (
                        include_remittances,
                        include_remittances,
                        actor_user_id,
                        include_renewals,
                        include_accounts,
                        include_accounts,
                        include_devices,
                        include_support,
                        actor_user_id,
                    ),
                )
                row = cursor.fetchone()

        if row is None:
            raise ManagementDashboardOverviewError(
                "The Management overview data is unavailable."
            )

        try:
            metrics = [
                ManagementDashboardMetric(
                    key="portfolio.active_clients",
                    count=_required_count(row, "active_client_count"),
                ),
                ManagementDashboardMetric(
                    key="portfolio.active_loans",
                    count=_required_count(row, "active_loan_count"),
                ),
                ManagementDashboardMetric(
                    key="portfolio.overdue_loans",
                    count=_required_count(row, "overdue_loan_count"),
                ),
                ManagementDashboardMetric(
                    key="portfolio.outstanding_balance",
                    amount=_required_amount(row, "outstanding_balance"),
                ),
                ManagementDashboardMetric(
                    key="collections.latest_day",
                    count=_required_count(row, "latest_collection_count"),
                    amount=_required_amount(row, "latest_collection_amount"),
                    as_of_date=_optional_date(row, "latest_collection_date"),
                ),
                ManagementDashboardMetric(
                    key="collections.unremitted",
                    count=_required_count(row, "unremitted_count"),
                    amount=_required_amount(row, "unremitted_amount"),
                ),
            ]
            if include_remittances:
                metrics.append(
                    ManagementDashboardMetric(
                        key="queues.remittances_assigned",
                        count=_required_count(row, "remittance_count"),
                        amount=_required_amount(row, "remittance_amount"),
                    )
                )
            if include_renewals:
                metrics.append(
                    ManagementDashboardMetric(
                        key="queues.renewals_protected",
                        count=_required_count(row, "renewal_count"),
                    )
                )
            if include_accounts:
                metrics.extend(
                    (
                        ManagementDashboardMetric(
                            key="queues.staff_registrations",
                            count=_required_count(
                                row,
                                "staff_registration_count",
                            ),
                        ),
                        ManagementDashboardMetric(
                            key="queues.client_registrations",
                            count=_required_count(
                                row,
                                "client_registration_count",
                            ),
                        ),
                    )
                )
            if include_devices:
                metrics.append(
                    ManagementDashboardMetric(
                        key="queues.collector_mobile_devices",
                        count=_required_count(row, "collector_device_count"),
                    )
                )
            if include_support:
                metrics.append(
                    ManagementDashboardMetric(
                        key="queues.borrower_support",
                        count=_required_count(row, "support_count"),
                    )
                )
            metrics.append(
                ManagementDashboardMetric(
                    key="activity.unread",
                    count=_required_count(row, "unread_activity_count"),
                )
            )
            generated_at = _generated_at(row)
        except (KeyError, TypeError) as exc:
            raise ManagementDashboardOverviewError(
                "The Management overview data is invalid."
            ) from exc

        return ManagementDashboardOverview(
            generated_at=generated_at,
            metrics=tuple(metrics),
        )
