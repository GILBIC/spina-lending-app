from __future__ import annotations

import sys
from pathlib import Path

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "gilbic_backend" / "src"
for import_root in (ROOT, BACKEND_SRC):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from gilbic_backend.config import get_settings


MIGRATION = (
    ROOT
    / "gilbic_backend"
    / "sql"
    / "0099_add_remittance_recipient_capacity.sql"
)
TABLE = "lending.collection_remittances"
CAPACITY_COLUMN = "recipient_capacity"
CAPACITY_CONSTRAINT = "collection_remittance_recipient_capacity_check"
CAPACITY_TRIGGER = "lending_collection_remittance_recipient_capacity_guard"
VALID_CAPACITIES = {"legacy", "assigned_collector", "management", "employee"}


def _transaction_body(sql_text: str) -> str:
    body = sql_text.strip()
    if not body.startswith("BEGIN;") or not body.endswith("COMMIT;"):
        raise SystemExit(
            "0099 safety gate failed: expected immutable BEGIN/COMMIT migration wrapper"
        )
    return body[len("BEGIN;") : -len("COMMIT;")].strip()


def _columns(connection: psycopg.Connection) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'lending'
              AND table_name = 'collection_remittances'
            ORDER BY ordinal_position
            """
        ).fetchall()
    ]


def _column_metadata(connection: psycopg.Connection) -> tuple[str, str | None] | None:
    row = connection.execute(
        """
        SELECT is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'lending'
          AND table_name = 'collection_remittances'
          AND column_name = %s
        """,
        (CAPACITY_COLUMN,),
    ).fetchone()
    if row is None:
        return None
    return str(row[0]), None if row[1] is None else str(row[1])


def _constraint_exists(connection: psycopg.Connection) -> bool:
    return (
        connection.execute(
            """
            SELECT count(*)::integer
            FROM pg_constraint
            WHERE conrelid = 'lending.collection_remittances'::regclass
              AND conname = %s
            """,
            (CAPACITY_CONSTRAINT,),
        ).fetchone()[0]
        == 1
    )


def _trigger_state(connection: psycopg.Connection) -> str | None:
    row = connection.execute(
        """
        SELECT t.tgenabled
        FROM pg_trigger t
        WHERE t.tgrelid = 'lending.collection_remittances'::regclass
          AND t.tgname = %s
          AND NOT t.tgisinternal
        """,
        (CAPACITY_TRIGGER,),
    ).fetchone()
    return None if row is None else str(row[0])


def _snapshot(
    connection: psycopg.Connection,
    columns: list[str],
) -> list[tuple[object, ...]]:
    query = sql.SQL("SELECT {} FROM lending.collection_remittances ORDER BY id").format(
        sql.SQL(", ").join(sql.Identifier(column) for column in columns)
    )
    return list(connection.execute(query).fetchall())


def _verify_installed(connection: psycopg.Connection) -> None:
    metadata = _column_metadata(connection)
    if metadata is None:
        raise SystemExit("0099 verification failed: recipient_capacity column is missing")
    is_nullable, column_default = metadata
    if is_nullable != "NO":
        raise SystemExit("0099 verification failed: recipient_capacity must be NOT NULL")
    if column_default is None or "legacy" not in column_default:
        raise SystemExit("0099 verification failed: legacy compatibility default is missing")
    if not _constraint_exists(connection):
        raise SystemExit("0099 verification failed: recipient capacity constraint is missing")
    if _trigger_state(connection) != "O":
        raise SystemExit("0099 verification failed: recipient capacity guard is not enabled")

    invalid_rows = connection.execute(
        """
        SELECT count(*)::bigint
        FROM lending.collection_remittances
        WHERE recipient_capacity IS NULL
           OR recipient_capacity <> ALL(%s)
        """,
        (list(sorted(VALID_CAPACITIES)),),
    ).fetchone()[0]
    if int(invalid_rows) != 0:
        raise SystemExit(
            f"0099 verification failed: {invalid_rows} remittances have invalid recipient capacity"
        )


def main() -> int:
    if not MIGRATION.is_file():
        raise SystemExit(f"0099 migration file was not found: {MIGRATION}")

    migration_body = _transaction_body(MIGRATION.read_text(encoding="utf-8"))
    database_url = get_settings().database_url

    try:
        with psycopg.connect(database_url) as connection:
            if connection.execute(
                "SELECT to_regclass('lending.collection_remittances')"
            ).fetchone()[0] is None:
                raise SystemExit(
                    "0099 safety gate failed: collection remittance schema is missing"
                )

            existing_columns = _columns(connection)
            column_present = CAPACITY_COLUMN in existing_columns
            constraint_present = _constraint_exists(connection)
            trigger_present = _trigger_state(connection) is not None

            if column_present:
                _verify_installed(connection)
                print("0099 is already installed and verified; no changes were made.")
                return 0

            if constraint_present or trigger_present:
                raise SystemExit(
                    "0099 safety gate failed: partial recipient-capacity objects already exist"
                )

            legacy_columns = list(existing_columns)
            before_rows = _snapshot(connection, legacy_columns)
            before_totals = connection.execute(
                """
                SELECT count(*)::bigint, coalesce(sum(total_amount), 0)
                FROM lending.collection_remittances
                """
            ).fetchone()
            before_ids = [row[legacy_columns.index("id")] for row in before_rows]

            # Prevent new remittances from appearing between the evidence snapshot and
            # the historical legacy backfill. The DDL and all checks remain atomic.
            connection.execute(
                "LOCK TABLE lending.collection_remittances IN ACCESS EXCLUSIVE MODE"
            )
            connection.execute(migration_body)

            after_rows = _snapshot(connection, legacy_columns)
            after_totals = connection.execute(
                """
                SELECT count(*)::bigint, coalesce(sum(total_amount), 0)
                FROM lending.collection_remittances
                """
            ).fetchone()
            if after_rows != before_rows:
                raise SystemExit(
                    "0099 safety gate failed: pre-existing remittance evidence changed"
                )
            if after_totals != before_totals:
                raise SystemExit(
                    "0099 safety gate failed: remittance row count or cash total changed"
                )

            if before_ids:
                nonlegacy = connection.execute(
                    """
                    SELECT count(*)::bigint
                    FROM lending.collection_remittances
                    WHERE id = ANY(%s)
                      AND recipient_capacity <> 'legacy'
                    """,
                    (before_ids,),
                ).fetchone()[0]
                if int(nonlegacy) != 0:
                    raise SystemExit(
                        "0099 safety gate failed: historical recipient intent was inferred instead of preserved as legacy"
                    )

            _verify_installed(connection)
            # psycopg commits only after every verification above succeeds.

    except psycopg.Error as error:
        raise SystemExit(f"0099 migration failed and was rolled back: {error}") from error

    print(
        "0099 live migration complete. Recipient capacity is installed and immutable; "
        "historical remittance evidence is unchanged and marked legacy."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
