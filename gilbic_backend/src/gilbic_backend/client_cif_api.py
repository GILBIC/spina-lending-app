from __future__ import annotations

from datetime import datetime, timezone
from typing import NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .account_repository import AccountContext, PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .client_cif_repository import (
    ClientCifAccessDenied,
    ClientCifConflict,
    ClientCifLivenessStatus,
    ClientCifVersion,
    PostgresClientCifRepository,
    normalize_cif_information,
)
from .request_auth import authenticated_device_context


_CIF_PERMISSION = "client_onboarding.requirement.review"


class BaselineLiveFaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_reference: str = Field(min_length=1, max_length=500)
    liveness_status: ClientCifLivenessStatus


class CifReviewInformation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    full_name: str
    phone_number: str
    email: str | None
    present_address: str


class CorrectCifDraftInformationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cif_version_id: UUID
    expected_information: CifReviewInformation
    corrected_information: CifReviewInformation
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("corrected_information")
    @classmethod
    def validate_new_information(
        cls, value: CifReviewInformation
    ) -> CifReviewInformation:
        return CifReviewInformation.model_validate(
            normalize_cif_information(value.model_dump())
        )

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 3:
            raise ValueError(
                "A CIF correction reason of at least 3 characters is required."
            )
        return normalized


class ConfirmCifReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cif_version_id: UUID
    expected_information: CifReviewInformation
    applicant_confirmation_evidence_reference: str = Field(strict=True)

    @field_validator("applicant_confirmation_evidence_reference")
    @classmethod
    def normalize_evidence_reference(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Applicant confirmation evidence reference is required.")
        return normalized


def client_cif_repository_dependency() -> PostgresClientCifRepository:
    return PostgresClientCifRepository()


def _office_cif_actor(
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
        permission=_CIF_PERMISSION,
        permission_error="Onboarding requirement review permission is required.",
    )
    if not any(role in actor.roles for role in ("employee", "management")):
        raise HTTPException(
            status_code=403,
            detail="Employee or Management role is required for CIF work.",
        )
    return actor


def _summary_payload(record: ClientCifVersion) -> dict[str, object]:
    return {
        "client_id": str(record.client_id),
        "version_number": record.version_number,
        "status": record.status,
        "liveness_status": record.baseline_liveness_status,
    }


def _iso_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _activation_payload(record: ClientCifVersion) -> dict[str, object]:
    payload = _summary_payload(record)
    payload.update(
        {
            "activated_at": _iso_timestamp(record.activated_at),
            "expires_at": _iso_timestamp(record.expires_at),
            "review_due_at": _iso_timestamp(record.review_due_at),
        }
    )
    return payload


def _raise_cif_conflict(error: ClientCifConflict) -> NoReturn:
    raise HTTPException(status_code=409, detail=str(error)) from error


def create_client_cif_router() -> APIRouter:
    router = APIRouter(tags=["client-cif"])

    @router.get("/api/v1/management/clients/{client_id}/cif/review-summary")
    def get_cif_review_summary(
        client_id: UUID,
        response: Response,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        cif: PostgresClientCifRepository = Depends(client_cif_repository_dependency),
    ) -> dict[str, object]:
        _office_cif_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = cif.get_review_summary(client_id=client_id)
        except ClientCifConflict as error:
            _raise_cif_conflict(error)
        response.headers["Cache-Control"] = "no-store"
        payload = _summary_payload(record)
        payload.update(
            {
                "cif_version_id": str(record.id),
                "full_name": record.full_name,
                "phone_number": record.phone_number,
                "email": record.email,
                "present_address": record.present_address,
                "review_scope": "cif_information_only",
            }
        )
        return payload

    @router.patch("/api/v1/management/clients/{client_id}/cif/draft-information")
    def correct_cif_draft_information(
        client_id: UUID,
        body: CorrectCifDraftInformationRequest,
        response: Response,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        cif: PostgresClientCifRepository = Depends(client_cif_repository_dependency),
    ) -> dict[str, object]:
        actor = _office_cif_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = cif.correct_draft_information(
                actor_user_id=actor.user_id,
                client_id=client_id,
                cif_version_id=body.cif_version_id,
                expected_information=body.expected_information.model_dump(),
                corrected_information=body.corrected_information.model_dump(),
                reason=body.reason,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except ClientCifConflict as error:
            _raise_cif_conflict(error)
        response.headers["Cache-Control"] = "no-store"
        payload = _summary_payload(record)
        payload.update(
            {
                "cif_version_id": str(record.id),
                "full_name": record.full_name,
                "phone_number": record.phone_number,
                "email": record.email,
                "present_address": record.present_address,
                "review_scope": "cif_information_only",
            }
        )
        return payload

    @router.post(
        "/api/v1/management/clients/{client_id}/cif/review-confirmations",
        status_code=status.HTTP_201_CREATED,
    )
    def confirm_cif_review(
        client_id: UUID,
        body: ConfirmCifReviewRequest,
        response: Response,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        cif: PostgresClientCifRepository = Depends(client_cif_repository_dependency),
    ) -> dict[str, object]:
        actor = _office_cif_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = cif.confirm_review(
                actor_user_id=actor.user_id,
                client_id=client_id,
                cif_version_id=body.cif_version_id,
                expected_information=body.expected_information.model_dump(),
                applicant_confirmation_evidence_reference=(
                    body.applicant_confirmation_evidence_reference
                ),
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except ClientCifAccessDenied as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        except ClientCifConflict as error:
            _raise_cif_conflict(error)
        response.headers["Cache-Control"] = "no-store"
        confirmed_at = record.confirmed_at.astimezone(timezone.utc)
        return {
            "review_confirmation_id": str(record.id),
            "client_id": str(record.client_id),
            "cif_version_id": str(record.cif_version_id),
            "review_cycle_number": record.review_cycle_number,
            "witnessed_by_user_id": str(record.witnessed_by_user_id),
            "confirmed_at": confirmed_at.isoformat().replace("+00:00", "Z"),
            "review_scope": "cif_information_only",
        }

    @router.post(
        "/api/v1/management/clients/{client_id}/cif/draft",
        status_code=status.HTTP_201_CREATED,
    )
    def begin_cif_draft(
        client_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        cif: PostgresClientCifRepository = Depends(client_cif_repository_dependency),
    ) -> dict[str, object]:
        actor = _office_cif_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = cif.begin_draft(actor_user_id=actor.user_id, client_id=client_id)
        except ClientCifConflict as error:
            _raise_cif_conflict(error)
        return _summary_payload(record)

    @router.patch(
        "/api/v1/management/clients/{client_id}/cif/baseline-live-face"
    )
    def record_baseline_live_face(
        client_id: UUID,
        body: BaselineLiveFaceRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        cif: PostgresClientCifRepository = Depends(client_cif_repository_dependency),
    ) -> dict[str, object]:
        _office_cif_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        try:
            record = cif.record_baseline_live_face(
                client_id=client_id,
                evidence_reference=body.evidence_reference,
                liveness_status=body.liveness_status,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except ClientCifConflict as error:
            _raise_cif_conflict(error)
        return _summary_payload(record)

    @router.post("/api/v1/management/clients/{client_id}/cif/activate")
    def activate_cif(
        client_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        cif: PostgresClientCifRepository = Depends(client_cif_repository_dependency),
    ) -> dict[str, object]:
        actor = _office_cif_actor(
            authorization=authorization,
            x_device_id=x_device_id,
            auth=auth,
            accounts=accounts,
        )
        if "management" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail="Management role is required to activate a CIF.",
            )
        try:
            record = cif.activate_current(
                actor_user_id=actor.user_id,
                client_id=client_id,
            )
        except ClientCifConflict as error:
            _raise_cif_conflict(error)
        return _activation_payload(record)

    return router
