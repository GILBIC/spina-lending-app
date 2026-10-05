"""Private Management review endpoints; operational Treasury never auto-posts."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .office_review_evidence_route import PrivateOfficeRoute
from .request_auth import authenticated_device_context
from .treasury_api import call
from .treasury_receipt_accounting_repository import (
    PostgresTreasuryReceiptAccountingRepository,
)


class ExactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CashMappingRequest(ExactRequest):
    cash_code: Literal["1010", "1030"]
    expected_version: int = Field(ge=0, strict=True)
    request_id: UUID
    evidence_reference: str = Field(min_length=1, max_length=1000)
    evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirm: StrictBool = False

    @field_validator("evidence_reference")
    @classmethod
    def exact_reference(cls, value):
        if value != value.strip() or not value.strip():
            raise ValueError(
                "Retained evidence reference requires exact text without outer whitespace."
            )
        return value


class ReceiptPrepareRequest(ExactRequest):
    mapping_id: UUID
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_id: UUID


class ReceiptPostRequest(ExactRequest):
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmation_token: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirm: StrictBool = False


def treasury_receipt_accounting_repository_dependency():
    return PostgresTreasuryReceiptAccountingRepository()


def receipt_accounting_actor(
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
            403, detail="Active Management access is required for receipt accounting."
        )
    return actor


def _confirmed(confirm):
    if not confirm:
        raise HTTPException(
            409,
            detail={
                "code": "receipt_accounting_confirmation_required",
                "message": "Explicit confirmation of the retained accounting review is required.",
            },
        )


def create_treasury_receipt_accounting_router():
    router = APIRouter(
        tags=["management financial accounting"], route_class=PrivateOfficeRoute
    )
    actor_dependency = Depends(receipt_accounting_actor)
    repository_dependency = Depends(treasury_receipt_accounting_repository_dependency)

    def read_mapping(
        account_id: UUID, actor=actor_dependency, repository=repository_dependency
    ):
        return call(lambda: repository.read_mapping(actor, account_id=account_id))

    def configure_mapping(
        account_id: UUID,
        body: CashMappingRequest,
        actor=actor_dependency,
        repository=repository_dependency,
    ):
        _confirmed(body.confirm)
        return call(
            lambda: repository.configure_mapping(
                actor, account_id=account_id, **body.model_dump(exclude={"confirm"})
            )
        )

    def review(
        receipt_id: UUID,
        mapping_id: UUID,
        actor=actor_dependency,
        repository=repository_dependency,
    ):
        return call(
            lambda: repository.review(
                actor, receipt_id=receipt_id, mapping_id=mapping_id
            )
        )

    def prepare(
        receipt_id: UUID,
        body: ReceiptPrepareRequest,
        actor=actor_dependency,
        repository=repository_dependency,
    ):
        return call(
            lambda: repository.prepare(
                actor, receipt_id=receipt_id, **body.model_dump()
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
        body: ReceiptPostRequest,
        actor=actor_dependency,
        repository=repository_dependency,
    ):
        _confirmed(body.confirm)
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
        public_schema = "/mobile/" not in prefix
        for path, endpoint, method in (
            ("/accounts/{account_id}/cash-mapping", read_mapping, "GET"),
            ("/accounts/{account_id}/cash-mapping", configure_mapping, "POST"),
            ("/receipts/{receipt_id}/review", review, "GET"),
            ("/receipts/{receipt_id}/prepare", prepare, "POST"),
            ("/receipt-preparations/{preparation_id}", read_preparation, "GET"),
            ("/receipt-preparations/{preparation_id}/post", post, "POST"),
        ):
            router.add_api_route(
                prefix + path,
                endpoint,
                methods=[method],
                include_in_schema=public_schema,
            )
    return router
