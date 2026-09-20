"""Preparation remains unsigned and version-bound even with plausible supplied facts."""

import hashlib
import io
import json
import subprocess
import sys
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest
from gilbic_backend.accounting_export import build_accounting_export

from tools import build_bir_registration_package as package

ROOT = Path(__file__).resolve().parents[1]


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], stderr=subprocess.DEVNULL, text=True
    ).strip()


def commit(repo):
    git(repo, "add", ".")
    git(
        repo,
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
    return git(repo, "rev-parse", "HEAD")


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


@pytest.fixture
def candidate(tmp_path):
    repo = tmp_path / "repo"
    (repo / "docs/bir").mkdir(parents=True)
    for name in package.DOC_NAMES:
        (repo / "docs/bir" / name).write_bytes((ROOT / "docs/bir" / name).read_bytes())
    (repo / "gilbic_backend/sql").mkdir(parents=True)
    (repo / "gilbic_backend/sql/0001_example.sql").write_bytes(b"SELECT 1;\n")
    module = repo / "spina_backend_mobile/src/spina_mobile_collections"
    module.mkdir(parents=True)
    (module / "__init__.py").write_bytes(b"# Synthetic module\n")
    git(repo, "init", "--initial-branch=main")
    git(repo, "config", "core.autocrlf", "false")
    sha = commit(repo)
    return repo, sha, tmp_path / "packet"


def build(candidate, **kwargs):
    repo, sha, output = candidate
    return package.build_package(
        repository=repo, expected_sha=sha, output_dir=output, **kwargs
    )


def export_bytes(audit=None):
    return build_accounting_export(
        {
            "accounts": [],
            "journals": [],
            "periods": [],
            "audit": audit or [],
            "cancelled": [],
            "generated_at": datetime(2026, 9, 20, tzinfo=timezone.utc),
        },
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 30),
        generated_by_user_id=UUID(int=1),
    )


def repack(data, change):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    change(files)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in files.items():
            archive.writestr(name, value)
    return buffer.getvalue()


def test_minimal_packet_retains_exact_source_and_missing_inputs(candidate):
    report = build(candidate)
    repo, sha, output = candidate
    assert report["status"] == "DRAFT_PENDING_INPUTS"
    assert report["source_sha"] == sha
    assert report["source_tree"] == git(repo, "rev-parse", "HEAD^{tree}")
    assert all(
        report[key] is False
        for key in (
            "registration_verified",
            "filing_ready",
            "government_submission_performed",
            "signed_or_notarized_by_tool",
        )
    )
    for name, metadata in report["files"].items():
        data = (output / name).read_bytes()
        assert metadata == {
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        }
    version = json.loads((output / "version-manifest.json").read_text())
    item = version["files"]["gilbic_backend/sql/0001_example.sql"]
    assert item["git_blob"] == git(
        repo, "rev-parse", "HEAD:gilbic_backend/sql/0001_example.sql"
    )
    assert item["sha256"] == hashlib.sha256(b"SELECT 1;\n").hexdigest()
    assert json.loads((output / "profile.json").read_text())["legal_name"] is None
    assert not git(repo, "status", "--porcelain")
    description = (output / "docs/bir/system-description.md").read_text(
        encoding="utf-8"
    )
    assert f"/blob/{sha}/gilbic_backend/src/" in description
    assert f"/tree/{sha}/spina_backend_mobile/src/spina_mobile_collections" in description
    assert "](../../gilbic_backend/" not in description


@pytest.mark.parametrize(
    "failure", ["dirty", "untracked", "wrong_sha", "inside", "existing"]
)
def test_unsafe_or_misbound_output_refused_without_overwrite(candidate, failure):
    repo, sha, output = candidate
    if failure == "dirty":
        (repo / "gilbic_backend/sql/0001_example.sql").write_text("changed")
    elif failure == "untracked":
        (repo / "new.txt").write_text("new")
    elif failure == "wrong_sha":
        sha = "f" * 40
    elif failure == "inside":
        output = repo / "packet"
    else:
        output.mkdir()
        (output / "keep.txt").write_text("prior frozen evidence")
    with pytest.raises(package.PackageError):
        build((repo, sha, output))
    if failure == "existing":
        assert (output / "keep.txt").read_text() == "prior frozen evidence"
    else:
        assert not output.exists()


