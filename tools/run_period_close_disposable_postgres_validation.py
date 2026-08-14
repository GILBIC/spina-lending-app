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


TEST_DATABASE_PREFIX = "spina_period_close_"
BOOTSTRAP_THROUGH = 90
TEST_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "tests"
INTEGRATION_TESTS = (
    TEST_ROOT / "test_period_close_migration.py",
    TEST_ROOT / "test_period_close_postgres.py",
)


def _configure_shared_safety_helpers() -> None:
    disposable.TEST_DATABASE_PREFIX = TEST_DATABASE_PREFIX
    disposable.BOOTSTRAP_THROUGH = BOOTSTRAP_THROUGH


def _run_tests(test_database_url: str) -> int:
    missing = [str(path) for path in INTEGRATION_TESTS if not path.is_file()]
    if missing:
        raise SystemExit(
            "Period-close validation refused: required test file is missing: "
            + ", ".join(missing)
        )
    env = os.environ.copy()
    for key in disposable.ENDPOINT_ENV_KEYS:
        env.pop(key, None)
    env["GILBIC_TEST_DATABASE_URL"] = test_database_url
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *(str(path) for path in INTEGRATION_TESTS)],
        env=env,
        check=False,
    )
    return int(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a loopback-only disposable PostgreSQL database, replay the exact "
            "SPINA schema through A6.2/0090, then apply 0091 only inside rollback-isolated "
            "tests and prove formal Management period close, exact direct transfer of period "
            "profit/loss to 3100 Retained Earnings, review-period freeze, closed-period write "
            "protection, immutable close audit/retry identity and forced-audit atomic rollback. "
            "Automatic source posting and period reopening remain disabled."
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
            "Period-close validation refused: configured database uses the reserved disposable prefix."
        )

    admin_url = disposable._conninfo_for_database(base_params, "postgres")
    if args.cleanup_stale_only:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            dropped = disposable._drop_stale_disposable_databases(admin)
        print(f"Period-close disposable PostgreSQL janitor passed: dropped={dropped}.")
        return 0

    test_database = f"{TEST_DATABASE_PREFIX}{uuid4().hex}"
    test_url = disposable._conninfo_for_database(base_params, test_database)
    cleanup_required = False
    primary_error: BaseException | None = None
    try:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            if disposable._database_exists(admin, test_database):
                raise SystemExit(
                    "Period-close validation refused: generated database already exists."
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
                "Period-close disposable PostgreSQL validation failed: "
                f"tests exited with code {result}."
            )
        print(
            "Period-close disposable PostgreSQL validation passed: current main schema through "
            "A6.2/0090 was replayed into a fresh loopback-only database; 0091 was applied only "
            "inside rollback-isolated tests and proved Management-only open-to-review freeze, "
            "exact income/expense temporary-account closing coordinates, direct transfer of period "
            "profit/loss to existing 3100 Retained Earnings, deterministic preparation/retry, exact "
            "review-period close posting, atomic reviewed-to-closed transition, zero-activity close "
            "without a fake journal, closed-period draft/post/reopen/reversal rejection and forced-"
            "audit atomic rollback. automatic_source_posting=False and period_reopen_enabled=False."
        )
        return 0
    except psycopg.Error as error:
        primary_error = error
        raise SystemExit(
            "Period-close disposable PostgreSQL validation failed: "
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
                    "Period-close disposable PostgreSQL cleanup failed: "
                    + str(cleanup_error).split("CONTEXT:", 1)[0].strip()
                )
                print(message, file=sys.stderr)
                if primary_error is None:
                    raise SystemExit(message) from cleanup_error


if __name__ == "__main__":
    raise SystemExit(main())
