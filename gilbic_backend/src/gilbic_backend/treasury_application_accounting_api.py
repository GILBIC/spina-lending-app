"""Explicit private review of supported Treasury applications; no automatic GL."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from .office_review_evidence_route import PrivateOfficeRoute
from .treasury_api import call
from .treasury_application_accounting_repository import (
    PostgresTreasuryApplicationAccountingRepository,
)
from .treasury_receipt_accounting_api import receipt_accounting_actor


class ApplicationPrepareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_id: UUID


class ApplicationPostRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmation_token: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirm: StrictBool = False


class PayoffReviewRequest(ApplicationPrepareRequest):
    treatment: Literal["full_contractual_payoff_no_rebate"]
    contract_evidence_reference: str = Field(min_length=3, max_length=1000)
    review_rationale: str = Field(min_length=20, max_length=2000)
    confirm: StrictBool = False


class ClosedTermReviewRequest(ApplicationPrepareRequest):
    treatment: Literal["original_eir_through_maturity_no_extension"]
    contract_evidence_reference: str = Field(min_length=3, max_length=1000)
    review_rationale: str = Field(min_length=20, max_length=2000)
    confirm: StrictBool = False


def treasury_application_accounting_repository_dependency():
    return PostgresTreasuryApplicationAccountingRepository()


def create_treasury_application_accounting_router():
    router = APIRouter(
        tags=["management financial accounting"], route_class=PrivateOfficeRoute
    )
    actor_dependency = Depends(receipt_accounting_actor)
    repository_dependency = Depends(
        treasury_application_accounting_repository_dependency
    )

    def review(
        application_id: UUID, actor=actor_dependency, repository=repository_dependency
    ):
        return call(lambda: repository.review(actor, application_id=application_id))

    def prepare(
        application_id: UUID,
        body: ApplicationPrepareRequest,
        actor=actor_dependency,
        repository=repository_dependency,
    ):
        return call(
            lambda: repository.prepare(
                actor, application_id=application_id, **body.model_dump()
            )
        )

    def payoff_candidate(
        application_id: UUID, actor=actor_dependency, repository=repository_dependency
    ):
        return call(
            lambda: repository.payoff_candidate(actor, application_id=application_id)
        )

    def review_payoff(
        application_id: UUID,
        body: PayoffReviewRequest,
        actor=actor_dependency,
        repository=repository_dependency,
    ):
        if not body.confirm:
            raise HTTPException(
                409,
                detail={
                    "code": "payoff_review_confirmation_required",
                    "message": "Confirm the exact contractual payoff treatment and settlement difference.",
                },
            )
        return call(
            lambda: repository.review_payoff(
                actor,
                application_id=application_id,
                **body.model_dump(exclude={"confirm"}),
            )
        )

    def closed_term_candidate(
        application_id: UUID, actor=actor_dependency, repository=repository_dependency
    ):
        return call(
            lambda: repository.closed_term_candidate(
                actor, application_id=application_id
            )
        )

    def review_closed_term(
        application_id: UUID,
        body: ClosedTermReviewRequest,
        actor=actor_dependency,
        repository=repository_dependency,
    ):
        if not body.confirm:
            raise HTTPException(
                409,
                detail={
                    "code": "closed_term_review_confirmation_required",
                    "message": "Confirm original interest ends at the signed contractual maturity without extension.",
                },
            )
        return call(
            lambda: repository.review_closed_term(
                actor,
                application_id=application_id,
                **body.model_dump(exclude={"confirm"}),
            )
        )

    def read_preparation(
        preparation_id: UUID, actor=actor_dependency, repository=repository_dependency
    ):
        return call(
            lambda: repository.read_preparation(actor, preparation_id=preparation_id)
        )

    def post(
        preparation_id: UUID,
        body: ApplicationPostRequest,
        actor=actor_dependency,
        repository=repository_dependency,
    ):
        if not body.confirm:
            raise HTTPException(
                409,
                detail={
                    "code": "application_accounting_confirmation_required",
                    "message": "Explicit confirmation of the retained application accounting review is required.",
                },
            )
        return call(
            lambda: repository.post(
                actor,
                preparation_id=preparation_id,
                **body.model_dump(exclude={"confirm"}),
            )
        )

    for prefix in (
        "/api/v1/management/financial-accounting/treasury",
        "/api/mobile/v1/management/financial-accounting/treasury",
    ):
        for path, endpoint, method in (
            ("/applications/{application_id}/review", review, "GET"),
            ("/applications/{application_id}/prepare", prepare, "POST"),
            ("/applications/{application_id}/payoff-review", payoff_candidate, "GET"),
            ("/applications/{application_id}/payoff-review", review_payoff, "POST"),
            (
                "/applications/{application_id}/closed-term-review",
                closed_term_candidate,
                "GET",
            ),
            (
                "/applications/{application_id}/closed-term-review",
                review_closed_term,
                "POST",
            ),
            ("/application-preparations/{preparation_id}", read_preparation, "GET"),
            ("/application-preparations/{preparation_id}/post", post, "POST"),
        ):
            router.add_api_route(
                prefix + path,
                endpoint,
                methods=[method],
                include_in_schema="/mobile/" not in prefix,
            )
    return router
