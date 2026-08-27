from __future__ import annotations

import os
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

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


def _require_0106_schema() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        relation = connection.execute(
            "select to_regclass('lending.seven_by_seven_extra_principal_adjustments')"
        ).fetchone()[0]
    if relation is None:
        pytest.skip(
            "Migration 0106 is not installed on this database; disposable Financial validation owns this schema test."
        )


def _insert_receipt(
    connection: psycopg.Connection,
    *,
    loan_id: UUID,
    client_id: UUID,
    collector_id: UUID,
    device_id: UUID,
    collection_date: date,
    entry_type: str,
    amount: str,
    sequence: int,
    intent: str,
) -> UUID:
    transaction_id = uuid4()
    accepted_at = datetime.combine(
        collection_date,
        datetime.min.time(),
        tzinfo=timezone.utc,
    )
    connection.execute(
        """
        insert into lending.collection_transactions (
            id,
            idempotency_key,
            loan_id,
            client_id,
            collector_user_id,
            registered_device_id,
            route_entry_id,
            collection_date,
            entry_type,
            amount,
            applied_amount,
            unallocated_amount,
            allocation_state,
            recorded_at,
            accepted_at,
            device_sequence,
            note,
            route_revision,
            previous_balance,
            official_balance,
            pass_count_after,
            advance_until_after,
            receipt_number,
            details
        ) values (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, 0.00, 'fully_allocated', %s, %s, %s, '', %s,
            3000.00, 3000.00, 0, null, %s, %s
        )
        """,
        (
            transaction_id,
            uuid4(),
            loan_id,
            client_id,
            collector_id,
            device_id,
            loan_id,
            collection_date,
            entry_type,
            Decimal(amount),
            Decimal(amount),
            accepted_at,
            accepted_at,
            sequence,
            f"loan:{loan_id}:v0",
            f"X7-EP-{uuid4().hex[:12]}",
            Jsonb(
                {
                    "source": "0106-disposable-postgres-test",
                    "payment_allocation_intent": intent,
                }
            ),
        ),
    )
    return transaction_id


def _setup_case() -> tuple[UUID, UUID, UUID, UUID, int]:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    collection_date = date(2099, 1, 1)
    first_due_date = date(2099, 1, 2)

    with psycopg.connect(DATABASE_URL) as connection:
        collector_id = connection.execute(
            """
            insert into core.users (username, full_name, status)
            values (%s, %s, 'active') returning id
            """,
            (f"x7-ep-{suffix}", f"7x7 Extra Principal {suffix}"),
        ).fetchone()[0]
        device_id = connection.execute(
            """
            insert into core.devices (
                user_id, device_identifier_hash, platform, app_version, status
            ) values (%s, %s, 'android', '0106-test', 'active')
            returning id
            """,
            (collector_id, f"0106-device-{suffix}"),
        ).fetchone()[0]
        loan_type_id = connection.execute(
            """
            insert into lending.loan_types (
                code, name, description, term_days, calculation_mode,
                daily_interest_per_1000, settings, is_active
            ) values (%s, %s, '0106 disposable 7x7', 120,
                      'seven_by_seven', 7.00, '{}'::jsonb, true)
            returning id
            """,
            (f"X7EP-{suffix}", f"7x7 Extra Principal {suffix}"),
        ).fetchone()[0]
        client_id = connection.execute(
            """
            insert into lending.clients (client_code, full_name, area, status)
            values (%s, %s, 'Cardona', 'active') returning id
            """,
            (f"X7EPC-{suffix}", f"7x7 Extra Principal Client {suffix}"),
        ).fetchone()[0]
        loan_id = connection.execute(
            """
            insert into lending.loans (
                loan_number, client_id, loan_type_id, principal, daily_amount,
                date_released, due_date, status, created_by_user_id
            ) values (%s, %s, %s, 3000.00, 50.00, %s, %s, 'active', %s)
            returning id
            """,
            (
                f"X7EPL-{suffix}",
                client_id,
                loan_type_id,
                collection_date,
                date(2099, 5, 1),
                collector_id,
            ),
        ).fetchone()[0]

        schedule_rows = generate_signed_seven_by_seven_schedule(
            original_principal=Decimal("3000.00"),
            agreed_daily_payment=Decimal("50.00"),
            daily_interest_per_1000=Decimal("7.00"),
            first_due_date=first_due_date,
        )
        with connection.cursor() as cursor:
            registration = register_verified_contract_schedule(
                cursor,
                loan_id=loan_id,
                payment_frequency="daily",
                contract_reference=f"SIGNED-X7-EP-{suffix}",
                contract_signed_date=collection_date,
                effective_from=collection_date,
                grace_days=0,
                installments=schedule_rows,
                evidence_basis="signed_contract",
                evidence_reference=f"SIGNED-X7-EP-DOC-{suffix}",
                verification_note="Borrower accepted the signed 50 peso daily payment.",
                verified_by_user_id=collector_id,
                confirmed=True,
            )
        schedule_id = registration.schedule_id
        installment_id = connection.execute(
            """
            select id
            from lending.loan_contract_installments
            where schedule_id = %s
              and principal_component = 29.00
              and contractual_amount = 50.00
            order by installment_number desc
            limit 1
            """,
            (schedule_id,),
        ).fetchone()[0]
        connection.execute(
            """
            insert into lending.loan_schedule_operational_state (
                schedule_id, operational_version, updated_by_user_id
            ) values (%s, 0, %s)
            on conflict (schedule_id) do nothing
            """,
            (schedule_id, collector_id),
        )

        advance_transaction_id = _insert_receipt(
            connection,
            loan_id=loan_id,
            client_id=client_id,
            collector_id=collector_id,
            device_id=device_id,
            collection_date=collection_date,
            entry_type="advance",
            amount="35.00",
            sequence=1,
            intent="extra_as_advance",
        )
        connection.execute(
            """
            insert into lending.loan_installment_payment_allocations (
                installment_id,
                transaction_id,
                amount_applied,
                allocation_basis,
                allocation_reference,
                created_by_user_id
            ) values (%s, %s, 35.00, 'future_advance_oldest_first', %s, %s)
            """,
            (
                installment_id,
                advance_transaction_id,
                f"0106-advance:{advance_transaction_id}",
                collector_id,
            ),
        )

    return loan_id, client_id, collector_id, device_id, installment_id


