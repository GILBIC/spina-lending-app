"""Private Management review and explicit confirmation of Collector accounting."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .collector_liability_accounting_repository import (
    PostgresCollectorLiabilityAccountingRepository,
)
from .office_review_evidence_route import PrivateOfficeRoute
from .request_auth import authenticated_device_context
from .treasury_api import call

SourceKind = Literal[
    "settlement",
    "recognition",
    "return_debit",
    "return_confirmation",
    "return_reversal",
]


class CollectorPrepareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_id: UUID


class CollectorPostRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmation_token: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirm: StrictBool = False


def collector_liability_accounting_repository_dependency():
    return PostgresCollectorLiabilityAccountingRepository()


def collector_accounting_actor(
    auth: Annotated[SupabaseAuthClient, Depends(auth_client_dependency)],
    accounts: Annotated[
        PostgresAccountRepository, Depends(account_repository_dependency)
    ],
    authorization: str | None = Header(None, alias="Authorization"),
    x_device_id: str | None = Header(None, alias="X-Device-Id"),
):
    actor = authenticated_device_context(
        authorization=authorization,
        device_identifier=x_device_id,
        auth=auth,
        accounts=accounts,
        permission="accounting.journal.manage",
        permission_error="Current accounting journal permission is required.",
    )
    if actor.status != "active" or "management" not in actor.roles:
        raise HTTPException(
            403, detail="Active Management access is required for Collector accounting."
        )
    return actor


def collector_schedule_actor(
    auth: Annotated[SupabaseAuthClient, Depends(auth_client_dependency)],
    accounts: Annotated[
        PostgresAccountRepository, Depends(account_repository_dependency)
    ],
    authorization: str | None = Header(None, alias="Authorization"),
    x_device_id: str | None = Header(None, alias="X-Device-Id"),
):
    actor = authenticated_device_context(
        authorization=authorization,
        device_identifier=x_device_id,
        auth=auth,
        accounts=accounts,
        permission="accounting.view",
        permission_error="Current accounting view permission is required.",
    )
    if actor.status != "active" or "management" not in actor.roles:
        raise HTTPException(
            403, detail="Current Management accounting access is required."
        )
    return actor


def create_collector_liability_accounting_router():
    router = APIRouter(
        tags=["management financial accounting"], route_class=PrivateOfficeRoute
    )
    actor_dependency = Depends(collector_accounting_actor)
    schedule_actor_dependency = Depends(collector_schedule_actor)
    repository_dependency = Depends(
        collector_liability_accounting_repository_dependency
    )

    def control_schedule(
        as_of: date | None = None,
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
        actor=schedule_actor_dependency,
        repository=repository_dependency,
    ):
        return call(
            lambda: repository.control_schedule(
                actor, as_of=as_of, limit=limit, offset=offset
            )
        )

    def review(
        source_kind: SourceKind,
        source_id: UUID,
        actor=actor_dependency,
        repository=repository_dependency,
    ):
        return call(
            lambda: repository.review(
                actor, source_kind=source_kind, source_id=source_id
            )
        )

    def prepare(
        source_kind: SourceKind,
        source_id: UUID,
        body: CollectorPrepareRequest,
        actor=actor_dependency,
        repository=repository_dependency,
    ):
        return call(
            lambda: repository.prepare(
                actor, source_kind=source_kind, source_id=source_id, **body.model_dump()
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
        body: CollectorPostRequest,
        actor=actor_dependency,
        repository=repository_dependency,
    ):
        if not body.confirm:
            raise HTTPException(
                409,
                detail={
                    "code": "collector_accounting_confirmation_required",
                    "message": "Explicit confirmation of this exact retained accounting review is required.",
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
        "/api/v1/management/financial-accounting/collector",
        "/api/mobile/v1/management/financial-accounting/collector",
    ):
        for path, endpoint, method in (
            ("/control-schedule", control_schedule, "GET"),
            ("/{source_kind}/{source_id}/review", review, "GET"),
            ("/{source_kind}/{source_id}/prepare", prepare, "POST"),
            ("/preparations/{preparation_id}", read_preparation, "GET"),
            ("/preparations/{preparation_id}/post", post, "POST"),
        ):
            router.add_api_route(
                prefix + path,
                endpoint,
                methods=[method],
                include_in_schema="/mobile/" not in prefix,
            )
    return router
