from __future__ import annotations

import importlib.util
import os
from datetime import timedelta
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
A3_HELPER_PATH = TEST_DIR / "test_ecl_read_only_measurement_postgres.py"
_spec = importlib.util.spec_from_file_location("ecl_a3_helpers", A3_HELPER_PATH)
assert _spec is not None and _spec.loader is not None
a3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(a3)

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
MIGRATIONS = tuple(
    (SQL_ROOT / name).read_text(encoding="utf-8")
    for name in (
        "0070_add_ecl_credit_risk_labels.sql",
        "0071_harden_ecl_cash_recovery_chronology.sql",
        "0072_add_ecl_quantitative_input_readiness.sql",
        "0073_add_ecl_forward_looking_evidence_governance.sql",
        "0074_integrate_ecl_forward_looking_readiness.sql",
        "0075_add_read_only_quantitative_ecl_measurement.sql",
        "0076_harden_read_only_quantitative_ecl_measurement.sql",
        "0077_add_protected_ecl_allowance_posting.sql",
    )
)

PREP_TOKEN = "a" * 64
POST_TOKEN = "b" * 64
DRAFT_POLICY = "ecl_allowance_initial_journal_draft_v1"
POSTING_POLICY = "ecl_allowance_initial_journal_posting_v1"


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    return body[len("BEGIN;") :].lstrip()[: -len("COMMIT;")].rstrip()


def _install(connection) -> None:
    for migration in MIGRATIONS:
        connection.execute(_transaction_body(migration))


def _measured_case(connection, suffix: str):
    actor_id = a3._actor(connection, suffix)
    release_date = connection.execute("SELECT current_date - 1").fetchone()[0]
    period_id = connection.execute(
        """
        INSERT INTO accounting.fiscal_periods (label, start_date, end_date, status)
        VALUES (%s, %s, %s, 'open')
        RETURNING id
        """,
        (f"ECL A4 {suffix}", release_date, release_date + timedelta(days=120)),
    ).fetchone()[0]

    _, loan_id = a3._loan(
        connection,
        suffix=suffix,
        actor_id=actor_id,
        release_date=release_date,
    )
    release_event_id = a3._record_release(
        connection,
        loan_id=loan_id,
        actor_id=actor_id,
        business_date=release_date,
        reference=f"ECLA4-REL-{suffix}",
    )
    a3._prepare_and_post_release(
        connection,
        event_id=release_event_id,
        actor_id=actor_id,
        token_char="c",
    )
    a3._register_schedule(
        connection,
        loan_id=loan_id,
        actor_id=actor_id,
        release_date=release_date,
        suffix=suffix,
    )
    a3._review_stage(
        connection,
        loan_id=loan_id,
        actor_id=actor_id,
        stage="stage_1_12_month",
        basis="contractual_dpd",
        reference=f"ECLA4-STAGE1-{suffix}",
    )
    evidence_a = a3._forward_evidence(
        connection,
        actor_id=actor_id,
        key=f"ecla4-macro-{suffix}",
        reference=f"ECLA4-MACRO-{suffix}",
    )
    evidence_b = a3._forward_evidence(
        connection,
        actor_id=actor_id,
        key=f"ecla4-portfolio-{suffix}",
        reference=f"ECLA4-PORTFOLIO-{suffix}",
    )
    measurement_id = a3._measure(
        connection,
        loan_id=loan_id,
        actor_id=actor_id,
        scenarios=a3._scenario_payload(
            evidence_ids=[evidence_b, evidence_a],
            release_date=release_date,
        ),
    )
    measurement = connection.execute(
        """
        SELECT id, loan_id, measurement_version, measurement_date,
               calculation_digest, ecl_amount
        FROM accounting.ecl_quantitative_measurements
        WHERE id = %s
        """,
        (measurement_id,),
    ).fetchone()
    assert measurement is not None
    assert measurement[5] > 0

    account_ids = connection.execute(
        """
        SELECT
            max(id) FILTER (WHERE system_key = 'credit_loss_expense'),
            max(id) FILTER (WHERE system_key = 'allowance_expected_credit_loss')
        FROM accounting.accounts
        """
    ).fetchone()
    assert account_ids is not None and all(account_ids)
    return actor_id, loan_id, period_id, measurement, account_ids


