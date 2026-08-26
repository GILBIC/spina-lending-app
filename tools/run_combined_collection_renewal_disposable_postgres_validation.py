from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

import run_stage5d17_disposable_postgres_validation as disposable


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "gilbic_backend" / "src"
MOBILE_SRC = ROOT / "spina_backend_mobile" / "src"
MIGRATION_RUNNER = ROOT / "tools" / "apply_0100_0101_collection_renewal_migrations.py"
TARGET_TESTS = (
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_combined_collection_renewal_workflow_postgres.py",
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_seven_by_seven_verified_advance_postgres.py",
)
# The current combined collection bridge reaches Past Due capture (0103),
# protected future-row Advance allocation basis (0104), and immutable No
# Collection voluntary-completion evidence (0105). The disposable schema must
# match those current code dependencies before exercising production posting.
BOOTSTRAP_THROUGH = 105
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
    for key in disposable.ENDPOINT_ENV_KEYS:
        env.pop(key, None)
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


def _bootstrap_database(test_url: str) -> None:
    # Reuse the proven Stage 5D.17 migration replayer directly against this
    # workflow-owned database. Running the Stage 5D.17 CLI would create its own
    # nested disposable database and leave this database unbootstrapped.
    disposable.BOOTSTRAP_THROUGH = BOOTSTRAP_THROUGH
    disposable._install_supabase_auth_prerequisite(test_url)
    disposable._bootstrap_database(test_url)


def main() -> int:
    for required in (MIGRATION_RUNNER, *TARGET_TESTS):
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

        print(f"Bootstrapping disposable database through migration {BOOTSTRAP_THROUGH:04d}...")
        _bootstrap_database(test_url)

        migration_env = _env(test_url)
        print("Re-running guarded 0100/0101 migrations to prove idempotency...")
        _run([sys.executable, str(MIGRATION_RUNNER)], env=migration_env, timeout=300)
        print("Re-running guarded migrations once more to prove idempotency...")
        _run([sys.executable, str(MIGRATION_RUNNER)], env=migration_env, timeout=300)

        print("Running atomic combined Pay/renewal and verified 7x7 Advance PostgreSQL tests...")
        _run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                *(str(path) for path in TARGET_TESTS),
            ],
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
