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


MIGRATIONS = (
    ROOT / "gilbic_backend" / "sql" / "0100_add_atomic_combined_collections.sql",
    ROOT / "gilbic_backend" / "sql" / "0101_add_collector_renewal_workflow.sql",
)
COMBINED_TABLE = "mobile.gilbic_combined_collection_idempotency"
RENEWAL_TABLE = "lending.client_renewal_requests"
REQUIRED_RENEWAL_COLUMNS = {
    "collector_recommendation",
    "collector_reason_code",
    "collector_comment",
    "recommended_by_user_id",
    "recommended_at",
    "approved_principal",
    "management_override_reason",
    "client_decision",
    "client_decided_at",
    "signer_readiness_status",
    "office_processing_required",
    "renewal_offset_amount",
    "net_release_amount",
    "amount_locked_at",
    "cash_released_by_user_id",
    "cash_released_to_collector_at",
    "collector_cash_received_at",
    "cash_given_to_client_at",
    "client_cash_confirmed_at",
    "handover_proof_status",
    "activation_status",
    "new_loan_id",
}
REQUIRED_PERMISSIONS = {
    "renewal.recommend.assigned",
    "renewal.cash_custody.assigned",
}


def _transaction_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    if not text.startswith("BEGIN;") or not text.endswith("COMMIT;"):
        raise SystemExit(
            f"0100/0101 safety gate failed: {path.name} must keep an immutable BEGIN/COMMIT wrapper"
        )
    return text[len("BEGIN;") : -len("COMMIT;")].strip()


def _columns(connection: psycopg.Connection, schema: str, table: str) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            """
            select column_name
            from information_schema.columns
            where table_schema=%s and table_name=%s
            order by ordinal_position
            """,
            (schema, table),
        ).fetchall()
    ]


def _snapshot(
    connection: psycopg.Connection,
    *,
    table: str,
    columns: list[str],
    order_by: str,
) -> list[tuple[object, ...]]:
    schema_name, table_name = table.split(".", 1)
    query = sql.SQL("select {} from {}.{} order by {}").format(
        sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        sql.Identifier(schema_name),
        sql.Identifier(table_name),
        sql.Identifier(order_by),
    )
    return list(connection.execute(query).fetchall())


def _relation_exists(connection: psycopg.Connection, name: str) -> bool:
    return connection.execute("select to_regclass(%s)", (name,)).fetchone()[0] is not None


def _verify(connection: psycopg.Connection) -> None:
    if not _relation_exists(connection, COMBINED_TABLE):
        raise SystemExit("0100 verification failed: combined idempotency table is missing")
    combined_columns = set(_columns(connection, "mobile", "gilbic_combined_collection_idempotency"))
    if not {
        "idempotency_key",
        "collector_account_id",
        "registered_device_id",
        "canonical_request_hash",
        "request_payload",
        "result_payload",
        "accepted_at",
    }.issubset(combined_columns):
        raise SystemExit("0100 verification failed: combined idempotency columns are incomplete")

    renewal_columns = set(_columns(connection, "lending", "client_renewal_requests"))
    missing = sorted(REQUIRED_RENEWAL_COLUMNS - renewal_columns)
    if missing:
        raise SystemExit(
            "0101 verification failed: renewal workflow columns are missing: "
            + ", ".join(missing)
        )
    for relation in (
        "lending.renewal_required_signers",
        "lending.renewal_handover_photos",
    ):
        if not _relation_exists(connection, relation):
            raise SystemExit(f"0101 verification failed: {relation} is missing")

    permission_rows = {
        str(row[0])
        for row in connection.execute(
            "select code from core.permissions where code = any(%s)",
            (list(sorted(REQUIRED_PERMISSIONS)),),
        ).fetchall()
    }
    if permission_rows != REQUIRED_PERMISSIONS:
        raise SystemExit("0101 verification failed: Collector renewal permissions are incomplete")
    collector_permissions = {
        str(row[0])
        for row in connection.execute(
            """
            select role_permission.permission_code
            from core.role_permissions role_permission
            join core.roles role on role.id = role_permission.role_id
            where role.code='collector'
              and role_permission.permission_code = any(%s)
            """,
            (list(sorted(REQUIRED_PERMISSIONS)),),
        ).fetchall()
    }
    if collector_permissions != REQUIRED_PERMISSIONS:
        raise SystemExit("0101 verification failed: Collector role lacks renewal workflow permissions")


