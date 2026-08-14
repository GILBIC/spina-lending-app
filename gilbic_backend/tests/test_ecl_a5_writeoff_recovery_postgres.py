from __future__ import annotations

import importlib.util
import os
from datetime import timedelta
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
A5_PATH = TEST_DIR / "test_ecl_a5_remeasurement_postgres.py"
_spec = importlib.util.spec_from_file_location("ecl_a5_helpers", A5_PATH)
assert _spec is not None and _spec.loader is not None
a5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(a5)
a3 = a5.a3

RECOVERY_PATH = TEST_DIR / "test_ecl_cash_recovery_chronology_postgres.py"
_recovery_spec = importlib.util.spec_from_file_location("ecl_recovery_helpers", RECOVERY_PATH)
assert _recovery_spec is not None and _recovery_spec.loader is not None
recovery_helpers = importlib.util.module_from_spec(_recovery_spec)
_recovery_spec.loader.exec_module(recovery_helpers)

WRITEOFF_POLICY = "ecl_full_writeoff_posting_v1"
RECOVERY_POLICY = "ecl_post_writeoff_recovery_posting_v1"


def _writeoff_review(connection: psycopg.Connection, case, suffix: str):
    actor_id, loan_id = case[0], case[1]
    return connection.execute(
        """
        SELECT accounting.review_ecl_credit_risk_labels(
            %s,
            'stage_3_credit_impaired',
            true,
            'supported_no_reasonable_expectation_of_recovery',
            'none',
            'verified_source_document',
            %s,
            %s,
            false,
            false,
            NULL,
            NULL,
            %s,
            %s,
            NULL,
            %s
        )
        """,
        (
            loan_id,
            f"ECLA5-WRITEOFF-SUPPORT-{suffix}",
            "Management reviewed retained evidence supporting Stage 3 default and no reasonable expectation of recovery.",
            f"ECLA5-WRITEOFF-EVIDENCE-{suffix}",
            "Protected write-off support only; derecognition still requires the explicit A5 accounting function.",
            actor_id,
        ),
    ).fetchone()[0]


def _full_loss_scenarios(case, *, base_probability: str = "0.500000000000"):
    evidence_ids = case[4]
    base = Decimal(base_probability)
    downside = Decimal("1.000000000000") - base
    return [
        {
            "scenario_key": "base",
            "probability": float(base),
            "evidence_reference": "A5-WRITEOFF-BASE",
            "management_rationale": "Retained protected evidence supports no expected future receipts for this exact full-loss measurement.",
            "forward_evidence_ids": [str(value) for value in evidence_ids],
            "expected_cash_flows": [],
        },
        {
            "scenario_key": "downside",
            "probability": float(downside),
            "evidence_reference": "A5-WRITEOFF-DOWNSIDE",
            "management_rationale": "Retained protected evidence independently supports no expected future receipts in the downside scenario.",
            "forward_evidence_ids": [str(value) for value in evidence_ids],
            "expected_cash_flows": [],
        },
    ]


def _full_loss_measurement(connection: psycopg.Connection, case):
    measurement_id = a3._measure(
        connection,
        loan_id=case[1],
        actor_id=case[0],
        scenarios=_full_loss_scenarios(case),
    )
    return a5._measurement(connection, measurement_id)


def _gross(connection: psycopg.Connection, loan_id):
    row = connection.execute(
        """
        SELECT loan_receivable_account_id,
               accrued_interest_account_id,
               loan_component,
               accrued_interest_component,
               gross_carrying_amount
        FROM accounting.ecl_loan_gross_carrying_components(%s)
        """,
        (loan_id,),
    ).fetchone()
    assert row is not None
    return row


def _post_writeoff(
    connection: psycopg.Connection,
    case,
    *,
    review_id,
    measurement,
    gross,
    token: str,
):
    actor_id, loan_id, period_id, today = case[0], case[1], case[2], case[3]
    allowance_account_id = case[6][1]
    return connection.execute(
        """
        SELECT accounting.post_ecl_full_writeoff(
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        """,
        (
            loan_id,
            actor_id,
            token,
            review_id,
            measurement[0],
            measurement[4],
            gross[2],
            gross[3],
            gross[4],
            gross[4],
            gross[0],
            gross[1],
            allowance_account_id,
            today,
            period_id,
            WRITEOFF_POLICY,
        ),
    ).fetchone()[0]


def _recovery_review(connection: psycopg.Connection, case, transaction_id, suffix: str):
    actor_id, loan_id = case[0], case[1]
    return connection.execute(
        """
        SELECT accounting.review_ecl_credit_risk_labels(
            %s,
            'stage_3_credit_impaired',
            true,
            'none',
            'cash_recovery_observed',
            'protected_collection_history',
            %s,
            %s,
            false,
            false,
            NULL,
            NULL,
            NULL,
            NULL,
            %s,
            %s
        )
        """,
        (
            loan_id,
            f"ECLA5-RECOVERY-EVIDENCE-{suffix}",
            "Exact protected same-loan cash was accepted after the completed accounting write-off.",
            transaction_id,
            actor_id,
        ),
    ).fetchone()[0]


