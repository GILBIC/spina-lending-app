from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.client_onboarding_api import client_onboarding_repository_dependency
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
APPLICANT_ID = UUID("33333333-3333-4333-8333-333333333333")
CLIENT_ID = UUID("44444444-4444-4444-8444-444444444444")
DEVICE_ID = "eligibility-device"


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
        assert access_token == "eligibility-token"
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
    def __init__(
        self,
        *,
        approval_status: str = "eligible_for_cif",
        promoted_client_id: UUID | None = CLIENT_ID,
    ) -> None:
        self.approval_status = approval_status
        self.promoted_client_id = promoted_client_id
        self.approval: dict[str, object] | None = None

    def approve_normal_eligibility(self, **payload: object):
        self.approval = payload
        return SimpleNamespace(
            status=self.approval_status,
            promoted_client_id=self.promoted_client_id,
        )


def _client_for(
    *,
    role: str,
    permissions: tuple[str, ...],
    approval_status: str = "eligible_for_cif",
    promoted_client_id: UUID | None = CLIENT_ID,
) -> tuple[TestClient, FakeOnboardingRepository]:
    auth = FakeAuthClient()
    accounts = FakeAccounts(_actor_context(role=role, permissions=permissions))
    onboarding = FakeOnboardingRepository(
        approval_status=approval_status,
        promoted_client_id=promoted_client_id,
    )
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: auth
    app.dependency_overrides[account_repository_dependency] = lambda: accounts
    app.dependency_overrides[client_onboarding_repository_dependency] = lambda: onboarding
    return TestClient(app), onboarding


def _headers(*, include_device: bool = True) -> dict[str, str]:
    headers = {"Authorization": "Bearer eligibility-token"}
    if include_device:
        headers["X-Device-Id"] = DEVICE_ID
    return headers


@pytest.mark.parametrize("role", ["employee", "management"])
def test_authorized_staff_can_approve_normal_eligibility(role: str) -> None:
    client, onboarding = _client_for(
        role=role,
        permissions=("client_onboarding.requirement.review",),
    )

    response = client.post(
        f"/api/v1/management/onboarding/applicants/{APPLICANT_ID}/eligibility",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "eligible_for_cif",
        "client_id": str(CLIENT_ID),
    }
    assert onboarding.approval == {
        "actor_user_id": ACTOR_USER_ID,
        "applicant_id": APPLICANT_ID,
    }


@pytest.mark.parametrize("role", ["collector", "client"])
def test_other_roles_cannot_approve_normal_eligibility_even_with_permission(
    role: str,
) -> None:
    client, onboarding = _client_for(
        role=role,
        permissions=("client_onboarding.requirement.review",),
    )

    response = client.post(
        f"/api/v1/management/onboarding/applicants/{APPLICANT_ID}/eligibility",
        headers=_headers(),
    )

    assert response.status_code == 403
    assert onboarding.approval is None


def test_normal_eligibility_requires_review_permission() -> None:
    client, onboarding = _client_for(role="employee", permissions=())

    response = client.post(
        f"/api/v1/management/onboarding/applicants/{APPLICANT_ID}/eligibility",
        headers=_headers(),
    )

    assert response.status_code == 403
    assert onboarding.approval is None


def test_non_passed_requirements_return_conflict_without_client_identity() -> None:
    client, onboarding = _client_for(
        role="employee",
        permissions=("client_onboarding.requirement.review",),
        approval_status="under_verification",
        promoted_client_id=None,
    )

    response = client.post(
        f"/api/v1/management/onboarding/applicants/{APPLICANT_ID}/eligibility",
        headers=_headers(),
    )

    assert response.status_code == 409
    assert "four" in response.json()["detail"].lower()
    assert "client_id" not in response.json()
    assert onboarding.approval == {
        "actor_user_id": ACTOR_USER_ID,
        "applicant_id": APPLICANT_ID,
    }


def test_normal_eligibility_requires_active_device_context() -> None:
    client, onboarding = _client_for(
        role="employee",
        permissions=("client_onboarding.requirement.review",),
    )

    response = client.post(
        f"/api/v1/management/onboarding/applicants/{APPLICANT_ID}/eligibility",
        headers=_headers(include_device=False),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "X-Device-Id is required."
    assert onboarding.approval is None
