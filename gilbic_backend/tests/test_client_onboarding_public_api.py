from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.main import create_app


class FakeClientOnboardingApplicants:
    def __init__(self) -> None:
        self.submitted: dict[str, Any] | None = None

    def submit_applicant(self, **payload: Any):
        self.submitted = payload
        return SimpleNamespace(
            application_reference="APP-2026-000124",
            status="requirements_incomplete",
        )


def onboarding_api_module():
    return importlib.import_module("gilbic_backend.client_onboarding_api")


def valid_payload() -> dict[str, object]:
    return {
        "full_name": "Juan Dela Cruz",
        "phone_number": "09171234567",
        "email": "juan@example.com",
        "present_address": "Cardona, Rizal",
        "national_id_egov_evidence_reference": "FAKE-EGOV-NATIONAL-ID-VERIFIED",
        "tin_id_egov_evidence_reference": "FAKE-EGOV-TIN-ID-VERIFIED",
        "meralco_bill_evidence_reference": "FAKE-MERALCO-BILL-EVIDENCE",
        "privacy_consent": True,
        "accuracy_declaration": True,
    }


def client_with_fake() -> tuple[TestClient, FakeClientOnboardingApplicants]:
    module = onboarding_api_module()
    repository = FakeClientOnboardingApplicants()
    app = create_app()
    app.dependency_overrides[module.client_onboarding_repository_dependency] = (
        lambda: repository
    )

    def unexpected_private_dependency():
        raise AssertionError(
            "Public pre-CIF intake must not use Auth or Client-account context."
        )

    app.dependency_overrides[auth_client_dependency] = unexpected_private_dependency
    app.dependency_overrides[account_repository_dependency] = unexpected_private_dependency
    return TestClient(app), repository


def test_public_pre_cif_intake_is_normalized_and_pre_account() -> None:
    client, repository = client_with_fake()
    payload = valid_payload()
    payload.update(
        {
            "full_name": "  Juan   Dela Cruz  ",
            "phone_number": " 0917 123-4567 ",
            "email": " JUAN@EXAMPLE.COM ",
            "present_address": "  Cardona,   Rizal ",
        }
    )

    response = client.post("/api/v1/public/onboarding/applicants", json=payload)

    assert response.status_code == 201
    assert response.json() == {
        "application_reference": "APP-2026-000124",
        "status": "requirements_incomplete",
        "detail": "Keep this application reference to check your onboarding status.",
    }
    assert repository.submitted is not None
    assert repository.submitted["full_name"] == "Juan Dela Cruz"
    assert repository.submitted["phone_number"] == "09171234567"
    assert repository.submitted["email"] == "juan@example.com"
    assert repository.submitted["present_address"] == "Cardona, Rizal"
    assert set(repository.submitted) == {
        "full_name",
        "phone_number",
        "email",
        "present_address",
        "national_id_egov_evidence_reference",
        "tin_id_egov_evidence_reference",
        "meralco_bill_evidence_reference",
        "privacy_consent",
        "accuracy_declaration",
    }


@pytest.mark.parametrize(
    "extra_field",
    [
        "requested_amount",
        "requested_loan_type",
        "loan_purpose",
        "baseline_face_scan_evidence_reference",
        "username",
        "password",
    ],
)
def test_public_pre_cif_intake_rejects_non_intake_fields(extra_field: str) -> None:
    client, repository = client_with_fake()
    payload = valid_payload()
    payload[extra_field] = "not-allowed"

    response = client.post("/api/v1/public/onboarding/applicants", json=payload)

    assert response.status_code == 422
    assert repository.submitted is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("privacy_consent", False),
        ("accuracy_declaration", False),
        ("full_name", "J"),
        ("phone_number", "123456"),
        ("present_address", "Riz"),
        ("national_id_egov_evidence_reference", ""),
        ("tin_id_egov_evidence_reference", ""),
        ("meralco_bill_evidence_reference", ""),
    ],
)
def test_public_pre_cif_intake_rejects_invalid_required_values(
    field: str,
    value: object,
) -> None:
    client, repository = client_with_fake()
    payload = valid_payload()
    payload[field] = value

    response = client.post("/api/v1/public/onboarding/applicants", json=payload)

    assert response.status_code == 422
    assert repository.submitted is None
