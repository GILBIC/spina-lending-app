from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "run_stage5d17_disposable_postgres_validation.py"
)
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
