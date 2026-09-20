from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from tools.build_release_candidate_evidence import HUMAN_GATES, JOBS, build_report

ROOT = Path(__file__).resolve().parents[1]


def test_missing_inputs_produce_blocked_report_instead_of_crashing(tmp_path):
    output = tmp_path / "candidate.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_release_candidate_evidence.py"),
            "--expected-sha",
            "a" * 40,
            "--inputs",
            str(tmp_path / "missing.json"),
            "--output",
            str(output),
            "--repository",
            str(ROOT),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    assert output.exists(), (
        "A missing evidence input must still produce a useful blocked report"
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "BLOCKED"
    assert report["production_ready"] is False
    assert report["blocked_gates"]


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_git(repository, *arguments):
    return subprocess.check_output(
        ["git", *arguments], cwd=repository, stderr=subprocess.DEVNULL, text=True
    ).strip()


@pytest.fixture
def complete_evidence(tmp_path):
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "gilbic_backend/sql").mkdir(parents=True)
    migration = repository / "gilbic_backend/sql/0001_synthetic.sql"
    migration.write_text("SELECT 1;\n", encoding="utf-8")
    (repository / "docs/release").mkdir(parents=True)
    tools = ("ruff", "pyright", "bandit", "gitleaks", "pip_audit", "format")
    write_json(
        repository / "docs/release/scanner-baseline.json",
        {"schema_version": 1, "tools": {name: {} for name in tools}},
    )
    run_git(repository, "init", "--initial-branch=main")
    run_git(repository, "add", ".")
    run_git(
        repository,
        "-c",
        "user.name=Synthetic Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "core.hooksPath=.no-hooks",
        "commit",
        "-m",
        "Synthetic candidate",
    )
    source = run_git(repository, "rev-parse", "HEAD")
    tree = run_git(repository, "rev-parse", "HEAD^{tree}")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    paths = {
        name: evidence / f"{name}.json"
        for name in (
            "ci_run",
            "ci_artifacts",
            "android_report",
            "recovery_report",
            "scanner_report",
            "performance_report",
            "bindings",
            "attestations",
        )
    }
    paths["android_apk"] = evidence / "candidate.apk"
    paths["scanner_reports_dir"] = evidence / "raw"
    paths["scanner_reports_dir"].mkdir()
    date = "2026-01-01T00:00:00Z"
    run_url = "https://github.com/GILBIC/spina-lending-app/actions/runs/123"
    run = {
        "headSha": source,
        "status": "completed",
        "conclusion": "success",
        "workflowName": "SPINA CI",
        "url": run_url,
        "databaseId": 123,
        "jobs": [
            {
                "name": name,
                "databaseId": number,
                "status": "completed",
                "conclusion": "success",
            }
            for number, name in enumerate(sorted(JOBS), 1)
        ],
    }
    write_json(paths["ci_run"], run)
    write_json(
        paths["ci_artifacts"],
        {
            "artifacts": [
                {
                    "id": number,
                    "name": name + source,
                    "expired": False,
                    "size_in_bytes": 100,
                    "workflow_run": {"id": 123, "head_sha": source},
                }
                for number, name in enumerate(
                    (
                        "spina-ci-backend-",
                        "Spina-Android-internal-",
                        "spina-ci-financial-",
                    ),
                    1,
                )
            ]
        },
    )
    metadata = {
        "source_sha": source,
        "build_mode": "release",
        "application_id": "com.spinalending.gilbic_mobile",
        "api_url": "https://synthetic.example",
        "version_name": "0.4.0",
        "version_code": 4,
        "pubspec_lock_sha256": "b" * 64,
        "expected_certificate_sha256": "c" * 64,
        "production_ready": False,
    }
    with zipfile.ZipFile(paths["android_apk"], "w") as archive:
        archive.writestr("assets/spina-build.json", json.dumps(metadata))
        for name in (
            "AndroidManifest.xml",
            "classes.dex",
            "lib/arm64-v8a/libflutter.so",
            "lib/x86_64/libflutter.so",
            "lib/arm64-v8a/libsqlcipher.so",
            "lib/x86_64/libsqlcipher.so",
        ):
            archive.writestr(name, "synthetic fixture")
    android = {
        **metadata,
        "apk_sha256": sha256(paths["android_apk"]),
        "apk_bytes": paths["android_apk"].stat().st_size,
        "certificate_sha256": "c" * 64,
        "debuggable": False,
        "status": "signed_candidate",
    }
    write_json(paths["android_report"], android)
    backup = {
        "kind": "synthetic_loopback_backup_restore",
        "status": "passed",
        "started_at": date,
        "production_backup_proven": False,
        "migrations": [{"file": migration.name, "sha256": sha256(migration)}],
        "backup": {
            "database_sha256": "a" * 64,
            "database_bytes": 100,
            "private_files": {"synthetic.pdf": {"sha256": "a" * 64, "bytes": 30}},
        },
        "restore": {
            "schema_sha256": "a" * 64,
            "private_content_verified": True,
            "tables": {
                name: {"rows": 1, "sha256": "b" * 64}
                for name in (
                    "core.users",
                    "core.devices",
                    "lending.clients",
                    "lending.loans",
                    "lending.client_payment_proof_versions",
                    "core.employee_profiles",
                    "core.employee_payroll",
                )
            },
        },
        "relationships": {
            "borrower_loan_device_proof_file": 1,
            "employee_profile_payroll": 1,
        },
        "database_corruption_rejected": True,
        "private_file_corruption_rejected": True,
        "cleanup": {"databases": True, "temporary_files": True},
    }
    write_json(paths["recovery_report"], backup)
    raw = paths["scanner_reports_dir"]
    for filename, value in {
        "ruff.json": [],
        "pyright.json": {"version": "1.1.414", "generalDiagnostics": []},
        "bandit.json": {"errors": [], "results": []},
        "gitleaks-redacted.json": [],
        "pip-audit.json": {
            "dependencies": [
                {"name": "synthetic-package", "version": "1.0.0", "vulns": []}
            ]
        },
    }.items():
        write_json(raw / filename, value)
    (raw / "ruff-format.txt").write_text(
        "0 files already formatted\n", encoding="utf-8"
    )
    write_json(
        paths["scanner_report"],
        {
            "kind": "scanner_regression_check",
            "status": "passed",
            "security_clearance": False,
            "tools": {
                name: {
                    "baseline_count": 0,
                    "current_count": 0,
                    "added": {},
                    "removed": {},
                }
                for name in tools
            },
        },
    )
    measures = [
        (path, 200)
        for path in (
            "/health/live",
            "/health/ready",
            "/api/v1/auth/me",
            "/api/v1/client/loans",
            "/api/v1/collector/cash-accountability",
            "/api/v1/employee-operations/workspace",
            "/api/v1/management/dashboard-overview",
        )
    ]
    measures.append(("/api/v1/management/dashboard-overview", 403))
    performance = {
        "schema_version": 1,
        "measurement_only": True,
        "production_acceptance": False,
        "outcome": "measured",
        "measured_at": date,
        "source_commit": source,
        "source_tree_dirty": False,
        "backend_revision_verified": False,
        "completed_requests": 80,
        "threshold_assessment": "met",
        "thresholds": {"max_p95_ms": 1000, "max_error_rate": 0},
        "synthetic_workload": {
            "synthetic": True,
            "clients": 10,
            "active_loans": 10,
            "route_entries": 10,
            "collectors": 3,
            "employees": 3,
        },
        "scenarios": [
            {
                "path": path,
                "expected_status": status,
                "method": "GET",
                "requests": 10,
                "status_counts": {str(status): 10},
                "error_counts": {},
                "error_rate": 0,
                "p50_ms": 1,
                "p95_ms": 2,
                "max_ms": 3,
            }
            for path, status in measures
        ],
    }
    write_json(paths["performance_report"], performance)
    bindings = {
        name: {
            "report_sha256": sha256(paths[name]),
            "source_sha": source,
            "source_tree": tree,
            "captured_at": date,
            "capture_ref": run_url,
        }
        for name in ("recovery_report", "scanner_report", "performance_report")
    }
    write_json(paths["bindings"], bindings)
    attestations = {
        name: {
            "outcome": "accepted",
            "source_sha": source,
            "reviewed_at": date,
            "review_ref": "https://github.com/GILBIC/spina-lending-app/issues/123",
            "evidence_sha256": {
                support: sha256(paths[support]) for support in supports
            },
        }
        for name, supports in HUMAN_GATES.items()
    }
    attestations["performance_acceptance"].update(
        backend_source_sha=source, environment_class="isolated_production_like"
    )
    write_json(paths["attestations"], attestations)
    inputs = evidence / "inputs.json"
    write_json(
        inputs,
        {
            "schema_version": 1,
            "template_only": False,
            **{name: path.name for name, path in paths.items()},
        },
    )
    return repository, source, inputs, paths


