from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql

import run_stage5d17_disposable_postgres_validation as disposable


ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_PREFIX = "spina_borrower_schedule_"
UPGRADE_BOOTSTRAP_THROUGH = 109
CURRENT_BOOTSTRAP_THROUGH = 111
TEST_ROOT = ROOT / "gilbic_backend" / "tests"
SQL_ROOT = ROOT / "gilbic_backend" / "sql"
AREA_MANAGEMENT_MIGRATION = SQL_ROOT / "0113_add_authoritative_area_management.sql"
UPGRADE_TESTS = (
    TEST_ROOT / "test_borrower_schedule_adjustment_upgrade_postgres.py",
)
CURRENT_INTEGRATION_TESTS = (
    TEST_ROOT / "test_borrower_schedule_adjustment_repository_postgres.py",
    TEST_ROOT / "test_borrower_schedule_finalization_postgres.py",
    TEST_ROOT / "test_collector_route_api.py",
    TEST_ROOT / "test_collector_schedule_repository.py",
    TEST_ROOT / "test_client_loan_api.py",
    TEST_ROOT / "test_client_operational_schedule_repository_postgres.py",
    TEST_ROOT / "test_voluntary_extra_receipt_application.py",
    TEST_ROOT / "test_regular_borrower_catchup_postgres.py",
    TEST_ROOT / "test_seven_by_seven_schedule_allocation.py",
    TEST_ROOT / "test_seven_by_seven_borrower_catchup_postgres.py",
)


def _configure_shared_safety_helpers() -> None:
    disposable.TEST_DATABASE_PREFIX = TEST_DATABASE_PREFIX
    disposable.BOOTSTRAP_THROUGH = UPGRADE_BOOTSTRAP_THROUGH


def _test_env(test_database_url: str) -> dict[str, str]:
    env = os.environ.copy()
    for key in disposable.ENDPOINT_ENV_KEYS:
        env.pop(key, None)
    env["GILBIC_DATABASE_URL"] = test_database_url
    env["GILBIC_TEST_DATABASE_URL"] = test_database_url
    python_paths = [
        str(ROOT),
        str(ROOT / "gilbic_backend" / "src"),
        str(ROOT / "spina_backend_mobile" / "src"),
    ]
    existing_python_path = env.get("PYTHONPATH", "").strip()
    if existing_python_path:
        python_paths.append(existing_python_path)
    env["PYTHONPATH"] = os.pathsep.join(python_paths)
    return env


def _run_tests(test_database_url: str, tests: tuple[Path, ...]) -> int:
    missing = [str(path) for path in tests if not path.is_file()]
    if missing:
        raise SystemExit(
            "Borrower-schedule validation refused: required integration test file is missing: "
            + ", ".join(missing)
        )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            *(str(path) for path in tests),
        ],
        env=_test_env(test_database_url),
        check=False,
    )
    return int(completed.returncode)


def _create_disposable_database(
    admin_url: str,
    base_params: dict[str, str],
    created_databases: list[str],
) -> tuple[str, str]:
    database_name = f"{TEST_DATABASE_PREFIX}{uuid4().hex}"
    database_url = disposable._conninfo_for_database(base_params, database_name)
    with psycopg.connect(admin_url, autocommit=True) as admin:
        if disposable._database_exists(admin, database_name):
            raise SystemExit(
                "Borrower-schedule validation refused: generated database already exists."
            )
        # Record cleanup responsibility before CREATE DATABASE. If PostgreSQL creates
        # the database but the client receives an ambiguous result, finally still
        # performs the idempotent drop.
        created_databases.append(database_name)
        admin.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                sql.Identifier(database_name)
            )
        )
    return database_name, database_url


def _bootstrap_upgrade_schema(test_database_url: str) -> None:
    previous_bootstrap_through = disposable.BOOTSTRAP_THROUGH
    try:
        disposable.BOOTSTRAP_THROUGH = UPGRADE_BOOTSTRAP_THROUGH
        disposable._install_supabase_auth_prerequisite(test_database_url)
        disposable._bootstrap_database(test_database_url)
    finally:
        disposable.BOOTSTRAP_THROUGH = previous_bootstrap_through


