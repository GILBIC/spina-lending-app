from __future__ import annotations

import sys
from pathlib import Path

import psycopg

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
    / "0102_add_remittance_review_and_rejection.sql"
)
REVIEW_TABLE = "lending.collection_remittance_reviews"
REJECTION_TABLE = "lending.collection_remittance_rejections"
ITEM_TABLE = "lending.collection_remittance_items"
ITEM_UNIQUE_CONSTRAINT = "collection_remittance_items_transaction_id_key"
ITEM_INDEX = "lending_collection_remittance_items_transaction_idx"
LOCK_TRIGGER = "lending_collection_transaction_lock_guard"
REQUIRED_REVIEW_COLUMNS = {
    "remittance_id",
    "reviewed_by_user_id",
    "reviewed_at",
}
REQUIRED_REJECTION_COLUMNS = {
    "remittance_id",
    "rejected_by_user_id",
    "rejected_at",
    "reason",
}


def _transaction_body(sql_text: str) -> str:
    body = sql_text.strip()
    if not body.startswith("BEGIN;") or not body.endswith("COMMIT;"):
        raise SystemExit(
            "0102 safety gate failed: expected immutable BEGIN/COMMIT migration wrapper"
        )
    return body[len("BEGIN;") : -len("COMMIT;")].strip()


def _relation_exists(connection: psycopg.Connection, name: str) -> bool:
    return connection.execute("select to_regclass(%s)", (name,)).fetchone()[0] is not None


def _columns(connection: psycopg.Connection, schema: str, table: str) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            """
            select column_name
            from information_schema.columns
            where table_schema=%s and table_name=%s
            """,
            (schema, table),
        ).fetchall()
    }


def _constraint_exists(connection: psycopg.Connection, constraint_name: str) -> bool:
    return (
        connection.execute(
            """
            select count(*)::integer
            from pg_constraint
            where conrelid = 'lending.collection_remittance_items'::regclass
              and conname = %s
            """,
            (constraint_name,),
        ).fetchone()[0]
        == 1
    )


def _index_definition(connection: psycopg.Connection, index_name: str) -> str | None:
    row = connection.execute(
        """
        select pg_get_indexdef(indexrelid)
        from pg_index
        where indexrelid = to_regclass(%s)
        """,
        (f"lending.{index_name}",),
    ).fetchone()
    return None if row is None else str(row[0])


def _function_definition(connection: psycopg.Connection) -> str:
    row = connection.execute(
        """
        select pg_get_functiondef(
            'lending.prevent_locked_collection_mutation()'::regprocedure
        )
        """
    ).fetchone()
    return "" if row is None else str(row[0])


def _trigger_state(connection: psycopg.Connection) -> str | None:
    row = connection.execute(
        """
        select tgenabled
        from pg_trigger
        where tgrelid='lending.collection_transactions'::regclass
          and tgname=%s
          and not tgisinternal
        """,
        (LOCK_TRIGGER,),
    ).fetchone()
    return None if row is None else str(row[0])


def _rejection_reason_guard_exists(connection: psycopg.Connection) -> bool:
    rows = connection.execute(
        """
        select pg_get_constraintdef(oid)
        from pg_constraint
        where conrelid='lending.collection_remittance_rejections'::regclass
          and contype='c'
        """
    ).fetchall()
    return any(
        "btrim(reason)" in str(row[0]).lower() and "<> ''" in str(row[0]).lower()
        for row in rows
    )


def _verify_installed(connection: psycopg.Connection) -> None:
    if not _relation_exists(connection, REVIEW_TABLE):
        raise SystemExit("0102 verification failed: remittance review table is missing")
    if not _relation_exists(connection, REJECTION_TABLE):
        raise SystemExit("0102 verification failed: remittance rejection table is missing")

    review_columns = _columns(connection, "lending", "collection_remittance_reviews")
    rejection_columns = _columns(
        connection,
        "lending",
        "collection_remittance_rejections",
    )
    if not REQUIRED_REVIEW_COLUMNS.issubset(review_columns):
        raise SystemExit("0102 verification failed: remittance review columns are incomplete")
    if not REQUIRED_REJECTION_COLUMNS.issubset(rejection_columns):
        raise SystemExit("0102 verification failed: remittance rejection columns are incomplete")
    if not _rejection_reason_guard_exists(connection):
        raise SystemExit("0102 verification failed: rejection reason guard is missing")

    if _constraint_exists(connection, ITEM_UNIQUE_CONSTRAINT):
        raise SystemExit(
            "0102 verification failed: transaction_id is still globally unique across remittance items"
        )
    index_definition = _index_definition(connection, ITEM_INDEX)
    if index_definition is None:
        raise SystemExit("0102 verification failed: remittance item transaction index is missing")
    lowered_index = index_definition.lower()
    if "transaction_id" not in lowered_index or "remittance_id" not in lowered_index:
        raise SystemExit("0102 verification failed: remittance item transaction index is incomplete")

    function_definition = _function_definition(connection).lower()
    for marker in (
        "collection_remittance_rejections",
        "new.remittance_id is null",
        "new.is_locked = false",
        "new_financial = old_financial",
    ):
        if marker not in function_definition:
            raise SystemExit(
                f"0102 verification failed: protected unlock guard is missing marker {marker!r}"
            )
    if _trigger_state(connection) != "O":
        raise SystemExit("0102 verification failed: collection lock guard trigger is not enabled")