def _prepare(connection, actor_id, period_id, measurement, account_ids, token=PREP_TOKEN):
    return connection.execute(
        """
        SELECT accounting.prepare_initial_ecl_allowance_journal(
            %s, %s, %s, %s, %s, %s, %s, %s, %s, 0.00, %s
        )
        """,
        (
            measurement[0],
            actor_id,
            token,
            measurement[4],
            measurement[5],
            measurement[3],
            period_id,
            account_ids[0],
            account_ids[1],
            DRAFT_POLICY,
        ),
    ).fetchone()[0]


def _preparation(connection, preparation_id):
    row = connection.execute(
        """
        SELECT id, measurement_id, loan_id, client_id, measurement_version,
               measurement_date, calculation_digest, journal_entry_id,
               source_event_key, posting_date, fiscal_period_id,
               credit_loss_expense_account_id, allowance_account_id,
               allowance_amount, prior_allowance_balance,
               preparation_review_token, preparation_digest, draft_policy_version
        FROM accounting.ecl_allowance_draft_preparations
        WHERE id = %s
        """,
        (preparation_id,),
    ).fetchone()
    assert row is not None
    return row


def _post(connection, actor_id, prepared, token=POST_TOKEN):
    return connection.execute(
        """
        SELECT accounting.post_initial_ecl_allowance_journal(
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            prepared[0],
            actor_id,
            token,
            prepared[1],
            prepared[6],
            prepared[7],
            prepared[8],
            prepared[16],
            prepared[9],
            prepared[10],
            prepared[11],
            prepared[12],
            prepared[13],
            prepared[14],
            POSTING_POLICY,
        ),
    ).fetchone()[0]


def test_a4_initial_allowance_is_exact_audited_idempotent_and_manual_bypass_blocked() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            actor_id, loan_id, period_id, measurement, account_ids = _measured_case(
                connection, suffix
            )

            # Baseline after the legitimate protected loan-release posting. A4
            # must add only its own allowance journal and immutable audit evidence.
            before_a4_journals = connection.execute(
                """
                SELECT count(*), (SELECT count(*) FROM accounting.journal_lines)
                FROM accounting.journal_entries
                """
            ).fetchone()

            queue = connection.execute(
                """
                SELECT measurement_id, measurement_status, authoritative_ecl_amount,
                       current_allowance_balance, allowance_posting_status,
                       protected_allowance_action_ready,
                       account_1190_posting_enabled, automatic_source_posting
                FROM accounting.ecl_allowance_posting_queue
                WHERE loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert queue == (
                measurement[0],
                "measured_read_only",
                measurement[5],
                0,
                "preparation_required",
                True,
                True,
                False,
            )

            # Account 1190 is no longer writable through a generic/manual journal.
            manual_entry_id = connection.execute(
                """
                INSERT INTO accounting.journal_entries (
                    fiscal_period_id, posting_date, description,
                    source_type, source_reference, source_event_key,
                    created_by_user_id
                ) VALUES (%s, current_date, 'manual 1190 bypass test',
                          'manual_test', 'ecl-a4-bypass', %s, %s)
                RETURNING id
                """,
                (period_id, f"manual-a4:{uuid4()}", actor_id),
            ).fetchone()[0]
            with pytest.raises(psycopg.Error, match="Account 1190"):
                with connection.transaction():
                    connection.execute(
                        """
                        INSERT INTO accounting.journal_lines (
                            journal_entry_id, line_number, account_id, description,
                            debit, credit, client_id, loan_id
                        )
                        SELECT %s, 1, id, 'manual 1190 bypass', 0, 1.00, NULL, %s
                        FROM accounting.accounts
                        WHERE system_key = 'allowance_expected_credit_loss'
                        """,
                        (manual_entry_id, loan_id),
                    )

            preparation_id = _prepare(
                connection, actor_id, period_id, measurement, account_ids
            )
            assert _prepare(
                connection, actor_id, period_id, measurement, account_ids
            ) == preparation_id
            prepared = _preparation(connection, preparation_id)
            assert prepared[1] == measurement[0]
            assert prepared[2] == loan_id
            assert prepared[4] == measurement[2]
            assert prepared[6] == measurement[4]
            assert prepared[9] == measurement[3]
            assert prepared[10] == period_id
            assert prepared[11:13] == account_ids
            assert prepared[13] == measurement[5]
            assert prepared[14] == 0
            assert prepared[15] == PREP_TOKEN
            assert prepared[17] == DRAFT_POLICY

            journal_state = connection.execute(
                """
                SELECT status, entry_number, source_type, source_reference,
                       source_event_key, posting_date, fiscal_period_id
                FROM accounting.journal_entries
                WHERE id = %s
                """,
                (prepared[7],),
            ).fetchone()
            assert journal_state == (
                "draft",
                None,
                "ecl_allowance",
                str(measurement[0]),
                prepared[8],
                measurement[3],
                period_id,
            )

            lines = connection.execute(
                """
                SELECT line.line_number, account.code, account.system_key,
                       line.debit, line.credit, line.client_id, line.loan_id
                FROM accounting.journal_lines line
                JOIN accounting.accounts account ON account.id = line.account_id
                WHERE line.journal_entry_id = %s
                ORDER BY line.line_number
                """,
                (prepared[7],),
            ).fetchall()
            assert [(row[0], row[1], row[2], row[3], row[4]) for row in lines] == [
                (1, "5000", "credit_loss_expense", measurement[5], 0),
                (2, "1190", "allowance_expected_credit_loss", 0, measurement[5]),
            ]
            assert all(row[6] == loan_id for row in lines)
            assert all(row[5] is not None for row in lines)

            with pytest.raises(psycopg.Error, match="protected allowance posting workflow"):
                with connection.transaction():
                    connection.execute(
                        "SELECT accounting.post_journal_entry(%s, %s)",
                        (prepared[7], actor_id),
                    )

            with pytest.raises(psycopg.Error, match="system generated and immutable"):
                with connection.transaction():
                    connection.execute(
                        """
                        UPDATE accounting.journal_lines
                        SET debit = debit + 1
                        WHERE journal_entry_id = %s AND line_number = 1
                        """,
                        (prepared[7],),
                    )

            posting_id = _post(connection, actor_id, prepared)
            assert _post(connection, actor_id, prepared) == posting_id
            with pytest.raises(psycopg.Error, match="confirmed posting identity"):
                with connection.transaction():
                    _post(connection, actor_id, prepared, token="d" * 64)

            posted = connection.execute(
                """
                SELECT id, preparation_id, measurement_id, journal_entry_id,
                       allowance_amount, prior_allowance_balance,
                       resulting_allowance_balance, posting_review_token,
                       posting_policy_version, entry_number
                FROM accounting.ecl_allowance_postings
                WHERE id = %s
                """,
                (posting_id,),
            ).fetchone()
            assert posted is not None
            assert posted[1] == preparation_id
            assert posted[2] == measurement[0]
            assert posted[3] == prepared[7]
            assert posted[4:7] == (measurement[5], 0, measurement[5])
            assert posted[7] == POST_TOKEN
            assert posted[8] == POSTING_POLICY
            assert posted[9]

            posting_lines = connection.execute(
                """
                SELECT line.line_number, line.account_system_key,
                       line.debit, line.credit, line.client_id, line.loan_id
                FROM accounting.ecl_allowance_posting_lines line
                WHERE line.posting_id = %s
                ORDER BY line.line_number
                """,
                (posting_id,),
            ).fetchall()
            assert [
                (row[0], row[1], row[2], row[3], row[5]) for row in posting_lines
            ] == [
                (1, "credit_loss_expense", measurement[5], 0, loan_id),
                (2, "allowance_expected_credit_loss", 0, measurement[5], loan_id),
            ]

            assert connection.execute(
                "SELECT accounting.ecl_loan_allowance_balance(%s)", (loan_id,)
            ).fetchone()[0] == measurement[5]

            with pytest.raises(psycopg.Error, match="manual General Journal"):
                with connection.transaction():
                    connection.execute(
                        "SELECT accounting.create_reversal_draft(%s, %s, current_date, %s)",
                        (prepared[7], actor_id, "manual A4 reversal bypass"),
                    )

            with pytest.raises(psycopg.Error, match="posting audit is immutable"):
                with connection.transaction():
                    connection.execute(
                        "UPDATE accounting.ecl_allowance_postings SET posting_review_token = %s WHERE id = %s",
                        ("e" * 64, posting_id),
                    )

            after_a4_journals = connection.execute(
                """
                SELECT count(*), (SELECT count(*) FROM accounting.journal_lines)
                FROM accounting.journal_entries
                """
            ).fetchone()
            # One manual test draft plus the one protected A4 journal were created;
            # only the protected A4 journal is posted. The manual test entry carries
            # no 1190 line and rolls back with this integration test.
            assert after_a4_journals[0] == before_a4_journals[0] + 2
            assert after_a4_journals[1] == before_a4_journals[1] + 2

            final_queue = connection.execute(
                """
                SELECT allowance_posting_status, current_allowance_balance,
                       protected_allowance_action_ready,
                       account_1190_posting_enabled, automatic_source_posting
                FROM accounting.ecl_allowance_posting_queue
                WHERE loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert final_queue == (
                "posted_current", measurement[5], False, True, False
            )
        finally:
            connection.rollback()


def test_a4_revalidates_period_and_prior_allowance_and_forced_audit_failure_rolls_back() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            actor_id, loan_id, period_id, measurement, account_ids = _measured_case(
                connection, suffix
            )
            preparation_id = _prepare(
                connection, actor_id, period_id, measurement, account_ids
            )
            prepared = _preparation(connection, preparation_id)

            connection.execute(
                "SELECT accounting.set_fiscal_period_status(%s, 'review', %s)",
                (period_id, actor_id),
            )
            with pytest.raises(psycopg.Error, match="open fiscal period"):
                with connection.transaction():
                    _post(connection, actor_id, prepared)
            assert connection.execute(
                "SELECT status, entry_number FROM accounting.journal_entries WHERE id = %s",
                (prepared[7],),
            ).fetchone() == ("draft", None)

            connection.execute(
                "SELECT accounting.set_fiscal_period_status(%s, 'open', %s)",
                (period_id, actor_id),
            )

            connection.execute(
                """
                CREATE OR REPLACE FUNCTION accounting.test_fail_ecl_allowance_posting_audit_insert()
                RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                    RAISE EXCEPTION 'forced ecl allowance posting audit failure';
                END;
                $$
                """
            )
            connection.execute(
                """
                CREATE TRIGGER zz_test_fail_ecl_allowance_posting_audit_insert
                BEFORE INSERT ON accounting.ecl_allowance_postings
                FOR EACH ROW EXECUTE FUNCTION accounting.test_fail_ecl_allowance_posting_audit_insert()
                """
            )

            with pytest.raises(
                psycopg.Error,
                match="forced ecl allowance posting audit failure",
            ):
                with connection.transaction():
                    _post(connection, actor_id, prepared)

            assert connection.execute(
                """
                SELECT status, entry_number, posted_by_user_id, posted_at
                FROM accounting.journal_entries WHERE id = %s
                """,
                (prepared[7],),
            ).fetchone() == ("draft", None, None, None)
            assert connection.execute(
                "SELECT count(*) FROM accounting.ecl_allowance_postings WHERE preparation_id = %s",
                (preparation_id,),
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT accounting.ecl_loan_allowance_balance(%s)", (loan_id,)
            ).fetchone()[0] == 0
        finally:
            connection.rollback()
