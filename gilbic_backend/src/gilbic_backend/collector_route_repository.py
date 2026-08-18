from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection


MONEY = Decimal("0.01")
CONTRACT_ALLOCATION_SETTING = "mobile_contract_schedule_allocation_enabled"


@dataclass(frozen=True, slots=True)
class CollectorRouteReceiptRecord:
    transaction_id: UUID
    receipt_number: str
    amount: Decimal
    entry_type: str
    collector_user_id: UUID
    collector_name: str
    is_locked: bool
    note: str = ""
    covered_dates: tuple[date, ...] = ()
    accepted_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CollectorRouteEntryRecord:
    route_entry_id: UUID
    client_id: UUID
    loan_id: UUID
    client_name: str
    area: str
    loan_type: str
    daily_amount: Decimal
    remaining_balance: Decimal
    pass_count: int
    last_payment_date: date | None
    advance_until: date | None
    status: str
    note: str
    state_version: int = 0
    is_reconciled: bool = False
    mobile_collections_enabled: bool = False
    mobile_balance_mode: str = ""
    contract_allocation_enabled: bool = False
    contract_schedule_verified: bool = False
    contract_dpd_status: str = "contract_schedule_required"
    contract_payment_frequency: str = ""
    contract_reference: str = ""
    contract_schedule_version: int | None = None
    contract_grace_days: int = 0
    contract_balance_reconciled: bool = False
    contract_schedule_ready: bool = False
    contract_collection_ready: bool = False
    contract_days_past_due: int | None = None
    contract_today_scheduled_amount: Decimal = Decimal("0.00")
    contract_today_unpaid_amount: Decimal = Decimal("0.00")
    contract_today_already_covered: bool = False
    contract_next_unpaid_date: date | None = None
    contract_next_unpaid_amount: Decimal = Decimal("0.00")
    processed_today: bool = False
    today_entry_type: str = ""
    today_collector_name: str = ""
    today_transaction_id: UUID | None = None
    today_collector_user_id: UUID | None = None
    today_is_locked: bool = False
    can_edit_today: bool = False
    today_amount: Decimal = Decimal("0.00")
    today_note: str = ""
    today_covered_dates: tuple[date, ...] = ()
    today_receipts: tuple[CollectorRouteReceiptRecord, ...] = ()
    covered_dates: tuple[date, ...] = ()

    @property
    def route_revision(self) -> str:
        return f"loan:{self.loan_id}:v{self.state_version}"

    @property
    def can_collect_mobile(self) -> bool:
        return self.is_reconciled and self.mobile_collections_enabled

    @property
    def can_enter_payment(self) -> bool:
        base_ready = (
            self.can_collect_mobile
            and self.mobile_balance_mode == "direct_remaining_balance"
        )
        if not base_ready:
            return False
        if self.contract_allocation_enabled:
            return self.contract_collection_ready
        return True

    @property
    def contract_readiness_message(self) -> str:
        status = self.contract_dpd_status.strip() or "contract_schedule_required"
        if status == "contract_schedule_required":
            return "Contract schedule: signed-contract verification is still required."
        if not self.contract_schedule_verified:
            return "Contract schedule exists, but Management verification is still required."
        if status == "contract_installments_required":
            return "Verified contract schedule is missing its exact installment dates or amounts."
        if status == "payment_allocation_required":
            return "Verified contract schedule needs prior payment allocation reconciliation."
        if status != "ready":
            return f"Contract schedule readiness: {status.replace('_', ' ')}."
        if not self.contract_balance_reconciled:
            return "Verified contract schedule is ready, but its unpaid amount does not match the operational balance."
        if not self.contract_schedule_ready:
            return "Contract schedule failed a protected accounting safety check."

        context: list[str] = []
        if self.contract_today_scheduled_amount > Decimal("0.00"):
            context.append(
                "Today's scheduled payment: "
                f"₱{self.contract_today_scheduled_amount:,.2f}."
            )
            if self.contract_today_already_covered:
                context.append("Today is already covered by advance.")
            elif self.contract_today_unpaid_amount > Decimal("0.00"):
                context.append(
                    "Still unpaid today: "
                    f"₱{self.contract_today_unpaid_amount:,.2f}."
                )
        else:
            context.append("No contractual installment is due today.")

        if self.contract_next_unpaid_date is not None:
            context.append(
                "Next unpaid installment: "
                f"{self.contract_next_unpaid_date.isoformat()} – "
                f"₱{self.contract_next_unpaid_amount:,.2f}."
            )
        if self.contract_days_past_due is not None:
            context.append(f"Contract DPD: {self.contract_days_past_due}.")

        if self.contract_allocation_enabled:
            lead = "Verified contractual collection is ready."
        else:
            lead = (
                "Contract schedule is verified and reconciled; contractual mobile "
                "allocation is not enabled yet."
            )
        return " ".join([lead, *context])

    @property
    def collection_message(self) -> str:
        if self.processed_today:
            if self.today_is_locked:
                return "Today's collection is already included in a remittance and is locked."
            return "Today's collection has already been recorded."
        if not self.is_reconciled:
            return "Checking this loan against SPINA records."
        if not self.mobile_collections_enabled:
            return "Use the SPINA desktop app for this loan type."
        if self.mobile_balance_mode != "direct_remaining_balance":
            return "Unable-to-pay is available, but payments still use SPINA desktop."
        if self.contract_allocation_enabled and not self.contract_collection_ready:
            return self.contract_readiness_message
        return f"Ready for mobile collection. {self.contract_readiness_message}"


