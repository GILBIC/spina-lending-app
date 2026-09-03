from __future__ import annotations

import os
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest

from gilbic_backend.remittance_repository import PostgresRemittanceRepository
from gilbic_backend.remittance_review_repository import (
    PostgresReviewedRemittanceRepository,
    RemittanceAlreadyReceived,
    RemittanceReviewRequired,
)


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)


def _user(connection: psycopg.Connection, *, label: str, role_code: str):
    user_id = connection.execute(
        """
        insert into core.users(username, full_name, status)
        values(%s, %s, 'active')
        returning id
        """,
        (f"0102-{label}-{uuid4().hex[:10]}", f"0102 {label}"),
    ).fetchone()[0]
    connection.execute(
        """
        insert into core.user_roles(user_id, role_id)
        select %s, id from core.roles where code=%s
        """,
        (user_id, role_code),
    )
    return user_id


def _seed_collection(*, suffix: str, collection_date: date):
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        collector_id = _user(connection, label=f"collector-{suffix}", role_code="collector")
        recipient_id = _user(connection, label=f"recipient-{suffix}", role_code="management")
        device_id = connection.execute(
            """
            insert into core.devices(user_id, device_identifier_hash, platform, status)
            values(%s, %s, 'android', 'active')
            returning id
            """,
            (collector_id, f"0102-device-{suffix}-{uuid4().hex[:8]}"),
        ).fetchone()[0]
        loan_type_id = connection.execute(
            """
            insert into lending.loan_types(
                code, name, term_days, calculation_mode, daily_interest_per_1000
            ) values(%s, %s, 120, 'fixed_daily', 0)
            returning id
            """,
            (f"R0102-{suffix}-{uuid4().hex[:6]}", f"0102 Regular {suffix}"),
        ).fetchone()[0]
        client_id = connection.execute(
            """
            insert into lending.clients(client_code, full_name, status, area)
            values(%s, %s, 'active', '0102 Area')
            returning id
            """,
            (f"C0102-{suffix}-{uuid4().hex[:8]}", f"0102 Client {suffix}"),
        ).fetchone()[0]
        release_date = collection_date - timedelta(days=10)
        loan_id = connection.execute(
            """
            insert into lending.loans(
                loan_number, client_id, loan_type_id, principal, daily_amount,
                date_released, due_date, status
            ) values(%s, %s, %s, 1000.00, 100.00, %s, %s, 'active')
            returning id
            """,
            (
                f"L0102-{suffix}-{uuid4().hex[:8]}",
                client_id,
                loan_type_id,
                release_date,
                release_date + timedelta(days=120),
            ),
        ).fetchone()[0]
        transaction_id = connection.execute(
            """
            insert into lending.collection_transactions(
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
            ) values(
                %s, %s, %s, %s, %s, %s, %s, 'payment', 100.00,
                now(), 1, '0102 disposable payment', 1000.00, 900.00,
                0, null, %s, '{"source":"0102-disposable"}'::jsonb
            )
            returning id
            """,
            (
                uuid4(),
                loan_id,
                client_id,
                collector_id,
                device_id,
                loan_id,
                collection_date,
                f"RCPT-0102-{suffix}-{uuid4().hex[:8]}",
            ),
        ).fetchone()[0]
    return collector_id, recipient_id, transaction_id


def _financial_snapshot(transaction_id):
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        return connection.execute(
            """
            select to_jsonb(t) - array[
                'remittance_id',
                'is_locked',
                'locked_at',
                'locked_by_user_id',
                'updated_at',
                'updated_by_user_id'
            ]::text[]
            from lending.collection_transactions t
            where id=%s
            """,
            (transaction_id,),
        ).fetchone()[0]


def _assert_financial_mutation_is_blocked(transaction_id) -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
            with connection.transaction():
                connection.execute(
                    """
                    update lending.collection_transactions
                    set amount = amount + 1
                    where id=%s
                    """,
                    (transaction_id,),
                )


