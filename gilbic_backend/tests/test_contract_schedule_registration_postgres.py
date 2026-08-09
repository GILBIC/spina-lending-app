from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from gilbic_backend.contract_schedule_engine import generate_contract_installments
from gilbic_backend.contract_schedule_registration_service import (
    register_verified_contract_schedule,
)
from gilbic_backend.contract_schedule_service import (
    ContractScheduleConflict,
    allocate_collection_transaction,
)


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

SQL_0034 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0034_add_contractual_schedule_dpd_foundation.sql"
).read_text(encoding="utf-8")
SQL_0035 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0035_add_verified_contract_schedule_registration.sql"
).read_text(encoding="utf-8")


def _transaction_body(sql: str) -> str:
    body = sql.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _create_fixture(connection, suffix: str):
    actor_id = connection.execute(
        """
        insert into core.users (username, full_name, status)
        values (%s, %s, 'active')
        returning id
        """,
        (f"verified-contract-{suffix}", f"Verified Contract {suffix}"),
    ).fetchone()[0]
    device_id = connection.execute(
        """
        insert into core.devices (
            user_id,
            device_identifier_hash,
            platform,
            status
        )
        values (%s, %s, 'desktop', 'active')
        returning id
        """,
        (actor_id, f"verified-contract-device-{suffix}"),
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
        values (%s, %s, 120, 'custom', 0)
        returning id
        """,
        (f"VC-{suffix}", f"Verified Contract {suffix}"),
    ).fetchone()[0]
    client_id = connection.execute(
        """
        insert into lending.clients (client_code, full_name, status)
        values (%s, %s, 'active')
        returning id
        """,
        (f"VC-C-{suffix}", f"Verified Contract Client {suffix}"),
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
            status
        )
        values (%s, %s, %s, 270.00, 90.00, current_date, current_date + 2, 'active')
        returning id
        """,
        (f"VC-L-{suffix}", client_id, loan_type_id),
    ).fetchone()[0]
    return actor_id, device_id, client_id, loan_id


def _create_payment(
    connection,
    *,
    suffix: str,
    loan_id,
    client_id,
    actor_id,
    device_id,
):
    return connection.execute(
        """
        insert into lending.collection_transactions (
            idempotency_key,
            loan_id,
            client_id,
            collector_user_id,
            registered_device_id,
            route_entry_id,
            collection_date,
            entry_type,
            amount,
            recorded_at,
            device_sequence,
            note,
            previous_balance,
            official_balance,
            pass_count_after,
            advance_until_after,
            receipt_number,
            details
        )
        values (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            current_date,
            'payment',
            90.00,
            now(),
            1,
            '',
            270.00,
            180.00,
            0,
            null,
            %s,
            '{}'::jsonb
        )
        returning id
        """,
        (
            uuid4(),
            loan_id,
            client_id,
            actor_id,
            device_id,
            loan_id,
            f"VC-R-{suffix}",
        ),
    ).fetchone()[0]