def _record_adjustment(
    connection: psycopg.Connection,
    *,
    loan_id: UUID,
    client_id: UUID,
    collector_id: UUID,
    device_id: UUID,
    installment_id: int,
    sequence: int,
    expected_version: int,
    prior_future_principal: str,
    reduction: str,
    prior_principal: str,
    prior_amount: str,
    new_principal: str,
    new_amount: str,
    advance_before: str,
    advance_retained: str,
    refund_due: str,
) -> UUID:
    payment_transaction_id = _insert_receipt(
        connection,
        loan_id=loan_id,
        client_id=client_id,
        collector_id=collector_id,
        device_id=device_id,
        collection_date=date(2099, 1, 1),
        entry_type="payment",
        amount="100.00",
        sequence=sequence,
        intent="extra_as_principal_reduction",
    )
    schedule_id, installment_number, effective_due_date = connection.execute(
        """
        select schedule_id, installment_number, due_date
        from lending.loan_contract_installments
        where id = %s
        """,
        (installment_id,),
    ).fetchone()
    resulting_future_principal = Decimal(prior_future_principal) - Decimal(reduction)
    adjustment_id = connection.execute(
        """
        insert into lending.seven_by_seven_extra_principal_adjustments (
            loan_id,
            schedule_id,
            transaction_id,
            principal_reduction,
            prior_future_principal,
            resulting_future_principal,
            removed_future_interest,
            advance_refund_due,
            expected_operational_version,
            resulting_operational_version,
            actor_user_id
        ) values (%s, %s, %s, %s, %s, %s, 0.00, %s, %s, %s, %s)
        returning id
        """,
        (
            loan_id,
            schedule_id,
            payment_transaction_id,
            Decimal(reduction),
            Decimal(prior_future_principal),
            resulting_future_principal,
            Decimal(refund_due),
            expected_version,
            expected_version + 1,
            collector_id,
        ),
    ).fetchone()[0]
    connection.execute(
        """
        insert into lending.seven_by_seven_extra_principal_adjustment_items (
            adjustment_id,
            installment_id,
            installment_number,
            effective_due_date,
            signed_contractual_amount,
            signed_principal_component,
            signed_interest_component,
            prior_operational_amount,
            prior_operational_principal_component,
            prior_operational_interest_component,
            new_operational_amount,
            new_operational_principal_component,
            new_operational_interest_component,
            advance_allocated_before,
            advance_retained_after,
            advance_refund_due,
            removed_from_operational_schedule
        ) values (
            %s, %s, %s, %s, 50.00, 29.00, 21.00,
            %s, %s, 21.00, %s, %s, 21.00, %s, %s, %s, false
        )
        """,
        (
            adjustment_id,
            installment_id,
            installment_number,
            effective_due_date,
            Decimal(prior_amount),
            Decimal(prior_principal),
            Decimal(new_amount),
            Decimal(new_principal),
            Decimal(advance_before),
            Decimal(advance_retained),
            Decimal(refund_due),
        ),
    )
    connection.execute(
        """
        insert into lending.loan_installment_operational_amounts (
            installment_id,
            operational_amount,
            operational_principal_component,
            operational_interest_component,
            removed_from_operational_schedule,
            last_extra_principal_adjustment_id,
            updated_by_user_id
        ) values (%s, %s, %s, 21.00, false, %s, %s)
        on conflict (installment_id) do update
        set operational_amount = excluded.operational_amount,
            operational_principal_component = excluded.operational_principal_component,
            operational_interest_component = excluded.operational_interest_component,
            removed_from_operational_schedule = excluded.removed_from_operational_schedule,
            last_extra_principal_adjustment_id = excluded.last_extra_principal_adjustment_id,
            updated_by_user_id = excluded.updated_by_user_id,
            updated_at = now()
        """,
        (
            installment_id,
            Decimal(new_amount),
            Decimal(new_principal),
            adjustment_id,
            collector_id,
        ),
    )
    if Decimal(refund_due) > 0:
        connection.execute(
            """
            insert into lending.loan_unused_advance_refund_dues (
                adjustment_id, installment_id, amount_due
            ) values (%s, %s, %s)
            """,
            (adjustment_id, installment_id, Decimal(refund_due)),
        )
    connection.execute(
        """
        update lending.loan_schedule_operational_state
        set operational_version = %s,
            updated_by_user_id = %s,
            updated_at = now()
        where schedule_id = %s
          and operational_version = %s
        """,
        (expected_version + 1, collector_id, schedule_id, expected_version),
    )
    return adjustment_id


