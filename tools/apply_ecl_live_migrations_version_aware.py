from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg


TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

import apply_ecl_credit_risk_labels_migration as ecl


# Historical ECL SQL files are forward migrations. Some intentionally CREATE OR
# REPLACE views that later migrations extend, so replaying an older migration
# after a newer one can try to remove newer view columns. Infer only proven
# milestones and apply the missing contiguous forward suffix.


def _column_exists(
    connection: psycopg.Connection,
    *,
    schema: str,
    relation: str,
    column: str,
) -> bool:
    return bool(
        connection.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name = %s
                  AND column_name = %s
            )
            """,
            (schema, relation, column),
        ).fetchone()[0]
    )


def _trigger_exists(
    connection: psycopg.Connection,
    *,
    schema: str,
    relation: str,
    trigger_name: str,
) -> bool:
    return bool(
        connection.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_trigger trigger
                JOIN pg_class relation ON relation.oid = trigger.tgrelid
                JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
                WHERE namespace.nspname = %s
                  AND relation.relname = %s
                  AND trigger.tgname = %s
                  AND NOT trigger.tgisinternal
            )
            """,
            (schema, relation, trigger_name),
        ).fetchone()[0]
    )


def _management_permission_exists(connection: psycopg.Connection, permission: str) -> bool:
    return bool(
        connection.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM core.role_permissions role_permission
                JOIN core.roles role ON role.id = role_permission.role_id
                WHERE role.code = 'management'
                  AND role_permission.permission_code = %s
            )
            """,
            (permission,),
        ).fetchone()[0]
    )


def _migration_installed(connection: psycopg.Connection, migration_name: str) -> bool:
    if migration_name == "0070_add_ecl_credit_risk_labels.sql":
        row = connection.execute(
            """
            SELECT
                to_regclass('accounting.ecl_credit_risk_label_reviews') IS NOT NULL,
                to_regclass('accounting.ecl_credit_risk_label_policy_v1') IS NOT NULL,
                to_regprocedure(
                    'accounting.review_ecl_credit_risk_labels(uuid,text,boolean,text,text,text,text,text,boolean,boolean,text,text,text,text,uuid,uuid)'
                ) IS NOT NULL
            """
        ).fetchone()
        return all(bool(value) for value in row)

    if migration_name == "0071_harden_ecl_cash_recovery_chronology.sql":
        return bool(
            connection.execute(
                "SELECT to_regprocedure('accounting.guard_ecl_cash_recovery_chronology()') IS NOT NULL"
            ).fetchone()[0]
        ) and _trigger_exists(
            connection,
            schema="accounting",
            relation="ecl_credit_risk_label_reviews",
            trigger_name="ecl_cash_recovery_chronology_guard",
        )

    if migration_name == "0072_add_ecl_quantitative_input_readiness.sql":
        # 0074 renames the exact 0072 gate to *_a1_base before layering A2.
        return bool(
            connection.execute(
                """
                SELECT
                    to_regclass('accounting.ecl_quantitative_input_readiness_a1_base') IS NOT NULL
                    OR (
                        to_regclass('accounting.ecl_quantitative_input_readiness') IS NOT NULL
                        AND to_regclass('accounting.ecl_forward_looking_evidence_readiness') IS NULL
                    )
                """
            ).fetchone()[0]
        )

    if migration_name == "0073_add_ecl_forward_looking_evidence_governance.sql":
        return bool(
            connection.execute(
                """
                SELECT
                    to_regclass('accounting.ecl_forward_looking_evidence') IS NOT NULL
                    AND to_regclass('accounting.ecl_forward_looking_evidence_revocations') IS NOT NULL
                    AND to_regprocedure(
                        'accounting.record_ecl_forward_looking_evidence(text,text,text,date,date,date,date,timestamp with time zone,date,text,uuid,uuid)'
                    ) IS NOT NULL
                """
            ).fetchone()[0]
        )

    if migration_name == "0074_integrate_ecl_forward_looking_readiness.sql":
        return bool(
            connection.execute(
                """
                SELECT
                    to_regclass('accounting.ecl_quantitative_input_readiness_a1_base') IS NOT NULL
                    AND to_regclass('accounting.ecl_forward_looking_evidence_readiness') IS NOT NULL
                """
            ).fetchone()[0]
        )

    if migration_name == "0075_add_read_only_quantitative_ecl_measurement.sql":
        return bool(
            connection.execute(
                """
                SELECT
                    to_regclass('accounting.ecl_quantitative_measurements') IS NOT NULL
                    AND to_regclass('accounting.ecl_quantitative_measurement_queue') IS NOT NULL
                    AND to_regprocedure(
                        'accounting.record_read_only_quantitative_ecl_measurement(uuid,date,jsonb,text,uuid)'
                    ) IS NOT NULL
                """
            ).fetchone()[0]
        )

    if migration_name == "0076_harden_read_only_quantitative_ecl_measurement.sql":
        return bool(
            connection.execute(
                """
                SELECT to_regprocedure(
                    'accounting.record_read_only_quantitative_ecl_measurement_v1_impl(uuid,date,jsonb,text,uuid)'
                ) IS NOT NULL
                """
            ).fetchone()[0]
        ) and _column_exists(
            connection,
            schema="accounting",
            relation="ecl_quantitative_measurement_queue",
            column="measurement_forward_evidence_current",
        )

    if migration_name == "0077_add_protected_ecl_allowance_posting.sql":
        row = connection.execute(
            """
            SELECT
                to_regclass('accounting.ecl_allowance_draft_preparations') IS NOT NULL,
                to_regclass('accounting.ecl_allowance_postings') IS NOT NULL,
                to_regclass('accounting.ecl_allowance_posting_lines') IS NOT NULL,
                to_regprocedure(
                    'accounting.prepare_initial_ecl_allowance_journal(uuid,uuid,text,text,numeric,date,uuid,uuid,uuid,numeric,text)'
                ) IS NOT NULL,
                to_regprocedure(
                    'accounting.post_initial_ecl_allowance_journal(uuid,uuid,text,uuid,text,uuid,text,text,date,uuid,uuid,uuid,numeric,numeric,text)'
                ) IS NOT NULL
            """
        ).fetchone()
        return all(bool(value) for value in row)

    if migration_name == "0078_harden_ecl_allowance_posting_queue.sql":
        return bool(
            connection.execute(
                "SELECT to_regclass('accounting.ecl_allowance_posting_summary') IS NOT NULL"
            ).fetchone()[0]
        ) and _column_exists(
            connection,
            schema="accounting",
            relation="ecl_allowance_posting_summary",
            column="preparation_blocked_count",
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
                to_regprocedure(
                    'accounting.post_ecl_allowance_remeasurement(uuid,uuid,text,text,numeric,numeric,date,uuid,uuid,uuid,text)'
                ) IS NOT NULL,
                to_regprocedure(
                    'accounting.post_ecl_full_writeoff(uuid,uuid,text,bigint,uuid,text,numeric,numeric,numeric,numeric,uuid,uuid,uuid,date,uuid,text)'
                ) IS NOT NULL,
                to_regprocedure(
                    'accounting.post_ecl_post_writeoff_recovery(bigint,uuid,text,uuid,numeric,date,uuid,uuid,uuid,text)'
                ) IS NOT NULL
            """
        ).fetchone()
        return all(bool(value) for value in row)

    if migration_name == "0080_harden_ecl_post_writeoff_boundaries.sql":
        row = connection.execute(
            """
            SELECT
                to_regclass('accounting.ecl_post_writeoff_recovery_review_provenance') IS NOT NULL,
                to_regprocedure(
                    'accounting.review_ecl_post_writeoff_recovery(uuid,uuid,text,uuid,numeric,text,text,text)'
                ) IS NOT NULL,
                to_regprocedure('accounting.guard_ecl_post_writeoff_loan_insert()') IS NOT NULL,
                to_regprocedure('accounting.guard_ecl_post_writeoff_collection_accounting()') IS NOT NULL
            """
        ).fetchone()
        if not all(bool(value) for value in row):
            return False
        if not _management_permission_exists(connection, "accounting.ecl.recovery.review"):
            return False
        required_triggers = (
            ("ecl_quantitative_measurements", "accounting_ecl_post_writeoff_measurement_guard"),
            ("ecl_allowance_draft_preparations", "accounting_ecl_post_writeoff_allowance_preparation_guard"),
            ("ecl_allowance_postings", "accounting_ecl_post_writeoff_allowance_posting_guard"),
            ("ecl_allowance_remeasurements", "accounting_ecl_post_writeoff_remeasurement_guard"),
            ("regular_journal_posting_entries", "accounting_ecl_post_writeoff_regular_collection_guard"),
            ("seven_by_seven_journal_postings", "accounting_ecl_post_writeoff_7x7_collection_guard"),
            (
                "ecl_post_writeoff_recovery_review_provenance",
                "accounting_ecl_post_writeoff_recovery_review_audit_guard",
            ),
        )
        return all(
            _trigger_exists(
                connection,
                schema="accounting",
                relation=relation,
                trigger_name=trigger,
            )
            for relation, trigger in required_triggers
        )

    raise SystemExit(f"No live ECL migration-state probe is defined for {migration_name}.")


