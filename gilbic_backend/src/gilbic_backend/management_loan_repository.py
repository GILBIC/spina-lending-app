from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection


@dataclass(frozen=True, slots=True)
class ManagementLoanSummary:
    active_loan_count: int
    active_client_count: int
    active_principal_total: Decimal
    active_remaining_total: Decimal
    overdue_active_count: int
    active_seven_by_seven_count: int
    approved_renewal_count: int


@dataclass(frozen=True, slots=True)
class ManagementLoanRecord:
    loan_id: UUID
    loan_number: str
    client_id: UUID
    client_code: str
    client_name: str
    client_area: str | None
    client_status: str
    loan_type_code: str | None
    loan_type_name: str
    calculation_mode: str
    principal: Decimal
    daily_amount: Decimal
    interest_rate: Decimal | None
    remaining_balance: Decimal
    date_released: date | None
    due_date: date | None
    loan_status: str
    last_payment_date: date | None
    advance_until: date | None
    pass_count: int
    payment_count: int
    state_version: int
    renewal_request_status: str | None

    @property
    def paid_amount(self) -> Decimal:
        value = self.principal - self.remaining_balance
        return value if value > 0 else Decimal("0.00")

    @property
    def paid_percent(self) -> Decimal:
        if self.principal <= 0:
            return Decimal("0.0")
        return (self.paid_amount / self.principal * Decimal("100")).quantize(
            Decimal("0.1")
        )

    @property
    def is_overdue(self) -> bool:
        return (
            self.loan_status.lower() == "active"
            and self.due_date is not None
            and self.due_date < date.today()
            and self.remaining_balance > 0
        )


@dataclass(frozen=True, slots=True)
class ManagementLoanPortfolio:
    summary: ManagementLoanSummary
    loans: tuple[ManagementLoanRecord, ...]


