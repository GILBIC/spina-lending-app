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
# Reuse one dedicated ECL disposable PostgreSQL workflow for the whole protected
# label/readiness/evidence/measurement/allowance/A5 chain and live upgrade planner;
# do not duplicate CI.
INTEGRATION_TESTS = (
    TEST_ROOT / "test_ecl_credit_risk_labels_postgres.py",
    TEST_ROOT / "test_ecl_cash_recovery_chronology_postgres.py",
    TEST_ROOT / "test_ecl_quantitative_input_readiness_postgres.py",
    TEST_ROOT / "test_ecl_forward_looking_evidence_postgres.py",
    TEST_ROOT / "test_ecl_read_only_measurement_postgres.py",
    TEST_ROOT / "test_ecl_allowance_posting_postgres.py",
    TEST_ROOT / "test_ecl_a5_migration.py",
    TEST_ROOT / "test_ecl_a5_remeasurement_postgres.py",
    TEST_ROOT / "test_ecl_a5_writeoff_recovery_postgres.py",
    TEST_ROOT / "test_ecl_live_migration_plan_postgres.py",
)


def _configure_shared_safety_helpers() -> None:
    disposable.TEST_DATABASE_PREFIX = TEST_DATABASE_PREFIX
    disposable.BOOTSTRAP_THROUGH = BOOTSTRAP_THROUGH


def _run_test(test_database_url: str) -> int:
    missing = [str(path) for path in INTEGRATION_TESTS if not path.is_file()]
    if missing:
        raise SystemExit(
            "ECL validation refused: integration test file is missing: "
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
            "through 0069, then prove protected 0070 labels, 0071 recovery chronology, "
            "0072 quantitative-input blockers, 0073/0074 forward-looking evidence governance, "
            "0075/0076 read-only quantitative ECL measurement/hardening, 0077/0078 "
            "explicit protected initial account-1190 allowance preparation/posting, 0079 "
            "controlled A5 remeasurement/write-off/post-write-off recovery, 0080 fail-closed "
            "post-write-off boundaries, and the version-aware live upgrade plan."
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
            "ECL validation refused: configured database uses the reserved disposable prefix."
        )

    admin_url = disposable._conninfo_for_database(base_params, "postgres")
    if args.cleanup_stale_only:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            dropped = disposable._drop_stale_disposable_databases(admin)
        print(f"ECL disposable PostgreSQL janitor passed: dropped={dropped}.")
        return 0

    test_database = f"{TEST_DATABASE_PREFIX}{uuid4().hex}"
    test_url = disposable._conninfo_for_database(base_params, test_database)
    cleanup_required = False
    primary_error: BaseException | None = None
    try:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            if disposable._database_exists(admin, test_database):
                raise SystemExit("ECL validation refused: generated database already exists.")
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
                "ECL disposable PostgreSQL validation failed: "
                f"integration tests exited with code {result}."
            )
        print(
            "ECL disposable PostgreSQL validation passed through A5 write-off/recovery: "
            "0070–0076 preserved protected labels/readiness/evidence/read-only measurement; "
            "0077/0078 preserved explicit Management-confirmed initial allowance posting; "
            "0079 real PostgreSQL proof covered allowance increase/decrease/full reversal, "
            "full write-off and exact same-loan post-write-off cash recovery with exact retry "
            "identity and forced-audit atomic rollback; 0080 proved fail-closed boundaries "
            "against new measurement/allowance activity and normal Regular/7x7 accounting "
            "after derecognition. Automatic source posting remained disabled."
        )
        return 0
    except psycopg.Error as error:
        primary_error = error
        raise SystemExit(
            "ECL disposable PostgreSQL validation failed: "
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
                    "ECL disposable PostgreSQL cleanup failed: "
                    + str(cleanup_error).split("CONTEXT:", 1)[0].strip()
                )
                print(message, file=sys.stderr)
                if primary_error is None:
                    raise SystemExit(message) from cleanup_error


if __name__ == "__main__":
    raise SystemExit(main())
