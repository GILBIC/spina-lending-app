from __future__ import annotations

import argparse
import os
from collections import Counter
from pathlib import Path

import psycopg


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "gilbic_backend"
    / "sql"
    / "0040_add_protected_regular_journal_drafts.sql"
)


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _transaction_body(sql: str) -> str:
    body = sql.strip()
    if not body.startswith("BEGIN;") or not body.endswith("COMMIT;"):
        raise SystemExit(
            "Protected Regular journal draft migration safety gate failed: expected BEGIN/COMMIT wrapper"
        )
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _count(connection: psycopg.Connection, relation: str) -> int:
    return int(connection.execute(f"SELECT count(*) FROM {relation}").fetchone()[0])


def _loan_status_counts(connection: psycopg.Connection) -> Counter[str]:
    rows = connection.execute(
        "SELECT status, count(*)::bigint FROM lending.loans GROUP BY status"
    ).fetchall()
    return Counter({str(status): int(count) for status, count in rows})


def _accounting_anchor_counts(connection: psycopg.Connection) -> tuple[int, ...]:
    return (
        _count(connection, "accounting.opening_balance_journal_preparations"),
        _count(connection, "accounting.opening_balance_journal_postings"),
        _count(connection, "accounting.opening_balance_loan_snapshot_batches"),
        _count(connection, "accounting.opening_balance_loan_measurement_snapshots"),
    )


def _historical_reviewed_count(connection: psycopg.Connection) -> int | None:
    exists = connection.execute(
        "SELECT to_regclass('accounting.ecl_historical_loan_episodes')"
    ).fetchone()[0]
    if exists is None:
        return None
    return int(
        connection.execute(
            """
            SELECT count(*)::bigint
            FROM accounting.ecl_historical_loan_episodes
            WHERE explicit_default_label IS NOT NULL
            """
        ).fetchone()[0]
    )


def _dpd_safety(connection: psycopg.Connection) -> tuple[object, ...] | None:
    exists = connection.execute(
        "SELECT to_regclass('accounting.loan_contract_dpd_summary')"
    ).fetchone()[0]
    if exists is None:
        return None
    row = connection.execute(
        """
        SELECT
            loan_count,
            automatic_default_label_written,
            ecl_included,
            ecl_amount,
            ready_to_post
        FROM accounting.loan_contract_dpd_summary
        """
    ).fetchone()
    return tuple(row) if row is not None else None


