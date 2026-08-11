from __future__ import annotations

import argparse
import os
from collections import Counter
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
DRAFT_MIGRATION = SQL_ROOT / "0040_add_protected_regular_journal_drafts.sql"
MANUAL_GUARD_MIGRATION = SQL_ROOT / "0041_harden_regular_journal_manual_post_guard.sql"
POSTING_MIGRATION = SQL_ROOT / "0042_add_protected_regular_journal_posting.sql"


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
            "Protected Regular accounting migration safety gate failed: expected BEGIN/COMMIT wrapper"
        )
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _count(connection: psycopg.Connection, relation: str) -> int:
    return int(connection.execute(f"SELECT count(*) FROM {relation}").fetchone()[0])


def _exists(connection: psycopg.Connection, relation: str) -> bool:
    return connection.execute(
        "SELECT to_regclass(%s)", (relation,)
    ).fetchone()[0] is not None


def _loan_status_counts(connection: psycopg.Connection) -> Counter[str]:
    rows = connection.execute(
        "SELECT status, count(*)::bigint FROM lending.loans GROUP BY status"
    ).fetchall()
    return Counter({str(status): int(count) for status, count in rows})


def _accounting_anchor_counts(connection: psycopg.Connection) -> tuple[int, ...]:
    return (
        _count(connection, "accounting.opening_balance_workbooks"),
        _count(connection, "accounting.opening_balance_journal_preparations"),
        _count(connection, "accounting.opening_balance_journal_postings"),
        _count(connection, "accounting.opening_balance_loan_snapshot_batches"),
        _count(connection, "accounting.opening_balance_loan_measurement_snapshots"),
    )


def _historical_reviewed_count(connection: psycopg.Connection) -> int | None:
    if not _exists(connection, "accounting.ecl_historical_loan_episodes"):
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
    if not _exists(connection, "accounting.loan_contract_dpd_summary"):
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


def _manual_post_is_null_safe(connection: psycopg.Connection) -> bool:
    row = connection.execute(
        """
        SELECT pg_get_functiondef(proc.oid)
        FROM pg_proc proc
        JOIN pg_namespace ns ON ns.oid = proc.pronamespace
        WHERE ns.nspname = 'accounting'
          AND proc.proname = 'post_manual_journal_entry'
        """
    ).fetchone()
    definition = str(row[0]) if row is not None else ""
    return (
        "source_type IS DISTINCT FROM 'manual'" in definition
        and "Only a manual draft journal entry can be posted" in definition
    )


def _function_count(connection: psycopg.Connection, name: str) -> int:
    return int(
        connection.execute(
            """
            SELECT count(*)
            FROM pg_proc proc
            JOIN pg_namespace ns ON ns.oid = proc.pronamespace
            WHERE ns.nspname = 'accounting'
              AND proc.proname = %s
            """,
            (name,),
        ).fetchone()[0]
    )


