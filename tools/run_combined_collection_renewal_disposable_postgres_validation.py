from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "gilbic_backend" / "src"
MOBILE_SRC = ROOT / "spina_backend_mobile" / "src"
BOOTSTRAP_SCRIPT = ROOT / "tools" / "run_stage5d17_disposable_postgres_validation.py"
MIGRATION_RUNNER = ROOT / "tools" / "apply_0100_0101_collection_renewal_migrations.py"
TARGET_TEST = (
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_combined_collection_renewal_workflow_postgres.py"
)
BOOTSTRAP_THROUGH = 99
BASE_DATABASE_URL_ENV = "COMBINED_RENEWAL_DATABASE_URL"
DISPOSABLE_DATABASE_PREFIX = "spina_combined_renewal_"


def _base_connection_params() -> dict[str, str]:
    database_url = os.getenv(BASE_DATABASE_URL_ENV)
    if not database_url:
        raise SystemExit(
            f"{BASE_DATABASE_URL_ENV} is not configured; refusing to guess PostgreSQL credentials."
        )

    params = conninfo_to_dict(database_url)
    host = (params.get("host") or "").strip().lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit(
            "Combined Pay + renewal disposable validation refused: PostgreSQL must be loopback-only."
        )
    return params


def _database_url(base_params: dict[str, str], database_name: str) -> str:
    params = dict(base_params)
    params["dbname"] = database_name
    params["connect_timeout"] = "5"
    return make_conninfo(**params)


def _env(database_url: str) -> dict[str, str]:
    env = os.environ.copy()
    env["GILBIC_DATABASE_URL"] = database_url
    env["GILBIC_TEST_DATABASE_URL"] = database_url
    roots = [str(ROOT), str(BACKEND_SRC), str(MOBILE_SRC)]
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(roots + ([existing] if existing else []))
    return env


def _run(command: list[str], *, env: dict[str, str], timeout: int = 300) -> None:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        check=False,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {completed.returncode}: {' '.join(command)}"
        )


def main() -> int:
    for required in (BOOTSTRAP_SCRIPT, MIGRATION_RUNNER, TARGET_TEST):
        if not required.is_file():
            raise SystemExit(f"Required validation file is missing: {required}")

    base_params = _base_connection_params()
    admin_url = _database_url(base_params, "postgres")
    database_name = f"{DISPOSABLE_DATABASE_PREFIX}{uuid.uuid4().hex[:10]}"
    test_url = _database_url(base_params, database_name)
    print(f"Creating disposable PostgreSQL database: {database_name}")

    created = False
    try:
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(f'CREATE DATABASE "{database_name}"')
        created = True

        bootstrap_env = _env(test_url)
        bootstrap_env["SPINA_STAGE5D17_BOOTSTRAP_ONLY"] = "1"
        bootstrap_env["SPINA_STAGE5D17_BOOTSTRAP_THROUGH"] = str(BOOTSTRAP_THROUGH)
        _run([sys.executable, str(BOOTSTRAP_SCRIPT)], env=bootstrap_env, timeout=600)

        migration_env = _env(test_url)
        print("Applying guarded 0100/0101 migrations...")
        _run([sys.executable, str(MIGRATION_RUNNER)], env=migration_env, timeout=300)
        print("Re-running guarded migrations to prove idempotency...")
        _run([sys.executable, str(MIGRATION_RUNNER)], env=migration_env, timeout=300)

        print("Running atomic combined Pay and renewal policy PostgreSQL tests...")
        _run(
            [sys.executable, "-m", "pytest", "-q", str(TARGET_TEST)],
            env=migration_env,
            timeout=600,
        )
    finally:
        if created:
            print(f"Dropping disposable PostgreSQL database: {database_name}")
            try:
                with psycopg.connect(admin_url, autocommit=True) as connection:
                    connection.execute(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
                        (database_name,),
                    )
                    connection.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
            except Exception as error:
                print(f"Warning: failed to drop disposable database: {error}")

    print("Disposable combined Pay + renewal workflow validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
