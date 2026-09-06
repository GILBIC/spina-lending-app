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
DEVICE_ID = "bypass-device"


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
        assert access_token == "bypass-token"
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
    def __init__(self, *, succeeds: bool = True) -> None:
        self.succeeds = succeeds
        self.bypass: dict[str, object] | None = None

    def bypass_and_approve_eligibility(self, **payload: object):
        self.bypass = payload
        if self.succeeds:
            return SimpleNamespace(
                status="eligible_for_cif",
                promoted_client_id=CLIENT_ID,
            )
        return SimpleNamespace(
            status="under_verification",
            promoted_client_id=None,
        )


def _client_for(
    *,
    role: str,
    permissions: tuple[str, ...],
    succeeds: bool = True,
) -> tuple[TestClient, FakeOnboardingRepository]:
    auth = FakeAuthClient()
    accounts = FakeAccounts(_actor_context(role=role, permissions=permissions))
    onboarding = FakeOnboardingRepository(succeeds=succeeds)
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: auth
    app.dependency_overrides[account_repository_dependency] = lambda: accounts
    app.dependency_overrides[client_onboarding_repository_dependency] = lambda: onboarding
    return TestClient(app), onboarding


def _headers(*, include_device: bool = True) -> dict[str, str]:
    headers = {"Authorization": "Bearer bypass-token"}
    if include_device:
        headers["X-Device-Id"] = DEVICE_ID
    return headers


def _post_bypass(
    client: TestClient,
    *,
    bypassed_requirements: list[str],
    reason: str,
    include_device: bool = True,
):
    return client.post(
        f"/api/v1/management/onboarding/applicants/{APPLICANT_ID}/eligibility/bypass",
        headers=_headers(include_device=include_device),
        json={
            "bypassed_requirements": bypassed_requirements,
            "reason": reason,
        },
    )


def test_management_can_bypass_with_exact_requirements_and_normalized_reason() -> None:
    client, onboarding = _client_for(
        role="management",
        permissions=("client_onboarding.bypass",),
    )

    response = _post_bypass(
        client,
        bypassed_requirements=["tin_id", "national_id"],
        reason="  Approved   Management exception  ",
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "eligible_for_cif",
        "client_id": str(CLIENT_ID),
    }
    assert onboarding.bypass == {
        "actor_user_id": ACTOR_USER_ID,
        "applicant_id": APPLICANT_ID,
        "bypassed_requirements": ["national_id", "tin_id"],
        "reason": "Approved Management exception",
    }


@pytest.mark.parametrize("role", ["employee", "collector", "client"])
def test_non_management_roles_cannot_bypass_even_if_permission_is_present(role: str) -> None:
    client, onboarding = _client_for(
        role=role,
        permissions=("client_onboarding.bypass",),
    )

    response = _post_bypass(
        client,
        bypassed_requirements=["national_id"],
        reason="Approved exception",
    )

    assert response.status_code == 403
    assert onboarding.bypass is None


def test_employee_normal_review_permission_does_not_grant_bypass() -> None:
    client, onboarding = _client_for(
        role="employee",
        permissions=("client_onboarding.requirement.review",),
    )

    response = _post_bypass(
        client,
        bypassed_requirements=["national_id"],
        reason="Approved exception",
    )

    assert response.status_code == 403
    assert onboarding.bypass is None


def test_management_requires_bypass_permission() -> None:
    client, onboarding = _client_for(role="management", permissions=())

    response = _post_bypass(
        client,
        bypassed_requirements=["national_id"],
        reason="Approved exception",
    )

    assert response.status_code == 403
    assert onboarding.bypass is None


def test_bypass_requires_active_device_context() -> None:
    client, onboarding = _client_for(
        role="management",
        permissions=("client_onboarding.bypass",),
    )

    response = _post_bypass(
        client,
        bypassed_requirements=["national_id"],
        reason="Approved exception",
        include_device=False,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "X-Device-Id is required."
    assert onboarding.bypass is None


def test_whitespace_only_bypass_reason_is_rejected_before_repository_access() -> None:
    client, onboarding = _client_for(
        role="management",
        permissions=("client_onboarding.bypass",),
    )

    response = _post_bypass(
        client,
        bypassed_requirements=["national_id"],
        reason="   ",
    )

    assert response.status_code == 422
    assert onboarding.bypass is None


def test_duplicate_bypass_names_are_collapsed_to_one_sorted_set() -> None:
    client, onboarding = _client_for(
        role="management",
        permissions=("client_onboarding.bypass",),
    )

    response = _post_bypass(
        client,
        bypassed_requirements=["tin_id", "tin_id", "national_id"],
        reason="Approved exception",
    )

    assert response.status_code == 200
    assert onboarding.bypass is not None
    assert onboarding.bypass["bypassed_requirements"] == ["national_id", "tin_id"]


def test_bypass_set_mismatch_returns_conflict_without_client_identity() -> None:
    client, onboarding = _client_for(
        role="management",
        permissions=("client_onboarding.bypass",),
        succeeds=False,
    )

    response = _post_bypass(
        client,
        bypassed_requirements=["national_id"],
        reason="Approved exception",
    )

    assert response.status_code == 409
    detail = response.json()["detail"].lower()
    assert "exact" in detail
    assert "normal eligibility" in detail
    assert "client_id" not in response.json()
    assert onboarding.bypass is not None


def test_all_passed_applicant_is_directed_to_normal_eligibility() -> None:
    client, onboarding = _client_for(
        role="management",
        permissions=("client_onboarding.bypass",),
        succeeds=False,
    )

    response = _post_bypass(
        client,
        bypassed_requirements=["collector_visit"],
        reason="Approved exception",
    )

    assert response.status_code == 409
    assert "normal eligibility" in response.json()["detail"].lower()
    assert onboarding.bypass is not None
