"""Protected review download; it never creates registered books or invoices."""

import re
from datetime import date
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BeforeValidator

from .account_repository import PostgresAccountRepository
from .accounting_export import (
    AccountingExportError,
    build_accounting_export,
    validate_range,
)
from .accounting_export_repository import PostgresAccountingExportRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .request_auth import authenticated_device_context


def accounting_export_repository_dependency() -> PostgresAccountingExportRepository:
    return PostgresAccountingExportRepository()


def _iso_date(value: object) -> date:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None
    ):
        raise ValueError("Use an ISO date in YYYY-MM-DD format.")
    return date.fromisoformat(value)


def create_accounting_export_router() -> APIRouter:
    router = APIRouter(tags=["management accounting export"])

    @router.get(
        "/api/v1/management/financial-accounting/export", response_class=Response
    )
    def download_accounting_export(
        start_date: Annotated[date, BeforeValidator(_iso_date)],
        end_date: Annotated[date, BeforeValidator(_iso_date)],
        auth: Annotated[SupabaseAuthClient, Depends(auth_client_dependency)],
        accounts: Annotated[
            PostgresAccountRepository, Depends(account_repository_dependency)
        ],
        repository: Annotated[
            PostgresAccountingExportRepository,
            Depends(accounting_export_repository_dependency),
        ],
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    ) -> Response:
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
                detail="Management access is required for accounting exports.",
            )
        try:
            validate_range(start_date, end_date)
            snapshot = repository.load_snapshot(
                start_date=start_date, end_date=end_date
            )
            content = build_accounting_export(
                snapshot,
                start_date=start_date,
                end_date=end_date,
                generated_by_user_id=actor.user_id,
            )
        except AccountingExportError as error:
            code = {"range": 422, "oversized": 413, "integrity": 409}[error.code]
            raise HTTPException(
                status_code=code,
                detail={
                    "code": f"accounting_export_{error.code}",
                    "message": str(error),
                },
            ) from error
        except psycopg.Error as error:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "accounting_export_unavailable",
                    "message": "Accounting export is unavailable; retry later or select a shorter range.",
                },
            ) from error
        filename = (
            f"spina-accounting-{start_date.isoformat()}-to-{end_date.isoformat()}.zip"
        )
        return Response(
            content=content,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router
