"""Restore genuine Stage 3 history and require a later real day for lifecycle proof."""

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import sys
import tempfile
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
for relative in (
    "gilbic_backend/src",
    "spina_backend_mobile/src",
    "gilbic_backend/tests",
    "tools",
):
    sys.path.insert(0, str(ROOT / relative))

import psycopg
import run_release_recovery_drill as recovery
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

OWNED_NAME = re.compile(r"spina_treasury_validation_[a-f0-9]{24}")


def migration_sources(root=ROOT):
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((root / "gilbic_backend" / "sql").glob("*.sql"))
    }


def source_provenance_matches(manifest, root=ROOT):
    captured = manifest.get("migration_sources")
    return bool(captured) and captured == migration_sources(root)


def read_capture(path: Path):
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if (
        manifest.get("kind") != "synthetic_native_stage3_closed_capture"
        or manifest["book"]["kind"] != "synthetic"
        or manifest["period"]["status"] != "closed"
        or manifest["assessment"]["measurement_snapshot"]["risk_review"]["stage_label"]
        != "stage_3_credit_impaired"
    ):
        raise ValueError("A genuine closed synthetic Stage 3 capture is required.")
    day = date.fromisoformat(manifest["captured_day"])
    instant = datetime.fromisoformat(manifest["captured_at"])
    if (
        instant.tzinfo is None
        or instant.astimezone(ZoneInfo("Asia/Manila")).date() != day
        or date.fromisoformat(manifest["period"]["end_date"]) != day
        or date.fromisoformat(manifest["assessment"]["as_of_date"]) != day
    ):
        raise ValueError("Capture, closed cutoff and actual capture date must agree.")
    archive = path.parent / "native-stage3.dump"
    if (
        archive.is_symlink()
        or archive.stat().st_size != manifest["dump_size"]
        or hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["dump_sha256"]
    ):
        raise ValueError("Retained Stage 3 archive bytes changed.")
    private = (path.parent / "private").resolve()
    for relative in manifest["private_files"]:
        target = (private / relative).resolve()
        if not target.is_relative_to(private) or target == private:
            raise ValueError("Private evidence path leaves the retained capture.")
    recovery.verify_files(private, manifest["private_files"])
    return manifest


def elapsed_gate(manifest, today):
    return today > date.fromisoformat(manifest["captured_day"])


def admin_params(path):
    content = path.read_text(encoding="utf-8").strip()
    dsn = json.loads(content)["dsn"] if content.startswith("{") else content
    params = conninfo_to_dict(dsn)
    if params.get("dbname") != "postgres" and not OWNED_NAME.fullmatch(
        params.get("dbname", "")
    ):
        raise ValueError(
            "Only explicit task-owned local database metadata is accepted."
        )
    params["dbname"] = "postgres"
    params = recovery.safe_admin_params(make_conninfo(**params))
    if (
        params.get("host") != "127.0.0.1"
        or params.get("hostaddr") != "127.0.0.1"
        or params.get("port") != "55442"
    ):
        raise ValueError("This proof is limited to the task-owned loopback port 55442.")
    return params


