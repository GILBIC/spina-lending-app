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


TEST_DATABASE_PREFIX = "spina_ecl_labels_"
BOOTSTRAP_THROUGH = 69
TEST_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "tests"
# Run the original label proof and the focused chronology regression together
# against one freshly bootstrapped local PostgreSQL database.
INTEGRATION_TESTS = (
    TEST_ROOT / "test_ecl_credit_risk_labels_postgres.py",
    TEST_ROOT / "test_ecl_cash_recovery_chronology_postgres.py",
)


def _configure_shared_safety_helpers() -> None:
    disposable.TEST_DATABASE_PREFIX = TEST_DATABASE_PREFIX
    disposable.BOOTSTRAP_THROUGH = BOOTSTRAP_THROUGH


def _run_test(test_database_url: str) -> int:
    missing = [str(path) for path in INTEGRATION_TESTS if not path.is_file()]
    if missing:
        raise SystemExit(
            "ECL credit-risk label validation refused: integration test file is missing: "
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
            "Create a loopback-only disposable PostgreSQL database, replay SPINA migrations "
            "through 0069, then apply and prove protected 0070 ECL credit-risk labels plus "
            "0071 strict cash-recovery chronology hardening."
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
            "ECL credit-risk label validation refused: configured database uses the reserved disposable prefix."
        )

    admin_url = disposable._conninfo_for_database(base_params, "postgres")
    if args.cleanup_stale_only:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            dropped = disposable._drop_stale_disposable_databases(admin)
        print(f"ECL credit-risk label janitor passed: dropped={dropped}.")
        return 0

    test_database = f"{TEST_DATABASE_PREFIX}{uuid4().hex}"
    test_url = disposable._conninfo_for_database(base_params, test_database)
    cleanup_required = False
    primary_error: BaseException | None = None
    try:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            if disposable._database_exists(admin, test_database):
                raise SystemExit(
                    "ECL credit-risk label validation refused: generated database already exists."
                )
            cleanup_required = True
            admin.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                    sql.Identifier(test_database)
                )
            )

        disposable._install_supabase_auth_prerequisite(test_url)
        disposable._bootstrap_database(test_url)
        result = _run_test(test_url)
        if result != 0:
            raise SystemExit(
                "ECL credit-risk label disposable PostgreSQL validation failed: "
                f"integration tests exited with code {result}."
            )
        print(
            "ECL credit-risk label disposable PostgreSQL validation passed: "
            "0070 enforced explicit Management stage/default/write-off-support/recovery/cure "
            "labels and 0071 proved that cash recovery requires an authoritative server "
            "accepted_at strictly after the prior deteriorated review, including same-day "
            "ordering. Quantitative ECL, account 1190 posting, write-off execution and "
            "automatic source posting remained disabled."
        )
        return 0
    except psycopg.Error as error:
        primary_error = error
        raise SystemExit(
            "ECL credit-risk label disposable PostgreSQL validation failed: "
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
                    "ECL credit-risk label disposable PostgreSQL cleanup failed: "
                    + str(cleanup_error).split("CONTEXT:", 1)[0].strip()
                )
                print(message, file=sys.stderr)
                if primary_error is None:
                    raise SystemExit(message) from cleanup_error


if __name__ == "__main__":
    raise SystemExit(main())
