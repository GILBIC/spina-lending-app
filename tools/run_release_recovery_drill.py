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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

# Historical disposable helpers are executable sibling modules. Support both
# direct CLI invocation and importing this tool from the repository test suite.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg
import run_client_onboarding_disposable_postgres_validation as onboarding
import run_stage5d17_disposable_postgres_validation as disposable
from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
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
        disposable.BOOTSTRAP_THROUGH = onboarding.BOOTSTRAP_THROUGH
        paths = [*disposable._migration_paths(), *onboarding.CIF_MIGRATIONS]
        current = sorted(disposable.SQL_ROOT.glob("[0-9][0-9][0-9][0-9]_*.sql"))
        if paths != current:
            raise DrillError(
                "Recovery bootstrap does not cover the current migration files."
            )
        disposable._install_supabase_auth_prerequisite(dsn)
        disposable._bootstrap_database(dsn)
        with psycopg.connect(dsn, autocommit=True) as connection:
            for path in onboarding.CIF_MIGRATIONS:
                connection.execute(path.read_bytes())
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


def verify_relationships(
    connection: psycopg.Connection, private_root: Path
) -> dict[str, int]:
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
    return {
        "borrower_loan_device_proof_file": len(proofs),
        "employee_profile_payroll": payroll[0],
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
