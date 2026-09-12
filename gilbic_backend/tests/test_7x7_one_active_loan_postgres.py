from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
SQL_0116 = (
    SQL_ROOT / "0116_enforce_one_active_7x7_per_client.sql"
).read_text(encoding="utf-8")


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _client(connection, suffix: str):
    return connection.execute(
        """
        insert into lending.clients (client_code, full_name, status)
        values (%s, %s, 'active') returning id
        """,
        (f"X7ONE-C-{suffix}", f"7x7 One Active Client {suffix}"),
    ).fetchone()[0]


def _loan_type(connection, suffix: str, *, mode: str):
    return connection.execute(
        """
        insert into lending.loan_types (
            code, name, term_days, calculation_mode,
            daily_interest_per_1000, settings
        ) values (%s, %s, 60, %s, 0, '{}'::jsonb)
        returning id
        """,
        (f"X7ONE-T-{mode}-{suffix}", f"{mode} {suffix}", mode),
    ).fetchone()[0]


def _loan(
    connection,
    *,
    suffix: str,
    client_id,
    loan_type_id,
    status: str,
):
    return connection.execute(
        """
        insert into lending.loans (
            loan_number, client_id, loan_type_id, principal, daily_amount,
            date_released, due_date, status
        ) values (
            %s, %s, %s, 3000.00, 50.00,
            date '2092-01-01', date '2092-04-15', %s
        ) returning id
        """,
        (f"X7ONE-L-{suffix}", client_id, loan_type_id, status),
    ).fetchone()[0]


def test_one_active_7x7_allows_regular_and_replacement_after_close() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0116))
            client_id = _client(connection, suffix)
            seven_type = _loan_type(connection, suffix, mode="seven_by_seven")
            regular_type = _loan_type(connection, suffix, mode="fixed_daily")

            first_seven = _loan(
                connection,
                suffix=f"{suffix}-7a",
                client_id=client_id,
                loan_type_id=seven_type,
                status="active",
            )
            regular = _loan(
                connection,
                suffix=f"{suffix}-reg",
                client_id=client_id,
                loan_type_id=regular_type,
                status="active",
            )
            assert regular is not None

            with pytest.raises(psycopg.errors.UniqueViolation):
                with connection.transaction():
                    _loan(
                        connection,
                        suffix=f"{suffix}-7b-conflict",
                        client_id=client_id,
                        loan_type_id=seven_type,
                        status="active",
                    )

            second_seven = _loan(
                connection,
                suffix=f"{suffix}-7b",
                client_id=client_id,
                loan_type_id=seven_type,
                status="draft",
            )
            with pytest.raises(psycopg.errors.UniqueViolation):
                with connection.transaction():
                    connection.execute(
                        "update lending.loans set status = 'active' where id = %s",
                        (second_seven,),
                    )

            connection.execute(
                "update lending.loans set status = 'closed' where id = %s",
                (first_seven,),
            )
            connection.execute(
                "update lending.loans set status = 'active' where id = %s",
                (second_seven,),
            )

            active_count = connection.execute(
                """
                select count(*)
                from lending.loans loan
                join lending.loan_types loan_type on loan_type.id = loan.loan_type_id
                where loan.client_id = %s
                  and loan.status = 'active'
                  and loan_type.calculation_mode = 'seven_by_seven'
                """,
                (client_id,),
            ).fetchone()[0]
            assert active_count == 1
        finally:
            connection.rollback()


def test_migration_refuses_preexisting_duplicate_active_7x7_state() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            client_id = _client(connection, suffix)
            seven_type = _loan_type(connection, suffix, mode="seven_by_seven")
            _loan(
                connection,
                suffix=f"{suffix}-dup-a",
                client_id=client_id,
                loan_type_id=seven_type,
                status="active",
            )
            _loan(
                connection,
                suffix=f"{suffix}-dup-b",
                client_id=client_id,
                loan_type_id=seven_type,
                status="active",
            )

            with pytest.raises(psycopg.errors.RaiseException):
                with connection.transaction():
                    connection.execute(_transaction_body(SQL_0116))
        finally:
            connection.rollback()


def test_concurrent_active_7x7_creation_cannot_both_succeed() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as setup:
        setup.execute(_transaction_body(SQL_0116))
        client_id = _client(setup, suffix)
        seven_type = _loan_type(setup, suffix, mode="seven_by_seven")
        setup.commit()

    barrier = Barrier(2)

    def attempt(label: str) -> str:
        assert DATABASE_URL is not None
        with psycopg.connect(DATABASE_URL) as connection:
            barrier.wait(timeout=10)
            try:
                _loan(
                    connection,
                    suffix=f"{suffix}-{label}",
                    client_id=client_id,
                    loan_type_id=seven_type,
                    status="active",
                )
                connection.commit()
                return "success"
            except psycopg.errors.UniqueViolation:
                connection.rollback()
                return "conflict"

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, ("concurrent-a", "concurrent-b")))
        assert sorted(results) == ["conflict", "success"]
    finally:
        with psycopg.connect(DATABASE_URL) as cleanup:
            cleanup.execute("delete from lending.loans where client_id = %s", (client_id,))
            cleanup.execute("delete from lending.clients where id = %s", (client_id,))
            cleanup.execute("delete from lending.loan_types where id = %s", (seven_type,))
            cleanup.commit()
