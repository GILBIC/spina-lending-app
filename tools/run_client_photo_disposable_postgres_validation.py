"""Verify private client-photo storage in a fresh, guarded loopback database."""

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("GILBIC_TEST_DATABASE_URL"))
    args = parser.parse_args()
    if os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") != "1" or not args.database_url:
        parser.error(
            "Set SPINA_ALLOW_DISPOSABLE_DATABASE=1 and an explicit loopback test database URL."
        )
    params = disposable._safe_local_connection_params(args.database_url)
    disposable._clear_endpoint_environment()
    name = "spina_onboarding_" + uuid4().hex[:12]
    admin_url = disposable._conninfo_for_database(params, "postgres")
    test_url = disposable._conninfo_for_database(params, name)
    old_through, old_prefix = (
        disposable.BOOTSTRAP_THROUGH,
        disposable.TEST_DATABASE_PREFIX,
    )
    created = False
    try:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                    sql.Identifier(name)
                )
            )
        created = True
        disposable.BOOTSTRAP_THROUGH = 143
        disposable.TEST_DATABASE_PREFIX = "spina_onboarding_"
        disposable._install_supabase_auth_prerequisite(test_url)
        disposable._bootstrap_database(test_url)
        env = dict(os.environ)
        env.update(
            GILBIC_TEST_DATABASE_URL=test_url,
            GILBIC_DATABASE_URL=test_url,
            PYTHONPATH=os.pathsep.join(
                str(ROOT / part)
                for part in (".", "gilbic_backend/src", "spina_backend_mobile/src")
            ),
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "gilbic_backend/tests/test_client_photo.py",
                "gilbic_backend/tests/test_client_photo_api.py",
                "gilbic_backend/tests/test_client_photo_postgres.py",
            ],
            cwd=ROOT,
            env=env,
            check=False,
            timeout=180,
        )
        return result.returncode
    finally:
        try:
            if created:
                with psycopg.connect(admin_url, autocommit=True) as admin:
                    disposable._drop_database(admin, name)
        finally:
            disposable.BOOTSTRAP_THROUGH = old_through
            disposable.TEST_DATABASE_PREFIX = old_prefix


if __name__ == "__main__":
    raise SystemExit(main())