def _post_recovery(
    connection: psycopg.Connection,
    case,
    *,
    review_id,
    transaction_id,
    token: str,
):
    cash_account_id = connection.execute(
        "SELECT id FROM accounting.accounts WHERE system_key='cash_collector_custody'"
    ).fetchone()[0]
    expense_account_id = case[6][0]
    posting_date = connection.execute(
        "SELECT collection_date FROM lending.collection_transactions WHERE id=%s",
        (transaction_id,),
    ).fetchone()[0]
    return connection.execute(
        """
        SELECT accounting.post_ecl_post_writeoff_recovery(
            %s,%s,%s,%s,10.00,%s,%s,%s,%s,%s
        )
        """,
        (
            review_id,
            case[0],
            token,
            transaction_id,
            posting_date,
            case[2],
            cash_account_id,
            expense_account_id,
            RECOVERY_POLICY,
        ),
    ).fetchone()[0]


def _assert_postwriteoff_insert_guards(connection: psycopg.Connection, case, transaction_id) -> None:
    loan_id = case[1]

    # The protected A3 function already fails closed earlier because derecognition
    # makes its quantitative input gate non-authoritative. Separately hit the 0080
    # table boundary directly so bypassing that gate cannot recreate a measurement.
    with pytest.raises(psycopg.Error, match="Quantitative ECL input gate is blocked"):
        with connection.transaction():
            a3._measure(
                connection,
                loan_id=loan_id,
                actor_id=case[0],
                scenarios=_full_loss_scenarios(case, base_probability="0.600000000000"),
            )

    with pytest.raises(psycopg.Error, match="fully written off"):
        with connection.transaction():
            connection.execute(
                "SELECT set_config('accounting.ecl_quantitative_measurement_insert_allowed','on',true)"
            )
            connection.execute(
                "INSERT INTO accounting.ecl_quantitative_measurements(loan_id) VALUES (%s)",
                (loan_id,),
            )

    guarded_audit_tables = (
        (
            "accounting.ecl_allowance_draft_preparations",
            "accounting.ecl_allowance_preparation_record_allowed",
        ),
        (
            "accounting.ecl_allowance_postings",
            "accounting.ecl_allowance_posting_audit_allowed",
        ),
        (
            "accounting.ecl_allowance_remeasurements",
            "accounting.ecl_a5_audit_insert_allowed",
        ),
    )
    for table_name, setting_name in guarded_audit_tables:
        with pytest.raises(psycopg.Error, match="fully written off"):
            with connection.transaction():
                connection.execute("SELECT set_config(%s,'on',true)", (setting_name,))
                connection.execute(f"INSERT INTO {table_name}(loan_id) VALUES (%s)", (loan_id,))

    collection_posting_guards = (
        (
            "accounting.regular_journal_posting_entries",
            "accounting.regular_journal_post_record_allowed",
        ),
        (
            "accounting.seven_by_seven_journal_postings",
            "accounting.seven_by_seven_journal_post_record_allowed",
        ),
    )
    for table_name, setting_name in collection_posting_guards:
        with pytest.raises(psycopg.Error, match="Normal Regular/7x7 collection accounting is blocked"):
            with connection.transaction():
                connection.execute("SELECT set_config(%s,'on',true)", (setting_name,))
                connection.execute(
                    f"INSERT INTO {table_name}(transaction_id) VALUES (%s)",
                    (transaction_id,),
                )


