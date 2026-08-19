from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

LEGACY_MARKER = "REM-20990101-99999999"
VALID_CAPACITIES = {
    "legacy",
    "assigned_collector",
    "management",
    "employee",
}


def _user(connection: psycopg.Connection, label: str):
    return connection.execute(
        """
        INSERT INTO core.users(username, full_name, status)
        VALUES(%s, %s, 'active')
        RETURNING id
        """,
        (f"remit-cap-{label}-{uuid4().hex[:10]}", f"Remit Capacity {label}"),
    ).fetchone()[0]


def _insert_remittance(
    connection: psycopg.Connection,
    *,
    collector_user_id,
    recipient_user_id,
    remittance_number: str,
    recipient_capacity: str | None,
):
    if recipient_capacity is None:
        return connection.execute(
            """
            INSERT INTO lending.collection_remittances(
                remittance_number,
                collector_user_id,
                recipient_user_id,
                collection_date,
                transaction_count,
                payment_count,
                unable_to_pay_count,
                covered_payment_count,
                client_count,
                total_amount
            )
            VALUES(%s, %s, %s, %s, 1, 1, 0, 0, 1, %s)
            RETURNING id, recipient_capacity
            """,
            (
                remittance_number,
                collector_user_id,
                recipient_user_id,
                date(2099, 1, 1),
                Decimal("50.00"),
            ),
        ).fetchone()

    return connection.execute(
        """
        INSERT INTO lending.collection_remittances(
            remittance_number,
            collector_user_id,
            recipient_user_id,
            recipient_capacity,
            collection_date,
            transaction_count,
            payment_count,
            unable_to_pay_count,
            covered_payment_count,
            client_count,
            total_amount
        )
        VALUES(%s, %s, %s, %s, %s, 1, 1, 0, 0, 1, %s)
        RETURNING id, recipient_capacity
        """,
        (
            remittance_number,
            collector_user_id,
            recipient_user_id,
            recipient_capacity,
            date(2099, 1, 1),
            Decimal("50.00"),
        ),
    ).fetchone()


def test_legacy_row_is_backfilled_without_inferred_role_intent() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        row = connection.execute(
            """
            SELECT recipient_capacity, total_amount
            FROM lending.collection_remittances
            WHERE remittance_number = %s
            """,
            (LEGACY_MARKER,),
        ).fetchone()
        assert row == ("legacy", Decimal("50.00"))

        metadata = connection.execute(
            """
            SELECT is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema='lending'
              AND table_name='collection_remittances'
              AND column_name='recipient_capacity'
            """
        ).fetchone()
        assert metadata is not None
        assert metadata[0] == "NO"
        assert metadata[1] is not None and "legacy" in metadata[1]

        trigger_state = connection.execute(
            """
            SELECT tgenabled
            FROM pg_trigger
            WHERE tgrelid='lending.collection_remittances'::regclass
              AND tgname='lending_collection_remittance_recipient_capacity_guard'
              AND NOT tgisinternal
            """
        ).fetchone()
        assert trigger_state == ("O",)


def test_valid_capacities_and_legacy_default_are_accepted() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            collector = _user(connection, "collector")
            recipient = _user(connection, "recipient")

            default_row = _insert_remittance(
                connection,
                collector_user_id=collector,
                recipient_user_id=recipient,
                remittance_number=f"REM-CAP-DEFAULT-{uuid4().hex}",
                recipient_capacity=None,
            )
            assert default_row[1] == "legacy"

            for capacity in sorted(VALID_CAPACITIES - {"legacy"}):
                row = _insert_remittance(
                    connection,
                    collector_user_id=collector,
                    recipient_user_id=recipient,
                    remittance_number=f"REM-CAP-{capacity}-{uuid4().hex}",
                    recipient_capacity=capacity,
                )
                assert row[1] == capacity
        finally:
            connection.rollback()


def test_invalid_capacity_is_rejected() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        collector = _user(connection, "invalid-collector")
        recipient = _user(connection, "invalid-recipient")
        with pytest.raises(psycopg.errors.CheckViolation):
            _insert_remittance(
                connection,
                collector_user_id=collector,
                recipient_user_id=recipient,
                remittance_number=f"REM-CAP-INVALID-{uuid4().hex}",
                recipient_capacity="superuser",
            )


def test_recipient_capacity_is_immutable_after_insert() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        collector = _user(connection, "immutable-collector")
        recipient = _user(connection, "immutable-recipient")
        row = _insert_remittance(
            connection,
            collector_user_id=collector,
            recipient_user_id=recipient,
            remittance_number=f"REM-CAP-IMMUTABLE-{uuid4().hex}",
            recipient_capacity="management",
        )
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
            connection.execute(
                """
                UPDATE lending.collection_remittances
                SET recipient_capacity='assigned_collector'
                WHERE id=%s
                """,
                (row[0],),
            )