def blocked(report):
    return {item["gate"] for item in report["blocked_gates"]}


def test_complete_linked_evidence_is_only_ready_for_human_review(complete_evidence):
    repository, source, inputs, paths = complete_evidence
    report = build_report(source, inputs, repository)
    assert report["blocked_gates"] == []
    assert report["candidate_ready_for_management_review"] is True
    assert report["production_ready"] is False
    assert report["remote_records_revalidated"] is False
    assert report["files"]["android_apk"]["sha256"] == sha256(paths["android_apk"])
    assert all(
        item["kind"] == "declared_human_acceptance"
        for item in report["human_attestations"]
    )


@pytest.mark.parametrize(
    "mutation", ["wrong_sha", "in_progress", "wrong_job", "no_artifacts"]
)
def test_ci_needs_matching_completed_jobs_and_real_artifact_records(
    complete_evidence, mutation
):
    repository, source, inputs, paths = complete_evidence
    run = json.loads(paths["ci_run"].read_text(encoding="utf-8"))
    if mutation == "wrong_sha":
        run["headSha"] = "f" * 40
    elif mutation == "in_progress":
        run["jobs"][0]["status"] = "in_progress"
    elif mutation == "wrong_job":
        run["jobs"][0]["name"] = "Unrelated green check"
    else:
        write_json(paths["ci_artifacts"], {"artifacts": []})
    write_json(paths["ci_run"], run)
    assert "ci" in blocked(build_report(source, inputs, repository))


