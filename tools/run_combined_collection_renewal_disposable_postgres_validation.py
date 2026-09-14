from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import run_stage5d17_disposable_postgres_validation as disposable
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "gilbic_backend" / "src"
MOBILE_SRC = ROOT / "spina_backend_mobile" / "src"
MIGRATION_RUNNER = ROOT / "tools" / "apply_0100_0101_collection_renewal_migrations.py"
AREA_MANAGEMENT_MIGRATION = (
    ROOT / "gilbic_backend" / "sql" / "0113_add_authoritative_area_management.sql"
)
AREA_ACCEPTANCE_TESTS = (
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_area_management_postgres.py",
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_area_management_collector_assignment.py",
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_area_management_client_transfer.py",
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_delegated_area_access_postgres.py",
)
TARGET_TESTS = (
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_combined_collection_renewal_workflow_postgres.py",
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_seven_by_seven_verified_advance_postgres.py",
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_seven_by_seven_no_collection_voluntary_postgres.py",
)
# The shared branch schema is contiguous through 0111. Migration 0112 belongs to
# the separately isolated onboarding work and is intentionally absent from this
# Area Management branch, while current collection posting now depends on the
# Area transfer table introduced by 0113. Replay the shared baseline through
# 0111, then apply this branch's 0113 feature migration directly.
BOOTSTRAP_THROUGH = 111
REQUIRED_7X7_READER_RELATIONS = (
    "lending.seven_by_seven_extra_principal_adjustments",
    "lending.loan_contract_installments_operational",
    "lending.loan_installment_active_advance",
    "accounting.loan_contract_dpd_assessment",
)
BASE_DATABASE_URL_ENV = "COMBINED_RENEWAL_DATABASE_URL"
DISPOSABLE_DATABASE_PREFIX = "spina_combined_renewal_"


def _base_connection_params() -> dict[str, str]:
    database_url = os.getenv(BASE_DATABASE_URL_ENV)
    if not database_url:
        raise SystemExit(
            f"{BASE_DATABASE_URL_ENV} is not configured; refusing to guess PostgreSQL credentials."
        )

    return disposable._safe_local_connection_params(database_url)


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
    previous_bootstrap_through = disposable.BOOTSTRAP_THROUGH
    try:
        disposable.BOOTSTRAP_THROUGH = BOOTSTRAP_THROUGH
        disposable._install_supabase_auth_prerequisite(test_url)
        disposable._bootstrap_database(test_url)
        with psycopg.connect(test_url, autocommit=True) as connection:
            connection.execute(AREA_MANAGEMENT_MIGRATION.read_text(encoding="utf-8"))
    finally:
        disposable.BOOTSTRAP_THROUGH = previous_bootstrap_through


def _assert_current_7x7_reader_schema(test_url: str) -> None:
    with psycopg.connect(test_url, autocommit=True) as connection:
        for relation in REQUIRED_7X7_READER_RELATIONS:
            row = connection.execute("SELECT to_regclass(%s)", (relation,)).fetchone()
            if row is None or row[0] is None:
                raise RuntimeError(
                    "Disposable combined Pay + renewal schema is stale; "
                    f"required 7x7 reader relation is missing after migration "
                    f"{BOOTSTRAP_THROUGH:04d}: {relation}"
                )

        row = connection.execute(
            "SELECT pg_get_viewdef(%s::regclass, true)",
            ("accounting.loan_contract_dpd_assessment",),
        ).fetchone()
        definition = "" if row is None or row[0] is None else str(row[0]).lower()
        required_reader_fragments = (
            "loan_contract_installments_operational",
            "loan_installment_active_advance",
            "seven_by_seven_extra_principal_adjustments",
        )
        missing_fragments = [
            fragment
            for fragment in required_reader_fragments
            if fragment not in definition
        ]
        if missing_fragments:
            raise RuntimeError(
                "Disposable combined Pay + renewal DPD reader is not aligned through "
                f"migration {BOOTSTRAP_THROUGH:04d}; missing view dependencies: "
                + ", ".join(missing_fragments)
            )


def main() -> int:
    for required in (
        AREA_MANAGEMENT_MIGRATION,
        MIGRATION_RUNNER,
        *AREA_ACCEPTANCE_TESTS,
        *TARGET_TESTS,
    ):
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

        print(
            f"Bootstrapping disposable database through migration {BOOTSTRAP_THROUGH:04d} "
            "plus Area Management migration 0113..."
        )
        _bootstrap_database(test_url)
        _assert_current_7x7_reader_schema(test_url)

        migration_env = _env(test_url)
        print("Re-running guarded 0100/0101 migrations to prove idempotency...")
        _run([sys.executable, str(MIGRATION_RUNNER)], env=migration_env, timeout=300)
        print("Re-running guarded migrations once more to prove idempotency...")
        _run([sys.executable, str(MIGRATION_RUNNER)], env=migration_env, timeout=300)

        # Run the Area acceptance suite first while the disposable database is
        # still clean. Existing 7x7 tests intentionally commit legacy Cardona
        # fixtures, which would otherwise create unrelated equal-specificity
        # owners and contaminate the delegated-ownership assertions.
        print("Running Area Management PostgreSQL acceptance tests on clean 0113 state...")
        _run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                *(str(path) for path in AREA_ACCEPTANCE_TESTS),
            ],
            env=migration_env,
            timeout=600,
        )

        print(
            "Running atomic combined Pay/renewal, verified 7x7 Advance, and NC voluntary "
            "PostgreSQL tests..."
        )
        _run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                *(str(path) for path in TARGET_TESTS),
            ],
            env=migration_env,
            timeout=900,
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
            except Exception as error:  # noqa: BLE001 - cleanup is best effort
                print(f"Warning: failed to drop disposable database: {error}")

    print("Disposable combined Pay + renewal + Area Management validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