def test_real_export_is_retained_without_certifying_it(candidate, tmp_path):
    export = tmp_path / "accounting.zip"
    export.write_bytes(export_bytes())
    build(candidate, accounting_export=export)
    proof = json.loads((candidate[2] / "accounting-export-validation.json").read_text())
    assert proof["byte_integrity_verified"] is True
    assert proof["source_authenticity_verified"] is False
    assert (candidate[2] / "accounting-review.zip").read_bytes() == export.read_bytes()


def test_valid_wide_audit_field_below_export_limit_is_accepted():
    data = export_bytes(
        [{"event_type": "synthetic", "details": {"note": "x" * 140000}}]
    )
    result = package.validate_export(data)
    assert result["manifest"]["files"]["accounting-audit.csv"]["rows"] == 1


@pytest.mark.parametrize(
    "failure", ["tamper", "extra", "rows", "certified", "unbalanced", "duplicate"]
)
def test_corrupt_or_misleading_export_is_rejected(failure):
    def change(files):
        if failure == "tamper":
            files["general-journal.csv"] += b"changed"
        elif failure == "extra":
            files["../escape.txt"] = b"escape"
        else:
            manifest = json.loads(files["manifest.json"])
            if failure == "rows":
                manifest["files"]["general-journal.csv"]["rows"] = 999
            elif failure == "certified":
                manifest["official_books_registered"] = True
            elif failure == "unbalanced":
                manifest["totals"]["movement_debit"] = "0.01"
            files["manifest.json"] = json.dumps(manifest).encode()

    data = repack(export_bytes(), change)
    if failure == "duplicate":
        stream = io.BytesIO(data)
        with zipfile.ZipFile(stream, "a") as archive, pytest.warns(UserWarning):
            archive.writestr("README.md", b"duplicate")
        data = stream.getvalue()
    with pytest.raises(package.PackageError):
        package.validate_export(data)


def test_prior_version_stays_unchanged_and_financial_changes_are_listed(
    candidate, tmp_path
):
    build(candidate)
    prior = candidate[2] / "version-manifest.json"
    frozen = prior.read_bytes()
    repo = candidate[0]
    (repo / "gilbic_backend/sql/0001_example.sql").unlink()
    (repo / "gilbic_backend/sql/0002_example.sql").write_text("SELECT 2;")
    (repo / "docs/bir/system-description.md").write_text("Updated engineering draft")
    sha = commit(repo)
    output = tmp_path / "next-packet"
    build((repo, sha, output), compare_manifest=prior)
    comparison = json.loads((output / "version-comparison.json").read_text())
    assert comparison["added"] == ["gilbic_backend/sql/0002_example.sql"]
    assert comparison["removed"] == ["gilbic_backend/sql/0001_example.sql"]
    assert comparison["changed"] == ["docs/bir/system-description.md"]
    assert comparison["impact_review_required"] is True
    assert comparison["legal_major_minor_classification"] == "not_determined"
    assert prior.read_bytes() == frozen
    assert (output / "prior-version-manifest.json").read_bytes() == frozen


def test_supplied_profile_and_evidence_are_only_declarations(candidate, tmp_path):
    profile = package.blank_profile()
    profile.update(dict.fromkeys(package.FACTS, "Synthetic fixture only"))
    profile["reviewed_at"] = "2026-09-20"
    profile["system_classification"] = "CBA"
    for value in profile["applicability"].values():
        value.update(
            status="not_applicable",
            rationale="Synthetic test rationale",
            evidence_reference="Test review",
        )
    profile_path = write_json(tmp_path / "profile.json", profile)
    (tmp_path / "sample.pdf").write_bytes(b"%PDF-1.7\nSynthetic test only")
    evidence_path = write_json(
        tmp_path / "inputs.json",
        {
            "schema_version": 1,
            "items": [
                {
                    "key": key,
                    "path": "sample.pdf",
                    "status": "signed",
                    "reference": "Declared synthetic signature",
                }
                for key in package.REQUIRED_EVIDENCE
            ],
        },
    )
    export = tmp_path / "sample.zip"
    export.write_bytes(export_bytes())
    report = build(
        candidate,
        profile_path=profile_path,
        evidence_path=evidence_path,
        accounting_export=export,
    )
    assert report["status"] == "DRAFT_FOR_OWNER_REVIEW"
    assert report["filing_ready"] is report["registration_verified"] is False
    declaration = json.loads((candidate[2] / "evidence-declarations.json").read_text())
    assert declaration["independently_verified"] is False
    assert all(item["independently_verified"] is False for item in declaration["items"])
    assert str(tmp_path) not in (candidate[2] / "package-manifest.json").read_text()


