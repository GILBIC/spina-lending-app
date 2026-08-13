from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


@dataclass(frozen=True, slots=True)
class EclForwardLookingEvidence:
    id: UUID
    evidence_key: str
    version: int
    source_name: str
    source_reference: str
    observation_period_start: date | None
    observation_period_end: date | None
    forecast_period_start: date
    forecast_period_end: date
    retrieved_at: datetime
    effective_date: date
    management_interpretation: str
    approved_by_user_id: UUID
    approved_at: datetime
    supersedes_evidence_id: UUID | None
    evidence_status: str
    ready_for_new_measurement: bool
    revocation_id: UUID | None
    revocation_reason: str | None
    revoked_by_user_id: UUID | None
    revoked_at: datetime | None


class EclForwardLookingEvidenceError(RuntimeError):
    code = "ecl_forward_looking_evidence_error"


class EclForwardLookingEvidenceNotFound(EclForwardLookingEvidenceError):
    code = "ecl_forward_looking_evidence_not_found"


class EclForwardLookingEvidenceBlocked(EclForwardLookingEvidenceError):
    code = "ecl_forward_looking_evidence_blocked"


class PostgresEclForwardLookingEvidenceRepository:
    """Protected Management forward-looking evidence used by ECL readiness."""

    _COLUMNS = """
        id, evidence_key, version, source_name, source_reference,
        observation_period_start, observation_period_end,
        forecast_period_start, forecast_period_end, retrieved_at,
        effective_date, management_interpretation, approved_by_user_id,
        approved_at, supersedes_evidence_id, evidence_status,
        ready_for_new_measurement, revocation_id, revocation_reason,
        revoked_by_user_id, revoked_at
    """

    def list_evidence(
        self,
        *,
        status: str = "all",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[EclForwardLookingEvidence, ...]:
        where_clause = {
            "all": "true",
            "current": "evidence_status = 'current'",
            "stale": "evidence_status = 'stale'",
            "superseded": "evidence_status = 'superseded'",
            "revoked": "evidence_status = 'revoked'",
            "not_yet_effective": "evidence_status = 'not_yet_effective'",
            "ready": "ready_for_new_measurement = true",
        }.get(status)
        if where_clause is None:
            raise ValueError("Unsupported forward-looking evidence status filter.")

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._COLUMNS}
                    FROM accounting.ecl_forward_looking_evidence_status
                    WHERE {where_clause}
                    ORDER BY evidence_key, version DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                return tuple(self._from_row(row) for row in cursor.fetchall())

    def record_evidence(
        self,
        *,
        evidence_key: str,
        source_name: str,
        source_reference: str,
        observation_period_start: date | None,
        observation_period_end: date | None,
        forecast_period_start: date,
        forecast_period_end: date,
        retrieved_at: datetime,
        effective_date: date,
        management_interpretation: str,
        actor_user_id: UUID,
        supersedes_evidence_id: UUID | None,
    ) -> EclForwardLookingEvidence:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT accounting.record_ecl_forward_looking_evidence(
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        ) AS evidence_id
                        """,
                        (
                            evidence_key,
                            source_name,
                            source_reference,
                            observation_period_start,
                            observation_period_end,
                            forecast_period_start,
                            forecast_period_end,
                            retrieved_at,
                            effective_date,
                            management_interpretation,
                            actor_user_id,
                            supersedes_evidence_id,
                        ),
                    )
                    created = cursor.fetchone()
                    evidence_id = created["evidence_id"]
                    cursor.execute(
                        f"""
                        SELECT {self._COLUMNS}
                        FROM accounting.ecl_forward_looking_evidence_status
                        WHERE id = %s
                        """,
                        (evidence_id,),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise EclForwardLookingEvidenceNotFound(
                            "Forward-looking evidence was not found after protected creation."
                        )
                    return self._from_row(row)
        except psycopg.Error as error:
            raise self._translate_error(error) from error

    def revoke_evidence(
        self,
        *,
        evidence_id: UUID,
        reason: str,
        actor_user_id: UUID,
    ) -> EclForwardLookingEvidence:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "SELECT accounting.revoke_ecl_forward_looking_evidence(%s, %s, %s)",
                        (evidence_id, reason, actor_user_id),
                    )
                    cursor.fetchone()
                    cursor.execute(
                        f"""
                        SELECT {self._COLUMNS}
                        FROM accounting.ecl_forward_looking_evidence_status
                        WHERE id = %s
                        """,
                        (evidence_id,),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise EclForwardLookingEvidenceNotFound(
                            "Forward-looking evidence was not found after revocation."
                        )
                    return self._from_row(row)
        except psycopg.Error as error:
            raise self._translate_error(error) from error

    @staticmethod
    def _from_row(row) -> EclForwardLookingEvidence:
        return EclForwardLookingEvidence(
            id=row["id"],
            evidence_key=str(row["evidence_key"]),
            version=int(row["version"]),
            source_name=str(row["source_name"]),
            source_reference=str(row["source_reference"]),
            observation_period_start=row["observation_period_start"],
            observation_period_end=row["observation_period_end"],
            forecast_period_start=row["forecast_period_start"],
            forecast_period_end=row["forecast_period_end"],
            retrieved_at=row["retrieved_at"],
            effective_date=row["effective_date"],
            management_interpretation=str(row["management_interpretation"]),
            approved_by_user_id=row["approved_by_user_id"],
            approved_at=row["approved_at"],
            supersedes_evidence_id=row["supersedes_evidence_id"],
            evidence_status=str(row["evidence_status"]),
            ready_for_new_measurement=bool(row["ready_for_new_measurement"]),
            revocation_id=row["revocation_id"],
            revocation_reason=(str(row["revocation_reason"]) if row["revocation_reason"] else None),
            revoked_by_user_id=row["revoked_by_user_id"],
            revoked_at=row["revoked_at"],
        )

    @staticmethod
    def _translate_error(error: psycopg.Error) -> EclForwardLookingEvidenceError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lowered = message.lower()
        if "does not exist" in lowered:
            return EclForwardLookingEvidenceNotFound(message)
        blocked_markers = (
            "required",
            "must",
            "already been superseded",
            "revoked evidence",
            "same evidence key",
            "explicit supersedes",
            "unique constraint",
        )
        if any(marker in lowered for marker in blocked_markers):
            return EclForwardLookingEvidenceBlocked(message)
        return EclForwardLookingEvidenceError(
            message or "Forward-looking ECL evidence operation failed."
        )
