from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


@dataclass(frozen=True, slots=True)
class EclOutcomeReviewSummary:
    episode_count: int
    structurally_usable_count: int
    source_review_required_count: int
    pending_outcome_review_count: int
    reviewed_outcome_count: int
    reviewed_default_count: int
    reviewed_non_default_count: int
    review_status: str
    ecl_included: bool
    ecl_amount: Decimal | None
    ready_to_post: bool


@dataclass(frozen=True, slots=True)
class EclOutcomeReviewEpisode:
    historical_episode_id: int
    episode_key: str
    borrower_key: str
    episode_sequence: int
    loan_type: str
    source_event: str
    release_date: date | None
    due_date: date | None
    principal: Decimal
    contractual_total: Decimal | None
    interest_rate: Decimal | None
    outcome_evidence: str
    outcome_date: date | None
    renewal_rollover_amount: Decimal | None
    cash_collected: Decimal
    positive_payment_count: int
    zero_payment_observation_count: int
    observed_collection_days: int
    source_quality_status: str
    source_quality_note: str | None
    explicit_default_label: bool | None
    review_id: int | None
    review_version: int | None
    evidence_basis: str | None
    evidence_reference: str | None
    review_note: str | None
    reviewer_name: str | None
    reviewed_at: datetime | None
    review_status: str


class EclOutcomeReviewError(RuntimeError):
    code = "ecl_outcome_review_error"


class EclOutcomeReviewNotFound(EclOutcomeReviewError):
    code = "ecl_outcome_review_not_found"


class EclOutcomeReviewSourceBlocked(EclOutcomeReviewError):
    code = "ecl_outcome_review_source_blocked"


