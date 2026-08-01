from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
    CollectionStatus,
)
from .service import (
    CollectionProtocolError,
    CollectionSubmissionService,
    SubmissionHeaders,
)


class CollectionSubmissionBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    client_transaction_id: UUID
    route_entry_id: str = Field(min_length=1, max_length=128)
    client_id: str = Field(min_length=1, max_length=128)
    loan_id: str = Field(min_length=1, max_length=128)
    collection_date: date
    entry_type: CollectionEntryType
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    advance_from: date | None = None
    advance_until: date | None = None
    recorded_at: datetime
    device_id: str = Field(min_length=1, max_length=256)
    device_sequence: int = Field(ge=1)
    note: str = Field(default="", max_length=500)
    route_revision: str | None = Field(default=None, max_length=128)

    def to_command(self) -> CollectionCommand:
        return CollectionCommand(
            idempotency_key=self.client_transaction_id,
            route_entry_id=self.route_entry_id,
            client_id=self.client_id,
            loan_id=self.loan_id,
            collection_date=self.collection_date,
            entry_type=self.entry_type,
            amount=self.amount,
            advance_from=self.advance_from,
            advance_until=self.advance_until,
            recorded_at=self.recorded_at,
            device_id=self.device_id,
            device_sequence=self.device_sequence,
            note=self.note,
            route_revision=self.route_revision,
        )


ActorDependency = Callable[[], ActorContext]
ServiceDependency = Callable[[], CollectionSubmissionService]


def create_collection_router(
    *,
    get_actor: ActorDependency,
    get_service: ServiceDependency,
) -> APIRouter:
    """Create the official payment, ADV, and PASS endpoints.

    ``get_actor`` authenticates the bearer session and resolves the active
    registered device. ``get_service`` supplies the PostgreSQL idempotency
    executor and official SPINA posting bridge.
    """

    router = APIRouter(tags=["collector collections"])

    @router.post("/api/v1/collector/collections", response_class=JSONResponse)
    @router.post(
        "/api/mobile/v1/collector/collections",
        response_class=JSONResponse,
        include_in_schema=False,
    )
    def submit_collection(
        body: CollectionSubmissionBody,
        idempotency_key: UUID = Header(alias="Idempotency-Key"),
        client_transaction_id: UUID = Header(
            alias="X-Client-Transaction-Id"
        ),
        device_id: str = Header(alias="X-Device-Id"),
        contract_version: str = Header(alias="X-Gilbic-Contract-Version"),
        actor: ActorContext = Depends(get_actor),
        service: CollectionSubmissionService = Depends(get_service),
    ) -> JSONResponse:
        try:
            outcome = service.submit(
                actor=actor,
                headers=SubmissionHeaders(
                    idempotency_key=idempotency_key,
                    client_transaction_id=client_transaction_id,
                    device_id=device_id,
                    contract_version=contract_version,
                ),
                command=body.to_command(),
            )
        except CollectionProtocolError as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "success": False,
                    "message": exc.message,
                    "error": {"code": exc.code},
                },
            )

        payload = outcome.response_payload()
        if outcome.status is CollectionStatus.ACCEPTED:
            return JSONResponse(
                status_code=201,
                content={"success": True, "data": payload},
            )
        if outcome.status is CollectionStatus.DUPLICATE:
            return JSONResponse(
                status_code=200,
                content={"success": True, "data": payload},
            )
        if outcome.status is CollectionStatus.CONFLICT:
            return JSONResponse(
                status_code=409,
                content={
                    "success": False,
                    "message": outcome.message,
                    "error": {"code": outcome.code},
                    "data": payload,
                },
            )
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": outcome.message,
                "error": {"code": outcome.code},
                "data": payload,
            },
        )

    return router
