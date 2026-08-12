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

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
SQL_0060 = (
    SQL_ROOT / "0060_add_7x7_contractual_cash_flow_readiness.sql"
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
        (f"x7cf-{suffix}", f"7x7 Contract Cash Flow {suffix}"),
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
        (f"X7CF-{suffix}", f"7x7 Contract Cash Flow {suffix}"),
    ).fetchone()[0]


def _loan(connection, *, suffix: str, actor_id, loan_type_id, release_date: date):
    client_id = connection.execute(
        """
        insert into lending.clients (client_code, full_name, status)
        values (%s, %s, 'active') returning id
        """,
        (f"X7CF-C-{suffix}", f"7x7 Cash Flow Client {suffix}"),
    ).fetchone()[0]
    loan_id = connection.execute(
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
            f"X7CF-L-{suffix}",
            client_id,
            loan_type_id,
            release_date,
            release_date + timedelta(days=120),
            actor_id,
        ),
    ).fetchone()[0]
    return loan_id


def _schedule(
    connection,
    *,
    loan_id,
    actor_id,
    release_date: date,
    suffix: str,
    evidence_basis: str | None = "signed_contract",
    final_includes_principal: bool = True,
    first_principal_component: str = "0.00",
):
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
            f"X7CF-CONTRACT-{suffix}",
            release_date,
            release_date,
            actor_id,
        ),
    ).fetchone()[0]

    final_amount = Decimal("3021.00") if final_includes_principal else Decimal("21.00")
    final_principal = Decimal("3000.00") if final_includes_principal else Decimal("0.00")
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
            case when day_number = 120 then %s::numeric else 21.00::numeric end,
            case
                when day_number = 1 then %s::numeric
                when day_number = 120 then %s::numeric
                else 0.00::numeric
            end,
            21.00::numeric
        from generate_series(1, 120) day_number
        """,
        (
            schedule_id,
            release_date,
            final_amount,
            Decimal(first_principal_component),
            final_principal,
        ),
    )

    if evidence_basis is not None:
        connection.execute(
            """
            insert into lending.loan_contract_schedule_registrations (
                schedule_id, evidence_basis, evidence_reference,
                verification_note, verified_by_user_id
            ) values (%s, %s, %s, %s, %s)
            """,
            (
                schedule_id,
                evidence_basis,
                f"X7CF-EVIDENCE-{suffix}",
                "Verified exact 7x7 contractual cash-flow schedule",
                actor_id,
            ),
        )
    return schedule_id


def _readiness(connection, loan_id):
    return connection.execute(
        """
        select
            expected_daily_contractual_interest,
            expected_contractual_interest_total,
            expected_contractual_total_no_prepayment,
            installment_count,
            first_due_date,
            last_due_date,
            contractual_schedule_total,
            line_mismatch_count,
            readiness_status,
            contractual_cash_flow_validation_ready,
            prepayment_option_requires_eir_estimate,
            validated_base_schedule_basis,
            sppi_classification_concluded,
            eir_policy_ready,
            carrying_amount_ready,
            journal_lines_enabled,
            automatic_source_posting
        from accounting.seven_by_seven_contractual_cash_flow_readiness
        where loan_id = %s
        """,
        (loan_id,),
    ).fetchone()


def test_verified_7x7_base_contract_cash_flows_are_exact_and_follow_on_policy_stays_off() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    release_date = date(2091, 1, 10)

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0060))
            actor_id = _actor(connection, suffix)
            loan_type_id = _loan_type(connection, suffix)

            valid_loan = _loan(
                connection,
                suffix=f"{suffix}-valid",
                actor_id=actor_id,
                loan_type_id=loan_type_id,
                release_date=release_date,
            )
            _schedule(
                connection,
                loan_id=valid_loan,
                actor_id=actor_id,
                release_date=release_date,
                suffix=f"{suffix}-valid",
            )

            valid = _readiness(connection, valid_loan)
            assert valid is not None
            assert valid[0] == Decimal("21.00")
            assert valid[1] == Decimal("2520.00")
            assert valid[2] == Decimal("5520.00")
            assert valid[3] == 120
            assert valid[4] == release_date + timedelta(days=1)
            assert valid[5] == release_date + timedelta(days=120)
            assert valid[6] == Decimal("5520.00")
            assert valid[7] == 0
            assert valid[8] == "pfrs9_contract_cash_flow_ready"
            assert valid[9] is True
            assert valid[10] is True
            assert valid[11] == "no_prepayment_through_maturity_base_schedule"
            assert valid[12:] == (False, False, False, False, False)

            final_line = connection.execute(
                """
                select contractual_amount, principal_component, interest_component,
                       expected_contractual_amount, expected_principal_component,
                       expected_interest_component, line_status
                from accounting.seven_by_seven_contractual_cash_flow_lines
                where loan_id = %s and installment_number = 120
                """,
                (valid_loan,),
            ).fetchone()
            assert final_line == (
                Decimal("3021.00"),
                Decimal("3000.00"),
                Decimal("21.00"),
                Decimal("3021.00"),
                Decimal("3000.00"),
                Decimal("21.00"),
                "line_ready",
            )

            no_principal_loan = _loan(
                connection,
                suffix=f"{suffix}-noprin",
                actor_id=actor_id,
                loan_type_id=loan_type_id,
                release_date=release_date,
            )
            _schedule(
                connection,
                loan_id=no_principal_loan,
                actor_id=actor_id,
                release_date=release_date,
                suffix=f"{suffix}-noprin",
                final_includes_principal=False,
            )
            no_principal = _readiness(connection, no_principal_loan)
            assert no_principal is not None
            assert no_principal[8] == "contract_cash_flow_mismatch"
            assert no_principal[9] is False

            early_principal_loan = _loan(
                connection,
                suffix=f"{suffix}-early",
                actor_id=actor_id,
                loan_type_id=loan_type_id,
                release_date=release_date,
            )
            _schedule(
                connection,
                loan_id=early_principal_loan,
                actor_id=actor_id,
                release_date=release_date,
                suffix=f"{suffix}-early",
                first_principal_component="100.00",
            )
            early = _readiness(connection, early_principal_loan)
            assert early is not None
            assert early[8] == "contract_cash_flow_mismatch"
            assert early[9] is False

            unverified_loan = _loan(
                connection,
                suffix=f"{suffix}-unverified",
                actor_id=actor_id,
                loan_type_id=loan_type_id,
                release_date=release_date,
            )
            _schedule(
                connection,
                loan_id=unverified_loan,
                actor_id=actor_id,
                release_date=release_date,
                suffix=f"{suffix}-unverified",
                evidence_basis=None,
            )
            unverified = _readiness(connection, unverified_loan)
            assert unverified is not None
            assert unverified[8] == "verified_signed_contract_schedule_required"
            assert unverified[9] is False

            renewal_loan = _loan(
                connection,
                suffix=f"{suffix}-renewal",
                actor_id=actor_id,
                loan_type_id=loan_type_id,
                release_date=release_date,
            )
            _schedule(
                connection,
                loan_id=renewal_loan,
                actor_id=actor_id,
                release_date=release_date,
                suffix=f"{suffix}-renewal",
                evidence_basis="signed_renewal_contract",
            )
            renewal = _readiness(connection, renewal_loan)
            assert renewal is not None
            assert renewal[8] == "renewal_or_restructure_policy_required"
            assert renewal[9] is False

            summary = connection.execute(
                """
                select seven_by_seven_loan_count, ready_count,
                       review_required_count, sppi_classification_concluded,
                       eir_policy_ready, carrying_amount_ready,
                       journal_lines_enabled, automatic_source_posting
                from accounting.seven_by_seven_contractual_cash_flow_summary
                """
            ).fetchone()
            assert summary is not None
            assert summary[1] >= 1
            assert summary[2] >= 4
            assert summary[3:] == (False, False, False, False, False)
        finally:
            connection.rollback()
