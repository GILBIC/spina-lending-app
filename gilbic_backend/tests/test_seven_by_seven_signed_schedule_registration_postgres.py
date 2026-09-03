from __future__ import annotations

import os
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest

from gilbic_backend.contract_schedule_registration_service import (
    register_verified_contract_schedule,
)
from gilbic_backend.seven_by_seven_signed_schedule import (
    generate_signed_seven_by_seven_schedule,
)


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)


def test_signed_7x7_registration_persists_daily_payment_and_components() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    release_date = date(2098, 1, 1)
    first_due_date = release_date + timedelta(days=1)

    with psycopg.connect(DATABASE_URL) as connection:
        if connection.execute(
            "select to_regclass('lending.loan_contract_installments')"
        ).fetchone()[0] is None:
            pytest.skip("Contract schedule schema is not installed in the test database")

        try:
            actor_id = connection.execute(
                """
                insert into core.users (username, full_name, status)
                values (%s, %s, 'active')
                returning id
                """,
                (f"x7-signed-{suffix}", f"7x7 Signed {suffix}"),
            ).fetchone()[0]
            loan_type_id = connection.execute(
                """
                insert into lending.loan_types (
                    code,
                    name,
                    term_days,
                    calculation_mode,
                    daily_interest_per_1000
                )
                values (%s, %s, 120, 'seven_by_seven', 7.00)
                returning id
                """,
                (f"X7S-{suffix}", f"7x7 Signed {suffix}"),
            ).fetchone()[0]
            client_id = connection.execute(
                """
                insert into lending.clients (client_code, full_name, status)
                values (%s, %s, 'active')
                returning id
                """,
                (f"X7SC-{suffix}", f"7x7 Signed Client {suffix}"),
            ).fetchone()[0]
            loan_id = connection.execute(
                """
                insert into lending.loans (
                    loan_number,
                    client_id,
                    loan_type_id,
                    principal,
                    daily_amount,
                    date_released,
                    due_date,
                    status,
                    created_by_user_id
                )
                values (%s, %s, %s, 3000.00, 21.00, %s, %s, 'active', %s)
                returning id
                """,
                (
                    f"X7SL-{suffix}",
                    client_id,
                    loan_type_id,
                    release_date,
                    release_date + timedelta(days=120),
                    actor_id,
                ),
            ).fetchone()[0]

            rows = generate_signed_seven_by_seven_schedule(
                original_principal=Decimal("3000.00"),
                agreed_daily_payment=Decimal("50.00"),
                daily_interest_per_1000=Decimal("7.00"),
                first_due_date=first_due_date,
            )
            with connection.cursor() as cursor:
                schedule_id = register_verified_contract_schedule(
                    cursor,
                    loan_id=loan_id,
                    payment_frequency="daily",
                    contract_reference=f"SIGNED-X7-{suffix}",
                    contract_signed_date=release_date,
                    effective_from=release_date,
                    grace_days=0,
                    installments=rows,
                    evidence_basis="signed_contract",
                    evidence_reference=f"SIGNED-DOC-{suffix}",
                    verification_note="Borrower accepted the agreed 50 peso daily payment.",
                    verified_by_user_id=actor_id,
                    confirmed=True,
                )

            stored = connection.execute(
                """
                select
                    installment_number,
                    due_date,
                    contractual_amount,
                    principal_component,
                    interest_component
                from lending.loan_contract_installments
                where schedule_id = %s
                order by installment_number
                """,
                (schedule_id,),
            ).fetchall()

            assert len(stored) == 104
            assert stored[0] == (
                1,
                first_due_date,
                Decimal("50.00"),
                Decimal("29.00"),
                Decimal("21.00"),
            )
            assert stored[-1] == (
                104,
                first_due_date + timedelta(days=103),
                Decimal("34.00"),
                Decimal("13.00"),
                Decimal("21.00"),
            )
            assert sum(row[3] for row in stored) == Decimal("3000.00")
            assert connection.execute(
                """
                select count(*)
                from lending.loan_contract_schedule_registrations
                where schedule_id = %s
                  and evidence_basis = 'signed_contract'
                  and evidence_reference = %s
                """,
                (schedule_id, f"SIGNED-DOC-{suffix}"),
            ).fetchone()[0] == 1
        finally:
            connection.rollback()
