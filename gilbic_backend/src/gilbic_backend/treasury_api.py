"""One authenticated backend contract shared by Web, installed Windows and native."""

import base64
import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from psycopg import OperationalError, errors
from pydantic import ValidationError
from spina_mobile_collections.service import CollectionConflict, CollectionRejected
from starlette.concurrency import run_in_threadpool

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .client_payment_proof_api import _upload_bytes
from .collection_void_repository import CollectionVoidError
from .office_review_evidence_route import PrivateOfficeRoute
from .office_review_evidence_storage import EvidenceFileError
from .request_auth import authenticated_device_context
from .treasury_authorization import (
    TreasuryConflict,
    TreasuryDenied,
    TreasuryUnavailable,
)
from .treasury_claims import submit_claim, upload_evidence
from .treasury_models import (
    AllocationPreview,
    ClaimMetadata,
    SettlementPreview,
    TreasuryCommand,
)
from .treasury_repository import TreasuryService


def treasury_repository_dependency():
    return TreasuryService()


_AUTH_DEPENDENCY = Depends(auth_client_dependency)
_ACCOUNT_DEPENDENCY = Depends(account_repository_dependency)


def treasury_actor(
    authorization: str | None = Header(None, alias="Authorization"),
    x_device_id: str | None = Header(None, alias="X-Device-Id"),
    auth: SupabaseAuthClient = _AUTH_DEPENDENCY,
    accounts: PostgresAccountRepository = _ACCOUNT_DEPENDENCY,
):
    return authenticated_device_context(
        authorization=authorization,
        device_identifier=x_device_id,
        auth=auth,
        accounts=accounts,
    )


_ACTOR_DEPENDENCY = Depends(treasury_actor)
_REPOSITORY_DEPENDENCY = Depends(treasury_repository_dependency)


def call(operation):
    try:
        return {"success": True, "data": operation()}
    except TreasuryDenied as error:
        raise HTTPException(
            403, detail={"code": error.code, "message": str(error)}
        ) from error
    except TreasuryConflict as error:
        raise HTTPException(
            409, detail={"code": error.code, "message": str(error)}
        ) from error
    except (CollectionRejected, CollectionConflict) as error:
        raise HTTPException(
            409, detail={"code": "treasury_allocation_blocked", "message": str(error)}
        ) from error
    except CollectionVoidError as error:
        raise HTTPException(
            409, detail={"code": error.code, "message": str(error)}
        ) from error
    except TreasuryUnavailable as error:
        raise HTTPException(
            503, detail={"code": error.code, "message": str(error)}
        ) from error
    except EvidenceFileError as error:
        raise HTTPException(
            503,
            detail={
                "code": "treasury_evidence_unavailable",
                "message": "Private evidence is unavailable; no new action was confirmed.",
            },
        ) from error
    except (
        errors.UniqueViolation,
        errors.CheckViolation,
        errors.ForeignKeyViolation,
        errors.RaiseException,
    ) as error:
        raise HTTPException(
            409,
            detail={
                "code": "treasury_conflict",
                "message": "The record conflicts; refresh and review.",
            },
        ) from error
    except (OperationalError, errors.UndefinedTable, errors.InvalidSchemaName) as error:
        raise HTTPException(
            503,
            detail={
                "code": "treasury_unavailable",
                "message": "Treasury setup is unavailable; no action was confirmed.",
            },
        ) from error


def metadata_header(value):
    try:
        if len(value) > 12000:
            raise ValueError("Header too long")
        return ClaimMetadata.model_validate(
            json.loads(base64.b64decode(value, validate=True).decode("utf-8"))
        )
    except (ValueError, UnicodeError, ValidationError) as error:
        raise HTTPException(
            422,
            "X-Treasury-Metadata must encode the strict UTF-8 ClaimMetadata JSON contract.",
        ) from error


def binary_result(result):
    row, content = result["data"]
    return Response(
        content,
        media_type=row["media_type"],
        headers={
            "Content-Disposition": 'attachment; filename="treasury-private-evidence.'
            + {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg"}[
                row["media_type"]
            ]
            + '"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
            "Cache-Control": "no-store",
        },
    )


