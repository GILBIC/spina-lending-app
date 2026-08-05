from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection


class ClientLoanError(RuntimeError):
    code = "client_loan_error"


class ClientBorrowerNotLinked(ClientLoanError):
    code = "client_borrower_not_linked"


@dataclass(frozen=True, slots=True)
class ClientLoanRecord:
    loan_id: UUID
    loan_number: str
    loan_type_code: str | None
    loan_type_name: str
    principal: Decimal
    daily_amount: Decimal
    interest_rate: Decimal | None
    date_released: date | None
    due_date: date | None
    status: str
    remaining_balance: Decimal
    pass_count: int
    last_payment_date: date | None
    advance_until: date | None
    state_version: int
    payment_count: int

    @property
    def paid_amount(self) -> Decimal:
        paid = self.principal - self.remaining_balance
        return paid if paid > 0 else Decimal("0.00")


@dataclass(frozen=True, slots=True)
class ClientLoanPortfolio:
    client_id: UUID
    client_code: str
    client_name: str
    area: str | None
    client_status: str
    loans: tuple[ClientLoanRecord, ...]


class PostgresClientLoanRepository:
    def list_for_user(self, *, user_id: UUID) -> ClientLoanPortfolio:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select id, client_code, full_name, area, status
                    from lending.clients
                    where user_id = %s
                    limit 1
                    """,
                    (user_id,),
                )
                client = cursor.fetchone()
                if not client:
                    raise ClientBorrowerNotLinked(
                        "This client account is not linked to a borrower record."
                    )

                cursor.execute(
                    """
                    select
                        loan.id as loan_id,
                        loan.loan_number,
                        loan_type.code as loan_type_code,
                        coalesce(nullif(btrim(loan_type.name), ''), 'Loan')
                            as loan_type_name,
                        loan.principal,
                        loan.daily_amount,
                        loan.interest_rate,
                        loan.date_released,
                        loan.due_date,
                        loan.status,
                        coalesce(state.remaining_balance, loan.principal)
                            as remaining_balance,
                        coalesce(state.pass_count, 0) as pass_count,
                        state.last_payment_date,
                        state.advance_until,
                        coalesce(state.state_version, 0) as state_version,
                        coalesce(
                            (
                                select count(*)
                                from lending.collection_transactions transaction
                                where transaction.loan_id = loan.id
                                  and transaction.is_voided = false
                                  and transaction.amount > 0
                            ),
                            0
                        ) as payment_count
                    from lending.loans loan
                    left join lending.loan_types loan_type
                      on loan_type.id = loan.loan_type_id
                    left join lending.loan_collection_state state
                      on state.loan_id = loan.id
                    where loan.client_id = %s
                    order by
                        case when lower(loan.status) = 'active' then 0 else 1 end,
                        loan.date_released desc nulls last,
                        loan.created_at desc,
                        loan.id desc
                    """,
                    (client["id"],),
                )
                rows = cursor.fetchall()

        return ClientLoanPortfolio(
            client_id=client["id"],
            client_code=str(client["client_code"]),
            client_name=str(client["full_name"]),
            area=str(client["area"]) if client["area"] else None,
            client_status=str(client["status"]),
            loans=tuple(self._loan_from_row(row) for row in rows),
        )

    @staticmethod
    def _loan_from_row(row) -> ClientLoanRecord:
        return ClientLoanRecord(
            loan_id=row["loan_id"],
            loan_number=str(row["loan_number"]),
            loan_type_code=(
                str(row["loan_type_code"]) if row["loan_type_code"] else None
            ),
            loan_type_name=str(row["loan_type_name"]),
            principal=Decimal(row["principal"]),
            daily_amount=Decimal(row["daily_amount"]),
            interest_rate=(
                Decimal(row["interest_rate"])
                if row["interest_rate"] is not None
                else None
            ),
            date_released=row["date_released"],
            due_date=row["due_date"],
            status=str(row["status"]),
            remaining_balance=Decimal(row["remaining_balance"]),
            pass_count=int(row["pass_count"]),
            last_payment_date=row["last_payment_date"],
            advance_until=row["advance_until"],
            state_version=int(row["state_version"]),
            payment_count=int(row["payment_count"]),
        )
