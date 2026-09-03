from __future__ import annotations

import sys
from pathlib import Path

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gilbic_backend.config import get_settings


MIGRATION = (
    ROOT
    / "gilbic_backend"
    / "sql"
    / "0096_separate_collection_receipt_cash_from_loan_application.sql"
)
LOCK_TRIGGER = "lending_collection_transaction_lock_guard"
NORMALIZE_TRIGGER = "normalize_collection_receipt_application_insert"
NEW_COLUMNS = {"applied_amount", "unallocated_amount", "allocation_state"}


def _transaction_body(sql_text: str) -> str:
    body = sql_text.strip()
    if not body.startswith("BEGIN;") or not body.endswith("COMMIT;"):
        raise SystemExit(
            "0096 safety gate failed: expected immutable BEGIN/COMMIT migration wrapper"
        )
    return body[len("BEGIN;") : -len("COMMIT;")].strip()


def _table_columns(connection: psycopg.Connection) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'lending'
              AND table_name = 'collection_transactions'
            ORDER BY ordinal_position
            """
        ).fetchall()
    ]


def _snapshot(
    connection: psycopg.Connection,
    columns: list[str],
    *,
    voided_only: bool = False,
) -> list[tuple[object, ...]]:
    query = sql.SQL("SELECT {} FROM lending.collection_transactions").format(
        sql.SQL(", ").join(sql.Identifier(column) for column in columns)
    )
    if voided_only:
        query += sql.SQL(" WHERE is_voided = true")
    query += sql.SQL(" ORDER BY id")
    return list(connection.execute(query).fetchall())


def _trigger_state(connection: psycopg.Connection, trigger_name: str) -> str | None:
    row = connection.execute(
        """
        SELECT t.tgenabled
        FROM pg_trigger t
        WHERE t.tgrelid = 'lending.collection_transactions'::regclass
          AND t.tgname = %s
          AND NOT t.tgisinternal
        """,
        (trigger_name,),
    ).fetchone()
    return None if row is None else str(row[0])


def _verify_installed(connection: psycopg.Connection, expected_rows: int | None = None) -> None:
    view_name = connection.execute(
        "SELECT to_regclass('lending.collection_receipt_application_state')"
    ).fetchone()[0]
    if view_name is None:
        raise SystemExit("0096 verification failed: receipt application view is missing")

    columns = set(_table_columns(connection))
    if not NEW_COLUMNS.issubset(columns):
        raise SystemExit(
            "0096 verification failed: receipt application columns are incomplete"
        )

    constraints = {
        str(row[0])
        for row in connection.execute(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conrelid = 'lending.collection_transactions'::regclass
              AND conname IN (
                  'lending_collection_applied_amount_check',
                  'lending_collection_unallocated_amount_check',
                  'lending_collection_receipt_application_sum_check',
                  'lending_collection_allocation_state_check'
              )
            """
        ).fetchall()
    }
    expected_constraints = {
        "lending_collection_applied_amount_check",
        "lending_collection_unallocated_amount_check",
        "lending_collection_receipt_application_sum_check",
        "lending_collection_allocation_state_check",
    }
    if constraints != expected_constraints:
        raise SystemExit(
            "0096 verification failed: receipt application constraints are incomplete"
        )

    if _trigger_state(connection, LOCK_TRIGGER) != "O":
        raise SystemExit(
            "0096 verification failed: collection immutability trigger is not enabled"
        )
    if _trigger_state(connection, NORMALIZE_TRIGGER) != "O":
        raise SystemExit(
            "0096 verification failed: legacy-writer normalization trigger is not enabled"
        )

    invalid = connection.execute(
        """
        SELECT count(*)::bigint
        FROM lending.collection_transactions
        WHERE
            (entry_type = 'pass' AND NOT (
                amount = 0
                AND applied_amount = 0
                AND unallocated_amount = 0
                AND allocation_state = 'not_applicable'
            ))
            OR
            (entry_type IN ('payment', 'advance') AND NOT (
                applied_amount = amount
                AND unallocated_amount = 0
                AND allocation_state = 'fully_allocated'
            ))
            OR entry_type NOT IN ('payment', 'advance', 'pass')
        """
    ).fetchone()[0]
    if int(invalid) != 0:
        raise SystemExit(
            f"0096 verification failed: {invalid} historical receipt rows have invalid application state"
        )

    totals = connection.execute(
        """
        SELECT
            count(*)::bigint,
            coalesce(sum(amount), 0),
            coalesce(sum(applied_amount), 0),
            coalesce(sum(unallocated_amount), 0)
        FROM lending.collection_transactions
        """
    ).fetchone()
    if expected_rows is not None and int(totals[0]) != expected_rows:
        raise SystemExit(
            "0096 verification failed: collection transaction row count changed"
        )
    if totals[1] != totals[2] or totals[3] != 0:
        raise SystemExit(
            "0096 verification failed: historical cash/application totals do not reconcile"
        )

    view_rows = int(
        connection.execute(
            "SELECT count(*)::bigint FROM lending.collection_receipt_application_state"
        ).fetchone()[0]
    )
    if view_rows != int(totals[0]):
        raise SystemExit(
            "0096 verification failed: receipt application view does not cover every collection transaction"
        )


