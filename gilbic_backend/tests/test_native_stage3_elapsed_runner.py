"""Capture integrity and date admission are independent of any mocked clock."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import run_native_stage3_elapsed_validation as runner


def test_standalone_runner_can_import_its_lifecycle_tests_without_pythonpath(tmp_path):
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("GILBIC_", "SPINA_", "SUPABASE_", "PG"))
        and key not in {"PYTHONPATH", "DATABASE_URL", "POSTGRES_URL"}
    }
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            (
                "import runpy, sys; "
                "runpy.run_path(sys.argv[1], run_name='stage3_bootstrap_probe'); "
                "import test_native_stage3_elapsed_lifecycle_postgres"
            ),
            str(Path(runner.__file__).resolve()),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture
def capture(tmp_path):
    archive = tmp_path / "native-stage3.dump"
    archive.write_bytes(b"Synthetic integrity unit fixture")
    private = tmp_path / "private"
    private.mkdir()
    evidence = b"retained private receipt"
    (private / "receipt.bin").write_bytes(evidence)
    manifest = {
        "kind": "synthetic_native_stage3_closed_capture",
        "captured_day": "2030-01-01",
        "captured_at": "2030-01-01 01:00:00+00:00",
        "book": {"kind": "synthetic"},
        "period": {"status": "closed", "end_date": "2030-01-01"},
        "assessment": {
            "as_of_date": "2030-01-01",
            "measurement_snapshot": {
                "risk_review": {"stage_label": "stage_3_credit_impaired"}
            },
        },
        "dump_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "dump_size": archive.stat().st_size,
        "private_files": {
            "receipt.bin": {
                "bytes": len(evidence),
                "sha256": hashlib.sha256(evidence).hexdigest(),
            }
        },
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path, manifest


def test_elapsed_gate_requires_a_strictly_later_calendar_day(capture):
    _, manifest = capture
    assert not runner.elapsed_gate(manifest, date(2030, 1, 1))
    assert not runner.elapsed_gate(manifest, date(2029, 12, 31))
    assert runner.elapsed_gate(manifest, date(2030, 1, 2))


def test_capture_accepts_exact_dump_and_private_bytes(capture):
    path, expected = capture
    assert runner.read_capture(path) == expected


@pytest.mark.parametrize("changed", ["dump", "private", "escape", "stage"])
def test_capture_rejects_changed_or_outside_evidence(capture, changed):
    path, manifest = capture
    if changed == "dump":
        (path.parent / "native-stage3.dump").write_bytes(b"Changed archive")
    elif changed == "private":
        (path.parent / "private" / "receipt.bin").write_bytes(b"Changed receipt")
    elif changed == "escape":
        manifest["private_files"]["../receipt.bin"] = manifest["private_files"].pop(
            "receipt.bin"
        )
        path.write_text(json.dumps(manifest), encoding="utf-8")
    else:
        manifest["assessment"]["measurement_snapshot"]["risk_review"]["stage_label"] = (
            "stage_1_12_month"
        )
        path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises((ValueError, RuntimeError)):
        runner.read_capture(path)


@pytest.mark.parametrize("change", [None, "missing", "changed", "added", "removed"])
def test_positive_proof_requires_exact_captured_migration_sources(tmp_path, change):
    sql = tmp_path / "gilbic_backend" / "sql"
    sql.mkdir(parents=True)
    migration = sql / "0171_current_risk.sql"
    migration.write_text("SELECT 1;", encoding="utf-8")
    manifest = {
        "migration_sources": {
            migration.name: hashlib.sha256(migration.read_bytes()).hexdigest()
        }
    }
    if change == "missing":
        manifest.pop("migration_sources")
    elif change == "changed":
        migration.write_text("SELECT 2;", encoding="utf-8")
    elif change == "added":
        (sql / "0172_additional.sql").write_text("SELECT 3;", encoding="utf-8")
    elif change == "removed":
        migration.unlink()
    assert runner.source_provenance_matches(manifest, tmp_path) is (change is None)


def test_independent_unwind_is_gross_interest_less_net_interest_after_rounding():
    from native_stage3_elapsed_support import independent_interest

    # Gross 10 x .0015 rounds to .02; net 9 x .0015 rounds to .01.
    # Rounding allowance 1 x .0015 directly would lose the .01 difference.
    assert independent_interest("10", "1", ".0015", 1) == (
        Decimal("0.02"),
        Decimal("0.01"),
    )
