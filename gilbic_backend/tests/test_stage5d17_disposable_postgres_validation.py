from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "tools" / "run_stage5d17_disposable_postgres_validation.py"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "stage5d17-disposable-postgres.yml"
SPEC = importlib.util.spec_from_file_location("stage5d17_disposable", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_disposable_validator_accepts_and_forces_loopback_endpoint() -> None:
    params = MODULE._safe_local_connection_params(
        "postgresql://postgres:secret@127.0.0.1:5432/spina_live"
    )
    assert params["host"] == "127.0.0.1"
    assert params["hostaddr"] == "127.0.0.1"
    assert params["dbname"] == "spina_live"

    params = MODULE._safe_local_connection_params(
        "postgresql://postgres:secret@localhost:5432/spina_live"
    )
    assert params["host"] == "localhost"
    assert params["hostaddr"] == "127.0.0.1"

    params = MODULE._safe_local_connection_params(
        "hostaddr=::1 dbname=spina_live user=postgres password=secret"
    )
    assert params["host"] == "::1"
    assert params["hostaddr"] == "::1"


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://postgres:secret@db.example.com:5432/spina_live",
        "host=10.0.0.50 dbname=spina_live user=postgres password=secret",
        "host=localhost hostaddr=10.0.0.50 dbname=spina_live user=postgres password=secret",
    ],
)
def test_disposable_validator_refuses_remote_postgres(database_url: str) -> None:
    with pytest.raises(SystemExit, match="host"):
        MODULE._safe_local_connection_params(database_url)


def test_disposable_validator_requires_explicit_endpoint() -> None:
    with pytest.raises(SystemExit, match="explicit loopback"):
        MODULE._safe_local_connection_params(
            "dbname=spina_live user=postgres password=secret"
        )


def test_disposable_validator_refuses_libpq_service_settings() -> None:
    with pytest.raises(SystemExit, match="service"):
        MODULE._safe_local_connection_params(
            "service=spina_local host=localhost dbname=spina_live user=postgres"
        )


def test_disposable_validator_requires_named_database() -> None:
    with pytest.raises(SystemExit, match="database name is missing"):
        MODULE._safe_local_connection_params(
            "host=localhost user=postgres password=secret"
        )


def test_disposable_validator_clears_endpoint_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in MODULE.ENDPOINT_ENV_KEYS:
        monkeypatch.setenv(key, "unsafe-value")
    monkeypatch.setenv("PGPASSWORD", "keep-me")

    MODULE._clear_endpoint_environment()

    for key in MODULE.ENDPOINT_ENV_KEYS:
        assert key not in MODULE.os.environ
    assert MODULE.os.environ["PGPASSWORD"] == "keep-me"


def test_disposable_validator_retargets_only_database_name() -> None:
    base = MODULE._safe_local_connection_params(
        "postgresql://postgres:secret@localhost:5432/spina_live?sslmode=disable"
    )
    target = MODULE._conninfo_for_database(base, "spina_stage5d17_test")
    parsed = MODULE.conninfo_to_dict(target)
    assert parsed["dbname"] == "spina_stage5d17_test"
    assert parsed["host"] == "localhost"
    assert parsed["hostaddr"] == "127.0.0.1"
    assert parsed["user"] == "postgres"
    assert parsed["sslmode"] == "disable"


def test_disposable_validator_defines_minimal_supabase_auth_prerequisite() -> None:
    assert MODULE.AUTH_SCHEMA_SQL == "CREATE SCHEMA IF NOT EXISTS auth"
    assert MODULE.AUTH_USERS_SQL == (
        "CREATE TABLE IF NOT EXISTS auth.users (id uuid PRIMARY KEY)"
    )


def test_disposable_validator_arms_cleanup_before_create_database() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    cleanup_index = source.index("cleanup_required = True")
    create_index = source.index('sql.SQL("CREATE DATABASE {} TEMPLATE template0")')
    assert cleanup_index < create_index
    assert "DROP DATABASE IF EXISTS" in source


def test_disposable_janitor_only_accepts_reserved_hex_database_names() -> None:
    prefix = MODULE.TEST_DATABASE_PREFIX
    assert MODULE._is_disposable_database_name(prefix + "a" * 12)
    assert MODULE._is_disposable_database_name(prefix + "b" * 32)
    assert not MODULE._is_disposable_database_name("spina_live")
    assert not MODULE._is_disposable_database_name(prefix + "g" * 32)
    assert not MODULE._is_disposable_database_name(prefix + "a" * 16)


def test_disposable_drop_waits_and_retries_after_backend_termination() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert MODULE.DROP_RETRY_ATTEMPTS >= 2
    assert MODULE.DROP_SESSION_WAIT_ATTEMPTS >= 2
    assert MODULE.DROP_SESSION_WAIT_SECONDS > 0
    assert "_wait_for_database_sessions_to_end" in source
    assert "psycopg.errors.ObjectInUse" in source
    assert "pg_terminate_backend" in source


def test_disposable_workflow_serializes_and_reserves_final_janitor_budget() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "group: stage5d17-disposable-local-postgres" in workflow
    assert "cancel-in-progress: false" in workflow
    # Every step before/post execution has an explicit maximum. Their documented
    # maximums total 39 minutes, leaving 21 minutes below the 60-minute job cap.
    assert "timeout-minutes: 60" in workflow
    for timeout in (2, 5, 10, 12):
        assert f"timeout-minutes: {timeout}" in workflow
    assert workflow.count("timeout-minutes: 5") == 3
    assert "if: always()" in workflow
    assert workflow.count("--cleanup-stale-only") == 2
    assert "Reap stale Stage 5D.17 disposable databases before execution" in workflow
    assert "Reap Stage 5D.17 disposable databases after execution" in workflow


def test_disposable_validator_bootstraps_every_historical_file_through_0039() -> None:
    paths = MODULE._migration_paths()
    numbers = [int(path.name[:4]) for path in paths]

    assert paths == sorted(paths, key=lambda item: item.name)
    assert paths[0].name.startswith("0001_")
    assert paths[-1].name.startswith("0039_")
    assert set(numbers) == set(range(1, 40))

    # The repository intentionally contains two historical 0018 migrations.
    # Both must be preserved rather than deduplicated by numeric prefix.
    assert numbers.count(18) == 2
    assert len(paths) == 40


def test_disposable_validator_targets_only_real_regular_posting_test() -> None:
    assert MODULE.POSTING_TEST.name == "test_regular_journal_posting_postgres.py"
    assert MODULE.POSTING_TEST.is_file()
