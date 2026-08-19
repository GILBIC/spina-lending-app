from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql

import run_stage5d17_disposable_postgres_validation as disposable


TEST_DATABASE_PREFIX = "spina_remittance_capacity_"
BOOTSTRAP_THROUGH = 98
ROOT = Path(__file__).resolve().parents[1]
APPLY_TOOL = ROOT / "tools" / "apply_0099_remittance_recipient_capacity_migration.py"
INTEGRATION_TEST = (
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_remittance_recipient_capacity_postgres.py"
)
LEGACY_MARKER = "REM-20990101-99999999"


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
            "0099 disposable validation refused: guarded live migration tool is missing."
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
            "0099 disposable validation refused: PostgreSQL integration test is missing."
        )
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(INTEGRATION_TEST)],
        env=_subprocess_env(test_database_url),
        check=False,
    )
    return int(completed.returncode)


def _seed_legacy_remittance(test_database_url: str) -> tuple[object, ...]:
    with psycopg.connect(test_database_url) as connection:
        collector_user_id = connection.execute(
            """
            INSERT INTO core.users(username, full_name, status)
            VALUES(%s, '0099 Legacy Collector', 'active')
            RETURNING id
            """,
            (f"0099-legacy-collector-{uuid4().hex[:10]}",),
        ).fetchone()[0]
        recipient_user_id = connection.execute(
            """
            INSERT INTO core.users(username, full_name, status)
            VALUES(%s, '0099 Legacy Recipient', 'active')
            RETURNING id
            """,
            (f"0099-legacy-recipient-{uuid4().hex[:10]}",),
        ).fetchone()[0]
        row = connection.execute(
            """
            INSERT INTO lending.collection_remittances(
                remittance_number,
                collector_user_id,
                recipient_user_id,
                collection_date,
                transaction_count,
                payment_count,
                unable_to_pay_count,
                covered_payment_count,
                client_count,
                total_amount,
                note
            )
            VALUES(%s, %s, %s, %s, 1, 1, 0, 0, 1, %s, %s)
            RETURNING id, remittance_number, collector_user_id, recipient_user_id,
                      collection_date, status, transaction_count, payment_count,
                      unable_to_pay_count, covered_payment_count, client_count,
                      total_amount, note, submitted_at, received_at,
                      received_by_user_id, created_at, updated_at
            """,
            (
                LEGACY_MARKER,
                collector_user_id,
                recipient_user_id,
                date(2099, 1, 1),
                Decimal("50.00"),
                "Disposable 0099 legacy evidence",
            ),
        ).fetchone()
    return tuple(row)


def _legacy_snapshot(test_database_url: str) -> tuple[object, ...]:
    with psycopg.connect(test_database_url) as connection:
        row = connection.execute(
            """
            SELECT id, remittance_number, collector_user_id, recipient_user_id,
                   collection_date, status, transaction_count, payment_count,
                   unable_to_pay_count, covered_payment_count, client_count,
                   total_amount, note, submitted_at, received_at,
                   received_by_user_id, created_at, updated_at
            FROM lending.collection_remittances
            WHERE remittance_number=%s
            """,
            (LEGACY_MARKER,),
        ).fetchone()
        if row is None:
            raise SystemExit(
                "0099 disposable validation failed: seeded legacy remittance disappeared."
            )
        return tuple(row)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a loopback-only disposable PostgreSQL database, replay SPINA through "
            "0098, seed historical remittance evidence, install 0099 through the same "
            "guarded runner intended for acceptance, verify an exact retry is idempotent, "
            "prove recipient-capacity constraints and immutability, then delete the database."
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
            "0099 disposable validation refused: configured database uses the reserved disposable prefix."
        )

    admin_url = disposable._conninfo_for_database(base_params, "postgres")
    if args.cleanup_stale_only:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            dropped = disposable._drop_stale_disposable_databases(admin)
        print(f"0099 disposable PostgreSQL janitor passed: dropped={dropped}.")
        return 0

    test_database = f"{TEST_DATABASE_PREFIX}{uuid4().hex}"
    test_url = disposable._conninfo_for_database(base_params, test_database)
    cleanup_required = False
    primary_error: BaseException | None = None
    try:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            if disposable._database_exists(admin, test_database):
                raise SystemExit(
                    "0099 disposable validation refused: generated database already exists."
                )
            cleanup_required = True
            admin.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                    sql.Identifier(test_database)
                )
            )

        disposable._install_supabase_auth_prerequisite(test_url)
        disposable._bootstrap_database(test_url)

        before_legacy = _seed_legacy_remittance(test_url)

        first_apply = _run_live_apply_tool(test_url)
        if first_apply != 0:
            raise SystemExit(
                "0099 disposable PostgreSQL validation failed: guarded installation "
                f"exited with code {first_apply}."
            )

        after_first_apply = _legacy_snapshot(test_url)
        if after_first_apply != before_legacy:
            raise SystemExit(
                "0099 disposable PostgreSQL validation failed: historical remittance evidence changed."
            )

        second_apply = _run_live_apply_tool(test_url)
        if second_apply != 0:
            raise SystemExit(
                "0099 disposable PostgreSQL validation failed: idempotent verification "
                f"exited with code {second_apply}."
            )

        after_second_apply = _legacy_snapshot(test_url)
        if after_second_apply != before_legacy:
            raise SystemExit(
                "0099 disposable PostgreSQL validation failed: exact retry changed historical evidence."
            )

        result = _run_test(test_url)
        if result != 0:
            raise SystemExit(
                "0099 disposable PostgreSQL validation failed: PostgreSQL behavior tests "
                f"exited with code {result}."
            )

        print(
            "0099 disposable PostgreSQL validation passed: schema through 0098 was replayed, "
            "historical remittance evidence was preserved and marked legacy, the guarded "
            "acceptance runner installed 0099 and verified an idempotent retry, valid "
            "recipient capacities/defaults were accepted, invalid capacity was rejected, "
            "and recipient capacity was immutable after insertion."
        )
        return 0
    except psycopg.Error as error:
        primary_error = error
        raise SystemExit(
            "0099 disposable PostgreSQL validation failed: "
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
                    "0099 disposable PostgreSQL cleanup failed: "
                    + str(cleanup_error).split("CONTEXT:", 1)[0].strip()
                )
                print(message, file=sys.stderr)
                if primary_error is None:
                    raise SystemExit(message) from cleanup_error


if __name__ == "__main__":
    raise SystemExit(main())
