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
    / "0036_add_per_loan_contract_collection_activation.sql"
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
            "Stage 5E.4.6A migration safety gate failed: expected BEGIN/COMMIT wrapper"
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


def _schedule_counts(connection: psycopg.Connection) -> tuple[int, int, int, int]:
    return (
        _count(connection, "lending.loan_contract_schedules"),
        _count(connection, "lending.loan_contract_installments"),
        _count(connection, "lending.loan_installment_payment_allocations"),
        _count(connection, "lending.loan_contract_schedule_registrations"),
    )


def _dpd_summary(connection: psycopg.Connection) -> tuple[object, ...]:
    row = connection.execute(
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
    if row is None:
        raise SystemExit("Stage 5E.4.6A verification failed: DPD summary is unavailable")
    return tuple(row)


def _activation_counts(connection: psycopg.Connection) -> tuple[int, int]:
    events = _count(connection, "lending.loan_contract_collection_activation_events")
    active = int(
        connection.execute(
            """
            SELECT count(*)::bigint
            FROM lending.loan_contract_collection_activation_state
            WHERE is_active = true
            """
        ).fetchone()[0]
    )
    return events, active


def _verify_installed(
    connection: psycopg.Connection,
    *,
    require_pristine_install: bool,
) -> None:
    activation_table = connection.execute(
        "SELECT to_regclass('lending.loan_contract_collection_activation_events')"
    ).fetchone()[0]
    activation_view = connection.execute(
        "SELECT to_regclass('lending.loan_contract_collection_activation_state')"
    ).fetchone()[0]
    if activation_table is None or activation_view is None:
        raise SystemExit(
            "Stage 5E.4.6A verification failed: activation audit table/view is missing"
        )

    permission_count = int(
        connection.execute(
            "SELECT count(*) FROM core.permissions WHERE code = 'lending.contract_collection.activate'"
        ).fetchone()[0]
    )
    management_permission_count = int(
        connection.execute(
            """
            SELECT count(*)
            FROM core.role_permissions rp
            JOIN core.roles r ON r.id = rp.role_id
            WHERE r.code = 'management'
              AND rp.permission_code = 'lending.contract_collection.activate'
            """
        ).fetchone()[0]
    )
    if permission_count != 1 or management_permission_count != 1:
        raise SystemExit(
            "Stage 5E.4.6A verification failed: Management per-loan activation permission is not installed"
        )

    trigger_rows = connection.execute(
        """
        SELECT tgname
        FROM pg_trigger
        WHERE NOT tgisinternal
          AND tgname IN (
              'lending_contract_collection_activation_validate',
              'lending_contract_collection_activation_audit_guard'
          )
        """
    ).fetchall()
    trigger_names = {str(row[0]) for row in trigger_rows}
    required_triggers = {
        "lending_contract_collection_activation_validate",
        "lending_contract_collection_activation_audit_guard",
    }
    if trigger_names != required_triggers:
        raise SystemExit(
            "Stage 5E.4.6A verification failed: activation validation/audit guards are missing"
        )

    event_count, active_count = _activation_counts(connection)
    if require_pristine_install and (event_count != 0 or active_count != 0):
        raise SystemExit(
            "Stage 5E.4.6A verification failed: live install must create zero activation events and zero active loans"
        )

    schedule_count, installment_count, allocation_count, registration_count = (
        _schedule_counts(connection)
    )
    summary = _dpd_summary(connection)
    live_loan_count = _count(connection, "lending.loans")
    if int(summary[0]) != live_loan_count:
        raise SystemExit(
            "Stage 5E.4.6A verification failed: DPD summary does not cover every live loan"
        )
    if bool(summary[8]) or bool(summary[9]) or summary[10] is not None or bool(summary[11]):
        raise SystemExit(
            "Stage 5E.4.6A verification failed: default, ECL, or posting was unexpectedly enabled"
        )

    print(
        "Stage 5E.4.6A activation summary: "
        f"loans={summary[0]}, ready={summary[1]}, schedule_required={summary[2]}, "
        f"installments_required={summary[3]}, allocation_required={summary[4]}, "
        f"past_due={summary[5]}, backstop30={summary[6]}, backstop90={summary[7]}, "
        f"schedules={schedule_count}, installments={installment_count}, "
        f"allocations={allocation_count}, registrations={registration_count}, "
        f"activation_events={event_count}, active_activations={active_count}, "
        f"automatic_default={summary[8]}, ecl_included={summary[9]}, "
        f"ecl_amount={summary[10]}, ready_to_post={summary[11]}."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Apply the guarded Stage 5E.4.6A per-loan contractual collection "
            "activation audit schema without activating any live loan."
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
        raise SystemExit(f"Stage 5E.4.6A migration file was not found: {MIGRATION}")

    migration_body = _transaction_body(MIGRATION.read_text(encoding="utf-8"))

    try:
        with psycopg.connect(database_url) as connection:
            required = (
                "lending.loans",
                "lending.collection_transactions",
                "lending.loan_contract_schedules",
                "lending.loan_contract_installments",
                "lending.loan_installment_payment_allocations",
                "lending.loan_contract_schedule_registrations",
                "accounting.loan_contract_dpd_summary",
            )
            for relation in required:
                if connection.execute(
                    "SELECT to_regclass(%s)", (relation,)
                ).fetchone()[0] is None:
                    raise SystemExit(
                        f"Stage 5E.4.6A prerequisite is not installed: {relation}"
                    )

            already_installed = connection.execute(
                "SELECT to_regclass('lending.loan_contract_collection_activation_events')"
            ).fetchone()[0]
            if already_installed is not None:
                print("Stage 5E.4.6A is already installed; skipping migration application.")
                _verify_installed(connection, require_pristine_install=False)
                return 0

            before_loans = _count(connection, "lending.loans")
            before_statuses = _loan_status_counts(connection)
            before_transactions = _count(connection, "lending.collection_transactions")
            before_journals = _journal_count(connection)
            before_reviewed = _historical_reviewed_count(connection)
            before_schedule_counts = _schedule_counts(connection)
            before_dpd_summary = _dpd_summary(connection)

            connection.execute(migration_body)

            after_loans = _count(connection, "lending.loans")
            after_statuses = _loan_status_counts(connection)
            after_transactions = _count(connection, "lending.collection_transactions")
            after_journals = _journal_count(connection)
            after_reviewed = _historical_reviewed_count(connection)
            after_schedule_counts = _schedule_counts(connection)
            after_dpd_summary = _dpd_summary(connection)

            if after_loans != before_loans or after_statuses != before_statuses:
                raise SystemExit(
                    "Stage 5E.4.6A safety gate failed: lending.loans changed during schema install"
                )
            if after_transactions != before_transactions:
                raise SystemExit(
                    "Stage 5E.4.6A safety gate failed: collection transactions changed during schema install"
                )
            if after_journals != before_journals:
                raise SystemExit(
                    "Stage 5E.4.6A safety gate failed: journal entries changed during schema install"
                )
            if after_reviewed != before_reviewed:
                raise SystemExit(
                    "Stage 5E.4.6A safety gate failed: historical ECL outcome labels changed"
                )
            if after_schedule_counts != before_schedule_counts:
                raise SystemExit(
                    "Stage 5E.4.6A safety gate failed: schedules, installments, payment allocations, or registrations changed during schema install"
                )
            if after_dpd_summary != before_dpd_summary:
                raise SystemExit(
                    "Stage 5E.4.6A safety gate failed: DPD readiness or delinquency state changed during schema install"
                )

            _verify_installed(connection, require_pristine_install=True)
            # The psycopg connection context commits only after every safety gate succeeds.
    except psycopg.Error as error:
        raise SystemExit(f"Stage 5E.4.6A migration failed and was rolled back: {error}") from error

    print(
        "Stage 5E.4.6A live migration complete. Per-loan activation audit controls "
        "are installed with zero activation events; no live collection behavior changed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
