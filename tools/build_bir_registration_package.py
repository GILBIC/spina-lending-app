"""Build a local, unsigned review packet from an exact source revision.

No network, database, signatures or government submission. Input statuses are
operator declarations; even a complete packet still requires accountable review.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import posixpath
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import tomllib

MAX_FILE = 25 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_SOURCE = 256 * 1024 * 1024
DOC_NAMES = (
    "README.md",
    "official-requirements.md",
    "system-description.md",
    "technical-matrix.md",
    "registration-checklist.md",
    "profile.example.json",
    "version-control.md",
)
FACTS = (
    "legal_name",
    "address",
    "tin",
    "branch_code",
    "rdo_code",
    "taxpayer_classification",
    "vat_status",
    "maintainer_arrangement",
    "reviewed_by",
    "reviewed_at",
    "review_reference",
)
APPLICABILITY = ("invoice", "saf", "electronic_invoicing", "sales_reporting")
EVIDENCE_KEYS = (
    "official_sworn_statement",
    "official_system_summary",
    "official_technical_checklist",
    "taxpayer_registration",
    "authority_to_file",
    "invoice_sample",
    "supplementary_document_sample",
    "saf_assessment",
    "retention_policy",
    "access_policy",
    "backup_restore_evidence",
    "system_flow_diagram",
    "accountant_review",
    "submission_receipt",
    "acknowledgement_certificate",
    "annual_books_qr",
)
REQUIRED_EVIDENCE = EVIDENCE_KEYS[:5] + (
    "supplementary_document_sample",
    "retention_policy",
    "access_policy",
    "backup_restore_evidence",
    "system_flow_diagram",
    "accountant_review",
)
EXPORT_FILES = {
    "general-journal.csv",
    "general-ledger.csv",
    "trial-balance.csv",
    "chart-of-accounts.csv",
    "accounting-audit.csv",
    "cancelled-drafts.json",
    "README.md",
    "print-view.html",
}
DISCLAIMER = (
    "Unsigned preparation draft. Source hashes identify bytes, not BIR acceptance. "
    "Supplied identity, applicability, signatures and references are operator declarations. "
    "Review current official forms, taxpayer facts and applicable requirements before filing. "
    "This tool performs no government submission and creates no certificate, QR or signature."
)


class PackageError(ValueError):
    """A bounded, non-sensitive reason the packet cannot be built."""


def require(condition: Any, message: str) -> None:
    if not condition:
        raise PackageError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def no_links(path: Path) -> Path:
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        require(
            not item.is_symlink() and not getattr(item, "is_junction", lambda: False)(),
            "Linked input or output paths are not allowed.",
        )
    return path.resolve()


def read_file(path: Path, limit: int = MAX_FILE) -> bytes:
    path = no_links(path)
    require(path.is_file(), "An explicitly supplied input is not a regular file.")
    require(path.stat().st_size <= limit, "An input exceeds the size limit.")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    require(len(data) <= limit, "An input exceeds the size limit.")
    return data


def parse_json(data: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON keys are not allowed.")
            result[key] = value
        return result

    try:
        return json.loads(
            data.decode("utf-8-sig"),
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(
                PackageError("Invalid JSON number.")
            ),
        )
    except PackageError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise PackageError("An input is not valid bounded UTF-8 JSON.") from exc


def text_value(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= 2000
        and all(ord(char) >= 32 or char in "\n\t" for char in value)
    )


def blank_profile() -> dict:
    return {
        "schema_version": 1,
        **dict.fromkeys(FACTS),
        "system_classification": "unresolved",
        "applicability": {
            key: {"status": "pending", "rationale": None, "evidence_reference": None}
            for key in APPLICABILITY
        },
    }


def validate_profile(value: Any) -> dict:
    template = blank_profile()
    require(
        isinstance(value, dict) and set(value) == set(template),
        "Invalid profile fields.",
    )
    require(
        type(value["schema_version"]) is int and value["schema_version"] == 1,
        "Unsupported profile schema.",
    )
    for key in FACTS:
        require(
            value[key] is None or text_value(value[key]), "Invalid profile text field."
        )
    require(
        value["system_classification"] in ("CAS", "CBA", "component", "unresolved"),
        "Invalid system classification.",
    )
    decisions = value["applicability"]
    require(
        isinstance(decisions, dict) and set(decisions) == set(APPLICABILITY),
        "Invalid applicability fields.",
    )
    for decision in decisions.values():
        require(
            isinstance(decision, dict)
            and set(decision) == {"status", "rationale", "evidence_reference"},
            "Invalid applicability decision.",
        )
        require(
            decision["status"] in ("pending", "required", "not_applicable"),
            "Invalid applicability status.",
        )
        for key in ("rationale", "evidence_reference"):
            require(
                decision[key] is None or text_value(decision[key]),
                "Invalid applicability text.",
            )
        if decision["status"] != "pending":
            require(
                all(
                    text_value(decision[key])
                    for key in ("rationale", "evidence_reference")
                )
                and all(
                    text_value(value[key])
                    for key in ("reviewed_by", "reviewed_at", "review_reference")
                ),
                "Resolved applicability requires rationale, evidence and accountable review.",
            )
    if value["reviewed_at"] is not None:
        try:
            date.fromisoformat(value["reviewed_at"])
        except ValueError as exc:
            raise PackageError("Review date must use YYYY-MM-DD.") from exc
    return value


def git(repository: Path, *args: str, input_data: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        input=input_data,
        capture_output=True,
        check=False,
        timeout=120,
    )
    require(result.returncode == 0, "Source repository inspection failed.")
    return result.stdout


def assert_clean(repository: Path, expected_sha: str) -> None:
    require(
        re.fullmatch(r"[0-9a-f]{40}", expected_sha),
        "Expected source SHA must contain 40 lowercase hex characters.",
    )
    require(
        git(repository, "rev-parse", "--show-toplevel")
        .decode()
        .strip()
        .replace("\\", "/")
        .casefold()
        == repository.as_posix().casefold(),
        "Repository must name the worktree root.",
    )
    require(
        git(repository, "rev-parse", "HEAD").decode().strip() == expected_sha,
        "Source revision mismatch.",
    )
    require(
        not git(repository, "status", "--porcelain=v1", "--untracked-files=all"),
        "Source checkout must be clean, including non-ignored untracked files.",
    )


def relevant(path: str) -> bool:
    return path.startswith(
        (
            "gilbic_backend/src/",
            "gilbic_backend/sql/",
            "spina_backend_mobile/src/",
            "spina_app/",
            "spina_portal/assets/",
            "gilbic_mobile/lib/",
            "docs/accounting/",
            "docs/bir/",
        )
    ) or path in {
        "gilbic_backend/pyproject.toml",
        "spina_backend_mobile/pyproject.toml",
        "gilbic_mobile/pubspec.yaml",
        "gilbic_mobile/pubspec.lock",
        "package.json",
        "tools/build_bir_registration_package.py",
        "tools/run_accounting_export_disposable_validation.py",
    }


def source_manifest(
    repository: Path, expected_sha: str
) -> tuple[dict, dict[str, bytes]]:
    entries = []
    for record in git(repository, "ls-tree", "-r", "-z", "-l", expected_sha).split(
        b"\0"
    ):
        if not record:
            continue
        fields, raw_path = record.split(b"\t", 1)
        mode, kind, oid, size = fields.split()
        path = raw_path.decode("utf-8")
        if relevant(path):
            require(
                kind == b"blob" and mode in (b"100644", b"100755"),
                "Linked or special source assets are not allowed.",
            )
            entries.append((path, mode.decode(), oid.decode(), int(size)))
    require(
        entries and len(entries) <= 10000 and sum(e[3] for e in entries) <= MAX_SOURCE,
        "Source inventory is empty or exceeds its bound.",
    )
    raw = git(
        repository,
        "cat-file",
        "--batch",
        input_data="".join(e[2] + "\n" for e in entries).encode(),
    )
    offset, inventory, docs, versions = 0, {}, {}, {}
    for path, mode, oid, size in entries:
        boundary = raw.index(b"\n", offset)
        require(
            raw[offset:boundary].decode() == f"{oid} blob {size}",
            "Source object metadata mismatch.",
        )
        data = raw[boundary + 1 : boundary + 1 + size]
        offset = boundary + 2 + size
        require(len(data) == size, "Incomplete source object.")
        inventory[path] = {
            "git_blob": oid,
            "sha256": digest(data),
            "bytes": size,
            "mode": mode,
        }
        if path.endswith("pyproject.toml"):
            versions[path] = tomllib.loads(data.decode("utf-8"))["project"]["version"]
        elif path == "package.json":
            versions[path] = parse_json(data)["version"]
        elif path == "gilbic_mobile/pubspec.yaml":
            match = re.search(r"^version:\s*(\S+)", data.decode("utf-8"), re.MULTILINE)
            require(match is not None, "Missing mobile component version.")
            versions[path] = match.group(1)
        if path.startswith("docs/bir/") and path.removeprefix("docs/bir/") in DOC_NAMES:
            docs[path.removeprefix("docs/bir/")] = data
    require(
        set(docs) == set(DOC_NAMES),
        "The committed BIR preparation documents are incomplete.",
    )
    return {
        "schema_version": 1,
        "kind": "spina_bir_source_version",
        "source_sha": expected_sha,
        "source_tree": git(repository, "rev-parse", expected_sha + "^{tree}")
        .decode()
        .strip(),
        "inventory_scope": "Conservative financial backend, SQL, clients, accounting/BIR docs and export tools; exact Git blob bytes.",
        "files": inventory,
        "schema_migrations": [
            name
            for name in inventory
            if name.startswith("gilbic_backend/sql/") and name.endswith(".sql")
        ],
        "component_version_sources": [
            name
            for name in inventory
            if name.endswith(("pyproject.toml", "pubspec.yaml", "package.json"))
        ],
        "registration_verified": False,
        "component_versions": versions,
    }, docs


def version_comparison(previous: Any, current: dict) -> dict:
    require(
        isinstance(previous, dict)
        and previous.get("schema_version") == 1
        and previous.get("kind") == "spina_bir_source_version"
        and re.fullmatch(r"[0-9a-f]{40}", str(previous.get("source_sha", "")))
        and isinstance(previous.get("files"), dict),
        "Invalid prior version manifest.",
    )
    old, new = previous["files"], current["files"]
    for name, entry in old.items():
        require(
            isinstance(name, str)
            and relevant(name)
            and not any(part in ("..", "") for part in name.split("/"))
            and "\\" not in name
            and isinstance(entry, dict)
            and re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256", ""))),
            "Invalid prior source inventory.",
        )
    return {
        "previous_source_sha": previous["source_sha"],
        "current_source_sha": current["source_sha"],
        "added": sorted(new.keys() - old.keys()),
        "removed": sorted(old.keys() - new.keys()),
        "changed": sorted(
            name for name in old.keys() & new.keys() if old[name] != new[name]
        ),
        "impact_review_required": True,
        "legal_major_minor_classification": "not_determined",
        "prior_record_modified": False,
    }


def load_evidence(path: Path | None) -> tuple[dict[str, bytes], list[dict]]:
    if path is None:
        return {}, []
    value = parse_json(read_file(path, 1024 * 1024))
    require(
        isinstance(value, dict)
        and set(value) == {"schema_version", "items"}
        and type(value["schema_version"]) is int
        and value["schema_version"] == 1
        and isinstance(value["items"], list)
        and len(value["items"]) <= len(EVIDENCE_KEYS),
        "Invalid evidence list.",
    )
    files, declarations, seen, total = {}, [], set(), 0
    for item in value["items"]:
        require(
            isinstance(item, dict)
            and set(item) == {"key", "path", "status", "reference"},
            "Invalid evidence item.",
        )
        key = item["key"]
        require(
            isinstance(key, str) and key in EVIDENCE_KEYS and key not in seen,
            "Unknown or duplicate evidence key.",
        )
        require(
            item["status"] in ("unsigned", "signed", "reviewed")
            and text_value(item["reference"])
            and text_value(item["path"]),
            "Invalid evidence declaration.",
        )
        source = Path(item["path"])
        if not source.is_absolute():
            source = path.parent / source
        extension = source.suffix.lower()
        require(
            extension
            in (
                ".pdf",
                ".png",
                ".jpg",
                ".jpeg",
                ".csv",
                ".json",
                ".md",
                ".txt",
                ".dat",
            ),
            "Unsupported evidence file type.",
        )
        data = read_file(source)
        require(bool(data), "Empty evidence file.")
        if extension == ".pdf":
            require(data.startswith(b"%PDF-"), "Invalid PDF evidence header.")
        elif extension == ".png":
            require(
                data.startswith(b"\x89PNG\r\n\x1a\n"), "Invalid PNG evidence header."
            )
        elif extension in (".jpg", ".jpeg"):
            require(data.startswith(b"\xff\xd8\xff"), "Invalid JPEG evidence header.")
        else:
            require(
                b"\0" not in data
                and not data.startswith((b"MZ", b"\x7fELF", b"PK\x03\x04")),
                "Unexpected binary evidence.",
            )
            if extension == ".json":
                parse_json(data)
            else:
                try:
                    data.decode("utf-8-sig")
                except UnicodeError as exc:
                    raise PackageError("Text evidence must be UTF-8.") from exc
        total += len(data)
        require(total <= MAX_TOTAL, "Combined evidence exceeds the size limit.")
        filename = f"evidence/{key}{extension}"
        files[filename] = data
        declarations.append(
            {
                "key": key,
                "file": filename,
                "declared_status": item["status"],
                "reference": item["reference"],
                "independently_verified": False,
            }
        )
        seen.add(key)
    return files, declarations


def validate_export(data: bytes) -> dict:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            require(
                len(infos) == len(EXPORT_FILES) + 1
                and {i.filename for i in infos} == EXPORT_FILES | {"manifest.json"},
                "Accounting export file inventory mismatch.",
            )
            require(
                sum(i.file_size for i in infos) <= MAX_TOTAL
                and all(
                    not i.flag_bits & 1
                    and not stat.S_ISLNK(i.external_attr >> 16)
                    and not i.is_dir()
                    for i in infos
                ),
                "Unsafe or oversized accounting export.",
            )
            contents = {i.filename: archive.read(i) for i in infos}
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise PackageError("Invalid accounting export archive.") from exc
    manifest = parse_json(contents.pop("manifest.json"))
    require(
        isinstance(manifest, dict)
        and manifest.get("schema_version") == 1
        and manifest.get("kind") == "spina_accounting_export"
        and manifest.get("review_only") is True
        and all(
            manifest.get(key) is False
            for key in (
                "official_books_registered",
                "saf_compliance_verified",
                "taxpayer_identity_verified",
            )
        ),
        "Invalid accounting review manifest.",
    )
    require(
        all(
            manifest.get(key, False) is False
            for key in ("registered", "saf_compliant", "tax_invoice")
        ),
        "Contradictory accounting export certification claims.",
    )
    try:
        start, end = (
            date.fromisoformat(manifest["start_date"]),
            date.fromisoformat(manifest["end_date"]),
        )
        require(0 <= (end - start).days < 366, "Invalid accounting export date range.")
    except (KeyError, TypeError, ValueError) as exc:
        raise PackageError("Invalid accounting export date range.") from exc
    require(
        isinstance(manifest.get("files"), dict)
        and set(manifest["files"]) == EXPORT_FILES,
        "Accounting manifest inventory mismatch.",
    )
    for name, content in contents.items():
        entry = manifest["files"][name]
        require(
            isinstance(entry, dict)
            and entry.get("sha256") == digest(content)
            and type(entry.get("bytes")) is int
            and entry["bytes"] == len(content),
            "Accounting export hash or size mismatch.",
        )
        if name.endswith(".csv"):
            previous_field_limit = csv.field_size_limit(MAX_TOTAL)
            try:
                reader = csv.reader(
                    io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True
                )
                require(bool(next(reader, None)), "Accounting CSV header is missing.")
                count = sum(1 for _ in reader)
            except (csv.Error, UnicodeError) as exc:
                raise PackageError("Invalid accounting CSV.") from exc
            finally:
                csv.field_size_limit(previous_field_limit)
            require(
                type(entry.get("rows")) is int
                and entry["rows"] == count
                and count <= 100000,
                "Accounting CSV row count mismatch.",
            )
        elif name == "cancelled-drafts.json":
            cancelled = parse_json(content)
            require(
                isinstance(cancelled, list)
                and type(entry.get("rows")) is int
                and entry["rows"] == len(cancelled) <= 100000,
                "Cancelled-draft count mismatch.",
            )
        else:
            require(entry.get("rows") is None, "Invalid accounting manifest row count.")
    totals = manifest.get("totals")
    require(isinstance(totals, dict), "Accounting totals are missing.")
    for period in ("opening", "movement", "closing"):
        values = [totals.get(f"{period}_{side}") for side in ("debit", "credit")]
        require(
            all(
                isinstance(v, str) and re.fullmatch(r"[0-9]{1,24}\.[0-9]{2}", v)
                for v in values
            ),
            "Invalid exact accounting totals.",
        )
        require(
            Decimal(values[0]) == Decimal(values[1]),
            "Unbalanced accounting export totals.",
        )
    return {
        "manifest": manifest,
        "byte_integrity_verified": True,
        "source_authenticity_verified": False,
        "saf_compliance_verified": False,
    }


def readiness(profile: dict, evidence: list[dict], has_export: bool) -> list[dict]:
    rows = [
        {
            "key": key,
            "status": "supplied_unverified" if profile[key] is not None else "pending",
        }
        for key in FACTS
    ]
    rows.append(
        {
            "key": "system_classification",
            "status": "pending"
            if profile["system_classification"] == "unresolved"
            else "supplied_unverified",
        }
    )
    for key, item in profile["applicability"].items():
        rows.append(
            {
                "key": key + "_applicability",
                "status": "pending"
                if item["status"] == "pending"
                else "supplied_unverified",
            }
        )
    supplied = {item["key"] for item in evidence}
    required = list(REQUIRED_EVIDENCE)
    if profile["applicability"]["invoice"]["status"] == "required":
        required.append("invoice_sample")
    if profile["applicability"]["saf"]["status"] == "required":
        required.append("saf_assessment")
    rows.extend(
        {"key": key, "status": "supplied_unverified" if key in supplied else "pending"}
        for key in required
    )
    rows.append(
        {
            "key": "accounting_review_export",
            "status": "bytes_checked" if has_export else "pending",
        }
    )
    return rows


def linked_draft(content: bytes, source_sha: str) -> bytes:
    """Keep packet-local links; bind repository references to retained source."""

    def replace(match: re.Match[str]) -> str:
        target = match.group(2)
        url = urlsplit(target)
        if url.scheme or url.netloc or target.startswith("#"):
            return match.group(0)
        path = posixpath.normpath(posixpath.join("docs/bir", url.path))
        if path in {"docs/bir/" + name for name in DOC_NAMES}:
            return match.group(0)
        require(
            not path.startswith("../") and not path.startswith("/"),
            "Unsafe source documentation link.",
        )
        permalink = f"https://github.com/GILBIC/spina-lending-app/blob/{source_sha}/{quote(path, safe='/')}"
        if url.fragment:
            permalink += "#" + url.fragment
        return f"{match.group(1)}({permalink})"

    return re.sub(
        r"(\[[^\]]+\])\(([^()\s]+)\)", replace, content.decode("utf-8")
    ).encode("utf-8")


def build_package(
    *,
    repository: Path,
    expected_sha: str,
    output_dir: Path,
    profile_path: Path | None = None,
    evidence_path: Path | None = None,
    accounting_export: Path | None = None,
    compare_manifest: Path | None = None,
) -> dict:
    repository, output = no_links(repository), no_links(output_dir)
    require(
        not output.is_relative_to(repository) and not repository.is_relative_to(output),
        "Output must be outside the source repository.",
    )
    require(
        not output.exists() and output.parent.is_dir(),
        "Output must be a new directory under an existing parent.",
    )
    assert_clean(repository, expected_sha)
    version, docs = source_manifest(repository, expected_sha)
    profile = (
        validate_profile(parse_json(read_file(profile_path, 1024 * 1024)))
        if profile_path
        else blank_profile()
    )
    files, declarations = load_evidence(evidence_path)
    for name, content in docs.items():
        files["docs/bir/" + name] = (
            linked_draft(content, expected_sha) if name.endswith(".md") else content
        )
    files["profile.json"] = json_bytes(profile)
    files["version-manifest.json"] = json_bytes(version)
    files["evidence-declarations.json"] = json_bytes(
        {"schema_version": 1, "items": declarations, "independently_verified": False}
    )
    if accounting_export:
        export = read_file(accounting_export, MAX_TOTAL)
        verified = validate_export(export)
        files["accounting-review.zip"] = export
        files["accounting-export-validation.json"] = json_bytes(verified)
    if compare_manifest:
        prior_bytes = read_file(compare_manifest, 16 * 1024 * 1024)
        comparison = version_comparison(parse_json(prior_bytes), version)
        comparison["prior_manifest_sha256"] = digest(prior_bytes)
        files["version-comparison.json"] = json_bytes(comparison)
        files["prior-version-manifest.json"] = prior_bytes
    rows = readiness(profile, declarations, accounting_export is not None)
    status = (
        "DRAFT_PENDING_INPUTS"
        if any(row["status"] == "pending" for row in rows)
        else "DRAFT_FOR_OWNER_REVIEW"
    )
    files["readiness.json"] = json_bytes(
        {
            "schema_version": 1,
            "status": status,
            "items": rows,
            "required_human_reviews": [
                "Current official forms and filing channel",
                "Taxpayer and applicability evidence",
                "Signatures and authority",
                "Accounting samples and SAF where applicable",
                "Retention/access/backup practice",
                "Legal change classification and actual government records",
            ],
            "filing_ready": False,
            "registration_verified": False,
        }
    )
    pending = (
        "\n".join("- " + row["key"] for row in rows if row["status"] == "pending")
        or "- No missing input fields; all supplied facts still require review."
    )
    files["README.md"] = (
        f"# Spina BIR preparation draft\n\n{DISCLAIMER}\n\nStatus: {status}\nSource: {expected_sha}\n\n"
        "Read docs/bir/README.md and readiness.json. Supplied private records are retained in this directory; restrict access. "
        "Accounting ZIP hashes and counts prove byte integrity only. CSV review books are not a validated SAF. "
        "Keep this candidate unchanged if reviewed or submitted, and retain actual government records separately.\n\n"
        f"## Missing preparation inputs\n\n{pending}\n"
    ).encode()
    manifest = {
        "schema_version": 1,
        "kind": "spina_bir_preparation_package",
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_sha": expected_sha,
        "source_tree": version["source_tree"],
        "registration_verified": False,
        "filing_ready": False,
        "government_submission_performed": False,
        "signed_or_notarized_by_tool": False,
        "warning": DISCLAIMER,
        "files": {
            name: {"sha256": digest(data), "bytes": len(data)}
            for name, data in sorted(files.items())
        },
    }
    files["package-manifest.json"] = json_bytes(manifest)
    assert_clean(repository, expected_sha)
    stage = Path(tempfile.mkdtemp(prefix=".spina-bir-", dir=output.parent)).resolve()
    try:
        for name, data in files.items():
            destination = stage / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        require(
            not output.exists(),
            "Output appeared during preparation; refusing replacement.",
        )
        stage.rename(output)
    finally:
        if stage.exists():
            require(
                stage.parent == output.parent
                and stage.name.startswith(".spina-bir-")
                and not stage.is_symlink(),
                "Unsafe temporary cleanup target.",
            )
            shutil.rmtree(stage)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--accounting-export", type=Path)
    parser.add_argument("--compare-manifest", type=Path)
    args = parser.parse_args()
    try:
        report = build_package(
            repository=args.repository,
            expected_sha=args.expected_sha,
            output_dir=args.output_dir,
            profile_path=args.profile,
            evidence_path=args.evidence,
            accounting_export=args.accounting_export,
            compare_manifest=args.compare_manifest,
        )
    except (PackageError, OSError, subprocess.SubprocessError, UnicodeError) as exc:
        print(
            f"BIR preparation failed: {exc if isinstance(exc, PackageError) else 'Input or repository operation failed.'}"
        )
        return 2
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "status",
                    "source_sha",
                    "source_tree",
                    "filing_ready",
                    "registration_verified",
                )
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
