from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row

from .accounting_book_repository import AccountingBookIdentity, read_book_identity
from .database import open_connection
from .financial_reporting import cash_flow_statement, equity_rollforward, money
from .journal_disclosure_repository import read_journal_disclosures
from .reporting_evidence_repository import (
    read_internal_collector_cash,
    read_internal_transfer_principals,
    read_reporting_policy,
)

ZERO = Decimal(0)


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
    book_identity: AccountingBookIdentity | None = None
    reporting_supplement: dict | None = None


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
    book_identity: AccountingBookIdentity | None = None,
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
    unclosed_earnings_to_date = sum(
        (line.amount for line in cumulative_income), ZERO
    ) - sum((line.amount for line in cumulative_expenses), ZERO)
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
        book_identity=book_identity,
    )


class PostgresFinancialStatementsRepository:
    def load_statement_pack(
        self,
        *,
        period_id: UUID | None = None,
        actor_user_id: UUID | None = None,
    ) -> FinancialStatementPack:
        with (
            open_connection() as connection,
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            # Profit and cumulative balances must describe the same ledger,
            # even if another session posts while this pack is being read.
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            book_identity = read_book_identity(cursor)
            period = self._load_period(cursor, period_id)
            disclosure_actor = None
            if actor_user_id is not None:
                cursor.execute(
                    "SELECT to_regclass('accounting.journal_disclosure_reviews') AS relation"
                )
                if cursor.fetchone()["relation"] is not None:
                    cursor.execute(
                        "SELECT accounting.require_disclosure_actor(%s,%s,'accounting.view')",
                        (actor_user_id, period.period_id),
                    )
                    disclosure_actor = actor_user_id
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
            pack = build_financial_statement_pack(
                period=period,
                period_movements=period_movements,
                cumulative_movements=cumulative_movements,
                book_identity=book_identity,
            )
            return replace(
                pack,
                reporting_supplement=self._supplement(
                    cursor, pack, period_movements, disclosure_actor=disclosure_actor
                ),
            )

    def _supplement(
        self,
        cursor,
        pack,
        period_movements,
        *,
        include_comparative=True,
        disclosure_actor=None,
    ):
        opening = self._load_movements(
            cursor,
            period_id=None,
            through_date=pack.period.start_date - timedelta(days=1),
            exclude_period_close=False,
        )
        opening_equity = sum(
            (
                item.total_credit - item.total_debit
                for item in opening
                if item.account_type in {"equity", "income", "expense"}
            ),
            ZERO,
        )
        equity = equity_rollforward(
            pack, opening_equity=opening_equity, equity_movements=period_movements
        )
        policy = read_reporting_policy(cursor, pack.period.period_id)
        lines = []
        opening_cash = closing_cash = None
        noncash = []
        if policy and policy["cash_definition_valid"]:
            codes = policy["cash_account_codes"]
            opening_cash = sum(
                (
                    item.total_debit - item.total_credit
                    for item in opening
                    if item.account_code in codes
                ),
                ZERO,
            )
            closing_cash = sum(
                (
                    item.amount
                    for item in pack.asset_lines
                    if item.account_code in codes
                ),
                ZERO,
            )
            cursor.execute(
                """SELECT line.id AS journal_line_id,journal.id AS journal_entry_id,
                account.code AS account_code,line.debit-line.credit AS amount,journal.entry_number,journal.source_type,
                reviewed.payload->'allocations' AS allocations,coalesce(reviewed.version,0) AS classification_version,
                (journal.source_type='opening_balance' OR EXISTS(SELECT 1 FROM accounting.journal_entries original
                    WHERE original.id=journal.reversal_of_entry_id AND original.source_type='opening_balance')) AS is_opening_adjustment
                FROM accounting.journal_lines line JOIN accounting.journal_entries journal ON journal.id=line.journal_entry_id
                JOIN accounting.accounts account ON account.id=line.account_id
                LEFT JOIN LATERAL (SELECT version,payload FROM accounting.cash_flow_classifications item
                    WHERE item.policy_id=%s AND item.journal_line_id=line.id ORDER BY version DESC LIMIT 1) reviewed ON true
                WHERE journal.status='posted' AND journal.fiscal_period_id=%s AND account.code=ANY(%s)
                ORDER BY journal.posting_date,journal.id,line.line_number""",
                (UUID(policy["id"]), pack.period.period_id, codes),
            )
            lines = list(cursor.fetchall())
            transfer_principals = read_internal_transfer_principals(
                cursor, pack.period.period_id
            )
            collector_cash = read_internal_collector_cash(cursor, pack.period.period_id)
            lines = [
                line
                | {
                    "internal_transfer": transfer_principals.get(
                        line["journal_line_id"]
                    ),
                    "collector_cash": collector_cash.get(line["journal_line_id"]),
                }
                for line in lines
            ]
            cursor.execute(
                """SELECT journal.id AS journal_entry_id,journal.entry_number,journal.posting_date,
                journal.source_type,sum(line.debit) AS gross_debit
                FROM accounting.journal_entries journal JOIN accounting.journal_lines line ON line.journal_entry_id=journal.id
                JOIN accounting.accounts account ON account.id=line.account_id
                WHERE journal.status='posted' AND journal.fiscal_period_id=%s AND journal.source_type<>'period_close'
                GROUP BY journal.id HAVING NOT bool_or(account.code=ANY(%s))
                ORDER BY journal.posting_date,journal.id""",
                (pack.period.period_id, codes),
            )
            noncash = [
                {
                    "journal_entry_id": str(row["journal_entry_id"]),
                    "entry_number": row["entry_number"],
                    "posting_date": row["posting_date"].isoformat(),
                    "source_type": row["source_type"],
                    "gross_debit": money(row["gross_debit"]),
                }
                for row in cursor.fetchall()
            ]
        cash = cash_flow_statement(
            policy=policy,
            opening_cash=opening_cash,
            closing_cash=closing_cash,
            lines=lines,
        )
        cash["cash_lines"] = [
            {
                **{
                    key: str(row[key])
                    for key in (
                        "journal_line_id",
                        "journal_entry_id",
                        "account_code",
                        "entry_number",
                        "source_type",
                    )
                },
                "amount": money(row["amount"]),
                "classification_version": row["classification_version"],
                "allocations": row["allocations"],
                "is_opening_adjustment": row["is_opening_adjustment"],
            }
            for row in lines
        ]
        result = {
            "changes_in_equity": equity,
            "cash_flows": cash,
            "notes": {
                "status": "retained_management_notes"
                if policy
                else "reporting_policy_required",
                "items": policy["notes"] if policy else [],
                "framework_label": policy["framework_label"] if policy else None,
            },
            "noncash_activity": noncash,
            "noncash_disclosure_status": "mixed_transactions_require_review",
            "noncash_inventory_scope": "journals_with_no_cash_leg",
            "comparative": None,
            "notice": "These are posted-ledger reports. Retained notes and classifications are Management evidence; they do not certify statutory compliance or complete source recognition.",
        }
        if disclosure_actor is not None:
            disclosures = read_journal_disclosures(
                cursor, pack.period.period_id, disclosure_actor
            )
            result["journal_disclosures"] = disclosures
            result["noncash_disclosure_status"] = disclosures["status"]
            result["noncash_inventory_scope"] = "all_posted_journals"
        if include_comparative:
            cursor.execute(
                "SELECT id FROM accounting.fiscal_periods WHERE end_date<%s ORDER BY end_date DESC,start_date DESC LIMIT 1",
                (pack.period.start_date,),
            )
            prior = cursor.fetchone()
            if prior:
                period = self._load_period(cursor, prior["id"])
                # Explicit base implementation prevents instrumentation of the
                # selected-period read from being replayed for the comparative.
                movements = PostgresFinancialStatementsRepository._load_movements(
                    cursor,
                    period_id=period.period_id,
                    through_date=None,
                    exclude_period_close=True,
                )
                cumulative = self._load_movements(
                    cursor,
                    period_id=None,
                    through_date=period.end_date,
                    exclude_period_close=False,
                )
                previous = build_financial_statement_pack(
                    period=period,
                    period_movements=movements,
                    cumulative_movements=cumulative,
                    book_identity=pack.book_identity,
                )
                result["comparative"] = replace(
                    previous,
                    reporting_supplement=self._supplement(
                        cursor,
                        previous,
                        movements,
                        include_comparative=False,
                        disclosure_actor=disclosure_actor,
                    ),
                )
        return result

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
