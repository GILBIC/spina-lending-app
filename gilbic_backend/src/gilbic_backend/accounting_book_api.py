"""Authenticated setup and read access for this deployment's accounting book."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from .account_repository import PostgresAccountRepository
from .accounting_book_repository import (
    AccountingBookConflict,
    AccountingBookDenied,
    AccountingBookError,
    BookKind,
    PostgresAccountingBookRepository,
    book_identity_payload,
)
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .request_auth import authenticated_device_context

SETUP_PERMISSION = "accounting.journal.manage"


class ConfigureAccountingBookRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: BookKind
    entity_label: str = Field(min_length=1, max_length=200)
    evidence_reference: str = Field(min_length=1, max_length=1000)
    evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirm: StrictBool = False

    @field_validator("entity_label", "evidence_reference")
    @classmethod
    def retained_exact_text(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError(
                "Retained identity and evidence text must be nonblank without outer whitespace."
            )
        return value


def accounting_book_repository_dependency() -> PostgresAccountingBookRepository:
    return PostgresAccountingBookRepository()


def _actor(authorization, x_device_id, auth, accounts, *, permission):
    actor = authenticated_device_context(
        authorization=authorization,
        device_identifier=x_device_id,
        auth=auth,
        accounts=accounts,
        permission=permission,
        permission_error="Current accounting permission is required.",
    )
    if actor.status != "active" or "management" not in actor.roles:
        raise HTTPException(
            status_code=403,
            detail="Active Management access is required for accounting book identity.",
        )
    return actor


def _exception(error: AccountingBookError) -> HTTPException:
    status = (
        403
        if isinstance(error, AccountingBookDenied)
        else 409
        if isinstance(error, AccountingBookConflict)
        else 503
    )
    return HTTPException(
        status_code=status, detail={"code": error.code, "message": str(error)}
    )


def create_accounting_book_router() -> APIRouter:
    router = APIRouter(tags=["management financial accounting"])

    @router.get("/api/v1/management/financial-accounting/book")
    @router.get(
        "/api/mobile/v1/management/financial-accounting/book", include_in_schema=False
    )
    def get_book_identity(
        auth: Annotated[SupabaseAuthClient, Depends(auth_client_dependency)],
        accounts: Annotated[
            PostgresAccountRepository, Depends(account_repository_dependency)
        ],
        books: Annotated[
            PostgresAccountingBookRepository,
            Depends(accounting_book_repository_dependency),
        ],
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    ) -> dict[str, object]:
        actor = _actor(
            authorization, x_device_id, auth, accounts, permission="accounting.view"
        )
        try:
            identity = books.get_book_identity()
        except AccountingBookError as error:
            raise _exception(error) from error
        return {
            "success": True,
            "data": {
                "book": book_identity_payload(identity),
                "can_configure": SETUP_PERMISSION in actor.permissions,
            },
        }

    @router.post("/api/v1/management/financial-accounting/book")
    @router.post(
        "/api/mobile/v1/management/financial-accounting/book", include_in_schema=False
    )
    def configure_book_identity(
        body: ConfigureAccountingBookRequest,
        auth: Annotated[SupabaseAuthClient, Depends(auth_client_dependency)],
        accounts: Annotated[
            PostgresAccountRepository, Depends(account_repository_dependency)
        ],
        books: Annotated[
            PostgresAccountingBookRepository,
            Depends(accounting_book_repository_dependency),
        ],
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    ) -> dict[str, object]:
        actor = _actor(
            authorization, x_device_id, auth, accounts, permission=SETUP_PERMISSION
        )
        if not body.confirm:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "accounting_book_confirmation_required",
                    "message": "Explicit confirmation is required for immutable accounting book setup.",
                },
            )
        try:
            identity = books.configure_book_identity(
                kind=body.kind,
                entity_label=body.entity_label,
                evidence_reference=body.evidence_reference,
                evidence_digest=body.evidence_digest,
                actor_user_id=actor.user_id,
            )
        except AccountingBookError as error:
            raise _exception(error) from error
        return {
            "success": True,
            "data": {"book": book_identity_payload(identity), "can_configure": True},
        }

    return router