class PostgresEclOutcomeReviewRepository:
    """Read the Stage 5E.3 queue and invoke the protected outcome review function."""

    def load_review_queue(
        self,
        *,
        review_status: str = "pending",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[EclOutcomeReviewSummary, tuple[EclOutcomeReviewEpisode, ...]]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        episode_count,
                        structurally_usable_count,
                        source_review_required_count,
                        pending_outcome_review_count,
                        reviewed_outcome_count,
                        reviewed_default_count,
                        reviewed_non_default_count,
                        review_status,
                        ecl_included,
                        ecl_amount,
                        ready_to_post
                    from accounting.ecl_outcome_label_review_summary
                    """
                )
                summary_row = cursor.fetchone()

                where_clause = {
                    "pending": "review_status = 'outcome_review_required'",
                    "reviewed": "review_status = 'outcome_reviewed'",
                    "source_review": "review_status = 'source_review_required'",
                    "all": "true",
                }.get(review_status)
                if where_clause is None:
                    raise ValueError("Unsupported ECL outcome review status filter.")

                cursor.execute(
                    f"""
                    select
                        historical_episode_id,
                        episode_key,
                        borrower_key,
                        episode_sequence,
                        loan_type,
                        source_event,
                        release_date,
                        due_date,
                        principal,
                        contractual_total,
                        interest_rate,
                        outcome_evidence,
                        outcome_date,
                        renewal_rollover_amount,
                        cash_collected,
                        positive_payment_count,
                        zero_payment_observation_count,
                        observed_collection_days,
                        source_quality_status,
                        source_quality_note,
                        explicit_default_label,
                        review_id,
                        review_version,
                        evidence_basis,
                        evidence_reference,
                        review_note,
                        reviewer_name,
                        reviewed_at,
                        review_status
                    from accounting.ecl_outcome_label_review_queue
                    where {where_clause}
                    order by
                        case review_status
                            when 'outcome_review_required' then 0
                            when 'source_review_required' then 1
                            else 2
                        end,
                        release_date nulls last,
                        historical_episode_id
                    limit %s offset %s
                    """,
                    (limit, offset),
                )
                episodes = tuple(
                    self._episode_from_row(row) for row in cursor.fetchall()
                )

        return self._summary_from_row(summary_row), episodes

    def review_outcome(
        self,
        *,
        historical_episode_id: int,
        default_label: bool,
        evidence_basis: str,
        evidence_reference: str,
        review_note: str,
        actor_user_id: UUID,
    ) -> EclOutcomeReviewEpisode:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        select accounting.review_ecl_historical_outcome(
                            %s, %s, %s, %s, %s, %s
                        ) as review_id
                        """,
                        (
                            historical_episode_id,
                            default_label,
                            evidence_basis,
                            evidence_reference,
                            review_note,
                            actor_user_id,
                        ),
                    )
                    cursor.fetchone()
                    cursor.execute(
                        """
                        select
                            historical_episode_id,
                            episode_key,
                            borrower_key,
                            episode_sequence,
                            loan_type,
                            source_event,
                            release_date,
                            due_date,
                            principal,
                            contractual_total,
                            interest_rate,
                            outcome_evidence,
                            outcome_date,
                            renewal_rollover_amount,
                            cash_collected,
                            positive_payment_count,
                            zero_payment_observation_count,
                            observed_collection_days,
                            source_quality_status,
                            source_quality_note,
                            explicit_default_label,
                            review_id,
                            review_version,
                            evidence_basis,
                            evidence_reference,
                            review_note,
                            reviewer_name,
                            reviewed_at,
                            review_status
                        from accounting.ecl_outcome_label_review_queue
                        where historical_episode_id = %s
                        """,
                        (historical_episode_id,),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise EclOutcomeReviewNotFound(
                            "Historical ECL episode was not found after review."
                        )
                    return self._episode_from_row(row)
        except psycopg.Error as error:
            raise self._review_error(error) from error

    @staticmethod
    def _summary_from_row(row) -> EclOutcomeReviewSummary:
        return EclOutcomeReviewSummary(
            episode_count=int(row["episode_count"] or 0),
            structurally_usable_count=int(row["structurally_usable_count"] or 0),
            source_review_required_count=int(row["source_review_required_count"] or 0),
            pending_outcome_review_count=int(row["pending_outcome_review_count"] or 0),
            reviewed_outcome_count=int(row["reviewed_outcome_count"] or 0),
            reviewed_default_count=int(row["reviewed_default_count"] or 0),
            reviewed_non_default_count=int(row["reviewed_non_default_count"] or 0),
            review_status=str(row["review_status"]),
            ecl_included=bool(row["ecl_included"]),
            ecl_amount=(
                Decimal(row["ecl_amount"]) if row["ecl_amount"] is not None else None
            ),
            ready_to_post=bool(row["ready_to_post"]),
        )

    @staticmethod
    def _episode_from_row(row) -> EclOutcomeReviewEpisode:
        def optional_decimal(key: str) -> Decimal | None:
            value = row[key]
            return Decimal(value) if value is not None else None

        return EclOutcomeReviewEpisode(
            historical_episode_id=int(row["historical_episode_id"]),
            episode_key=str(row["episode_key"]),
            borrower_key=str(row["borrower_key"]),
            episode_sequence=int(row["episode_sequence"]),
            loan_type=str(row["loan_type"]),
            source_event=str(row["source_event"]),
            release_date=row["release_date"],
            due_date=row["due_date"],
            principal=Decimal(row["principal"] or 0),
            contractual_total=optional_decimal("contractual_total"),
            interest_rate=optional_decimal("interest_rate"),
            outcome_evidence=str(row["outcome_evidence"]),
            outcome_date=row["outcome_date"],
            renewal_rollover_amount=optional_decimal("renewal_rollover_amount"),
            cash_collected=Decimal(row["cash_collected"] or 0),
            positive_payment_count=int(row["positive_payment_count"] or 0),
            zero_payment_observation_count=int(
                row["zero_payment_observation_count"] or 0
            ),
            observed_collection_days=int(row["observed_collection_days"] or 0),
            source_quality_status=str(row["source_quality_status"]),
            source_quality_note=(
                str(row["source_quality_note"]) if row["source_quality_note"] else None
            ),
            explicit_default_label=row["explicit_default_label"],
            review_id=int(row["review_id"]) if row["review_id"] is not None else None,
            review_version=(
                int(row["review_version"])
                if row["review_version"] is not None
                else None
            ),
            evidence_basis=(
                str(row["evidence_basis"]) if row["evidence_basis"] else None
            ),
            evidence_reference=(
                str(row["evidence_reference"]) if row["evidence_reference"] else None
            ),
            review_note=str(row["review_note"]) if row["review_note"] else None,
            reviewer_name=(
                str(row["reviewer_name"]) if row["reviewer_name"] else None
            ),
            reviewed_at=row["reviewed_at"],
            review_status=str(row["review_status"]),
        )

    @staticmethod
    def _review_error(error: psycopg.Error) -> EclOutcomeReviewError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lowered = message.lower()
        if "was not found" in lowered:
            return EclOutcomeReviewNotFound(message)
        if "source review must be completed" in lowered:
            return EclOutcomeReviewSourceBlocked(message)
        return EclOutcomeReviewError(message or "Historical ECL outcome review failed.")
