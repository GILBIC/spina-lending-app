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
BACKEND_SRC = ROOT / "gilbic_backend" / "src"
TARGET_TEST = (
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_client_onboarding_promotion_postgres.py"
)
BOOTSTRAP_THROUGH = 112
DISPOSABLE_DATABASE_PREFIX = "spina_onboarding_"


def _test_environment(database_url: str) -> dict[str, str]:
    env = os.environ.copy()
    for key in disposable.ENDPOINT_ENV_KEYS:
        env.pop(key, None)
    env["GILBIC_DATABASE_URL"] = database_url
    env["GILBIC_TEST_DATABASE_URL"] = database_url
    roots = [str(ROOT), str(BACKEND_SRC)]
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(roots + ([existing] if existing else []))
    return env


def validate(base_database_url: str) -> None:
    if os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") != "1":
        raise RuntimeError(
            "Onboarding disposable validation requires SPINA_ALLOW_DISPOSABLE_DATABASE=1."
        )
    if not TARGET_TEST.is_file():
        raise RuntimeError(f"Required onboarding PostgreSQL test is missing: {TARGET_TEST}")

    base_params = disposable._safe_local_connection_params(base_database_url)
    admin_url = disposable._conninfo_for_database(base_params, "postgres")
    database_name = f"{DISPOSABLE_DATABASE_PREFIX}{uuid4().hex[:12]}"
    test_url = disposable._conninfo_for_database(base_params, database_name)
    original_bootstrap_through = disposable.BOOTSTRAP_THROUGH
    created = False

    print(f"Creating onboarding disposable PostgreSQL database: {database_name}")
    try:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                    sql.Identifier(database_name)
                )
            )
        created = True

        disposable.BOOTSTRAP_THROUGH = BOOTSTRAP_THROUGH
        disposable._install_supabase_auth_prerequisite(test_url)
        disposable._bootstrap_database(test_url)

        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", str(TARGET_TEST)],
            cwd=ROOT,
            env=_test_environment(test_url),
            text=True,
            check=False,
            timeout=600,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "Onboarding disposable PostgreSQL validation failed: "
                f"test exited with code {completed.returncode}."
            )
    finally:
        disposable.BOOTSTRAP_THROUGH = original_bootstrap_through
        if created:
            print(f"Dropping onboarding disposable PostgreSQL database: {database_name}")
            with psycopg.connect(admin_url, autocommit=True) as admin:
                disposable._drop_database(admin, database_name)

    print(
        "Onboarding disposable PostgreSQL validation passed: schema through 0112 "
        "was replayed in a fresh loopback database and normal/bypass promotion "
        "proved exactly-one inactive Client identity, idempotency, preserved bypass "
        "requirement states, and zero new Auth-user or loan side effects."
    )
