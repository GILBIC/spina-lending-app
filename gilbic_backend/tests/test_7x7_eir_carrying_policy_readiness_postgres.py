from __future__ import annotations

import os
from datetime import date, timedelta
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

SQL_0061 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0061_add_7x7_eir_carrying_policy_readiness.sql"
).read_text(encoding="utf-8")


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _actor(connection, suffix: str):
    return connection.execute(
        """
        insert into core.users (username, full_name, status)
        values (%s, %s, 'active') returning id
        """,
        (f"x7eir-{suffix}", f"7x7 EIR Policy {suffix}"),
    ).fetchone()[0]


def _loan_type(connection, suffix: str):
    return connection.execute(
        """
        insert into lending.loan_types (
            code, name, term_days, calculation_mode,
            daily_interest_per_1000, settings
        ) values (
            %s, %s, 120, 'seven_by_seven', 7.00,
            jsonb_build_object(
                'contractual_interest_payment_frequency', 'daily',
                'contractual_principal_due', 'on_or_before_maturity',
                'principal_prepayment_allowed', true,
                'principal_prepayment_changes_daily_interest', false,
                'mobile_collections_enabled', false
            )
        ) returning id
        """,
        (f"X7EIR-{suffix}", f"7x7 EIR Policy {suffix}"),
    ).fetchone()[0]


def _loan(connection, *, suffix: str, actor_id, loan_type_id, release_date: date):
    client_id = connection.execute(
        """
        insert into lending.clients (client_code, full_name, status)
        values (%s, %s, 'active') returning id
        """,
        (f"X7EIR-C-{suffix}", f"7x7 EIR Client {suffix}"),
    ).fetchone()[0]
    return connection.execute(
        """
        insert into lending.loans (
            loan_number, client_id, loan_type_id, principal, daily_amount,
            date_released, due_date, status, created_by_user_id
        ) values (
            %s, %s, %s, 3000.00, 21.00,
            %s, %s, 'active', %s
        ) returning id
        """,
        (
            f"X7EIR-L-{suffix}",
            client_id,
            loan_type_id,
            release_date,
            release_date + timedelta(days=120),
            actor_id,
        ),
    ).fetchone()[0]


def _verified_schedule(connection, *, loan_id, actor_id, release_date: date, suffix: str):
    schedule_id = connection.execute(
        """
        insert into lending.loan_contract_schedules (
            loan_id, schedule_version, status, payment_frequency,
            contract_reference, contract_signed_date, effective_from,
            grace_days, settings, created_by_user_id
        ) values (
            %s, 1, 'active', 'daily', %s, %s, %s,
            0, '{}'::jsonb, %s
        ) returning id
        """,
        (
            loan_id,
            f"X7EIR-CONTRACT-{suffix}",
            release_date,
            release_date,
            actor_id,
        ),
    ).fetchone()[0]
    connection.execute(
        """
        insert into lending.loan_contract_installments (
            schedule_id, installment_number, due_date, contractual_amount,
            principal_component, interest_component
        )
        select
            %s,
            day_number,
            %s::date + day_number,
            case when day_number = 120 then 3021.00::numeric else 21.00::numeric end,
            case when day_number = 120 then 3000.00::numeric else 0.00::numeric end,
            21.00::numeric
        from generate_series(1, 120) day_number
        """,
        (schedule_id, release_date),
    )
    connection.execute(
        """
        insert into lending.loan_contract_schedule_registrations (
            schedule_id, evidence_basis, evidence_reference,
            verification_note, verified_by_user_id
        ) values (%s, 'signed_contract', %s, %s, %s)
        """,
        (
            schedule_id,
            f"X7EIR-EVIDENCE-{suffix}",
            "Verified exact 7x7 signed-contract schedule for EIR policy separation",
            actor_id,
        ),
    )
    return schedule_id


