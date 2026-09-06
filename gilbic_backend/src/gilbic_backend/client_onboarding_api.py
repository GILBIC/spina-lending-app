from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .client_onboarding_repository import PostgresClientOnboardingRepository


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _normalize_phone(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


class SubmitClientOnboardingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

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

    return router
