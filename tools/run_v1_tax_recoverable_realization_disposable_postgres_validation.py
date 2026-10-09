"""Replay current schema and prove recoverable mutual exclusion on loopback."""

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

TEST_DATABASE_PREFIX = "spina_tax_race_"
BOOTSTRAP_THROUGH = 142
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TEST_PATH = (
    REPOSITORY_ROOT
    / "gilbic_backend/tests/test_v1_tax_recoverable_realization_concurrency_postgres.py"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a fresh loopback-only disposable database, replay migrations "
            "0001-0142, and prove credit/refund exclusion using independent SQL "
            "transactions and observed lock waits. Drop only the generated database."
        )
    )
    parser.add_argument("--database-url-env", default="GILBIC_TEST_DATABASE_URL")
    args = parser.parse_args()
    configured_url = os.getenv(args.database_url_env)
    if not configured_url:
        raise SystemExit(f"{args.database_url_env} is not configured")
    if os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") != "1":
        raise SystemExit("Explicit SPINA_ALLOW_DISPOSABLE_DATABASE=1 is required")
    base_params = disposable._safe_local_connection_params(configured_url)
    if not base_params.get("port") or any(
        base_params.get(key) for key in ("passfile", "options")
    ):
        raise SystemExit(
            "Tax-race validation requires an explicit port and no passfile/options"
        )
    # The test module requires an unambiguous IPv4 loopback endpoint.
    if base_params["hostaddr"] != "127.0.0.1":
        raise SystemExit("Tax-race validation requires IPv4 loopback")
    base_params["host"] = "127.0.0.1"
    disposable._clear_endpoint_environment()
    disposable.TEST_DATABASE_PREFIX = TEST_DATABASE_PREFIX
    disposable.BOOTSTRAP_THROUGH = BOOTSTRAP_THROUGH
    name = TEST_DATABASE_PREFIX + uuid4().hex
    admin_url = disposable._conninfo_for_database(base_params, "postgres")
    test_url = disposable._conninfo_for_database(base_params, name)
    created = False
    try:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                    sql.Identifier(name)
                )
            )
        created = True
        disposable._install_supabase_auth_prerequisite(test_url)
        disposable._bootstrap_database(test_url)
        environment = os.environ.copy()
        environment["SPINA_TAX_RACE_DATABASE_URL"] = test_url
        environment["GILBIC_TEST_DATABASE_URL"] = test_url
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", str(TEST_PATH)],
            cwd=REPOSITORY_ROOT,
            env=environment,
            check=False,
        )
        return int(result.returncode)
    finally:
        if created:
            with psycopg.connect(admin_url, autocommit=True) as admin:
                disposable._drop_database(admin, name)


if __name__ == "__main__":
    raise SystemExit(main())