def create_treasury_router():
    router = APIRouter(tags=["treasury"], route_class=PrivateOfficeRoute)

    def routes(prefix, mobile=False):
        @router.get(
            prefix
            + "/collector-surplus/remittances/{remittance_id}/receiving-contract",
            include_in_schema=not mobile,
        )
        def surplus_receiving_contract(
            remittance_id: UUID,
            actor=_ACTOR_DEPENDENCY,
            repository=_REPOSITORY_DEPENDENCY,
        ):
            from .collector_settlement import receiving_contract

            def operation():
                with repository.connect() as conn, conn.transaction():
                    return receiving_contract(repository, conn, actor, remittance_id)

            return call(operation)

        @router.get(
            prefix + "/collector-surplus/workspace", include_in_schema=not mobile
        )
        def surplus_workspace(
            kind: Literal[
                "credits",
                "cases",
                "actions",
                "requests",
                "counts",
                "exceptions",
                "remittances",
                "openings",
            ] = "credits",
            account_id: UUID | None = None,
            collector_user_id: UUID | None = None,
            limit: int = Query(50, ge=1, le=100),
            offset: int = Query(0, ge=0, le=100000),
            mode: Literal["own", "staff"] | None = None,
            actor=_ACTOR_DEPENDENCY,
            repository=_REPOSITORY_DEPENDENCY,
        ):
            from .collector_surplus_reads import workspace

            def operation():
                with repository.connect() as conn, conn.transaction():
                    return workspace(
                        repository,
                        conn,
                        actor,
                        kind,
                        account_id,
                        collector_user_id,
                        limit,
                        offset,
                        mode=mode,
                    )

            return call(operation)

        @router.get(prefix + "/collector-surplus/export", include_in_schema=not mobile)
        def surplus_export(
            kind: Literal[
                "credits",
                "cases",
                "actions",
                "requests",
                "counts",
                "exceptions",
                "remittances",
                "openings",
            ] = "credits",
            account_id: UUID | None = None,
            collector_user_id: UUID | None = None,
            mode: Literal["own", "staff"] | None = None,
            actor=_ACTOR_DEPENDENCY,
            repository=_REPOSITORY_DEPENDENCY,
        ):
            from .collector_surplus_reads import workspace

            def operation():
                with repository.connect() as conn, conn.transaction():
                    return workspace(
                        repository,
                        conn,
                        actor,
                        kind,
                        account_id,
                        collector_user_id,
                        export=True,
                        mode=mode,
                    )

            result = call(operation)
            return Response(
                json.dumps(result),
                media_type="application/json",
                headers={
                    "Content-Disposition": 'attachment; filename="collector-surplus-private.json"',
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                },
            )

        @router.post(
            prefix + "/collector-surplus/remittances/{remittance_id}/preview",
            include_in_schema=not mobile,
        )
        def surplus_preview(
            remittance_id: UUID,
            command: SettlementPreview,
            actor=_ACTOR_DEPENDENCY,
            repository=_REPOSITORY_DEPENDENCY,
        ):
            from .collector_settlement import preview

            def operation():
                with repository.connect() as conn, conn.transaction():
                    return preview(repository, conn, actor, remittance_id, command)

            return call(operation)

        @router.get(
            prefix + "/collector-surplus/{kind}/{target_id}",
            include_in_schema=not mobile,
        )
        def surplus_detail(
            kind: Literal[
                "credits", "cases", "actions", "counts", "exceptions", "requests"
            ],
            target_id: UUID,
            mode: Literal["own", "staff"] | None = None,
            actor=_ACTOR_DEPENDENCY,
            repository=_REPOSITORY_DEPENDENCY,
        ):
            from .collector_surplus_reads import detail

            def operation():
                with repository.connect() as conn, conn.transaction():
                    return detail(repository, conn, actor, kind, target_id, mode=mode)

            return call(operation)

        @router.get(prefix + "/workspace", include_in_schema=not mobile)
        def workspace(actor=_ACTOR_DEPENDENCY, repository=_REPOSITORY_DEPENDENCY):
            return call(lambda: repository.workspace(actor))

        @router.get(prefix + "/instructions", include_in_schema=not mobile)
        def instructions(actor=_ACTOR_DEPENDENCY, repository=_REPOSITORY_DEPENDENCY):
            return call(lambda: repository.instructions(actor))

        @router.get(prefix + "/requests/{request_id}", include_in_schema=not mobile)
        def request_result(
            request_id: UUID, actor=_ACTOR_DEPENDENCY, repository=_REPOSITORY_DEPENDENCY
        ):
            return call(lambda: repository.request_result(actor, request_id))

        @router.post(prefix + "/actions", include_in_schema=not mobile)
        def actions(
            command: TreasuryCommand,
            actor=_ACTOR_DEPENDENCY,
            repository=_REPOSITORY_DEPENDENCY,
        ):
            return call(lambda: repository.execute(actor, command))

        @router.get(
            prefix + "/accounts/{account_id}/{kind}", include_in_schema=not mobile
        )
        def records(
            account_id: UUID,
            kind: Literal[
                "events", "receipts", "reconciliations", "claims", "openings"
            ],
            limit: int = Query(50, ge=1, le=100),
            offset: int = Query(0, ge=0, le=100000),
            actor=_ACTOR_DEPENDENCY,
            repository=_REPOSITORY_DEPENDENCY,
        ):
            return call(
                lambda: repository.list_records(actor, account_id, kind, limit, offset)
            )

        @router.get(prefix + "/claims", include_in_schema=not mobile)
        def claims(
            account_id: UUID | None = None,
            client_id: UUID | None = None,
            limit: int = Query(50, ge=1, le=100),
            offset: int = Query(0, ge=0, le=100000),
            actor=_ACTOR_DEPENDENCY,
            repository=_REPOSITORY_DEPENDENCY,
        ):
            return call(
                lambda: repository.list_claims(
                    actor, account_id, client_id, limit, offset
                )
            )

        @router.get(prefix + "/claims/{claim_id}", include_in_schema=not mobile)
        def claim(
            claim_id: UUID, actor=_ACTOR_DEPENDENCY, repository=_REPOSITORY_DEPENDENCY
        ):
            return call(lambda: repository.get_claim(actor, claim_id))

        @router.get(
            prefix + "/claims/{claim_id}/versions/{version}/content",
            include_in_schema=not mobile,
        )
        def claim_content(
            claim_id: UUID,
            version: int,
            actor=_ACTOR_DEPENDENCY,
            repository=_REPOSITORY_DEPENDENCY,
        ):
            return binary_result(
                call(lambda: repository.claim_content(actor, claim_id, version))
            )

        @router.post(prefix + "/claims", status_code=201, include_in_schema=not mobile)
        async def upload_claim(
            request: Request,
            x_treasury_metadata: str = Header(alias="X-Treasury-Metadata"),
            actor=_ACTOR_DEPENDENCY,
            repository=_REPOSITORY_DEPENDENCY,
        ):
            metadata = metadata_header(x_treasury_metadata)
            data, media_type = await _upload_bytes(request)
            return await run_in_threadpool(
                call,
                lambda: submit_claim(repository, actor, metadata, data, media_type),
            )

        @router.post(
            prefix + "/claims/{claim_id}/versions",
            status_code=201,
            include_in_schema=not mobile,
        )
        async def upload_version(
            claim_id: UUID,
            request: Request,
            x_treasury_metadata: str = Header(alias="X-Treasury-Metadata"),
            actor=_ACTOR_DEPENDENCY,
            repository=_REPOSITORY_DEPENDENCY,
        ):
            metadata = metadata_header(x_treasury_metadata)
            if metadata.expected_version is None:
                raise HTTPException(
                    422, "The exact previous claim version is required."
                )
            data, media_type = await _upload_bytes(request)
            return await run_in_threadpool(
                call,
                lambda: submit_claim(
                    repository, actor, metadata, data, media_type, claim_id
                ),
            )

        @router.post(
            prefix + "/evidence", status_code=201, include_in_schema=not mobile
        )
        async def evidence_upload(
            request: Request,
            request_id: UUID,
            account_id: UUID,
            purpose: Literal[
                "recipient", "opening", "statement", "correction"
            ] = "recipient",
            actor=_ACTOR_DEPENDENCY,
            repository=_REPOSITORY_DEPENDENCY,
        ):
            data, media_type = await _upload_bytes(request)
            return await run_in_threadpool(
                call,
                lambda: upload_evidence(
                    repository, actor, request_id, account_id, purpose, data, media_type
                ),
            )

        @router.get(
            prefix + "/evidence/{evidence_id}/content", include_in_schema=not mobile
        )
        def evidence_content(
            evidence_id: UUID,
            actor=_ACTOR_DEPENDENCY,
            repository=_REPOSITORY_DEPENDENCY,
        ):
            return binary_result(
                call(lambda: repository.evidence_content(actor, evidence_id))
            )

        @router.get(prefix + "/receipts/{receipt_id}", include_in_schema=not mobile)
        def receipt(
            receipt_id: UUID, actor=_ACTOR_DEPENDENCY, repository=_REPOSITORY_DEPENDENCY
        ):
            return call(lambda: repository.receipt_detail(actor, receipt_id))

        @router.post(
            prefix + "/receipts/{receipt_id}/allocation-preview",
            include_in_schema=not mobile,
        )
        def preview(
            receipt_id: UUID,
            command: AllocationPreview,
            actor=_ACTOR_DEPENDENCY,
            repository=_REPOSITORY_DEPENDENCY,
        ):
            return call(
                lambda: repository.preview_receipt_application(
                    actor, receipt_id, command
                )
            )

        @router.get(
            prefix + "/reconciliations/{reconciliation_id}",
            include_in_schema=not mobile,
        )
        def reconciliation(
            reconciliation_id: UUID,
            actor=_ACTOR_DEPENDENCY,
            repository=_REPOSITORY_DEPENDENCY,
        ):
            return call(
                lambda: repository.reconciliation_detail(actor, reconciliation_id)
            )

        @router.get(
            prefix + "/reconciliations/{reconciliation_id}/export",
            include_in_schema=not mobile,
        )
        def reconciliation_export(
            reconciliation_id: UUID,
            actor=_ACTOR_DEPENDENCY,
            repository=_REPOSITORY_DEPENDENCY,
        ):
            result = call(
                lambda: repository.reconciliation_export(actor, reconciliation_id)
            )
            return Response(
                json.dumps(result),
                media_type="application/json",
                headers={
                    "Cache-Control": "no-store",
                    "Content-Disposition": 'attachment; filename="treasury-private-reconciliation.json"',
                    "X-Content-Type-Options": "nosniff",
                },
            )

    routes("/api/v1/treasury")
    routes("/api/mobile/v1/treasury", mobile=True)
    return router
