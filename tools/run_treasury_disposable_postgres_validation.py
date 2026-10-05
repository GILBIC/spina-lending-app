"""Verify manual treasury controls in a newly created loopback-only database."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import run_stage5d17_disposable_postgres_validation as disposable
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
DATABASE_PREFIX = "spina_treasury_validation_"


def main() -> int:
    if os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") != "1":
        raise SystemExit(
            "Set SPINA_ALLOW_DISPOSABLE_DATABASE=1 for this synthetic verifier."
        )
    configured = os.getenv("TREASURY_DATABASE_URL", "")
    params = disposable._safe_local_connection_params(configured)
    if params["dbname"].startswith(DATABASE_PREFIX):
        raise SystemExit("The configured database cannot use the reserved test prefix.")
    disposable._clear_endpoint_environment()
    disposable.TEST_DATABASE_PREFIX = DATABASE_PREFIX
    disposable.BOOTSTRAP_THROUGH = 140
    name = DATABASE_PREFIX + uuid4().hex[:24]
    admin_url = disposable._conninfo_for_database(params, "postgres")
    test_url = disposable._conninfo_for_database(params, name)
    tests = sorted(
        [
            *(ROOT / "gilbic_backend" / "tests").glob("test_treasury*.py"),
            *(ROOT / "gilbic_backend" / "tests").glob("test_collector_surplus*.py"),
        ]
    )
    if len(tests) < 9:
        raise SystemExit("Required treasury acceptance files are missing.")
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
        env = os.environ.copy()
        env.update(GILBIC_DATABASE_URL=test_url, GILBIC_TEST_DATABASE_URL=test_url)
        env["PYTHONPATH"] = os.pathsep.join(
            str(ROOT / part)
            for part in (
                "gilbic_backend/src",
                "spina_backend_mobile/src",
                "gilbic_backend/tests",
                "tools",
                ".",
            )
        )
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", *(str(path) for path in tests)],
            cwd=ROOT,
            env=env,
            check=False,
            timeout=900,
        )
        if result.returncode:
            raise SystemExit(
                "Treasury disposable acceptance failed; inspect the synthetic test report."
            )
        print("Treasury disposable validation passed on fresh schema 0140.")
        return 0
    except psycopg.Error:
        raise SystemExit("Treasury disposable database validation failed.") from None
    finally:
        if created:
            with psycopg.connect(admin_url, autocommit=True) as admin:
                disposable._drop_database(admin, name)


if __name__ == "__main__":
    raise SystemExit(main())