def test_rejection_preserves_snapshot_unlocks_and_allows_corrected_resubmission() -> None:
    assert DATABASE_URL is not None
    collection_date = date(2099, 2, 10)
    suffix = uuid4().hex[:8]
    collector_id, recipient_id, transaction_id = _seed_collection(
        suffix=suffix,
        collection_date=collection_date,
    )

    submitter = PostgresRemittanceRepository()
    reviewer = PostgresReviewedRemittanceRepository()
    first = submitter.submit(
        collector_user_id=collector_id,
        recipient_user_id=recipient_id,
        collection_date=collection_date,
        note="First handover",
    )
    assert first.transaction_count == 1
    assert first.items[0].transaction_id == transaction_id

    financial_before = _financial_snapshot(transaction_id)
    _assert_financial_mutation_is_blocked(transaction_id)

    with pytest.raises(RemittanceReviewRequired):
        reviewer.reject(
            remittance_id=first.remittance_id,
            recipient_user_id=recipient_id,
            reason="Cash count mismatch",
            review_acknowledged=False,
        )

    with psycopg.connect(DATABASE_URL) as connection:
        assert connection.execute(
            "select count(*) from lending.collection_remittance_reviews where remittance_id=%s",
            (first.remittance_id,),
        ).fetchone()[0] == 0

    rejected = reviewer.reject(
        remittance_id=first.remittance_id,
        recipient_user_id=recipient_id,
        reason="  Cash count mismatch  ",
        review_acknowledged=True,
    )
    assert rejected.status == "rejected"
    assert rejected.rejection_reason == "Cash count mismatch"
    assert rejected.items[0].transaction_id == transaction_id

    with psycopg.connect(DATABASE_URL) as connection:
        review_row = connection.execute(
            """
            select reviewed_by_user_id, reviewed_at
            from lending.collection_remittance_reviews
            where remittance_id=%s
            """,
            (first.remittance_id,),
        ).fetchone()
        assert review_row is not None
        assert review_row[0] == recipient_id
        assert review_row[1] is not None

        rejection_row = connection.execute(
            """
            select rejected_by_user_id, reason
            from lending.collection_remittance_rejections
            where remittance_id=%s
            """,
            (first.remittance_id,),
        ).fetchone()
        assert rejection_row == (recipient_id, "Cash count mismatch")

        unlocked = connection.execute(
            """
            select remittance_id, is_locked, locked_at, locked_by_user_id
            from lending.collection_transactions
            where id=%s
            """,
            (transaction_id,),
        ).fetchone()
        assert unlocked == (None, False, None, None)

        first_item_snapshot = connection.execute(
            """
            select transaction_snapshot
            from lending.collection_remittance_items
            where remittance_id=%s and transaction_id=%s
            """,
            (first.remittance_id, transaction_id),
        ).fetchone()[0]
        assert first_item_snapshot["transaction_id"] == str(transaction_id)
        assert first_item_snapshot["amount"] == "100.00"

    assert _financial_snapshot(transaction_id) == financial_before

    second = submitter.submit(
        collector_user_id=collector_id,
        recipient_user_id=recipient_id,
        collection_date=collection_date,
        note="Corrected resubmission",
    )
    assert second.remittance_id != first.remittance_id
    assert second.items[0].transaction_id == transaction_id

    with psycopg.connect(DATABASE_URL) as connection:
        linked_rows = connection.execute(
            """
            select remittance_id, transaction_snapshot
            from lending.collection_remittance_items
            where transaction_id=%s
            order by created_at, remittance_id
            """,
            (transaction_id,),
        ).fetchall()
        assert len(linked_rows) == 2
        assert {row[0] for row in linked_rows} == {
            first.remittance_id,
            second.remittance_id,
        }
        assert linked_rows[0][1]["transaction_id"] == str(transaction_id)
        assert linked_rows[1][1]["transaction_id"] == str(transaction_id)

        permanent_rejection = connection.execute(
            """
            select reason
            from lending.collection_remittance_rejections
            where remittance_id=%s
            """,
            (first.remittance_id,),
        ).fetchone()
        assert permanent_rejection == ("Cash count mismatch",)

    history = reviewer.list_for_user(actor_user_id=recipient_id)
    by_id = {record.remittance_id: record for record in history}
    assert by_id[first.remittance_id].status == "rejected"
    assert by_id[first.remittance_id].rejection_reason == "Cash count mismatch"
    assert by_id[second.remittance_id].status == "submitted"
    _assert_financial_mutation_is_blocked(transaction_id)


def test_acceptance_records_review_and_keeps_collection_locked() -> None:
    assert DATABASE_URL is not None
    collection_date = date(2099, 2, 11)
    suffix = uuid4().hex[:8]
    collector_id, recipient_id, transaction_id = _seed_collection(
        suffix=suffix,
        collection_date=collection_date,
    )

    submitter = PostgresRemittanceRepository()
    reviewer = PostgresReviewedRemittanceRepository()
    remittance = submitter.submit(
        collector_user_id=collector_id,
        recipient_user_id=recipient_id,
        collection_date=collection_date,
        note="Acceptance proof",
    )

    with pytest.raises(RemittanceReviewRequired):
        reviewer.confirm_received(
            remittance_id=remittance.remittance_id,
            recipient_user_id=recipient_id,
            review_acknowledged=False,
        )

    accepted = reviewer.confirm_received(
        remittance_id=remittance.remittance_id,
        recipient_user_id=recipient_id,
        review_acknowledged=True,
    )
    assert accepted.status == "received"
    assert accepted.reviewed_by_user_id == recipient_id
    assert accepted.reviewed_at is not None

    with psycopg.connect(DATABASE_URL) as connection:
        review_row = connection.execute(
            """
            select reviewed_by_user_id
            from lending.collection_remittance_reviews
            where remittance_id=%s
            """,
            (remittance.remittance_id,),
        ).fetchone()
        assert review_row == (recipient_id,)
        assert connection.execute(
            "select count(*) from lending.collection_remittance_rejections where remittance_id=%s",
            (remittance.remittance_id,),
        ).fetchone()[0] == 0
        locked = connection.execute(
            """
            select remittance_id, is_locked
            from lending.collection_transactions
            where id=%s
            """,
            (transaction_id,),
        ).fetchone()
        assert locked == (remittance.remittance_id, True)

    with pytest.raises(RemittanceAlreadyReceived):
        reviewer.reject(
            remittance_id=remittance.remittance_id,
            recipient_user_id=recipient_id,
            reason="Too late",
            review_acknowledged=True,
        )
    _assert_financial_mutation_is_blocked(transaction_id)
