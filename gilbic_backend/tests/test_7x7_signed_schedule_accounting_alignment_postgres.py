from __future__ import annotations

import os
from datetime import date, timedelta
from decimal import Decimal
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


def test_accounting_readiness_uses_exact_signed_7x7_schedule_not_default_term() -> None:
    """Accounting must mirror the verified signed schedule, not rebuild one.

    This fixture proves Contract -> Accounting authority only. It does not
    approve the PHP 7 / PHP 1,000 pricing for any regulatory category; pricing
    eligibility is a separate pre-contract compliance gate.
    """

    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    release_date = date(2091, 2, 1)
    first_due_date = release_date + timedelta(days=1)

    signed_rows = generate_signed_seven_by_seven_schedule(
        original_principal=Decimal("3000.00"),
        agreed_daily_payment=Decimal("50.00"),
        daily_interest_per_1000=Decimal("7.00"),
        first_due_date=first_due_date,
    )

    assert len(signed_rows) == 104
    assert signed_rows[-1].due_date == release_date + timedelta(days=104)
    assert sum(row.principal_component for row in signed_rows) == Decimal("3000.00")
    assert sum(row.interest_component for row in signed_rows) == Decimal("2184.00")
    assert sum(row.contractual_amount for row in signed_rows) == Decimal("5184.00")

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            actor_id = connection.execute(
                """
                insert into core.users (username, full_name, status)
                values (%s, %s, 'active') returning id
                """,
                (f"p6-x7-{suffix}", f"Priority 6 7x7 {suffix}"),
            ).fetchone()[0]

            client_id = connection.execute(
                """
                insert into lending.clients (client_code, full_name, status)
                values (%s, %s, 'active') returning id
                """,
                (f"P6-X7-C-{suffix}", f"Priority 6 Client {suffix}"),
            ).fetchone()[0]

            loan_type_id = connection.execute(
                """
                insert into lending.loan_types (
                    code, name, term_days, calculation_mode,
                    daily_interest_per_1000, settings
                ) values (
                    %s, %s, 60, 'seven_by_seven', 7.00,
                    jsonb_build_object(
                        'contractual_interest_payment_frequency', 'daily',
                        'contractual_principal_due', 'amortized_in_signed_installments',
                        'principal_prepayment_allowed', true,
                        'principal_prepayment_changes_daily_interest', false,
                        'mobile_collections_enabled', false
                    )
                ) returning id
                """,
                (f"P6-X7-{suffix}", f"Priority 6 7x7 {suffix}"),
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
                    f"P6-X7-L-{suffix}",
                    client_id,
                    loan_type_id,
                    release_date,
                    signed_rows[-1].due_date,
                    actor_id,
                ),
            ).fetchone()[0]

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
                    f"P6-X7-CONTRACT-{suffix}",
                    release_date,
                    release_date,
                    actor_id,
                ),
            ).fetchone()[0]

            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    insert into lending.loan_contract_installments (
                        schedule_id, installment_number, due_date,
                        contractual_amount, principal_component, interest_component
                    ) values (%s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            schedule_id,
                            row.installment_number,
                            row.due_date,
                            row.contractual_amount,
                            row.principal_component,
                            row.interest_component,
                        )
                        for row in signed_rows
                    ],
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
                    f"P6-X7-EVIDENCE-{suffix}",
                    "Verified exact borrower/Management-approved 7x7 schedule",
                    actor_id,
                ),
            )

            readiness = connection.execute(
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
                    contractual_cash_flow_validation_ready
                from accounting.seven_by_seven_contractual_cash_flow_readiness
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone()

            assert readiness == (
                Decimal("21.00"),
                Decimal("2184.00"),
                Decimal("5184.00"),
                104,
                first_due_date,
                signed_rows[-1].due_date,
                Decimal("5184.00"),
                0,
                "pfrs9_contract_cash_flow_ready",
                True,
            )
        finally:
            connection.rollback()
