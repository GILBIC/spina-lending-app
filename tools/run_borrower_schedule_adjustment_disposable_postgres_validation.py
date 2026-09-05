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
BOOTSTRAP_THROUGH = 109
TEST_ROOT = ROOT / "gilbic_backend" / "tests"
INTEGRATION_TESTS = (
    TEST_ROOT / "test_borrower_schedule_adjustment_upgrade_postgres.py",
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
    disposable.BOOTSTRAP_THROUGH = BOOTSTRAP_THROUGH


def _run_tests(test_database_url: str) -> int:
    missing = [str(path) for path in INTEGRATION_TESTS if not path.is_file()]
    if missing:
        raise SystemExit(
            "Borrower-schedule validation refused: required integration test file is missing: "
            + ", ".join(missing)
        )
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
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            *(str(path) for path in INTEGRATION_TESTS),
        ],
        env=env,
        check=False,
    )
    return int(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a loopback-only disposable PostgreSQL database, replay SPINA migrations "
            "through both 0109 migrations, seed existing audited No Collection history, "
            "apply 0110 only inside the disposable test, and prove the upgrade preserves "
            "immutable schedule-adjustment evidence while exercising borrower shortfall/catch-up persistence, elapsed-date finalization, Collector route refresh behavior, authoritative Collector and Client schedule reads, Regular protected/transactional catch-up allocation, and 7x7 catch-up planning/posting."
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

    test_database = f"{TEST_DATABASE_PREFIX}{uuid4().hex}"
    test_url = disposable._conninfo_for_database(base_params, test_database)
    cleanup_required = False
    primary_error: BaseException | None = None
    try:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            if disposable._database_exists(admin, test_database):
                raise SystemExit(
                    "Borrower-schedule validation refused: generated database already exists."
                )
            cleanup_required = True
            admin.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                    sql.Identifier(test_database)
                )
            )

        disposable._install_supabase_auth_prerequisite(test_url)
        disposable._bootstrap_database(test_url)
        result = _run_tests(test_url)
        if result != 0:
            raise SystemExit(
                "Borrower-schedule disposable PostgreSQL validation failed: "
                f"tests exited with code {result}."
            )
        print(
            "Borrower-schedule disposable PostgreSQL validation passed: schema through 0109 "
            "upgraded with 0110 after existing audited No Collection history was created; "
            "event_date backfill, immutable evidence preservation, borrower schedule "
            "repository integration, elapsed-date finalization, Collector route refresh, "
            "authoritative Collector/Client schedule reads, Regular protected/transactional "
            "catch-up allocation, and 7x7 catch-up planning/posting were proven."
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
        if cleanup_required:
            try:
                with psycopg.connect(admin_url, autocommit=True) as admin:
                    disposable._drop_database(admin, test_database)
            except (psycopg.Error, SystemExit) as cleanup_error:
                message = (
                    "Borrower-schedule disposable PostgreSQL cleanup failed: "
                    + str(cleanup_error).split("CONTEXT:", 1)[0].strip()
                )
                print(message, file=sys.stderr)
                if primary_error is None:
                    raise SystemExit(message) from cleanup_error


if __name__ == "__main__":
    raise SystemExit(main())
