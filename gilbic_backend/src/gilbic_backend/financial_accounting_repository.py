from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

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
class FinancialAccountingOverview:
    summary: FinancialAccountingSummary
    policies: tuple[LoanAccountingPolicy, ...]


class PostgresFinancialAccountingRepository:
    """Read existing lending sources without creating accounting journals."""

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
                        count(*) filter (
                            where t.is_voided = false
                        ) as valid_collection_count,
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
            policies=policies,
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
                "Track principal receivable and accrued interest separately. "
                "Recognize earned contractual interest over time, collect accrued "
                "interest without recognizing it twice, and assess impairment/ECL "
                "separately when collectibility deteriorates."
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