def test_stage5e43_requires_confirmation_records_evidence_and_blocks_unsafe_supersession() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:8]

    with psycopg.connect(DATABASE_URL) as connection:
        if connection.execute(
            "select to_regclass('lending.collection_transactions')"
        ).fetchone()[0] is None:
            pytest.skip("Collection schema is not installed in the test database")
        if connection.execute(
            """
            select 1
            from information_schema.columns
            where table_schema = 'lending'
              and table_name = 'collection_transactions'
              and column_name = 'is_voided'
            """
        ).fetchone() is None:
            pytest.skip("Collection void support is not installed in the test database")

        try:
            connection.execute(_transaction_body(SQL_0034))
            connection.execute(_transaction_body(SQL_0035))
            actor_id, device_id, client_id, loan_id = _create_fixture(connection, suffix)

            installments = generate_contract_installments(
                payment_frequency="daily",
                contractual_total=Decimal("270.00"),
                first_due_date=date.today(),
                installment_count=3,
                regular_installment_amount=Decimal("90.00"),
            )

            with connection.cursor() as cursor:
                with pytest.raises(ContractScheduleConflict):
                    register_verified_contract_schedule(
                        cursor,
                        loan_id=loan_id,
                        payment_frequency="daily",
                        contract_reference=f"VC-CONTRACT-{suffix}",
                        contract_signed_date=date.today(),
                        effective_from=date.today(),
                        grace_days=0,
                        installments=installments,
                        evidence_basis="signed_contract",
                        evidence_reference=f"DOC-{suffix}",
                        verification_note="Matched against the signed borrower contract.",
                        verified_by_user_id=actor_id,
                        confirmed=False,
                    )

                assert connection.execute(
                    "select count(*) from lending.loan_contract_schedules where loan_id = %s",
                    (loan_id,),
                ).fetchone()[0] == 0

                schedule_id = register_verified_contract_schedule(
                    cursor,
                    loan_id=loan_id,
                    payment_frequency="daily",
                    contract_reference=f"VC-CONTRACT-{suffix}",
                    contract_signed_date=date.today(),
                    effective_from=date.today(),
                    grace_days=0,
                    installments=installments,
                    evidence_basis="signed_contract",
                    evidence_reference=f"DOC-{suffix}",
                    verification_note="Matched against the signed borrower contract.",
                    verified_by_user_id=actor_id,
                    confirmed=True,
                )

            registration = connection.execute(
                """
                select
                    evidence_basis,
                    evidence_reference,
                    verification_note,
                    verified_by_user_id
                from lending.loan_contract_schedule_registrations
                where schedule_id = %s
                """,
                (schedule_id,),
            ).fetchone()
            assert registration == (
                "signed_contract",
                f"DOC-{suffix}",
                "Matched against the signed borrower contract.",
                actor_id,
            )

            stored_schedule = connection.execute(
                """
                select schedule_version, status, payment_frequency, contract_reference
                from lending.loan_contract_schedules
                where id = %s
                """,
                (schedule_id,),
            ).fetchone()
            assert stored_schedule == (
                1,
                "active",
                "daily",
                f"VC-CONTRACT-{suffix}",
            )

            with pytest.raises(psycopg.errors.RaiseException):
                with connection.transaction():
                    connection.execute(
                        """
                        update lending.loan_contract_schedule_registrations
                        set verification_note = 'rewritten'
                        where schedule_id = %s
                        """,
                        (schedule_id,),
                    )

            payment_id = _create_payment(
                connection,
                suffix=suffix,
                loan_id=loan_id,
                client_id=client_id,
                actor_id=actor_id,
                device_id=device_id,
            )
            with connection.cursor() as cursor:
                allocation = allocate_collection_transaction(
                    cursor,
                    transaction_id=payment_id,
                )
            assert len(allocation) == 1
            assert allocation[0].installment_number == 1
            assert allocation[0].amount_applied == Decimal("90.00")

            superseding_installments = generate_contract_installments(
                payment_frequency="weekly",
                contractual_total=Decimal("270.00"),
                first_due_date=date.today(),
                installment_count=3,
                regular_installment_amount=Decimal("90.00"),
            )
            with connection.cursor() as cursor:
                with pytest.raises(ContractScheduleConflict):
                    register_verified_contract_schedule(
                        cursor,
                        loan_id=loan_id,
                        payment_frequency="weekly",
                        contract_reference=f"VC-RESTRUCTURE-{suffix}",
                        contract_signed_date=date.today(),
                        effective_from=date.today(),
                        grace_days=0,
                        installments=superseding_installments,
                        evidence_basis="signed_restructure_contract",
                        evidence_reference=f"RESTRUCTURE-DOC-{suffix}",
                        verification_note="Synthetic restructure safety check.",
                        verified_by_user_id=actor_id,
                        confirmed=True,
                        supersede_active=True,
                    )

            schedule_state = connection.execute(
                """
                select count(*), count(*) filter (where status = 'active')
                from lending.loan_contract_schedules
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert schedule_state == (1, 1)

            assessment = connection.execute(
                """
                select
                    dpd_data_status,
                    days_past_due,
                    automatic_default_label_written,
                    ecl_included,
                    ecl_amount,
                    ready_to_post
                from accounting.loan_contract_dpd_assessment
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert assessment == ("ready", 0, False, False, None, False)
        finally:
            # The fixture, registration, payment, and allocations are synthetic.
            connection.rollback()
