from __future__ import annotations

import importlib.util
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

TEST_DIR = Path(__file__).resolve().parent


def _load_helper(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, TEST_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tax_helpers = _load_helper("a6_cycle_tax_helpers", "test_v1_tax_evidence_postgres.py")
capital_helpers = _load_helper(
    "a6_cycle_capital_helpers", "test_initial_capital_funding_postgres.py"
)

DISBURSEMENT_DRAFT_POLICY = "new_loan_disbursement_journal_draft_v1"
DISBURSEMENT_COORDINATE_POLICY = "new_loan_disbursement_coordinates_v1"
DISBURSEMENT_POSTING_POLICY = "new_loan_disbursement_journal_posting_v1"
REMITTANCE_DRAFT_POLICY = "remittance_transfer_journal_draft_v1"
REMITTANCE_COORDINATE_POLICY = "remittance_transfer_coordinates_v1"
REMITTANCE_POSTING_POLICY = "remittance_transfer_journal_posting_v1"
TAX_LIABILITY_POLICY = "v1_tax_liability_posting_v1"
TAX_SETTLEMENT_POLICY = "v1_tax_settlement_posting_v1"
PERIOD_CLOSE_POLICY = "period_close_retained_earnings_v1"


def _post_initial_capital(
    connection: psycopg.Connection,
    *,
    actor_id,
    posting_date,
    period_id,
    suffix: str,
) -> tuple[object, object]:
    evidence_id = capital_helpers._record(
        connection,
        actor_id=actor_id,
        key=uuid4(),
        funding_date=posting_date,
        amount="100000.00",
        cash_code="1010",
        suffix=f"a6-cycle-{suffix}",
        digest_char="a",
    )
    journal_id = connection.execute(
        "SELECT accounting.prepare_initial_capital_funding_journal(%s,%s)",
        (evidence_id, actor_id),
    ).fetchone()[0]
    posting_id = capital_helpers._post(
        connection,
        evidence_id=evidence_id,
        actor_id=actor_id,
        token="b" * 64,
        digest="a" * 64,
        amount="100000.00",
        cash_code="1010",
        posting_date=posting_date,
        period_id=period_id,
    )
    assert posting_id == evidence_id
    return evidence_id, journal_id


def _post_regular_disbursement(
    connection: psycopg.Connection,
    *,
    actor_id,
    posting_date,
    suffix: str,
) -> tuple[object, object, object, object]:
    client_id = connection.execute(
        """
        INSERT INTO lending.clients(client_code, full_name, status)
        VALUES(%s,%s,'active') RETURNING id
        """,
        (f"A6C-C-{suffix}", f"A6 Cycle Client {suffix}"),
    ).fetchone()[0]
    loan_type_id = connection.execute(
        """
        INSERT INTO lending.loan_types(
            code, name, term_days, calculation_mode, daily_interest_per_1000
        ) VALUES(%s,%s,120,'fixed_daily',0) RETURNING id
        """,
        (f"A6C-REG-{suffix}", f"A6 Cycle Regular {suffix}"),
    ).fetchone()[0]
    loan_id = connection.execute(
        """
        INSERT INTO lending.loans(
            loan_number, client_id, loan_type_id, principal, daily_amount,
            interest_rate, date_released, due_date, status, created_by_user_id
        ) VALUES(%s,%s,%s,5000.00,50.00,20.0000,%s,%s,'active',%s)
        RETURNING id
        """,
        (
            f"A6C-L-{suffix}",
            client_id,
            loan_type_id,
            posting_date,
            posting_date + timedelta(days=120),
            actor_id,
        ),
    ).fetchone()[0]
    disbursed_at = datetime(
        posting_date.year,
        posting_date.month,
        posting_date.day,
        9,
        0,
        tzinfo=timezone(timedelta(hours=8)),
    )
    event_id = connection.execute(
        """
        SELECT accounting.record_loan_disbursement_evidence(
            %s,%s,'new_loan_release',%s,%s,5000.00,0.00,0.00,
            'cash_office',%s,%s
        )
        """,
        (
            loan_id,
            actor_id,
            posting_date,
            disbursed_at,
            f"A6-CYCLE-RELEASE-{suffix}",
            "Retained synthetic release evidence for the disposable A6.4 cycle only.",
        ),
    ).fetchone()[0]
    coordinate = connection.execute(
        """
        SELECT source_event_key, posting_date, fiscal_period_id,
               debit_account_id, credit_account_id, debit_amount
        FROM accounting.loan_disbursement_journal_coordinates
        WHERE disbursement_event_id=%s AND coordinate_status='coordinate_ready'
        """,
        (event_id,),
    ).fetchone()
    assert coordinate is not None
    preparation_id = connection.execute(
        """
        SELECT accounting.create_new_loan_disbursement_journal_draft(
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        """,
        (
            event_id,
            actor_id,
            "c" * 64,
            coordinate[0],
            coordinate[1],
            coordinate[2],
            coordinate[3],
            coordinate[4],
            coordinate[5],
            DISBURSEMENT_COORDINATE_POLICY,
            DISBURSEMENT_DRAFT_POLICY,
        ),
    ).fetchone()[0]
    status = connection.execute(
        """
        SELECT preparation_id, journal_entry_id, source_event_key,
               draft_review_token, posting_date, fiscal_period_id,
               debit_account_id, credit_account_id, amount,
               total_debit, total_credit, posting_ready
        FROM accounting.loan_disbursement_journal_posting_status
        WHERE preparation_id=%s
        """,
        (preparation_id,),
    ).fetchone()
    assert status is not None and status[-1] is True
    posting_id = connection.execute(
        """
        SELECT accounting.post_new_loan_disbursement_journal(
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        """,
        (
            status[0],
            actor_id,
            "d" * 64,
            status[1],
            status[2],
            status[3],
            status[4],
            status[5],
            status[6],
            status[7],
            status[8],
            status[9],
            status[10],
            DISBURSEMENT_POSTING_POLICY,
        ),
    ).fetchone()[0]
    return loan_id, event_id, status[1], posting_id


def _post_remittance(
    connection: psycopg.Connection,
    *,
    actor_id,
    transaction_id,
    collection_date,
    suffix: str,
) -> tuple[object, object, object, object]:
    # A remittance must have a recipient different from the collector. The first
    # disposable run deliberately exposed this operational invariant, so the A6.4
    # fixture now models the actual protected handoff rather than weakening it.
    recipient_id = connection.execute(
        """
        INSERT INTO core.users(username, full_name, status)
        VALUES(%s,%s,'active') RETURNING id
        """,
        (f"a6c-recipient-{suffix}", f"A6 Cycle Recipient {suffix}"),
    ).fetchone()[0]
    connection.execute(
        """
        INSERT INTO core.user_roles(user_id, role_id)
        SELECT %s,id FROM core.roles WHERE code='employee'
        """,
        (recipient_id,),
    )

    transaction = connection.execute(
        """
        SELECT client_id, loan_id, collection_date, entry_type, amount,
               receipt_number
        FROM lending.collection_transactions
        WHERE id=%s AND is_voided=false
        """,
        (transaction_id,),
    ).fetchone()
    assert transaction is not None
    assert transaction[2] == collection_date
    assert Decimal(transaction[4]) == Decimal("50.00")

    received_at = datetime(
        collection_date.year,
        collection_date.month,
        collection_date.day,
        15,
        0,
        tzinfo=timezone(timedelta(hours=8)),
    )
    submitted_at = received_at - timedelta(minutes=5)
    remittance_id = connection.execute(
        """
        INSERT INTO lending.collection_remittances(
            remittance_number, collector_user_id, recipient_user_id,
            collection_date, status, transaction_count, payment_count,
            unable_to_pay_count, covered_payment_count, client_count,
            total_amount, note, submitted_at, received_at,
            received_by_user_id, custody_user_id, custody_transferred_at,
            created_at, updated_at
        ) VALUES(
            %s,%s,%s,%s,'received',1,1,0,0,1,50.00,'',
            %s,%s,%s,%s,%s,%s,%s
        ) RETURNING id
        """,
        (
            f"A6C-REM-{suffix}",
            actor_id,
            recipient_id,
            collection_date,
            submitted_at,
            received_at,
            recipient_id,
            recipient_id,
            received_at,
            submitted_at,
            received_at,
        ),
    ).fetchone()[0]
    connection.execute(
        """
        INSERT INTO lending.collection_remittance_items(
            remittance_id, transaction_id, client_id, loan_id,
            collection_date, entry_type, amount, receipt_number,
            transaction_snapshot
        ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'{}'::jsonb)
        """,
        (
            remittance_id,
            transaction_id,
            transaction[0],
            transaction[1],
            transaction[2],
            transaction[3],
            transaction[4],
            transaction[5],
        ),
    )
    connection.execute(
        """
        UPDATE lending.collection_transactions
        SET remittance_id=%s, is_locked=true, locked_at=%s,
            locked_by_user_id=%s, updated_at=%s, updated_by_user_id=%s
        WHERE id=%s AND is_voided=false AND remittance_id IS NULL
        """,
        (
            remittance_id,
            submitted_at,
            actor_id,
            submitted_at,
            actor_id,
            transaction_id,
        ),
    )
    assert connection.execute(
        "SELECT remittance_id,is_locked FROM lending.collection_transactions WHERE id=%s",
        (transaction_id,),
    ).fetchone() == (remittance_id, True)

    transferred_at = received_at + timedelta(minutes=5)
    evidence_id = connection.execute(
        """
        SELECT accounting.record_remittance_transfer_evidence(
            %s,%s,'cash_office',%s,%s,%s,%s
        )
        """,
        (
            remittance_id,
            actor_id,
            collection_date,
            transferred_at,
            f"A6C-OFFICE-{suffix}",
            "Retained synthetic custody-transfer evidence for the disposable A6.4 cycle only.",
        ),
    ).fetchone()[0]
    source_key = f"remittance_transfer:{remittance_id}"
    preparation_id = connection.execute(
        """
        SELECT accounting.create_remittance_transfer_journal_draft(
            %s,%s,%s,%s,%s,%s,'cash_office','cash_collector_custody',50.00,%s,%s
        )
        """,
        (
            remittance_id,
            actor_id,
            "e" * 64,
            evidence_id,
            source_key,
            collection_date,
            REMITTANCE_COORDINATE_POLICY,
            REMITTANCE_DRAFT_POLICY,
        ),
    ).fetchone()[0]
    status = connection.execute(
        """
        SELECT journal_entry_id, posting_ready
        FROM accounting.remittance_transfer_journal_status
        WHERE preparation_id=%s
        """,
        (preparation_id,),
    ).fetchone()
    assert status is not None and status[1] is True
    journal_id = status[0]
    posting_id = connection.execute(
        """
        SELECT accounting.post_remittance_transfer_journal(
            %s,%s,%s,%s,%s,%s,50.00,%s
        )
        """,
        (
            preparation_id,
            actor_id,
            "f" * 64,
            journal_id,
            source_key,
            "e" * 64,
            REMITTANCE_POSTING_POLICY,
        ),
    ).fetchone()[0]
    return remittance_id, evidence_id, journal_id, posting_id


def _post_percentage_tax_and_settle(
    connection: psycopg.Connection,
    *,
    actor_id,
    transaction_id,
    period_id,
    collection_date,
    suffix: str,
) -> tuple[object, object, object, object, object, object]:
    rule_id = tax_helpers._record_rule(
        connection,
        actor_id=actor_id,
        tax_type="percentage_tax_lending",
        key=f"a6-cycle-grt-{suffix}",
        effective_from=collection_date,
        rate="0.0500000000",
        maturity_max_days=1825,
        digest_char="1",
    )
    evidence_id = tax_helpers._record_percentage(
        connection,
        actor_id=actor_id,
        transaction_id=transaction_id,
        rule_id=rule_id,
        taxable="21.00",
        principal="29.00",
        tax_due="1.05",
        digest_char="2",
    )
    liability_journal_id = connection.execute(
        "SELECT accounting.prepare_v1_tax_liability_journal(%s,%s,%s)",
        ("percentage_tax_lending", evidence_id, actor_id),
    ).fetchone()[0]
    liability_posting_id = connection.execute(
        """
        SELECT accounting.post_v1_tax_liability_journal(
            'percentage_tax_lending',%s,%s,%s,%s,1.05,'5300','2100',%s,%s,%s
        )
        """,
        (
            evidence_id,
            actor_id,
            "3" * 64,
            "2" * 64,
            collection_date,
            period_id,
            TAX_LIABILITY_POLICY,
        ),
    ).fetchone()[0]

    return_id = connection.execute(
        """
        SELECT accounting.record_v1_tax_return_evidence(
            %s,%s,'percentage_tax_lending',%s,%s,%s,1.05,%s,%s,%s,%s,%s
        )
        """,
        (
            actor_id,
            uuid4(),
            collection_date,
            collection_date,
            collection_date + timedelta(days=1),
            f"A6C-2551Q-{suffix}",
            f"A6C-RETURN-{suffix}",
            "4" * 64,
            "Retained synthetic percentage-tax return evidence for the disposable A6.4 cycle only.",
            [liability_posting_id],
        ),
    ).fetchone()[0]
    payment_date = collection_date + timedelta(days=2)
    payment_id = connection.execute(
        """
        SELECT accounting.record_v1_tax_payment_evidence(
            %s,%s,%s,%s,1.05,'cash_office',%s,%s,%s,%s
        )
        """,
        (
            actor_id,
            uuid4(),
            return_id,
            payment_date,
            f"A6C-TAX-PAY-{suffix}",
            f"A6C-TAX-PAYMENT-EVIDENCE-{suffix}",
            "5" * 64,
            "Retained synthetic tax-payment evidence funded from Office Cash for the disposable A6.4 cycle only.",
        ),
    ).fetchone()[0]
    settlement_journal_id = connection.execute(
        "SELECT accounting.prepare_v1_tax_settlement_journal(%s,%s)",
        (payment_id, actor_id),
    ).fetchone()[0]
    settlement_posting_id = connection.execute(
        """
        SELECT accounting.post_v1_tax_settlement_journal(
            %s,%s,%s,%s,%s,1.05,'2100','1010',%s,%s,%s
        )
        """,
        (
            payment_id,
            actor_id,
            "6" * 64,
            "4" * 64,
            "5" * 64,
            payment_date,
            period_id,
            TAX_SETTLEMENT_POLICY,
        ),
    ).fetchone()[0]
    return (
        evidence_id,
        liability_journal_id,
        liability_posting_id,
        return_id,
        settlement_journal_id,
        settlement_posting_id,
    )


def _period_balances(connection: psycopg.Connection, period_id):
    rows = connection.execute(
        """
        SELECT account.code, account.account_type,
               sum(line.debit-line.credit)::numeric(18,2) AS net
        FROM accounting.journal_lines line
        JOIN accounting.journal_entries journal
          ON journal.id=line.journal_entry_id
        JOIN accounting.accounts account
          ON account.id=line.account_id
        WHERE journal.status='posted'
          AND journal.fiscal_period_id=%s
        GROUP BY account.id, account.code, account.account_type
        ORDER BY account.code
        """,
        (period_id,),
    ).fetchall()
    return [(str(code), str(kind), Decimal(net)) for code, kind, net in rows]


def _trial_balance_totals(balances):
    debit = sum((net for _, _, net in balances if net > 0), Decimal("0.00"))
    credit = sum((-net for _, _, net in balances if net < 0), Decimal("0.00"))
    return debit, credit


def _profit_or_loss(balances):
    income = sum((-net for _, kind, net in balances if kind == "income"), Decimal("0.00"))
    expense = sum((net for _, kind, net in balances if kind == "expense"), Decimal("0.00"))
    return income, expense, income - expense


def _financial_position(balances):
    assets = sum((net for _, kind, net in balances if kind == "asset"), Decimal("0.00"))
    liabilities = sum((-net for _, kind, net in balances if kind == "liability"), Decimal("0.00"))
    equity = sum((-net for _, kind, net in balances if kind == "equity"), Decimal("0.00"))
    return assets, liabilities, equity


def _account_period_net(connection: psycopg.Connection, period_id, account_code: str):
    return connection.execute(
        """
        SELECT coalesce(sum(line.debit-line.credit),0)::numeric(18,2)
        FROM accounting.journal_lines line
        JOIN accounting.journal_entries journal
          ON journal.id=line.journal_entry_id
        JOIN accounting.accounts account
          ON account.id=line.account_id
        WHERE journal.status='posted'
          AND journal.fiscal_period_id=%s
          AND account.code=%s
        """,
        (period_id, account_code),
    ).fetchone()[0]


def test_a6_end_to_end_disposable_accounting_cycle_reconciles_without_residuals() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            actor_id, _, period_id, transaction_id, x7_status = (
                tax_helpers._current_schema_posted_7x7_case(connection, suffix)
            )
            period = connection.execute(
                "SELECT start_date,end_date,status FROM accounting.fiscal_periods WHERE id=%s",
                (period_id,),
            ).fetchone()
            assert period is not None and period[2] == "open"
            start_date, end_date = period[0], period[1]
            collection_date = connection.execute(
                "SELECT collection_date FROM lending.collection_transactions WHERE id=%s",
                (transaction_id,),
            ).fetchone()[0]
            assert collection_date == start_date + timedelta(days=1)

            capital_evidence_id, capital_journal_id = _post_initial_capital(
                connection,
                actor_id=actor_id,
                posting_date=start_date,
                period_id=period_id,
                suffix=suffix,
            )
            _, release_event_id, release_journal_id, release_posting_id = (
                _post_regular_disbursement(
                    connection,
                    actor_id=actor_id,
                    posting_date=start_date,
                    suffix=suffix,
                )
            )
            remittance_id, _, remittance_journal_id, remittance_posting_id = _post_remittance(
                connection,
                actor_id=actor_id,
                transaction_id=transaction_id,
                collection_date=collection_date,
                suffix=suffix,
            )
            (
                tax_evidence_id,
                tax_liability_journal_id,
                tax_liability_posting_id,
                tax_return_id,
                tax_settlement_journal_id,
                tax_settlement_posting_id,
            ) = _post_percentage_tax_and_settle(
                connection,
                actor_id=actor_id,
                transaction_id=transaction_id,
                period_id=period_id,
                collection_date=collection_date,
                suffix=suffix,
            )

            # Exact preparation retries must reuse the same journal identity.
            assert connection.execute(
                "SELECT accounting.prepare_initial_capital_funding_journal(%s,%s)",
                (capital_evidence_id, actor_id),
            ).fetchone()[0] == capital_journal_id
            assert connection.execute(
                "SELECT accounting.prepare_v1_tax_liability_journal(%s,%s,%s)",
                ("percentage_tax_lending", tax_evidence_id, actor_id),
            ).fetchone()[0] == tax_liability_journal_id
            payment_evidence_id = connection.execute(
                """
                SELECT payment_evidence_id FROM accounting.v1_tax_settlement_queue
                WHERE tax_return_id=%s
                """,
                (tax_return_id,),
            ).fetchone()[0]
            assert connection.execute(
                "SELECT accounting.prepare_v1_tax_settlement_journal(%s,%s)",
                (payment_evidence_id, actor_id),
            ).fetchone()[0] == tax_settlement_journal_id

            before_close = _period_balances(connection, period_id)
            trial_debit, trial_credit = _trial_balance_totals(before_close)
            assert trial_debit == trial_credit
            income, expense, profit_or_loss = _profit_or_loss(before_close)
            assert income > Decimal("0.00")
            assert expense == Decimal("1.05")
            assert profit_or_loss != Decimal("0.00")

            assert connection.execute(
                """
                SELECT count(*) FROM accounting.journal_entries
                WHERE fiscal_period_id=%s AND status='draft'
                """,
                (period_id,),
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT accounting.set_fiscal_period_status(%s,'review',%s)",
                (period_id, actor_id),
            ).fetchone()[0] == "review"
            close_preparation_id = connection.execute(
                "SELECT accounting.prepare_period_close(%s,%s)",
                (period_id, actor_id),
            ).fetchone()[0]
            close_row = connection.execute(
                """
                SELECT journal_entry_id, net_income, close_digest
                FROM accounting.period_close_preparations WHERE id=%s
                """,
                (close_preparation_id,),
            ).fetchone()
            assert close_row is not None
            close_journal_id, close_net_income, close_digest = close_row
            assert Decimal(close_net_income) == profit_or_loss
            close_posting_id = connection.execute(
                """
                SELECT accounting.post_period_close(
                    %s,%s,%s,%s,%s,'3100',%s,%s
                )
                """,
                (
                    period_id,
                    actor_id,
                    "7" * 64,
                    close_digest,
                    profit_or_loss,
                    end_date,
                    PERIOD_CLOSE_POLICY,
                ),
            ).fetchone()[0]
            assert close_posting_id is not None

            after_close = _period_balances(connection, period_id)
            post_debit, post_credit = _trial_balance_totals(after_close)
            assert post_debit == post_credit
            temporary = [
                (code, net)
                for code, kind, net in after_close
                if kind in {"income", "expense"}
            ]
            assert temporary
            assert all(net == Decimal("0.00") for _, net in temporary)
            assets, liabilities, equity = _financial_position(after_close)
            assert assets == liabilities + equity

            assert _account_period_net(connection, period_id, "2100") == Decimal("0.00")
            assert _account_period_net(connection, period_id, "3100") == -profit_or_loss
            custody = connection.execute(
                """
                SELECT coalesce(sum(line.debit-line.credit),0)::numeric(18,2)
                FROM accounting.journal_lines line
                JOIN accounting.journal_entries journal
                  ON journal.id=line.journal_entry_id
                JOIN accounting.accounts account
                  ON account.id=line.account_id
                WHERE journal.status='posted'
                  AND journal.fiscal_period_id=%s
                  AND account.system_key='cash_collector_custody'
                """,
                (period_id,),
            ).fetchone()[0]
            assert custody == Decimal("0.00")

            duplicates = connection.execute(
                """
                SELECT source_event_key,count(*)
                FROM accounting.journal_entries
                WHERE status='posted' AND source_event_key IS NOT NULL
                GROUP BY source_event_key HAVING count(*) > 1
                """
            ).fetchall()
            assert duplicates == []
            assert connection.execute(
                "SELECT count(*) FROM accounting.journal_entries WHERE status='draft'"
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT count(*) FROM accounting.journal_entries WHERE source_type='opening_balance'"
            ).fetchone()[0] == 0
            assert connection.execute(
                """
                SELECT count(*) FROM accounting.journal_events event
                LEFT JOIN accounting.journal_entries journal
                  ON journal.id=event.journal_entry_id
                WHERE journal.id IS NULL
                """
            ).fetchone()[0] == 0

            expected_journals = {
                capital_journal_id,
                release_journal_id,
                x7_status[4],
                remittance_journal_id,
                tax_liability_journal_id,
                tax_settlement_journal_id,
                close_journal_id,
            }
            posted_journals = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT id FROM accounting.journal_entries
                    WHERE id=ANY(%s) AND status='posted'
                    """,
                    (list(expected_journals),),
                ).fetchall()
            }
            assert posted_journals == expected_journals

            audit_checks = (
                (
                    "accounting.loan_disbursement_journal_postings",
                    release_posting_id,
                ),
                ("accounting.seven_by_seven_journal_postings", x7_status[22]),
                (
                    "accounting.remittance_transfer_journal_postings",
                    remittance_posting_id,
                ),
                ("accounting.v1_tax_liability_postings", tax_liability_posting_id),
                ("accounting.v1_tax_settlement_postings", tax_settlement_posting_id),
                ("accounting.period_close_postings", close_posting_id),
            )
            for table_name, row_id in audit_checks:
                count = connection.execute(
                    f"SELECT count(*) FROM {table_name} WHERE id=%s",
                    (row_id,),
                ).fetchone()[0]
                assert count == 1

            assert connection.execute(
                """
                SELECT remittance_id,is_locked
                FROM lending.collection_transactions WHERE id=%s
                """,
                (transaction_id,),
            ).fetchone() == (remittance_id, True)
            assert connection.execute(
                """
                SELECT count(*) FROM lending.collection_remittance_items
                WHERE remittance_id=%s AND transaction_id=%s
                """,
                (remittance_id, transaction_id),
            ).fetchone()[0] == 1
            assert release_event_id is not None

            assert x7_status[-1] is False
            assert connection.execute(
                """
                SELECT automatic_source_posting
                FROM accounting.initial_capital_funding_queue
                WHERE evidence_id=%s
                """,
                (capital_evidence_id,),
            ).fetchone()[0] is False
            assert connection.execute(
                """
                SELECT automatic_source_posting
                FROM accounting.v1_tax_liability_queue
                WHERE tax_type='percentage_tax_lending' AND evidence_id=%s
                """,
                (tax_evidence_id,),
            ).fetchone()[0] is False
            assert connection.execute(
                """
                SELECT automatic_source_posting
                FROM accounting.period_close_queue WHERE fiscal_period_id=%s
                """,
                (period_id,),
            ).fetchone()[0] is False
            assert connection.execute(
                "SELECT status FROM accounting.fiscal_periods WHERE id=%s",
                (period_id,),
            ).fetchone()[0] == "closed"
        finally:
            connection.rollback()
