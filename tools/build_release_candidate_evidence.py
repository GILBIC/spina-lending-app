"""Check linked candidate evidence; never grant production release approval."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_release_scanner_regressions as scanners

JOBS = {
    "Backend, quality, and security",
    "Portal, Flutter, and Android",
    "Financial and disposable PostgreSQL",
}
INPUTS = {
    "ci_run",
    "ci_artifacts",
    "android_report",
    "android_apk",
    "recovery_report",
    "scanner_report",
    "scanner_reports_dir",
    "performance_report",
    "bindings",
    "attestations",
}
HUMAN_GATES = {
    "android_device": {"android_report", "android_apk", "ci_run"},
    "windows_desktop": {"ci_run"},
    "web_roles": {"ci_run"},
    "security_review": {"scanner_report", "ci_run"},
    "repository_governance": {"ci_run"},
    "operational_setup": {"recovery_report"},
    "performance_acceptance": {"performance_report"},
}
SHA = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"[0-9a-f]{64}")
RUN_URL = re.compile(
    r"https://github\.com/GILBIC/spina-lending-app/actions/runs/[1-9][0-9]*"
)


class EvidenceError(ValueError):
    pass


def require(condition: Any, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8-sig"))
    require(isinstance(result, dict), "Expected a JSON object")
    return result


def git(repository: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=repository, text=True, stderr=subprocess.DEVNULL
    ).strip()


def aware_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return date.tzinfo is not None and date <= datetime.now(timezone.utc)
    except ValueError:
        return False


def reference(value: Any) -> bool:
    if not isinstance(value, str) or len(value) > 1000:
        return False
    try:
        uri = urlsplit(value)
        return bool(
            uri.scheme == "https"
            and uri.hostname
            and not uri.username
            and not uri.password
            and not uri.query
        )
    except ValueError:
        return False


def positive(value: Any) -> bool:
    return type(value) in {int, float} and math.isfinite(value) and value > 0


def validate_ci(run: dict[str, Any], artifacts: dict[str, Any], expected: str) -> None:
    require(run.get("headSha") == expected, "CI run belongs to another source SHA")
    require(
        run.get("workflowName") == "SPINA CI", "Expected the unified SPINA CI workflow"
    )
    require(
        run.get("status") == "completed" and run.get("conclusion") == "success",
        "CI is incomplete or unsuccessful",
    )
    require(
        RUN_URL.fullmatch(str(run.get("url", ""))),
        "CI run reference is missing or invalid",
    )
    require(
        str(run.get("databaseId")) == run["url"].rsplit("/", 1)[1],
        "CI run identity disagrees with its URL",
    )
    jobs = run.get("jobs")
    if not isinstance(jobs, list):
        raise EvidenceError("CI job evidence is missing")
    names = [job.get("name") for job in jobs if isinstance(job, dict)]
    require(
        len(names) == len(jobs)
        and len(names) == len(set(names))
        and JOBS <= set(names),
        "Required CI job names are missing or duplicated",
    )
    for job in jobs:
        if job["name"] in JOBS:
            require(
                job.get("status") == "completed"
                and job.get("conclusion") == "success"
                and positive(job.get("databaseId")),
                "A required CI job is incomplete or unsuccessful",
            )
    records = artifacts.get("artifacts")
    if not isinstance(records, list) or not records:
        raise EvidenceError("CI artifacts are missing")
    required = {
        f"spina-ci-backend-{expected}",
        f"Spina-Android-internal-{expected}",
        f"spina-ci-financial-{expected}",
    }
    available = set()
    for artifact in records:
        if isinstance(artifact, dict) and artifact.get("name") in required:
            require(
                artifact.get("expired") is False
                and positive(artifact.get("id"))
                and positive(artifact.get("size_in_bytes")),
                "A required CI artifact is expired or empty",
            )
            workflow = artifact.get("workflow_run", {})
            require(
                workflow.get("head_sha") == expected
                and workflow.get("id") == run["databaseId"],
                "CI artifact belongs to another run or source SHA",
            )
            available.add(artifact["name"])
    require(
        available == required,
        "Exact-source backend, Android and financial CI artifacts are required",
    )


def validate_android(report: dict[str, Any], apk: Path, expected: str) -> None:
    require(
        report.get("source_sha") == expected,
        "Android report belongs to another source SHA",
    )
    require(
        report.get("application_id") == "com.spinalending.gilbic_mobile",
        "Android application identity differs",
    )
    require(
        report.get("apk_sha256") == digest(apk)
        and report.get("apk_bytes") == apk.stat().st_size,
        "APK bytes differ from their verification report",
    )
    with zipfile.ZipFile(apk) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "APK has duplicate archive entries")
        require(
            {
                "AndroidManifest.xml",
                "classes.dex",
                "assets/spina-build.json",
                "lib/arm64-v8a/libflutter.so",
                "lib/x86_64/libflutter.so",
                "lib/arm64-v8a/libsqlcipher.so",
                "lib/x86_64/libsqlcipher.so",
            }
            <= set(names),
            "APK native/package contents are incomplete",
        )
        metadata = json.loads(archive.read("assets/spina-build.json"))
        require(isinstance(metadata, dict), "APK source provenance is malformed")
    for key in (
        "source_sha",
        "build_mode",
        "application_id",
        "api_url",
        "version_name",
        "version_code",
        "pubspec_lock_sha256",
        "expected_certificate_sha256",
    ):
        require(
            key in metadata and metadata[key] == report.get(key),
            "APK embedded provenance disagrees with its verification report",
        )
    require(
        report.get("production_ready") is False,
        "An APK verifier must not claim production approval",
    )
    require(
        report.get("build_mode") in {"debug", "release"}
        and DIGEST.fullmatch(str(report.get("certificate_sha256", ""))),
        "Android verification lacks build/signing facts",
    )
    require(
        report.get("status")
        == (
            "signed_candidate"
            if report["build_mode"] == "release"
            else "internal_test_only"
        ),
        "Android build classification is inconsistent",
    )
    require(
        report.get("debuggable") is (report["build_mode"] == "debug"),
        "Android debug status is inconsistent",
    )


def validate_recovery(report: dict[str, Any], repository: Path, expected: str) -> None:
    require(
        report.get("kind") == "synthetic_loopback_backup_restore"
        and report.get("status") == "passed",
        "Successful isolated backup/restore evidence is missing",
    )
    require(
        report.get("production_backup_proven") is False
        and aware_date(report.get("started_at")),
        "Recovery scope/time is invalid",
    )
    paths = sorted(
        (repository / "gilbic_backend/sql").glob("[0-9][0-9][0-9][0-9]_*.sql")
    )
    migrations = report.get("migrations")
    if not paths or not isinstance(migrations, list) or len(paths) != len(migrations):
        raise EvidenceError("Recovery migration inventory is incomplete")
    for path, migration in zip(paths, migrations, strict=True):
        require(
            isinstance(migration, dict) and migration.get("file") == path.name,
            "Recovery migration order differs",
        )
        # CI uses Git's LF blobs; an earlier Windows drill may contain CRLF bytes.
        blob = subprocess.check_output(
            ["git", "show", f"{expected}:gilbic_backend/sql/{path.name}"],
            cwd=repository,
            stderr=subprocess.DEVNULL,
        )
        require(
            migration.get("sha256") in {digest(path), hashlib.sha256(blob).hexdigest()},
            "Recovery migration contents differ from the candidate",
        )
    backup, restore = report.get("backup", {}), report.get("restore", {})
    require(
        DIGEST.fullmatch(str(backup.get("database_sha256", "")))
        and positive(backup.get("database_bytes")),
        "Recovery database backup hash/size is missing",
    )
    files = backup.get("private_files")
    require(
        isinstance(files, dict)
        and files
        and all(
            isinstance(item, dict)
            and DIGEST.fullmatch(str(item.get("sha256", "")))
            and positive(item.get("bytes"))
            for item in files.values()
        ),
        "Recovery private-file hash evidence is missing",
    )
    require(
        DIGEST.fullmatch(str(restore.get("schema_sha256", "")))
        and restore.get("private_content_verified") is True,
        "Restored schema or private content was not verified",
    )
    tables = restore.get("tables", {})
    for name in (
        "core.users",
        "core.devices",
        "lending.clients",
        "lending.loans",
        "lending.client_payment_proof_versions",
        "core.employee_profiles",
        "core.employee_payroll",
    ):
        item = tables.get(name, {})
        require(
            positive(item.get("rows"))
            and DIGEST.fullmatch(str(item.get("sha256", ""))),
            "Recovery representative table hashes/rows are missing",
        )
    require(
        report.get("relationships")
        == {"borrower_loan_device_proof_file": 1, "employee_profile_payroll": 1},
        "Recovery linked-record evidence is incomplete",
    )
    require(
        report.get("database_corruption_rejected") is True
        and report.get("private_file_corruption_rejected") is True,
        "Recovery corruption controls were not proven",
    )
    require(
        report.get("cleanup") == {"databases": True, "temporary_files": True},
        "Recovery cleanup was not completed",
    )


def validate_performance(report: dict[str, Any]) -> None:
    require(
        report.get("schema_version") == 1
        and report.get("measurement_only") is True
        and report.get("production_acceptance") is False,
        "Performance scope is malformed",
    )
    require(
        report.get("outcome") == "measured" and aware_date(report.get("measured_at")),
        "Performance measurements are missing or failed",
    )
    workload = report.get("synthetic_workload", {})
    require(
        workload.get("synthetic") is True
        and all(
            positive(workload.get(key))
            for key in (
                "clients",
                "active_loans",
                "route_entries",
                "collectors",
                "employees",
            )
        ),
        "Representative synthetic workload counts are missing",
    )
    rows = report.get("scenarios")
    if not isinstance(rows, list) or not rows:
        raise EvidenceError("Performance scenarios are missing")
    required = {
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
    }
    required.add(("/api/v1/management/dashboard-overview", 403))
    observed, total = set(), 0
    for row in rows:
        require(
            isinstance(row, dict)
            and row.get("method") == "GET"
            and positive(row.get("requests")),
            "Performance request evidence is malformed",
        )
        observed.add((row.get("path"), row.get("expected_status")))
        require(
            row.get("status_counts") == {str(row["expected_status"]): row["requests"]}
            and row.get("error_counts") == {}
            and row.get("error_rate") == 0,
            "Performance requests include errors or inconsistent counts",
        )
        require(
            all(
                type(row.get(key)) in {int, float}
                and math.isfinite(row[key])
                and row[key] >= 0
                for key in ("p50_ms", "p95_ms", "max_ms")
            ),
            "Performance latency measurements are missing",
        )
        require(
            row["p50_ms"] <= row["p95_ms"] <= row["max_ms"],
            "Performance latency ordering is inconsistent",
        )
        total += row["requests"]
    require(
        required <= observed and report.get("completed_requests") == total,
        "Performance role/read/denial coverage is incomplete",
    )
    thresholds = report.get("thresholds", {})
    require(
        report.get("threshold_assessment") == "met"
        and positive(thresholds.get("max_p95_ms"))
        and thresholds.get("max_error_rate") == 0,
        "Performance acceptance thresholds are absent or not met",
    )
    require(
        all(row["p95_ms"] <= thresholds["max_p95_ms"] for row in rows),
        "Performance measurements exceed their stated latency budget",
    )


def validate_binding(
    name: str,
    bindings: dict[str, Any],
    record: dict[str, Any],
    report_hash: str,
    expected: str,
    tree: str,
    repository: Path,
) -> None:
    item = bindings.get(name, {})
    require(
        isinstance(item, dict) and item.get("report_sha256") == report_hash,
        "Evidence capture hash is missing or does not match this report",
    )
    require(
        aware_date(item.get("captured_at")) and reference(item.get("capture_ref")),
        "Evidence capture date/reference is missing",
    )
    source = item.get("source_sha", "")
    require(
        isinstance(source, str) and SHA.fullmatch(source) and source != "0" * 40,
        "Evidence original source SHA is missing",
    )
    if "source_commit" in record:
        require(
            record["source_commit"] == source
            and record.get("source_tree_dirty") is False,
            "Evidence records a different or dirty source checkout",
        )
    require(
        item.get("source_tree") == tree
        and git(repository, "rev-parse", f"{source}^{{tree}}") == tree,
        "Evidence original source tree differs from the candidate",
    )
    # An older commit is retained honestly when its entire Git tree is identical.
    require(
        source == expected or item.get("source_tree") == tree,
        "Evidence source binding is stale",
    )


def build_report(expected: str, inputs_path: Path, repository: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": 1,
        "expected_source_sha": expected if SHA.fullmatch(expected) else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "BLOCKED",
        "production_ready": False,
        "candidate_ready_for_management_review": False,
        "evidence_consistency_only": True,
        "remote_records_revalidated": False,
        "checks": [],
        "files": {},
        "human_attestations": [],
    }
    data: dict[str, Any] = {}
    paths: dict[str, Path] = {}
    tree = ""

    def check(name: str, operation) -> None:
        try:
            operation()
            report["checks"].append({"gate": name, "status": "passed"})
        except (
            EvidenceError,
            OSError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            subprocess.CalledProcessError,
            zipfile.BadZipFile,
        ):
            # Only our fixed explanatory messages are safe for public output.
            error = sys.exception()
            detail = (
                str(error)
                if isinstance(error, EvidenceError)
                else "Missing, malformed or inaccessible supporting evidence"
            )
            report["checks"].append(
                {"gate": name, "status": "blocked", "detail": detail}
            )

    def source() -> None:
        nonlocal tree
        require(
            bool(SHA.fullmatch(expected)) and expected != "0" * 40,
            "A real full candidate SHA is required",
        )
        require(
            git(repository, "rev-parse", "HEAD") == expected,
            "Checkout HEAD differs from the requested candidate",
        )
        require(
            not git(repository, "status", "--porcelain", "--untracked-files=all"),
            "Candidate checkout is dirty",
        )
        tree = git(repository, "rev-parse", "HEAD^{tree}")
        report["source_tree"] = tree

    def load_inputs() -> None:
        inputs = read_object(inputs_path)
        require(
            inputs.get("schema_version") == 1
            and inputs.get("template_only") is False
            and set(inputs) <= INPUTS | {"schema_version", "template_only"},
            "Complete the finite candidate input template",
        )
        data["inputs"] = inputs
        report["files"]["inputs"] = {
            "sha256": digest(inputs_path),
            "bytes": inputs_path.stat().st_size,
        }

    def load(name: str) -> None:
        value = data.get("inputs", {}).get(name)
        require(
            isinstance(value, str) and value.strip(),
            f"Required {name} input is missing",
        )
        path = (inputs_path.parent / value).resolve()
        paths[name] = path
        if name == "scanner_reports_dir":
            require(path.is_dir(), "Scanner raw report directory is missing")
            return
        report["files"][name] = {"sha256": digest(path), "bytes": path.stat().st_size}
        if name != "android_apk":
            data[name] = read_object(path)

    check("source", source)
    check("inputs", load_inputs)
    for name in sorted(INPUTS):
        check(f"input_{name}", lambda name=name: load(name))
    check("ci", lambda: validate_ci(data["ci_run"], data["ci_artifacts"], expected))
    check(
        "android_package",
        lambda: validate_android(
            data["android_report"], paths["android_apk"], expected
        ),
    )

    def signed() -> None:
        android = data["android_report"]
        require(
            android.get("build_mode") == "release"
            and android.get("status") == "signed_candidate"
            and android.get("debuggable") is False,
            "A debug APK is only internal evidence; owner-signed release is missing",
        )
        fingerprint = android.get("certificate_sha256", "")
        require(
            isinstance(fingerprint, str)
            and DIGEST.fullmatch(fingerprint)
            and android.get("expected_certificate_sha256") == fingerprint,
            "Owner signing certificate verification is missing",
        )

    check("android_release_signing", signed)
    check(
        "backup_restore",
        lambda: validate_recovery(data["recovery_report"], repository, expected),
    )

    def scanner() -> None:
        baseline_path = repository / "docs/release/scanner-baseline.json"
        baseline = read_object(baseline_path)
        calculated = scanners.compare(
            baseline["tools"], scanners.load_reports(paths["scanner_reports_dir"])
        )
        require(
            calculated.get("status") == "passed"
            and data["scanner_report"] == calculated,
            "Scanner comparison differs from raw reports or contains regressions",
        )
        report["files"]["scanner_baseline"] = {
            "sha256": digest(baseline_path),
            "bytes": baseline_path.stat().st_size,
        }
        for name, filename in scanners.FILES.items():
            path = paths["scanner_reports_dir"] / filename
            report["files"][f"scanner_raw_{name}"] = {
                "sha256": digest(path),
                "bytes": path.stat().st_size,
            }

    check("scanner_regression", scanner)
    check("performance", lambda: validate_performance(data["performance_report"]))
    for name in ("recovery_report", "scanner_report", "performance_report"):
        check(
            f"binding_{name}",
            lambda name=name: validate_binding(
                name,
                data["bindings"],
                data[name],
                report["files"][name]["sha256"],
                expected,
                tree,
                repository,
            ),
        )

    def human(gate: str, supports: set[str]) -> None:
        entry = data["attestations"].get(gate, {})
        require(
            isinstance(entry, dict) and entry.get("outcome") == "accepted",
            "Explicit human acceptance is still pending",
        )
        require(
            entry.get("source_sha") == expected
            and aware_date(entry.get("reviewed_at"))
            and reference(entry.get("review_ref")),
            "Human acceptance lacks exact scope, date or review reference",
        )
        hashes = entry.get("evidence_sha256", {})
        require(
            isinstance(hashes, dict)
            and set(hashes) == supports
            and all(
                hashes[name] == report["files"][name]["sha256"] for name in supports
            ),
            "Human acceptance refers to missing or changed supporting evidence",
        )
        if gate == "performance_acceptance":
            require(
                entry.get("backend_source_sha") == expected
                and entry.get("environment_class") == "isolated_production_like",
                "Performance backend revision/environment acceptance is missing",
            )
        report["human_attestations"].append(
            {
                "gate": gate,
                "kind": "declared_human_acceptance",
                "reviewed_at": entry["reviewed_at"],
                "review_reference_sha256": hashlib.sha256(
                    entry["review_ref"].encode()
                ).hexdigest(),
                "source_sha": expected,
            }
        )

    for name, supports in HUMAN_GATES.items():
        check(
            f"human_{name}", lambda name=name, supports=supports: human(name, supports)
        )
    report["blocked_gates"] = [
        item for item in report["checks"] if item["status"] == "blocked"
    ]
    if not report["blocked_gates"]:
        report["status"] = "READY_FOR_MANAGEMENT_REVIEW"
        report["candidate_ready_for_management_review"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = build_report(
        args.expected_sha, args.inputs.resolve(), args.repository.resolve()
    )
    # Never overwrite input evidence while producing its digest.
    protected = {args.inputs.resolve()}
    try:
        inputs = read_object(args.inputs)
        protected.update(
            (args.inputs.parent / value).resolve()
            for key, value in inputs.items()
            if key in INPUTS and isinstance(value, str)
        )
        raw = inputs.get("scanner_reports_dir")
        if isinstance(raw, str):
            protected.update(
                (args.inputs.parent / raw / filename).resolve()
                for filename in scanners.FILES.values()
            )
    except (OSError, ValueError, EvidenceError):
        pass
    output = args.output.resolve()
    if output in protected or args.repository.resolve() in output.parents:
        parser.exit(2, "Output must be separate from all input evidence\n")
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except OSError:
        parser.exit(2, "Candidate report could not be written\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "blocked_gates": [item["gate"] for item in result["blocked_gates"]],
                "production_ready": False,
            }
        )
    )
    return 0 if result["candidate_ready_for_management_review"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
