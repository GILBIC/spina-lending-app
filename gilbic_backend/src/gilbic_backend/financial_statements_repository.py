from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection


ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class AccountingStatementPeriod:
    period_id: UUID
    label: str
    start_date: date
    end_date: date
    status: str


@dataclass(frozen=True, slots=True)
class AccountMovement:
    account_code: str
    account_name: str
    account_type: str
    normal_balance: str
    total_debit: Decimal
    total_credit: Decimal


@dataclass(frozen=True, slots=True)
class FinancialStatementLine:
    account_code: str
    account_name: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class FinancialStatementPack:
    period: AccountingStatementPeriod
    income_lines: tuple[FinancialStatementLine, ...]
    expense_lines: tuple[FinancialStatementLine, ...]
    total_income: Decimal
    total_expenses: Decimal
    net_income: Decimal
    asset_lines: tuple[FinancialStatementLine, ...]
    liability_lines: tuple[FinancialStatementLine, ...]
    equity_lines: tuple[FinancialStatementLine, ...]
    total_assets: Decimal
    total_liabilities: Decimal
    recorded_equity: Decimal
    unclosed_earnings_to_date: Decimal
    total_equity: Decimal
    total_liabilities_and_equity: Decimal
    balanced: bool


class FinancialStatementsError(RuntimeError):
    code = "financial_statements_error"


class StatementPeriodNotFound(FinancialStatementsError):
    code = "financial_statement_period_not_found"


def _amount_for_type(movement: AccountMovement) -> Decimal:
    if movement.account_type in {"asset", "expense"}:
        return movement.total_debit - movement.total_credit
    return movement.total_credit - movement.total_debit


def _lines_for_type(
    movements: tuple[AccountMovement, ...],
    account_type: str,
) -> tuple[FinancialStatementLine, ...]:
    return tuple(
        FinancialStatementLine(
            account_code=item.account_code,
            account_name=item.account_name,
            amount=_amount_for_type(item),
        )
        for item in movements
        if item.account_type == account_type and _amount_for_type(item) != ZERO
    )


def build_financial_statement_pack(
    *,
    period: AccountingStatementPeriod,
    period_movements: tuple[AccountMovement, ...],
    cumulative_movements: tuple[AccountMovement, ...],
) -> FinancialStatementPack:
    """Build read-only statements from posted General Ledger movements.

    Profit or loss uses movements inside the selected fiscal period. The
    statement of financial position uses cumulative posted balances through the
    selected period end date. Income and expense balances that have not yet
    been formally closed to retained earnings are presented as unclosed
    earnings so the accounting equation remains explicit and auditable.
    """

    income_lines = _lines_for_type(period_movements, "income")
    expense_lines = _lines_for_type(period_movements, "expense")
    total_income = sum((line.amount for line in income_lines), ZERO)
    total_expenses = sum((line.amount for line in expense_lines), ZERO)
    net_income = total_income - total_expenses

    asset_lines = _lines_for_type(cumulative_movements, "asset")
    liability_lines = _lines_for_type(cumulative_movements, "liability")
    equity_lines = _lines_for_type(cumulative_movements, "equity")
    cumulative_income = _lines_for_type(cumulative_movements, "income")
    cumulative_expenses = _lines_for_type(cumulative_movements, "expense")

    total_assets = sum((line.amount for line in asset_lines), ZERO)
    total_liabilities = sum((line.amount for line in liability_lines), ZERO)
    recorded_equity = sum((line.amount for line in equity_lines), ZERO)
    unclosed_earnings_to_date = (
        sum((line.amount for line in cumulative_income), ZERO)
        - sum((line.amount for line in cumulative_expenses), ZERO)
    )
    total_equity = recorded_equity + unclosed_earnings_to_date
    total_liabilities_and_equity = total_liabilities + total_equity

    return FinancialStatementPack(
        period=period,
        income_lines=income_lines,
        expense_lines=expense_lines,
        total_income=total_income,
        total_expenses=total_expenses,
        net_income=net_income,
        asset_lines=asset_lines,
        liability_lines=liability_lines,
        equity_lines=equity_lines,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        recorded_equity=recorded_equity,
        unclosed_earnings_to_date=unclosed_earnings_to_date,
        total_equity=total_equity,
        total_liabilities_and_equity=total_liabilities_and_equity,
        balanced=total_assets == total_liabilities_and_equity,
    )


class PostgresFinancialStatementsRepository:
    def load_statement_pack(
        self,
        *,
        period_id: UUID | None = None,
    ) -> FinancialStatementPack:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                period = self._load_period(cursor, period_id)
                period_movements = self._load_movements(
                    cursor,
                    period_id=period.period_id,
                    through_date=None,
                    exclude_period_close=True,
                )
                cumulative_movements = self._load_movements(
                    cursor,
                    period_id=None,
                    through_date=period.end_date,
                    exclude_period_close=False,
                )
                return build_financial_statement_pack(
                    period=period,
                    period_movements=period_movements,
                    cumulative_movements=cumulative_movements,
                )

    @staticmethod
    def _load_period(cursor, period_id: UUID | None) -> AccountingStatementPeriod:
        if period_id is None:
            cursor.execute(
                """
                select id, label, start_date, end_date, status
                from accounting.fiscal_periods
                order by end_date desc, start_date desc
                limit 1
                """
            )
        else:
            cursor.execute(
                """
                select id, label, start_date, end_date, status
                from accounting.fiscal_periods
                where id = %s
                """,
                (period_id,),
            )
        row = cursor.fetchone()
        if row is None:
            raise StatementPeriodNotFound("Accounting period was not found.")
        return AccountingStatementPeriod(
            period_id=UUID(str(row["id"])),
            label=str(row["label"]),
            start_date=row["start_date"],
            end_date=row["end_date"],
            status=str(row["status"]),
        )

    @staticmethod
    def _load_movements(
        cursor,
        *,
        period_id: UUID | None,
        through_date: date | None,
        exclude_period_close: bool,
    ) -> tuple[AccountMovement, ...]:
        cursor.execute(
            """
            select
                account.code,
                account.name,
                account.account_type,
                account.normal_balance,
                coalesce(sum(line.debit) filter (
                    where journal.status = 'posted'
                      and (%s::uuid is null or journal.fiscal_period_id = %s::uuid)
                      and (%s::date is null or journal.posting_date <= %s::date)
                      and (%s::boolean = false or coalesce(journal.source_type, '') <> 'period_close')
                ), 0) as total_debit,
                coalesce(sum(line.credit) filter (
                    where journal.status = 'posted'
                      and (%s::uuid is null or journal.fiscal_period_id = %s::uuid)
                      and (%s::date is null or journal.posting_date <= %s::date)
                      and (%s::boolean = false or coalesce(journal.source_type, '') <> 'period_close')
                ), 0) as total_credit
            from accounting.accounts account
            left join accounting.journal_lines line
              on line.account_id = account.id
            left join accounting.journal_entries journal
              on journal.id = line.journal_entry_id
            group by account.id
            order by account.code
            """,
            (
                period_id,
                period_id,
                through_date,
                through_date,
                exclude_period_close,
                period_id,
                period_id,
                through_date,
                through_date,
                exclude_period_close,
            ),
        )
        return tuple(
            AccountMovement(
                account_code=str(row["code"]),
                account_name=str(row["name"]),
                account_type=str(row["account_type"]),
                normal_balance=str(row["normal_balance"]),
                total_debit=Decimal(row["total_debit"] or 0),
                total_credit=Decimal(row["total_credit"] or 0),
            )
            for row in cursor.fetchall()
        )
