from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


@dataclass(frozen=True, slots=True)
class FinancialAccountingSummary:
    active_loan_count: int
    active_principal: Decimal
    operational_outstanding: Decimal
    regular_outstanding: Decimal
    seven_by_seven_outstanding: Decimal
    unremitted_cash: Decimal
    received_remittance_total: Decimal
    valid_collection_count: int
    correction_count: int
    void_count: int


@dataclass(frozen=True, slots=True)
class AccountingFoundationSummary:
    account_count: int
    posting_account_count: int
    fiscal_period_count: int
    open_period_count: int
    journal_entry_count: int
    draft_journal_count: int
    posted_journal_count: int
    reversal_draft_count: int


@dataclass(frozen=True, slots=True)
class AccountingAccount:
    code: str
    system_key: str
    name: str
    account_type: str
    normal_balance: str
    is_posting: bool
    is_active: bool


@dataclass(frozen=True, slots=True)
class AccountingFiscalPeriod:
    period_id: UUID
    label: str
    start_date: date
    end_date: date
    status: str
    journal_count: int
    draft_journal_count: int
    posted_journal_count: int
    closed_by_name: str | None
    closed_at: datetime | None


@dataclass(frozen=True, slots=True)
class LoanAccountingPolicy:
    code: str
    name: str
    term_days: int
    calculation_mode: str
    daily_interest_per_1000: Decimal
    mobile_collections_enabled: bool
    operational_rule: str
    accounting_rule: str
    renewal_rule: str


@dataclass(frozen=True, slots=True)
class AccountingCutoverReadinessSummary:
    active_loan_count: int
    source_ready_count: int
    contract_validation_count: int
    blocked_count: int
    opening_balances_configured: bool
    automatic_source_posting_enabled: bool
    overall_status: str


@dataclass(frozen=True, slots=True)
class AccountingCutoverLoan:
    loan_number: str
    client_code: str
    client_name: str
    loan_type_name: str
    calculation_mode: str
    term_days: int
    principal: Decimal
    daily_amount: Decimal
    interest_rate: Decimal | None
    date_released: date
    due_date: date
    operational_balance: Decimal
    regular_contract_total: Decimal | None
    regular_scheduled_total: Decimal | None
    seven_by_seven_expected_daily_interest: Decimal | None
    seven_by_seven_contract_interest_total: Decimal | None
    seven_by_seven_contract_total_if_principal_at_maturity: Decimal | None
    seven_by_seven_base_daily_rate_percent: Decimal | None
    readiness_status: str
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OpeningBalanceCutoverSummary:
    cutover_date: date | None
    worksheet_status: str
    worksheet_line_count: int
    source_reference_count: int
    manual_required_count: int
    reconciliation_required_count: int
    calculation_required_count: int
    assessment_required_count: int
    profit_loss_migration_policy_required: bool
    worksheet_balanced: bool
    ready_to_post: bool
    opening_balance_posting_enabled: bool
    automatic_source_posting_enabled: bool


@dataclass(frozen=True, slots=True)
class OpeningBalanceCutoverLine:
    account_code: str
    system_key: str
    account_name: str
    account_type: str
    normal_balance: str
    source_reference_amount: Decimal | None
    source_basis: str
    readiness_status: str
    guidance: str


@dataclass(frozen=True, slots=True)
class FinancialAccountingOverview:
    summary: FinancialAccountingSummary
    foundation: AccountingFoundationSummary
    accounts: tuple[AccountingAccount, ...]
    fiscal_periods: tuple[AccountingFiscalPeriod, ...]
    policies: tuple[LoanAccountingPolicy, ...]
    cutover_summary: AccountingCutoverReadinessSummary
    cutover_loans: tuple[AccountingCutoverLoan, ...]
    opening_balance_summary: OpeningBalanceCutoverSummary
    opening_balance_lines: tuple[OpeningBalanceCutoverLine, ...]


class AccountingPeriodError(RuntimeError):
    code = "accounting_period_error"


class AccountingPeriodConflict(AccountingPeriodError):
    code = "accounting_period_conflict"


class AccountingPeriodNotFound(AccountingPeriodError):
    code = "accounting_period_not_found"


class AccountingPeriodInvalidTransition(AccountingPeriodError):
    code = "accounting_period_invalid_transition"