@dataclass(frozen=True, slots=True)
class CollectorRouteRecord:
    route_date: date
    collector_name: str
    areas: tuple[str, ...]
    entries: tuple[CollectorRouteEntryRecord, ...]

    @property
    def expected_total(self) -> Decimal:
        return sum((entry.daily_amount for entry in self.entries), start=Decimal("0"))


def _date_value(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _datetime_value(value: object | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _receipt_records(value: object) -> tuple[CollectorRouteReceiptRecord, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    receipts: list[CollectorRouteReceiptRecord] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        transaction_id = raw.get("transaction_id")
        receipt_number = str(raw.get("receipt_number") or "").strip()
        collector_user_id = raw.get("collector_user_id")
        if transaction_id is None or collector_user_id is None or not receipt_number:
            continue
        covered_raw = raw.get("covered_dates")
        covered_dates = tuple(
            _date_value(item)
            for item in covered_raw
        ) if isinstance(covered_raw, (list, tuple)) else ()
        receipts.append(
            CollectorRouteReceiptRecord(
                transaction_id=UUID(str(transaction_id)),
                receipt_number=receipt_number,
                amount=Decimal(str(raw.get("amount") or 0)).quantize(MONEY),
                entry_type=str(raw.get("entry_type") or "payment"),
                collector_user_id=UUID(str(collector_user_id)),
                collector_name=str(raw.get("collector_name") or "Collector"),
                is_locked=bool(raw.get("is_locked")),
                note=str(raw.get("note") or ""),
                covered_dates=covered_dates,
                accepted_at=_datetime_value(raw.get("accepted_at")),
            )
        )
    return tuple(receipts)


class PostgresCollectorRouteRepository:
    """Read the live route for one authenticated collector."""

    def get_today_route(
        self,
        *,
        collector_user_id: UUID,
        collector_name: str,
        route_date: date,
    ) -> CollectorRouteRecord:
        with open_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select area
                    from lending.collector_area_assignments
                    where collector_user_id = %s
                      and is_active = true
                    order by sort_order, lower(area), id
                    """,
                    (collector_user_id,),
                )
                areas = tuple(str(row[0]) for row in cursor.fetchall())

            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        l.id as route_entry_id,
                        c.id as client_id,
                        l.id as loan_id,
                        c.full_name as client_name,
                        c.area,
                        lt.name as loan_type,
                        l.daily_amount,
                        coalesce(s.remaining_balance, l.principal) as remaining_balance,
                        coalesce(s.pass_count, 0) as pass_count,
                        s.last_payment_date,
                        s.advance_until,
                        case
                            when today.entry_type = 'pass'
                                then 'Unable to pay'
                            when today.entry_type is not null
                                then 'Recorded today'
                            when coalesce(s.is_reconciled, false) = false
                                then 'Needs review'
                            when lower(coalesce(lt.settings->>'mobile_collections_enabled', ''))
                                 not in ('true', '1', 'yes', 'on')
                                then 'Desktop only'
                            when coalesce(coverage.covered_today, false)
                                then 'Covered'
                            when coalesce(s.pass_count, 0) > 0
                                then 'Missed payment'
                            else 'Pending'
                        end as collection_status,
                        coalesce(s.note, '') as note,
                        coalesce(s.state_version, 0) as state_version,
                        coalesce(s.is_reconciled, false) as is_reconciled,
                        lower(coalesce(lt.settings->>'mobile_collections_enabled', ''))
                            in ('true', '1', 'yes', 'on') as mobile_collections_enabled,
                        coalesce(lt.settings->>'mobile_balance_mode', '') as mobile_balance_mode,
                        lower(coalesce(lt.settings->>%s, ''))
                            in ('true', '1', 'yes', 'on') as contract_allocation_enabled,
                        assessment.schedule_version as contract_schedule_version,
                        coalesce(assessment.payment_frequency, '') as contract_payment_frequency,
                        coalesce(assessment.contract_reference, '') as contract_reference,
                        coalesce(assessment.grace_days, 0) as contract_grace_days,
                        coalesce(assessment.dpd_data_status, 'contract_schedule_required')
                            as contract_dpd_status,
                        assessment.days_past_due as contract_days_past_due,
                        coalesce(assessment.contractual_schedule_total, 0)::numeric(18,2)
                            as contract_schedule_total,
                        coalesce(assessment.allocated_schedule_total, 0)::numeric(18,2)
                            as contract_allocated_total,
                        coalesce(assessment.automatic_default_label_written, false)
                            as contract_automatic_default,
                        coalesce(assessment.ecl_included, false) as contract_ecl_included,
                        assessment.ecl_amount as contract_ecl_amount,
                        coalesce(assessment.ready_to_post, false) as contract_ready_to_post,
                        registration.id is not null as contract_schedule_verified,
                        coalesce(contract_today.installment_count, 0)::bigint
                            as contract_today_installment_count,
                        coalesce(contract_today.scheduled_amount, 0)::numeric(18,2)
                            as contract_today_scheduled_amount,
                        coalesce(contract_today.unpaid_amount, 0)::numeric(18,2)
                            as contract_today_unpaid_amount,
                        contract_next.effective_due_date as contract_next_unpaid_date,
                        coalesce(contract_next.unpaid_amount, 0)::numeric(18,2)
                            as contract_next_unpaid_amount,
                        today.entry_type is not null as processed_today,
                        coalesce(today.entry_type, '') as today_entry_type,
                        coalesce(today.collector_name, '') as today_collector_name,
                        today.transaction_id as today_transaction_id,
                        today.collector_user_id as today_collector_user_id,
                        today.assigned_collector_user_id as today_assigned_collector_user_id,
                        coalesce(today.collection_origin, '') as today_collection_origin,
                        coalesce(today.is_locked, false) as today_is_locked,
                        coalesce(today.amount, 0) as today_amount,
                        coalesce(today.note, '') as today_note,
                        coalesce(today.covered_dates, ARRAY[]::date[]) as today_covered_dates,
                        coalesce(today.receipts, '[]'::jsonb) as today_receipts,
                        coalesce(coverage.covered_dates, ARRAY[]::date[]) as covered_dates
                    from lending.clients c
                    join lateral (
                        select
                            assignment.area as assignment_area,
                            assignment.sort_order
                        from lending.collector_area_assignments assignment
                        where assignment.collector_user_id = %s
                          and assignment.is_active = true
                          and lending.area_path_contains(
                              assignment.area,
                              coalesce(c.area, ''),
                              true
                          )
                        order by
                            char_length(lending.normalize_area_path(assignment.area)) desc,
                            assignment.sort_order,
                            lower(lending.normalize_area_path(assignment.area)),
                            assignment.id
                        limit 1
                    ) route_assignment on true
                    join lending.loans l
                      on l.client_id = c.id
                     and l.status = 'active'
                    join lending.loan_types lt
                      on lt.id = l.loan_type_id
                     and lt.is_active = true
                    left join lending.loan_collection_state s
                      on s.loan_id = l.id
                    left join accounting.loan_contract_dpd_assessment assessment
                      on assessment.loan_id = l.id
                    left join lending.loan_contract_schedule_registrations registration
                      on registration.schedule_id = assessment.schedule_id
                    left join lateral (
                        select
                            coalesce(bool_or(cd.covered_date = %s), false) as covered_today,
                            coalesce(
                                array_agg(cd.covered_date order by cd.covered_date)
                                    filter (where cd.covered_date >= %s),
                                ARRAY[]::date[]
                            ) as covered_dates
                        from lending.collection_covered_dates cd
                        where cd.loan_id = l.id
                    ) coverage on true
                    left join lateral (
                        select
                            t.id as transaction_id,
                            t.entry_type,
                            t.amount,
                            t.note,
                            t.collector_user_id,
                            t.assigned_collector_user_id,
                            t.collection_origin,
                            t.is_locked,
                            coalesce(
                                array(
                                    select cd.covered_date
                                    from lending.collection_covered_dates cd
                                    where cd.transaction_id = t.id
                                    order by cd.covered_date
                                ),
                                ARRAY[]::date[]
                            ) as covered_dates,
                            coalesce(
                                nullif(btrim(u.full_name), ''),
                                nullif(btrim(u.username), ''),
                                'Collector'
                            ) as collector_name,
                            coalesce((
                                select jsonb_agg(
                                    jsonb_build_object(
                                        'transaction_id', receipt.id,
                                        'receipt_number', receipt.receipt_number,
                                        'amount', receipt.amount,
                                        'entry_type', receipt.entry_type,
                                        'collector_user_id', receipt.collector_user_id,
                                        'collector_name', coalesce(
                                            nullif(btrim(receipt_user.full_name), ''),
                                            nullif(btrim(receipt_user.username), ''),
                                            'Collector'
                                        ),
                                        'is_locked', receipt.is_locked,
                                        'note', receipt.note,
                                        'accepted_at', receipt.accepted_at,
                                        'covered_dates', coalesce((
                                            select jsonb_agg(
                                                receipt_date.covered_date
                                                order by receipt_date.covered_date
                                            )
                                            from lending.collection_covered_dates receipt_date
                                            where receipt_date.transaction_id = receipt.id
                                        ), '[]'::jsonb)
                                    )
                                    order by receipt.accepted_at, receipt.id
                                )
                                from lending.collection_transactions receipt
                                left join core.users receipt_user
                                  on receipt_user.id = receipt.collector_user_id
                                where receipt.loan_id = l.id
                                  and receipt.collection_date = t.collection_date
                                  and receipt.is_voided = false
                                  and receipt.entry_type in ('payment', 'advance')
                            ), '[]'::jsonb) as receipts
                        from lending.collection_transactions t
                        left join core.users u
                          on u.id = t.collector_user_id
                        where t.loan_id = l.id
                          and t.collection_date = %s
                          and t.is_voided = false
                        order by t.accepted_at desc, t.id desc
                        limit 1
                    ) today on true
                    left join lateral (
                        select
                            count(installment.id)::bigint as installment_count,
                            coalesce(sum(installment.contractual_amount), 0)::numeric(18,2)
                                as scheduled_amount,
                            coalesce(sum(greatest(
                                installment.contractual_amount
                                - coalesce(applied.allocated_amount, 0),
                                0
                            )), 0)::numeric(18,2) as unpaid_amount
                        from lending.loan_contract_installments_operational installment
                        left join lateral (
                            select coalesce(sum(allocation.amount_applied) filter (
                                where transaction.is_voided = false
                            ), 0)::numeric(18,2) as allocated_amount
                            from lending.loan_installment_payment_allocations allocation
                            join lending.collection_transactions transaction
                              on transaction.id = allocation.transaction_id
                            where allocation.installment_id = installment.id
                        ) applied on true
                        where installment.schedule_id = assessment.schedule_id
                          and installment.effective_due_date = %s
                    ) contract_today on true
                    left join lateral (
                        select
                            balance.effective_due_date,
                            sum(balance.remaining_amount)::numeric(18,2) as unpaid_amount
                        from (
                            select
                                installment.id,
                                installment.effective_due_date,
                                greatest(
                                    installment.contractual_amount
                                    - coalesce(sum(allocation.amount_applied) filter (
                                        where transaction.is_voided = false
                                    ), 0),
                                    0
                                )::numeric(18,2) as remaining_amount
                            from lending.loan_contract_installments_operational installment
                            left join lending.loan_installment_payment_allocations allocation
                              on allocation.installment_id = installment.id
                            left join lending.collection_transactions transaction
                              on transaction.id = allocation.transaction_id
                            where installment.schedule_id = assessment.schedule_id
                            group by
                                installment.id,
                                installment.effective_due_date,
                                installment.contractual_amount
                        ) balance
                        where balance.remaining_amount > 0
                        group by balance.effective_due_date
                        order by balance.effective_due_date
                        limit 1
                    ) contract_next on true
                    where c.status = 'active'
                      and lending.collector_area_owner(coalesce(c.area, '')) = %s
                      and coalesce(s.remaining_balance, l.principal) > 0
                    order by
                        route_assignment.sort_order,
                        lower(lending.normalize_area_path(route_assignment.assignment_area)),
                        lower(coalesce(c.area, '')),
                        lower(c.full_name),
                        l.date_released,
                        l.id
                    """,
                    (
                        CONTRACT_ALLOCATION_SETTING,
                        collector_user_id,
                        route_date,
                        route_date,
                        route_date,
                        route_date,
                        collector_user_id,
                    ),
                )
                rows = cursor.fetchall()

        entries: list[CollectorRouteEntryRecord] = []
        for row in rows:
            remaining_balance = Decimal(row["remaining_balance"]).quantize(MONEY)
            contract_schedule_total = Decimal(row["contract_schedule_total"]).quantize(MONEY)
            contract_allocated_total = Decimal(row["contract_allocated_total"]).quantize(MONEY)
            contract_unpaid_total = (contract_schedule_total - contract_allocated_total).quantize(MONEY)
            contract_dpd_status = str(row["contract_dpd_status"] or "contract_schedule_required")
            contract_schedule_verified = bool(row["contract_schedule_verified"])
            contract_balance_reconciled = (
                contract_dpd_status == "ready"
                and remaining_balance == contract_unpaid_total
            )
            accounting_safe = not (
                bool(row["contract_automatic_default"])
                or bool(row["contract_ecl_included"])
                or row["contract_ecl_amount"] is not None
                or bool(row["contract_ready_to_post"])
            )
            contract_schedule_ready = (
                contract_schedule_verified
                and contract_dpd_status == "ready"
                and contract_balance_reconciled
                and accounting_safe
            )
            contract_allocation_enabled = bool(row["contract_allocation_enabled"])
            contract_collection_ready = (
                contract_allocation_enabled and contract_schedule_ready
            )
            today_scheduled = Decimal(row["contract_today_scheduled_amount"]).quantize(MONEY)
            today_unpaid = Decimal(row["contract_today_unpaid_amount"]).quantize(MONEY)
            today_has_installment = int(row["contract_today_installment_count"]) > 0

            entries.append(
                CollectorRouteEntryRecord(
                    route_entry_id=row["route_entry_id"],
                    client_id=row["client_id"],
                    loan_id=row["loan_id"],
                    client_name=row["client_name"],
                    area=row["area"] or "",
                    loan_type=row["loan_type"],
                    daily_amount=row["daily_amount"],
                    remaining_balance=remaining_balance,
                    pass_count=row["pass_count"],
                    last_payment_date=row["last_payment_date"],
                    advance_until=row["advance_until"],
                    status=row["collection_status"],
                    note=row["note"],
                    state_version=int(row["state_version"]),
                    is_reconciled=bool(row["is_reconciled"]),
                    mobile_collections_enabled=bool(row["mobile_collections_enabled"]),
                    mobile_balance_mode=str(row["mobile_balance_mode"] or ""),
                    contract_allocation_enabled=contract_allocation_enabled,
                    contract_schedule_verified=contract_schedule_verified,
                    contract_dpd_status=contract_dpd_status,
                    contract_payment_frequency=str(row["contract_payment_frequency"] or ""),
                    contract_reference=str(row["contract_reference"] or ""),
                    contract_schedule_version=(
                        int(row["contract_schedule_version"])
                        if row["contract_schedule_version"] is not None
                        else None
                    ),
                    contract_grace_days=int(row["contract_grace_days"] or 0),
                    contract_balance_reconciled=contract_balance_reconciled,
                    contract_schedule_ready=contract_schedule_ready,
                    contract_collection_ready=contract_collection_ready,
                    contract_days_past_due=(
                        int(row["contract_days_past_due"])
                        if row["contract_days_past_due"] is not None
                        else None
                    ),
                    contract_today_scheduled_amount=today_scheduled,
                    contract_today_unpaid_amount=today_unpaid,
                    contract_today_already_covered=(
                        today_has_installment
                        and today_scheduled > Decimal("0.00")
                        and today_unpaid == Decimal("0.00")
                    ),
                    contract_next_unpaid_date=row["contract_next_unpaid_date"],
                    contract_next_unpaid_amount=Decimal(
                        row["contract_next_unpaid_amount"]
                    ).quantize(MONEY),
                    processed_today=bool(row["processed_today"]),
                    today_entry_type=str(row["today_entry_type"] or ""),
                    today_collector_name=str(row["today_collector_name"] or ""),
                    today_transaction_id=row["today_transaction_id"],
                    today_collector_user_id=row["today_collector_user_id"],
                    today_is_locked=bool(row["today_is_locked"]),
                    can_edit_today=(
                        row["today_transaction_id"] is not None
                        and not bool(row["today_is_locked"])
                        and (
                            row["today_collector_user_id"] == collector_user_id
                            or (
                                str(row["today_collection_origin"] or "")
                                == "cross_collector"
                                and row["today_assigned_collector_user_id"]
                                == collector_user_id
                            )
                        )
                    ),
                    today_amount=Decimal(row["today_amount"]),
                    today_note=str(row["today_note"] or ""),
                    today_covered_dates=tuple(row["today_covered_dates"] or ()),
                    today_receipts=_receipt_records(row.get("today_receipts")),
                    covered_dates=tuple(row["covered_dates"] or ()),
                )
            )

        return CollectorRouteRecord(
            route_date=route_date,
            collector_name=collector_name,
            areas=areas,
            entries=tuple(entries),
        )