def _verify_installed(
    connection: psycopg.Connection,
    *,
    require_pristine_install: bool,
) -> None:
    required_relations = (
        "accounting.regular_journal_draft_preparations",
        "accounting.regular_journal_draft_preparation_entries",
        "accounting.regular_journal_draft_preparation_status",
    )
    missing = [
        relation
        for relation in required_relations
        if connection.execute(
            "SELECT to_regclass(%s)", (relation,)
        ).fetchone()[0]
        is None
    ]
    if missing:
        raise SystemExit(
            "Protected Regular journal draft verification failed: missing "
            + ", ".join(missing)
        )

    function_count = int(
        connection.execute(
            """
            SELECT count(*)
            FROM pg_proc proc
            JOIN pg_namespace ns ON ns.oid = proc.pronamespace
            WHERE ns.nspname = 'accounting'
              AND proc.proname = 'create_regular_journal_draft_batch'
            """
        ).fetchone()[0]
    )
    if function_count != 1:
        raise SystemExit(
            "Protected Regular journal draft verification failed: preparation function is missing"
        )

    permission_count = int(
        connection.execute(
            """
            SELECT count(*)
            FROM core.permissions
            WHERE code = 'accounting.regular_journal.prepare'
            """
        ).fetchone()[0]
    )
    management_permission_count = int(
        connection.execute(
            """
            SELECT count(*)
            FROM core.role_permissions rp
            JOIN core.roles role ON role.id = rp.role_id
            WHERE role.code = 'management'
              AND rp.permission_code = 'accounting.regular_journal.prepare'
            """
        ).fetchone()[0]
    )
    if permission_count != 1 or management_permission_count != 1:
        raise SystemExit(
            "Protected Regular journal draft verification failed: Management preparation permission is missing"
        )

    trigger_rows = connection.execute(
        """
        SELECT tgname
        FROM pg_trigger
        WHERE NOT tgisinternal
          AND tgname IN (
              'accounting_regular_journal_draft_preparation_guard',
              'accounting_regular_journal_draft_preparation_entry_guard',
              'accounting_regular_system_journal_entry_guard',
              'accounting_regular_system_journal_line_guard'
          )
        """
    ).fetchall()
    trigger_names = {str(row[0]) for row in trigger_rows}
    required_triggers = {
        "accounting_regular_journal_draft_preparation_guard",
        "accounting_regular_journal_draft_preparation_entry_guard",
        "accounting_regular_system_journal_entry_guard",
        "accounting_regular_system_journal_line_guard",
    }
    if trigger_names != required_triggers:
        raise SystemExit(
            "Protected Regular journal draft verification failed: one or more immutability/posting guards are missing"
        )

    manual_post_definition = str(
        connection.execute(
            """
            SELECT pg_get_functiondef(proc.oid)
            FROM pg_proc proc
            JOIN pg_namespace ns ON ns.oid = proc.pronamespace
            WHERE ns.nspname = 'accounting'
              AND proc.proname = 'post_manual_journal_entry'
            """
        ).fetchone()[0]
    )
    if (
        "source_type <> 'manual'" not in manual_post_definition
        or "Only a manual draft journal entry can be posted" not in manual_post_definition
    ):
        raise SystemExit(
            "Protected Regular journal draft verification failed: manual General Journal posting is not source-type hardened"
        )

    preparation_count = _count(
        connection, "accounting.regular_journal_draft_preparations"
    )
    preparation_entry_count = _count(
        connection, "accounting.regular_journal_draft_preparation_entries"
    )
    protected_journal_count = int(
        connection.execute(
            """
            SELECT count(*)::bigint
            FROM accounting.journal_entries journal
            WHERE EXISTS (
                SELECT 1
                FROM accounting.regular_journal_draft_preparation_entries prepared
                WHERE prepared.journal_entry_id = journal.id
            )
            """
        ).fetchone()[0]
    )
    posted_protected_count = int(
        connection.execute(
            """
            SELECT count(*)::bigint
            FROM accounting.journal_entries journal
            WHERE journal.status = 'posted'
              AND EXISTS (
                SELECT 1
                FROM accounting.regular_journal_draft_preparation_entries prepared
                WHERE prepared.journal_entry_id = journal.id
              )
            """
        ).fetchone()[0]
    )

    if require_pristine_install and (
        preparation_count != 0
        or preparation_entry_count != 0
        or protected_journal_count != 0
    ):
        raise SystemExit(
            "Protected Regular journal draft verification failed: schema install must create zero preparations and zero Regular journals"
        )
    if posted_protected_count != 0:
        raise SystemExit(
            "Protected Regular journal draft verification failed: Stage 5D.16 must not post any Regular journal"
        )

    dpd = _dpd_safety(connection)
    if dpd is not None and (
        bool(dpd[1]) or bool(dpd[2]) or dpd[3] is not None or bool(dpd[4])
    ):
        raise SystemExit(
            "Protected Regular journal draft verification failed: default, ECL, or automatic posting was unexpectedly enabled"
        )

    print(
        "Protected Regular journal draft summary: "
        f"preparations={preparation_count}, preparation_entries={preparation_entry_count}, "
        f"regular_journals={protected_journal_count}, posted_regular_journals={posted_protected_count}, "
        "regular_posting_enabled=False, automatic_source_posting=False"
        + (
            f", loans={dpd[0]}, automatic_default={dpd[1]}, ecl_included={dpd[2]}, "
            f"ecl_amount={dpd[3]}, ready_to_post={dpd[4]}."
            if dpd is not None
            else "."
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install protected Regular source-event journal draft controls "
            "without preparing or posting any live Regular journal."
        )
    )
    parser.add_argument("--env-file", action="append", type=Path, default=[])
    parser.add_argument("--database-url-env", default="GILBIC_DATABASE_URL")
    args = parser.parse_args()

    for env_path in args.env_file:
        _load_env_file(env_path)

    database_url = os.getenv(args.database_url_env)
    if not database_url:
        raise SystemExit(f"{args.database_url_env} is not configured")
    if not MIGRATION.is_file():
        raise SystemExit(f"Migration file was not found: {MIGRATION}")

    migration_body = _transaction_body(MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            required = (
                "lending.loans",
                "lending.loan_collection_state",
                "lending.loan_types",
                "lending.collection_transactions",
                "accounting.accounts",
                "accounting.fiscal_periods",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "accounting.journal_events",
                "accounting.opening_balance_journal_preparations",
                "accounting.opening_balance_journal_postings",
                "accounting.opening_balance_loan_snapshot_batches",
                "accounting.opening_balance_loan_measurement_snapshots",
            )
            for relation in required:
                if connection.execute(
                    "SELECT to_regclass(%s)", (relation,)
                ).fetchone()[0] is None:
                    raise SystemExit(
                        "Protected Regular journal draft prerequisite is not installed: "
                        + relation
                    )

            already_installed = connection.execute(
                "SELECT to_regclass('accounting.regular_journal_draft_preparations')"
            ).fetchone()[0]
            if already_installed is not None:
                print(
                    "Protected Regular journal draft controls are already installed; skipping migration application."
                )
                _verify_installed(connection, require_pristine_install=False)
                return 0

            before_loans = _count(connection, "lending.loans")
            before_loan_statuses = _loan_status_counts(connection)
            before_transactions = _count(connection, "lending.collection_transactions")
            before_journals = _count(connection, "accounting.journal_entries")
            before_lines = _count(connection, "accounting.journal_lines")
            before_events = _count(connection, "accounting.journal_events")
            before_anchors = _accounting_anchor_counts(connection)
            before_reviewed = _historical_reviewed_count(connection)
            before_dpd = _dpd_safety(connection)

            connection.execute(migration_body)

            after_loans = _count(connection, "lending.loans")
            after_loan_statuses = _loan_status_counts(connection)
            after_transactions = _count(connection, "lending.collection_transactions")
            after_journals = _count(connection, "accounting.journal_entries")
            after_lines = _count(connection, "accounting.journal_lines")
            after_events = _count(connection, "accounting.journal_events")
            after_anchors = _accounting_anchor_counts(connection)
            after_reviewed = _historical_reviewed_count(connection)
            after_dpd = _dpd_safety(connection)

            if after_loans != before_loans or after_loan_statuses != before_loan_statuses:
                raise SystemExit(
                    "Protected Regular journal draft safety gate failed: live loans changed during schema install"
                )
            if after_transactions != before_transactions:
                raise SystemExit(
                    "Protected Regular journal draft safety gate failed: collection transactions changed during schema install"
                )
            if (
                after_journals != before_journals
                or after_lines != before_lines
                or after_events != before_events
            ):
                raise SystemExit(
                    "Protected Regular journal draft safety gate failed: journal rows changed during schema install"
                )
            if after_anchors != before_anchors:
                raise SystemExit(
                    "Protected Regular journal draft safety gate failed: opening-balance/cutover anchor state changed"
                )
            if after_reviewed != before_reviewed or after_dpd != before_dpd:
                raise SystemExit(
                    "Protected Regular journal draft safety gate failed: ECL/DPD/default readiness state changed"
                )

            _verify_installed(connection, require_pristine_install=True)
    except psycopg.Error as error:
        raise SystemExit(
            "Protected Regular journal draft migration failed and was rolled back: "
            + str(error)
        ) from error

    print(
        "Protected Regular journal draft live migration complete. Controls are "
        "installed with zero live drafts created and all posting paths disabled."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
