"""Private retained source snapshots with a small Management review projection."""

import json
from contextlib import contextmanager
from decimal import Decimal
from typing import LiteralString
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import set_json_loads

from .accounting_book_repository import book_identity_payload, read_book_identity
from .accounting_query import require_row
from .database import open_connection


class CutoffAssessmentError(RuntimeError):
    code = "cutoff_assessment_unavailable"


class CutoffAssessmentDenied(CutoffAssessmentError):
    code = "cutoff_assessment_permission_required"


class CutoffAssessmentConflict(CutoffAssessmentError):
    code = "cutoff_assessment_source_conflict"


def _error(error: psycopg.Error) -> CutoffAssessmentError:
    if error.sqlstate == "42501":
        return CutoffAssessmentDenied(
            "Current Management accounting permission is required."
        )
    if error.sqlstate in {
        "P0001",
        "22023",
        "23514",
        "23505",
        "40001",
        "40P01",
        "55000",
    }:
        return CutoffAssessmentConflict(
            "Assessment source evidence changed or is unsupported; reload the authorized candidate."
        )
    return CutoffAssessmentError("Retained cutoff assessment is unavailable.")


def _require_actor(cursor, actor_user_id: UUID, permission: str) -> None:
    cursor.execute(
        """SELECT actor.id FROM core.users actor
           JOIN core.user_roles membership ON membership.user_id=actor.id
           JOIN core.roles role ON role.id=membership.role_id
           JOIN core.role_permissions permission ON permission.role_id=role.id
           WHERE actor.id=%s AND actor.status='active' AND role.code='management'
             AND permission.permission_code=%s
           FOR SHARE OF actor,membership,role,permission""",
        (actor_user_id, permission),
    )
    if cursor.fetchone() is None:
        raise CutoffAssessmentDenied(
            "Current Management accounting permission is required."
        )


def _money(value) -> str | None:
    return format(Decimal(str(value)), ".2f") if value is not None else None


def _source_json_loads(raw):
    return json.loads(raw, parse_float=Decimal)


@contextmanager
def _candidate_connection():
    with open_connection() as conn:
        # Configure before constructing a cursor: its adapters are copied from
        # the connection. Default JSON floats cannot represent all NUMERIC cents.
        set_json_loads(_source_json_loads, context=conn)
        yield conn


class PostgresRetainedCutoffAssessmentRepository:
    def load_candidate(
        self, *, period_id: UUID, loan_id: UUID, actor_user_id: UUID
    ) -> dict[str, object]:
        try:
            with (
                _candidate_connection() as conn,
                conn.cursor(row_factory=dict_row) as cursor,
            ):
                # Auth locks require a read/write transaction. One snapshot keeps
                # the candidate, identity and retained proof mutually consistent.
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                _require_actor(cursor, actor_user_id, "accounting.view")
                book = book_identity_payload(read_book_identity(cursor))
                cursor.execute(
                    "SELECT accounting.loan_period_assessment_candidate(%s,%s) AS candidate",
                    (period_id, loan_id),
                )
                candidate = require_row(cursor.fetchone())["candidate"]
                cursor.execute(
                    "SELECT accounting.period_loan_assessment_exact(%s,%s) AS exact",
                    (period_id, loan_id),
                )
                current = require_row(cursor.fetchone())["exact"]
                cursor.execute(
                    """SELECT p.id AS preparation_id,confirmation.id AS confirmation_id
                       FROM accounting.loan_period_assessment_preparations p
                       LEFT JOIN accounting.loan_period_assessment_postings confirmation ON confirmation.preparation_id=p.id
                       WHERE p.fiscal_period_id=%s AND p.loan_id=%s AND p.source_digest=%s
                       ORDER BY p.prepared_at DESC LIMIT 1""",
                    (period_id, loan_id, candidate.get("source_digest")),
                )
                audit = cursor.fetchone()
                ready = candidate.get("ready") is True
                # Never return full loan, journal, forward-evidence or source
                # snapshots. Unsupported Treasury states expose no money detail.
                snapshot = candidate.get("snapshot", {}) if ready else {}
                measured = snapshot.get("measurement") or {}
                anchor = snapshot.get("anchor") or {}
                return {
                    "book": book,
                    "period_id": str(period_id),
                    "loan_id": str(loan_id),
                    "ready": ready,
                    "blockers": candidate.get("blockers", []),
                    "source_digest": candidate.get("source_digest") if ready else None,
                    "current_confirmation": bool(current),
                    "preparation_id": str(audit["preparation_id"])
                    if ready and audit
                    else None,
                    "confirmation_id": str(audit["confirmation_id"])
                    if ready and audit and audit["confirmation_id"]
                    else None,
                    "cutoff_date": snapshot.get("cutoff_date"),
                    "policy_version": snapshot.get("policy_version"),
                    "measurement": {
                        "id": measured.get("id"),
                        "date": measured.get("measurement_date"),
                        "version": measured.get("measurement_version"),
                        "calculation_digest": measured.get("calculation_digest"),
                        "ecl_amount": _money(measured.get("ecl_amount")),
                    }
                    if ready
                    else None,
                    "balances": {
                        code: _money(snapshot.get(key))
                        for code, key in (
                            ("1100", "receivable_1100"),
                            ("1110", "receivable_1110"),
                            ("1120", "receivable_1120"),
                            ("1190", "allowance_1190"),
                        )
                    }
                    if ready
                    else None,
                    "boundary": {
                        "anchor_date": anchor.get("anchor_date"),
                        "release_source_key": anchor.get("release_source_event_key"),
                    }
                    if ready
                    else None,
                    "comprehensive_source_coverage": False,
                    "notice": "This confirms an actual Regular release-day boundary and dated ECL allowance. Elapsed EIR, other source adapters, tax and liabilities remain independent checks.",
                }
        except psycopg.Error as error:
            raise _error(error) from error

    def prepare(
        self,
        *,
        period_id: UUID,
        loan_id: UUID,
        expected_book_id: UUID,
        source_digest: str,
        review_rationale: str,
        actor_user_id: UUID,
    ) -> UUID:
        return self._write(
            permission="accounting.period.close.prepare",
            expected_book_id=expected_book_id,
            actor_user_id=actor_user_id,
            query="SELECT accounting.prepare_loan_period_assessment(%s,%s,%s,%s,%s) AS id",
            values=(period_id, loan_id, actor_user_id, source_digest, review_rationale),
        )

    def confirm(
        self,
        *,
        preparation_id: UUID,
        expected_book_id: UUID,
        source_digest: str,
        actor_user_id: UUID,
    ) -> UUID:
        return self._write(
            permission="accounting.period.close.post",
            expected_book_id=expected_book_id,
            actor_user_id=actor_user_id,
            query="SELECT accounting.post_loan_period_assessment(%s,%s,%s) AS id",
            values=(preparation_id, actor_user_id, source_digest),
        )

    @staticmethod
    def _write(
        *,
        permission: str,
        expected_book_id: UUID,
        actor_user_id: UUID,
        query: LiteralString,
        values: tuple,
    ) -> UUID:
        try:
            with open_connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
                _require_actor(cursor, actor_user_id, permission)
                book = read_book_identity(cursor)
                if book is None or book.book_id != expected_book_id:
                    raise CutoffAssessmentConflict(
                        "The confirmed accounting book does not match this deployment."
                    )
                cursor.execute(query, values)
                return require_row(cursor.fetchone())["id"]
        except psycopg.Error as error:
            raise _error(error) from error
