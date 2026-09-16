from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.client_onboarding_api import client_onboarding_repository_dependency
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
DEVICE_ID = "office-onboarding-device"


def _actor_context(*, role: str, permissions: tuple[str, ...]) -> AccountContext:
    return AccountContext(
        user_id=ACTOR_USER_ID,
        auth_user_id=AUTH_USER_ID,
        username=f"{role}.one",
        email=f"{role}@example.com",
        full_name=f"{role.title()} One",
        status="active",
        roles=(role,),
        permissions=permissions,
        device_registered=True,
    )


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "office-onboarding-token"
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="actor@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def __init__(self, context: AccountContext) -> None:
        self.context = context

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == DEVICE_ID
        return self.context


class FakeOnboardingRepository:
    def __init__(self) -> None:
        self.submitted: dict[str, Any] | None = None

    def submit_applicant(self, **payload: Any):
        self.submitted = payload
        return SimpleNamespace(
            application_reference="APP-2026-000124",
            status="requirements_incomplete",
        )


def _valid_payload() -> dict[str, object]:
    return {
        "full_name": "  Juan   Dela Cruz  ",
        "phone_number": " 0917 123-4567 ",
        "email": " JUAN@EXAMPLE.COM ",
        "present_address": "  Cardona,   Rizal ",
        "national_id_egov_evidence_reference": "FAKE-EGOV-NATIONAL-ID-VERIFIED",
        "tin_id_egov_evidence_reference": "FAKE-EGOV-TIN-ID-VERIFIED",
        "meralco_bill_evidence_reference": "FAKE-MERALCO-BILL-EVIDENCE",
        "privacy_consent": True,
        "accuracy_declaration": True,
    }


def _client_for(
    *,
    role: str,
    permissions: tuple[str, ...],
) -> tuple[TestClient, FakeOnboardingRepository]:
    auth = FakeAuthClient()
    accounts = FakeAccounts(_actor_context(role=role, permissions=permissions))
    onboarding = FakeOnboardingRepository()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: auth
    app.dependency_overrides[account_repository_dependency] = lambda: accounts
    app.dependency_overrides[client_onboarding_repository_dependency] = lambda: onboarding
    return TestClient(app), onboarding


def _headers(*, include_device: bool = True) -> dict[str, str]:
    headers = {"Authorization": "Bearer office-onboarding-token"}
    if include_device:
        headers["X-Device-Id"] = DEVICE_ID
    return headers


def test_public_new_applicant_intake_is_not_exposed() -> None:
    client, onboarding = _client_for(
        role="employee",
        permissions=("client_onboarding.requirement.review",),
    )

    response = client.post(
        "/api/v1/public/onboarding/applicants",
        json=_valid_payload(),
    )

    assert response.status_code == 404
    assert onboarding.submitted is None


def test_employee_with_permission_can_encode_office_intake() -> None:
    client, onboarding = _client_for(
        role="employee",
        permissions=("client_onboarding.requirement.review",),
    )

    response = client.post(
        "/api/v1/management/onboarding/applicants",
        headers=_headers(),
        json=_valid_payload(),
    )

    assert response.status_code == 201
    assert response.json() == {
        "application_reference": "APP-2026-000124",
        "status": "requirements_incomplete",
        "detail": "Office applicant intake recorded.",
    }
    assert onboarding.submitted is not None
    assert onboarding.submitted["full_name"] == "Juan Dela Cruz"
    assert onboarding.submitted["phone_number"] == "09171234567"
    assert onboarding.submitted["email"] == "juan@example.com"
    assert onboarding.submitted["present_address"] == "Cardona, Rizal"
    assert set(onboarding.submitted) == {
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


def test_management_with_permission_can_encode_office_intake() -> None:
    client, onboarding = _client_for(
        role="management",
        permissions=("client_onboarding.requirement.review",),
    )

    response = client.post(
        "/api/v1/management/onboarding/applicants",
        headers=_headers(),
        json=_valid_payload(),
    )

    assert response.status_code == 201
    assert onboarding.submitted is not None


def test_collector_cannot_encode_office_intake_even_with_permission() -> None:
    client, onboarding = _client_for(
        role="collector",
        permissions=("client_onboarding.requirement.review",),
    )

    response = client.post(
        "/api/v1/management/onboarding/applicants",
        headers=_headers(),
        json=_valid_payload(),
    )

    assert response.status_code == 403
    assert onboarding.submitted is None


def test_office_intake_requires_permission() -> None:
    client, onboarding = _client_for(role="employee", permissions=())

    response = client.post(
        "/api/v1/management/onboarding/applicants",
        headers=_headers(),
        json=_valid_payload(),
    )

    assert response.status_code == 403
    assert onboarding.submitted is None


def test_office_intake_requires_active_device_context() -> None:
    client, onboarding = _client_for(
        role="employee",
        permissions=("client_onboarding.requirement.review",),
    )

    response = client.post(
        "/api/v1/management/onboarding/applicants",
        headers=_headers(include_device=False),
        json=_valid_payload(),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "X-Device-Id is required."
    assert onboarding.submitted is None