def test_applicability_cannot_be_resolved_by_status_alone():
    profile = package.blank_profile()
    profile["applicability"]["saf"]["status"] = "not_applicable"
    with pytest.raises(package.PackageError, match="accountable review"):
        package.validate_profile(profile)


def test_linked_output_path_is_rejected(candidate, tmp_path):
    alias = tmp_path / "linked-parent"
    real = tmp_path / "real-parent"
    real.mkdir()
    try:
        alias.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("Platform does not permit unprivileged symlinks")
    with pytest.raises(package.PackageError, match="Linked"):
        build((candidate[0], candidate[1], alias / "packet"))
    assert list(real.iterdir()) == []


@pytest.mark.parametrize(
    "failure", ["duplicate", "unknown", "binary", "oversized", "empty", "invalid_pdf"]
)
def test_unsafe_evidence_is_rejected(candidate, tmp_path, monkeypatch, failure):
    source = tmp_path / "sample.txt"
    source.write_bytes(b"Synthetic evidence")
    item = {
        "key": "access_policy",
        "path": source.name,
        "status": "reviewed",
        "reference": "Synthetic",
    }
    items = [item]
    if failure == "duplicate":
        items.append(item)
    elif failure == "unknown":
        item["key"] = "../../secret"
    elif failure == "binary":
        source.write_bytes(b"MZ executable bytes")
    elif failure == "oversized":
        # Use the actual 25 MiB bound: file reads are capped even if stat changes.
        with source.open("wb") as stream:
            stream.truncate(package.MAX_FILE + 1)
    elif failure == "empty":
        source.write_bytes(b"")
    elif failure == "invalid_pdf":
        source = tmp_path / "fake.pdf"
        source.write_bytes(b"not a PDF")
        item["path"] = source.name
    evidence = write_json(
        tmp_path / "evidence.json", {"schema_version": 1, "items": items}
    )
    with pytest.raises(package.PackageError):
        build(candidate, evidence_path=evidence)
    assert not candidate[2].exists()


def test_duplicate_json_does_not_silently_replace_a_fact():
    with pytest.raises(package.PackageError, match="Duplicate"):
        package.parse_json(b'{"status":"pending","status":"signed"}')


def test_oversized_json_integer_has_a_sanitized_failure():
    with pytest.raises(package.PackageError):
        package.parse_json(b'{"value":' + b"9" * 5000 + b"}")


@pytest.mark.parametrize("flag", ["registered", "saf_compliant", "tax_invoice"])
def test_legacy_flags_cannot_claim_certification(flag):
    def change(files):
        manifest = json.loads(files["manifest.json"])
        manifest[flag] = True
        files["manifest.json"] = json.dumps(manifest).encode()

    with pytest.raises(package.PackageError, match="Contradictory"):
        package.validate_export(repack(export_bytes(), change))


def test_output_failure_cleans_only_owned_staging(candidate, monkeypatch):
    original = Path.write_bytes

    def fail_on_profile(path, data):
        if path.name == "profile.json" and path.parent.name.startswith(".spina-bir-"):
            raise OSError("simulated disk failure")
        return original(path, data)

    monkeypatch.setattr(Path, "write_bytes", fail_on_profile)
    with pytest.raises(OSError):
        build(candidate)
    assert not candidate[2].exists()
    assert not list(candidate[2].parent.glob(".spina-bir-*"))
    assert candidate[0].is_dir()


def test_cli_failure_does_not_print_private_path_or_values(candidate, tmp_path):
    private = tmp_path / "private-taxpayer-identity.json"
    private.write_text('{"sensitive":"private-tin-value"}')
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_bir_registration_package.py"),
            "--repository",
            str(candidate[0]),
            "--expected-sha",
            candidate[1],
            "--output-dir",
            str(candidate[2]),
            "--profile",
            str(private),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "Invalid profile fields" in result.stdout
    assert "private-tin-value" not in result.stdout + result.stderr
    assert str(private) not in result.stdout + result.stderr
