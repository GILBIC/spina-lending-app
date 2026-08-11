from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
COORDINATE_MIGRATION = SQL_ROOT / "0046_add_new_loan_disbursement_journal_coordinates.sql"


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
            "Stage 5D.20 live migration safety gate failed: expected BEGIN/COMMIT wrapper"
        )
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _exists(connection: psycopg.Connection, relation: str) -> bool:
    return connection.execute(
        "select to_regclass(%s)", (relation,)
    ).fetchone()[0] is not None


def _count(connection: psycopg.Connection, relation: str) -> int:
    return int(connection.execute(f"select count(*) from {relation}").fetchone()[0])


def _data_snapshot(connection: psycopg.Connection) -> tuple[int, ...]:
    return (
        _count(connection, "lending.clients"),
        _count(connection, "lending.loans"),
        _count(connection, "lending.collection_transactions"),
        _count(connection, "lending.loan_disbursement_events"),
        _count(connection, "accounting.journal_entries"),
        _count(connection, "accounting.journal_lines"),
        _count(connection, "accounting.journal_events"),
        _count(connection, "core.audit_logs"),
    )


def _verify_installed(connection: psycopg.Connection) -> dict[str, int]:
    relation = "accounting.loan_disbursement_journal_coordinates"
    if not _exists(connection, relation):
        raise SystemExit(
            "Stage 5D.20 live verification failed: missing " + relation
        )

    permission = connection.execute(
        """
        select
            count(*) filter (where permission.code is not null),
            count(*) filter (where role.code = 'management')
        from core.permissions permission
        left join core.role_permissions rp
          on rp.permission_code = permission.code
        left join core.roles role on role.id = rp.role_id
        where permission.code = 'accounting.loan_disbursement.coordinates.view'
        """
    ).fetchone()
    if permission != (1, 1):
        raise SystemExit(
            "Stage 5D.20 live verification failed: Management coordinate-view permission is missing"
        )

    invalid_flags = int(
        connection.execute(
            """
            select count(*)
            from accounting.loan_disbursement_journal_coordinates
            where journal_draft_enabled = true
               or automatic_source_posting = true
            """
        ).fetchone()[0]
    )
    if invalid_flags:
        raise SystemExit(
            "Stage 5D.20 live verification failed: coordinates unexpectedly enabled drafting or automatic posting"
        )

    rows = _count(connection, relation)
    loans = _count(connection, "lending.loans")
    if rows != loans:
        raise SystemExit(
            "Stage 5D.20 live verification failed: coordinate row count does not equal authoritative loan count"
        )

    ready = int(
        connection.execute(
            """
            select count(*)
            from accounting.loan_disbursement_journal_coordinates
            where coordinate_status = 'coordinate_ready'
            """
        ).fetchone()[0]
    )
    exposed_blocked_amounts = int(
        connection.execute(
            """
            select count(*)
            from accounting.loan_disbursement_journal_coordinates
            where coordinate_status <> 'coordinate_ready'
              and (
                    debit_account_system_key is not null
                 or debit_amount is not null
                 or credit_account_system_key is not null
                 or credit_amount is not null
              )
            """
        ).fetchone()[0]
    )
    if exposed_blocked_amounts:
        raise SystemExit(
            "Stage 5D.20 live verification failed: a blocked source exposed accounting coordinates"
        )

    invalid_ready = int(
        connection.execute(
            """
            select count(*)
            from accounting.loan_disbursement_journal_coordinates
            where coordinate_status = 'coordinate_ready'
              and (
                    evidence_readiness_status <> 'source_evidence_ready'
                 or event_kind <> 'new_loan_release'
                 or calculation_mode <> 'fixed_daily'
                 or debit_account_system_key <> 'loans_receivable_regular'
                 or credit_account_system_key not in (
                        'cash_office', 'cash_collector_custody', 'cash_bank_gcash'
                    )
                 or debit_amount is null
                 or credit_amount is null
                 or debit_amount <> credit_amount
                 or fiscal_period_id is null
                 or existing_journal_entry_id is not null
              )
            """
        ).fetchone()[0]
    )
    if invalid_ready:
        raise SystemExit(
            "Stage 5D.20 live verification failed: a coordinate-ready row violates the pure new-Regular release contract"
        )

    return {"rows": rows, "ready": ready, "blocked": rows - ready}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify Stage 5D.20 read-only new-Regular-loan disbursement "
            "coordinates without creating, changing, or posting any financial history."
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
    if not COORDINATE_MIGRATION.is_file():
        raise SystemExit("Stage 5D.20 migration file was not found: " + str(COORDINATE_MIGRATION))
    body = _transaction_body(COORDINATE_MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            prerequisites = (
                "lending.clients",
                "lending.loans",
                "lending.collection_transactions",
                "lending.loan_disbursement_events",
                "accounting.loan_disbursement_source_readiness",
                "accounting.accounts",
                "accounting.fiscal_periods",
                "accounting.journal_entries",
                "accounting.journal_lines",
                "accounting.journal_events",
                "core.audit_logs",
            )
            missing = [relation for relation in prerequisites if not _exists(connection, relation)]
            if missing:
                raise SystemExit(
                    "Stage 5D.20 live migration prerequisite is not installed: "
                    + ", ".join(missing)
                )

            before = _data_snapshot(connection)
            connection.execute(body)
            summary = _verify_installed(connection)
            after = _data_snapshot(connection)

            if after != before:
                raise SystemExit(
                    "Stage 5D.20 live migration safety gate failed: installing the read-only coordinate layer changed operational/accounting/audit rows"
                )

            print(
                "Stage 5D.20 loan-disbursement coordinate summary: "
                f"rows={summary['rows']}, coordinate_ready={summary['ready']}, "
                f"blocked={summary['blocked']}, journal_draft_enabled=False, "
                "automatic_source_posting=False; no financial-history rows changed."
            )
            return 0
    except psycopg.Error as error:
        raise SystemExit(
            "Stage 5D.20 new-loan disbursement coordinate migration failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
