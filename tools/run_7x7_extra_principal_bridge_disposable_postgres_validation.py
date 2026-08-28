from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import run_stage5d17_disposable_postgres_validation as disposable
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_PREFIX = "spina_7x7_extra_principal_bridge_"
BOOTSTRAP_THROUGH = 108
TEST_ROOT = ROOT / "gilbic_backend" / "tests"
INTEGRATION_TESTS = (
    TEST_ROOT / "test_seven_by_seven_mobile_collection_postgres.py",
    TEST_ROOT / "test_seven_by_seven_extra_principal_persistence_postgres.py",
    TEST_ROOT / "test_seven_by_seven_extra_principal_bridge_postgres.py",
    TEST_ROOT / "test_refund_due_postgres.py",
    TEST_ROOT / "test_seven_by_seven_extra_principal_reversal_requests_postgres.py",
    TEST_ROOT / "test_seven_by_seven_extra_principal_reversal_postgres.py",
    TEST_ROOT / "test_7x7_controlled_collection_reversal_postgres.py",
)


def _configure_shared_safety_helpers() -> None:
    disposable.TEST_DATABASE_PREFIX = TEST_DATABASE_PREFIX
    disposable.BOOTSTRAP_THROUGH = BOOTSTRAP_THROUGH


def _run_tests(test_database_url: str) -> int:
    missing = [str(path) for path in INTEGRATION_TESTS if not path.is_file()]
    if missing:
        raise SystemExit(
            "7x7 Extra Principal bridge validation refused: required integration "
            "test file is missing: " + ", ".join(missing)
        )

    env = os.environ.copy()
    for key in disposable.ENDPOINT_ENV_KEYS:
        env.pop(key, None)
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
            "Create a loopback-only disposable PostgreSQL database, replay SPINA "
            "migrations through 0108, execute the real 7x7 Extra Principal persistence "
            "bridge-schema, Refund Due, and controlled reversal tests, then drop "
            "the disposable database."
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
            "7x7 Extra Principal bridge validation refused: configured database uses "
            "the reserved disposable prefix."
        )

    admin_url = disposable._conninfo_for_database(base_params, "postgres")
    if args.cleanup_stale_only:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            dropped = disposable._drop_stale_disposable_databases(admin)
        print(f"7x7 Extra Principal bridge janitor passed: dropped={dropped}.")
        return 0

    test_database = f"{TEST_DATABASE_PREFIX}{uuid4().hex}"
    test_url = disposable._conninfo_for_database(base_params, test_database)
    cleanup_required = False
    primary_error: BaseException | None = None
    try:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            if disposable._database_exists(admin, test_database):
                raise SystemExit(
                    "7x7 Extra Principal bridge validation refused: generated "
                    "database already exists."
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
                "7x7 Extra Principal bridge disposable PostgreSQL validation failed: "
                f"integration tests exited with code {result}."
            )
        print(
            "7x7 Extra Principal bridge disposable PostgreSQL validation passed: "
            "migration 0108 compiled on the full schema; immutable adjustment evidence "
            "still reconciled; reversal reconstruction, itemized approval, physical-"
            "release evidence, derived lifecycle views, and "
            "direct-write guards were verified. No live database was modified."
        )
        return 0
    except psycopg.Error as error:
        primary_error = error
        raise SystemExit(
            "7x7 Extra Principal bridge disposable PostgreSQL validation failed: "
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
                    "7x7 Extra Principal bridge disposable PostgreSQL cleanup failed: "
                    + str(cleanup_error).split("CONTEXT:", 1)[0].strip()
                )
                print(message, file=sys.stderr)
                if primary_error is None:
                    raise SystemExit(message) from cleanup_error


if __name__ == "__main__":
    raise SystemExit(main())
