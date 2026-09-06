from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .account_repository import PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .client_onboarding_repository import PostgresClientOnboardingRepository
from .request_auth import authenticated_device_context


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _normalize_phone(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


class StrictOnboardingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SubmitClientOnboardingRequest(StrictOnboardingRequest):
    full_name: str = Field(min_length=2, max_length=200)
    phone_number: str = Field(min_length=7, max_length=40)
    email: str | None = Field(default=None, max_length=320)
    present_address: str = Field(min_length=5, max_length=500)
    national_id_egov_evidence_reference: str = Field(min_length=1, max_length=500)
    tin_id_egov_evidence_reference: str = Field(min_length=1, max_length=500)
    meralco_bill_evidence_reference: str = Field(min_length=1, max_length=500)
    privacy_consent: Literal[True]
    accuracy_declaration: Literal[True]

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        normalized = _normalize_text(value)
        if len(normalized) < 2:
            raise ValueError("Full name is required.")
        return normalized

    @field_validator("phone_number")
    @classmethod
    def normalize_phone_number(cls, value: str) -> str:
        normalized = _normalize_phone(value)
        if len(normalized) < 7:
            raise ValueError("Phone number must contain at least 7 digits.")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized or None

    @field_validator("present_address")
    @classmethod
    def normalize_present_address(cls, value: str) -> str:
        normalized = _normalize_text(value)
        if len(normalized) < 5:
            raise ValueError("Present address is required.")
        return normalized

    @field_validator(
        "national_id_egov_evidence_reference",
        "tin_id_egov_evidence_reference",
        "meralco_bill_evidence_reference",
    )
    @classmethod
    def normalize_evidence_reference(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Evidence reference is required.")
        return normalized


class DocumentRequirementReviewRequest(StrictOnboardingRequest):
    national_id_status: Literal["passed", "failed"]
    tin_id_status: Literal["passed", "failed"]
    meralco_bill_status: Literal["passed", "failed"]


class CollectorVisitRequest(StrictOnboardingRequest):
    result: Literal["passed", "failed"]
    note: str = Field(default="", max_length=500)
    evidence_reference: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        return _normalize_text(value)

    @field_validator("evidence_reference")
    @classmethod
    def normalize_optional_evidence_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


def client_onboarding_repository_dependency() -> PostgresClientOnboardingRepository:
    return PostgresClientOnboardingRepository()


def create_client_onboarding_router() -> APIRouter:
    router = APIRouter(tags=["client-onboarding"])

    @router.post(
        "/api/v1/public/onboarding/applicants",
        status_code=status.HTTP_201_CREATED,
    )
    def submit_public_applicant(
        body: SubmitClientOnboardingRequest,
        onboarding: PostgresClientOnboardingRepository = Depends(
            client_onboarding_repository_dependency
        ),
    ) -> dict[str, str]:
        record = onboarding.submit_applicant(
            full_name=body.full_name,
            phone_number=body.phone_number,
            email=body.email,
            present_address=body.present_address,
            national_id_egov_evidence_reference=(
                body.national_id_egov_evidence_reference
            ),
            tin_id_egov_evidence_reference=body.tin_id_egov_evidence_reference,
            meralco_bill_evidence_reference=body.meralco_bill_evidence_reference,
            privacy_consent=body.privacy_consent,
            accuracy_declaration=body.accuracy_declaration,
        )
        return {
            "application_reference": record.application_reference,
            "status": record.status,
            "detail": "Keep this application reference to check your onboarding status.",
        }

    @router.patch(
        "/api/v1/management/onboarding/applicants/{applicant_id}/document-requirements"
    )
    def review_document_requirements(
        applicant_id: UUID,
        body: DocumentRequirementReviewRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        onboarding: PostgresClientOnboardingRepository = Depends(
            client_onboarding_repository_dependency
        ),
    ) -> dict[str, str]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="client_onboarding.requirement.review",
            permission_error="Onboarding requirement review permission is required.",
        )
        if not any(role in actor.roles for role in ("employee", "management")):
            raise HTTPException(
                status_code=403,
                detail="Employee or Management role is required to review requirements.",
            )
        record = onboarding.review_document_requirements(
            actor_user_id=actor.user_id,
            applicant_id=applicant_id,
            national_id_status=body.national_id_status,
            tin_id_status=body.tin_id_status,
            meralco_bill_status=body.meralco_bill_status,
        )
        return {"status": record.status}

    @router.post("/api/v1/collector/onboarding/applicants/{applicant_id}/visit")
    def record_collector_visit(
        applicant_id: UUID,
        body: CollectorVisitRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        onboarding: PostgresClientOnboardingRepository = Depends(
            client_onboarding_repository_dependency
        ),
    ) -> dict[str, str]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="client_onboarding.visit.record",
            permission_error="Collector residence-visit permission is required.",
        )
        if "collector" not in actor.roles:
            raise HTTPException(
                status_code=403,
                detail="Collector role is required to record the residence visit.",
            )
        record = onboarding.record_collector_visit(
            actor_user_id=actor.user_id,
            applicant_id=applicant_id,
            result=body.result,
            note=body.note,
            evidence_reference=body.evidence_reference,
        )
        return {"status": record.status}

    @router.post(
        "/api/v1/management/onboarding/applicants/{applicant_id}/eligibility"
    )
    def approve_normal_eligibility(
        applicant_id: UUID,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
        auth: SupabaseAuthClient = Depends(auth_client_dependency),
        accounts: PostgresAccountRepository = Depends(account_repository_dependency),
        onboarding: PostgresClientOnboardingRepository = Depends(
            client_onboarding_repository_dependency
        ),
    ) -> dict[str, str]:
        actor = authenticated_device_context(
            authorization=authorization,
            device_identifier=x_device_id,
            auth=auth,
            accounts=accounts,
            permission="client_onboarding.requirement.review",
            permission_error="Onboarding requirement review permission is required.",
        )
        if not any(role in actor.roles for role in ("employee", "management")):
            raise HTTPException(
                status_code=403,
                detail="Employee or Management role is required to approve eligibility.",
            )

        record = onboarding.approve_normal_eligibility(
            actor_user_id=actor.user_id,
            applicant_id=applicant_id,
        )
        if record.status != "eligible_for_cif" or record.promoted_client_id is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "All four pre-CIF requirements must be passed "
                    "before normal eligibility."
                ),
            )

        return {
            "status": record.status,
            "client_id": str(record.promoted_client_id),
        }

    return router