@contextmanager
def local_fence(params, database):
    original_connect = psycopg.connect
    original_socket_connect = socket.socket.connect
    original_socket_connect_ex = socket.socket.connect_ex

    def connect(conninfo="", **kwargs):
        supplied = conninfo_to_dict(conninfo)
        for key in recovery.ALLOWED_PARAMS | {
            "options",
            "service",
            "servicefile",
            "passfile",
        }:
            if key in kwargs:
                supplied[key] = str(kwargs[key])
        if (
            supplied.get("host") != "127.0.0.1"
            or supplied.get("hostaddr") != "127.0.0.1"
            or supplied.get("port") != "55442"
            or supplied.get("user") != params["user"]
            or supplied.get("dbname") not in {"postgres", database}
            or set(supplied) - recovery.ALLOWED_PARAMS
        ):
            raise ValueError("Connection is outside this isolated Stage 3 proof.")
        kwargs.setdefault(
            "options", "-c jit=off -c statement_timeout=60000 -c lock_timeout=15000"
        )
        return original_connect(conninfo, **kwargs)

    def socket_connect(instance, address):
        if (
            not isinstance(address, tuple)
            or address[0] not in {"127.0.0.1", "::1"}
            or address[1] != 55442
        ):
            raise ValueError(
                "Outbound access is disabled during this accounting proof."
            )
        return original_socket_connect(instance, address)

    def socket_connect_ex(instance, address):
        socket_connect(instance, address)
        return 0

    psycopg.connect = connect
    socket.socket.connect = socket_connect
    socket.socket.connect_ex = socket_connect_ex
    try:
        yield
    finally:
        psycopg.connect = original_connect
        socket.socket.connect = original_socket_connect
        socket.socket.connect_ex = original_socket_connect_ex


class ProofResults:
    def __init__(self):
        self.passed = 0
        self.skipped = 0
        self.failed = 0

    def pytest_runtest_logreport(self, report):
        if report.skipped:
            self.skipped += 1
        elif report.failed:
            self.failed += 1
        elif report.when == "call" and report.passed:
            self.passed += 1


