from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
MIGRATION = SQL_ROOT / "0081_add_protected_initial_capital_funding.sql"


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
    source = source.strip()
    if not source.startswith("BEGIN;") or not source.endswith("COMMIT;"):
        raise SystemExit(
            "Initial-capital live migration safety gate failed: expected BEGIN/COMMIT wrapper"
        )
    return source[len("BEGIN;") :].lstrip()[: -len("COMMIT;")].rstrip()


def _exists(connection: psycopg.Connection, relation: str) -> bool:
    return connection.execute("SELECT to_regclass(%s)", (relation,)).fetchone()[0] is not None


def _count(connection: psycopg.Connection, relation: str) -> int:
    return int(connection.execute(f"SELECT count(*) FROM {relation}").fetchone()[0])


def _function_count(connection: psycopg.Connection, schema: str, name: str) -> int:
    return int(
        connection.execute(
            """
            SELECT count(*)
            FROM pg_proc proc
            JOIN pg_namespace ns ON ns.oid = proc.pronamespace
            WHERE ns.nspname=%s AND proc.proname=%s
            """,
            (schema, name),
        ).fetchone()[0]
    )


def _trigger_count(connection: psycopg.Connection, relation: str, trigger: str) -> int:
    return int(
        connection.execute(
            """
            SELECT count(*)
            FROM pg_trigger
            WHERE tgrelid=%s::regclass AND NOT tgisinternal AND tgname=%s
            """,
            (relation, trigger),
        ).fetchone()[0]
    )


def _history_counts(connection: psycopg.Connection) -> tuple[int, ...]:
    return (
        _count(connection, "lending.loans"),
        _count(connection, "lending.collection_transactions"),
        _count(connection, "accounting.journal_entries"),
        _count(connection, "accounting.journal_lines"),
        _count(connection, "accounting.journal_events"),
        _count(connection, "accounting.ecl_allowance_remeasurements"),
        _count(connection, "accounting.ecl_accounting_writeoffs"),
        _count(connection, "accounting.ecl_post_writeoff_recoveries"),
        _count(connection, "core.audit_logs"),
    )


def _verify_installed(connection: psycopg.Connection) -> dict[str, int]:
    required_relations = (
        "accounting.initial_capital_funding_evidence",
        "accounting.initial_capital_funding_preparations",
        "accounting.initial_capital_funding_postings",
        "accounting.initial_capital_funding_queue",
    )
    for relation in required_relations:
        if not _exists(connection, relation):
            raise SystemExit(
                "Initial-capital live verification failed: missing " + relation
            )

    required_functions = (
        "require_initial_capital_management_actor",
        "guard_initial_capital_evidence_write",
        "guard_initial_capital_preparation_write",
        "guard_initial_capital_posting_write",
        "guard_initial_capital_journal_entry_change",
        "guard_initial_capital_journal_line_change",
        "record_initial_capital_funding_evidence",
        "prepare_initial_capital_funding_journal",
        "post_initial_capital_funding_journal",
    )
    for function_name in required_functions:
        if _function_count(connection, "accounting", function_name) != 1:
            raise SystemExit(
                "Initial-capital live verification failed: protected function missing or ambiguous: accounting."
                + function_name
            )

    triggers = (
        (
            "accounting.initial_capital_funding_evidence",
            "accounting_initial_capital_evidence_guard",
        ),
        (
            "accounting.initial_capital_funding_preparations",
            "accounting_initial_capital_preparation_guard",
        ),
        (
            "accounting.initial_capital_funding_postings",
            "accounting_initial_capital_posting_guard",
        ),
        (
            "accounting.journal_entries",
            "accounting_initial_capital_journal_entry_guard",
        ),
        (
            "accounting.journal_lines",
            "accounting_initial_capital_journal_line_guard",
        ),
    )
    for relation, trigger in triggers:
        if _trigger_count(connection, relation, trigger) != 1:
            raise SystemExit(
                "Initial-capital live verification failed: protected trigger is missing: "
                + trigger
            )

    permission_rows = connection.execute(
        """
        SELECT permission.code,
               count(*) FILTER (WHERE role.code='management') AS management_grants
        FROM core.permissions permission
        LEFT JOIN core.role_permissions role_permission
          ON role_permission.permission_code=permission.code
        LEFT JOIN core.roles role ON role.id=role_permission.role_id
        WHERE permission.code IN (
            'accounting.initial_capital.evidence.record',
            'accounting.initial_capital.prepare',
            'accounting.initial_capital.post'
        )
        GROUP BY permission.code
        ORDER BY permission.code
        """
    ).fetchall()
    if len(permission_rows) != 3 or any(row[1] != 1 for row in permission_rows):
        raise SystemExit(
            "Initial-capital live verification failed: exact Management permissions are missing"
        )

    accounts = connection.execute(
        """
        SELECT code, system_key, account_type, normal_balance, is_active, is_posting
        FROM accounting.accounts
        WHERE code IN ('1010','1030','3000')
        ORDER BY code
        """
    ).fetchall()
    if accounts != [
        ("1010", "cash_office", "asset", "debit", True, True),
        ("1030", "cash_bank_gcash", "asset", "debit", True, True),
        ("3000", "capital", "equity", "credit", True, True),
    ]:
        raise SystemExit(
            "Initial-capital live verification failed: protected cash/bank/Capital account coordinates changed"
        )

    invalid_flags = _count_invalid_flags(connection)
    if invalid_flags:
        raise SystemExit(
            "Initial-capital live verification failed: queue enabled a synthetic opening balance or automatic source posting"
        )

    return {
        "evidence": _count(connection, "accounting.initial_capital_funding_evidence"),
        "preparations": _count(
            connection, "accounting.initial_capital_funding_preparations"
        ),
        "postings": _count(connection, "accounting.initial_capital_funding_postings"),
    }


def _count_invalid_flags(connection: psycopg.Connection) -> int:
    return int(
        connection.execute(
            """
            SELECT count(*)
            FROM accounting.initial_capital_funding_queue
            WHERE protected_initial_capital_funding_enabled IS DISTINCT FROM true
               OR synthetic_opening_balance_required IS DISTINCT FROM false
               OR automatic_source_posting IS DISTINCT FROM false
            """
        ).fetchone()[0]
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify A6.1 initial-capital funding controls on the approved live "
            "database without creating capital evidence, journal drafts/postings, or changing history."
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
        raise SystemExit("Initial-capital migration file was not found: " + str(MIGRATION))
    body = _transaction_body(MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "core.users",
                "core.roles",
                "core.permissions",
                "core.role_permissions",
                "core.audit_logs",
                "lending.loans",
                "lending.collection_transactions",
                "accounting.accounts",
                "accounting.fiscal_periods",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "accounting.journal_events",
                "accounting.ecl_allowance_remeasurements",
                "accounting.ecl_accounting_writeoffs",
                "accounting.ecl_post_writeoff_recoveries",
            )
            missing = [relation for relation in prerequisites if not _exists(connection, relation)]
            if missing:
                raise SystemExit(
                    "Initial-capital live migration prerequisite is not installed: "
                    + ", ".join(missing)
                )

            before_history = _history_counts(connection)
            evidence_already_installed = _exists(
                connection, "accounting.initial_capital_funding_evidence"
            )
            before_specific = (
                (
                    _count(connection, "accounting.initial_capital_funding_evidence"),
                    _count(connection, "accounting.initial_capital_funding_preparations"),
                    _count(connection, "accounting.initial_capital_funding_postings"),
                )
                if evidence_already_installed
                else (0, 0, 0)
            )

            connection.execute(body)
            summary = _verify_installed(connection)

            after_history = _history_counts(connection)
            after_specific = (
                summary["evidence"],
                summary["preparations"],
                summary["postings"],
            )
            if after_history != before_history:
                raise SystemExit(
                    "Initial-capital live migration safety gate failed: installing controls changed protected operational/accounting history"
                )
            if after_specific != before_specific:
                raise SystemExit(
                    "Initial-capital live migration safety gate failed: installing controls created or removed funding evidence/preparation/posting rows"
                )

            print(
                "Initial-capital live summary: "
                f"evidence={summary['evidence']}, preparations={summary['preparations']}, "
                f"postings={summary['postings']}, history_unchanged=True, "
                "protected_initial_capital_funding_enabled=True, "
                "synthetic_opening_balance_required=False, automatic_source_posting=False."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "Initial-capital live migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
