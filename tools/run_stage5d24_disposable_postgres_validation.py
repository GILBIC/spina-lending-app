from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo


ROOT = Path(__file__).resolve().parents[1]
SQL_ROOT = ROOT / "gilbic_backend" / "sql"
EVIDENCE_TESTS = (
    ROOT / "gilbic_backend" / "tests" / "test_loan_renewal_execution_evidence_postgres.py",
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_loan_renewal_execution_status_progression_postgres.py",
)
BOOTSTRAP_THROUGH = 49
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
LOCAL_HOSTADDRS = {"127.0.0.1", "::1"}
DEFAULT_HOSTADDR = {
    "localhost": "127.0.0.1",
    "127.0.0.1": "127.0.0.1",
    "::1": "::1",
}
ENDPOINT_ENV_KEYS = (
    "PGHOST",
    "PGHOSTADDR",
    "PGSERVICE",
    "PGSERVICEFILE",
    "PGPORT",
    "PGDATABASE",
)


def _safe_loopback_conninfo(database_url: str) -> str:
    params = {str(key): str(value) for key, value in conninfo_to_dict(database_url).items()}
    host = params.get("host", "").strip().lower()
    hostaddr = params.get("hostaddr", "").strip().lower()
    if params.get("service") or params.get("servicefile"):
        raise SystemExit(
            "Stage 5D.24 disposable PostgreSQL validation refused: libpq service settings are not allowed."
        )
    if not host and not hostaddr:
        raise SystemExit(
            "Stage 5D.24 disposable PostgreSQL validation refused: an explicit loopback host or hostaddr is required."
        )
    if host and host not in LOCAL_HOSTS:
        raise SystemExit(
            "Stage 5D.24 disposable PostgreSQL validation refused: configured database host is not local."
        )
    if hostaddr and hostaddr not in LOCAL_HOSTADDRS:
        raise SystemExit(
            "Stage 5D.24 disposable PostgreSQL validation refused: configured database hostaddr is not loopback."
        )
    if not host:
        host = hostaddr
    if not hostaddr:
        hostaddr = DEFAULT_HOSTADDR[host]
    params["host"] = host
    params["hostaddr"] = hostaddr
    if not params.get("dbname", "").strip():
        raise SystemExit(
            "Stage 5D.24 disposable PostgreSQL validation refused: configured database name is missing."
        )
    return make_conninfo(**params)


def _require_owned_cluster_marker(marker_path: Path) -> None:
    if not marker_path.is_file():
        raise SystemExit(
            "Stage 5D.24 disposable PostgreSQL validation refused: owned temporary-cluster readiness marker is missing."
        )
    marker = marker_path.read_text(encoding="ascii", errors="strict")
    if "ready=true" not in marker:
        raise SystemExit(
            "Stage 5D.24 disposable PostgreSQL validation refused: temporary-cluster marker is not ready."
        )


def _migration_paths() -> list[Path]:
    paths: list[Path] = []
    for path in SQL_ROOT.glob("[0-9][0-9][0-9][0-9]_*.sql"):
        try:
            migration_number = int(path.name[:4])
        except ValueError:
            continue
        if migration_number <= BOOTSTRAP_THROUGH:
            paths.append(path)
    paths.sort(key=lambda item: item.name)

    expected_numbers = set(range(1, BOOTSTRAP_THROUGH + 1))
    actual_numbers = {int(path.name[:4]) for path in paths}
    missing_numbers = sorted(expected_numbers - actual_numbers)
    if missing_numbers:
        raise SystemExit(
            "Stage 5D.24 disposable PostgreSQL validation refused: historical migrations are incomplete before 0050: "
            + ", ".join(f"{number:04d}" for number in missing_numbers)
        )
    if not paths or paths[0].name[:4] != "0001" or paths[-1].name[:4] != "0049":
        raise SystemExit(
            "Stage 5D.24 disposable PostgreSQL validation refused: expected historical replay through migration 0049."
        )
    return paths


def _assert_fresh_database(connection: psycopg.Connection) -> None:
    rows = connection.execute(
        """
        select nspname
        from pg_namespace
        where nspname in ('core', 'lending', 'accounting')
        order by nspname
        """
    ).fetchall()
    if rows:
        raise SystemExit(
            "Stage 5D.24 disposable PostgreSQL validation refused: target database is not a fresh temporary cluster."
        )


def _bootstrap_database(database_url: str) -> None:
    with psycopg.connect(database_url, autocommit=True) as connection:
        _assert_fresh_database(connection)
        connection.execute("CREATE SCHEMA auth")
        connection.execute("CREATE TABLE auth.users (id uuid PRIMARY KEY)")
        for path in _migration_paths():
            connection.execute(path.read_text(encoding="utf-8"))


def _run_evidence_tests(database_url: str) -> int:
    missing = [str(path) for path in EVIDENCE_TESTS if not path.is_file()]
    if missing:
        raise SystemExit(
            "Stage 5D.24 disposable PostgreSQL validation refused: evidence integration test file is missing: "
            + ", ".join(missing)
        )
    env = os.environ.copy()
    for key in ENDPOINT_ENV_KEYS:
        env.pop(key, None)
    env["GILBIC_TEST_DATABASE_URL"] = database_url
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *(str(path) for path in EVIDENCE_TESTS)],
        env=env,
        check=False,
    )
    return int(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Replay SPINA through migration 0049 in an owned loopback-only temporary "
            "PostgreSQL cluster, then execute the real Stage 5D.24 authoritative "
            "renewal execution evidence proofs."
        )
    )
    parser.add_argument("--database-url-env", default="STAGE5D24_DATABASE_URL")
    parser.add_argument("--cluster-marker-env", default="STAGE5D24_CLUSTER_MARKER")
    args = parser.parse_args()

    database_url = os.getenv(args.database_url_env)
    marker_value = os.getenv(args.cluster_marker_env)
    if not database_url:
        raise SystemExit(f"{args.database_url_env} is not configured")
    if not marker_value:
        raise SystemExit(f"{args.cluster_marker_env} is not configured")

    _require_owned_cluster_marker(Path(marker_value))
    normalized_url = _safe_loopback_conninfo(database_url)
    for key in ENDPOINT_ENV_KEYS:
        os.environ.pop(key, None)

    try:
        _bootstrap_database(normalized_url)
        result = _run_evidence_tests(normalized_url)
        if result != 0:
            raise SystemExit(
                f"Stage 5D.24 disposable PostgreSQL validation failed: renewal execution evidence integration tests exited with code {result}."
            )
        print(
            "Stage 5D.24 disposable PostgreSQL validation passed: client renewal requests were not treated as execution proof, old/new loan linkage required an explicit active renewal_release event and exact settlement evidence, direct mutation was blocked, retries stayed idempotent across normal loan status progression, policy-review cases stayed blocked, journal creation remained disabled, and evidence with future journal history could not be voided."
        )
        return 0
    except psycopg.Error as error:
        raise SystemExit(
            "Stage 5D.24 disposable PostgreSQL validation failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error


if __name__ == "__main__":
    raise SystemExit(main())
