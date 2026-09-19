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
DEVICE_ID = "onboarding-device"


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
        assert access_token == "onboarding-token"
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
        self.document_review: dict[str, object] | None = None
        self.collector_visit: dict[str, object] | None = None

    def review_document_requirements(self, **payload: object):
        self.document_review = payload
        return SimpleNamespace(status="under_verification")

    def record_collector_visit(self, **payload: object):
        self.collector_visit = payload
        return SimpleNamespace(status="under_verification")


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
    headers = {"Authorization": "Bearer onboarding-token"}
    if include_device:
        headers["X-Device-Id"] = DEVICE_ID
    return headers


def _document_body() -> dict[str, str]:
    return {
        "national_id_status": "passed",
        "tin_id_status": "passed",
        "meralco_bill_status": "passed",
    }


def test_employee_with_permission_can_review_document_requirements() -> None:
    client, onboarding = _client_for(
        role="employee",
        permissions=("client_onboarding.requirement.review",),
    )

    response = client.patch(
        f"/api/v1/management/onboarding/applicants/{APPLICANT_ID}/document-requirements",
        headers=_headers(),
        json=_document_body(),
    )

    assert response.status_code == 200
    assert onboarding.document_review == {
        "actor_user_id": ACTOR_USER_ID,
        "applicant_id": APPLICANT_ID,
        "national_id_status": "passed",
        "tin_id_status": "passed",
        "meralco_bill_status": "passed",
    }


def test_management_with_permission_can_review_document_requirements() -> None:
    client, onboarding = _client_for(
        role="management",
        permissions=("client_onboarding.requirement.review",),
    )

    response = client.patch(
        f"/api/v1/management/onboarding/applicants/{APPLICANT_ID}/document-requirements",
        headers=_headers(),
        json={
            "national_id_status": "failed",
            "tin_id_status": "passed",
            "meralco_bill_status": "passed",
        },
    )

    assert response.status_code == 200
    assert onboarding.document_review is not None
    assert onboarding.document_review["actor_user_id"] == ACTOR_USER_ID
    assert onboarding.document_review["national_id_status"] == "failed"


@pytest.mark.parametrize("role", ["collector", "client"])
def test_other_roles_cannot_review_documents_even_with_permission(role: str) -> None:
    client, onboarding = _client_for(
        role=role,
        permissions=("client_onboarding.requirement.review",),
    )

    response = client.patch(
        f"/api/v1/management/onboarding/applicants/{APPLICANT_ID}/document-requirements",
        headers=_headers(),
        json=_document_body(),
    )

    assert response.status_code == 403
    assert onboarding.document_review is None


def test_document_review_requires_permission() -> None:
    client, onboarding = _client_for(role="employee", permissions=())

    response = client.patch(
        f"/api/v1/management/onboarding/applicants/{APPLICANT_ID}/document-requirements",
        headers=_headers(),
        json=_document_body(),
    )

    assert response.status_code == 403
    assert onboarding.document_review is None


def test_collector_with_permission_can_record_residence_visit() -> None:
    client, onboarding = _client_for(
        role="collector",
        permissions=("client_onboarding.visit.record",),
    )

    response = client.post(
        f"/api/v1/collector/onboarding/applicants/{APPLICANT_ID}/visit",
        headers=_headers(),
        json={
            "result": "passed",
            "note": "Residence confirmed",
            "evidence_reference": "FAKE-COLLECTOR-VISIT-EVIDENCE",
        },
    )

    assert response.status_code == 200
    assert onboarding.collector_visit == {
        "actor_user_id": ACTOR_USER_ID,
        "applicant_id": APPLICANT_ID,
        "result": "passed",
        "note": "Residence confirmed",
        "evidence_reference": "FAKE-COLLECTOR-VISIT-EVIDENCE",
    }


@pytest.mark.parametrize("role", ["employee", "management", "client"])
def test_other_roles_cannot_record_collector_visit_even_with_permission(role: str) -> None:
    client, onboarding = _client_for(
        role=role,
        permissions=("client_onboarding.visit.record",),
    )

    response = client.post(
        f"/api/v1/collector/onboarding/applicants/{APPLICANT_ID}/visit",
        headers=_headers(),
        json={"result": "passed", "note": "Residence confirmed"},
    )

    assert response.status_code == 403
    assert onboarding.collector_visit is None


def test_collector_visit_requires_permission() -> None:
    client, onboarding = _client_for(role="collector", permissions=())

    response = client.post(
        f"/api/v1/collector/onboarding/applicants/{APPLICANT_ID}/visit",
        headers=_headers(),
        json={"result": "passed", "note": "Residence confirmed"},
    )

    assert response.status_code == 403
    assert onboarding.collector_visit is None


@pytest.mark.parametrize(
    ("role", "permission", "method", "path", "payload"),
    [
        (
            "employee",
            "client_onboarding.requirement.review",
            "PATCH",
            f"/api/v1/management/onboarding/applicants/{APPLICANT_ID}/document-requirements",
            _document_body(),
        ),
        (
            "collector",
            "client_onboarding.visit.record",
            "POST",
            f"/api/v1/collector/onboarding/applicants/{APPLICANT_ID}/visit",
            {"result": "passed", "note": "Residence confirmed"},
        ),
    ],
)
def test_protected_onboarding_routes_require_active_device_context(
    role: str,
    permission: str,
    method: str,
    path: str,
    payload: dict[str, str],
) -> None:
    client, onboarding = _client_for(role=role, permissions=(permission,))

    response = client.request(
        method,
        path,
        headers=_headers(include_device=False),
        json=payload,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "X-Device-Id is required."
    assert onboarding.document_review is None
    assert onboarding.collector_visit is None
