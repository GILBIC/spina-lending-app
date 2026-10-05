"""Authorized historical calculation review without exposing private snapshots."""

from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .accounting_book_repository import book_identity_payload, read_book_identity
from .retained_cutoff_assessment_repository import (
    CutoffAssessmentConflict,
    _candidate_connection,
    _error,
    _money,
    _require_actor,
)


def _prepared_payload(row):
    source = row["source_snapshot"]
    measured = row["measurement_snapshot"]
    return {
        "preparation_id": str(row["id"]),
        "confirmation_digest": row["confirmation_digest"],
        "source_digest": row["source_digest"],
        "book_id": str(row["book_id"]),
        "period_id": str(row["fiscal_period_id"]),
        "loan_id": str(row["loan_id"]),
        "as_of_date": row["as_of_date"].isoformat(),
        "calculated_at": row["calculated_at"].isoformat(),
        "policy_version": measured["policy_version"],
        "incremental_interest": _money(source["eir"]["incremental_interest"]),
        "cumulative_interest": _money(source["eir"]["cumulative_interest"]),
        "ecl_amount": _money(measured["ecl_amount"]),
        "prior_allowance": _money(measured["prior_allowance"]),
        "allowance_delta": _money(measured["allowance_delta"]),
        "scenario_count": len(measured["scenarios"]),
        "review_inputs": {
            "risk_review": {
                key: row["risk_review"][key]
                for key in (
                    "as_of_date",
                    "stage_label",
                    "default_label",
                    "write_off_label",
                    "recovery_label",
                    "primary_evidence_basis",
                    "evidence_reference",
                    "review_note",
                )
            },
            "scenarios": [
                {
                    "scenario_key": scenario["scenario_key"],
                    "probability": str(scenario["probability"]),
                    "evidence_reference": scenario["evidence_reference"],
                    "management_rationale": scenario["management_rationale"],
                    "forward_evidence_ids": [
                        str(value) for value in scenario["forward_evidence_ids"]
                    ],
                    "expected_cash_flows": [
                        {
                            "cash_date": flow["cash_date"],
                            "amount": _money(flow["amount"]),
                        }
                        for flow in scenario["expected_cash_flows"]
                    ],
                }
                for scenario in row["scenarios"]
            ],
            "review_rationale": row["review_rationale"],
        },
        "comprehensive_source_coverage": False,
    }


class PostgresElapsedPeriodAssessmentRepository:
    def load_candidate(self, *, period_id, loan_id, actor_user_id):
        try:
            with (
                _candidate_connection() as conn,
                conn.cursor(row_factory=dict_row) as cursor,
            ):
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                _require_actor(cursor, actor_user_id, "accounting.view")
                book = book_identity_payload(read_book_identity(cursor))
                cursor.execute(
                    "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS candidate",
                    (period_id, loan_id),
                )
                candidate = cursor.fetchone()["candidate"]
                cursor.execute(
                    "SELECT accounting.period_elapsed_loan_assessment_exact(%s,%s) AS exact",
                    (period_id, loan_id),
                )
                exact = cursor.fetchone()["exact"]
                ready = candidate.get("ready") is True
                source = candidate.get("snapshot", {}) if ready else {}
                cursor.execute(
                    "SELECT * FROM accounting.loan_elapsed_assessment_preparations "
                    "WHERE fiscal_period_id=%s AND loan_id=%s AND source_digest=%s "
                    "ORDER BY calculated_at DESC,id DESC LIMIT 1",
                    (period_id, loan_id, candidate.get("source_digest")),
                )
                prepared = cursor.fetchone()
                return {
                    "book": book,
                    "period_id": str(period_id),
                    "loan_id": str(loan_id),
                    "ready": ready,
                    "blockers": candidate.get("blockers", []),
                    "as_of_date": candidate.get("as_of_date"),
                    "source_digest": candidate.get("source_digest") if ready else None,
                    "current_confirmation": bool(exact),
                    "eir": {
                        key: _money(source["eir"][key])
                        for key in (
                            "cumulative_interest",
                            "prior_recognized_interest",
                            "incremental_interest",
                        )
                    }
                    if ready
                    else None,
                    "gross_carrying_amount": _money(source.get("gross_carrying_amount"))
                    if ready
                    else None,
                    "prior_allowance": _money(source.get("prior_allowance"))
                    if ready
                    else None,
                    "days_past_due": source.get("dpd") if ready else None,
                    "preparation": _prepared_payload(prepared)
                    if ready and prepared
                    else None,
                    "comprehensive_source_coverage": False,
                    "notice": "The economic cutoff is distinct from actual calculation time. Explicit historical risk and forecast inputs are required; unsupported source transitions remain blocked.",
                }
        except psycopg.Error as error:
            raise _error(error) from error

    def prepare(
        self,
        *,
        period_id,
        loan_id,
        expected_book_id,
        source_digest,
        risk_review,
        scenarios,
        review_rationale,
        actor_user_id,
    ):
        try:
            with (
                _candidate_connection() as conn,
                conn.cursor(row_factory=dict_row) as cursor,
            ):
                self._write_authority(
                    cursor,
                    actor_user_id,
                    expected_book_id,
                    "accounting.period.close.prepare",
                )
                cursor.execute(
                    "SELECT accounting.prepare_elapsed_loan_period_assessment(%s,%s,%s,%s,%s,%s,%s) AS id",
                    (
                        period_id,
                        loan_id,
                        actor_user_id,
                        source_digest,
                        Jsonb(risk_review),
                        Jsonb(scenarios),
                        review_rationale,
                    ),
                )
                prepared = cursor.fetchone()["id"]
                cursor.execute(
                    "SELECT * FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
                    (prepared,),
                )
                return _prepared_payload(cursor.fetchone())
        except psycopg.Error as error:
            raise _error(error) from error

    def confirm(
        self, *, preparation_id, expected_book_id, confirmation_digest, actor_user_id
    ) -> UUID:
        try:
            with (
                _candidate_connection() as conn,
                conn.cursor(row_factory=dict_row) as cursor,
            ):
                self._write_authority(
                    cursor,
                    actor_user_id,
                    expected_book_id,
                    "accounting.period.close.post",
                )
                cursor.execute(
                    "SELECT accounting.post_elapsed_loan_period_assessment(%s,%s,%s) AS id",
                    (preparation_id, actor_user_id, confirmation_digest),
                )
                return cursor.fetchone()["id"]
        except psycopg.Error as error:
            raise _error(error) from error

    @staticmethod
    def _write_authority(cursor, actor_user_id, expected_book_id, permission):
        cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
        _require_actor(cursor, actor_user_id, permission)
        book = read_book_identity(cursor)
        if book is None or book.book_id != expected_book_id:
            raise CutoffAssessmentConflict(
                "The confirmed accounting book does not match this deployment."
            )
