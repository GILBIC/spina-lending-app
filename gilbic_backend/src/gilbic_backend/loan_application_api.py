from __future__ import annotations

from datetime import timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Response

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .loan_application_repository import (
    APPLICATION_REVIEW_PERMISSION,
    LoanApplicationAccessDenied,
    LoanApplicationConflict,
    PostgresLoanApplicationRepository,
)
from .request_auth import authenticated_device_context


def loan_application_repository_dependency() -> PostgresLoanApplicationRepository:
    return PostgresLoanApplicationRepository()


def create_loan_application_router() -> APIRouter:
    router = APIRouter(tags=["loan-applications"])

    @router.get(
        "/api/v1/management/clients/{client_id}/loan-applications/"
        "{application_id}/versions/{version_number}/review-summary"
    )
    def get_application_review_summary(
        client_id: UUID,
        application_id: UUID,
        version_number: Annotated[int, Path(ge=1)],
        response: Response,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        applications: PostgresLoanApplicationRepository = Depends(
            loan_application_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission=APPLICATION_REVIEW_PERMISSION,
            permission_error="Onboarding requirement review permission is required.",
        )
        if not any(role in actor.roles for role in ("employee", "management")):
            raise HTTPException(
                status_code=403,
                detail="Employee or Management role is required for application review.",
            )
        try:
            record = applications.get_version(
                actor_user_id=actor.user_id,
                client_id=client_id,
                application_id=application_id,
                version_number=version_number,
            )
        except LoanApplicationAccessDenied as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except LoanApplicationConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

        response.headers["Cache-Control"] = "no-store"
        return {
            "client_id": str(record.client_id),
            "application_id": str(record.application_id),
            "application_version_id": str(record.id),
            "application_reference": record.application_reference,
            "cif_version_id": str(record.cif_version_id),
            "version_number": record.version_number,
            "information": record.information.model_dump(mode="json"),
            "missing_fields": list(record.information.missing_fields()),
            "recorded_at": record.recorded_at.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "review_scope": "loan_application_information_only",
        }

    return router
