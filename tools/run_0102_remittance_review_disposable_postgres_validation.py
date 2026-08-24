from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.types.json import Jsonb

import run_stage5d17_disposable_postgres_validation as disposable


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "gilbic_backend" / "src"
MIGRATION_RUNNER = ROOT / "tools" / "apply_0102_remittance_review_rejection_migration.py"
TARGET_TEST = (
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_remittance_review_rejection_postgres.py"
)
BOOTSTRAP_THROUGH = 101
BASE_DATABASE_URL_ENV = "REMIT_REVIEW_DATABASE_URL"
DISPOSABLE_DATABASE_PREFIX = "spina_remit_review_"


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
            "0102 disposable validation refused: PostgreSQL must be loopback-only."
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
    roots = [str(ROOT), str(BACKEND_SRC)]
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
    disposable.BOOTSTRAP_THROUGH = BOOTSTRAP_THROUGH
    disposable._install_supabase_auth_prerequisite(test_url)
    disposable._bootstrap_database(test_url)


def _seed_preexisting_locked_handover(test_url: str):
    suffix = uuid.uuid4().hex[:8]
    collection_date = date(2099, 2, 1)
    with psycopg.connect(test_url) as connection:
        collector_id = connection.execute(
            """
            insert into core.users(username, full_name, status)
            values(%s, %s, 'active')
            returning id
            """,
            (f"0102-pre-collector-{suffix}", f"0102 Pre Collector {suffix}"),
        ).fetchone()[0]
        recipient_id = connection.execute(
            """
            insert into core.users(username, full_name, status)
            values(%s, %s, 'active')
            returning id
            """,
            (f"0102-pre-recipient-{suffix}", f"0102 Pre Recipient {suffix}"),
        ).fetchone()[0]
        connection.execute(
            """
            insert into core.user_roles(user_id, role_id)
            select %s, id from core.roles where code='collector'
            """,
            (collector_id,),
        )
        connection.execute(
            """
            insert into core.user_roles(user_id, role_id)
            select %s, id from core.roles where code='management'
            """,
            (recipient_id,),
        )
        device_id = connection.execute(
            """
            insert into core.devices(user_id, device_identifier_hash, platform, status)
            values(%s, %s, 'android', 'active')
            returning id
            """,
            (collector_id, f"0102-pre-device-{suffix}"),
        ).fetchone()[0]
        loan_type_id = connection.execute(
            """
            insert into lending.loan_types(
                code, name, term_days, calculation_mode, daily_interest_per_1000
            ) values(%s, %s, 120, 'fixed_daily', 0)
            returning id
            """,
            (f"0102-PRE-{suffix}", f"0102 Pre Regular {suffix}"),
        ).fetchone()[0]
        client_id = connection.execute(
            """
            insert into lending.clients(client_code, full_name, status, area)
            values(%s, %s, 'active', '0102 Pre Area')
            returning id
            """,
            (f"0102-PRE-C-{suffix}", f"0102 Pre Client {suffix}"),
        ).fetchone()[0]
        release_date = collection_date - timedelta(days=10)
        loan_id = connection.execute(
            """
            insert into lending.loans(
                loan_number, client_id, loan_type_id, principal, daily_amount,
                date_released, due_date, status
            ) values(%s, %s, %s, 1000.00, 100.00, %s, %s, 'active')
            returning id
            """,
            (
                f"0102-PRE-L-{suffix}",
                client_id,
                loan_type_id,
                release_date,
                release_date + timedelta(days=120),
            ),
        ).fetchone()[0]
        transaction_id, accepted_at = connection.execute(
            """
            insert into lending.collection_transactions(
                idempotency_key,
                loan_id,
                client_id,
                collector_user_id,
                registered_device_id,
                route_entry_id,
                collection_date,
                entry_type,
                amount,
                recorded_at,
                device_sequence,
                note,
                previous_balance,
                official_balance,
                pass_count_after,
                advance_until_after,
                receipt_number,
                details
            ) values(
                %s, %s, %s, %s, %s, %s, %s, 'payment', 100.00,
                now(), 1, 'Pre-existing locked handover', 1000.00, 900.00,
                0, null, %s, '{"source":"0102-preexisting"}'::jsonb
            )
            returning id, accepted_at
            """,
            (
                uuid.uuid4(),
                loan_id,
                client_id,
                collector_id,
                device_id,
                loan_id,
                collection_date,
                f"0102-PRE-R-{suffix}",
            ),
        ).fetchone()
        remittance_id = connection.execute(
            """
            insert into lending.collection_remittances(
                remittance_number,
                collector_user_id,
                recipient_user_id,
                collection_date,
                status,
                transaction_count,
                payment_count,
                unable_to_pay_count,
                covered_payment_count,
                client_count,
                total_amount,
                note
            ) values(%s, %s, %s, %s, 'submitted', 1, 1, 0, 0, 1, 100.00, %s)
            returning id
            """,
            (
                f"REM-0102-PRE-{suffix}",
                collector_id,
                recipient_id,
                collection_date,
                "Pre-existing handover must remain unchanged",
            ),
        ).fetchone()[0]
        connection.execute(
            """
            update lending.collection_transactions
            set remittance_id=%s,
                is_locked=true,
                locked_at=now(),
                locked_by_user_id=%s,
                updated_at=now(),
                updated_by_user_id=%s
            where id=%s
            """,
            (remittance_id, collector_id, collector_id, transaction_id),
        )
        connection.execute(
            """
            insert into lending.collection_remittance_items(
                remittance_id,
                transaction_id,
                client_id,
                loan_id,
                collection_date,
                entry_type,
                amount,
                receipt_number,
                transaction_snapshot
            ) values(%s, %s, %s, %s, %s, 'payment', 100.00, %s, %s)
            """,
            (
                remittance_id,
                transaction_id,
                client_id,
                loan_id,
                collection_date,
                f"0102-PRE-R-{suffix}",
                Jsonb(
                    {
                        "transaction_id": str(transaction_id),
                        "client_id": str(client_id),
                        "client_name": f"0102 Pre Client {suffix}",
                        "loan_id": str(loan_id),
                        "loan_type": f"0102 Pre Regular {suffix}",
                        "collection_date": collection_date.isoformat(),
                        "entry_type": "payment",
                        "amount": "100.00",
                        "receipt_number": f"0102-PRE-R-{suffix}",
                        "accepted_at": accepted_at.isoformat(),
                        "note": "Pre-existing locked handover",
                        "covered_dates": [],
                    }
                ),
            ),
        )
    return remittance_id, transaction_id