class PostgresFinancialAccountingRepository:
    """Read lending sources and manage protected accounting fiscal periods."""

    def load_overview(self) -> FinancialAccountingOverview:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        count(*) filter (where loan.status = 'active')
                            as active_loan_count,
                        coalesce(sum(loan.principal) filter (
                            where loan.status = 'active'
                        ), 0) as active_principal,
                        coalesce(sum(coalesce(state.remaining_balance, loan.principal))
                            filter (where loan.status = 'active'), 0)
                            as operational_outstanding,
                        coalesce(sum(coalesce(state.remaining_balance, loan.principal))
                            filter (
                                where loan.status = 'active'
                                  and loan_type.calculation_mode = 'fixed_daily'
                            ), 0) as regular_outstanding,
                        coalesce(sum(coalesce(state.remaining_balance, loan.principal))
                            filter (
                                where loan.status = 'active'
                                  and loan_type.calculation_mode = 'seven_by_seven'
                            ), 0) as seven_by_seven_outstanding
                    from lending.loans loan
                    left join lending.loan_types loan_type
                      on loan_type.id = loan.loan_type_id
                    left join lending.loan_collection_state state
                      on state.loan_id = loan.id
                    """
                )
                loan_summary = cursor.fetchone()

                cursor.execute(
                    """
                    select
                        coalesce(sum(t.amount) filter (
                            where t.is_voided = false
                              and t.is_locked = false
                              and t.remittance_id is null
                              and t.entry_type <> 'pass'
                        ), 0) as unremitted_cash,
                        count(*) filter (where t.is_voided = false)
                            as valid_collection_count,
                        (select count(*)
                           from lending.collection_transaction_edits)
                            as correction_count,
                        (select count(*)
                           from lending.collection_transaction_voids)
                            as void_count
                    from lending.collection_transactions t
                    """
                )
                collection_summary = cursor.fetchone()

                cursor.execute(
                    """
                    select coalesce(sum(total_amount) filter (
                        where status = 'received'
                    ), 0) as received_remittance_total
                    from lending.collection_remittances
                    """
                )
                remittance_summary = cursor.fetchone()

                cursor.execute(
                    """
                    select
                        code,
                        name,
                        term_days,
                        calculation_mode,
                        daily_interest_per_1000,
                        coalesce(
                            (settings ->> 'mobile_collections_enabled')::boolean,
                            false
                        ) as mobile_collections_enabled
                    from lending.loan_types
                    where is_active = true
                    order by name
                    """
                )
                policies = tuple(
                    self._policy_from_row(row) for row in cursor.fetchall()
                )

                cursor.execute(
                    """
                    select
                        (select count(*) from accounting.accounts)
                            as account_count,
                        (select count(*) from accounting.accounts
                          where is_active = true and is_posting = true)
                            as posting_account_count,
                        (select count(*) from accounting.fiscal_periods)
                            as fiscal_period_count,
                        (select count(*) from accounting.fiscal_periods
                          where status = 'open')
                            as open_period_count,
                        (select count(*) from accounting.journal_entries)
                            as journal_entry_count,
                        (select count(*) from accounting.journal_entries
                          where status = 'draft')
                            as draft_journal_count,
                        (select count(*) from accounting.journal_entries
                          where status = 'posted')
                            as posted_journal_count,
                        (select count(*) from accounting.journal_entries
                          where status = 'draft'
                            and reversal_of_entry_id is not null)
                            as reversal_draft_count
                    """
                )
                foundation_row = cursor.fetchone()

                cursor.execute(
                    """
                    select
                        code,
                        system_key,
                        name,
                        account_type,
                        normal_balance,
                        is_posting,
                        is_active
                    from accounting.accounts
                    order by code
                    """
                )
                chart_of_accounts = tuple(
                    AccountingAccount(
                        code=str(row["code"]),
                        system_key=str(row["system_key"]),
                        name=str(row["name"]),
                        account_type=str(row["account_type"]),
                        normal_balance=str(row["normal_balance"]),
                        is_posting=bool(row["is_posting"]),
                        is_active=bool(row["is_active"]),
                    )
                    for row in cursor.fetchall()
                )

                fiscal_periods = self._load_periods(cursor)

                cursor.execute(
                    """
                    select
                        active_loan_count,
                        source_ready_count,
                        contract_validation_count,
                        blocked_count,
                        opening_balances_configured,
                        automatic_source_posting_enabled,
                        overall_status
                    from accounting.cutover_readiness_summary
                    """
                )
                cutover_summary_row = cursor.fetchone()

                cursor.execute(
                    """
                    select
                        loan_number,
                        client_code,
                        client_name,
                        loan_type_name,
                        calculation_mode,
                        term_days,
                        principal,
                        daily_amount,
                        interest_rate,
                        date_released,
                        due_date,
                        operational_balance,
                        regular_contract_total,
                        regular_scheduled_total,
                        seven_by_seven_expected_daily_interest,
                        seven_by_seven_contract_interest_total,
                        seven_by_seven_contract_total_if_principal_at_maturity,
                        seven_by_seven_base_daily_rate_percent,
                        readiness_status,
                        blockers
                    from accounting.loan_cutover_readiness
                    where status = 'active'
                    order by calculation_mode, client_name, loan_number
                    """
                )
                cutover_loans = tuple(
                    self._cutover_loan_from_row(row) for row in cursor.fetchall()
                )

                cursor.execute(
                    """
                    select
                        cutover_date,
                        worksheet_status,
                        worksheet_line_count,
                        source_reference_count,
                        manual_required_count,
                        reconciliation_required_count,
                        calculation_required_count,
                        assessment_required_count,
                        profit_loss_migration_policy_required,
                        worksheet_balanced,
                        ready_to_post,
                        opening_balance_posting_enabled,
                        automatic_source_posting_enabled
                    from accounting.opening_balance_cutover_summary
                    """
                )
                opening_summary_row = cursor.fetchone()

                cursor.execute(
                    """
                    select
                        account_code,
                        system_key,
                        account_name,
                        account_type,
                        normal_balance,
                        source_reference_amount,
                        source_basis,
                        readiness_status,
                        guidance
                    from accounting.opening_balance_cutover_worksheet
                    order by account_code
                    """
                )
                opening_lines = tuple(
                    OpeningBalanceCutoverLine(
                        account_code=str(row["account_code"]),
                        system_key=str(row["system_key"]),
                        account_name=str(row["account_name"]),
                        account_type=str(row["account_type"]),
                        normal_balance=str(row["normal_balance"]),
                        source_reference_amount=(
                            Decimal(row["source_reference_amount"])
                            if row["source_reference_amount"] is not None
                            else None
                        ),
                        source_basis=str(row["source_basis"]),
                        readiness_status=str(row["readiness_status"]),
                        guidance=str(row["guidance"]),
                    )
                    for row in cursor.fetchall()
                )

        return FinancialAccountingOverview(
            summary=FinancialAccountingSummary(
                active_loan_count=int(loan_summary["active_loan_count"] or 0),
                active_principal=Decimal(loan_summary["active_principal"] or 0),
                operational_outstanding=Decimal(
                    loan_summary["operational_outstanding"] or 0
                ),
                regular_outstanding=Decimal(
                    loan_summary["regular_outstanding"] or 0
                ),
                seven_by_seven_outstanding=Decimal(
                    loan_summary["seven_by_seven_outstanding"] or 0
                ),
                unremitted_cash=Decimal(
                    collection_summary["unremitted_cash"] or 0
                ),
                received_remittance_total=Decimal(
                    remittance_summary["received_remittance_total"] or 0
                ),
                valid_collection_count=int(
                    collection_summary["valid_collection_count"] or 0
                ),
                correction_count=int(collection_summary["correction_count"] or 0),
                void_count=int(collection_summary["void_count"] or 0),
            ),
            foundation=AccountingFoundationSummary(
                account_count=int(foundation_row["account_count"] or 0),
                posting_account_count=int(
                    foundation_row["posting_account_count"] or 0
                ),
                fiscal_period_count=int(foundation_row["fiscal_period_count"] or 0),
                open_period_count=int(foundation_row["open_period_count"] or 0),
                journal_entry_count=int(foundation_row["journal_entry_count"] or 0),
                draft_journal_count=int(foundation_row["draft_journal_count"] or 0),
                posted_journal_count=int(foundation_row["posted_journal_count"] or 0),
                reversal_draft_count=int(foundation_row["reversal_draft_count"] or 0),
            ),
            accounts=chart_of_accounts,
            fiscal_periods=fiscal_periods,
            policies=policies,
            cutover_summary=AccountingCutoverReadinessSummary(
                active_loan_count=int(cutover_summary_row["active_loan_count"] or 0),
                source_ready_count=int(cutover_summary_row["source_ready_count"] or 0),
                contract_validation_count=int(
                    cutover_summary_row["contract_validation_count"] or 0
                ),
                blocked_count=int(cutover_summary_row["blocked_count"] or 0),
                opening_balances_configured=bool(
                    cutover_summary_row["opening_balances_configured"]
                ),
                automatic_source_posting_enabled=bool(
                    cutover_summary_row["automatic_source_posting_enabled"]
                ),
                overall_status=str(cutover_summary_row["overall_status"]),
            ),
            cutover_loans=cutover_loans,
            opening_balance_summary=OpeningBalanceCutoverSummary(
                cutover_date=opening_summary_row["cutover_date"],
                worksheet_status=str(opening_summary_row["worksheet_status"]),
                worksheet_line_count=int(
                    opening_summary_row["worksheet_line_count"] or 0
                ),
                source_reference_count=int(
                    opening_summary_row["source_reference_count"] or 0
                ),
                manual_required_count=int(
                    opening_summary_row["manual_required_count"] or 0
                ),
                reconciliation_required_count=int(
                    opening_summary_row["reconciliation_required_count"] or 0
                ),
                calculation_required_count=int(
                    opening_summary_row["calculation_required_count"] or 0
                ),
                assessment_required_count=int(
                    opening_summary_row["assessment_required_count"] or 0
                ),
                profit_loss_migration_policy_required=bool(
                    opening_summary_row["profit_loss_migration_policy_required"]
                ),
                worksheet_balanced=bool(opening_summary_row["worksheet_balanced"]),
                ready_to_post=bool(opening_summary_row["ready_to_post"]),
                opening_balance_posting_enabled=bool(
                    opening_summary_row["opening_balance_posting_enabled"]
                ),
                automatic_source_posting_enabled=bool(
                    opening_summary_row["automatic_source_posting_enabled"]
                ),
            ),
            opening_balance_lines=opening_lines,
        )

    def create_fiscal_period(
        self,
        *,
        actor_user_id: UUID,
        label: str,
        start_date: date,
        end_date: date,
    ) -> AccountingFiscalPeriod:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        select accounting.create_fiscal_period(
                            %s, %s, %s, %s
                        ) as period_id
                        """,
                        (label, start_date, end_date, actor_user_id),
                    )
                    created = cursor.fetchone()
                    return self._load_period(cursor, UUID(str(created["period_id"])))
        except psycopg.Error as error:
            raise self._period_error(error) from error

    def set_fiscal_period_status(
        self,
        *,
        actor_user_id: UUID,
        period_id: UUID,
        status: str,
    ) -> AccountingFiscalPeriod:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        select accounting.set_fiscal_period_status(
                            %s, %s, %s
                        ) as status
                        """,
                        (period_id, status, actor_user_id),
                    )
                    cursor.fetchone()
                    return self._load_period(cursor, period_id)
        except psycopg.Error as error:
            raise self._period_error(error) from error

    @classmethod
    def _load_periods(cls, cursor) -> tuple[AccountingFiscalPeriod, ...]:
        cursor.execute(
            """
            select
                period.id,
                period.label,
                period.start_date,
                period.end_date,
                period.status,
                count(journal.id) as journal_count,
                count(journal.id) filter (where journal.status = 'draft')
                    as draft_journal_count,
                count(journal.id) filter (where journal.status = 'posted')
                    as posted_journal_count,
                closed_by.full_name as closed_by_name,
                period.closed_at
            from accounting.fiscal_periods period
            left join accounting.journal_entries journal
              on journal.fiscal_period_id = period.id
            left join core.users closed_by
              on closed_by.id = period.closed_by_user_id
            group by period.id, closed_by.full_name
            order by period.start_date desc, period.end_date desc
            """
        )
        return tuple(cls._period_from_row(row) for row in cursor.fetchall())

    @classmethod
    def _load_period(cls, cursor, period_id: UUID) -> AccountingFiscalPeriod:
        cursor.execute(
            """
            select
                period.id,
                period.label,
                period.start_date,
                period.end_date,
                period.status,
                count(journal.id) as journal_count,
                count(journal.id) filter (where journal.status = 'draft')
                    as draft_journal_count,
                count(journal.id) filter (where journal.status = 'posted')
                    as posted_journal_count,
                closed_by.full_name as closed_by_name,
                period.closed_at
            from accounting.fiscal_periods period
            left join accounting.journal_entries journal
              on journal.fiscal_period_id = period.id
            left join core.users closed_by
              on closed_by.id = period.closed_by_user_id
            where period.id = %s
            group by period.id, closed_by.full_name
            """,
            (period_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise AccountingPeriodNotFound("Accounting period was not found.")
        return cls._period_from_row(row)

    @staticmethod
    def _period_from_row(row) -> AccountingFiscalPeriod:
        return AccountingFiscalPeriod(
            period_id=UUID(str(row["id"])),
            label=str(row["label"]),
            start_date=row["start_date"],
            end_date=row["end_date"],
            status=str(row["status"]),
            journal_count=int(row["journal_count"] or 0),
            draft_journal_count=int(row["draft_journal_count"] or 0),
            posted_journal_count=int(row["posted_journal_count"] or 0),
            closed_by_name=(
                str(row["closed_by_name"]) if row["closed_by_name"] else None
            ),
            closed_at=row["closed_at"],
        )

    @staticmethod
    def _period_error(error: psycopg.Error) -> AccountingPeriodError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lowered = message.lower()
        if "was not found" in lowered:
            return AccountingPeriodNotFound(message)
        if (
            "cannot overlap" in lowered
            or "already exists for this date range" in lowered
            or "draft journal entries remain" in lowered
        ):
            return AccountingPeriodConflict(message)
        if (
            "must move to review" in lowered
            or "can only be reopened or closed" in lowered
            or "unsupported accounting period status" in lowered
            or "closed accounting periods are immutable" in lowered
        ):
            return AccountingPeriodInvalidTransition(message)
        return AccountingPeriodError(message or "Accounting period operation failed.")

    @staticmethod
    def _cutover_loan_from_row(row) -> AccountingCutoverLoan:
        def optional_decimal(key: str) -> Decimal | None:
            value = row[key]
            return Decimal(value) if value is not None else None

        blockers = row["blockers"] or []
        return AccountingCutoverLoan(
            loan_number=str(row["loan_number"]),
            client_code=str(row["client_code"]),
            client_name=str(row["client_name"]),
            loan_type_name=str(row["loan_type_name"]),
            calculation_mode=str(row["calculation_mode"]),
            term_days=int(row["term_days"] or 0),
            principal=Decimal(row["principal"] or 0),
            daily_amount=Decimal(row["daily_amount"] or 0),
            interest_rate=optional_decimal("interest_rate"),
            date_released=row["date_released"],
            due_date=row["due_date"],
            operational_balance=Decimal(row["operational_balance"] or 0),
            regular_contract_total=optional_decimal("regular_contract_total"),
            regular_scheduled_total=optional_decimal("regular_scheduled_total"),
            seven_by_seven_expected_daily_interest=optional_decimal(
                "seven_by_seven_expected_daily_interest"
            ),
            seven_by_seven_contract_interest_total=optional_decimal(
                "seven_by_seven_contract_interest_total"
            ),
            seven_by_seven_contract_total_if_principal_at_maturity=optional_decimal(
                "seven_by_seven_contract_total_if_principal_at_maturity"
            ),
            seven_by_seven_base_daily_rate_percent=optional_decimal(
                "seven_by_seven_base_daily_rate_percent"
            ),
            readiness_status=str(row["readiness_status"]),
            blockers=tuple(str(item) for item in blockers),
        )

    @staticmethod
    def _policy_from_row(row) -> LoanAccountingPolicy:
        mode = str(row["calculation_mode"])
        if mode == "seven_by_seven":
            operational_rule = (
                "Daily interest is fixed at the configured amount per PHP 1,000 "
                "of original principal. A payment first settles accrued interest; "
                "any excess reduces principal. The daily interest remains based on "
                "the original principal until principal reaches zero."
            )
            accounting_rule = (
                "The validated base contract schedule uses daily contractual interest "
                "with principal due on or before maturity. Principal prepayments are "
                "allowed but do not reduce the fixed daily contractual interest. "
                "Use this cash-flow schedule to derive the PFRS effective-interest "
                "measurement before automatic journal posting is enabled. Previously "
                "recognized interest must never be recognized twice, and ECL remains "
                "a separate impairment assessment."
            )
            renewal_rule = (
                "Cash release = new principal minus old principal outstanding minus "
                "accrued unpaid interest. Close the old loan and create the renewal "
                "as a separate new loan."
            )
        else:
            operational_rule = (
                "Regular loans use a fixed contractual interest arrangement over "
                "the contractual term and a fixed daily collection amount."
            )
            accounting_rule = (
                "Do not recognize the full fixed interest on release. The official "
                "financial-accounting layer will use an effective-interest schedule "
                "for amortized-cost interest recognition, while cash collections "
                "reduce the accounting carrying amount."
            )
            renewal_rule = (
                "Settle and preserve the old loan separately, then create a new "
                "renewal loan. Any contractual settlement difference is handled in "
                "the old-loan derecognition accounting; new-loan interest starts a "
                "new schedule and is not recognized twice."
            )

        return LoanAccountingPolicy(
            code=str(row["code"]),
            name=str(row["name"]),
            term_days=int(row["term_days"] or 0),
            calculation_mode=mode,
            daily_interest_per_1000=Decimal(
                row["daily_interest_per_1000"] or 0
            ),
            mobile_collections_enabled=bool(row["mobile_collections_enabled"]),
            operational_rule=operational_rule,
            accounting_rule=accounting_rule,
            renewal_rule=renewal_rule,
        )
