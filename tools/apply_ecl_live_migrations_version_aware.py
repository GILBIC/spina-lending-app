from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg

TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

import apply_ecl_credit_risk_labels_migration as ecl

A5_MIGRATION = ecl.SQL_ROOT / "0079_add_ecl_remeasurement_writeoff_recovery.sql"
if A5_MIGRATION not in ecl.MIGRATIONS:
    ecl.MIGRATIONS = (*ecl.MIGRATIONS, A5_MIGRATION)

A5_AUDIT_RELATIONS = (
    "accounting.ecl_allowance_remeasurements",
    "accounting.ecl_accounting_writeoffs",
    "accounting.ecl_post_writeoff_recoveries",
)


def _column_exists(connection: psycopg.Connection, *, schema: str, relation: str, column: str) -> bool:
    return bool(
        connection.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema=%s AND table_name=%s AND column_name=%s
            )
            """,
            (schema, relation, column),
        ).fetchone()[0]
    )


def _trigger_exists(connection: psycopg.Connection, *, schema: str, relation: str, trigger_name: str) -> bool:
    return bool(
        connection.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_trigger trigger
                JOIN pg_class relation ON relation.oid=trigger.tgrelid
                JOIN pg_namespace namespace ON namespace.oid=relation.relnamespace
                WHERE namespace.nspname=%s AND relation.relname=%s
                  AND trigger.tgname=%s AND NOT trigger.tgisinternal
            )
            """,
            (schema, relation, trigger_name),
        ).fetchone()[0]
    )


def _migration_installed(connection: psycopg.Connection, migration_name: str) -> bool:
    if migration_name == "0070_add_ecl_credit_risk_labels.sql":
        row = connection.execute(
            """
            SELECT
                to_regclass('accounting.ecl_credit_risk_label_reviews') IS NOT NULL,
                to_regclass('accounting.ecl_credit_risk_label_policy_v1') IS NOT NULL,
                to_regprocedure('accounting.review_ecl_credit_risk_labels(uuid,text,boolean,text,text,text,text,text,boolean,boolean,text,text,text,text,uuid,uuid)') IS NOT NULL
            """
        ).fetchone()
        return all(bool(value) for value in row)

    if migration_name == "0071_harden_ecl_cash_recovery_chronology.sql":
        return bool(connection.execute("SELECT to_regprocedure('accounting.guard_ecl_cash_recovery_chronology()') IS NOT NULL").fetchone()[0]) and _trigger_exists(
            connection, schema="accounting", relation="ecl_credit_risk_label_reviews", trigger_name="ecl_cash_recovery_chronology_guard"
        )

    if migration_name == "0072_add_ecl_quantitative_input_readiness.sql":
        return bool(
            connection.execute(
                """
                SELECT to_regclass('accounting.ecl_quantitative_input_readiness_a1_base') IS NOT NULL
                    OR (to_regclass('accounting.ecl_quantitative_input_readiness') IS NOT NULL
                        AND to_regclass('accounting.ecl_forward_looking_evidence_readiness') IS NULL)
                """
            ).fetchone()[0]
        )

    if migration_name == "0073_add_ecl_forward_looking_evidence_governance.sql":
        return bool(
            connection.execute(
                """
                SELECT to_regclass('accounting.ecl_forward_looking_evidence') IS NOT NULL
                    AND to_regclass('accounting.ecl_forward_looking_evidence_revocations') IS NOT NULL
                    AND to_regprocedure('accounting.record_ecl_forward_looking_evidence(text,text,text,date,date,date,date,timestamp with time zone,date,text,uuid,uuid)') IS NOT NULL
                """
            ).fetchone()[0]
        )

    if migration_name == "0074_integrate_ecl_forward_looking_readiness.sql":
        return bool(
            connection.execute(
                """
                SELECT to_regclass('accounting.ecl_quantitative_input_readiness_a1_base') IS NOT NULL
                    AND to_regclass('accounting.ecl_forward_looking_evidence_readiness') IS NOT NULL
                """
            ).fetchone()[0]
        )

    if migration_name == "0075_add_read_only_quantitative_ecl_measurement.sql":
        return bool(
            connection.execute(
                """
                SELECT to_regclass('accounting.ecl_quantitative_measurements') IS NOT NULL
                    AND to_regclass('accounting.ecl_quantitative_measurement_queue') IS NOT NULL
                    AND to_regprocedure('accounting.record_read_only_quantitative_ecl_measurement(uuid,date,jsonb,text,uuid)') IS NOT NULL
                """
            ).fetchone()[0]
        )

    if migration_name == "0076_harden_read_only_quantitative_ecl_measurement.sql":
        return bool(
            connection.execute(
                "SELECT to_regprocedure('accounting.record_read_only_quantitative_ecl_measurement_v1_impl(uuid,date,jsonb,text,uuid)') IS NOT NULL"
            ).fetchone()[0]
        ) and _column_exists(
            connection, schema="accounting", relation="ecl_quantitative_measurement_queue", column="measurement_forward_evidence_current"
        )

    if migration_name == "0077_add_protected_ecl_allowance_posting.sql":
        row = connection.execute(
            """
            SELECT
                to_regclass('accounting.ecl_allowance_draft_preparations') IS NOT NULL,
                to_regclass('accounting.ecl_allowance_postings') IS NOT NULL,
                to_regclass('accounting.ecl_allowance_posting_lines') IS NOT NULL,
                to_regprocedure('accounting.prepare_initial_ecl_allowance_journal(uuid,uuid,text,text,numeric,date,uuid,uuid,uuid,numeric,text)') IS NOT NULL,
                to_regprocedure('accounting.post_initial_ecl_allowance_journal(uuid,uuid,text,uuid,text,uuid,text,text,date,uuid,uuid,uuid,numeric,numeric,text)') IS NOT NULL
            """
        ).fetchone()
        return all(bool(value) for value in row)

    if migration_name == "0078_harden_ecl_allowance_posting_queue.sql":
        return bool(connection.execute("SELECT to_regclass('accounting.ecl_allowance_posting_summary') IS NOT NULL").fetchone()[0]) and _column_exists(
            connection, schema="accounting", relation="ecl_allowance_posting_summary", column="preparation_blocked_count"
        )

    if migration_name == "0079_add_ecl_remeasurement_writeoff_recovery.sql":
        row = connection.execute(
            """
            SELECT
                to_regclass('accounting.ecl_allowance_remeasurements') IS NOT NULL,
                to_regclass('accounting.ecl_accounting_writeoffs') IS NOT NULL,
                to_regclass('accounting.ecl_post_writeoff_recoveries') IS NOT NULL,
                to_regclass('accounting.ecl_a5_action_queue') IS NOT NULL,
                to_regclass('accounting.ecl_a5_summary') IS NOT NULL,
                to_regprocedure('accounting.post_ecl_allowance_remeasurement(uuid,uuid,text,text,numeric,numeric,date,uuid,uuid,uuid,text)') IS NOT NULL,
                to_regprocedure('accounting.post_ecl_full_writeoff(uuid,uuid,text,bigint,uuid,text,numeric,numeric,numeric,numeric,uuid,uuid,uuid,date,uuid,text)') IS NOT NULL,
                to_regprocedure('accounting.post_ecl_post_writeoff_recovery(bigint,uuid,text,uuid,numeric,date,uuid,uuid,uuid,text)') IS NOT NULL
            """
        ).fetchone()
        return all(bool(value) for value in row)

    raise SystemExit(f"No live ECL migration-state probe is defined for {migration_name}.")


