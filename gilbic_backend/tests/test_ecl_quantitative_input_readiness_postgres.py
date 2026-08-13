from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
LABEL_SQL = (SQL_ROOT / "0070_add_ecl_credit_risk_labels.sql").read_text(encoding="utf-8")
CHRONOLOGY_SQL = (
    SQL_ROOT / "0071_harden_ecl_cash_recovery_chronology.sql"
).read_text(encoding="utf-8")
READINESS_SQL = (
    SQL_ROOT / "0072_add_ecl_quantitative_input_readiness.sql"
).read_text(encoding="utf-8")


def _transaction_body(sql: str) -> str:
    body = sql.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def test_quantitative_input_gate_exposes_exact_blockers_without_calculating_or_posting() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        if connection.execute(
            "SELECT to_regclass('accounting.ecl_methodology_policy_v1')"
        ).fetchone()[0] is None:
            pytest.skip("0069 ECL methodology/source policy is not installed")

        try:
            connection.execute(_transaction_body(LABEL_SQL))
            connection.execute(_transaction_body(CHRONOLOGY_SQL))

            actor_user_id = connection.execute(
                """
                INSERT INTO core.users (username, full_name, status)
                VALUES (%s, %s, 'active')
                RETURNING id
                """,
                (f"ecl-input-reviewer-{suffix}", f"ECL Input Reviewer {suffix}"),
            ).fetchone()[0]

            loan_type_id = connection.execute(
                """
                INSERT INTO lending.loan_types (
                    code, name, term_days, calculation_mode, daily_interest_per_1000
                )
                VALUES (%s, %s, 120, 'fixed_daily', 7)
                RETURNING id
                """,
                (f"ECLIN-{suffix}", f"ECL Input Test {suffix}"),
            ).fetchone()[0]

            client_id = connection.execute(
                """
                INSERT INTO lending.clients (client_code, full_name, status)
                VALUES (%s, %s, 'active')
                RETURNING id
                """,
                (f"ECLIN-C-{suffix}", f"ECL Input Client {suffix}"),
            ).fetchone()[0]

            loan_id = connection.execute(
                """
                INSERT INTO lending.loans (
                    loan_number, client_id, loan_type_id, principal, daily_amount,
                    date_released, due_date, status, created_by_user_id
                )
                VALUES (
                    %s, %s, %s, 1000.00, 10.00,
                    current_date - 120, current_date + 30, 'active', %s
                )
                RETURNING id
                """,
                (f"ECLIN-L-{suffix}", client_id, loan_type_id, actor_user_id),
            ).fetchone()[0]

            schedule_id = connection.execute(
                """
                INSERT INTO lending.loan_contract_schedules (
                    loan_id, schedule_version, payment_frequency,
                    contract_reference, contract_signed_date, effective_from,
                    grace_days, created_by_user_id
                )
                VALUES (
                    %s, 1, 'daily', %s,
                    current_date - 120, current_date - 120, 0, %s
                )
                RETURNING id
                """,
                (loan_id, f"ECLIN-CONTRACT-{suffix}", actor_user_id),
            ).fetchone()[0]

            connection.execute(
                """
                INSERT INTO lending.loan_contract_installments (
                    schedule_id, installment_number, due_date, contractual_amount
                )
                VALUES (%s, 1, current_date - 10, 1000.00)
                """,
                (schedule_id,),
            )

            review_id = connection.execute(
                """
                SELECT accounting.review_ecl_credit_risk_labels(
                    %s,
                    'stage_1_12_month',
                    false,
                    'none',
                    'none',
                    'contractual_dpd',
                    'ECL-INPUT-TEST-EVIDENCE',
                    'Typed note claims every input is complete, but notes cannot clear protected blockers.',
                    false,
                    false,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    %s
                )
                """,
                (loan_id, actor_user_id),
            ).fetchone()[0]
            assert review_id is not None

            before_history = connection.execute(
                """
                SELECT
                    (SELECT count(*) FROM accounting.journal_entries),
                    (SELECT count(*) FROM accounting.journal_lines),
                    (SELECT count(*) FROM accounting.ecl_credit_risk_label_reviews),
                    (SELECT count(*) FROM accounting.ecl_outcome_label_reviews)
                """
            ).fetchone()

            connection.execute(_transaction_body(READINESS_SQL))

            row = connection.execute(
                """
                SELECT
                    contractual_schedule_dpd_ready,
                    current_credit_risk_label_ready,
                    original_eir_initial_carrying_ready,
                    protected_collection_posting_reversal_history_ready,
                    authoritative_current_carrying_ready,
                    required_loss_recovery_writeoff_outcome_evidence_ready,
                    approved_forward_looking_evidence_ready,
                    blocker_codes,
                    blockers,
                    quantitative_input_ready,
                    ecl_amount,
                    ecl_calculation_enabled,
                    account_1190_posting_enabled,
                    automatic_source_posting
                FROM accounting.ecl_quantitative_input_readiness
                WHERE loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert row is not None
            assert row[:7] == (True, True, False, True, False, True, False)
            assert row[7] == [
                "original_eir_initial_carrying_evidence_required",
                "authoritative_current_gross_carrying_evidence_required",
                "approved_forward_looking_evidence_required",
            ]
            assert [item["code"] for item in row[8]] == row[7]
            assert row[8][-1]["source_status"] == "forward_looking_governance_not_installed"
            assert row[9:] == (False, None, False, False, False)

            summary = connection.execute(
                """
                SELECT
                    loan_count,
                    quantitative_input_ready_count,
                    original_eir_initial_carrying_blocked_count,
                    current_carrying_blocked_count,
                    forward_looking_evidence_blocked_count,
                    quantitative_ecl_ready,
                    ecl_amount,
                    ecl_calculation_enabled,
                    account_1190_posting_enabled,
                    automatic_source_posting
                FROM accounting.ecl_quantitative_input_readiness_summary
                """
            ).fetchone()
            assert summary is not None
            assert summary[0] >= 1
            assert summary[1] == 0
            assert summary[2] >= 1
            assert summary[3] >= 1
            assert summary[4] == summary[0]
            assert summary[5:] == (False, None, False, False, False)

            after_history = connection.execute(
                """
                SELECT
                    (SELECT count(*) FROM accounting.journal_entries),
                    (SELECT count(*) FROM accounting.journal_lines),
                    (SELECT count(*) FROM accounting.ecl_credit_risk_label_reviews),
                    (SELECT count(*) FROM accounting.ecl_outcome_label_reviews)
                """
            ).fetchone()
            assert after_history == before_history
        finally:
            connection.rollback()