def test_a5_full_writeoff_and_postwriteoff_recovery_are_exact_idempotent_atomic_and_fail_closed() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            a5._install(connection)
            case = a5._case(connection, suffix)

            writeoff_review_id = _writeoff_review(connection, case, suffix)
            measurement = _full_loss_measurement(connection, case)
            gross = _gross(connection, case[1])
            assert gross[4] == Decimal("5000.00")
            assert measurement[5] == gross[4]

            a5._remeasure(connection, case, measurement, "6" * 64)
            assert connection.execute(
                "SELECT accounting.ecl_loan_allowance_balance(%s)",
                (case[1],),
            ).fetchone()[0] == gross[4]

            before_writeoff = connection.execute(
                """
                SELECT
                    (SELECT count(*) FROM accounting.journal_entries),
                    (SELECT count(*) FROM accounting.ecl_accounting_writeoffs),
                    accounting.ecl_loan_allowance_balance(%s)
                """,
                (case[1],),
            ).fetchone()
            with pytest.raises(psycopg.Error, match="Forced A5 audit failure"):
                with connection.transaction():
                    connection.execute(
                        "SELECT set_config('accounting.ecl_a5_force_audit_failure','on',true)"
                    )
                    _post_writeoff(
                        connection,
                        case,
                        review_id=writeoff_review_id,
                        measurement=measurement,
                        gross=gross,
                        token="7" * 64,
                    )
            assert connection.execute(
                """
                SELECT
                    (SELECT count(*) FROM accounting.journal_entries),
                    (SELECT count(*) FROM accounting.ecl_accounting_writeoffs),
                    accounting.ecl_loan_allowance_balance(%s)
                """,
                (case[1],),
            ).fetchone() == before_writeoff
            assert _gross(connection, case[1])[4] == gross[4]

            writeoff_id = _post_writeoff(
                connection,
                case,
                review_id=writeoff_review_id,
                measurement=measurement,
                gross=gross,
                token="8" * 64,
            )
            assert _post_writeoff(
                connection,
                case,
                review_id=writeoff_review_id,
                measurement=measurement,
                gross=gross,
                token="8" * 64,
            ) == writeoff_id
            with pytest.raises(psycopg.Error, match="immutable retry identity"):
                with connection.transaction():
                    _post_writeoff(
                        connection,
                        case,
                        review_id=writeoff_review_id,
                        measurement=measurement,
                        gross=gross,
                        token="9" * 64,
                    )

            writeoff_row = connection.execute(
                "SELECT journal_entry_id, posted_at FROM accounting.ecl_accounting_writeoffs WHERE id=%s",
                (writeoff_id,),
            ).fetchone()
            assert writeoff_row is not None
            assert _gross(connection, case[1])[4] == Decimal("0.00")
            assert connection.execute(
                "SELECT accounting.ecl_loan_allowance_balance(%s)",
                (case[1],),
            ).fetchone()[0] == Decimal("0.00")

            writeoff_lines = connection.execute(
                """
                SELECT account_id, debit, credit
                FROM accounting.journal_lines
                WHERE journal_entry_id=%s
                ORDER BY line_number
                """,
                (writeoff_row[0],),
            ).fetchall()
            assert writeoff_lines == [
                (case[6][1], gross[4], Decimal("0.00")),
                (gross[0], Decimal("0.00"), gross[2]),
            ]

            device_id = recovery_helpers._device(connection, case[0], suffix)
            accepted_at = writeoff_row[1] + timedelta(seconds=1)
            recovery_tx = recovery_helpers._collection(
                connection,
                loan_id=case[1],
                actor_user_id=case[0],
                device_id=device_id,
                suffix=suffix,
                device_sequence=1,
                accepted_at=accepted_at,
            )

            _assert_postwriteoff_insert_guards(connection, case, recovery_tx)

            recovery_review_id = _recovery_review(connection, case, recovery_tx, suffix)
            before_recovery = connection.execute(
                """
                SELECT
                    (SELECT count(*) FROM accounting.journal_entries),
                    (SELECT count(*) FROM accounting.ecl_post_writeoff_recoveries)
                """
            ).fetchone()
            with pytest.raises(psycopg.Error, match="Forced A5 audit failure"):
                with connection.transaction():
                    connection.execute(
                        "SELECT set_config('accounting.ecl_a5_force_audit_failure','on',true)"
                    )
                    _post_recovery(
                        connection,
                        case,
                        review_id=recovery_review_id,
                        transaction_id=recovery_tx,
                        token="a" * 64,
                    )
            assert connection.execute(
                """
                SELECT
                    (SELECT count(*) FROM accounting.journal_entries),
                    (SELECT count(*) FROM accounting.ecl_post_writeoff_recoveries)
                """
            ).fetchone() == before_recovery

            recovery_id = _post_recovery(
                connection,
                case,
                review_id=recovery_review_id,
                transaction_id=recovery_tx,
                token="b" * 64,
            )
            assert _post_recovery(
                connection,
                case,
                review_id=recovery_review_id,
                transaction_id=recovery_tx,
                token="b" * 64,
            ) == recovery_id
            with pytest.raises(psycopg.Error, match="immutable retry identity"):
                with connection.transaction():
                    _post_recovery(
                        connection,
                        case,
                        review_id=recovery_review_id,
                        transaction_id=recovery_tx,
                        token="c" * 64,
                    )

            recovery_row = connection.execute(
                """
                SELECT journal_entry_id, recovery_amount
                FROM accounting.ecl_post_writeoff_recoveries
                WHERE id=%s
                """,
                (recovery_id,),
            ).fetchone()
            assert recovery_row is not None
            assert recovery_row[1] == Decimal("10.00")

            recovery_lines = connection.execute(
                """
                SELECT account.system_key, line.debit, line.credit
                FROM accounting.journal_lines line
                JOIN accounting.accounts account ON account.id=line.account_id
                WHERE line.journal_entry_id=%s
                ORDER BY line.line_number
                """,
                (recovery_row[0],),
            ).fetchall()
            assert recovery_lines == [
                ("cash_collector_custody", Decimal("10.00"), Decimal("0.00")),
                ("credit_loss_expense", Decimal("0.00"), Decimal("10.00")),
            ]
            assert _gross(connection, case[1])[4] == Decimal("0.00")
            assert connection.execute(
                "SELECT accounting.ecl_loan_allowance_balance(%s)",
                (case[1],),
            ).fetchone()[0] == Decimal("0.00")

            summary = connection.execute(
                "SELECT protected_a5_accounting_enabled, automatic_source_posting FROM accounting.ecl_a5_summary"
            ).fetchone()
            assert summary == (True, False)
        finally:
            connection.rollback()
