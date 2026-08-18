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


TEST_DATABASE_PREFIX = "spina_delegated_area_"
BOOTSTRAP_THROUGH = 96
ROOT = Path(__file__).resolve().parents[1]
APPLY_TOOL = ROOT / "tools" / "apply_0097_0098_delegated_area_migrations.py"
INTEGRATION_TEST = (
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_delegated_area_access_postgres.py"
)


def _configure_shared_safety_helpers() -> None:
    disposable.TEST_DATABASE_PREFIX = TEST_DATABASE_PREFIX
    disposable.BOOTSTRAP_THROUGH = BOOTSTRAP_THROUGH


def _subprocess_env(test_database_url: str) -> dict[str, str]:
    env = os.environ.copy()
    for key in disposable.ENDPOINT_ENV_KEYS:
        env.pop(key, None)
    env["GILBIC_DATABASE_URL"] = test_database_url
    env["GILBIC_TEST_DATABASE_URL"] = test_database_url
    return env


def _run_live_apply_tool(test_database_url: str) -> int:
    if not APPLY_TOOL.is_file():
        raise SystemExit(
            "Delegated-area validation refused: guarded live migration tool is missing."
        )
    completed = subprocess.run(
        [sys.executable, str(APPLY_TOOL)],
        env=_subprocess_env(test_database_url),
        check=False,
    )
    return int(completed.returncode)


def _run_test(test_database_url: str) -> int:
    if not INTEGRATION_TEST.is_file():
        raise SystemExit(
            "Delegated-area validation refused: integration test file is missing."
        )
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(INTEGRATION_TEST)],
        env=_subprocess_env(test_database_url),
        check=False,
    )
    return int(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a loopback-only disposable PostgreSQL database, replay SPINA through "
            "0096, install 0097/0098 through the same guarded live migration runner used "
            "for acceptance, prove hierarchy/grant safety and idempotent verification, "
            "then delete the disposable database."
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
            "Delegated-area validation refused: configured database uses the reserved disposable prefix."
        )

    admin_url = disposable._conninfo_for_database(base_params, "postgres")
    if args.cleanup_stale_only:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            dropped = disposable._drop_stale_disposable_databases(admin)
        print(f"Delegated-area disposable PostgreSQL janitor passed: dropped={dropped}.")
        return 0

    test_database = f"{TEST_DATABASE_PREFIX}{uuid4().hex}"
    test_url = disposable._conninfo_for_database(base_params, test_database)
    cleanup_required = False
    primary_error: BaseException | None = None
    try:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            if disposable._database_exists(admin, test_database):
                raise SystemExit(
                    "Delegated-area validation refused: generated database already exists."
                )
            cleanup_required = True
            admin.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                    sql.Identifier(test_database)
                )
            )

        disposable._install_supabase_auth_prerequisite(test_url)
        disposable._bootstrap_database(test_url)

        first_apply = _run_live_apply_tool(test_url)
        if first_apply != 0:
            raise SystemExit(
                "Delegated-area disposable PostgreSQL validation failed: guarded 0097/0098 "
                f"installation exited with code {first_apply}."
            )

        # Exact retry must be verification-only and succeed without changing evidence.
        second_apply = _run_live_apply_tool(test_url)
        if second_apply != 0:
            raise SystemExit(
                "Delegated-area disposable PostgreSQL validation failed: guarded 0097/0098 "
                f"idempotent verification exited with code {second_apply}."
            )

        result = _run_test(test_url)
        if result != 0:
            raise SystemExit(
                "Delegated-area disposable PostgreSQL validation failed: "
                f"integration test exited with code {result}."
            )
        print(
            "Delegated-area disposable PostgreSQL validation passed: the exact schema "
            "through 0096 was replayed first, the guarded acceptance runner installed "
            "0097/0098 and then verified an exact retry without changes, and the resulting "
            "schema proved Collector permissions, normalized hierarchical path boundaries, "
            "most-specific ownership, equal-specificity ambiguity fail-closed behavior, "
            "temporary grant ownership revalidation, nested override invalidation, expiry, "
            "revocation, immutable request/grant/scope/event evidence, preservation of "
            "existing collection history, and hierarchical future assignment capture."
        )
        return 0
    except psycopg.Error as error:
        primary_error = error
        raise SystemExit(
            "Delegated-area disposable PostgreSQL validation failed: "
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
                    "Delegated-area disposable PostgreSQL cleanup failed: "
                    + str(cleanup_error).split("CONTEXT:", 1)[0].strip()
                )
                print(message, file=sys.stderr)
                if primary_error is None:
                    raise SystemExit(message) from cleanup_error


if __name__ == "__main__":
    raise SystemExit(main())