def _select_missing_forward_migrations(
    connection: psycopg.Connection,
) -> tuple[Path, ...]:
    installed = [
        _migration_installed(connection, migration.name)
        for migration in ecl.MIGRATIONS
    ]

    first_missing = next(
        (index for index, value in enumerate(installed) if not value),
        len(installed),
    )
    if any(installed[first_missing:]):
        states = ", ".join(
            f"{migration.name}={'installed' if state else 'missing'}"
            for migration, state in zip(ecl.MIGRATIONS, installed, strict=True)
        )
        raise SystemExit(
            "Live ECL migration state is non-contiguous; refusing to guess a migration order: "
            + states
        )

    return tuple(ecl.MIGRATIONS[first_missing:])


def main() -> int:
    # Keep the established CLI contract. Load env files early only so the
    # version-aware planner can inspect the same database that the protected
    # verifier will later install/verify.
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
        selected = _select_missing_forward_migrations(connection)

    selected_names = [migration.name for migration in selected]
    skipped_names = [
        migration.name for migration in ecl.MIGRATIONS if migration not in selected
    ]
    print(
        "Live ECL migration plan: "
        f"already_installed={skipped_names}, apply_forward={selected_names}."
    )

    ecl.MIGRATIONS = selected
    return ecl.main()


if __name__ == "__main__":
    raise SystemExit(main())
