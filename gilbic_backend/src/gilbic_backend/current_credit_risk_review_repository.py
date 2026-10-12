"""Source-bound credit-risk review with a deliberately small public projection."""

from datetime import timezone
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .accounting_query import require_row
from .retained_cutoff_assessment_repository import (
    _candidate_connection,
    _error,
    _money,
    _require_actor,
)


def public_context(source: dict) -> dict[str, object]:
    result: dict[str, object] = {
        key: source.get(key)
        for key in (
            "book_id",
            "period_id",
            "loan_id",
            "ready",
            "blockers",
            "as_of_date",
            "source_digest",
            "schedule_id",
            "schedule_version",
            "days_past_due",
            "thirty_day_sicr_backstop_reached",
            "ninety_day_default_backstop_reached",
        )
    }
    result["due_unpaid_amount"] = _money(source.get("due_unpaid_amount"))
    review_fields = (
        "id",
        "review_version",
        "stage_label",
        "default_label",
        "write_off_label",
        "recovery_label",
        "reviewed_at",
    )
    for name in ("prior_review", "inherited_review"):
        review = source.get(name)
        fields = review_fields + (("loan_id",) if name == "inherited_review" else ())
        result[name] = (
            {key: review.get(key) for key in fields}
            if isinstance(review, dict)
            else None
        )
    return result


class PostgresCurrentCreditRiskReviewRepository:
    def load_context(
        self, *, period_id: UUID, loan_id: UUID, actor_user_id: UUID
    ) -> dict[str, object]:
        try:
            with (
                _candidate_connection() as conn,
                conn.cursor(row_factory=dict_row) as cursor,
            ):
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                _require_actor(cursor, actor_user_id, "accounting.view")
                cursor.execute(
                    "SELECT accounting.current_credit_risk_review_context(%s,%s) AS value",
                    (period_id, loan_id),
                )
                return public_context(require_row(cursor.fetchone())["value"])
        except psycopg.Error as error:
            raise _error(error) from error

    def retain(
        self,
        *,
        period_id: UUID,
        loan_id: UUID,
        expected_book_id: UUID,
        source_digest: str,
        review: dict,
        actor_user_id: UUID,
    ) -> dict[str, object]:
        try:
            with (
                _candidate_connection() as conn,
                conn.cursor(row_factory=dict_row) as cursor,
            ):
                cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
                _require_actor(
                    cursor, actor_user_id, "accounting.ecl.credit_risk_label.review"
                )
                cursor.execute(
                    "SELECT accounting.retain_current_credit_risk_review(%s,%s,%s,%s,%s,%s) AS id",
                    (
                        period_id,
                        loan_id,
                        expected_book_id,
                        source_digest,
                        Jsonb(review),
                        actor_user_id,
                    ),
                )
                identity = require_row(cursor.fetchone())["id"]
                cursor.execute(
                    """SELECT id,created_at,stage_label,default_label,recovery_label,
                       (created_at AT TIME ZONE 'Asia/Manila')::date AS as_of_date
                       FROM accounting.ecl_credit_risk_label_reviews WHERE id=%s""",
                    (identity,),
                )
                row = require_row(cursor.fetchone())
                return {
                    "review_id": row["id"],
                    "reviewed_at": row["created_at"]
                    .astimezone(timezone.utc)
                    .isoformat(),
                    "as_of_date": row["as_of_date"].isoformat(),
                    "stage_label": row["stage_label"],
                    "default_label": row["default_label"],
                    "recovery_label": row["recovery_label"],
                }
        except psycopg.Error as error:
            raise _error(error) from error
