from __future__ import annotations

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .ecl_outcome_review_repository import (
    EclOutcomeReviewEpisode,
    EclOutcomeReviewError,
    EclOutcomeReviewNotFound,
    EclOutcomeReviewSourceBlocked,
    EclOutcomeReviewSummary,
    PostgresEclOutcomeReviewRepository,
)
from .request_auth import authenticated_device_context


class StrictEclOutcomeReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReviewHistoricalOutcomeRequest(StrictEclOutcomeReviewRequest):
    default_label: bool
    evidence_basis: Literal[
        "source_document",
        "collection_history",
        "renewal_settlement",
        "management_review",
    ]
    evidence_reference: str = Field(min_length=1, max_length=300)
    review_note: str = Field(min_length=1, max_length=1000)

    @field_validator("evidence_reference", "review_note")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Review evidence text cannot be blank.")
        return normalized


def ecl_outcome_review_repository_dependency() -> PostgresEclOutcomeReviewRepository:
    return PostgresEclOutcomeReviewRepository()


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _optional_decimal(value: Decimal | None) -> str | None:
    return _decimal(value) if value is not None else None


def _summary_payload(summary: EclOutcomeReviewSummary) -> dict[str, object]:
    return {
        "episode_count": summary.episode_count,
        "structurally_usable_count": summary.structurally_usable_count,
        "source_review_required_count": summary.source_review_required_count,
        "pending_outcome_review_count": summary.pending_outcome_review_count,
        "reviewed_outcome_count": summary.reviewed_outcome_count,
        "reviewed_default_count": summary.reviewed_default_count,
        "reviewed_non_default_count": summary.reviewed_non_default_count,
        "review_status": summary.review_status,
        "ecl_included": summary.ecl_included,
        "ecl_amount": _optional_decimal(summary.ecl_amount),
        "ready_to_post": summary.ready_to_post,
    }


def _episode_payload(episode: EclOutcomeReviewEpisode) -> dict[str, object]:
    return {
        "historical_episode_id": episode.historical_episode_id,
        "episode_key": episode.episode_key,
        "borrower_key": episode.borrower_key,
        "episode_sequence": episode.episode_sequence,
        "loan_type": episode.loan_type,
        "source_event": episode.source_event,
        "release_date": episode.release_date.isoformat() if episode.release_date else None,
        "due_date": episode.due_date.isoformat() if episode.due_date else None,
        "principal": _decimal(episode.principal),
        "contractual_total": _optional_decimal(episode.contractual_total),
        "interest_rate": _optional_decimal(episode.interest_rate),
        "outcome_evidence": episode.outcome_evidence,
        "outcome_date": episode.outcome_date.isoformat() if episode.outcome_date else None,
        "renewal_rollover_amount": _optional_decimal(episode.renewal_rollover_amount),
        "cash_collected": _decimal(episode.cash_collected),
        "positive_payment_count": episode.positive_payment_count,
        "zero_payment_observation_count": episode.zero_payment_observation_count,
        "observed_collection_days": episode.observed_collection_days,
        "source_quality_status": episode.source_quality_status,
        "source_quality_note": episode.source_quality_note,
        "explicit_default_label": episode.explicit_default_label,
        "review_id": episode.review_id,
        "review_version": episode.review_version,
        "evidence_basis": episode.evidence_basis,
        "evidence_reference": episode.evidence_reference,
        "review_note": episode.review_note,
        "reviewer_name": episode.reviewer_name,
        "reviewed_at": episode.reviewed_at.isoformat() if episode.reviewed_at else None,
        "review_status": episode.review_status,
    }


def _review_exception(error: EclOutcomeReviewError) -> HTTPException:
    if isinstance(error, EclOutcomeReviewNotFound):
        status_code = 404
    elif isinstance(error, EclOutcomeReviewSourceBlocked):
        status_code = 409
    else:
        status_code = 500
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code, "message": str(error)},
    )


def create_ecl_outcome_review_router() -> APIRouter:
    router = APIRouter(tags=["management financial accounting"])

    @router.get("/api/v1/management/financial-accounting/ecl-outcome-review")
    @router.get(
        "/api/mobile/v1/management/financial-accounting/ecl-outcome-review",
        include_in_schema=False,
    )
    def list_ecl_outcome_review(
        review_status: Literal["pending", "reviewed", "source_review", "all"] = Query(
            default="pending"
        ),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        reviews: PostgresEclOutcomeReviewRepository = Depends(
            ecl_outcome_review_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        if "management" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "management_role_required",
                    "message": "Management access is required for ECL outcome review.",
                },
            )
        summary, episodes = reviews.load_review_queue(
            review_status=review_status,
            limit=limit,
            offset=offset,
        )
        return {
            "success": True,
            "data": {
                "summary": _summary_payload(summary),
                "episodes": [_episode_payload(item) for item in episodes],
                "filter": review_status,
                "limit": limit,
                "offset": offset,
                "review_permission": "accounting.ecl.review" in actor.permissions,
                "notice": (
                    "Historical outcomes require explicit evidence-backed review. "
                    "Renewal, archive, deletion, cash totals and arrears are not "
                    "automatic default or non-default labels. ECL remains unquantified."
                ),
            },
        }

    @router.post(
        "/api/v1/management/financial-accounting/ecl-outcome-review/{historical_episode_id}"
    )
    @router.post(
        "/api/mobile/v1/management/financial-accounting/ecl-outcome-review/{historical_episode_id}",
        include_in_schema=False,
    )
    def review_historical_outcome(
        historical_episode_id: int,
        body: ReviewHistoricalOutcomeRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        reviews: PostgresEclOutcomeReviewRepository = Depends(
            ecl_outcome_review_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.ecl.review",
            permission_error="Historical ECL outcome review permission is required.",
        )
        try:
            reviewed = reviews.review_outcome(
                historical_episode_id=historical_episode_id,
                default_label=body.default_label,
                evidence_basis=body.evidence_basis,
                evidence_reference=body.evidence_reference,
                review_note=body.review_note,
                actor_user_id=actor.user_id,
            )
        except EclOutcomeReviewError as error:
            raise _review_exception(error) from error

        return {
            "success": True,
            "data": _episode_payload(reviewed),
            "notice": (
                "Outcome review recorded with immutable evidence history. "
                "No loss, recovery, PD, LGD or ECL amount was calculated or posted."
            ),
        }

    return router
