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
    / "0039_add_protected_cutover_eir_snapshots.sql"
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
            "Cutover EIR snapshot migration safety gate failed: expected BEGIN/COMMIT wrapper"
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


def _journal_snapshot(connection: psycopg.Connection) -> tuple[object, ...]:
    row = connection.execute(
        """
        SELECT
            count(*)::bigint,
            count(*) FILTER (WHERE status = 'draft')::bigint,
            count(*) FILTER (WHERE status = 'posted')::bigint,
            count(*) FILTER (
                WHERE source_type = 'opening_balance' AND status = 'draft'
            )::bigint,
            count(*) FILTER (
                WHERE source_type = 'opening_balance' AND status = 'posted'
            )::bigint,
            count(*) FILTER (WHERE entry_number IS NOT NULL)::bigint
        FROM accounting.journal_entries
        """
    ).fetchone()
    return tuple(row) + (
        _count(connection, "accounting.journal_lines"),
        _count(connection, "accounting.journal_events"),
    )


def _workbook_snapshot(connection: psycopg.Connection) -> tuple[object, ...]:
    row = connection.execute(
        """
        SELECT
            count(*)::bigint,
            count(*) FILTER (WHERE status = 'draft')::bigint,
            count(*) FILTER (WHERE status = 'review_ready')::bigint,
            coalesce(sum((profit_loss_policy_confirmed)::int), 0)::bigint
        FROM accounting.opening_balance_workbooks
        """
    ).fetchone()
    return tuple(row) + (
        _count(connection, "accounting.opening_balance_workbook_lines"),
        _count(connection, "accounting.opening_balance_journal_preparations"),
        _count(connection, "accounting.opening_balance_journal_postings"),
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
    require_zero_snapshots: bool,
) -> None:
    for relation in (
        "accounting.opening_balance_loan_snapshot_batches",
        "accounting.opening_balance_loan_measurement_snapshots",
        "accounting.opening_balance_loan_snapshot_reconciliation",
    ):
        if connection.execute("SELECT to_regclass(%s)", (relation,)).fetchone()[0] is None:
            raise SystemExit(
                f"Cutover EIR snapshot verification failed: relation is missing: {relation}"
            )

    function_count = int(
        connection.execute(
            """
            SELECT count(*)
            FROM pg_proc proc
            JOIN pg_namespace ns ON ns.oid = proc.pronamespace
            WHERE ns.nspname = 'accounting'
              AND proc.proname = 'capture_opening_balance_loan_eir_snapshots'
            """
        ).fetchone()[0]
    )
    if function_count != 1:
        raise SystemExit(
            "Cutover EIR snapshot verification failed: protected capture function is missing"
        )

    trigger_names = {
        str(row[0])
        for row in connection.execute(
            """
            SELECT tgname
            FROM pg_trigger
            WHERE NOT tgisinternal
              AND tgname IN (
                  'opening_balance_loan_snapshot_batch_guard',
                  'opening_balance_loan_measurement_snapshot_guard',
                  'accounting_opening_balance_loan_snapshot_capture'
              )
            """
        ).fetchall()
    }
    expected_triggers = {
        "opening_balance_loan_snapshot_batch_guard",
        "opening_balance_loan_measurement_snapshot_guard",
        "accounting_opening_balance_loan_snapshot_capture",
    }
    if trigger_names != expected_triggers:
        raise SystemExit(
            "Cutover EIR snapshot verification failed: immutable/capture triggers are missing"
        )

    batch_count = _count(connection, "accounting.opening_balance_loan_snapshot_batches")
    snapshot_count = _count(
        connection,
        "accounting.opening_balance_loan_measurement_snapshots",
    )
    if require_zero_snapshots and (batch_count != 0 or snapshot_count != 0):
        raise SystemExit(
            "Cutover EIR snapshot verification failed: schema install must create zero snapshot batches and rows"
        )

    dpd = _dpd_safety(connection)
    if dpd is not None and (
        bool(dpd[1]) or bool(dpd[2]) or dpd[3] is not None or bool(dpd[4])
    ):
        raise SystemExit(
            "Cutover EIR snapshot verification failed: default, ECL, or automatic posting was unexpectedly enabled"
        )

    preparation_count = _count(
        connection,
        "accounting.opening_balance_journal_preparations",
    )
    posting_count = _count(
        connection,
        "accounting.opening_balance_journal_postings",
    )
    opening_posted = int(
        connection.execute(
            """
            SELECT count(*)::bigint
            FROM accounting.journal_entries
            WHERE source_type = 'opening_balance' AND status = 'posted'
            """
        ).fetchone()[0]
    )
    print(
        "Cutover EIR snapshot summary: "
        f"snapshot_batches={batch_count}, snapshot_rows={snapshot_count}, "
        f"opening_preparations={preparation_count}, posting_records={posting_count}, "
        f"posted_opening_balance_journals={opening_posted}, automatic_source_posting=False"
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
            "Install protected per-loan cutover EIR snapshot controls without "
            "preparing/posting a journal or backfilling any snapshot."
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
                "lending.loan_types",
                "lending.loan_collection_state",
                "lending.collection_transactions",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "accounting.journal_events",
                "accounting.opening_balance_workbooks",
                "accounting.opening_balance_workbook_lines",
                "accounting.opening_balance_journal_preparations",
                "accounting.opening_balance_journal_postings",
                "accounting.loan_cutover_readiness",
            )
            for relation in required:
                if connection.execute(
                    "SELECT to_regclass(%s)", (relation,)
                ).fetchone()[0] is None:
                    raise SystemExit(
                        f"Cutover EIR snapshot prerequisite is not installed: {relation}"
                    )

            measure_function_count = int(
                connection.execute(
                    """
                    SELECT count(*)
                    FROM pg_proc proc
                    JOIN pg_namespace ns ON ns.oid = proc.pronamespace
                    WHERE ns.nspname = 'accounting'
                      AND proc.proname = 'measure_loan_at_cutover'
                    """
                ).fetchone()[0]
            )
            if measure_function_count != 1:
                raise SystemExit(
                    "Cutover EIR snapshot prerequisite is missing: accounting.measure_loan_at_cutover"
                )

            already_installed = connection.execute(
                "SELECT to_regclass('accounting.opening_balance_loan_snapshot_batches')"
            ).fetchone()[0]
            if already_installed is not None:
                print(
                    "Protected cutover EIR snapshot controls are already installed; skipping migration application."
                )
                _verify_installed(connection, require_zero_snapshots=False)
                return 0

            before_loans = _count(connection, "lending.loans")
            before_loan_statuses = _loan_status_counts(connection)
            before_transactions = _count(connection, "lending.collection_transactions")
            before_journals = _journal_snapshot(connection)
            before_workbook = _workbook_snapshot(connection)
            before_reviewed = _historical_reviewed_count(connection)
            before_dpd = _dpd_safety(connection)

            connection.execute(migration_body)

            after_loans = _count(connection, "lending.loans")
            after_loan_statuses = _loan_status_counts(connection)
            after_transactions = _count(connection, "lending.collection_transactions")
            after_journals = _journal_snapshot(connection)
            after_workbook = _workbook_snapshot(connection)
            after_reviewed = _historical_reviewed_count(connection)
            after_dpd = _dpd_safety(connection)

            if after_loans != before_loans or after_loan_statuses != before_loan_statuses:
                raise SystemExit(
                    "Cutover EIR snapshot safety gate failed: live loans changed during schema install"
                )
            if after_transactions != before_transactions:
                raise SystemExit(
                    "Cutover EIR snapshot safety gate failed: collection transactions changed during schema install"
                )
            if after_journals != before_journals:
                raise SystemExit(
                    "Cutover EIR snapshot safety gate failed: journal entries, events, statuses, numbers, or lines changed during schema install"
                )
            if after_workbook != before_workbook:
                raise SystemExit(
                    "Cutover EIR snapshot safety gate failed: workbook, preparation, or posting state changed during schema install"
                )
            if after_reviewed != before_reviewed:
                raise SystemExit(
                    "Cutover EIR snapshot safety gate failed: historical ECL labels changed"
                )
            if after_dpd != before_dpd:
                raise SystemExit(
                    "Cutover EIR snapshot safety gate failed: DPD/default/ECL readiness state changed"
                )

            _verify_installed(connection, require_zero_snapshots=True)
    except psycopg.Error as error:
        raise SystemExit(
            f"Cutover EIR snapshot migration failed and was rolled back: {error}"
        ) from error

    print(
        "Protected cutover EIR snapshot migration complete. Immutable capture controls "
        "are installed with zero snapshots created by deployment and automatic source posting disabled."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