def _preexisting_snapshot(test_url: str, *, remittance_id, transaction_id):
    with psycopg.connect(test_url) as connection:
        remittance = connection.execute(
            "select to_jsonb(r) from lending.collection_remittances r where id=%s",
            (remittance_id,),
        ).fetchone()[0]
        transaction = connection.execute(
            "select to_jsonb(t) from lending.collection_transactions t where id=%s",
            (transaction_id,),
        ).fetchone()[0]
        item = connection.execute(
            """
            select to_jsonb(i)
            from lending.collection_remittance_items i
            where remittance_id=%s and transaction_id=%s
            """,
            (remittance_id, transaction_id),
        ).fetchone()[0]
        return remittance, transaction, item


def main() -> int:
    for required in (MIGRATION_RUNNER, TARGET_TEST):
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
        remittance_id, transaction_id = _seed_preexisting_locked_handover(test_url)
        before = _preexisting_snapshot(
            test_url,
            remittance_id=remittance_id,
            transaction_id=transaction_id,
        )

        migration_env = _env(test_url)
        print("Applying guarded 0102 remittance review/rejection migration...")
        _run([sys.executable, str(MIGRATION_RUNNER)], env=migration_env, timeout=300)
        after_first = _preexisting_snapshot(
            test_url,
            remittance_id=remittance_id,
            transaction_id=transaction_id,
        )
        if after_first != before:
            raise RuntimeError(
                "0102 disposable validation failed: pre-existing locked handover evidence changed"
            )

        print("Re-running guarded 0102 migration to prove idempotency...")
        _run([sys.executable, str(MIGRATION_RUNNER)], env=migration_env, timeout=300)
        after_second = _preexisting_snapshot(
            test_url,
            remittance_id=remittance_id,
            transaction_id=transaction_id,
        )
        if after_second != before:
            raise RuntimeError(
                "0102 disposable validation failed: idempotent retry changed historical evidence"
            )

        print("Running remittance review/rejection PostgreSQL behavior tests...")
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

    print(
        "0102 disposable PostgreSQL validation passed: pre-existing locked handover evidence "
        "survived installation and retry unchanged; recipient review is required; acceptance "
        "records permanent review evidence; rejection preserves the frozen item snapshot and "
        "reason, unlocks only custody metadata, keeps financial fields immutable, and permits "
        "the same official payment to be audibly linked through a corrected resubmission."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
