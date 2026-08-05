from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.management_api import (
    management_account_repository_dependency,
    management_auth_client_dependency,
    management_repository_dependency,
)
from gilbic_backend.management_repository import (
    ClientLinkCandidate,
    ClientRegistrationRecord,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
TARGET_USER_ID = UUID("33333333-3333-4333-8333-333333333333")
CLIENT_ID = UUID("44444444-4444-4444-8444-444444444444")
NOW = datetime(2026, 8, 5, 5, 0, tzinfo=UTC)
DEVICE_ID = "management-device"


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "management-token"
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="manager@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == DEVICE_ID
        return AccountContext(
            user_id=ACTOR_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username="manager.one",
            email="manager@example.com",
            full_name="Manager One",
            status="active",
            roles=("management",),
            permissions=("account.manage", "management.dashboard.view"),
            device_registered=True,
        )


def registration(*, status: str = "pending") -> ClientRegistrationRecord:
    return ClientRegistrationRecord(
        user_id=TARGET_USER_ID,
        username="client.one",
        email="client@example.com",
        full_name="Client One",
        account_status="pending" if status == "pending" else "active",
        claimed_client_code="CLIENT-001",
        claimed_phone_number="09171234567",
        registration_status=status,
        linked_client_id=CLIENT_ID if status == "approved" else None,
        linked_client_code="CLIENT-001" if status == "approved" else None,
        linked_client_name="Client One" if status == "approved" else None,
        review_note="",
        submitted_at=NOW,
        reviewed_at=NOW if status != "pending" else None,
    )


class FakeManagementRepository:
    def __init__(self) -> None:
        self.approved: tuple[UUID, UUID, UUID, str] | None = None
        self.rejected: tuple[UUID, UUID, str] | None = None

    def list_client_registrations(
        self,
        *,
        registration_status: str,
        limit: int,
        offset: int,
    ):
        assert registration_status == "pending"
        assert limit == 100
        assert offset == 0
        return [registration()]

    def search_client_link_candidates(self, *, query: str, limit: int):
        assert query == "CLIENT-001"
        assert limit == 25
        return [
            ClientLinkCandidate(
                id=CLIENT_ID,
                client_code="CLIENT-001",
                full_name="Client One",
                phone_number="09171234567",
                area="TEST AREA",
                status="active",
            )
        ]

    def approve_client_registration(
        self,
        *,
        actor_user_id: UUID,
        target_user_id: UUID,
        client_id: UUID,
        review_note: str,
    ):
        self.approved = (
            actor_user_id,
            target_user_id,
            client_id,
            review_note,
        )
        return registration(status="approved")

    def reject_client_registration(
        self,
        *,
        actor_user_id: UUID,
        target_user_id: UUID,
        review_note: str,
    ):
        self.rejected = (actor_user_id, target_user_id, review_note)
        return registration(status="rejected")


def client_with_fakes():
    management = FakeManagementRepository()
    app = create_app()
    app.dependency_overrides[management_auth_client_dependency] = (
        lambda: FakeAuthClient()
    )
    app.dependency_overrides[management_account_repository_dependency] = (
        lambda: FakeAccounts()
    )
    app.dependency_overrides[management_repository_dependency] = lambda: management
    return TestClient(app), management


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer management-token",
        "X-Device-Id": DEVICE_ID,
    }


def test_management_lists_pending_client_registrations() -> None:
    client, _ = client_with_fakes()

    response = client.get(
        "/api/v1/management/client-registrations",
        headers=headers(),
    )

    assert response.status_code == 200
    item = response.json()["data"]["registrations"][0]
    assert item["full_name"] == "Client One"
    assert item["claimed_client_code"] == "CLIENT-001"
    assert item["registration_status"] == "pending"


def test_management_searches_only_link_candidates() -> None:
    client, _ = client_with_fakes()

    response = client.get(
        "/api/v1/management/client-link-candidates?q=CLIENT-001",
        headers=headers(),
    )

    assert response.status_code == 200
    item = response.json()["data"]["clients"][0]
    assert item["id"] == str(CLIENT_ID)
    assert item["client_code"] == "CLIENT-001"
    assert item["area"] == "TEST AREA"


def test_management_approves_and_links_client_registration() -> None:
    client, management = client_with_fakes()

    response = client.post(
        f"/api/v1/management/client-registrations/{TARGET_USER_ID}/approve",
        headers=headers(),
        json={"client_id": str(CLIENT_ID), "review_note": "Verified"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["registration"]["registration_status"] == (
        "approved"
    )
    assert management.approved == (
        ACTOR_USER_ID,
        TARGET_USER_ID,
        CLIENT_ID,
        "Verified",
    )


def test_management_rejects_client_registration_with_reason() -> None:
    client, management = client_with_fakes()

    response = client.post(
        f"/api/v1/management/client-registrations/{TARGET_USER_ID}/reject",
        headers=headers(),
        json={"review_note": "Client code could not be verified."},
    )

    assert response.status_code == 200
    assert response.json()["data"]["registration"]["registration_status"] == (
        "rejected"
    )
    assert management.rejected == (
        ACTOR_USER_ID,
        TARGET_USER_ID,
        "Client code could not be verified.",
    )