def _evidence_signature(connection: psycopg.Connection) -> tuple[tuple[object, ...], ...]:
    remittances = connection.execute(
        """
        select count(*)::bigint,
               coalesce(sum(total_amount), 0),
               count(*) filter (where status='received')::bigint,
               count(*) filter (where status='submitted')::bigint
        from lending.collection_remittances
        """
    ).fetchone()
    items = connection.execute(
        """
        select count(*)::bigint,
               coalesce(sum(amount), 0),
               count(distinct transaction_id)::bigint
        from lending.collection_remittance_items
        """
    ).fetchone()
    transactions = connection.execute(
        """
        select count(*)::bigint,
               coalesce(sum(amount), 0),
               coalesce(sum(official_balance), 0),
               count(*) filter (where is_locked)::bigint,
               count(*) filter (where remittance_id is not null)::bigint
        from lending.collection_transactions
        """
    ).fetchone()
    return tuple(tuple(row) for row in (remittances, items, transactions))


def _fully_installed(connection: psycopg.Connection) -> bool:
    if not (
        _relation_exists(connection, REVIEW_TABLE)
        and _relation_exists(connection, REJECTION_TABLE)
    ):
        return False
    if _constraint_exists(connection, ITEM_UNIQUE_CONSTRAINT):
        return False
    if _index_definition(connection, ITEM_INDEX) is None:
        return False
    function_definition = _function_definition(connection).lower()
    return (
        "collection_remittance_rejections" in function_definition
        and "new_financial = old_financial" in function_definition
    )


def main() -> int:
    if not MIGRATION.is_file():
        raise SystemExit(f"0102 migration file was not found: {MIGRATION}")
    migration_body = _transaction_body(MIGRATION.read_text(encoding="utf-8"))
    database_url = get_settings().database_url

    try:
        with psycopg.connect(database_url) as connection:
            for required in (
                "lending.collection_remittances",
                "lending.collection_remittance_items",
                "lending.collection_transactions",
            ):
                if not _relation_exists(connection, required):
                    raise SystemExit(
                        f"0102 safety gate failed: prerequisite {required} is missing"
                    )

            if _fully_installed(connection):
                _verify_installed(connection)
                print("0102 is already installed and verified; no changes were made.")
                return 0

            review_exists = _relation_exists(connection, REVIEW_TABLE)
            rejection_exists = _relation_exists(connection, REJECTION_TABLE)
            item_index_exists = _index_definition(connection, ITEM_INDEX) is not None
            item_unique_exists = _constraint_exists(connection, ITEM_UNIQUE_CONSTRAINT)
            guarded_function = (
                "collection_remittance_rejections" in _function_definition(connection).lower()
            )
            if (
                review_exists
                or rejection_exists
                or item_index_exists
                or not item_unique_exists
                or guarded_function
            ):
                raise SystemExit(
                    "0102 safety gate failed: partial remittance review/rejection objects already exist"
                )

            connection.execute(
                "LOCK TABLE lending.collection_remittances IN ACCESS EXCLUSIVE MODE"
            )
            connection.execute(
                "LOCK TABLE lending.collection_remittance_items IN ACCESS EXCLUSIVE MODE"
            )
            connection.execute(
                "LOCK TABLE lending.collection_transactions IN ACCESS EXCLUSIVE MODE"
            )
            before = _evidence_signature(connection)
            connection.execute(migration_body)
            after = _evidence_signature(connection)
            if after != before:
                raise SystemExit(
                    "0102 safety gate failed: existing remittance or collection financial evidence changed"
                )
            _verify_installed(connection)
    except psycopg.Error as error:
        raise SystemExit(f"0102 migration failed and was rolled back: {error}") from error

    print(
        "0102 live migration complete. Permanent remittance review/rejection evidence and "
        "the narrow rejected-handover unlock are installed without changing existing "
        "remittance or collection financial evidence."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
