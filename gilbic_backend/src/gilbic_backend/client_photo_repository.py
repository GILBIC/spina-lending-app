"""Private client portraits, separate from identity/liveness evidence."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from io import BytesIO
from uuid import UUID
from zoneinfo import ZoneInfo

from PIL import Image, ImageOps, UnidentifiedImageError
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .account_repository import AccountContext
from .area_management_repository import apply_due_client_area_transfers
from .database import open_connection

MAX_PHOTO_BYTES = 5 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}


class InvalidClientPhoto(ValueError):
    pass


class ClientPhotoNotFound(RuntimeError):
    pass


class ClientPhotoConflict(RuntimeError):
    pass


class ClientPhotoForbidden(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PreparedPhoto:
    content: bytes
    content_type: str
    request_sha256: str


def prepare_photo(content: bytes, content_type: str) -> PreparedPhoto:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise InvalidClientPhoto("Choose a JPEG or PNG client photo.")
    if not content or len(content) > MAX_PHOTO_BYTES:
        raise InvalidClientPhoto("Choose a photo up to 5 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as source:
                if (
                    Image.MIME.get(source.format or "") != content_type
                    or getattr(source, "n_frames", 1) != 1
                    or max(source.size) > 8192
                    or source.width * source.height > 24_000_000
                ):
                    raise InvalidClientPhoto(
                        "Choose a single JPEG or PNG photo up to 24 megapixels."
                    )
                source.load()
                oriented = ImageOps.exif_transpose(source)
                oriented.thumbnail((1600, 1600))
                # Rebuild pixels only: no EXIF/GPS, comments, profiles or appended data.
                rgba = oriented.convert("RGBA")
                clean = Image.new("RGB", rgba.size, "white")
                clean.paste(rgba, mask=rgba.getchannel("A"))
                output = BytesIO()
                clean.save(output, "JPEG", quality=85)
    except InvalidClientPhoto:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise InvalidClientPhoto(
            "Choose a complete, readable JPEG or PNG photo."
        ) from exc
    return PreparedPhoto(
        output.getvalue(),
        "image/jpeg",
        sha256(content_type.encode() + b"\0" + content).hexdigest(),
    )


def can_upload(actor: AccountContext) -> bool:
    return (
        actor.status == "active"
        and bool({"employee", "management"}.intersection(actor.roles))
        and "client_onboarding.requirement.review" in actor.permissions
    )


class PostgresClientPhotoRepository:
    def _access(self, connection, *, actor: AccountContext, client_id: UUID):
        if actor.status != "active":
            raise ClientPhotoNotFound("Client photo is not available.")
        office = can_upload(actor)
        collector = "collector" in actor.roles and "route.view" in actor.permissions
        if collector and not office:
            apply_due_client_area_transfers(
                connection, as_of_date=datetime.now(ZoneInfo("Asia/Manila")).date()
            )
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                select client.id from lending.clients client
                left join lending.area_nodes node on node.area_uid=client.area_uid
                where client.id=%s and (
                    %s or (%s and client.user_id=%s) or (
                        %s and client.status='active'
                        and (client.area_uid is null or node.is_active=true)
                        and (lending.collector_area_owner(coalesce(node.full_path,client.area,''))=%s
                            or lending.collector_has_active_delegated_area_access(
                                %s,coalesce(node.full_path,client.area,''),now()))
                    )
                )
            """,
                (
                    client_id,
                    office,
                    "client" in actor.roles,
                    actor.user_id,
                    collector,
                    actor.user_id,
                    actor.user_id,
                ),
            )
            if cursor.fetchone() is None:
                raise ClientPhotoNotFound("Client photo is not available.")

    @staticmethod
    def _latest(connection, client_id, *, include_content=False):
        content_column = sql.SQL(", photo_data") if include_content else sql.SQL("")
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                sql.SQL("""
                select id, client_id, version, content_type, byte_size,
                    uploaded_at, uploaded_by_user_id {}
                from lending.client_photos where client_id=%s order by version desc limit 1
            """).format(content_column),
                (client_id,),
            )
            return cursor.fetchone()

    @staticmethod
    def _payload(actor, client_id, row):
        photo = None
        if row:
            photo = {
                "photo_id": str(row["id"]),
                "version": row["version"],
                "content_type": row["content_type"],
                "byte_size": row["byte_size"],
                "uploaded_at": row["uploaded_at"].isoformat(),
                "uploaded_by_user_id": str(row["uploaded_by_user_id"]),
                "content_url": f"/api/v1/clients/{client_id}/photo/content?photo_id={row['id']}",
            }
        return {
            "client_id": str(client_id),
            "can_upload": can_upload(actor),
            "photo": photo,
        }

    def get(self, *, actor: AccountContext, client_id: UUID):
        with open_connection() as connection:
            self._access(connection, actor=actor, client_id=client_id)
            return self._payload(actor, client_id, self._latest(connection, client_id))

    def content(self, *, actor: AccountContext, client_id: UUID, photo_id: UUID):
        with open_connection() as connection:
            self._access(connection, actor=actor, client_id=client_id)
            row = self._latest(connection, client_id, include_content=True)
            if row is None or row["id"] != photo_id:
                raise ClientPhotoNotFound(
                    "Refresh the client photo to view the current picture."
                )
            return bytes(row["photo_data"]), row["content_type"]

    def upload(
        self,
        *,
        actor: AccountContext,
        client_id: UUID,
        request_id: UUID,
        expected_version: int,
        prepared: PreparedPhoto,
    ):
        if not can_upload(actor):
            raise ClientPhotoForbidden(
                "Office CIF permission is required to upload client photos."
            )
        with (
            open_connection() as connection,
            connection.transaction(),
            connection.cursor(row_factory=dict_row) as cursor,
        ):
            # A retry ID cannot be retargeted to another client, and two
            # staff members cannot replace the same observed version.
            for lock in (
                f"client-photo-request:{actor.user_id}:{request_id}",
                f"client-photo:{client_id}",
            ):
                cursor.execute(
                    "select pg_advisory_xact_lock(hashtextextended(%s,0))",
                    (lock,),
                )
            self._access(connection, actor=actor, client_id=client_id)
            cursor.execute(
                """
                select client_id, request_sha256, expected_version from lending.client_photos
                where uploaded_by_user_id=%s and request_id=%s
            """,
                (actor.user_id, request_id),
            )
            existing = cursor.fetchone()
            current = self._latest(connection, client_id)
            if existing:
                if (
                    existing["client_id"] != client_id
                    or existing["request_sha256"] != prepared.request_sha256
                    or existing["expected_version"] != expected_version
                ):
                    raise ClientPhotoConflict(
                        "This upload request already belongs to a different photo. Refresh the client photo."
                    )
                return self._payload(actor, client_id, current)
            version = current["version"] if current else 0
            if version != expected_version:
                raise ClientPhotoConflict(
                    "The client photo changed. Refresh it before choosing a replacement."
                )
            cursor.execute(
                """
                insert into lending.client_photos(client_id,version,uploaded_by_user_id,
                    request_id,expected_version,request_sha256,content_type,byte_size,photo_data)
                values(%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id
            """,
                (
                    client_id,
                    version + 1,
                    actor.user_id,
                    request_id,
                    expected_version,
                    prepared.request_sha256,
                    prepared.content_type,
                    len(prepared.content),
                    prepared.content,
                ),
            )
            inserted = cursor.fetchone()
            if inserted is None:
                raise RuntimeError("Client photo was not saved.")
            photo_id = inserted["id"]
            cursor.execute(
                """
                insert into core.audit_logs(actor_user_id,action,target_type,target_id,details)
                values(%s,'client.photo_uploaded','client',%s,%s)
            """,
                (
                    actor.user_id,
                    client_id,
                    Jsonb(
                        {
                            "photo_id": str(photo_id),
                            "version": version + 1,
                            "previous_photo_id": str(current["id"])
                            if current
                            else None,
                        }
                    ),
                ),
            )
            return self._payload(actor, client_id, self._latest(connection, client_id))
