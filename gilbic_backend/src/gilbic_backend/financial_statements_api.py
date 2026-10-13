from __future__ import annotations

from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException, Query

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .financial_statement_payload import statement_pack_payload as _pack_payload
from .financial_statements_repository import (
    PostgresFinancialStatementsRepository,
    StatementPeriodNotFound,
)
from .request_auth import authenticated_device_context


def financial_statements_repository_dependency() -> (
    PostgresFinancialStatementsRepository
):
    return PostgresFinancialStatementsRepository()


def create_financial_statements_router() -> APIRouter:
    router = APIRouter(tags=["management financial statements"])

    @router.get("/api/v1/management/financial-accounting/statements")
    @router.get(
        "/api/mobile/v1/management/financial-accounting/statements",
        include_in_schema=False,
    )
    def financial_statements(
        *,
        period_id: Annotated[UUID | None, Query()] = None,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: Annotated[SupabaseAuthClient, Depends(auth_client_dependency)],
        accounts: Annotated[
            PostgresAccountRepository, Depends(account_repository_dependency)
        ],
        statements: Annotated[
            PostgresFinancialStatementsRepository,
            Depends(financial_statements_repository_dependency),
        ],
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="accounting.view",
            permission_error="Financial Accounting view permission is required.",
        )
        if "management" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "management_role_required",
                    "message": "Management access is required for Financial Statements.",
                },
            )
        try:
            pack = statements.load_statement_pack(
                period_id=period_id, actor_user_id=actor.user_id
            )
        except StatementPeriodNotFound as error:
            raise HTTPException(
                status_code=404,
                detail={"code": error.code, "message": str(error)},
            ) from error
        except psycopg.Error as error:
            raise HTTPException(
                status_code=403 if error.sqlstate == "42501" else 503,
                detail="Current statement disclosure access or evidence is unavailable.",
            ) from error
        return {"success": True, "data": {"statements": _pack_payload(pack)}}

    return router
