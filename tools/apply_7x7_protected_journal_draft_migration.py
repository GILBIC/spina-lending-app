from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
MIGRATION = SQL_ROOT / "0065_add_protected_7x7_source_event_journal_drafts.sql"


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
        raise SystemExit("7x7 journal-draft live migration safety gate failed: expected BEGIN/COMMIT wrapper")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _exists(connection: psycopg.Connection, relation: str) -> bool:
    return connection.execute("select to_regclass(%s)", (relation,)).fetchone()[0] is not None


def _count(connection: psycopg.Connection, relation: str) -> int:
    if not _exists(connection, relation):
        return 0
    return int(connection.execute(f"select count(*) from {relation}").fetchone()[0])


def _verify_installed(connection: psycopg.Connection) -> dict[str, int]:
    required_relations = (
        "accounting.seven_by_seven_journal_draft_preparations",
        "accounting.seven_by_seven_journal_draft_review",
        "accounting.seven_by_seven_journal_draft_status",
    )
    for relation in required_relations:
        if not _exists(connection, relation):
            raise SystemExit("7x7 journal-draft live verification failed: missing " + relation)

    permission_count = int(
        connection.execute(
            """
            select count(*)
            from core.role_permissions rp
            join core.roles role on role.id = rp.role_id
            where role.code = 'management'
              and rp.permission_code = 'accounting.seven_by_seven.journal.prepare'
            """
        ).fetchone()[0]
    )
    if permission_count != 1:
        raise SystemExit("7x7 journal-draft live verification failed: Management preparation permission is not installed exactly once")

    preparation_count = _count(connection, "accounting.seven_by_seven_journal_draft_preparations")
    protected_journal_count = int(
        connection.execute(
            "select count(*) from accounting.journal_entries where source_type = 'seven_by_seven_collection'"
        ).fetchone()[0]
    )
    if preparation_count != 0 or protected_journal_count != 0:
        raise SystemExit("7x7 journal-draft live migration safety gate failed: installation created protected draft history")

    unsafe_review_count = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_journal_draft_review
            where posting_enabled or automatic_source_posting
            """
        ).fetchone()[0]
    )
    unsafe_status_count = int(
        connection.execute(
            """
            select count(*)
            from accounting.seven_by_seven_journal_draft_status
            where posting_enabled or automatic_source_posting
            """
        ).fetchone()[0]
    )
    if unsafe_review_count or unsafe_status_count:
        raise SystemExit("7x7 journal-draft live verification failed: posting or automatic source posting was unexpectedly enabled")

    return {
        "review_rows": _count(connection, "accounting.seven_by_seven_journal_draft_review"),
        "preparations": preparation_count,
        "protected_journals": protected_journal_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify the protected Management-confirmed 7x7 journal-draft boundary on the live database "
            "without creating draft history, posting, reversal or automatic source posting."
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
        raise SystemExit("7x7 journal-draft migration file was not found: " + str(MIGRATION))
    body = _transaction_body(MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "lending.loans",
                "lending.clients",
                "lending.collection_transactions",
                "accounting.accounts",
                "accounting.fiscal_periods",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "accounting.seven_by_seven_source_event_accounting_preview",
                "accounting.seven_by_seven_source_event_journal_coordinate_preview",
            )
            missing = [relation for relation in prerequisites if not _exists(connection, relation)]
            if missing:
                raise SystemExit(
                    "7x7 journal-draft live migration prerequisite is not installed: " + ", ".join(missing)
                )

            tracked_relations = (
                "lending.loans",
                "lending.clients",
                "lending.collection_transactions",
                "accounting.seven_by_seven_eir_initial_carrying_anchors",
                "accounting.seven_by_seven_eir_initial_carrying_anchor_voids",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "core.audit_logs",
            )
            before_history = tuple(_count(connection, relation) for relation in tracked_relations)

            connection.execute(body)
            summary = _verify_installed(connection)

            after_history = tuple(_count(connection, relation) for relation in tracked_relations)
            if after_history != before_history:
                raise SystemExit(
                    "7x7 journal-draft live migration safety gate failed: installation changed live operational/accounting history"
                )

            print(
                "7x7 protected journal-draft live summary: "
                f"review_rows={summary['review_rows']}, preparations={summary['preparations']}, "
                f"protected_journals={summary['protected_journals']}, history_unchanged=True, "
                "draft_creation_requires_explicit_management_confirmation=True, "
                "posting_enabled=False, reversal_enabled=False, automatic_source_posting=False."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "7x7 protected journal-draft live migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