def main() -> int:
    for migration in MIGRATIONS:
        if not migration.is_file():
            raise SystemExit(f"0100/0101 migration file was not found: {migration}")
    bodies = [_transaction_body(path) for path in MIGRATIONS]
    database_url = get_settings().database_url

    try:
        with psycopg.connect(database_url) as connection:
            for required in (
                "mobile.gilbic_collection_idempotency",
                "lending.client_renewal_requests",
                "lending.loan_renewal_execution_events",
            ):
                if not _relation_exists(connection, required):
                    raise SystemExit(
                        f"0100/0101 safety gate failed: prerequisite {required} is missing"
                    )

            original_columns = _columns(
                connection,
                "lending",
                "client_renewal_requests",
            )
            already_combined = _relation_exists(connection, COMBINED_TABLE)
            installed_renewal_columns = set(original_columns) & REQUIRED_RENEWAL_COLUMNS
            signer_exists = _relation_exists(connection, "lending.renewal_required_signers")
            photo_exists = _relation_exists(connection, "lending.renewal_handover_photos")

            fully_installed = (
                already_combined
                and installed_renewal_columns == REQUIRED_RENEWAL_COLUMNS
                and signer_exists
                and photo_exists
            )
            if fully_installed:
                _verify(connection)
                print("0100/0101 are already installed and verified; no changes were made.")
                return 0
            if (
                already_combined
                or installed_renewal_columns
                or signer_exists
                or photo_exists
            ):
                raise SystemExit(
                    "0100/0101 safety gate failed: partial atomic-collection/renewal objects already exist"
                )

            before_requests = _snapshot(
                connection,
                table=RENEWAL_TABLE,
                columns=original_columns,
                order_by="id",
            )
            before_collection_count = connection.execute(
                "select count(*)::bigint from lending.collection_transactions"
            ).fetchone()[0]
            before_renewal_execution_count = connection.execute(
                "select count(*)::bigint from lending.loan_renewal_execution_events"
            ).fetchone()[0]

            connection.execute(
                "LOCK TABLE lending.client_renewal_requests IN ACCESS EXCLUSIVE MODE"
            )
            for body in bodies:
                connection.execute(body)

            after_requests = _snapshot(
                connection,
                table=RENEWAL_TABLE,
                columns=original_columns,
                order_by="id",
            )
            if after_requests != before_requests:
                raise SystemExit(
                    "0100/0101 safety gate failed: pre-existing renewal request evidence changed"
                )
            if connection.execute(
                "select count(*)::bigint from lending.collection_transactions"
            ).fetchone()[0] != before_collection_count:
                raise SystemExit(
                    "0100/0101 safety gate failed: collection history changed during schema migration"
                )
            if connection.execute(
                "select count(*)::bigint from lending.loan_renewal_execution_events"
            ).fetchone()[0] != before_renewal_execution_count:
                raise SystemExit(
                    "0100/0101 safety gate failed: renewal execution evidence changed during schema migration"
                )
            _verify(connection)
    except psycopg.Error as error:
        raise SystemExit(
            f"0100/0101 migration failed and was rolled back: {error}"
        ) from error

    print(
        "0100/0101 live migration complete. Atomic combined-payment idempotency and the "
        "assigned-Collector renewal workflow are installed; existing collection, renewal "
        "request, and renewal execution evidence is unchanged."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