def test_repeated_extra_principal_preserves_signed_row_and_conserves_advance() -> None:
    assert DATABASE_URL is not None
    _require_0106_schema()
    loan_id, client_id, collector_id, device_id, installment_id = _setup_case()

    with psycopg.connect(DATABASE_URL) as connection:
        first_adjustment_id = _record_adjustment(
            connection,
            loan_id=loan_id,
            client_id=client_id,
            collector_id=collector_id,
            device_id=device_id,
            installment_id=installment_id,
            sequence=2,
            expected_version=0,
            prior_future_principal="3000.00",
            reduction="20.00",
            prior_principal="29.00",
            prior_amount="50.00",
            new_principal="9.00",
            new_amount="30.00",
            advance_before="35.00",
            advance_retained="30.00",
            refund_due="5.00",
        )

        signed_amount, operational_amount, active_advance, refund_total = connection.execute(
            """
            select
                installment.contractual_amount,
                operational.operational_amount,
                advance.active_advance_allocated,
                advance.refund_due_total
            from lending.loan_contract_installments installment
            join lending.loan_contract_installments_operational operational
              on operational.id = installment.id
            join lending.loan_installment_active_advance advance
              on advance.installment_id = installment.id
            where installment.id = %s
            """,
            (installment_id,),
        ).fetchone()
        assert signed_amount == Decimal("50.00")
        assert operational_amount == Decimal("30.00")
        assert active_advance == Decimal("30.00")
        assert refund_total == Decimal("5.00")

        second_adjustment_id = _record_adjustment(
            connection,
            loan_id=loan_id,
            client_id=client_id,
            collector_id=collector_id,
            device_id=device_id,
            installment_id=installment_id,
            sequence=3,
            expected_version=1,
            prior_future_principal="2980.00",
            reduction="5.00",
            prior_principal="9.00",
            prior_amount="30.00",
            new_principal="4.00",
            new_amount="25.00",
            advance_before="30.00",
            advance_retained="25.00",
            refund_due="5.00",
        )

        signed_amount, operational_amount, active_advance, refund_total, version = (
            connection.execute(
                """
                select
                    installment.contractual_amount,
                    operational.operational_amount,
                    advance.active_advance_allocated,
                    advance.refund_due_total,
                    state.operational_version
                from lending.loan_contract_installments installment
                join lending.loan_contract_installments_operational operational
                  on operational.id = installment.id
                join lending.loan_installment_active_advance advance
                  on advance.installment_id = installment.id
                join lending.loan_schedule_operational_state state
                  on state.schedule_id = installment.schedule_id
                where installment.id = %s
                """,
                (installment_id,),
            ).fetchone()
        )
        assert signed_amount == Decimal("50.00")
        assert operational_amount == Decimal("25.00")
        assert active_advance == Decimal("25.00")
        assert refund_total == Decimal("10.00")
        assert version == 2

        connection.commit()
        with pytest.raises(psycopg.Error):
            connection.execute(
                """
                update lending.loan_unused_advance_refund_dues
                set amount_due = 1.00
                where adjustment_id = %s
                  and installment_id = %s
                """,
                (first_adjustment_id, installment_id),
            )
        connection.rollback()

        count = connection.execute(
            """
            select count(*)
            from lending.seven_by_seven_extra_principal_adjustments
            where id in (%s, %s)
            """,
            (first_adjustment_id, second_adjustment_id),
        ).fetchone()[0]
        assert count == 2