def main() -> int:
    if not MIGRATION.is_file():
        raise SystemExit(f"0096 migration file was not found: {MIGRATION}")

    migration_body = _transaction_body(MIGRATION.read_text(encoding="utf-8"))
    database_url = get_settings().database_url

    try:
        with psycopg.connect(database_url) as connection:
            if connection.execute(
                "SELECT to_regclass('lending.collection_transactions')"
            ).fetchone()[0] is None:
                raise SystemExit("0096 safety gate failed: collection transaction schema is missing")

            existing_view = connection.execute(
                "SELECT to_regclass('lending.collection_receipt_application_state')"
            ).fetchone()[0]
            existing_columns = _table_columns(connection)
            existing_new_columns = NEW_COLUMNS.intersection(existing_columns)

            if existing_view is not None:
                _verify_installed(connection)
                print("0096 is already installed and verified; no changes were made.")
                return 0

            if existing_new_columns:
                raise SystemExit(
                    "0096 safety gate failed: partial receipt-split columns already exist without the view"
                )

            if _trigger_state(connection, LOCK_TRIGGER) != "O":
                raise SystemExit(
                    "0096 safety gate failed: expected collection immutability trigger is missing or disabled"
                )

            invalid_legacy = connection.execute(
                """
                SELECT id, entry_type, amount
                FROM lending.collection_transactions
                WHERE entry_type NOT IN ('payment', 'advance', 'pass')
                   OR (entry_type = 'pass' AND amount <> 0)
                   OR (entry_type IN ('payment', 'advance') AND amount <= 0)
                ORDER BY id
                LIMIT 10
                """
            ).fetchall()
            if invalid_legacy:
                raise SystemExit(
                    f"0096 safety gate failed: legacy rows violate the new receipt model: {invalid_legacy}"
                )

            legacy_columns = list(existing_columns)
            before_all = _snapshot(connection, legacy_columns)
            before_voided = _snapshot(connection, legacy_columns, voided_only=True)
            before_totals = connection.execute(
                """
                SELECT count(*)::bigint, coalesce(sum(amount), 0)
                FROM lending.collection_transactions
                """
            ).fetchone()

            # Block concurrent receipt writes while the one-time schema/backfill runs.
            connection.execute(
                "LOCK TABLE lending.collection_transactions IN ACCESS EXCLUSIVE MODE"
            )

            # The historical immutability trigger correctly rejects every UPDATE to a
            # voided receipt. 0096 must initialize three newly-added metadata columns on
            # those immutable rows, so suspend only that user trigger inside this same
            # transaction. Any error rolls this DDL back together with the migration.
            connection.execute(
                "ALTER TABLE lending.collection_transactions "
                "DISABLE TRIGGER lending_collection_transaction_lock_guard"
            )
            connection.execute(migration_body)
            connection.execute(
                "ALTER TABLE lending.collection_transactions "
                "ENABLE TRIGGER lending_collection_transaction_lock_guard"
            )

            if _trigger_state(connection, LOCK_TRIGGER) != "O":
                raise SystemExit(
                    "0096 safety gate failed: immutability trigger was not restored before commit"
                )

            after_all = _snapshot(connection, legacy_columns)
            after_voided = _snapshot(connection, legacy_columns, voided_only=True)
            after_totals = connection.execute(
                """
                SELECT count(*)::bigint, coalesce(sum(amount), 0)
                FROM lending.collection_transactions
                """
            ).fetchone()

            if after_all != before_all:
                raise SystemExit(
                    "0096 safety gate failed: pre-existing collection transaction fields changed"
                )
            if after_voided != before_voided:
                raise SystemExit(
                    "0096 safety gate failed: voided receipt evidence changed"
                )
            if after_totals != before_totals:
                raise SystemExit(
                    "0096 safety gate failed: collection row count or cash total changed"
                )

            _verify_installed(connection, expected_rows=int(before_totals[0]))
            # psycopg's connection context commits only after all gates above succeed.

    except psycopg.Error as error:
        raise SystemExit(f"0096 migration failed and was rolled back: {error}") from error

    print(
        "0096 live migration complete. Receipt cash/application fields are installed; "
        "legacy collection evidence is unchanged and the immutability trigger is enabled."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
