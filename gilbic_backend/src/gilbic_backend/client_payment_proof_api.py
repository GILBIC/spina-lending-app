from __future__ import annotations

from base64 import b64decode
from binascii import Error as Base64Error
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from starlette.concurrency import run_in_threadpool

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .client_payment_proof_repository import (
    REVIEW_PERMISSION,
    PaymentProofAccessDenied,
    PaymentProofConflict,
    PaymentProofInvalid,
    PaymentProofNotFound,
    PostgresClientPaymentProofRepository,
)
from .office_review_evidence_route import PrivateOfficeRoute
from .office_review_evidence_storage import (
    EVIDENCE_MEDIA_TYPES,
    MAX_EVIDENCE_BYTES,
    EvidenceFileError,
    validate_evidence_content,
)
from .request_auth import authenticated_device_context


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    expected_version: StrictInt = Field(ge=1)
    expected_review_id: UUID | None
    decision: Literal["reviewed", "correction_required", "rejected"]
    reason: str = Field(default="", max_length=1000)


def client_payment_proof_repository_dependency():
    return PostgresClientPaymentProofRepository()


def _actor_dependency(management):
    def actor(
        authorization: str | None = Header(None, alias="Authorization"),
        x_device_id: str | None = Header(None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
    ):
        context = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission=REVIEW_PERMISSION if management else None,
            permission_error="Management payment-proof review permission is required.",
        )
        if ("management" if management else "client") not in context.roles:
            raise HTTPException(403, "This account cannot access payment proofs.")
        if context.registered_device_id is None:
            raise HTTPException(403, "An active registered device is required.")
        if management and REVIEW_PERMISSION not in context.permissions:
            raise HTTPException(
                403, "Management payment-proof review permission is required."
            )
        return context

    return actor


def _call(method, **arguments):
    try:
        return method(**arguments)
    except PaymentProofAccessDenied as error:
        raise HTTPException(
            403, "An active authorized account and device are required."
        ) from error
    except PaymentProofNotFound as error:
        raise HTTPException(404, "Payment proof or loan was not found.") from error
    except PaymentProofConflict as error:
        raise HTTPException(409, str(error)) from error
    except PaymentProofInvalid as error:
        raise HTTPException(422, str(error)) from error
    except EvidenceFileError as error:
        raise HTTPException(
            503, "Private payment-proof storage is unavailable."
        ) from error


def _identity(actor):
    return {
        "actor_user_id": actor.user_id,
        "registered_device_id": actor.registered_device_id,
    }


def _upload_note(encoded: str) -> str:
    try:
        if len(encoded) > 5336:
            raise ValueError("Encoded note is too long")
        note = b64decode(encoded, validate=True).decode("utf-8")
        if len(note) > 1000 or "\x00" in note:
            raise ValueError("Invalid note text")
        return note
    except (Base64Error, UnicodeError, ValueError) as error:
        raise HTTPException(
            422,
            "Payment-proof note must be valid UTF-8 text of at most 1000 characters.",
        ) from error


async def _upload_bytes(request):
    media_type = (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    )
    if media_type not in EVIDENCE_MEDIA_TYPES:
        raise HTTPException(415, "Upload a PDF, PNG or JPEG file.")
    length = request.headers.get("content-length")
    if length is not None and (
        not length.isdecimal() or int(length) > MAX_EVIDENCE_BYTES
    ):
        raise HTTPException(413, "Payment proof must contain at most 10 MiB.")
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > MAX_EVIDENCE_BYTES:
            raise HTTPException(413, "Payment proof must contain at most 10 MiB.")
        content.extend(chunk)
    data = bytes(content)
    try:
        validate_evidence_content(data, media_type)
    except EvidenceFileError as error:
        raise HTTPException(
            415, "Upload a complete PDF, PNG or JPEG file up to 10 MiB."
        ) from error
    return data, media_type