def run(args, report):
    manifest_path = args.manifest.resolve()
    manifest = read_capture(manifest_path)
    params = admin_params(args.admin_dsn_file)
    suffix = ".exe" if os.name == "nt" else ""
    dump_binary = args.postgres_bin / ("pg_dump" + suffix)
    restore_binary = args.postgres_bin / ("pg_restore" + suffix)
    if not dump_binary.is_file() or not restore_binary.is_file():
        raise ValueError(
            "Explicit local PostgreSQL dump and restore tools are required."
        )
    scratch_root = ROOT.parent / "checkpoints" / "native-stage3-proof"
    scratch_root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(scratch_root).free < 250 * 1024**2:
        raise ValueError("Insufficient scratch capacity for the isolated restore.")
    name = "spina_treasury_validation_" + uuid4().hex[:24]
    dsn = make_conninfo(**(params | {"dbname": name}))
    report.update(
        captured_day=manifest["captured_day"], capture_sha256=manifest["dump_sha256"]
    )
    with (
        local_fence(params, name),
        recovery.isolated_pg_environment(),
        tempfile.TemporaryDirectory(prefix="proof-", dir=scratch_root) as temporary,
    ):
        scratch = Path(temporary).resolve()
        assert (
            scratch.is_relative_to(scratch_root.resolve())
            and scratch != scratch_root.resolve()
        )
        with psycopg.connect(make_conninfo(**params), autocommit=True) as admin:
            admin.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                    sql.Identifier(name)
                )
            )
            try:
                recovery.run_pg(
                    restore_binary,
                    [
                        "--exit-on-error",
                        "--no-owner",
                        "--dbname",
                        name,
                        str(manifest_path.parent / "native-stage3.dump"),
                    ],
                    recovery.pg_environment(params, name),
                )
                with psycopg.connect(dsn) as conn:
                    recovery.verify_database(conn, manifest["database_snapshot"])
                    conn.row_factory = dict_row
                    today = conn.execute(
                        "SELECT (clock_timestamp() AT TIME ZONE 'Asia/Manila')::date AS day"
                    ).fetchone()["day"]
                    assert conn.execute(
                        "SELECT accounting.period_elapsed_loan_assessment_exact(%s,%s) AS exact",
                        (manifest["period_id"], manifest["loan_id"]),
                    ).fetchone()["exact"]
                    assert conn.execute(
                        "SELECT accounting.period_review_manifest_state(%s) AS value",
                        (manifest["period_id"],),
                    ).fetchone()["value"]["current"]
                if (
                    recovery.schema_snapshot(
                        dump_binary, recovery.pg_environment(params, name), dsn
                    )
                    != manifest["schema_snapshot"]
                ):
                    raise ValueError(
                        "Restored Stage 3 schema differs from its retained capture."
                    )
                private = scratch / "private"
                shutil.copytree(manifest_path.parent / "private", private)
                recovery.verify_files(private, manifest["private_files"])
                report.update(
                    restore_integrity="VERIFIED",
                    actual_manila_day=str(today),
                    source_provenance=(
                        "VERIFIED"
                        if source_provenance_matches(manifest)
                        else "NOT VERIFIED"
                    ),
                )
                if (
                    not args.integrity_only
                    and report["source_provenance"] != "VERIFIED"
                ):
                    report["reason"] = (
                        "Captured migration source hashes are absent or differ from current source. "
                        "A new genuine capture of the final schema is required for positive proof."
                    )
                    return 1
                if args.integrity_only or not elapsed_gate(manifest, today):
                    report["reason"] = (
                        "Integrity only requested; elapsed lifecycle was not run."
                        if args.integrity_only
                        else "A real Manila calendar day after the retained Stage 3 cutoff is required."
                    )
                    return 0 if args.integrity_only else 2
                retained_environment = dict(os.environ)
                try:
                    for key in list(os.environ):
                        if key.startswith(("GILBIC_", "SPINA_", "SUPABASE_")):
                            os.environ.pop(key)
                    os.environ.update(
                        GILBIC_DATABASE_URL=dsn,
                        GILBIC_TEST_DATABASE_URL=dsn,
                        SPINA_ALLOW_DISPOSABLE_DATABASE="1",
                        SPINA_STAGE3_ELAPSED_PROOF="1",
                        SPINA_STAGE3_HISTORY_MANIFEST=str(manifest_path),
                        SPINA_STAGE3_RESTORED_PRIVATE=str(private),
                        SPINA_STAGE3_PUBLIC_OUTPUT=str(args.report.parent.resolve()),
                    )
                    import pytest

                    results = ProofResults()
                    code = pytest.main(
                        [
                            "-q",
                            "-p",
                            "no:cacheprovider",
                            "--basetemp",
                            str(scratch / "pytest"),
                            str(
                                ROOT
                                / "gilbic_backend/tests/test_native_stage3_elapsed_lifecycle_postgres.py"
                            ),
                        ],
                        plugins=[results],
                    )
                    report.update(
                        passed=results.passed,
                        skipped=results.skipped,
                        failed=results.failed,
                        source_provenance=(
                            "VERIFIED"
                            if source_provenance_matches(manifest)
                            else "NOT VERIFIED"
                        ),
                    )
                    if (
                        code == 0
                        and results.passed == 2
                        and results.skipped == results.failed == 0
                        and report["source_provenance"] == "VERIFIED"
                    ):
                        report["aged_lifecycle"] = "VERIFIED"
                        return 0
                    report["reason"] = (
                        "Both positive aged lifecycle cases must execute and pass; skips never establish proof."
                    )
                    return 1
                finally:
                    os.environ.clear()
                    os.environ.update(retained_environment)
            finally:
                assert OWNED_NAME.fullmatch(name)
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--admin-dsn-file", type=Path, required=True)
    parser.add_argument("--postgres-bin", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--integrity-only", action="store_true")
    args = parser.parse_args()
    if args.report.resolve().is_relative_to(args.manifest.resolve().parent):
        parser.error("Proof reports must be outside the immutable capture directory.")
    report = {
        "restore_integrity": "NOT VERIFIED",
        "aged_lifecycle": "NOT VERIFIED",
        "source_provenance": "NOT VERIFIED",
        "passed": 0,
        "skipped": 0,
        "failed": 0,
    }
    try:
        code = run(args, report)
    except (
        AssertionError,
        ValueError,
        KeyError,
        OSError,
        psycopg.Error,
        recovery.DrillError,
    ) as error:
        report["reason"] = (
            f"Proof stopped: {type(error).__name__}. Inspect the local test log; no lifecycle success is claimed."
        )
        code = 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
