from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .database import open_connection


MAX_PHOTO_BYTES = 5 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


class RemittancePhotoError(RuntimeError):
    code = "remittance_photo_error"


class RemittancePhotoNotFound(RemittancePhotoError):
    code = "remittance_photo_not_found"


class RemittancePhotoForbidden(RemittancePhotoError):
    code = "remittance_photo_forbidden"


class RemittancePhotoLocked(RemittancePhotoError):
    code = "remittance_photo_locked"


class RemittancePhotoInvalid(RemittancePhotoError):
    code = "remittance_photo_invalid"


@dataclass(frozen=True, slots=True)
class RemittancePhotoRecord:
    photo_id: UUID
    remittance_id: UUID
    version: int
    uploaded_by_user_id: UUID
    original_filename: str
    content_type: str
    byte_size: int
    sha256_hex: str
    uploaded_at: datetime
    photo_data: bytes | None = None


class PostgresRemittancePhotoRepository:
    def upload(
        self,
        *,
        remittance_id: UUID,
        actor_user_id: UUID,
        content_type: str,
        original_filename: str,
        photo_data: bytes,
    ) -> RemittancePhotoRecord:
        normalized_type = content_type.split(";", 1)[0].strip().lower()
        self._validate_image(
            content_type=normalized_type,
            photo_data=photo_data,
        )
        digest = sha256(photo_data).hexdigest()
        clean_filename = original_filename.strip()[:255]

        with open_connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                        (f"gilbic-remittance-photo:{remittance_id}",),
                    )
                    cursor.execute(
                        """
                        select id, collector_user_id, recipient_user_id, status
                        from lending.collection_remittances
                        where id = %s
                        for update
                        """,
                        (remittance_id,),
                    )
                    remittance = cursor.fetchone()
                    if not remittance:
                        raise RemittancePhotoNotFound("Remittance was not found.")
                    if remittance["collector_user_id"] != actor_user_id:
                        raise RemittancePhotoForbidden(
                            "Only the collector who submitted the remittance may upload the handover photo."
                        )
                    if remittance["status"] != "submitted":
                        raise RemittancePhotoLocked(
                            "The handover photo is locked after the recipient accepts the remittance."
                        )

                    cursor.execute(
                        """
                        select *
                        from lending.remittance_handover_photos
                        where remittance_id = %s and sha256_hex = %s
                        """,
                        (remittance_id, digest),
                    )
                    existing = cursor.fetchone()
                    if existing:
                        return self._from_row(existing, include_data=False)

                    cursor.execute(
                        """
                        select coalesce(max(version), 0) + 1 as next_version
                        from lending.remittance_handover_photos
                        where remittance_id = %s
                        """,
                        (remittance_id,),
                    )
                    version = int(cursor.fetchone()["next_version"])
                    uploaded_at = datetime.now(timezone.utc)
                    photo_id = uuid4()
                    cursor.execute(
                        """
                        insert into lending.remittance_handover_photos (
                            id,
                            remittance_id,
                            version,
                            uploaded_by_user_id,
                            original_filename,
                            content_type,
                            byte_size,
                            sha256_hex,
                            photo_data,
                            uploaded_at
                        ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            photo_id,
                            remittance_id,
                            version,
                            actor_user_id,
                            clean_filename,
                            normalized_type,
                            len(photo_data),
                            digest,
                            photo_data,
                            uploaded_at,
                        ),
                    )
                    cursor.execute(
                        """
                        insert into core.audit_logs (
                            actor_user_id,
                            action,
                            target_type,
                            target_id,
                            details,
                            created_at
                        ) values (%s, 'remittance.handover_photo_uploaded', 'collection_remittance', %s, %s, %s)
                        """,
                        (
                            actor_user_id,
                            remittance_id,
                            Jsonb(
                                {
                                    "photo_id": str(photo_id),
                                    "version": version,
                                    "content_type": normalized_type,
                                    "byte_size": len(photo_data),
                                    "sha256_hex": digest,
                                    "original_filename": clean_filename,
                                }
                            ),
                            uploaded_at,
                        ),
                    )

        return RemittancePhotoRecord(
            photo_id=photo_id,
            remittance_id=remittance_id,
            version=version,
            uploaded_by_user_id=actor_user_id,
            original_filename=clean_filename,
            content_type=normalized_type,
            byte_size=len(photo_data),
            sha256_hex=digest,
            uploaded_at=uploaded_at,
        )

    def latest_for_actor(
        self,
        *,
        remittance_id: UUID,
        actor_user_id: UUID,
        include_data: bool,
    ) -> RemittancePhotoRecord:
        select_data = ", photo.photo_data" if include_data else ""
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    select
                        photo.id,
                        photo.remittance_id,
                        photo.version,
                        photo.uploaded_by_user_id,
                        photo.original_filename,
                        photo.content_type,
                        photo.byte_size,
                        photo.sha256_hex,
                        photo.uploaded_at
                        {select_data}
                    from lending.collection_remittances remittance
                    join lateral (
                        select *
                        from lending.remittance_handover_photos candidate
                        where candidate.remittance_id = remittance.id
                        order by candidate.version desc
                        limit 1
                    ) photo on true
                    where remittance.id = %s
                      and %s in (
                          remittance.collector_user_id,
                          remittance.recipient_user_id
                      )
                    """,
                    (remittance_id, actor_user_id),
                )
                row = cursor.fetchone()
        if not row:
            raise RemittancePhotoNotFound(
                "No handover photo is available for this remittance."
            )
        return self._from_row(row, include_data=include_data)

    @staticmethod
    def _validate_image(*, content_type: str, photo_data: bytes) -> None:
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise RemittancePhotoInvalid(
                "Choose a JPEG, PNG, or WebP handover photo."
            )
        if not photo_data:
            raise RemittancePhotoInvalid("The handover photo is empty.")
        if len(photo_data) > MAX_PHOTO_BYTES:
            raise RemittancePhotoInvalid(
                "The handover photo must be 5 MB or smaller."
            )
        detected = PostgresRemittancePhotoRepository._detect_content_type(photo_data)
        if detected != content_type:
            raise RemittancePhotoInvalid(
                "The uploaded file does not match its image type."
            )

    @staticmethod
    def _detect_content_type(photo_data: bytes) -> str | None:
        if photo_data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if photo_data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if (
            len(photo_data) >= 12
            and photo_data[:4] == b"RIFF"
            and photo_data[8:12] == b"WEBP"
        ):
            return "image/webp"
        return None

    @staticmethod
    def _from_row(row, *, include_data: bool) -> RemittancePhotoRecord:
        return RemittancePhotoRecord(
            photo_id=row["id"],
            remittance_id=row["remittance_id"],
            version=int(row["version"]),
            uploaded_by_user_id=row["uploaded_by_user_id"],
            original_filename=str(row["original_filename"] or ""),
            content_type=str(row["content_type"]),
            byte_size=int(row["byte_size"]),
            sha256_hex=str(row["sha256_hex"]),
            uploaded_at=row["uploaded_at"],
            photo_data=bytes(row["photo_data"])
            if include_data and row.get("photo_data") is not None
            else None,
        )
