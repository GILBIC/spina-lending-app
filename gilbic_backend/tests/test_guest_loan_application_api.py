from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.main import create_app


class FakeGuestApplications:
    def __init__(self) -> None:
        self.submitted: dict[str, Any] | None = None

    def submit(self, **payload: Any):
        self.submitted = payload
        return SimpleNamespace(
            application_reference="APP-2026-000124",
            status="submitted",
        )


def guest_api_module():
    return importlib.import_module("gilbic_backend.guest_loan_application_api")


def valid_payload() -> dict[str, object]:
    return {
        "full_name": "Juan Dela Cruz",
        "phone_number": "09171234567",
        "email": "juan@example.com",
        "present_address": "Cardona, Rizal",
        "permanent_address": "Cardona, Rizal",
        "livelihood_type": "Self-employed",
        "livelihood_details": "Sari-sari store",
        "declared_monthly_income": 18000,
        "declared_monthly_expenses": 9000,
        "declared_monthly_debt_payments": 1500,
        "requested_loan_type": "regular",
        "requested_amount": 5000,
        "requested_term_days": 120,
        "loan_purpose": "Working capital",
        "national_id_egov_evidence_reference": "FAKE-EGOV-NATIONAL-ID-VERIFIED",
        "tin_id_egov_evidence_reference": "FAKE-EGOV-TIN-ID-VERIFIED",
        "meralco_bill_evidence_reference": "FAKE-MERALCO-BILL-EVIDENCE",
        "baseline_face_scan_evidence_reference": "FAKE-BASELINE-FACE-SCAN-EVIDENCE",
        "privacy_consent": True,
        "accuracy_declaration": True,
    }


def client_with_fake() -> tuple[TestClient, FakeGuestApplications]:
    module = guest_api_module()
    repository = FakeGuestApplications()
    app = create_app()
    app.dependency_overrides[module.guest_loan_application_repository_dependency] = (
        lambda: repository
    )

    def unexpected_private_dependency():
        raise AssertionError("Public guest submission must not use Auth or Client account context.")

    app.dependency_overrides[auth_client_dependency] = unexpected_private_dependency
    app.dependency_overrides[account_repository_dependency] = unexpected_private_dependency
    return TestClient(app), repository


def test_public_guest_submission_is_normalized_and_pre_account() -> None:
    client, repository = client_with_fake()
    payload = valid_payload()
    payload.update(
        {
            "full_name": "  Juan   Dela Cruz  ",
            "phone_number": " 0917 123-4567 ",
            "email": " JUAN@EXAMPLE.COM ",
            "present_address": "  Cardona,   Rizal ",
            "requested_loan_type": " Regular ",
        }
    )

    response = client.post("/api/v1/public/loan-applications", json=payload)

    assert response.status_code == 201
    assert response.json() == {
        "application_reference": "APP-2026-000124",
        "status": "submitted",
        "detail": "Keep this application reference to check your status.",
    }
    assert repository.submitted is not None
    assert repository.submitted["full_name"] == "Juan Dela Cruz"
    assert repository.submitted["phone_number"] == "09171234567"
    assert repository.submitted["email"] == "juan@example.com"
    assert repository.submitted["present_address"] == "Cardona, Rizal"
    assert repository.submitted["requested_loan_type"] == "regular"
    assert (
        repository.submitted["national_id_egov_evidence_reference"]
        == "FAKE-EGOV-NATIONAL-ID-VERIFIED"
    )
    assert (
        repository.submitted["tin_id_egov_evidence_reference"]
        == "FAKE-EGOV-TIN-ID-VERIFIED"
    )
    assert (
        repository.submitted["meralco_bill_evidence_reference"]
        == "FAKE-MERALCO-BILL-EVIDENCE"
    )
    assert (
        repository.submitted["baseline_face_scan_evidence_reference"]
        == "FAKE-BASELINE-FACE-SCAN-EVIDENCE"
    )


def test_public_guest_submission_forbids_extra_input() -> None:
    client, repository = client_with_fake()
    payload = valid_payload()
    payload["create_account_now"] = True

    response = client.post("/api/v1/public/loan-applications", json=payload)

    assert response.status_code == 422
    assert repository.submitted is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("privacy_consent", False),
        ("accuracy_declaration", False),
        ("declared_monthly_income", -1),
        ("declared_monthly_expenses", -1),
        ("declared_monthly_debt_payments", -1),
        ("requested_amount", 0),
        ("requested_term_days", 0),
        ("national_id_egov_evidence_reference", ""),
        ("tin_id_egov_evidence_reference", ""),
        ("meralco_bill_evidence_reference", ""),
        ("baseline_face_scan_evidence_reference", ""),
    ],
)
def test_public_guest_submission_rejects_invalid_required_values(
    field: str,
    value: object,
) -> None:
    client, repository = client_with_fake()
    payload = valid_payload()
    payload[field] = value

    response = client.post("/api/v1/public/loan-applications", json=payload)

    assert response.status_code == 422
    assert repository.submitted is None


def test_public_guest_submission_normalizes_7x7_product() -> None:
    client, repository = client_with_fake()
    payload = valid_payload()
    payload["requested_loan_type"] = " 7X7 "

    response = client.post("/api/v1/public/loan-applications", json=payload)

    assert response.status_code == 201
    assert repository.submitted is not None
    assert repository.submitted["requested_loan_type"] == "7x7"