def test_verified_schedule_solves_base_math_but_authoritative_eir_and_carrying_stay_blocked() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    release_date = date(2092, 2, 1)

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0061))
            actor_id = _actor(connection, suffix)
            loan_type_id = _loan_type(connection, suffix)
            loan_id = _loan(
                connection,
                suffix=suffix,
                actor_id=actor_id,
                loan_type_id=loan_type_id,
                release_date=release_date,
            )
            schedule_id = _verified_schedule(
                connection,
                loan_id=loan_id,
                actor_id=actor_id,
                release_date=release_date,
                suffix=suffix,
            )

            contract_gate = connection.execute(
                """
                select readiness_status, contractual_cash_flow_validation_ready
                from accounting.seven_by_seven_contractual_cash_flow_readiness
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert contract_gate == ("pfrs9_contract_cash_flow_ready", True)

            solved = connection.execute(
                "select accounting.solve_verified_schedule_daily_eir_preview(%s, 3000.00)",
                (schedule_id,),
            ).fetchone()[0]
            assert solved == Decimal("0.007000000000")

            policy = connection.execute(
                """
                select
                    operational_daily_contractual_interest,
                    operational_daily_rate_on_original_principal,
                    base_no_prepayment_daily_eir_preview,
                    base_no_prepayment_daily_eir_percent,
                    operational_rate_matches_base_math_preview,
                    principal_prepayment_allowed,
                    principal_prepayment_changes_daily_interest,
                    business_model_assessment_required,
                    sppi_assessment_required,
                    prepayment_expected_cash_flow_policy_required,
                    expected_life_assessment_required,
                    authoritative_daily_eir,
                    authoritative_initial_gross_carrying_amount,
                    authoritative_current_gross_carrying_amount,
                    policy_readiness_status,
                    sppi_classification_concluded,
                    business_model_classification_concluded,
                    expected_cash_flow_policy_approved,
                    eir_policy_ready,
                    carrying_amount_ready,
                    journal_lines_enabled,
                    automatic_source_posting
                from accounting.seven_by_seven_eir_carrying_policy_readiness
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert policy is not None
            assert policy[0] == Decimal("21.00")
            assert policy[1] == Decimal("0.007000000000")
            assert policy[2] == Decimal("0.007000000000")
            assert policy[3] == Decimal("0.70000000")
            assert policy[4] is True
            assert policy[5] is True
            assert policy[6] is False
            assert policy[7:11] == (True, True, True, True)
            assert policy[11:14] == (None, None, None)
            assert policy[14] == "sppi_and_prepayment_policy_review_required"
            assert policy[15:] == (False, False, False, False, False, False, False)

            # A matching mathematical rate in the untouched base schedule is
            # explicitly not promoted into authoritative accounting measurement.
            assert policy[2] == policy[1]
            assert policy[11] is None

            summary = connection.execute(
                """
                select
                    base_eir_preview_solved_count,
                    sppi_and_prepayment_review_required_count,
                    sppi_classification_concluded,
                    business_model_classification_concluded,
                    expected_cash_flow_policy_approved,
                    eir_policy_ready,
                    carrying_amount_ready,
                    journal_lines_enabled,
                    automatic_source_posting
                from accounting.seven_by_seven_eir_carrying_policy_summary
                """
            ).fetchone()
            assert summary is not None
            assert summary[0] >= 1
            assert summary[1] >= 1
            assert summary[2:] == (False, False, False, False, False, False, False)
        finally:
            connection.rollback()


def test_missing_verified_contract_keeps_even_base_eir_preview_blocked() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    release_date = date(2092, 3, 1)

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0061))
            actor_id = _actor(connection, suffix)
            loan_type_id = _loan_type(connection, suffix)
            loan_id = _loan(
                connection,
                suffix=suffix,
                actor_id=actor_id,
                loan_type_id=loan_type_id,
                release_date=release_date,
            )

            policy = connection.execute(
                """
                select base_no_prepayment_daily_eir_preview,
                       authoritative_daily_eir,
                       policy_readiness_status,
                       eir_policy_ready,
                       carrying_amount_ready,
                       journal_lines_enabled,
                       automatic_source_posting
                from accounting.seven_by_seven_eir_carrying_policy_readiness
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert policy == (
                None,
                None,
                "contractual_cash_flow_readiness_required",
                False,
                False,
                False,
                False,
            )
        finally:
            connection.rollback()
