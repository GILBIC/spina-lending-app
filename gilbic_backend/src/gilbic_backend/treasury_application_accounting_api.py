"""Explicit private review of supported Treasury applications; no automatic GL."""

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
