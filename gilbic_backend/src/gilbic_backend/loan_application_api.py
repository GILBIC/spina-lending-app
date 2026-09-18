from __future__ import annotations

from datetime import timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .account_repository import AccountContext, PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .loan_application_information import LoanApplicationInformation
from .loan_application_repository import (
    APPLICATION_REVIEW_PERMISSION,
    LoanApplicationAccessDenied,
    LoanApplicationConflict,
    LoanApplicationVersionRecord,
    PostgresLoanApplicationRepository,
)
from .request_auth import authenticated_device_context


class CreateLoanApplicationDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cif_version_id: UUID
    application_reference: str
    information: LoanApplicationInformation

    @field_validator("application_reference")
    @classmethod
    def normalize_reference(cls, value: str) -> str:
        reference = value.strip()
        if not reference:
            raise ValueError("Application reference is required.")
        return reference


class AppendLoanApplicationDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cif_version_id: UUID
    expected_version_number: Annotated[int, Field(strict=True, ge=1)]
    information: LoanApplicationInformation


def _office_application_actor(
    *,
    authorization: str | None,
    x_device_id: str | None,
    auth: SupabaseAuthClient,
    accounts: PostgresAccountRepository,
) -> AccountContext:
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
    return actor


def _application_payload(record: LoanApplicationVersionRecord) -> dict[str, object]:
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
        actor = _office_application_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
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
        return _application_payload(record)

    @router.post(
        "/api/v1/management/clients/{client_id}/loan-applications/drafts",
        status_code=201,
    )
    def create_application_draft(
        client_id: UUID,
        payload: CreateLoanApplicationDraftRequest,
        response: Response,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        applications: PostgresLoanApplicationRepository = Depends(
            loan_application_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _office_application_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = applications.create_draft(
                actor_user_id=actor.user_id,
                client_id=client_id,
                cif_version_id=payload.cif_version_id,
                application_reference=payload.application_reference,
                information=payload.information,
            )
        except LoanApplicationAccessDenied as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except LoanApplicationConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

        response.headers["Cache-Control"] = "no-store"
        return _application_payload(record)

    @router.post(
        "/api/v1/management/clients/{client_id}/loan-applications/"
        "{application_id}/draft-versions",
        status_code=200,
    )
    def append_application_draft(
        client_id: UUID,
        application_id: UUID,
        payload: AppendLoanApplicationDraftRequest,
        response: Response,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        applications: PostgresLoanApplicationRepository = Depends(
            loan_application_repository_dependency
        ),
    ) -> dict[str, object]:
        actor = _office_application_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = applications.append_draft(
                actor_user_id=actor.user_id,
                client_id=client_id,
                application_id=application_id,
                cif_version_id=payload.cif_version_id,
                expected_version_number=payload.expected_version_number,
                information=payload.information,
            )
        except LoanApplicationAccessDenied as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except LoanApplicationConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

        response.headers["Cache-Control"] = "no-store"
        return _application_payload(record)

    return router
