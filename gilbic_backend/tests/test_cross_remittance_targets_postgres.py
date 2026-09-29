"""Exercise recipient discovery with actual PostgreSQL DISTINCT/order semantics."""

import os
from contextlib import contextmanager
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest
from gilbic_backend import cross_remittance_repository
from test_contract_schedule_registration_postgres import (
    _create_fixture,
    _create_payment,
)

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="Disposable database required")


def test_other_area_cash_lists_unique_eligible_management_and_assigned_targets(
    monkeypatch,
):
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            suffix = uuid4().hex[:12]
            collector, device, client, loan = _create_fixture(connection, suffix)

            def user(label, roles, status="active"):
                identifier = connection.execute(
                    "insert into core.users(username,full_name,status) values(%s,%s,%s) returning id",
                    (f"cross-target-{suffix}-{label}", label, status),
                ).fetchone()[0]
                connection.execute(
                    "insert into core.user_roles(user_id,role_id) select %s,id from core.roles where code=any(%s)",
                    (identifier, roles),
                )
                return identifier

            assigned = user("Assigned", ["collector"])
            alpha = user("alpha", ["management", "employee"])
            zulu = user("Zulu", ["management"])
            inactive = user("Inactive", ["management"], "inactive")
            non_manager = user("Employee", ["employee"])
            connection.execute(
                "insert into core.user_roles(user_id,role_id) select %s,id from core.roles where code='management'",
                (collector,),
            )
            transaction = _create_payment(
                connection,
                suffix=suffix,
                loan_id=loan,
                client_id=client,
                actor_id=collector,
                device_id=device,
            )
            connection.execute(
                "update lending.collection_transactions set collection_origin='cross_collector',assigned_collector_user_id=%s where id=%s",
                (assigned, transaction),
            )

            @contextmanager
            def local_connection():
                yield connection

            monkeypatch.setattr(
                cross_remittance_repository, "open_connection", local_connection
            )
            targets = cross_remittance_repository.PostgresCrossRemittanceRepository().list_targets(
                collector_user_id=collector,
                collection_date=connection.execute(
                    "select collection_date from lending.collection_transactions where id=%s",
                    (transaction,),
                ).fetchone()[0],
            )
            assigned_targets = [
                t for t in targets if t.recipient_capacity == "assigned_collector"
            ]
            assert [
                (t.recipient_user_id, t.total_amount) for t in assigned_targets
            ] == [(assigned, Decimal("90.00"))]
            management = [t for t in targets if t.recipient_capacity == "management"]
            ids = [t.recipient_user_id for t in management]
            assert ids.count(alpha) == ids.count(zulu) == 1
            assert ids.index(alpha) < ids.index(zulu)
            assert not {collector, inactive, non_manager}.intersection(ids)
            assert all(
                t.total_amount == Decimal("90.00") and t.transaction_count == 1
                for t in management
            )
        finally:
            connection.rollback()
