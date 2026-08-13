from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
POSTING_MIGRATION = SQL_ROOT / "0066_add_protected_7x7_source_event_journal_posting.sql"
REVERSAL_MIGRATION = SQL_ROOT / "0067_add_controlled_7x7_collection_reversals.sql"
REVERSAL_HARDENING_MIGRATION = SQL_ROOT / "0068_harden_controlled_7x7_collection_reversal_guard.sql"


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


def _transaction_body(source: str, label: str) -> str:
    body = source.strip()
    if not body.startswith("BEGIN;") or not body.endswith("COMMIT;"):
        raise SystemExit(
            f"7x7 journal-lifecycle live migration safety gate failed: {label} expected BEGIN/COMMIT wrapper"
        )
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _exists(connection: psycopg.Connection, relation: str) -> bool:
    return connection.execute("select to_regclass(%s)", (relation,)).fetchone()[0] is not None


def _count(connection: psycopg.Connection, relation: str) -> int:
    if not _exists(connection, relation):
        return 0
    return int(connection.execute(f"select count(*) from {relation}").fetchone()[0])


def _verify_posting_stage(connection: psycopg.Connection) -> None:
    required = (
        "accounting.seven_by_seven_journal_postings",
        "accounting.seven_by_seven_journal_posting_lines",
        "accounting.seven_by_seven_journal_posting_status",
    )
    for relation in required:
        if not _exists(connection, relation):
            raise SystemExit("7x7 posting live verification failed: missing " + relation)

    permission_count = int(
        connection.execute(
            """
            select count(*)
            from core.role_permissions rp
            join core.roles role on role.id = rp.role_id
            where role.code = 'management'
              and rp.permission_code = 'accounting.seven_by_seven.journal.post'
            """
        ).fetchone()[0]
    )
    if permission_count != 1:
        raise SystemExit(
            "7x7 posting live verification failed: Management posting permission is not installed exactly once"
        )

    unsafe = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_journal_posting_status
            where protected_posting_enabled is distinct from true
               or reversal_enabled
               or automatic_source_posting
            """
        ).fetchone()[0]
    )
    if unsafe:
        raise SystemExit(
            "7x7 posting live verification failed before 0067: posting/reversal/automatic-source flags are unsafe"
        )


def _verify_lifecycle(connection: psycopg.Connection) -> dict[str, int]:
    required = (
        "accounting.seven_by_seven_journal_reversals",
        "accounting.seven_by_seven_journal_reversal_lines",
        "accounting.seven_by_seven_journal_reversal_status",
        "accounting.seven_by_seven_journal_posting_status",
    )
    for relation in required:
        if not _exists(connection, relation):
            raise SystemExit("7x7 journal-lifecycle live verification failed: missing " + relation)

    unsafe_posting = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_journal_posting_status
            where protected_posting_enabled is distinct from true
               or reversal_enabled is distinct from true
               or automatic_source_posting
            """
        ).fetchone()[0]
    )
    if unsafe_posting:
        raise SystemExit(
            "7x7 journal-lifecycle live verification failed: posting lifecycle flags are unsafe"
        )

    unsafe_reversal = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_journal_reversal_status
            where protected_reversal_enabled is distinct from true
               or automatic_source_posting
               or (is_voided and reversal_audit_exact is distinct from true)
            """
        ).fetchone()[0]
    )
    if unsafe_reversal:
        raise SystemExit(
            "7x7 journal-lifecycle live verification failed: existing protected reversal history is not exact"
        )

    posting_count = _count(connection, "accounting.seven_by_seven_journal_postings")
    posting_line_count = _count(connection, "accounting.seven_by_seven_journal_posting_lines")
    reversal_count = _count(connection, "accounting.seven_by_seven_journal_reversals")
    reversal_line_count = _count(connection, "accounting.seven_by_seven_journal_reversal_lines")
    posted_protected_count = int(
        connection.execute(
            """
            select count(*) from accounting.journal_entries
            where source_type = 'seven_by_seven_collection' and status = 'posted'
            """
        ).fetchone()[0]
    )
    posting_audit_exact_count = int(
        connection.execute(
            """
            select count(*) from accounting.seven_by_seven_journal_posting_status
            where posted_audit_exact
            """
        ).fetchone()[0]
    )
    if posting_count != posted_protected_count or posting_count != posting_audit_exact_count:
        raise SystemExit(
            "7x7 journal-lifecycle live verification failed: protected posting history is not audit-exact"
        )

    voided_posting_count = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_journal_postings posted
            join lending.collection_transactions source on source.id = posted.transaction_id
            where source.is_voided
            """
        ).fetchone()[0]
    )
    exact_reversal_count = int(
        connection.execute(
            """
            select count(*) from accounting.seven_by_seven_journal_reversal_status
            where reversal_audit_exact
            """
        ).fetchone()[0]
    )
    if reversal_count != exact_reversal_count or voided_posting_count != exact_reversal_count:
        raise SystemExit(
            "7x7 journal-lifecycle live verification failed: voided protected postings do not reconcile to exact reversals"
        )

    return {
        "postings": posting_count,
        "posting_lines": posting_line_count,
        "reversals": reversal_count,
        "reversal_lines": reversal_line_count,
        "voided_postings": voided_posting_count,
        "exact_reversals": exact_reversal_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify protected 7x7 explicit posting plus controlled posted-collection "
            "void/reversal on the live database without creating or changing operational/accounting history."
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
    for migration in (
        POSTING_MIGRATION,
        REVERSAL_MIGRATION,
        REVERSAL_HARDENING_MIGRATION,
    ):
        if not migration.is_file():
            raise SystemExit("7x7 journal-lifecycle migration file was not found: " + str(migration))

    posting_body = _transaction_body(
        POSTING_MIGRATION.read_text(encoding="utf-8"), "0066"
    )
    reversal_body = _transaction_body(
        REVERSAL_MIGRATION.read_text(encoding="utf-8"), "0067"
    )
    reversal_hardening_body = _transaction_body(
        REVERSAL_HARDENING_MIGRATION.read_text(encoding="utf-8"), "0068"
    )

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "lending.collection_transactions",
                "lending.collection_transaction_voids",
                "accounting.accounts",
                "accounting.fiscal_periods",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "accounting.seven_by_seven_journal_draft_preparations",
                "accounting.seven_by_seven_journal_draft_status",
                "accounting.seven_by_seven_source_event_journal_coordinate_preview",
            )
            missing = [relation for relation in prerequisites if not _exists(connection, relation)]
            if missing:
                raise SystemExit(
                    "7x7 journal-lifecycle live migration prerequisite is not installed: "
                    + ", ".join(missing)
                )

            tracked = (
                "lending.collection_transactions",
                "lending.collection_transaction_voids",
                "accounting.seven_by_seven_journal_draft_preparations",
                "accounting.seven_by_seven_journal_postings",
                "accounting.seven_by_seven_journal_posting_lines",
                "accounting.seven_by_seven_journal_reversals",
                "accounting.seven_by_seven_journal_reversal_lines",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "core.audit_logs",
            )
            before = tuple(_count(connection, relation) for relation in tracked)

            connection.execute(posting_body)
            _verify_posting_stage(connection)
            connection.execute(reversal_body)
            connection.execute(reversal_hardening_body)
            summary = _verify_lifecycle(connection)

            after = tuple(_count(connection, relation) for relation in tracked)
            if after != before:
                raise SystemExit(
                    "7x7 journal-lifecycle live migration safety gate failed: installation changed live operational/accounting history"
                )

            print(
                "7x7 protected journal-lifecycle live summary: "
                f"postings={summary['postings']}, posting_lines={summary['posting_lines']}, "
                f"reversals={summary['reversals']}, reversal_lines={summary['reversal_lines']}, "
                f"voided_postings={summary['voided_postings']}, exact_reversals={summary['exact_reversals']}, "
                "history_unchanged=True, explicit_management_posting=True, "
                "protected_reversal_enabled=True, automatic_source_posting=False."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "7x7 protected journal-lifecycle live migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