def _verify_installed(
    connection: psycopg.Connection,
    *,
    require_zero_new_posting_rows: bool,
) -> None:
    required_relations = (
        "accounting.regular_journal_draft_preparations",
        "accounting.regular_journal_draft_preparation_entries",
        "accounting.regular_journal_draft_preparation_status",
        "accounting.regular_journal_posting_sets",
        "accounting.regular_journal_posting_entries",
    )
    missing = [relation for relation in required_relations if not _exists(connection, relation)]
    if missing:
        raise SystemExit(
            "Protected Regular accounting verification failed: missing "
            + ", ".join(missing)
        )

    if _function_count(connection, "create_regular_journal_draft_batch") != 1:
        raise SystemExit(
            "Protected Regular accounting verification failed: draft preparation function is missing"
        )
    if _function_count(connection, "post_regular_journal_review_set") != 1:
        raise SystemExit(
            "Protected Regular accounting verification failed: protected posting function is missing"
        )

    for permission in (
        "accounting.regular_journal.prepare",
        "accounting.regular_journal.post",
    ):
        permission_count = int(
            connection.execute(
                "SELECT count(*) FROM core.permissions WHERE code = %s",
                (permission,),
            ).fetchone()[0]
        )
        management_count = int(
            connection.execute(
                """
                SELECT count(*)
                FROM core.role_permissions rp
                JOIN core.roles role ON role.id = rp.role_id
                WHERE role.code = 'management'
                  AND rp.permission_code = %s
                """,
                (permission,),
            ).fetchone()[0]
        )
        if permission_count != 1 or management_count != 1:
            raise SystemExit(
                "Protected Regular accounting verification failed: Management permission is missing: "
                + permission
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
              'accounting_regular_system_journal_line_guard',
              'accounting_regular_journal_posting_set_guard',
              'accounting_regular_journal_posting_entry_guard'
          )
        """
    ).fetchall()
    trigger_names = {str(row[0]) for row in trigger_rows}
    required_triggers = {
        "accounting_regular_journal_draft_preparation_guard",
        "accounting_regular_journal_draft_preparation_entry_guard",
        "accounting_regular_system_journal_entry_guard",
        "accounting_regular_system_journal_line_guard",
        "accounting_regular_journal_posting_set_guard",
        "accounting_regular_journal_posting_entry_guard",
    }
    if trigger_names != required_triggers:
        raise SystemExit(
            "Protected Regular accounting verification failed: an immutability/posting guard is missing"
        )

    if not _manual_post_is_null_safe(connection):
        raise SystemExit(
            "Protected Regular accounting verification failed: manual General Journal posting is not NULL-safe and source-type hardened"
        )

    preparation_count = _count(connection, "accounting.regular_journal_draft_preparations")
    preparation_entry_count = _count(
        connection, "accounting.regular_journal_draft_preparation_entries"
    )
    posting_set_count = _count(connection, "accounting.regular_journal_posting_sets")
    posting_entry_count = _count(connection, "accounting.regular_journal_posting_entries")
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
    unaudited_posted_count = int(
        connection.execute(
            """
            SELECT count(*)::bigint
            FROM accounting.journal_entries journal
            JOIN accounting.regular_journal_draft_preparation_entries prepared
              ON prepared.journal_entry_id = journal.id
            LEFT JOIN accounting.regular_journal_posting_entries posted
              ON posted.journal_entry_id = journal.id
            WHERE journal.status = 'posted'
              AND posted.journal_entry_id IS NULL
            """
        ).fetchone()[0]
    )
    invalid_audit_count = int(
        connection.execute(
            """
            SELECT count(*)::bigint
            FROM accounting.regular_journal_posting_entries posted
            JOIN accounting.journal_entries journal
              ON journal.id = posted.journal_entry_id
            WHERE journal.status <> 'posted'
               OR journal.entry_number IS DISTINCT FROM posted.entry_number
               OR journal.source_event_key IS DISTINCT FROM posted.source_event_key
            """
        ).fetchone()[0]
    )

    if require_zero_new_posting_rows and (posting_set_count or posting_entry_count):
        raise SystemExit(
            "Protected Regular accounting verification failed: posting-control schema install created live posting audit rows"
        )
    if unaudited_posted_count != 0 or invalid_audit_count != 0:
        raise SystemExit(
            "Protected Regular accounting verification failed: a posted Regular journal is missing or disagrees with its immutable protected audit"
        )
    if posted_protected_count != posting_entry_count:
        raise SystemExit(
            "Protected Regular accounting verification failed: posted Regular journal count does not equal protected posting audit entry count"
        )

    dpd = _dpd_safety(connection)
    if dpd is not None and (
        bool(dpd[1]) or bool(dpd[2]) or dpd[3] is not None or bool(dpd[4])
    ):
        raise SystemExit(
            "Protected Regular accounting verification failed: default, ECL, or automatic posting was unexpectedly enabled"
        )

    print(
        "Protected Regular accounting summary: "
        f"preparations={preparation_count}, preparation_entries={preparation_entry_count}, "
        f"regular_journals={protected_journal_count}, posted_regular_journals={posted_protected_count}, "
        f"posting_sets={posting_set_count}, posting_entries={posting_entry_count}, "
        "regular_posting_enabled=True, automatic_source_posting=False"
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
            "Install and verify protected Regular source-event draft and explicit "
            "full-review-set posting controls without automatically posting anything."
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

    migration_paths = (DRAFT_MIGRATION, MANUAL_GUARD_MIGRATION, POSTING_MIGRATION)
    missing = [path for path in migration_paths if not path.is_file()]
    if missing:
        raise SystemExit(
            "Protected Regular accounting migration file was not found: "
            + ", ".join(str(path) for path in missing)
        )
    bodies = {
        path: _transaction_body(path.read_text(encoding="utf-8"))
        for path in migration_paths
    }

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "lending.loans",
                "lending.loan_collection_state",
                "lending.loan_types",
                "lending.collection_transactions",
                "accounting.accounts",
                "accounting.fiscal_periods",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "accounting.journal_events",
                "accounting.opening_balance_workbooks",
                "accounting.opening_balance_journal_preparations",
                "accounting.opening_balance_journal_postings",
                "accounting.opening_balance_loan_snapshot_batches",
                "accounting.opening_balance_loan_measurement_snapshots",
            )
            for relation in prerequisites:
                if not _exists(connection, relation):
                    raise SystemExit(
                        "Protected Regular accounting prerequisite is not installed: "
                        + relation
                    )

            draft_installed = _exists(
                connection, "accounting.regular_journal_draft_preparations"
            )
            posting_installed = _exists(
                connection, "accounting.regular_journal_posting_sets"
            )

            before_loans = _count(connection, "lending.loans")
            before_loan_statuses = _loan_status_counts(connection)
            before_transactions = _count(connection, "lending.collection_transactions")
            before_journals = _count(connection, "accounting.journal_entries")
            before_lines = _count(connection, "accounting.journal_lines")
            before_events = _count(connection, "accounting.journal_events")
            before_anchors = _accounting_anchor_counts(connection)
            before_reviewed = _historical_reviewed_count(connection)
            before_dpd = _dpd_safety(connection)

            if not draft_installed:
                connection.execute(bodies[DRAFT_MIGRATION])
                connection.execute(bodies[MANUAL_GUARD_MIGRATION])
            elif not _manual_post_is_null_safe(connection):
                connection.execute(bodies[MANUAL_GUARD_MIGRATION])

            if not posting_installed:
                connection.execute(bodies[POSTING_MIGRATION])

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
                    "Protected Regular accounting safety gate failed: live loans changed during schema install"
                )
            if after_transactions != before_transactions:
                raise SystemExit(
                    "Protected Regular accounting safety gate failed: collection transactions changed during schema install"
                )
            if (
                after_journals != before_journals
                or after_lines != before_lines
                or after_events != before_events
            ):
                raise SystemExit(
                    "Protected Regular accounting safety gate failed: journal rows changed during schema install"
                )
            if after_anchors != before_anchors:
                raise SystemExit(
                    "Protected Regular accounting safety gate failed: opening/cutover anchors changed during schema install"
                )
            if after_reviewed != before_reviewed or after_dpd != before_dpd:
                raise SystemExit(
                    "Protected Regular accounting safety gate failed: ECL/DPD state changed during schema install"
                )

            _verify_installed(
                connection,
                require_zero_new_posting_rows=not posting_installed,
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "Protected Regular accounting migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
