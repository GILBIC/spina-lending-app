"""Explicit, durable capture of genuine synthetic Stage 3 accounting history."""

import hashlib
import json
import os
import re
import shutil
from pathlib import Path

import psycopg
import run_release_recovery_drill as recovery
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
from run_native_stage3_elapsed_validation import migration_sources


def capture_if_requested(f, private_source: Path, assessment_id):
    requested = os.getenv("SPINA_CAPTURE_NATIVE_STAGE3")
    if not requested:
        return
    sources = migration_sources()
    assert os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") == "1"
    root = Path(__file__).resolve().parents[2].parent / "checkpoints"
    destination = Path(requested).resolve()
    assert destination.is_relative_to(root.resolve()) and destination != root.resolve()
    assert not destination.exists(), "A retained capture must never be replaced"
    assert shutil.disk_usage(root).free >= 100 * 1024**2
    params = conninfo_to_dict(os.environ["GILBIC_TEST_DATABASE_URL"])
    assert params.get("host") == params.get("hostaddr") == "127.0.0.1"
    assert params.get("port") == "55442"
    assert re.fullmatch(r"spina_treasury_validation_[a-f0-9]{24}", params["dbname"])
    assert params["dbname"] == f["conn"].info.dbname
    assert (
        params["dbname"]
        != conninfo_to_dict(os.environ["GILBIC_DATABASE_URL"])["dbname"]
    )
    assert not {"options", "service", "servicefile", "passfile"}.intersection(params)
    conn = f["conn"]
    actual = conn.execute(
        "SELECT clock_timestamp() AS captured_at, "
        "(clock_timestamp() AT TIME ZONE 'Asia/Manila')::date AS captured_day"
    ).fetchone()
    assert actual["captured_day"] == f["today"]
    assert (
        conn.execute(
            "SELECT status FROM accounting.fiscal_periods WHERE id=%s", (f["period"],)
        ).fetchone()["status"]
        == "closed"
    )
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
    conn.commit()
    destination.mkdir(parents=True)
    copied_private = destination / "private"
    shutil.copytree(private_source, copied_private)
    files = recovery.file_manifest(private_source)
    recovery.verify_files(copied_private, files)
    suffix = ".exe" if os.name == "nt" else ""
    binary = Path(os.environ["SPINA_POSTGRES_BIN"]) / ("pg_dump" + suffix)
    environment = recovery.pg_environment(params, params["dbname"])
    dsn = os.environ["GILBIC_TEST_DATABASE_URL"]
    archive = destination / "native-stage3.dump"
    schema = recovery.schema_snapshot(binary, environment, dsn)
    with psycopg.connect(dsn) as captured:
        rows = recovery.database_snapshot(captured)
        captured.row_factory = dict_row
        assessment = captured.execute(
            "SELECT * FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
            (assessment_id,),
        ).fetchone()
        assert (
            assessment["measurement_snapshot"]["risk_review"]["stage_label"]
            == "stage_3_credit_impaired"
        )
        book = captured.execute("SELECT * FROM accounting.book_identity").fetchone()
        assert book["kind"] == "synthetic"
        origin = captured.execute(
            "SELECT accounting.regular_original_origin(%s,%s) AS source",
            (f["loan_id"], f["today"]),
        ).fetchone()["source"]
        assert origin["ready"]
        period = captured.execute(
            "SELECT * FROM accounting.fiscal_periods WHERE id=%s", (f["period"],)
        ).fetchone()
        close = captured.execute(
            "SELECT * FROM accounting.period_close_postings WHERE fiscal_period_id=%s",
            (f["period"],),
        ).fetchall()
        manifest_state = captured.execute(
            "SELECT accounting.period_review_manifest_state(%s) AS state",
            (f["period"],),
        ).fetchone()["state"]
        assert manifest_state["current"]
    recovery.run_pg(binary, ["--format=custom", "--file", str(archive)], environment)
    assert archive.stat().st_size > 0
    assert sources and sources == migration_sources(), (
        "Migration sources changed during capture"
    )
    manifest = {
        "kind": "synthetic_native_stage3_closed_capture",
        **actual,
        "source_database": params["dbname"],
        "book": book,
        "loan_id": f["loan_id"],
        "client_id": f["client_id"],
        "payout_id": f["payout_id"],
        "actor_id": f["actor_id"],
        "device_id": f["device_id"],
        "wallet_id": f["wallet"],
        "release_date": f["release_day"],
        "period_id": f["period"],
        "assessment_id": assessment_id,
        "period": period,
        "assessment": assessment,
        "origin_at_capture": origin,
        "close_postings": close,
        "manifest_state": manifest_state,
        "database_snapshot": rows,
        "schema_snapshot": schema,
        "migration_sources": sources,
        "private_files": files,
        "original_private_root": str(private_source.resolve()),
        "dump_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "dump_size": archive.stat().st_size,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )
