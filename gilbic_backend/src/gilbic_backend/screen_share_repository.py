"""Consent metadata and frame publication share a single serialization boundary.

One API worker only. No frame bytes enter SQL. A new process identity expires old
consent on access; no client may resume it after a process restart.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from threading import RLock
from typing import Any, TypeVar
from uuid import UUID, uuid4

from psycopg import Cursor
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .account_repository import AccountContext
from .database import open_connection
from .screen_share_frames import Frame, FrameCache, ScreenShareError, validate_png

Row = dict[str, Any]
SQLCursor = Cursor[Row]
T = TypeVar("T")

LIVE = ("pending", "active")
FIELDS = (
    "id",
    "state",
    "generation",
    "viewer_user_id",
    "viewer_device_id",
    "viewer_name",
    "holder_user_id",
    "holder_device_id",
    "holder_name",
    "created_at",
    "expires_at",
    "lease_expires_at",
    "ended_reason",
)
SELECT = """SELECT s.*,v.full_name AS viewer_name,h.full_name AS holder_name
 FROM core.screen_share_sessions s JOIN core.users v ON v.id=s.viewer_user_id
 JOIN core.users h ON h.id=s.holder_user_id"""


def required(row: Row | None) -> Row:
    if row is None:
        raise RuntimeError("Expected screen sharing database row is missing.")
    return row


def payload(row: Row) -> Row:
    return {
        key: str(row[key]) if isinstance(row[key], UUID) else row[key] for key in FIELDS
    }


class PostgresScreenShareRepository:
    def __init__(
        self, *, cache: FrameCache | None = None, process_id: UUID | None = None
    ) -> None:
        self.cache = cache if cache is not None else FrameCache()
        self.process_id = process_id or uuid4()
        self._lock = RLock()

    def _audit(
        self, c: SQLCursor, row: Row, action: str, actor: UUID | None = None
    ) -> None:
        c.execute(
            """INSERT INTO core.audit_logs(actor_user_id,action,target_type,target_id,details)
        VALUES(%s,%s,'screen_share',%s,%s)""",
            (
                actor or row["viewer_user_id"],
                "screen_share." + action,
                row["id"],
                Jsonb(
                    {
                        "viewer_device_id": str(row["viewer_device_id"]),
                        "holder_user_id": str(row["holder_user_id"]),
                        "holder_device_id": str(row["holder_device_id"]),
                        "generation": row["generation"],
                    }
                ),
            ),
        )

    def _end(
        self, c: SQLCursor, row: Row, state: str, reason: str, actor: UUID | None = None
    ) -> Row:
        if row["state"] in LIVE:
            row.update(
                required(
                    c.execute(
                        """UPDATE core.screen_share_sessions SET state=%s,ended_reason=%s,
              generation=generation+1,lease_expires_at=NULL WHERE id=%s RETURNING state,ended_reason,generation,lease_expires_at""",
                        (state, reason, row["id"]),
                    ).fetchone()
                )
            )
            self._audit(c, row, state, actor)
        self.cache.clear(row["id"])
        return payload(row)

    def _begin(self, c: SQLCursor) -> datetime:
        # Serializes caps/request creation across separate connections as well as the
        # process lock; a second API worker is unsupported and fails old grants closed.
        c.execute("SET LOCAL statement_timeout = '5s'")
        c.execute("SET LOCAL lock_timeout = '2s'")
        c.execute("SELECT pg_advisory_xact_lock(7341020134)")
        now = required(c.execute("SELECT clock_timestamp() AS now").fetchone())["now"]
        stale = c.execute(
            SELECT
            + """ WHERE s.state IN ('pending','active') AND
          (s.process_id<>%s OR s.expires_at<=%s OR (s.state='active' AND s.lease_expires_at<=%s)) FOR UPDATE OF s""",
            (self.process_id, now, now),
        ).fetchall()
        for row in stale:
            self._end(
                c,
                row,
                "expired",
                "process_changed"
                if row["process_id"] != self.process_id
                else "timeout",
            )
        return now

    def _identity(self, c: SQLCursor, user: UUID, device: UUID | None) -> bool:
        u = c.execute(
            "SELECT status FROM core.users WHERE id=%s FOR SHARE", (user,)
        ).fetchone()
        d = c.execute(
            "SELECT user_id,status FROM core.devices WHERE id=%s FOR SHARE", (device,)
        ).fetchone()
        return bool(
            u
            and d
            and u["status"] == "active"
            and d["status"] == "active"
            and d["user_id"] == user
        )

    def _viewer(self, c: SQLCursor, user: UUID) -> bool:
        return bool(
            c.execute(
                """SELECT ur.user_id FROM core.user_roles ur JOIN core.roles r ON r.id=ur.role_id
         JOIN core.role_permissions rp ON rp.role_id=r.id
         WHERE ur.user_id=%s AND r.code='management' AND rp.permission_code='screen_share.view'
         FOR SHARE OF ur,r,rp""",
                (user,),
            ).fetchone()
        )

    def _participants(self, c: SQLCursor, row: Row) -> bool:
        pairs = sorted(
            [
                (row["viewer_user_id"], row["viewer_device_id"]),
                (row["holder_user_id"], row["holder_device_id"]),
            ]
        )
        valid = [self._identity(c, u, d) for u, d in pairs]
        return all(valid) and self._viewer(c, row["viewer_user_id"])

    def _one(
        self,
        actor: AccountContext,
        sid: UUID,
        operation: Callable[[SQLCursor, Row, datetime], T],
    ) -> T:
        outcome = None
        with self._lock:
            with (
                open_connection() as connection,
                connection.transaction(),
                connection.cursor(row_factory=dict_row) as c,
            ):
                now = self._begin(c)
                row = c.execute(
                    SELECT + " WHERE s.id=%s FOR UPDATE OF s", (sid,)
                ).fetchone()
                participant = bool(
                    row
                    and (actor.user_id, actor.registered_device_id)
                    in (
                        (row["viewer_user_id"], row["viewer_device_id"]),
                        (row["holder_user_id"], row["holder_device_id"]),
                    )
                )
                if row is None or not participant:
                    outcome = ScreenShareError(404, "Screen request was not found.")
                elif not self._participants(c, row):
                    self._end(c, row, "stopped", "authorization_revoked")
                    outcome = ScreenShareError(
                        403, "Screen sharing authorization ended."
                    )
                else:
                    try:
                        outcome = operation(c, row, now)
                    except ScreenShareError as error:
                        outcome = error
            if isinstance(outcome, ScreenShareError):
                raise outcome
            return outcome

    def targets(self, actor: AccountContext) -> Row:
        with (
            self._lock,
            open_connection() as connection,
            connection.transaction(),
            connection.cursor(row_factory=dict_row) as c,
        ):
            self._begin(c)
            if not self._identity(
                c, actor.user_id, actor.registered_device_id
            ) or not self._viewer(c, actor.user_id):
                raise ScreenShareError(
                    403, "Management screen viewing permission is required."
                )
            rows = c.execute(
                """SELECT u.id AS user_id,d.id AS device_id,u.full_name AS display_name,
              d.platform || ' · last seen ' || COALESCE(to_char(d.last_seen_at AT TIME ZONE 'UTC',
                  'YYYY-MM-DD HH24:MI:SS') || ' UTC','not recorded') AS device_name
                  FROM core.users u JOIN core.devices d ON d.user_id=u.id
              WHERE u.status='active' AND d.status='active' AND u.id<>%s
              ORDER BY d.last_seen_at DESC NULLS LAST,u.full_name,u.id,d.id LIMIT 100""",
                (actor.user_id,),
            ).fetchall()
            return {"targets": rows}

    def request(
        self, actor: AccountContext, holder_user_id: UUID, holder_device_id: UUID
    ) -> Row:
        outcome = None
        with (
            self._lock,
            open_connection() as connection,
            connection.transaction(),
            connection.cursor(row_factory=dict_row) as c,
        ):
            now = self._begin(c)
            if not self._identity(
                c, actor.user_id, actor.registered_device_id
            ) or not self._viewer(c, actor.user_id):
                raise ScreenShareError(
                    403, "Management screen viewing permission is required."
                )
            if holder_user_id == actor.user_id or not self._identity(
                c, holder_user_id, holder_device_id
            ):
                raise ScreenShareError(404, "Active target device was not found.")
            if (
                required(
                    c.execute(
                        "SELECT count(*) AS n FROM core.screen_share_sessions WHERE viewer_user_id=%s AND created_at>%s",
                        (actor.user_id, now - timedelta(seconds=60)),
                    ).fetchone()
                )["n"]
                >= 3
            ):
                raise ScreenShareError(429, "Wait before requesting another screen.")
            if (
                required(
                    c.execute(
                        "SELECT count(*) AS n FROM core.screen_share_sessions WHERE state='pending'"
                    ).fetchone()
                )["n"]
                >= 100
            ):
                raise ScreenShareError(429, "Too many pending screen requests.")
            if c.execute(
                """SELECT 1 FROM core.screen_share_sessions WHERE state IN ('pending','active')
              AND (viewer_device_id=%s OR holder_device_id=%s)""",
                (actor.registered_device_id, holder_device_id),
            ).fetchone():
                raise ScreenShareError(409, "This device already has a screen request.")
            sid = uuid4()
            c.execute(
                """INSERT INTO core.screen_share_sessions(id,process_id,viewer_user_id,viewer_device_id,
            holder_user_id,holder_device_id,state,created_at,expires_at) VALUES(%s,%s,%s,%s,%s,%s,'pending',%s,%s)""",
                (
                    sid,
                    self.process_id,
                    actor.user_id,
                    actor.registered_device_id,
                    holder_user_id,
                    holder_device_id,
                    now,
                    now + timedelta(seconds=60),
                ),
            )
            row = c.execute(SELECT + " WHERE s.id=%s", (sid,)).fetchone()
            row = required(row)
            self._audit(c, row, "requested", actor.user_id)
            outcome = payload(row)
        return outcome

    def pending(self, actor: AccountContext) -> Row:
        with (
            self._lock,
            open_connection() as connection,
            connection.transaction(),
            connection.cursor(row_factory=dict_row) as c,
        ):
            self._begin(c)
            if not self._identity(c, actor.user_id, actor.registered_device_id):
                raise ScreenShareError(
                    403, "An active account and device are required."
                )
            rows = c.execute(
                SELECT
                + " WHERE s.holder_user_id=%s AND s.holder_device_id=%s AND s.state='pending' LIMIT 1 FOR UPDATE OF s",
                (actor.user_id, actor.registered_device_id),
            ).fetchall()
            result = []
            for row in rows:
                if self._participants(c, row):
                    result.append(payload(row))
                else:
                    self._end(c, row, "stopped", "authorization_revoked")
            return {"sessions": result}

    def status(self, actor: AccountContext, sid: UUID) -> Row:
        return self._one(actor, sid, lambda c, row, now: payload(row))

    def _holder_pending(self, actor: AccountContext, row: Row, generation: int) -> None:
        if (actor.user_id, actor.registered_device_id) != (
            row["holder_user_id"],
            row["holder_device_id"],
        ):
            raise ScreenShareError(404, "Screen request was not found.")
        if row["state"] != "pending" or row["generation"] != generation:
            raise ScreenShareError(409, "Screen request is no longer pending.")

    def accept(self, actor: AccountContext, sid: UUID, generation: int) -> Row:
        def perform(c: SQLCursor, row: Row, now: datetime):
            self._holder_pending(actor, row, generation)
            if (
                required(
                    c.execute(
                        "SELECT count(*) AS n FROM core.screen_share_sessions WHERE state='active'"
                    ).fetchone()
                )["n"]
                >= 2
            ):
                raise ScreenShareError(429, "Two screens are already being shared.")
            row.update(
                required(
                    c.execute(
                        """UPDATE core.screen_share_sessions SET state='active',expires_at=%s,
              lease_expires_at=%s WHERE id=%s RETURNING state,expires_at,lease_expires_at""",
                        (
                            now + timedelta(seconds=600),
                            now + timedelta(seconds=15),
                            row["id"],
                        ),
                    ).fetchone()
                )
            )
            self._audit(c, row, "accepted", actor.user_id)
            return payload(row)

        return self._one(actor, sid, perform)

    def decline(self, actor: AccountContext, sid: UUID, generation: int) -> Row:
        def perform(c: SQLCursor, row: Row, now: datetime):
            self._holder_pending(actor, row, generation)
            return self._end(c, row, "declined", "holder_declined", actor.user_id)

        return self._one(actor, sid, perform)

    def stop(self, actor: AccountContext, sid: UUID, generation: int) -> Row:
        def perform(c: SQLCursor, row: Row, now: datetime):
            if row["state"] not in LIVE:
                return payload(row)
            if row["generation"] != generation:
                raise ScreenShareError(409, "Screen generation changed.")
            return self._end(c, row, "stopped", "participant_stopped", actor.user_id)

        return self._one(actor, sid, perform)

    def check_upload(
        self, actor: AccountContext, sid: UUID, generation: int, sequence: int
    ) -> None:
        def perform(c: SQLCursor, row: Row, now: datetime):
            if (actor.user_id, actor.registered_device_id) != (
                row["holder_user_id"],
                row["holder_device_id"],
            ):
                raise ScreenShareError(404, "Screen request was not found.")
            if (
                row["state"] != "active"
                or row["generation"] != generation
                or sequence <= row["last_sequence"]
            ):
                raise ScreenShareError(
                    409, "Screen generation or sequence is no longer active."
                )

        return self._one(actor, sid, perform)

    def upload(
        self,
        actor: AccountContext,
        sid: UUID,
        generation: int,
        sequence: int,
        data: bytes,
    ) -> None:
        validate_png(data)

        def perform(c: SQLCursor, row: Row, now: datetime):
            if (actor.user_id, actor.registered_device_id) != (
                row["holder_user_id"],
                row["holder_device_id"],
            ):
                raise ScreenShareError(404, "Screen request was not found.")
            if (
                row["state"] != "active"
                or row["generation"] != generation
                or sequence <= row["last_sequence"]
            ):
                raise ScreenShareError(
                    409, "Screen generation or sequence is no longer active."
                )
            if row["last_frame_at"] and now - row["last_frame_at"] < timedelta(
                seconds=1
            ):
                raise ScreenShareError(429, "Send at most one screen image per second.")
            c.execute(
                "UPDATE core.screen_share_sessions SET last_sequence=%s,last_frame_at=%s,lease_expires_at=%s WHERE id=%s",
                (
                    sequence,
                    now,
                    min(row["expires_at"], now + timedelta(seconds=15)),
                    row["id"],
                ),
            )
            return row["id"]

        with self._lock:
            key = self._one(actor, sid, perform)
            self.cache.put(key, generation, sequence, data)

    def frame(self, actor: AccountContext, sid: UUID) -> Frame | None:
        def perform(c: SQLCursor, row: Row, now: datetime):
            if (actor.user_id, actor.registered_device_id) != (
                row["viewer_user_id"],
                row["viewer_device_id"],
            ):
                raise ScreenShareError(404, "Screen request was not found.")
            if row["state"] != "active":
                raise ScreenShareError(409, "Screen sharing ended.")
            frame = self.cache.get(row["id"])
            if frame and (
                frame.generation != row["generation"]
                or frame.sequence != row["last_sequence"]
            ):
                self.cache.clear(row["id"])
                return None
            return frame

        return self._one(actor, sid, perform)
