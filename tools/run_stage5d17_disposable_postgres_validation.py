from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo


SQL_ROOT = Path(__file__).resolve().parents[1] / "gilbic_backend" / "sql"
POSTING_TEST = (
    Path(__file__).resolve().parents[1]
    / "gilbic_backend"
    / "tests"
    / "test_regular_journal_posting_postgres.py"
)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
BOOTSTRAP_THROUGH = 39


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _safe_local_connection_params(database_url: str) -> dict[str, str]:
    params = {str(key): str(value) for key, value in conninfo_to_dict(database_url).items()}
    host = params.get("host", "").strip().lower()
    hostaddr = params.get("hostaddr", "").strip().lower()

    # On Windows, an omitted host means libpq's local/default connection. Any
    # explicit host must be loopback. This verifier must never create or drop a
    # synthetic database on a remote/production PostgreSQL server.
    if host and host not in LOCAL_HOSTS:
        raise SystemExit(
            "Stage 5D.17 disposable PostgreSQL validation refused: configured database host is not local."
        )
    if hostaddr and hostaddr not in LOCAL_HOSTS:
        raise SystemExit(
            "Stage 5D.17 disposable PostgreSQL validation refused: configured database hostaddr is not loopback."
        )

    live_db = params.get("dbname", "").strip()
    if not live_db:
        raise SystemExit(
            "Stage 5D.17 disposable PostgreSQL validation refused: configured database name is missing."
        )
    return params


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
    if not paths or paths[0].name[:4] != "0001" or paths[-1].name[:4] != f"{BOOTSTRAP_THROUGH:04d}":
        raise SystemExit(
            "Stage 5D.17 disposable PostgreSQL validation refused: expected migrations 0001 through 0039 are incomplete."
        )

    expected_numbers = set(range(1, BOOTSTRAP_THROUGH + 1))
    actual_numbers = {int(path.name[:4]) for path in paths}
    missing_numbers = sorted(expected_numbers - actual_numbers)
    if missing_numbers:
        missing_text = ", ".join(f"{number:04d}" for number in missing_numbers)
        raise SystemExit(
            "Stage 5D.17 disposable PostgreSQL validation refused: missing migration numbers before 0040: "
            + missing_text
        )

    # Historical migration numbering contains a duplicate 0018. Preserve every
    # migration file in deterministic filename order instead of pretending the
    # numeric prefixes are unique.
    return paths


def _conninfo_for_database(base_params: dict[str, str], database_name: str) -> str:
    params = dict(base_params)
    params["dbname"] = database_name
    return make_conninfo(**params)


def _drop_database(admin_connection: psycopg.Connection, database_name: str) -> None:
    admin_connection.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
        (database_name,),
    )
    admin_connection.execute(
        sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database_name))
    )


def _bootstrap_database(test_database_url: str) -> None:
    with psycopg.connect(test_database_url, autocommit=True) as connection:
        for path in _migration_paths():
            connection.execute(path.read_text(encoding="utf-8"))


def _run_posting_test(test_database_url: str) -> int:
    if not POSTING_TEST.is_file():
        raise SystemExit(
            "Stage 5D.17 disposable PostgreSQL validation refused: posting integration test file is missing."
        )
    env = os.environ.copy()
    env["GILBIC_TEST_DATABASE_URL"] = test_database_url
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(POSTING_TEST)],
        env=env,
        check=False,
    )
    return int(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a local disposable PostgreSQL database, bootstrap SPINA through "
            "migration 0039, execute the real Stage 5D.17 protected Regular posting "
            "integration test, then drop the disposable database."
        )
    )
    parser.add_argument("--env-file", action="append", type=Path, default=[])
    parser.add_argument("--database-url-env", default="GILBIC_DATABASE_URL")
    args = parser.parse_args()

    for env_path in args.env_file:
        _load_env_file(env_path)

    database_url = os.getenv(args.database_url_env)
    if not database_url:
        raise SystemExit(f"{args.database_url_env} is not configured")

    base_params = _safe_local_connection_params(database_url)
    live_db = base_params["dbname"]
    test_db = f"spina_stage5d17_{uuid4().hex[:12]}"
    if test_db == live_db:
        raise SystemExit("Stage 5D.17 disposable PostgreSQL validation refused: test database matches live database.")

    admin_url = _conninfo_for_database(base_params, "postgres")
    test_url = _conninfo_for_database(base_params, test_db)
    created = False
    primary_error: BaseException | None = None

    try:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(test_db))
            )
            created = True

        _bootstrap_database(test_url)
        result = _run_posting_test(test_url)
        if result != 0:
            raise SystemExit(
                f"Stage 5D.17 disposable PostgreSQL validation failed: posting integration test exited with code {result}."
            )
        print(
            "Stage 5D.17 disposable PostgreSQL validation passed: atomic protected posting, exact retry, manual-post rejection, immutable audit, and forced rollback were executed in a disposable local database."
        )
        return 0
    except psycopg.Error as error:
        primary_error = error
        raise SystemExit(
            "Stage 5D.17 disposable PostgreSQL validation failed: "
            + str(error).split("CONTEXT:", 1)[0].strip()
        ) from error
    except BaseException as error:
        primary_error = error
        raise
    finally:
        if created:
            try:
                with psycopg.connect(admin_url, autocommit=True) as admin:
                    _drop_database(admin, test_db)
            except psycopg.Error as cleanup_error:
                message = (
                    "Stage 5D.17 disposable PostgreSQL cleanup failed: "
                    + str(cleanup_error).split("CONTEXT:", 1)[0].strip()
                )
                print(message, file=sys.stderr)
                if primary_error is None:
                    raise SystemExit(message) from cleanup_error


if __name__ == "__main__":
    raise SystemExit(main())
