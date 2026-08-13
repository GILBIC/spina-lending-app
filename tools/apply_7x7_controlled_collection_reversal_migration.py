from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
MIGRATION = SQL_ROOT / "0067_add_controlled_7x7_collection_reversals.sql"


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


def _transaction_body(source: str) -> str:
    body = source.strip()
    if not body.startswith("BEGIN;") or not body.endswith("COMMIT;"):
        raise SystemExit(
            "7x7 collection-reversal live migration safety gate failed: expected BEGIN/COMMIT wrapper"
        )
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _exists(connection: psycopg.Connection, relation: str) -> bool:
    return connection.execute("select to_regclass(%s)", (relation,)).fetchone()[0] is not None


def _count(connection: psycopg.Connection, relation: str) -> int:
    if not _exists(connection, relation):
        return 0
    return int(connection.execute(f"select count(*) from {relation}").fetchone()[0])


def _verify_installed(connection: psycopg.Connection) -> dict[str, int]:
    required = (
        "accounting.seven_by_seven_journal_reversals",
        "accounting.seven_by_seven_journal_reversal_lines",
        "accounting.seven_by_seven_journal_reversal_status",
        "accounting.seven_by_seven_journal_posting_status",
    )
    for relation in required:
        if not _exists(connection, relation):
            raise SystemExit(
                "7x7 collection-reversal live verification failed: missing " + relation
            )

    unsafe_posting_status = int(
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
    if unsafe_posting_status:
        raise SystemExit(
            "7x7 collection-reversal live verification failed: protected posting lifecycle flags are unsafe"
        )

    unsafe_reversal_status = int(
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
    if unsafe_reversal_status:
        raise SystemExit(
            "7x7 collection-reversal live verification failed: existing reversal lifecycle is not exact"
        )

    posting_count = _count(connection, "accounting.seven_by_seven_journal_postings")
    reversal_count = _count(connection, "accounting.seven_by_seven_journal_reversals")
    reversal_line_count = _count(connection, "accounting.seven_by_seven_journal_reversal_lines")
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
            select count(*)
            from accounting.seven_by_seven_journal_reversal_status
            where reversal_audit_exact
            """
        ).fetchone()[0]
    )
    if voided_posting_count != exact_reversal_count or reversal_count != exact_reversal_count:
        raise SystemExit(
            "7x7 collection-reversal live verification failed: voided protected postings and immutable reversal audits do not reconcile"
        )

    return {
        "postings": posting_count,
        "reversals": reversal_count,
        "reversal_lines": reversal_line_count,
        "voided_postings": voided_posting_count,
        "exact_reversals": exact_reversal_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify the controlled posted-7x7 collection void/reversal on the live database "
            "without creating source, void, journal, posting, or reversal history and without enabling automatic source posting."
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
        raise SystemExit("7x7 collection-reversal migration file was not found: " + str(MIGRATION))
    body = _transaction_body(MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "lending.collection_transactions",
                "lending.collection_transaction_voids",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "accounting.seven_by_seven_journal_postings",
                "accounting.seven_by_seven_journal_posting_lines",
                "accounting.seven_by_seven_journal_posting_status",
            )
            missing = [relation for relation in prerequisites if not _exists(connection, relation)]
            if missing:
                raise SystemExit(
                    "7x7 collection-reversal live migration prerequisite is not installed: "
                    + ", ".join(missing)
                )

            tracked = (
                "lending.collection_transactions",
                "lending.collection_transaction_voids",
                "accounting.seven_by_seven_journal_postings",
                "accounting.seven_by_seven_journal_posting_lines",
                "accounting.seven_by_seven_journal_reversals",
                "accounting.seven_by_seven_journal_reversal_lines",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "core.audit_logs",
            )
            before = tuple(_count(connection, relation) for relation in tracked)
            connection.execute(body)
            summary = _verify_installed(connection)
            after = tuple(_count(connection, relation) for relation in tracked)
            if after != before:
                raise SystemExit(
                    "7x7 collection-reversal live migration safety gate failed: installation changed live operational/accounting history"
                )

            print(
                "7x7 controlled collection-reversal live summary: "
                f"postings={summary['postings']}, reversals={summary['reversals']}, "
                f"reversal_lines={summary['reversal_lines']}, voided_postings={summary['voided_postings']}, "
                f"exact_reversals={summary['exact_reversals']}, history_unchanged=True, "
                "explicit_management_posting=True, protected_reversal_enabled=True, "
                "automatic_source_posting=False."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "7x7 controlled collection-reversal live migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