class PostgresManagementLoanRepository:
    def list_portfolio(
        self,
        *,
        query: str,
        status: str,
        limit: int,
        offset: int,
    ) -> ManagementLoanPortfolio:
        normalized_query = " ".join(query.split())
        pattern = f"%{normalized_query}%"
        normalized_status = status.strip().lower()

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        count(*) filter (where lower(loan.status) = 'active')
                            as active_loan_count,
                        count(distinct loan.client_id) filter (
                            where lower(loan.status) = 'active'
                        ) as active_client_count,
                        coalesce(sum(loan.principal) filter (
                            where lower(loan.status) = 'active'
                        ), 0) as active_principal_total,
                        coalesce(sum(coalesce(state.remaining_balance, loan.principal)) filter (
                            where lower(loan.status) = 'active'
                        ), 0) as active_remaining_total,
                        count(*) filter (
                            where lower(loan.status) = 'active'
                              and loan.due_date < current_date
                              and coalesce(state.remaining_balance, loan.principal) > 0
                        ) as overdue_active_count,
                        count(*) filter (
                            where lower(loan.status) = 'active'
                              and lower(coalesce(loan_type.calculation_mode, '')) = 'seven_by_seven'
                        ) as active_seven_by_seven_count,
                        (
                            select count(*)
                            from lending.client_renewal_requests request
                            where request.status = 'approved'
                        ) as approved_renewal_count
                    from lending.loans loan
                    left join lending.loan_types loan_type
                      on loan_type.id = loan.loan_type_id
                    left join lending.loan_collection_state state
                      on state.loan_id = loan.id
                    """
                )
                summary_row = cursor.fetchone()

                cursor.execute(
                    """
                    select
                        loan.id as loan_id,
                        loan.loan_number,
                        client.id as client_id,
                        client.client_code,
                        client.full_name as client_name,
                        client.area as client_area,
                        client.status as client_status,
                        loan_type.code as loan_type_code,
                        coalesce(nullif(btrim(loan_type.name), ''), 'Loan')
                            as loan_type_name,
                        coalesce(loan_type.calculation_mode, '')
                            as calculation_mode,
                        loan.principal,
                        loan.daily_amount,
                        loan.interest_rate,
                        coalesce(state.remaining_balance, loan.principal)
                            as remaining_balance,
                        loan.date_released,
                        loan.due_date,
                        loan.status as loan_status,
                        state.last_payment_date,
                        state.advance_until,
                        coalesce(state.pass_count, 0) as pass_count,
                        coalesce(state.state_version, 0) as state_version,
                        coalesce((
                            select count(*)
                            from lending.collection_transactions item
                            where item.loan_id = loan.id
                              and item.is_voided = false
                              and item.amount > 0
                        ), 0) as payment_count,
                        renewal.status as renewal_request_status
                    from lending.loans loan
                    join lending.clients client on client.id = loan.client_id
                    left join lending.loan_types loan_type
                      on loan_type.id = loan.loan_type_id
                    left join lending.loan_collection_state state
                      on state.loan_id = loan.id
                    left join lateral (
                        select request.status
                        from lending.client_renewal_requests request
                        where request.client_id = loan.client_id
                          and request.loan_id = loan.id
                          and request.status in ('pending', 'approved')
                        order by
                            case when request.status = 'approved' then 0 else 1 end,
                            request.submitted_at desc
                        limit 1
                    ) renewal on true
                    where (%s = 'all' or lower(loan.status) = %s)
                      and (
                        %s = ''
                        or client.full_name ilike %s
                        or client.client_code ilike %s
                        or loan.loan_number ilike %s
                        or coalesce(client.area, '') ilike %s
                      )
                    order by
                        case when lower(loan.status) = 'active' then 0 else 1 end,
                        case
                            when lower(loan.status) = 'active'
                             and loan.due_date < current_date
                             and coalesce(state.remaining_balance, loan.principal) > 0
                            then 0 else 1
                        end,
                        loan.due_date asc nulls last,
                        client.full_name,
                        loan.created_at desc
                    limit %s offset %s
                    """,
                    (
                        normalized_status,
                        normalized_status,
                        normalized_query,
                        pattern,
                        pattern,
                        pattern,
                        pattern,
                        limit,
                        offset,
                    ),
                )
                loan_rows = cursor.fetchall()

        return ManagementLoanPortfolio(
            summary=ManagementLoanSummary(
                active_loan_count=int(summary_row["active_loan_count"] or 0),
                active_client_count=int(summary_row["active_client_count"] or 0),
                active_principal_total=Decimal(
                    summary_row["active_principal_total"] or 0
                ),
                active_remaining_total=Decimal(
                    summary_row["active_remaining_total"] or 0
                ),
                overdue_active_count=int(summary_row["overdue_active_count"] or 0),
                active_seven_by_seven_count=int(
                    summary_row["active_seven_by_seven_count"] or 0
                ),
                approved_renewal_count=int(
                    summary_row["approved_renewal_count"] or 0
                ),
            ),
            loans=tuple(self._record_from_row(row) for row in loan_rows),
        )

    @staticmethod
    def _record_from_row(row) -> ManagementLoanRecord:
        return ManagementLoanRecord(
            loan_id=row["loan_id"],
            loan_number=str(row["loan_number"]),
            client_id=row["client_id"],
            client_code=str(row["client_code"]),
            client_name=str(row["client_name"]),
            client_area=(str(row["client_area"]) if row["client_area"] else None),
            client_status=str(row["client_status"]),
            loan_type_code=(
                str(row["loan_type_code"]) if row["loan_type_code"] else None
            ),
            loan_type_name=str(row["loan_type_name"]),
            calculation_mode=str(row["calculation_mode"]),
            principal=Decimal(row["principal"]),
            daily_amount=Decimal(row["daily_amount"]),
            interest_rate=(
                Decimal(row["interest_rate"])
                if row["interest_rate"] is not None
                else None
            ),
            remaining_balance=Decimal(row["remaining_balance"]),
            date_released=row["date_released"],
            due_date=row["due_date"],
            loan_status=str(row["loan_status"]),
            last_payment_date=row["last_payment_date"],
            advance_until=row["advance_until"],
            pass_count=int(row["pass_count"]),
            payment_count=int(row["payment_count"]),
            state_version=int(row["state_version"]),
            renewal_request_status=(
                str(row["renewal_request_status"])
                if row["renewal_request_status"]
                else None
            ),
        )
