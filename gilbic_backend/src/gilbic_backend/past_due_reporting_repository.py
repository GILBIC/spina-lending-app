from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection


PAST_DUE_REASON_CODES = frozenset(
    {
        "no_cash",
        "client_absent",
        "business_slow",
        "sick_hospital",
        "emergency",
        "promised_to_pay_later",
        "other",
    }
)
PAST_DUE_EVENT_KINDS = frozenset({"unable_to_pay", "partial_payment"})


@dataclass(frozen=True, slots=True)
class PastDueReasonReportRow:
    client_id: UUID
    client_name: str
    collector_user_id: UUID
    collector_name: str
    area: str
    reason_code: str
    event_kind: str
    event_count: int
    total_past_due_amount: Decimal
    remaining_past_due_amount: Decimal


@dataclass(frozen=True, slots=True)
class PastDueReasonReport:
    schema_available: bool
    rows: tuple[PastDueReasonReportRow, ...]


class PostgresPastDueReportingRepository:
    def report_reason_summary(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        client_id: UUID | None = None,
        collector_user_id: UUID | None = None,
        area: str | None = None,
        reason_code: str | None = None,
        event_kind: str | None = None,
        limit: int = 500,
    ) -> PastDueReasonReport:
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ValueError("start_date cannot be after end_date.")

        normalized_reason = reason_code.strip().lower() if reason_code else None
        if normalized_reason is not None and normalized_reason not in PAST_DUE_REASON_CODES:
            raise ValueError("Unknown Past Due reason code.")

        normalized_kind = event_kind.strip().lower() if event_kind else None
        if normalized_kind is not None and normalized_kind not in PAST_DUE_EVENT_KINDS:
            raise ValueError("Unknown Past Due event kind.")

        normalized_area = " ".join(area.split()) if area else None
        safe_limit = min(max(limit, 1), 500)

        with open_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("select to_regclass('lending.past_due_obligations')", ())
                if cursor.fetchone()[0] is None:
                    return PastDueReasonReport(schema_available=False, rows=())

            conditions = ["1 = 1"]
            parameters: list[object] = []
            if start_date is not None:
                conditions.append("p.obligation_date >= %s")
                parameters.append(start_date)
            if end_date is not None:
                conditions.append("p.obligation_date <= %s")
                parameters.append(end_date)
            if client_id is not None:
                conditions.append("p.client_id = %s")
                parameters.append(client_id)
            if collector_user_id is not None:
                conditions.append("p.created_by_user_id = %s")
                parameters.append(collector_user_id)
            if normalized_area:
                conditions.append("lower(btrim(coalesce(c.area, ''))) = lower(%s)")
                parameters.append(normalized_area)
            if normalized_reason is not None:
                conditions.append("p.current_reason_code = %s")
                parameters.append(normalized_reason)
            if normalized_kind is not None:
                conditions.append("p.event_kind = %s")
                parameters.append(normalized_kind)

            parameters.append(safe_limit)
            query = f"""
                select
                    p.client_id,
                    c.full_name as client_name,
                    p.created_by_user_id as collector_user_id,
                    u.full_name as collector_name,
                    coalesce(c.area, '') as area,
                    p.current_reason_code as reason_code,
                    p.event_kind,
                    count(*)::bigint as event_count,
                    coalesce(sum(p.original_past_due_amount), 0)::numeric(18,2)
                        as total_past_due_amount,
                    coalesce(sum(p.remaining_past_due_amount), 0)::numeric(18,2)
                        as remaining_past_due_amount
                from lending.past_due_obligations p
                join lending.clients c on c.id = p.client_id
                join core.users u on u.id = p.created_by_user_id
                where {' and '.join(conditions)}
                group by
                    p.client_id,
                    c.full_name,
                    p.created_by_user_id,
                    u.full_name,
                    coalesce(c.area, ''),
                    p.current_reason_code,
                    p.event_kind
                order by
                    total_past_due_amount desc,
                    event_count desc,
                    c.full_name,
                    u.full_name,
                    p.current_reason_code,
                    p.event_kind
                limit %s
            """
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(query, tuple(parameters))
                rows = cursor.fetchall()

        return PastDueReasonReport(
            schema_available=True,
            rows=tuple(self._row_from_mapping(row) for row in rows),
        )

    @staticmethod
    def _row_from_mapping(row: dict[str, object]) -> PastDueReasonReportRow:
        return PastDueReasonReportRow(
            client_id=row["client_id"],
            client_name=str(row["client_name"]),
            collector_user_id=row["collector_user_id"],
            collector_name=str(row["collector_name"]),
            area=str(row["area"] or ""),
            reason_code=str(row["reason_code"]),
            event_kind=str(row["event_kind"]),
            event_count=int(row["event_count"]),
            total_past_due_amount=Decimal(row["total_past_due_amount"]),
            remaining_past_due_amount=Decimal(row["remaining_past_due_amount"]),
        )
