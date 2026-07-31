from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import psycopg
import pytest

from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
    CollectionStatus,
    PostedCollection,
)
from spina_mobile_collections.postgres import PostgresCollectionExecutor
from spina_mobile_collections.service import (
    CONTRACT_VERSION,
    CollectionSubmissionService,
    SubmissionHeaders,
)

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)
KEY = UUID("6cb93829-dccd-4d43-a25c-a1f31859cc1b")


class IntegrationBridge:
    def post_collection(
        self,
        connection: psycopg.Connection,
        actor: ActorContext,
        command: CollectionCommand,
    ) -> PostedCollection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO mobile.gilbic_test_postings (
                    idempotency_key,
                    collector_account_id,
                    amount
                ) VALUES (%s, %s, %s)
                RETURNING id
                """,
                (command.idempotency_key, actor.account_id, command.amount),
            )
            posting_id = cursor.fetchone()[0]
        return PostedCollection(
            server_transaction_id=f"collection-{posting_id}",
            receipt_number=f"TEST-{posting_id:08d}",
            official_balance=Decimal("4600.00"),
            accepted_at=datetime.now(timezone.utc),
            route_revision="route-v4",
        )


def connection_factory() -> psycopg.Connection:
    assert DATABASE_URL is not None
    return psycopg.connect(DATABASE_URL)


def actor() -> ActorContext:
    return ActorContext(
        account_id="collector-7",
        device_id="collector-phone-15",
        permissions=frozenset({"collection.create"}),
    )


def command() -> CollectionCommand:
    return CollectionCommand(
        idempotency_key=KEY,
        route_entry_id="route-entry-304",
        client_id="client-304",
        loan_id="loan-815",
        collection_date=date(2026, 7, 31),
        entry_type=CollectionEntryType.PAYMENT,
        amount=Decimal("200.00"),
        recorded_at=datetime(2026, 7, 31, 5, 15, tzinfo=timezone.utc),
        device_id="collector-phone-15",
        device_sequence=45,
        route_revision="route-v3",
    )


def headers() -> SubmissionHeaders:
    return SubmissionHeaders(
        idempotency_key=KEY,
        client_transaction_id=KEY,
        device_id="collector-phone-15",
        contract_version=CONTRACT_VERSION,
    )


def prepare_database() -> None:
    migration = (
        Path(__file__).parents[1]
        / "migrations"
        / "0001_gilbic_collection_idempotency.sql"
    ).read_text(encoding="utf-8")
    with connection_factory() as connection:
        connection.execute(migration)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS mobile.gilbic_test_postings (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                idempotency_key UUID NOT NULL,
                collector_account_id TEXT NOT NULL,
                amount NUMERIC(18, 2) NOT NULL
            )
            """
        )
        connection.execute(
            "TRUNCATE mobile.gilbic_collection_idempotency, "
            "mobile.gilbic_test_postings RESTART IDENTITY"
        )


def cleanup_database() -> None:
    with connection_factory() as connection:
        connection.execute("DROP TABLE IF EXISTS mobile.gilbic_test_postings")
        connection.execute("DROP TABLE IF EXISTS mobile.gilbic_collection_idempotency")


def test_postgresql_serializes_concurrent_duplicate_submissions() -> None:
    prepare_database()
    try:
        service = CollectionSubmissionService(
            PostgresCollectionExecutor(
                connection_factory=connection_factory,
                posting_bridge=IntegrationBridge(),
            )
        )

        def submit(_: int):
            return service.submit(
                actor=actor(),
                headers=headers(),
                command=command(),
            )

        with ThreadPoolExecutor(max_workers=12) as pool:
            outcomes = list(pool.map(submit, range(24)))

        assert sum(item.status is CollectionStatus.ACCEPTED for item in outcomes) == 1
        assert sum(item.status is CollectionStatus.DUPLICATE for item in outcomes) == 23
        assert {item.posted.receipt_number for item in outcomes if item.posted} == {
            "TEST-00000001"
        }

        with connection_factory() as connection:
            posting_count = connection.execute(
                "SELECT COUNT(*) FROM mobile.gilbic_test_postings"
            ).fetchone()[0]
            idempotency_count = connection.execute(
                "SELECT COUNT(*) FROM mobile.gilbic_collection_idempotency"
            ).fetchone()[0]
        assert posting_count == 1
        assert idempotency_count == 1
    finally:
        cleanup_database()