def create_client_payment_proof_router():
    router = APIRouter(tags=["client payment proofs"], route_class=PrivateOfficeRoute)

    def add_routes(prefix, management, *, mobile=False):
        actor_dependency = _actor_dependency(management)

        @router.get(prefix, include_in_schema=not mobile)
        def list_proofs(
            limit: int = Query(50, ge=1, le=100),
            offset: int = Query(0, ge=0, le=100000),
            actor=Depends(actor_dependency),
            repository=Depends(client_payment_proof_repository_dependency),
        ):
            return {
                "success": True,
                "data": _call(
                    repository.list_proofs,
                    **_identity(actor),
                    management=management,
                    limit=limit,
                    offset=offset,
                ),
            }

        @router.get(prefix + "/{proof_id}", include_in_schema=not mobile)
        def get_proof(
            proof_id: UUID,
            actor=Depends(actor_dependency),
            repository=Depends(client_payment_proof_repository_dependency),
        ):
            return {
                "success": True,
                "data": _call(
                    repository.get,
                    **_identity(actor),
                    proof_id=proof_id,
                    management=management,
                ),
            }

        @router.get(
            prefix + "/{proof_id}/versions/{version_number}/content",
            include_in_schema=not mobile,
        )
        def content(
            proof_id: UUID,
            version_number: int,
            actor=Depends(actor_dependency),
            repository=Depends(client_payment_proof_repository_dependency),
        ):
            if version_number < 1:
                raise HTTPException(404, "Payment proof was not found.")
            metadata, data = _call(
                repository.content,
                **_identity(actor),
                proof_id=proof_id,
                version_number=version_number,
                management=management,
            )
            extension = {
                "application/pdf": "pdf",
                "image/png": "png",
                "image/jpeg": "jpg",
            }[metadata["media_type"]]
            return Response(
                data,
                media_type=metadata["media_type"],
                headers={
                    "Content-Disposition": f'attachment; filename="payment-proof-{proof_id}-v{version_number}.{extension}"',
                    "X-Content-Type-Options": "nosniff",
                    "Content-Security-Policy": "sandbox",
                },
            )

        if management:

            @router.post(
                prefix + "/{proof_id}/reviews",
                status_code=201,
                include_in_schema=not mobile,
            )
            def review(
                proof_id: UUID,
                body: ReviewRequest,
                actor=Depends(actor_dependency),
                repository=Depends(client_payment_proof_repository_dependency),
            ):
                return {
                    "success": True,
                    "data": _call(
                        repository.review,
                        **_identity(actor),
                        proof_id=proof_id,
                        **body.model_dump(),
                    ),
                }
        else:

            @router.post(prefix, status_code=201, include_in_schema=not mobile)
            async def upload(
                request: Request,
                loan_id: UUID,
                request_id: UUID,
                x_proof_note: str = Header("", alias="X-Proof-Note"),
                actor=Depends(actor_dependency),
                repository=Depends(client_payment_proof_repository_dependency),
            ):
                note = _upload_note(x_proof_note)
                data, media_type = await _upload_bytes(request)
                record = await run_in_threadpool(
                    _call,
                    repository.upload,
                    **_identity(actor),
                    loan_id=loan_id,
                    request_id=request_id,
                    note=note,
                    content=data,
                    media_type=media_type,
                )
                return {"success": True, "data": record}

            @router.post(
                prefix + "/{proof_id}/versions",
                status_code=201,
                include_in_schema=not mobile,
            )
            async def reupload(
                proof_id: UUID,
                request: Request,
                request_id: UUID,
                expected_version: int = Query(ge=1),
                x_proof_note: str = Header("", alias="X-Proof-Note"),
                actor=Depends(actor_dependency),
                repository=Depends(client_payment_proof_repository_dependency),
            ):
                note = _upload_note(x_proof_note)
                data, media_type = await _upload_bytes(request)
                record = await run_in_threadpool(
                    _call,
                    repository.upload,
                    **_identity(actor),
                    proof_id=proof_id,
                    expected_version=expected_version,
                    request_id=request_id,
                    note=note,
                    content=data,
                    media_type=media_type,
                )
                return {"success": True, "data": record}

    for prefix in ("/api/v1", "/api/mobile/v1"):
        for role in ("client", "management"):
            add_routes(
                prefix + f"/{role}/payment-proofs",
                role == "management",
                mobile="/mobile/" in prefix,
            )
    return router
