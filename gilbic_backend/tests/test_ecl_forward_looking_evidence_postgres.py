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
MIGRATIONS = tuple(
    (SQL_ROOT / name).read_text(encoding="utf-8")
    for name in (
        "0070_add_ecl_credit_risk_labels.sql",
        "0071_harden_ecl_cash_recovery_chronology.sql",
        "0072_add_ecl_quantitative_input_readiness.sql",
        "0073_add_ecl_forward_looking_evidence_governance.sql",
        "0074_integrate_ecl_forward_looking_readiness.sql",
    )
)


def _transaction_body(sql: str) -> str:
    body = sql.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    return body[len("BEGIN;") :].lstrip()[: -len("COMMIT;")].rstrip()


def test_forward_looking_evidence_is_versioned_stale_safe_and_clears_only_its_blocker() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        if connection.execute(
            "SELECT to_regclass('accounting.ecl_methodology_policy_v1')"
        ).fetchone()[0] is None:
            pytest.skip("0069 ECL methodology/source policy is not installed")

        try:
            for migration in MIGRATIONS:
                connection.execute(_transaction_body(migration))

            actor_user_id = connection.execute(
                """
                INSERT INTO core.users (username, full_name, status)
                VALUES (%s, %s, 'active')
                RETURNING id
                """,
                (f"ecl-forward-reviewer-{suffix}", f"ECL Forward Reviewer {suffix}"),
            ).fetchone()[0]

            loan_type_id = connection.execute(
                """
                INSERT INTO lending.loan_types (
                    code, name, term_days, calculation_mode, daily_interest_per_1000
                )
                VALUES (%s, %s, 120, 'fixed_daily', 7)
                RETURNING id
                """,
                (f"ECLFW-{suffix}", f"ECL Forward Test {suffix}"),
            ).fetchone()[0]
            client_id = connection.execute(
                """
                INSERT INTO lending.clients (client_code, full_name, status)
                VALUES (%s, %s, 'active')
                RETURNING id
                """,
                (f"ECLFW-C-{suffix}", f"ECL Forward Client {suffix}"),
            ).fetchone()[0]
            loan_id = connection.execute(
                """
                INSERT INTO lending.loans (
                    loan_number, client_id, loan_type_id, principal, daily_amount,
                    date_released, due_date, status, created_by_user_id
                )
                VALUES (
                    %s, %s, %s, 1000.00, 10.00,
                    current_date - 30, current_date + 90, 'active', %s
                )
                RETURNING id
                """,
                (f"ECLFW-L-{suffix}", client_id, loan_type_id, actor_user_id),
            ).fetchone()[0]

            before = connection.execute(
                """
                SELECT approved_forward_looking_evidence_ready, blocker_codes
                FROM accounting.ecl_quantitative_input_readiness
                WHERE loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert before is not None
            assert before[0] is False
            assert "approved_forward_looking_evidence_required" in before[1]

            with pytest.raises(psycopg.Error):
                connection.execute(
                    """
                    INSERT INTO accounting.ecl_forward_looking_evidence (
                        evidence_key, version, source_name, source_reference,
                        forecast_period_start, forecast_period_end, retrieved_at,
                        effective_date, management_interpretation, approved_by_user_id
                    ) VALUES (
                        'macro', 1, 'Direct bypass', 'bypass-ref', current_date,
                        current_date + 30, clock_timestamp(), current_date,
                        'This direct insert must be rejected by the immutable protected boundary.', %s
                    )
                    """,
                    (actor_user_id,),
                )
            connection.rollback()

            # Reinstall inside the new transaction because the deliberate bypass
            # error rolled back the setup transaction.
            for migration in MIGRATIONS:
                connection.execute(_transaction_body(migration))
            actor_user_id = connection.execute(
                """
                INSERT INTO core.users (username, full_name, status)
                VALUES (%s, %s, 'active')
                RETURNING id
                """,
                (f"ecl-forward-reviewer2-{suffix}", f"ECL Forward Reviewer 2 {suffix}"),
            ).fetchone()[0]
            loan_type_id = connection.execute(
                """
                INSERT INTO lending.loan_types (
                    code, name, term_days, calculation_mode, daily_interest_per_1000
                ) VALUES (%s, %s, 120, 'fixed_daily', 7) RETURNING id
                """,
                (f"ECLFW2-{suffix}", f"ECL Forward Test 2 {suffix}"),
            ).fetchone()[0]
            client_id = connection.execute(
                """
                INSERT INTO lending.clients (client_code, full_name, status)
                VALUES (%s, %s, 'active') RETURNING id
                """,
                (f"ECLFW2-C-{suffix}", f"ECL Forward Client 2 {suffix}"),
            ).fetchone()[0]
            loan_id = connection.execute(
                """
                INSERT INTO lending.loans (
                    loan_number, client_id, loan_type_id, principal, daily_amount,
                    date_released, due_date, status, created_by_user_id
                ) VALUES (
                    %s, %s, %s, 1000.00, 10.00,
                    current_date - 30, current_date + 90, 'active', %s
                ) RETURNING id
                """,
                (f"ECLFW2-L-{suffix}", client_id, loan_type_id, actor_user_id),
            ).fetchone()[0]

            history_before = connection.execute(
                """
                SELECT
                    (SELECT count(*) FROM accounting.journal_entries),
                    (SELECT count(*) FROM accounting.journal_lines),
                    (SELECT count(*) FROM accounting.ecl_credit_risk_label_reviews)
                """
            ).fetchone()

            first_id = connection.execute(
                """
                SELECT accounting.record_ecl_forward_looking_evidence(
                    'macro_philippines', 'Authoritative Test Source', 'source:v1',
                    current_date - 30, current_date,
                    current_date, current_date + 90,
                    clock_timestamp(), current_date,
                    'Management approves this exact retained source version as relevant forward-looking evidence.',
                    %s, NULL
                )
                """,
                (actor_user_id,),
            ).fetchone()[0]

            first = connection.execute(
                """
                SELECT version, evidence_status, ready_for_new_measurement,
                       scenario_probability_defaulted, multiplier_defaulted,
                       management_overlay_defaulted, ecl_calculation_enabled,
                       account_1190_posting_enabled, automatic_source_posting
                FROM accounting.ecl_forward_looking_evidence_status
                WHERE id = %s
                """,
                (first_id,),
            ).fetchone()
            assert first == (1, "current", True, False, False, False, False, False, False)

            after_first = connection.execute(
                """
                SELECT approved_forward_looking_evidence_ready, blocker_codes,
                       ecl_amount, ecl_calculation_enabled,
                       account_1190_posting_enabled, automatic_source_posting
                FROM accounting.ecl_quantitative_input_readiness
                WHERE loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert after_first is not None
            assert after_first[0] is True
            assert "approved_forward_looking_evidence_required" not in after_first[1]
            assert after_first[2:] == (None, False, False, False)

            second_id = connection.execute(
                """
                SELECT accounting.record_ecl_forward_looking_evidence(
                    'macro_philippines', 'Authoritative Test Source', 'source:v2',
                    current_date - 15, current_date,
                    current_date, current_date + 120,
                    clock_timestamp(), current_date,
                    'Management explicitly approves the newer retained source version for future measurements only.',
                    %s, %s
                )
                """,
                (actor_user_id, first_id),
            ).fetchone()[0]

            versions = connection.execute(
                """
                SELECT id, version, evidence_status, ready_for_new_measurement, source_reference
                FROM accounting.ecl_forward_looking_evidence_status
                WHERE evidence_key = 'macro_philippines'
                ORDER BY version
                """
            ).fetchall()
            assert versions == [
                (first_id, 1, "superseded", False, "source:v1"),
                (second_id, 2, "current", True, "source:v2"),
            ]

            connection.execute(
                "SELECT accounting.revoke_ecl_forward_looking_evidence(%s, %s, %s)",
                (second_id, "Source withdrawn", actor_user_id),
            )
            revoked = connection.execute(
                """
                SELECT evidence_status, ready_for_new_measurement
                FROM accounting.ecl_forward_looking_evidence_status
                WHERE id = %s
                """,
                (second_id,),
            ).fetchone()
            assert revoked == ("revoked", False)

            final_gate = connection.execute(
                """
                SELECT approved_forward_looking_evidence_ready, blocker_codes
                FROM accounting.ecl_quantitative_input_readiness
                WHERE loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert final_gate is not None
            assert final_gate[0] is False
            assert "approved_forward_looking_evidence_required" in final_gate[1]

            history_after = connection.execute(
                """
                SELECT
                    (SELECT count(*) FROM accounting.journal_entries),
                    (SELECT count(*) FROM accounting.journal_lines),
                    (SELECT count(*) FROM accounting.ecl_credit_risk_label_reviews)
                """
            ).fetchone()
            assert history_after == history_before
        finally:
            connection.rollback()
