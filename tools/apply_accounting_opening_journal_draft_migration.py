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
    / "0037_add_opening_balance_journal_draft.sql"
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
            "Opening-balance journal draft migration safety gate failed: expected BEGIN/COMMIT wrapper"
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


def _workbook_snapshot(connection: psycopg.Connection) -> tuple[object, ...]:
    return tuple(
        connection.execute(
            """
            SELECT
                count(*)::bigint,
                count(*) FILTER (WHERE status = 'draft')::bigint,
                count(*) FILTER (WHERE status = 'review_ready')::bigint,
                coalesce(sum((profit_loss_policy_confirmed)::int), 0)::bigint
            FROM accounting.opening_balance_workbooks
            """
        ).fetchone()
    ) + (
        _count(connection, "accounting.opening_balance_workbook_lines"),
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
    table = connection.execute(
        "SELECT to_regclass('accounting.opening_balance_journal_preparations')"
    ).fetchone()[0]
    view = connection.execute(
        "SELECT to_regclass('accounting.opening_balance_journal_preparation_status')"
    ).fetchone()[0]
    if table is None or view is None:
        raise SystemExit(
            "Opening-balance journal draft verification failed: preparation table/view is missing"
        )

    function_count = int(
        connection.execute(
            """
            SELECT count(*)
            FROM pg_proc proc
            JOIN pg_namespace ns ON ns.oid = proc.pronamespace
            WHERE ns.nspname = 'accounting'
              AND proc.proname = 'create_opening_balance_journal_draft'
            """
        ).fetchone()[0]
    )
    if function_count != 1:
        raise SystemExit(
            "Opening-balance journal draft verification failed: protected preparation function is missing"
        )

    permission_count = int(
        connection.execute(
            "SELECT count(*) FROM core.permissions WHERE code = 'accounting.opening_balance.prepare'"
        ).fetchone()[0]
    )
    management_permission_count = int(
        connection.execute(
            """
            SELECT count(*)
            FROM core.role_permissions rp
            JOIN core.roles role ON role.id = rp.role_id
            WHERE role.code = 'management'
              AND rp.permission_code = 'accounting.opening_balance.prepare'
            """
        ).fetchone()[0]
    )
    if permission_count != 1 or management_permission_count != 1:
        raise SystemExit(
            "Opening-balance journal draft verification failed: Management preparation permission is missing"
        )

    trigger_rows = connection.execute(
        """
        SELECT tgname
        FROM pg_trigger
        WHERE NOT tgisinternal
          AND tgname IN (
              'accounting_opening_balance_journal_preparation_guard',
              'accounting_opening_balance_prepared_workbook_reopen_guard',
              'accounting_opening_balance_journal_entry_guard',
              'accounting_opening_balance_journal_line_guard'
          )
        """
    ).fetchall()
    trigger_names = {str(row[0]) for row in trigger_rows}
    required_triggers = {
        "accounting_opening_balance_journal_preparation_guard",
        "accounting_opening_balance_prepared_workbook_reopen_guard",
        "accounting_opening_balance_journal_entry_guard",
        "accounting_opening_balance_journal_line_guard",
    }
    if trigger_names != required_triggers:
        raise SystemExit(
            "Opening-balance journal draft verification failed: one or more immutability/posting guards are missing"
        )

    preparation_count = _count(
        connection, "accounting.opening_balance_journal_preparations"
    )
    opening_journal_count = int(
        connection.execute(
            """
            SELECT count(*)::bigint
            FROM accounting.journal_entries
            WHERE source_type = 'opening_balance'
            """
        ).fetchone()[0]
    )
    if require_pristine_install and (preparation_count != 0 or opening_journal_count != 0):
        raise SystemExit(
            "Opening-balance journal draft verification failed: schema install must create zero preparations and zero opening-balance journals"
        )

    dpd = _dpd_safety(connection)
    if dpd is not None and (
        bool(dpd[1]) or bool(dpd[2]) or dpd[3] is not None or bool(dpd[4])
    ):
        raise SystemExit(
            "Opening-balance journal draft verification failed: default, ECL, or posting was unexpectedly enabled"
        )

    print(
        "Opening-balance journal draft summary: "
        f"preparations={preparation_count}, opening_balance_journals={opening_journal_count}, "
        "posting_enabled=False, automatic_source_posting=False"
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
            "Install protected opening-balance journal draft preparation controls "
            "without preparing or posting any live journal."
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
                "lending.collection_transactions",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "accounting.opening_balance_workbooks",
                "accounting.opening_balance_workbook_lines",
                "accounting.loan_cutover_readiness",
            )
            for relation in required:
                if connection.execute(
                    "SELECT to_regclass(%s)", (relation,)
                ).fetchone()[0] is None:
                    raise SystemExit(
                        f"Opening-balance journal draft prerequisite is not installed: {relation}"
                    )

            already_installed = connection.execute(
                "SELECT to_regclass('accounting.opening_balance_journal_preparations')"
            ).fetchone()[0]
            if already_installed is not None:
                print(
                    "Opening-balance journal draft controls are already installed; skipping migration application."
                )
                _verify_installed(connection, require_pristine_install=False)
                return 0

            before_loans = _count(connection, "lending.loans")
            before_loan_statuses = _loan_status_counts(connection)
            before_transactions = _count(connection, "lending.collection_transactions")
            before_journals = _count(connection, "accounting.journal_entries")
            before_journal_lines = _count(connection, "accounting.journal_lines")
            before_workbook = _workbook_snapshot(connection)
            before_reviewed = _historical_reviewed_count(connection)
            before_dpd = _dpd_safety(connection)

            connection.execute(migration_body)

            after_loans = _count(connection, "lending.loans")
            after_loan_statuses = _loan_status_counts(connection)
            after_transactions = _count(connection, "lending.collection_transactions")
            after_journals = _count(connection, "accounting.journal_entries")
            after_journal_lines = _count(connection, "accounting.journal_lines")
            after_workbook = _workbook_snapshot(connection)
            after_reviewed = _historical_reviewed_count(connection)
            after_dpd = _dpd_safety(connection)

            if after_loans != before_loans or after_loan_statuses != before_loan_statuses:
                raise SystemExit(
                    "Opening-balance journal draft safety gate failed: live loans changed during schema install"
                )
            if after_transactions != before_transactions:
                raise SystemExit(
                    "Opening-balance journal draft safety gate failed: collection transactions changed during schema install"
                )
            if after_journals != before_journals or after_journal_lines != before_journal_lines:
                raise SystemExit(
                    "Opening-balance journal draft safety gate failed: journal entries or lines changed during schema install"
                )
            if after_workbook != before_workbook:
                raise SystemExit(
                    "Opening-balance journal draft safety gate failed: existing workbook state changed during schema install"
                )
            if after_reviewed != before_reviewed:
                raise SystemExit(
                    "Opening-balance journal draft safety gate failed: historical ECL labels changed"
                )
            if after_dpd != before_dpd:
                raise SystemExit(
                    "Opening-balance journal draft safety gate failed: DPD/default/ECL readiness state changed"
                )

            _verify_installed(connection, require_pristine_install=True)
    except psycopg.Error as error:
        raise SystemExit(
            f"Opening-balance journal draft migration failed and was rolled back: {error}"
        ) from error

    print(
        "Opening-balance journal draft live migration complete. Protected preparation controls "
        "are installed with zero drafts created and no General Ledger posting enabled."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
