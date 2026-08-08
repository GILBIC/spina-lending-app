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
    / "0034_add_contractual_schedule_dpd_foundation.sql"
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


def _count(connection: psycopg.Connection, relation: str) -> int:
    return int(connection.execute(f"SELECT count(*) FROM {relation}").fetchone()[0])


def _loan_status_counts(connection: psycopg.Connection) -> Counter[str]:
    rows = connection.execute(
        "SELECT status, count(*)::bigint FROM lending.loans GROUP BY status"
    ).fetchall()
    return Counter({str(status): int(count) for status, count in rows})


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


def _journal_count(connection: psycopg.Connection) -> int | None:
    exists = connection.execute(
        "SELECT to_regclass('accounting.journal_entries')"
    ).fetchone()[0]
    if exists is None:
        return None
    return _count(connection, "accounting.journal_entries")


def _verify_installed(
    connection: psycopg.Connection,
    *,
    require_pristine_install: bool,
) -> None:
    objects = connection.execute(
        """
        SELECT
            to_regclass('lending.loan_contract_schedules'),
            to_regclass('lending.loan_contract_installments'),
            to_regclass('lending.loan_installment_payment_allocations'),
            to_regclass('accounting.loan_contract_dpd_assessment'),
            to_regclass('accounting.loan_contract_dpd_summary')
        """
    ).fetchone()
    if any(item is None for item in objects):
        raise SystemExit(
            "Stage 5E.4.1 verification failed: required schedule/DPD objects are missing"
        )

    schedule_count = _count(connection, "lending.loan_contract_schedules")
    installment_count = _count(connection, "lending.loan_contract_installments")
    allocation_count = _count(
        connection, "lending.loan_installment_payment_allocations"
    )
    if require_pristine_install and (
        schedule_count or installment_count or allocation_count
    ):
        raise SystemExit(
            "Stage 5E.4.1 verification failed: live install must not auto-create "
            "contract schedules, installments, or payment allocations"
        )

    summary = connection.execute(
        """
        SELECT
            loan_count,
            ready_count,
            contract_schedule_required_count,
            contract_installments_required_count,
            payment_allocation_required_count,
            past_due_count,
            thirty_day_backstop_count,
            ninety_day_backstop_count,
            automatic_default_label_written,
            ecl_included,
            ecl_amount,
            ready_to_post
        FROM accounting.loan_contract_dpd_summary
        """
    ).fetchone()
    live_loan_count = _count(connection, "lending.loans")
    if int(summary[0]) != live_loan_count:
        raise SystemExit(
            "Stage 5E.4.1 verification failed: DPD summary does not cover every live loan"
        )

    if require_pristine_install:
        if int(summary[1]) != 0:
            raise SystemExit(
                "Stage 5E.4.1 verification failed: existing loans became DPD-ready without verified schedules"
            )
        if int(summary[2]) != live_loan_count:
            raise SystemExit(
                "Stage 5E.4.1 verification failed: existing loans must remain contract_schedule_required"
            )
        if any(int(summary[index]) != 0 for index in range(3, 8)):
            raise SystemExit(
                "Stage 5E.4.1 verification failed: live install unexpectedly produced DPD/backstop activity"
            )

    if bool(summary[8]) or bool(summary[9]) or summary[10] is not None or bool(summary[11]):
        raise SystemExit(
            "Stage 5E.4.1 verification failed: default, ECL, or posting was unexpectedly enabled"
        )

    print(
        "Stage 5E.4.1 DPD summary: "
        f"loans={summary[0]}, ready={summary[1]}, "
        f"schedule_required={summary[2]}, installments_required={summary[3]}, "
        f"allocation_required={summary[4]}, past_due={summary[5]}, "
        f"backstop30={summary[6]}, backstop90={summary[7]}, "
        f"schedules={schedule_count}, installments={installment_count}, "
        f"allocations={allocation_count}, automatic_default={summary[8]}, "
        f"ecl_included={summary[9]}, ecl_amount={summary[10]}, "
        f"ready_to_post={summary[11]}."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Apply the guarded Stage 5E.4.1 contractual schedule/DPD foundation "
            "to the live SPINA database without creating client schedules."
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
        raise SystemExit(f"Stage 5E.4.1 migration file was not found: {MIGRATION}")

    with psycopg.connect(database_url, autocommit=True) as connection:
        if connection.execute("SELECT to_regclass('lending.loans')").fetchone()[0] is None:
            raise SystemExit("Core lending schema is not installed")
        if connection.execute(
            "SELECT to_regclass('lending.collection_transactions')"
        ).fetchone()[0] is None:
            raise SystemExit("Collection transaction schema is not installed")

        already_installed = connection.execute(
            "SELECT to_regclass('lending.loan_contract_schedules')"
        ).fetchone()[0]
        if already_installed is not None:
            print("Stage 5E.4.1 is already installed; skipping migration application.")
            _verify_installed(connection, require_pristine_install=False)
            return 0

        before_loans = _count(connection, "lending.loans")
        before_statuses = _loan_status_counts(connection)
        before_transactions = _count(connection, "lending.collection_transactions")
        before_journals = _journal_count(connection)
        before_reviewed = _historical_reviewed_count(connection)

        migration_sql = MIGRATION.read_text(encoding="utf-8")
        try:
            connection.execute(migration_sql)
        except psycopg.Error as error:
            raise SystemExit(f"Stage 5E.4.1 migration failed: {error}") from error

        after_loans = _count(connection, "lending.loans")
        after_statuses = _loan_status_counts(connection)
        after_transactions = _count(connection, "lending.collection_transactions")
        after_journals = _journal_count(connection)
        after_reviewed = _historical_reviewed_count(connection)

        if after_loans != before_loans or after_statuses != before_statuses:
            raise SystemExit(
                "Stage 5E.4.1 safety gate failed: lending.loans changed during schema install"
            )
        if after_transactions != before_transactions:
            raise SystemExit(
                "Stage 5E.4.1 safety gate failed: collection transactions changed during schema install"
            )
        if after_journals != before_journals:
            raise SystemExit(
                "Stage 5E.4.1 safety gate failed: journal entries changed during schema install"
            )
        if after_reviewed != before_reviewed:
            raise SystemExit(
                "Stage 5E.4.1 safety gate failed: historical ECL outcome labels changed"
            )

        _verify_installed(connection, require_pristine_install=True)

    print(
        "Stage 5E.4.1 live migration complete. Contractual DPD schema is installed; "
        "existing loans remain unclassified and require verified contractual schedules."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
