from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_SOURCE = Path(r"C:\SPINA_ONLINE\spina_backend")
DEFAULT_DESTINATION = Path("spina_backend_live")

ALLOWED_SUFFIXES = {
    ".py",
    ".html",
    ".css",
    ".js",
    ".md",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
}
ALLOWED_FILENAMES = {
    "requirements",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
}
EXCLUDED_DIR_NAMES = {
    ".git",
    ".idea",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "backups",
    "backup",
    "certs",
    "data",
    "db",
    "env",
    "logs",
    "media",
    "node_modules",
    "uploads",
    "venv",
}
EXCLUDED_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "service-account.json",
    "credentials.json",
}
EXCLUDED_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".crt",
    ".cer",
    ".dump",
    ".bak",
    ".zip",
}

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private_key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "database_url_with_password",
        re.compile(
            r"(?:postgres(?:ql)?|mysql|mariadb)://[^\s:/]+:[^\s@/]+@",
            re.IGNORECASE,
        ),
    ),
    (
        "openai_style_secret",
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b"),
    ),
    (
        "hardcoded_secret_assignment",
        re.compile(
            r"(?im)^\s*(?:[A-Z0-9_]*?(?:PASSWORD|PASSWD|SECRET|API_KEY|ACCESS_TOKEN|REFRESH_TOKEN|JWT_KEY|JWT_SECRET|DATABASE_URL)[A-Z0-9_]*)\s*=\s*['\"][^'\"]{4,}['\"]"
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class FileDecision:
    relative_path: str
    decision: str
    reason: str


@dataclass(frozen=True, slots=True)
class ImportReport:
    source: str
    destination: str
    apply: bool
    safe_files: int
    excluded_files: int
    blocked_files: int
    copied_files: int
    decisions: list[FileDecision]

    @property
    def has_blocked_files(self) -> bool:
        return self.blocked_files > 0


def _is_excluded_path(relative: Path) -> str | None:
    if any(part.lower() in EXCLUDED_DIR_NAMES for part in relative.parts[:-1]):
        return "excluded_directory"

    name = relative.name.lower()
    if name in EXCLUDED_FILE_NAMES or name.startswith(".env."):
        return "sensitive_filename"
    if relative.suffix.lower() in EXCLUDED_SUFFIXES:
        return "sensitive_or_runtime_file_type"
    return None


def _is_allowed_source(relative: Path) -> bool:
    name = relative.name.lower()
    return name in ALLOWED_FILENAMES or relative.suffix.lower() in ALLOWED_SUFFIXES


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            return None


def _secret_reason(text: str) -> str | None:
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            return name
    return None


def build_report(
    source: Path,
    destination: Path,
    *,
    apply: bool,
) -> ImportReport:
    source = source.resolve()
    destination = destination.resolve()

    if not source.exists() or not source.is_dir():
        raise FileNotFoundError(f"SPINA backend source does not exist: {source}")
    if source == destination or source in destination.parents:
        raise ValueError("Destination must not be inside the source backend directory.")

    decisions: list[FileDecision] = []
    safe: list[tuple[Path, Path]] = []

    for path in sorted(p for p in source.rglob("*") if p.is_file()):
        relative = path.relative_to(source)
        excluded_reason = _is_excluded_path(relative)
        if excluded_reason:
            decisions.append(
                FileDecision(relative.as_posix(), "excluded", excluded_reason)
            )
            continue

        if not _is_allowed_source(relative):
            decisions.append(
                FileDecision(relative.as_posix(), "excluded", "unsupported_file_type")
            )
            continue

        text = _read_text(path)
        if text is None:
            decisions.append(
                FileDecision(relative.as_posix(), "excluded", "non_utf8_text")
            )
            continue

        secret_reason = _secret_reason(text)
        if secret_reason:
            decisions.append(FileDecision(relative.as_posix(), "blocked", secret_reason))
            continue

        decisions.append(FileDecision(relative.as_posix(), "safe", "source_file"))
        safe.append((path, destination / relative))

    copied = 0
    if apply:
        destination.mkdir(parents=True, exist_ok=True)
        for source_file, destination_file in safe:
            destination_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, destination_file)
            copied += 1

    safe_count = sum(item.decision == "safe" for item in decisions)
    excluded_count = sum(item.decision == "excluded" for item in decisions)
    blocked_count = sum(item.decision == "blocked" for item in decisions)
    return ImportReport(
        source=str(source),
        destination=str(destination),
        apply=apply,
        safe_files=safe_count,
        excluded_files=excluded_count,
        blocked_files=blocked_count,
        copied_files=copied,
        decisions=decisions,
    )


def write_manifest(report: ImportReport, path: Path) -> None:
    payload = asdict(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _print_summary(report: ImportReport) -> None:
    print(f"Source:       {report.source}")
    print(f"Destination:  {report.destination}")
    print(f"Mode:         {'APPLY' if report.apply else 'DRY RUN'}")
    print(f"Safe files:   {report.safe_files}")
    print(f"Excluded:     {report.excluded_files}")
    print(f"Blocked:      {report.blocked_files}")
    print(f"Copied:       {report.copied_files}")
    if report.has_blocked_files:
        print("\nBlocked files require manual review:")
        for item in report.decisions:
            if item.decision == "blocked":
                print(f"  - {item.relative_path}: {item.reason}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Safely inventory or import the existing SPINA FastAPI source into "
            "the GitHub working tree without copying runtime data or likely secrets."
        )
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Copy files classified as safe. Without this flag the tool is read-only.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("backend-import-manifest.json"),
        help="Write the sanitized classification report here.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = build_report(args.source, args.destination, apply=args.apply)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    write_manifest(report, args.manifest)
    _print_summary(report)
    if report.has_blocked_files:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
