from __future__ import annotations

import os
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from gilbic_backend.seven_by_seven_signed_schedule import (
    generate_signed_seven_by_seven_schedule,
)


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
SQL_0060 = (
    SQL_ROOT / "0060_add_7x7_contractual_cash_flow_readiness.sql"
).read_text(encoding="utf-8")
SQL_0115 = (
    SQL_ROOT / "0115_align_7x7_signed_schedule_accounting_authority.sql"
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
            %s, %s, 60, 'seven_by_seven', 7.00,
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


def _loan(
    connection,
    *,
    suffix: str,
    actor_id,
    loan_type_id,
    release_date: date,
    due_date: date,
):
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
            %s, %s, %s, 3000.00, 50.00,
            %s, %s, 'active', %s
        ) returning id
        """,
        (
            f"X7CF-L-{suffix}",
            client_id,
            loan_type_id,
            release_date,
            due_date,
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
    corrupt_first_principal: bool = False,
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

    rows = generate_signed_seven_by_seven_schedule(
        original_principal=Decimal("3000.00"),
        agreed_daily_payment=Decimal("50.00"),
        daily_interest_per_1000=Decimal("7.00"),
        first_due_date=release_date + timedelta(days=1),
    )
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            insert into lending.loan_contract_installments (
                schedule_id, installment_number, due_date, contractual_amount,
                principal_component, interest_component
            ) values (%s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    schedule_id,
                    row.installment_number,
                    row.due_date,
                    row.contractual_amount,
                    (
                        Decimal("28.00")
                        if corrupt_first_principal and row.installment_number == 1
                        else row.principal_component
                    ),
                    row.interest_component,
                )
                for row in rows
            ],
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
                "Verified exact 7x7 borrower/Management-approved daily-payment schedule",
                actor_id,
            ),
        )
    return schedule_id, rows


def _readiness(connection, loan_id):
    return connection.execute(
        """
        select
            expected_daily_contractual_interest,
            expected_contractual_interest_total,
            expected_contractual_total_no_prepayment,
            term_days,
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


def test_verified_signed_7x7_schedule_is_the_accounting_cash_flow_authority() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    release_date = date(2091, 1, 10)
    signed_maturity = release_date + timedelta(days=104)

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0060))
            connection.execute(_transaction_body(SQL_0115))
            actor_id = _actor(connection, suffix)
            loan_type_id = _loan_type(connection, suffix)

            valid_loan = _loan(
                connection,
                suffix=f"{suffix}-valid",
                actor_id=actor_id,
                loan_type_id=loan_type_id,
                release_date=release_date,
                due_date=signed_maturity,
            )
            _, rows = _schedule(
                connection,
                loan_id=valid_loan,
                actor_id=actor_id,
                release_date=release_date,
                suffix=f"{suffix}-valid",
            )
            assert len(rows) == 104

            valid = _readiness(connection, valid_loan)
            assert valid is not None
            assert valid[0] == Decimal("21.00")
            assert valid[1] == Decimal("2184.00")
            assert valid[2] == Decimal("5184.00")
            assert valid[3] == 104
            assert valid[4] == 104
            assert valid[5] == release_date + timedelta(days=1)
            assert valid[6] == signed_maturity
            assert valid[7] == Decimal("5184.00")
            assert valid[8] == 0
            assert valid[9] == "pfrs9_contract_cash_flow_ready"
            assert valid[10] is True
            assert valid[11] is True
            assert valid[12] == "no_prepayment_through_maturity_base_schedule"
            assert valid[13:] == (False, False, False, False, False)

            final_line = connection.execute(
                """
                select contractual_amount, principal_component, interest_component,
                       expected_contractual_amount, expected_principal_component,
                       expected_interest_component, line_status
                from accounting.seven_by_seven_contractual_cash_flow_lines
                where loan_id = %s and installment_number = 104
                """,
                (valid_loan,),
            ).fetchone()
            assert final_line == (
                Decimal("34.00"),
                Decimal("13.00"),
                Decimal("21.00"),
                Decimal("34.00"),
                Decimal("13.00"),
                Decimal("21.00"),
                "line_ready",
            )

            stale_due_loan = _loan(
                connection,
                suffix=f"{suffix}-stale-due",
                actor_id=actor_id,
                loan_type_id=loan_type_id,
                release_date=release_date,
                due_date=release_date + timedelta(days=60),
            )
            _schedule(
                connection,
                loan_id=stale_due_loan,
                actor_id=actor_id,
                release_date=release_date,
                suffix=f"{suffix}-stale-due",
            )
            stale_due = _readiness(connection, stale_due_loan)
            assert stale_due is not None
            assert stale_due[9] == "contract_cash_flow_mismatch"
            assert stale_due[10] is False

            corrupt_component_loan = _loan(
                connection,
                suffix=f"{suffix}-bad-component",
                actor_id=actor_id,
                loan_type_id=loan_type_id,
                release_date=release_date,
                due_date=signed_maturity,
            )
            _schedule(
                connection,
                loan_id=corrupt_component_loan,
                actor_id=actor_id,
                release_date=release_date,
                suffix=f"{suffix}-bad-component",
                corrupt_first_principal=True,
            )
            corrupt = _readiness(connection, corrupt_component_loan)
            assert corrupt is not None
            assert corrupt[9] == "contract_cash_flow_mismatch"
            assert corrupt[10] is False

            unverified_loan = _loan(
                connection,
                suffix=f"{suffix}-unverified",
                actor_id=actor_id,
                loan_type_id=loan_type_id,
                release_date=release_date,
                due_date=signed_maturity,
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
            assert unverified[9] == "verified_signed_contract_schedule_required"
            assert unverified[10] is False

            renewal_loan = _loan(
                connection,
                suffix=f"{suffix}-renewal",
                actor_id=actor_id,
                loan_type_id=loan_type_id,
                release_date=release_date,
                due_date=signed_maturity,
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
            assert renewal[9] == "renewal_or_restructure_policy_required"
            assert renewal[10] is False

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