def _bootstrap_current_schema(test_database_url: str) -> None:
    if not AREA_MANAGEMENT_MIGRATION.is_file():
        raise SystemExit(
            "Borrower-schedule validation refused: Area Management migration is missing: "
            + str(AREA_MANAGEMENT_MIGRATION)
        )

    previous_bootstrap_through = disposable.BOOTSTRAP_THROUGH
    try:
        disposable.BOOTSTRAP_THROUGH = CURRENT_BOOTSTRAP_THROUGH
        disposable._install_supabase_auth_prerequisite(test_database_url)
        disposable._bootstrap_database(test_database_url)
    finally:
        disposable.BOOTSTRAP_THROUGH = previous_bootstrap_through

    with psycopg.connect(test_database_url, autocommit=True) as connection:
        connection.execute(AREA_MANAGEMENT_MIGRATION.read_text(encoding="utf-8"))

        event_date_installed = connection.execute(
            """
            select count(*)
            from information_schema.columns
            where table_schema = 'lending'
              and table_name = 'loan_schedule_adjustments'
              and column_name = 'event_date'
            """
        ).fetchone()[0]
        if event_date_installed == 0:
            raise RuntimeError(
                "Borrower-schedule current-schema database is missing the 0110 event_date column."
            )

        area_transfer_table = connection.execute(
            "select to_regclass('lending.client_area_pending_transfers')"
        ).fetchone()[0]
        if area_transfer_table is None:
            raise RuntimeError(
                "Borrower-schedule current-schema database is missing Area transfer authority."
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Use two isolated loopback-only disposable PostgreSQL databases: one to replay "
            "SPINA through both 0109 migrations and prove the historical 0109-to-0110 "
            "upgrade, and a second clean database bootstrapped through the current shared "
            "Plan 1 schema plus Area Management migration 0113 before exercising current "
            "borrower shortfall/catch-up persistence, elapsed-date finalization, Collector "
            "route refresh behavior, authoritative Collector and Client schedule reads, "
            "Regular protected/transactional catch-up allocation, and 7x7 catch-up "
            "planning/posting."
        )
    )
    parser.add_argument("--env-file", action="append", type=Path, default=[])
    parser.add_argument("--database-url-env", default="GILBIC_DATABASE_URL")
    parser.add_argument("--cleanup-stale-only", action="store_true")
    args = parser.parse_args()

    _configure_shared_safety_helpers()
    for env_path in args.env_file:
        disposable._load_env_file(env_path)

    database_url = os.getenv(args.database_url_env)
    if not database_url:
        raise SystemExit(f"{args.database_url_env} is not configured")

    base_params = disposable._safe_local_connection_params(database_url)
    disposable._clear_endpoint_environment()
    configured_database = base_params["dbname"]
    if configured_database.startswith(TEST_DATABASE_PREFIX):
        raise SystemExit(
            "Borrower-schedule validation refused: configured database uses the reserved disposable prefix."
        )

    admin_url = disposable._conninfo_for_database(base_params, "postgres")
    if args.cleanup_stale_only:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            dropped = disposable._drop_stale_disposable_databases(admin)
        print(f"Borrower-schedule disposable PostgreSQL janitor passed: dropped={dropped}.")
        return 0

    created_databases: list[str] = []
    primary_error: BaseException | None = None
    try:
        upgrade_database, upgrade_url = _create_disposable_database(
            admin_url,
            base_params,
            created_databases,
        )
        print(f"Borrower-schedule upgrade proof database: {upgrade_database}")
        _bootstrap_upgrade_schema(upgrade_url)

        upgrade_result = _run_tests(upgrade_url, UPGRADE_TESTS)
        if upgrade_result != 0:
            raise SystemExit(
                "Borrower-schedule disposable PostgreSQL validation failed: "
                f"0109-to-0110 upgrade tests exited with code {upgrade_result}."
            )

        current_database, current_url = _create_disposable_database(
            admin_url,
            base_params,
            created_databases,
        )
        print(f"Borrower-schedule current-schema database: {current_database}")
        _bootstrap_current_schema(current_url)

        integration_result = _run_tests(current_url, CURRENT_INTEGRATION_TESTS)
        if integration_result != 0:
            raise SystemExit(
                "Borrower-schedule disposable PostgreSQL validation failed: "
                f"current-schema integration tests exited with code {integration_result}."
            )
        print(
            "Borrower-schedule disposable PostgreSQL validation passed: an isolated 0109 "
            "database proved the 0110 upgrade and immutable evidence preservation, while a "
            "separate clean current-schema database proved borrower schedule repository "
            "integration, elapsed-date finalization, Collector route refresh, authoritative "
            "Collector/Client schedule reads, Regular protected/transactional catch-up "
            "allocation, and 7x7 catch-up planning/posting under Plan 1 Area authority."
        )
        return 0
    except psycopg.Error as error:
        primary_error = error
        raise SystemExit(
            "Borrower-schedule disposable PostgreSQL validation failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error
    except BaseException as error:
        primary_error = error
        raise
    finally:
        cleanup_failures: list[str] = []
        for database_name in reversed(created_databases):
            try:
                with psycopg.connect(admin_url, autocommit=True) as admin:
                    disposable._drop_database(admin, database_name)
            except (psycopg.Error, SystemExit) as cleanup_error:
                message = (
                    "Borrower-schedule disposable PostgreSQL cleanup failed for "
                    f"{database_name}: "
                    + str(cleanup_error).split("CONTEXT:", 1)[0].strip()
                )
                print(message, file=sys.stderr)
                cleanup_failures.append(message)
        if cleanup_failures and primary_error is None:
            raise SystemExit(cleanup_failures[0])


if __name__ == "__main__":
    raise SystemExit(main())
