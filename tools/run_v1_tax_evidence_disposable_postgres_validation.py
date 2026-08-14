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


TEST_DATABASE_PREFIX = "spina_v1_tax_"
BOOTSTRAP_THROUGH = 81
TEST_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "tests"
INTEGRATION_TESTS = (
    TEST_ROOT / "test_v1_tax_adjustment_migration.py",
    TEST_ROOT / "test_v1_tax_adjustment_api_contract.py",
    TEST_ROOT / "test_v1_tax_adjustment_postgres.py",
    TEST_ROOT / "test_v1_tax_evidence_migration.py",
    TEST_ROOT / "test_v1_tax_evidence_api_contract.py",
    TEST_ROOT / "test_v1_tax_evidence_postgres.py",
    TEST_ROOT / "test_v1_tax_liability_migration.py",
    TEST_ROOT / "test_v1_tax_liability_api_contract.py",
    TEST_ROOT / "test_v1_tax_liability_postgres.py",
    TEST_ROOT / "test_v1_tax_settlement_migration.py",
    TEST_ROOT / "test_v1_tax_settlement_api_contract.py",
    TEST_ROOT / "test_v1_tax_settlement_postgres.py",
)


def _configure_shared_safety_helpers() -> None:
    disposable.TEST_DATABASE_PREFIX = TEST_DATABASE_PREFIX
    disposable.BOOTSTRAP_THROUGH = BOOTSTRAP_THROUGH


def _run_tests(test_database_url: str) -> int:
    missing = [str(path) for path in INTEGRATION_TESTS if not path.is_file()]
    if missing:
        raise SystemExit(
            "V1 tax validation refused: required test file is missing: "
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
            "SPINA schema through A6.1/0081, then apply A6.2 migrations 0082 through 0086 "
            "inside rollback-isolated tests and prove immutable evidence-backed V1 tax "
            "readiness, protected tax-liability recognition, retained return/payment evidence, "
            "exact settlement, and the protected pre-close tax correction/reversal core. "
            "Additional-tax amendment payment and later tax-refund/credit realization remain "
            "separate retained-evidence controls; automatic source posting remains disabled."
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
            "V1 tax validation refused: configured database uses the reserved disposable prefix."
        )

    admin_url = disposable._conninfo_for_database(base_params, "postgres")
    if args.cleanup_stale_only:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            dropped = disposable._drop_stale_disposable_databases(admin)
        print(f"V1 tax disposable PostgreSQL janitor passed: dropped={dropped}.")
        return 0

    test_database = f"{TEST_DATABASE_PREFIX}{uuid4().hex}"
    test_url = disposable._conninfo_for_database(base_params, test_database)
    cleanup_required = False
    primary_error: BaseException | None = None
    try:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            if disposable._database_exists(admin, test_database):
                raise SystemExit(
                    "V1 tax validation refused: generated database already exists."
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
                "V1 tax disposable PostgreSQL validation failed: "
                f"tests exited with code {result}."
            )
        print(
            "V1 tax disposable PostgreSQL validation passed: current schema through 0081 "
            "upgraded with A6.2 migrations 0082-0086 inside rollback-isolated tests; immutable "
            "Management-approved rule/transaction evidence, exact DST coordinates, independent "
            "percentage-tax allocation distinct from PFRS/EIR, dedicated 5300/5310 liability "
            "recognition against 2100 Tax Payables, retained exact return composition, immutable "
            "BIR return/payment evidence, approved 1010/1030 payment-cash coordinates, exact Dr "
            "2100 Tax Payables / Cr approved cash-bank settlement, protected unpaid stale-liability "
            "full reversal, protected settled-tax decrease recognition through 1130 Tax Recoverable, "
            "strict Management API/repository exposure, open-original-period/account/source "
            "revalidation, replacement-evidence duplicate-liability protection, retry integrity, "
            "manual bypass/reversal rejection and forced-audit atomic rollback were proven. "
            "Additional-tax amendment payment and tax-refund/credit realization remain explicit "
            "later evidence controls; automatic source posting remains disabled."
        )
        return 0
    except psycopg.Error as error:
        primary_error = error
        raise SystemExit(
            "V1 tax disposable PostgreSQL validation failed: "
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
                    "V1 tax disposable PostgreSQL cleanup failed: "
                    + str(cleanup_error).split("CONTEXT:", 1)[0].strip()
                )
                print(message, file=sys.stderr)
                if primary_error is None:
                    raise SystemExit(message) from cleanup_error


if __name__ == "__main__":
    raise SystemExit(main())