def test_tampered_apk_cannot_reuse_an_old_verifier_report(complete_evidence):
    repository, source, inputs, paths = complete_evidence
    with paths["android_apk"].open("ab") as stream:
        stream.write(b"tampered")
    assert "android_package" in blocked(build_report(source, inputs, repository))


def test_android_report_cannot_relabel_another_source_build(complete_evidence):
    repository, source, inputs, paths = complete_evidence
    android = json.loads(paths["android_report"].read_text(encoding="utf-8"))
    android["source_sha"] = "f" * 40
    write_json(paths["android_report"], android)
    assert "android_package" in blocked(build_report(source, inputs, repository))


def test_debug_signing_cannot_close_release_readiness(complete_evidence):
    repository, source, inputs, paths = complete_evidence
    android = json.loads(paths["android_report"].read_text(encoding="utf-8"))
    android.update(
        build_mode="debug",
        status="internal_test_only",
        debuggable=True,
        expected_certificate_sha256=None,
    )
    write_json(paths["android_report"], android)
    assert "android_release_signing" in blocked(
        build_report(source, inputs, repository)
    )


@pytest.mark.parametrize(
    "record", ["scanner_report", "recovery_report", "performance_report"]
)
def test_a_passed_checkbox_is_not_supporting_evidence(complete_evidence, record):
    repository, source, inputs, paths = complete_evidence
    write_json(paths[record], {"passed": True})
    report = build_report(source, inputs, repository)
    gate = {
        "scanner_report": "scanner_regression",
        "recovery_report": "backup_restore",
        "performance_report": "performance",
    }[record]
    assert gate in blocked(report)
    assert report["candidate_ready_for_management_review"] is False


def test_missing_human_acceptance_is_not_inferred_from_green_automation(
    complete_evidence,
):
    repository, source, inputs, paths = complete_evidence
    attestations = json.loads(paths["attestations"].read_text(encoding="utf-8"))
    del attestations["android_device"]
    write_json(paths["attestations"], attestations)
    assert "human_android_device" in blocked(build_report(source, inputs, repository))


def test_dirty_or_synthetic_source_never_qualifies(complete_evidence):
    repository, source, inputs, _paths = complete_evidence
    (repository / "untracked.txt").write_text("dirty", encoding="utf-8")
    assert "source" in blocked(build_report(source, inputs, repository))
    assert "source" in blocked(build_report("0" * 40, inputs, repository))


def test_public_output_does_not_copy_private_metadata(complete_evidence):
    repository, source, inputs, paths = complete_evidence
    attestations = json.loads(paths["attestations"].read_text(encoding="utf-8"))
    attestations["android_device"]["private_employee_name"] = "DO-NOT-PUBLISH"
    write_json(paths["attestations"], attestations)
    report = build_report(source, inputs, repository)
    assert "DO-NOT-PUBLISH" not in json.dumps(report)
    assert str(paths["android_apk"]) not in json.dumps(report)
