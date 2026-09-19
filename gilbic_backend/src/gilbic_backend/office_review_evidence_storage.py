"""Private immutable signed-review files; never a public/static upload directory."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
from uuid import UUID


MAX_EVIDENCE_BYTES = 10 * 1024 * 1024
EVIDENCE_MEDIA_TYPES = frozenset({"application/pdf", "image/png", "image/jpeg"})


class EvidenceFileError(RuntimeError):
    pass


def validate_evidence_content(content: bytes, media_type: str) -> None:
    if not isinstance(content, bytes) or not 0 < len(content) <= MAX_EVIDENCE_BYTES:
        raise EvidenceFileError("Signed evidence must contain at most 10 MiB.")
    valid = (
        (
            media_type == "application/pdf"
            and content.startswith(b"%PDF-")
            and content.rstrip().endswith(b"%%EOF")
        )
        or (
            media_type == "image/png"
            and content.startswith(b"\x89PNG\r\n\x1a\n")
            and content.endswith(b"IEND\xaeB`\x82")
        )
        or (
            media_type == "image/jpeg"
            and content.startswith(b"\xff\xd8\xff")
            and content.endswith(b"\xff\xd9")
        )
    )
    if not valid:
        raise EvidenceFileError("A signed PDF, PNG or JPEG scan is required.")


class PrivateEvidenceStore:
    def __init__(self, root: Path | None = None):
        configured = root or os.getenv("GILBIC_OFFICE_REVIEW_EVIDENCE_ROOT", "")
        if not configured:
            raise EvidenceFileError(
                "Private review evidence storage is not configured."
            )
        location = Path(configured)
        if not location.is_absolute():
            raise EvidenceFileError(
                "Private evidence storage must use an absolute path."
            )
        for item in (location, *location.parents):
            if item.is_symlink():
                raise EvidenceFileError(
                    "Private evidence storage cannot use symbolic links."
                )
        self.root = location.resolve()
        repository = Path(__file__).resolve().parents[3]
        if self.root == repository or repository in self.root.parents:
            raise EvidenceFileError(
                "Review evidence must be stored outside the application/web root."
            )
        try:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        except OSError as error:
            raise EvidenceFileError(
                "Private review evidence storage is unavailable."
            ) from error
        if not self.root.is_dir():
            raise EvidenceFileError("Private review evidence storage is unavailable.")

    def _path(self, key: UUID) -> Path:
        if not isinstance(key, UUID):
            raise EvidenceFileError("Invalid private evidence identity.")
        path = self.root / f"{key.hex}.bin"
        if path.is_symlink():
            raise EvidenceFileError("Private evidence is unavailable.")
        return path

    def put(self, key: UUID, content: bytes, media_type: str) -> str:
        validate_evidence_content(content, media_type)
        digest = hashlib.sha256(content).hexdigest()
        path = self._path(key)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileExistsError:
            # An exact retry may reuse a privately staged file after a DB rollback.
            if self.read(key, digest, len(content)) != content:
                raise EvidenceFileError("Private evidence identity is already used.")
            return digest
        except OSError as error:
            raise EvidenceFileError(
                "Private review evidence storage is unavailable."
            ) from error
        try:
            with os.fdopen(descriptor, "wb") as target:
                target.write(content)
                target.flush()
                os.fsync(target.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return digest

    def read(self, key: UUID, expected_digest: str, expected_size: int) -> bytes:
        if (
            type(expected_size) is not int
            or not 0 < expected_size <= MAX_EVIDENCE_BYTES
        ):
            raise EvidenceFileError("Private evidence integrity check failed.")
        path = self._path(key)
        try:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(descriptor, "rb") as source:
                info = os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size != expected_size:
                    raise EvidenceFileError("Private evidence integrity check failed.")
                content = source.read(MAX_EVIDENCE_BYTES + 1)
        except OSError as error:
            raise EvidenceFileError("Private evidence is unavailable.") from error
        if (
            len(content) != expected_size
            or hashlib.sha256(content).hexdigest() != expected_digest
        ):
            raise EvidenceFileError("Private evidence integrity check failed.")
        return content