def _select_missing_forward_migrations(connection: psycopg.Connection) -> tuple[Path, ...]:
    installed = [_migration_installed(connection, migration.name) for migration in ecl.MIGRATIONS]
    first_missing = next((index for index, value in enumerate(installed) if not value), len(installed))
    if any(installed[first_missing:]):
        states = ", ".join(
            f"{migration.name}={'installed' if state else 'missing'}"
            for migration, state in zip(ecl.MIGRATIONS, installed, strict=True)
        )
        raise SystemExit("Live ECL migration state is non-contiguous; refusing to guess a migration order: " + states)
    return tuple(ecl.MIGRATIONS[first_missing:])


def _a5_counts(connection: psycopg.Connection) -> tuple[int, int, int]:
    values: list[int] = []
    for relation in A5_AUDIT_RELATIONS:
        if connection.execute("SELECT to_regclass(%s)", (relation,)).fetchone()[0] is None:
            values.append(0)
        else:
            schema, table = relation.split(".", 1)
            value = connection.execute(
                f'SELECT count(*)::bigint FROM "{schema}"."{table}"'
            ).fetchone()[0]
            values.append(int(value))
    return tuple(values)  # type: ignore[return-value]


def _verify_a5_install_only(connection: psycopg.Connection, before: tuple[int, int, int]) -> None:
    if not _migration_installed(connection, A5_MIGRATION.name):
        raise SystemExit("Live ECL A5 verification failed: protected A5 schema/functions are incomplete.")
    after = _a5_counts(connection)
    if after != before:
        raise SystemExit(
            "Live ECL A5 verification failed: installing controls changed A5 financial audit history "
            f"from {before} to {after}."
        )
    summary = connection.execute(
        "SELECT protected_a5_accounting_enabled, automatic_source_posting, remeasurement_posting_count, writeoff_posting_count, post_writeoff_recovery_count FROM accounting.ecl_a5_summary"
    ).fetchone()
    if summary is None or summary[0] is not True or summary[1] is not False:
        raise SystemExit("Live ECL A5 verification failed: A5 safety flags are not explicit.")
    if tuple(int(value) for value in summary[2:]) != after:
        raise SystemExit("Live ECL A5 verification failed: A5 summary does not reconcile to immutable audit counts.")
    print(
        "Live ECL A5 controls verified: "
        f"remeasurements={after[0]}, writeoffs={after[1]}, post_writeoff_recoveries={after[2]}, "
        "protected_a5_accounting_enabled=True, automatic_source_posting=False."
    )


def main() -> int:
    env_paths: list[Path] = []
    database_url_env = "GILBIC_DATABASE_URL"
    args = sys.argv[1:]
    index = 0
    while index < len(args):
        if args[index] == "--env-file" and index + 1 < len(args):
            env_paths.append(Path(args[index + 1]))
            index += 2
            continue
        if args[index] == "--database-url-env" and index + 1 < len(args):
            database_url_env = args[index + 1]
            index += 2
            continue
        index += 1

    for env_path in env_paths:
        ecl._load_env_file(env_path)
    database_url = os.getenv(database_url_env)
    if not database_url:
        raise SystemExit(f"{database_url_env} is not configured")

    with psycopg.connect(database_url, autocommit=True) as connection:
        before_a5 = _a5_counts(connection)
        selected = _select_missing_forward_migrations(connection)

    selected_names = [migration.name for migration in selected]
    skipped_names = [migration.name for migration in ecl.MIGRATIONS if migration not in selected]
    print(f"Live ECL migration plan: already_installed={skipped_names}, apply_forward={selected_names}.")

    all_migrations = ecl.MIGRATIONS
    ecl.MIGRATIONS = selected
    result = ecl.main()
    ecl.MIGRATIONS = all_migrations

    with psycopg.connect(database_url, autocommit=True) as connection:
        _verify_a5_install_only(connection, before_a5)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
