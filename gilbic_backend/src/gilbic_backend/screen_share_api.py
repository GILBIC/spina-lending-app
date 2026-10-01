"""Authenticated app-only device readiness and ephemeral PNG transport; no remote control."""

from collections.abc import Callable, Iterator
from typing import Annotated, ParamSpec, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from .account_repository import AccountContext, PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .office_review_evidence_route import PrivateOfficeRoute
from .request_auth import authenticated_device_context, bearer_token
from .screen_share_frames import MAX_FRAME_BYTES, ScreenShareError
from .screen_share_repository import PostgresScreenShareRepository


class TargetBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    holder_user_id: UUID
    holder_device_id: UUID


class GenerationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    generation: int = Field(strict=True, ge=1, le=9223372036854775807)


def screen_share_auth(
    authorization: str | None = Header(default=None),
) -> Iterator[SupabaseAuthClient]:
    bearer_token(authorization)
    yield from auth_client_dependency()


def screen_share_actor(
    auth: Annotated[SupabaseAuthClient, Depends(screen_share_auth)],
    accounts: Annotated[
        PostgresAccountRepository, Depends(account_repository_dependency)
    ],
    authorization: str | None = Header(default=None),
    device: str | None = Header(default=None, alias="X-Device-Id"),
) -> AccountContext:
    return authenticated_device_context(
        authorization=authorization,
        device_identifier=device,
        auth=auth,
        accounts=accounts,
    )


def screen_share_repository(request: Request) -> PostgresScreenShareRepository:
    return request.app.state.screen_shares


P = ParamSpec("P")
T = TypeVar("T")
Actor = Annotated[AccountContext, Depends(screen_share_actor)]
Repository = Annotated[PostgresScreenShareRepository, Depends(screen_share_repository)]


def invoke(operation: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    try:
        return operation(*args, **kwargs)
    except ScreenShareError as error:
        raise HTTPException(error.status_code, error.detail) from None


def create_screen_share_router() -> APIRouter:
    router = APIRouter(
        prefix="/api/v1/screen-shares",
        tags=["screen sharing"],
        route_class=PrivateOfficeRoute,
    )

    @router.get("/targets")
    def targets(actor: Actor, repo: Repository):
        return invoke(repo.targets, actor)

    @router.post("", status_code=201)
    def request_share(
        body: TargetBody,
        actor: Actor,
        repo: Repository,
    ):
        return invoke(repo.request, actor, body.holder_user_id, body.holder_device_id)

    @router.get("/pending")
    def pending(actor: Actor, repo: Repository):
        return invoke(repo.pending, actor)

    @router.get("/{session_id}")
    def status(
        session_id: UUID,
        actor: Actor,
        repo: Repository,
    ):
        return invoke(repo.status, actor, session_id)

    @router.post("/{session_id}/ready")
    def ready(
        session_id: UUID,
        body: GenerationBody,
        actor: Actor,
        repo: Repository,
    ):
        return invoke(repo.ready, actor, session_id, body.generation)

    @router.post("/{session_id}/decline")
    def decline(
        session_id: UUID,
        body: GenerationBody,
        actor: Actor,
        repo: Repository,
    ):
        return invoke(repo.decline, actor, session_id, body.generation)

    @router.post("/{session_id}/stop")
    def stop(
        session_id: UUID,
        body: GenerationBody,
        actor: Actor,
        repo: Repository,
    ):
        return invoke(repo.stop, actor, session_id, body.generation)

    @router.put("/{session_id}/frame", status_code=204)
    async def upload(
        session_id: UUID,
        request: Request,
        actor: Actor,
        repo: Repository,
        generation: int = Header(
            alias="X-Screen-Share-Generation", ge=1, le=9223372036854775807
        ),
        sequence: int = Header(
            alias="X-Screen-Share-Sequence", ge=1, le=9223372036854775807
        ),
    ):
        if request.headers.get("content-type", "").lower() != "image/png":
            raise HTTPException(422, "Only PNG screen images are supported.")
        await run_in_threadpool(
            invoke, repo.check_upload, actor, session_id, generation, sequence
        )
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > MAX_FRAME_BYTES:
                raise HTTPException(413, "Screen image is too large.")
            data.extend(chunk)
        await run_in_threadpool(
            invoke, repo.upload, actor, session_id, generation, sequence, bytes(data)
        )
        return Response(status_code=204)

    @router.get("/{session_id}/frame")
    def frame(
        session_id: UUID,
        actor: Actor,
        repo: Repository,
    ):
        value = invoke(repo.frame, actor, session_id)
        if value is None:
            return Response(status_code=204)
        return Response(
            value.data,
            media_type="image/png",
            headers={
                "X-Screen-Share-Generation": str(value.generation),
                "X-Screen-Share-Sequence": str(value.sequence),
            },
        )

    return router
