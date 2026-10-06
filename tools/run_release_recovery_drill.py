"""Prove a synthetic local database AND private-evidence backup can be restored.

This is an isolated release drill, not a production backup or migration command.
The only connection input is an explicit loopback administrative DSN. All data,
database names, and temporary directories are generated and owned by this run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

# Historical disposable helpers are executable sibling modules. Support both
# direct CLI invocation and importing this tool from the repository test suite.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg
import run_stage5d17_disposable_postgres_validation as disposable
from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_THROUGH = 141
DATABASE_NAME = re.compile(r"spina_recovery_(source|restore)_[0-9a-f]{24}")
PDF = b"%PDF-1.4\nSYNTHETIC RECOVERY DRILL - NO REAL PAYMENT\n%%EOF"
ALLOWED_PARAMS = frozenset(
    {
        "host",
        "hostaddr",
        "port",
        "dbname",
        "user",
        "password",
        "sslmode",
        "connect_timeout",
    }
)
PG_ENV = {
    "host": "PGHOST",
    "hostaddr": "PGHOSTADDR",
    "port": "PGPORT",
    "dbname": "PGDATABASE",
    "user": "PGUSER",
    "password": "PGPASSWORD",
    "sslmode": "PGSSLMODE",
    "connect_timeout": "PGCONNECT_TIMEOUT",
}


class DrillError(RuntimeError):
    """A sanitized failure suitable for the public evidence report."""


def safe_admin_params(dsn: str) -> dict[str, str]:
    try:
        supplied = {
            str(key): str(value) for key, value in conninfo_to_dict(dsn).items()
        }
    except psycopg.Error:
        raise DrillError("Invalid explicit administrative DSN.") from None
    if set(supplied) - ALLOWED_PARAMS:
        raise DrillError(
            "Only explicit loopback administrative connection settings are allowed."
        )
    if supplied.get("dbname") != "postgres" or not supplied.get("user"):
        raise DrillError(
            "An explicit postgres administrative database and user are required."
        )
    try:
        port = int(supplied.get("port", "0"))
    except ValueError:
        port = 0
    if not 1 <= port <= 65535:
        raise DrillError("An explicit local administrative port is required.")
    try:
        params = disposable._safe_local_connection_params(dsn)
    except (SystemExit, psycopg.Error):
        raise DrillError(
            "An explicit loopback host is required; remote endpoints are refused."
        ) from None
    params["connect_timeout"] = "5"
    return params


def pg_environment(params: dict[str, str], database: str) -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("PG")
    }
    environment.update({PG_ENV[key]: value for key, value in params.items()})
    environment["PGDATABASE"] = database
    return environment


@contextmanager
def isolated_pg_environment():
    inherited = {
        key: value for key, value in os.environ.items() if key.upper().startswith("PG")
    }
    try:
        for key in inherited:
            os.environ.pop(key)
        yield
    finally:
        os.environ.update(inherited)


def run_pg(
    executable: Path, arguments: list[str], environment: dict[str, str]
) -> bytes:
    try:
        result = subprocess.run(
            [str(executable), "--no-password", *arguments],
            env=environment,
            capture_output=True,
            check=False,
            timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise DrillError(
            f"{executable.stem} could not complete the local drill."
        ) from None
    if result.returncode:
        # libpq/tool errors may contain connection credentials. Never publish them.
        raise DrillError(f"{executable.stem} failed during the local drill.")
    return result.stdout


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def schema_digest(dump: bytes, views: list[tuple[str, str, str]] | None = None) -> str:
    # PostgreSQL 17+ inserts a random psql restrict key into every text dump.
    lines = [
        line
        for line in dump.splitlines()
        if not line.startswith((b"\\restrict ", b"\\unrestrict "))
    ]
    text = b"\n".join(lines).decode("utf-8")
    for name, original, canonical in views or []:
        # Re-parsing a view can flatten associative AND nodes. PostgreSQL's own
        # pretty deparser preserves meaning and produces stable SQL in that case.
        # Replace only the exact identified view body; retain all surrounding
        # schema definitions/ACLs and reject unexpected dump layouts.
        marker = f"CREATE VIEW {name} "
        start = text.find(marker)
        separator = text.find(" AS\n", start) if start >= 0 else -1
        body_start = separator + len(" AS\n")
        original = "\n".join(original.splitlines())
        canonical = "\n".join(canonical.splitlines())
        if separator < 0 or not text[body_start:].startswith(original):
            raise DrillError("Schema dump view definition does not match PostgreSQL.")
        text = text[:body_start] + canonical + text[body_start + len(original) :]
    return sha256(text.encode("utf-8"))


def schema_snapshot(executable: Path, environment: dict[str, str], dsn: str) -> str:
    dump = run_pg(
        executable, ["--schema-only", "--no-owner", "--no-comments"], environment
    )
    with psycopg.connect(dsn) as connection:
        views = connection.execute(
            """SELECT format('%I.%I',n.nspname,c.relname),
            pg_get_viewdef(c.oid,false),pg_get_viewdef(c.oid,true)
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE c.relkind='v' AND n.nspname NOT IN ('pg_catalog','information_schema')
            ORDER BY n.nspname,c.relname"""
        ).fetchall()
    return schema_digest(dump, views)


def file_manifest(root: Path) -> dict[str, dict[str, str | int]]:
    manifest: dict[str, dict[str, str | int]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise DrillError(
                "Private evidence integrity cannot include symbolic links."
            )
        if path.is_file():
            content = path.read_bytes()
            if not content:
                raise DrillError("Private evidence backup must contain nonempty files.")
            manifest[path.relative_to(root).as_posix()] = {
                "sha256": sha256(content),
                "bytes": len(content),
            }
    if not manifest:
        raise DrillError("Private evidence backup must contain nonempty files.")
    return manifest


def verify_files(root: Path, expected: dict[str, dict[str, str | int]]) -> None:
    try:
        actual = file_manifest(root)
    except (DrillError, OSError):
        raise DrillError("Restored private evidence integrity check failed.") from None
    if actual != expected:
        raise DrillError("Restored private evidence integrity check failed.")


def bootstrap(dsn: str) -> list[dict[str, str]]:
    original_limit = disposable.BOOTSTRAP_THROUGH
    try:
        disposable.BOOTSTRAP_THROUGH = BOOTSTRAP_THROUGH
        paths = disposable._migration_paths()
        current = sorted(disposable.SQL_ROOT.glob("[0-9][0-9][0-9][0-9]_*.sql"))
        if paths != current:
            raise DrillError(
                "Recovery bootstrap does not cover the current migration files."
            )
        disposable._install_supabase_auth_prerequisite(dsn)
        disposable._bootstrap_database(dsn)
        return [
            {"file": path.name, "sha256": sha256(path.read_bytes())} for path in paths
        ]
    finally:
        disposable.BOOTSTRAP_THROUGH = original_limit


def seed(dsn: str, private_root: Path) -> None:
    """Synthetic fixtures following payment-proof and employee PostgreSQL tests."""
    user, device, client, loan_type, loan, proof, storage_key, payroll = (
        uuid4() for _ in range(8)
    )
    digest = PrivateEvidenceStore(private_root).put(storage_key, PDF, "application/pdf")
    with psycopg.connect(dsn) as connection:
        connection.execute(
            "INSERT INTO core.users(id,username,full_name,status) VALUES(%s,%s,'Synthetic recovery actor','active')",
            (user, "synthetic-recovery-" + user.hex),
        )
        connection.execute(
            "INSERT INTO core.devices(id,user_id,device_identifier_hash,platform,status) VALUES(%s,%s,%s,'web','active')",
            (device, user, sha256(device.bytes)),
        )
        connection.execute(
            "INSERT INTO core.user_roles(user_id,role_id) SELECT %s,id FROM core.roles WHERE code='collector'",
            (user,),
        )
        connection.execute(
            "INSERT INTO lending.clients(id,user_id,client_code,full_name) VALUES(%s,%s,%s,'Synthetic recovery borrower')",
            (client, user, client.hex),
        )
        connection.execute(
            "INSERT INTO lending.loan_types(id,code,name,term_days,calculation_mode) VALUES(%s,%s,'Synthetic recovery',30,'fixed_daily')",
            (loan_type, loan_type.hex),
        )
        connection.execute(
            "INSERT INTO lending.loans(id,loan_number,client_id,loan_type_id,principal,daily_amount,date_released,due_date,status) VALUES(%s,%s,%s,%s,1000,40,current_date,current_date+30,'active')",
            (loan, loan.hex, client, loan_type),
        )
        connection.execute(
            "INSERT INTO lending.client_payment_proofs(id,client_id,loan_id,created_by_user_id,created_device_id) VALUES(%s,%s,%s,%s,%s)",
            (proof, client, loan, user, device),
        )
        connection.execute(
            """INSERT INTO lending.client_payment_proof_versions
            (id,proof_id,version_number,request_id,media_type,content_sha256,byte_count,storage_key,uploaded_by_user_id,uploaded_device_id)
            VALUES(%s,%s,1,%s,'application/pdf',%s,%s,%s,%s,%s)""",
            (uuid4(), proof, uuid4(), digest, len(PDF), storage_key, user, device),
        )
        connection.execute(
            """INSERT INTO core.employee_profiles(id,employee_id,version,status,payload,created_by)
            VALUES(%s,%s,1,'active',%s,%s)""",
            (
                user,
                user,
                Jsonb({"daily_rate": "800.00", "synthetic_recovery_fixture": True}),
                user,
            ),
        )
        connection.execute(
            """INSERT INTO core.employee_payroll(id,employee_id,version,status,payload,created_by)
            VALUES(%s,%s,1,'draft',%s,%s)""",
            (
                payroll,
                user,
                Jsonb(
                    {
                        "week_start": "2026-09-13",
                        "payroll_kind": "weekly",
                        "gross": "800.00",
                        "synthetic_recovery_fixture": True,
                    }
                ),
                user,
            ),
        )
    seed_treasury(dsn, private_root, user, device, client, loan)
    from recovery_loan_payout_seed import seed_loan_payouts

    seed_loan_payouts(dsn, private_root, PDF)


def seed_treasury(dsn, private_root, user, device, client, loan):
    """Exercise actual service and protected loan posting before the full restore.

    Every amount/account/reference is synthetic. No raw fabricated application or
    official transaction is inserted; the existing posting adapter produces it.
    """
    from gilbic_backend.account_repository import AccountContext
    from gilbic_backend.treasury_claims import submit_claim, upload_evidence
    from gilbic_backend.treasury_models import (
        AccountConfigure,
        AllocationPreview,
        ClaimMetadata,
        DisbursementRecord,
        OpeningActivate,
        OpeningPrepare,
        ReceiptApply,
        ReceiptVerify,
        ReconciliationClose,
        ReconciliationMatch,
        ReconciliationObserve,
        TransferRecord,
    )
    from gilbic_backend.treasury_repository import TreasuryService
    from psycopg.rows import dict_row

    from gilbic_backend import combined_collection_api as combined

    previous = {
        key: os.environ.get(key)
        for key in [
            "SPINA_TREASURY_ENABLED",
            "SPINA_EMPLOYEE_OWNER_USER_ID",
            "SPINA_COLLECTOR_SURPLUS_ENABLED",
        ]
    }
    try:
        os.environ["SPINA_TREASURY_ENABLED"] = "true"
        os.environ["SPINA_EMPLOYEE_OWNER_USER_ID"] = str(user)

        def connection():
            params = conninfo_to_dict(dsn)
            if params.get("host") not in {
                "127.0.0.1",
                "localhost",
                "::1",
            } or not DATABASE_NAME.fullmatch(params.get("dbname", "")):
                raise DrillError(
                    "Treasury fixture requires a drill-owned loopback database."
                )
            return psycopg.connect(dsn, row_factory=dict_row)

        with connection() as conn:
            conn.execute(
                "update lending.clients set area='SYNTHETIC-RECOVERY' where id=%s",
                (client,),
            )
            conn.execute(
                "insert into lending.collector_area_assignments(collector_user_id,area) values(%s,'SYNTHETIC-RECOVERY')",
                (user,),
            )
            conn.execute(
                """update lending.loan_types set settings=%s where id=(select loan_type_id from lending.loans where id=%s)""",
                (
                    Jsonb(
                        {
                            "mobile_collections_enabled": True,
                            "mobile_balance_mode": "direct_remaining_balance",
                        }
                    ),
                    loan,
                ),
            )
            conn.execute(
                "insert into lending.loan_collection_state(loan_id,remaining_balance,is_reconciled,state_version) values(%s,1000,true,0)",
                (loan,),
            )
        actor = AccountContext(
            user,
            user,
            "synthetic",
            None,
            "Synthetic recovery actor",
            "active",
            ("collector",),
            ("treasury.payment.apply",),
            True,
            device,
        )
        service = TreasuryService(connection, PrivateEvidenceStore(private_root))
        context, account, bank = uuid4(), uuid4(), uuid4()

        def version(target=account):
            with connection() as conn:
                return conn.execute(
                    "select version from treasury.accounts where id=%s", (target,)
                ).fetchone()["version"]

        def evidence(purpose="recipient", target=account):
            return upload_evidence(
                service, actor, uuid4(), target, purpose, PDF, "application/pdf"
            )["target_id"]

        def run(model, **values):
            target = values.pop("account_id", account)
            return service.execute(
                actor,
                model(
                    request_id=uuid4(),
                    account_id=target,
                    expected_version=version(target),
                    **values,
                ),
            )

        for target, kind in [(account, "gcash"), (bank, "bank")]:
            service.execute(
                actor,
                AccountConfigure(
                    action="account_configure",
                    request_id=uuid4(),
                    account_id=target,
                    expected_version=0,
                    ledger_context_id=context,
                    context="synthetic",
                    kind=kind,
                    alias="Synthetic recovery " + kind,
                    ownership="synthetic",
                    custodian_user_id=user,
                    designated_receiving=kind == "gcash",
                    payment_instructions="Synthetic only",
                ),
            )
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        prepared = run(
            OpeningPrepare,
            action="opening_prepare",
            cutoff=cutoff,
            amount="10000.00",
            evidence_id=evidence("opening"),
            reason="Synthetic actual opening",
        )
        run(
            OpeningActivate,
            action="opening_activate",
            opening_id=prepared["target_id"],
            opening_version=prepared["version"],
            confirmed=True,
            reason="Synthetic owner confirmed",
        )
        now = datetime.now(timezone.utc)
        claim = submit_claim(
            service,
            actor,
            ClaimMetadata(
                request_id=uuid4(),
                account_id=account,
                account_version=version(),
                client_id=client,
                loan_ids=[loan],
                amount="1000.00",
                reference="recovery-receipt",
                claimed_at=now,
                sender_note="Synthetic proof",
            ),
            PDF,
            "application/pdf",
        )
        claim = submit_claim(
            service,
            actor,
            ClaimMetadata(
                request_id=uuid4(),
                account_id=account,
                account_version=version(),
                client_id=client,
                loan_ids=[loan],
                amount="1000.00",
                reference="recovery-receipt",
                claimed_at=now,
                sender_note="Synthetic corrected proof",
                expected_version=1,
            ),
            PDF,
            "application/pdf",
            claim["target_id"],
        )
        receipt = run(
            ReceiptVerify,
            action="receipt_verify",
            client_id=client,
            amount="1000.00",
            provider="gcash",
            reference="recovery-receipt",
            effective_at=now,
            evidence_id=evidence(),
            recipient_attestation="Synthetic recipient-side history independently verified",
            claim_id=claim["target_id"],
            claim_version=2,
        )
        reviewed = AllocationPreview(
            mode="single",
            total_amount="40.00",
            loans=[{"loan_id": loan, "expected_version": 0}],
            effective_date=combined._current_business_date(),
            expected_version=1,
        )
        preview = service.preview_receipt_application(
            actor, receipt["target_id"], reviewed
        )
        if not preview["can_apply"]:
            raise DrillError("Synthetic protected receipt application is unavailable.")
        service.execute(
            actor,
            ReceiptApply(
                **reviewed.model_dump(),
                action="receipt_apply",
                request_id=uuid4(),
                account_id=account,
                receipt_id=receipt["target_id"],
                digest=preview["digest"],
            ),
        )
        run(
            DisbursementRecord,
            action="disbursement_record",
            amount="100.00",
            provider="gcash",
            reference="recovery-refund",
            effective_at=datetime.now(timezone.utc),
            evidence_id=evidence(),
            recipient_attestation="Synthetic actual refund debit",
            purpose="refund",
            receipt_id=receipt["target_id"],
            reason="Actual synthetic provider refund",
        )
        transfer_id = uuid4()
        run(
            TransferRecord,
            action="transfer_record",
            transfer_id=transfer_id,
            leg="source",
            other_account_id=bank,
            other_account_version=version(bank),
            amount="200.00",
            provider="gcash",
            reference="recovery-transfer-source",
            effective_at=datetime.now(timezone.utc),
            evidence_id=evidence(),
            recipient_attestation="Synthetic actual source transfer",
            reason="Synthetic own-account transfer",
        )
        run(
            TransferRecord,
            account_id=bank,
            action="transfer_record",
            transfer_id=transfer_id,
            leg="destination",
            other_account_id=account,
            other_account_version=version(),
            amount="200.00",
            provider="bank",
            reference="recovery-transfer-destination",
            effective_at=datetime.now(timezone.utc),
            evidence_id=evidence(target=bank),
            recipient_attestation="Synthetic actual destination transfer",
            reason="Synthetic own-account receipt",
        )
        with connection() as conn:
            events = conn.execute(
                "select * from treasury.events where account_id=%s order by effective_at,id",
                (account,),
            ).fetchall()
        rows = [
            {
                "id": uuid4(),
                "provider": row["provider"],
                "reference": row["reference"],
                "direction": row["direction"],
                "amount": format(row["amount"], ".2f"),
                "effective_at": row["effective_at"],
            }
            for row in events
        ]
        reconciliation = run(
            ReconciliationObserve,
            action="reconciliation_observe",
            reconciliation_id=uuid4(),
            coverage_start=cutoff,
            cutoff=datetime.now(timezone.utc),
            actual_balance="10700.00",
            evidence_id=evidence("statement"),
            complete_history=True,
            rows=rows,
        )
        for observed, event in zip(rows, events):
            reconciliation = run(
                ReconciliationMatch,
                action="reconciliation_match",
                reconciliation_id=reconciliation["target_id"],
                reconciliation_version=reconciliation["version"],
                observation_id=observed["id"],
                event_id=event["id"],
            )
        closed = run(
            ReconciliationClose,
            action="reconciliation_close",
            reconciliation_id=reconciliation["target_id"],
            reconciliation_version=reconciliation["version"],
            opening_id=prepared["target_id"],
            movement_watermark=reconciliation["result"]["reconciliation"][
                "movement_watermark"
            ],
            reason="All exact synthetic statements matched",
        )
        if closed["status"] != "saved":
            raise DrillError("Synthetic full-coverage reconciliation did not close.")
        seed_collector_surplus(service, connection, actor, context, client, loan)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def database_snapshot(
    connection: psycopg.Connection,
) -> dict[str, dict[str, str | int]]:
    """Hash every row in each application table, without publishing row contents."""
    tables = connection.execute(
        """SELECT schemaname,tablename FROM pg_tables
        WHERE schemaname NOT IN ('pg_catalog','information_schema')
        AND schemaname NOT LIKE 'pg_toast%' ORDER BY schemaname,tablename"""
    ).fetchall()
    result: dict[str, dict[str, str | int]] = {}
    for schema, table in tables:
        rows = connection.execute(
            sql.SQL(
                "SELECT to_jsonb(t)::text FROM {}.{} t ORDER BY to_jsonb(t)::text"
            ).format(sql.Identifier(schema), sql.Identifier(table))
        ).fetchall()
        result[f"{schema}.{table}"] = {
            "rows": len(rows),
            "sha256": sha256("\n".join(row[0] for row in rows).encode()),
        }
    return result


def verify_database(
    connection: psycopg.Connection, expected: dict[str, dict[str, str | int]]
) -> None:
    if database_snapshot(connection) != expected:
        raise DrillError("Restored database row integrity check failed.")


def seed_collector_surplus(service, connection, owner, context, client, loan):
    """Populate every new relationship through real surplus services, synthetic only."""
    from gilbic_backend.account_repository import AccountContext
    from gilbic_backend.collector_settlement import preview
    from gilbic_backend.treasury_claims import upload_evidence
    from gilbic_backend.treasury_models import COMMAND_ADAPTER, SettlementPreview

    os.environ["SPINA_COLLECTOR_SURPLUS_ENABLED"] = "true"
    collector_id, device_id, account = uuid4(), uuid4(), uuid4()
    with connection() as conn:
        conn.execute(
            "insert into core.user_roles(user_id,role_id) select %s,id from core.roles where code='management' on conflict do nothing",
            (owner.user_id,),
        )
        conn.execute(
            "insert into core.users(id,username,full_name,status) values(%s,%s,'Synthetic surplus restore Collector','active')",
            (collector_id, "surplus-restore-" + collector_id.hex),
        )
        conn.execute(
            "insert into core.devices(id,user_id,device_identifier_hash,platform,status) values(%s,%s,%s,'web','active')",
            (device_id, collector_id, device_id.hex),
        )
        conn.execute(
            "insert into core.user_roles(user_id,role_id) select %s,id from core.roles where code='collector'",
            (collector_id,),
        )
    collector = AccountContext(
        collector_id,
        collector_id,
        "synthetic",
        None,
        "Synthetic surplus restore Collector",
        "active",
        ("collector",),
        (),
        True,
        device_id,
    )

    def version():
        with connection() as conn:
            return conn.execute(
                "select version from treasury.accounts where id=%s", (account,)
            ).fetchone()["version"]

    def run(action, actor=owner, **fields):
        own = action in {
            "collector_surplus_return_request",
            "collector_surplus_return_acknowledge",
        }
        common = (
            {}
            if own
            else {
                "account_id": account,
                "expected_version": 0 if action == "account_configure" else version(),
            }
        )
        return service.execute(
            actor,
            COMMAND_ADAPTER.validate_python(
                dict(action=action, request_id=uuid4(), **common, **fields)
            ),
        )

    run(
        "account_configure",
        ledger_context_id=context,
        context="synthetic",
        kind="physical_cash",
        alias="Synthetic surplus restore counter",
        ownership="synthetic",
        custodian_user_id=owner.user_id,
    )

    def evidence(purpose="recipient"):
        return upload_evidence(
            service, owner, uuid4(), account, purpose, PDF, "application/pdf"
        )["target_id"]

    proof = evidence()
    opening = run(
        "opening_prepare",
        cutoff=datetime.now(timezone.utc) - timedelta(days=1),
        amount="100.00",
        evidence_id=evidence("opening"),
        reason="Synthetic evidenced opening",
    )
    run(
        "opening_activate",
        opening_id=opening["target_id"],
        opening_version=opening["version"],
        confirmed=True,
        reason="Synthetic owner confirms",
    )
    anchor = run(
        "collector_surplus_opening_prepare",
        collector_user_id=collector_id,
        opening_id=opening["target_id"],
        opening_version=2,
        amount="10.00",
        evidence_id=evidence("opening"),
        overlap_review_acknowledged=True,
        reason="Synthetic separately evidenced opening credit",
    )
    run(
        "collector_surplus_opening_activate",
        anchor_id=anchor["target_id"],
        anchor_version=anchor["version"],
        reason="Synthetic retained liability, no new cash",
    )

    def remittance(sequence):
        rid, tid = uuid4(), uuid4()
        with connection() as conn:
            conn.execute(
                """insert into lending.collection_transactions(id,idempotency_key,loan_id,client_id,collector_user_id,registered_device_id,route_entry_id,collection_date,entry_type,amount,recorded_at,device_sequence,note,previous_balance,official_balance,pass_count_after,receipt_number,details)
             values(%s,%s,%s,%s,%s,%s,%s,current_date,'payment',20,now(),%s,'Synthetic restore source',960,940,0,%s,'{}')""",
                (
                    tid,
                    uuid4(),
                    loan,
                    client,
                    collector_id,
                    device_id,
                    loan,
                    sequence,
                    tid.hex,
                ),
            )
            conn.execute(
                """insert into lending.collection_remittances(id,remittance_number,collector_user_id,recipient_user_id,collection_date,status,transaction_count,payment_count,unable_to_pay_count,covered_payment_count,client_count,total_amount,note,submitted_at) values(%s,%s,%s,%s,current_date,'submitted',1,1,0,0,1,20,'Synthetic restore source',now())""",
                (rid, rid.hex, collector_id, owner.user_id),
            )
            conn.execute(
                "insert into lending.collection_remittance_items(remittance_id,transaction_id,client_id,loan_id,collection_date,entry_type,amount,receipt_number,transaction_snapshot) values(%s,%s,%s,%s,current_date,'payment',20,%s,'{}')",
                (rid, tid, client, loan, tid.hex),
            )
            conn.execute(
                "update lending.collection_transactions set remittance_id=%s,is_locked=true,locked_at=now(),locked_by_user_id=%s where id=%s",
                (rid, collector_id, tid),
            )
        return rid

    def count(rid, amount):
        with connection() as conn:
            p = preview(
                service,
                conn,
                owner,
                rid,
                SettlementPreview(account_id=account, expected_version=version()),
            )
        return run(
            "collector_count_record",
            remittance_id=rid,
            source_digest=p["source_digest"],
            counted_amount=amount,
            counted_at=datetime.now(timezone.utc),
            evidence_id=proof,
            recipient_attestation="Synthetic counted cash for restore",
            review_acknowledged=True,
        )["result"]["count"]

    counted = count(remittance(1), "30.00")
    accepted = run(
        "collector_count_accept",
        count_id=counted["id"],
        count_version=1,
        source_digest=counted["source_digest"],
        physical_receipt_acknowledged=True,
    )["result"]
    case = accepted["case"]
    credit = run(
        "collector_surplus_recognize",
        case_id=case["id"],
        case_version=1,
        source_digest=case["source_digest"],
        source_review_acknowledged=True,
        amount="10.00",
        evidence_id=proof,
        reason="Synthetic independent identification",
    )["result"]["credit"]
    request = run(
        "collector_surplus_return_request",
        actor=collector,
        credit_id=credit["id"],
        credit_version=1,
        amount="4.00",
        destination={"kind": "physical_cash", "recipient_reference": None},
        reason="Synthetic own return request",
    )["result"]["request"]
    reserved = run(
        "collector_surplus_return_prepare",
        credit_id=credit["id"],
        credit_version=1,
        collector_request_id=request["id"],
        collector_request_version=1,
        amount="4.00",
        destination=request["destination"],
        evidence_id=proof,
        reason="Synthetic independently approved return",
    )["result"]
    action = reserved["action_record"]
    credit = reserved["credit"]
    debit = run(
        "disbursement_record",
        purpose="collector_surplus_return",
        source_id=action["id"],
        source_version=action["version"],
        payee_id=collector_id,
        amount="4.00",
        provider="physical_cash",
        reference="surplus-restore-return",
        effective_at=datetime.now(timezone.utc),
        evidence_id=proof,
        recipient_attestation="Synthetic actual cash payout",
        reason="Actual independently observed payout",
    )["result"]
    action = debit["source_link"]["action_record"]
    event = debit["event"]
    ack = run(
        "collector_surplus_return_acknowledge",
        actor=collector,
        credit_id=credit["id"],
        credit_version=credit["version"],
        action_id=action["id"],
        action_version=action["version"],
        event_id=event["id"],
        event_version=1,
        reviewed_amount="4.00",
        confirmation="received",
        acknowledged_at=datetime.now(timezone.utc),
        reason="Synthetic own actual receipt",
    )["result"]["acknowledgment"]
    run(
        "collector_surplus_return_record",
        action_id=action["id"],
        action_version=action["version"],
        event_id=event["id"],
        event_version=1,
        acknowledgment_id=ack["id"],
        acknowledgment_version=1,
        reason="Synthetic received payout settlement",
    )
    short = count(remittance(2), "19.00")
    run(
        "collector_custody_exception_record",
        count_id=short["id"],
        count_version=1,
        source_digest=short["source_digest"],
        retained_amount="19.00",
        retained_at=datetime.now(timezone.utc),
        evidence_id=proof,
        holder_attestation="Synthetic dispute cash held by real recipient",
        reason="Preserve rejected obligation and actual held cash",
    )


def verify_relationships(
    connection: psycopg.Connection, private_root: Path
) -> dict[str, Any]:
    proofs = connection.execute(
        """SELECT v.storage_key,v.content_sha256,v.byte_count
        FROM lending.client_payment_proof_versions v
        JOIN lending.client_payment_proofs p ON p.id=v.proof_id
        JOIN lending.loans l ON l.id=p.loan_id AND l.client_id=p.client_id
        JOIN lending.clients c ON c.id=p.client_id
        JOIN core.users u ON u.id=c.user_id AND u.id=p.created_by_user_id
        JOIN core.devices d ON d.id=p.created_device_id AND d.user_id=u.id
        WHERE v.uploaded_by_user_id=u.id AND v.uploaded_device_id=d.id"""
    ).fetchall()
    payroll = connection.execute(
        """SELECT count(*) FROM core.employee_payroll p
        JOIN core.employee_profiles e ON e.employee_id=p.employee_id
        JOIN core.users u ON u.id=e.employee_id
        JOIN core.user_roles ur ON ur.user_id=u.id
        JOIN core.roles r ON r.id=ur.role_id AND r.code='collector'
        WHERE p.created_by=u.id AND e.created_by=u.id"""
    ).fetchone()
    if len(proofs) != 1 or payroll is None or payroll[0] != 1:
        raise DrillError("Restored representative row relationships are incomplete.")
    store = PrivateEvidenceStore(private_root)
    for key, digest, size in proofs:
        if store.read(key, digest, size) != PDF:
            raise DrillError("Restored database-linked private content differs.")
    treasury_files = connection.execute(
        "select id,sha256,byte_count from treasury.evidence"
    ).fetchall()
    for key, digest, size in treasury_files:
        if store.read(key, digest, size) != PDF:
            raise DrillError(
                "Restored treasury database-linked private content differs."
            )
    funded = connection.execute("""select count(*) from treasury.applications a join treasury.receipts r on r.id=a.receipt_id and r.account_id=a.account_id
        join treasury.events e on e.id=r.event_id and e.account_id=r.account_id and e.ledger_context_id=r.ledger_context_id
        join lending.collection_transactions t on a.source_result->'transaction_ids' ? t.id::text
        where t.funding_source='treasury_receipt' and t.funding_receipt_id=r.id and t.funding_account_id=a.account_id and t.client_id=r.client_id
        and a.amount=40 and t.applied_amount=40 and r.applied_amount=40 and r.refunded_amount=100""").fetchone()[
        0
    ]
    claim_versions = connection.execute("""select count(*) from treasury.claim_versions v join treasury.claims c on c.id=v.claim_id
        join treasury.evidence e on e.id=v.evidence_id and e.account_id=c.account_id
        join treasury.receipts r on r.id=c.receipt_id and r.client_id=c.client_id and r.account_id=c.account_id""").fetchone()[
        0
    ]
    closed = connection.execute(
        "select count(*) from treasury.reconciliations where status='reconciled' and difference=0 and expected_balance=10700 and closed_snapshot is not null"
    ).fetchone()[0]
    linked = connection.execute(
        "select count(*) from treasury.source_links where source_kind='receipt_refund' and linked_amount=100"
    ).fetchone()[0]
    transfers = connection.execute(
        "select count(*) from treasury.transfers where source_event_id is not null and destination_event_id is not null"
    ).fetchone()[0]
    outcomes = connection.execute("""select count(*) from treasury.outcomes o join core.devices d on d.id=o.device_id and d.user_id=o.actor_id
        join treasury.accounts a on a.id=o.account_id where o.result->'result'->>'account_id'=a.id::text
        and o.result->'result'->>'ledger_context_id'=a.ledger_context_id::text""").fetchone()[
        0
    ]
    if (
        funded != 1
        or claim_versions != 2
        or closed != 1
        or linked != 1
        or transfers != 1
        or outcomes < 10
        or len(treasury_files) < 7
    ):
        raise DrillError(
            "Restored treasury funding/evidence/version/source/reconciliation/outcome relationships are incomplete."
        )
    surplus_counts = {}
    for kind in [
        "counts",
        "settlements",
        "cases",
        "credits",
        "requests",
        "actions",
        "acknowledgments",
        "exceptions",
        "openings",
        "entries",
        "resolutions",
    ]:
        surplus_counts[kind] = connection.execute(
            sql.SQL("select count(*) from treasury.{}").format(
                sql.Identifier("collector_" + kind)
            )
        ).fetchone()[0]
    relationships = connection.execute("""select count(*) from treasury.collector_actions a
       join treasury.collector_credits c on c.id=a.credit_id and c.ledger_context_id=a.ledger_context_id and c.collector_user_id=a.collector_user_id
       join treasury.events e on e.id=a.event_id and e.account_id=a.account_id
       join treasury.collector_acknowledgments ack on ack.action_id=a.id
       where a.payload->>'status'='paid' and c.payload->>'outstanding_amount'='6.00' and ack.payload->>'confirmation'='received' and e.direction='debit' and e.amount=4""").fetchone()[
        0
    ]
    if any(count < 1 for count in surplus_counts.values()) or relationships != 1:
        raise DrillError(
            "Restored populated Collector settlement/liability/own-acknowledgment relationships are incomplete."
        )
    payout_relationships = connection.execute("""select count(*) from treasury.loan_payouts p
        join treasury.events e on e.id=p.event_id and e.account_id=p.account_id and e.ledger_context_id=p.ledger_context_id and e.direction='debit' and e.amount=p.amount
        join treasury.source_links link on link.event_id=e.id and link.source_id=p.id and link.source_kind='loan_payout_funding'
        join lending.first_loan_releases r on r.funding_payout_id=p.id and r.loan_id=p.loan_id and r.received_amount=p.amount
        join lending.loan_contract_schedules s on s.id=r.schedule_id and s.loan_id=p.loan_id
        join lending.first_loan_credential_intents i on i.loan_id=p.loan_id
        where p.status='completed' and r.cash_amount is null and r.cash_evidence_reference is null
        and r.borrower_receipt_reference=p.payload->'borrower_receipt'->>'office_evidence_reference'
        and r.receipt_method=case when p.destination='collector' then 'cash' else 'gcash' end""").fetchone()[
        0
    ]
    if payout_relationships != 2:
        raise DrillError(
            "Restored loan payouts lost their protected debit/borrower receipt/schedule relationships."
        )
    source_store = PrivateEvidenceStore(
        private_root / "loan-payout-support" / "evidence"
    )
    office_files = connection.execute(
        "select request_id,content_sha256,byte_count from lending.office_review_evidence"
    ).fetchall()
    document_files = connection.execute(
        "select storage_key,content_sha256,byte_count from lending.first_loan_packet_documents"
    ).fetchall()
    for key, digest, size in [*office_files, *document_files]:
        source_store.read(key, digest, size)
    return {
        "loan_payout_completed_relationships": payout_relationships,
        "loan_payout_source_private_files": len(office_files) + len(document_files),
        "collector_surplus_tables": surplus_counts,
        "collector_surplus_paid_relationship": relationships,
        "borrower_loan_device_proof_file": len(proofs),
        "employee_profile_payroll": payroll[0],
        "treasury_private_files": len(treasury_files),
        "treasury_funded_application": funded,
        "treasury_claim_versions": claim_versions,
        "treasury_closed_reconciliation": closed,
        "treasury_actual_refund_link": linked,
        "treasury_completed_transfer": transfers,
        "treasury_private_outcomes": outcomes,
    }


def drop_owned_database(
    admin: psycopg.Connection, name: str, created: set[str]
) -> None:
    if name not in created or DATABASE_NAME.fullmatch(name) is None:
        raise DrillError("Cleanup refused a database not owned by this drill.")
    disposable._drop_database(admin, name)
    if disposable._database_exists(admin, name):
        raise DrillError("A task-owned recovery database was not removed.")


def run_drill(dsn: str, *, allow_disposable: bool, pg_bin: Path) -> dict[str, Any]:
    if not allow_disposable:
        raise DrillError("Recovery requires explicit --allow-disposable opt-in.")
    params = safe_admin_params(dsn)
    suffix = ".exe" if os.name == "nt" else ""
    dump, restore = (
        pg_bin.resolve() / (name + suffix) for name in ("pg_dump", "pg_restore")
    )
    if not dump.is_file() or not restore.is_file():
        raise DrillError(
            "The explicit PostgreSQL binary directory must contain pg_dump and pg_restore."
        )
    token = uuid4().hex[:24]
    source_name, restore_name = (
        f"spina_recovery_{kind}_{token}" for kind in ("source", "restore")
    )
    source_dsn = make_conninfo(**{**params, "dbname": source_name})
    restore_dsn = make_conninfo(**{**params, "dbname": restore_name})
    created: set[str] = set()
    started = time.monotonic()
    report: dict[str, Any] = {
        "kind": "synthetic_loopback_backup_restore",
        "status": "failed",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "production_backup_proven": False,
        "cleanup": {"databases": False, "temporary_files": False},
    }
    with isolated_pg_environment():
        with tempfile.TemporaryDirectory(prefix="spina-recovery-") as directory:
            workspace = Path(directory).resolve()
            source_files, restored_files, backup_files = (
                workspace / part
                for part in ("source-private", "restored-private", "backup-private")
            )
            backup_dump = workspace / "database.dump"
            admin_dsn = make_conninfo(**params)
            try:
                with psycopg.connect(admin_dsn, autocommit=True) as admin:
                    for name in (source_name, restore_name):
                        admin.execute(
                            sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                                sql.Identifier(name)
                            )
                        )
                        created.add(name)
                report["migrations"] = bootstrap(source_dsn)
                seed(source_dsn, source_files)
                with psycopg.connect(source_dsn) as source:
                    expected_rows = database_snapshot(source)
                    verify_relationships(source, source_files)
                expected_files = file_manifest(source_files)
                dump_env = pg_environment(params, source_name)
                restore_env = pg_environment(params, restore_name)
                expected_schema = schema_snapshot(dump, dump_env, source_dsn)
                backup_started = time.monotonic()
                run_pg(dump, ["--format=custom", "--file", str(backup_dump)], dump_env)
                shutil.copytree(source_files, backup_files)
                verify_files(backup_files, expected_files)
                backup_bytes = backup_dump.read_bytes()
                if not backup_bytes:
                    raise DrillError("Database backup is empty.")
                report["backup"] = {
                    "database_sha256": sha256(backup_bytes),
                    "database_bytes": len(backup_bytes),
                    "private_files": expected_files,
                    "seconds": round(time.monotonic() - backup_started, 3),
                }
                restore_started = time.monotonic()
                run_pg(
                    restore,
                    [
                        "--exit-on-error",
                        "--no-owner",
                        "--dbname",
                        restore_name,
                        str(backup_dump),
                    ],
                    restore_env,
                )
                shutil.copytree(backup_files, restored_files)
                verify_files(restored_files, expected_files)
                actual_schema = schema_snapshot(dump, restore_env, restore_dsn)
                if actual_schema != expected_schema:
                    raise DrillError(
                        "Restored schema differs from the migrated source."
                    )
                with psycopg.connect(restore_dsn) as restored:
                    verify_database(restored, expected_rows)
                    report["relationships"] = verify_relationships(
                        restored, restored_files
                    )
                    # Mutate a real restored row, ensure verification fails, then roll back.
                    restored.execute(
                        'UPDATE core.employee_profiles SET payload=payload || \'{"daily_rate":"1.00"}\'::jsonb'
                    )
                    try:
                        verify_database(restored, expected_rows)
                    except DrillError:
                        report["database_corruption_rejected"] = True
                    else:
                        raise DrillError(
                            "The database corruption negative probe was not rejected."
                        )
                    restored.rollback()
                    verify_database(restored, expected_rows)
                # Same-size corruption must fail the hash/content check, not just size.
                evidence_name = next(iter(expected_files))
                evidence = restored_files / evidence_name
                content = evidence.read_bytes()
                evidence.write_bytes(bytes([content[0] ^ 1]) + content[1:])
                try:
                    verify_files(restored_files, expected_files)
                except DrillError:
                    report["private_file_corruption_rejected"] = True
                else:
                    raise DrillError(
                        "The private-file corruption negative probe was not rejected."
                    )
                shutil.copyfile(backup_files / evidence_name, evidence)
                verify_files(restored_files, expected_files)
                report["restore"] = {
                    "schema_sha256": actual_schema,
                    "tables": expected_rows,
                    "private_content_verified": True,
                    "seconds": round(time.monotonic() - restore_started, 3),
                }
            finally:
                failures = []
                for name in sorted(created):
                    try:
                        with psycopg.connect(admin_dsn, autocommit=True) as admin:
                            drop_owned_database(admin, name, created)
                    except (psycopg.Error, DrillError, SystemExit):
                        failures.append(name)
                if failures:
                    raise DrillError(
                        "Cleanup failed for a task-owned recovery database; check the local administrative server."
                    )
                report["cleanup"]["databases"] = True
        if workspace.exists():
            raise DrillError("Task-owned temporary file cleanup failed.")
        report["cleanup"]["temporary_files"] = True
    report["status"] = "passed"
    report["seconds"] = round(time.monotonic() - started, 3)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-dsn-file", type=Path, required=True)
    parser.add_argument("--pg-bin", type=Path, required=True)
    parser.add_argument("--allow-disposable", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.admin_dsn_file.resolve():
        parser.error("Evidence output must not replace the administrative DSN file.")
    try:
        result = run_drill(
            args.admin_dsn_file.read_text(encoding="utf-8-sig").strip(),
            allow_disposable=args.allow_disposable,
            pg_bin=args.pg_bin,
        )
    except DrillError as error:
        result = {
            "kind": "synthetic_loopback_backup_restore",
            "status": "failed",
            "reason": str(error),
        }
    except (psycopg.Error, OSError, ValueError, RuntimeError, SystemExit):
        result = {
            "kind": "synthetic_loopback_backup_restore",
            "status": "failed",
            "reason": "Local recovery drill failed; no production recovery claim is established.",
        }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "production_backup_proven": False}))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
