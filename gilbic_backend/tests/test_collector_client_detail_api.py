from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.collector_client_detail_api import (
    collector_client_detail_repository_dependency,
)
from gilbic_backend.collector_client_detail_repository import CollectorClientDetailRecord
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
OWNER_COLLECTOR_ID = UUID("22222222-2222-4222-8222-222222222222")
OVERRIDDEN_PARENT_ID = UUID("33333333-3333-4333-8333-333333333333")
DELEGATED_COLLECTOR_ID = UUID("44444444-4444-4444-8444-444444444444")
UNRELATED_COLLECTOR_ID = UUID("55555555-5555-4555-8555-555555555555")
CLIENT_ID = UUID("66666666-6666-4666-8666-666666666666")


def collector_context(
    user_id: UUID,
    *,
    permissions: tuple[str, ...] = ("route.view",),
) -> AccountContext:
    return AccountContext(
        user_id=user_id,
        auth_user_id=AUTH_USER_ID,
        username="collector.location",
        email="collector.location@example.com",
        full_name="Collector Location",
        status="active",
        roles=("collector",),
        permissions=permissions,
        device_registered=True,
    )


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "collector-location-token"
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="collector.location@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def __init__(self, user_id: UUID, *, permissions: tuple[str, ...] = ("route.view",)) -> None:
        self.context = collector_context(user_id, permissions=permissions)
        self.seen_device: str | None = None

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        self.seen_device = device_identifier
        return self.context


class FakeClientDetails:
    def __init__(self) -> None:
        self.request: tuple[UUID, UUID] | None = None
        self.verified = CollectorClientDetailRecord(
            client_id=CLIENT_ID,
            collection_location_status="verified",
            display_address="12 Mabini Street, Calahan, Cardona, Rizal",
            landmark="Beside Calahan Barangay Hall",
            photo_url="https://example.invalid/collection-location.jpg",
            verified_at=datetime(2026, 9, 1, 3, 15, tzinfo=UTC),
        )

    def get_collection_location(
        self,
        *,
        collector_user_id: UUID,
        client_id: UUID,
    ) -> CollectorClientDetailRecord | None:
        self.request = (collector_user_id, client_id)
        if client_id != CLIENT_ID:
            return None
        if collector_user_id in (OWNER_COLLECTOR_ID, DELEGATED_COLLECTOR_ID):
            return self.verified
        return None


def client_with_fakes(
    collector_user_id: UUID,
    *,
    permissions: tuple[str, ...] = ("route.view",),
) -> tuple[TestClient, FakeAccounts, FakeClientDetails]:
    auth = FakeAuthClient()
    accounts = FakeAccounts(collector_user_id, permissions=permissions)
    details = FakeClientDetails()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: auth
    app.dependency_overrides[account_repository_dependency] = lambda: accounts
    app.dependency_overrides[collector_client_detail_repository_dependency] = lambda: details
    return TestClient(app), accounts, details


def request_headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer collector-location-token",
        "X-Device-Id": "collector-location-device",
    }


def test_effective_owner_reads_only_approved_verified_collection_location() -> None:
    client, accounts, details = client_with_fakes(OWNER_COLLECTOR_ID)

    response = client.get(
        f"/api/mobile/v1/collector/clients/{CLIENT_ID}/collection-location",
        headers=request_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "client_id": str(CLIENT_ID),
            "collection_location_status": "verified",
            "display_address": "12 Mabini Street, Calahan, Cardona, Rizal",
            "landmark": "Beside Calahan Barangay Hall",
            "photo_url": "https://example.invalid/collection-location.jpg",
            "verified_at": "2026-09-01T03:15:00+00:00",
        },
    }
    data = response.json()["data"]
    forbidden = {
        "national_id",
        "national_id_egov_evidence_reference",
        "tin_id",
        "tin_id_egov_evidence_reference",
        "meralco_bill",
        "meralco_bill_evidence_reference",
        "present_address",
        "latitude",
        "longitude",
    }
    assert forbidden.isdisjoint(data)
    assert accounts.seen_device == "collector-location-device"
    assert details.request == (OWNER_COLLECTOR_ID, CLIENT_ID)


def test_overridden_parent_collector_cannot_probe_child_client_location() -> None:
    client, _, details = client_with_fakes(OVERRIDDEN_PARENT_ID)

    response = client.get(
        f"/api/mobile/v1/collector/clients/{CLIENT_ID}/collection-location",
        headers=request_headers(),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Collection location is not available for this route."
    assert details.request == (OVERRIDDEN_PARENT_ID, CLIENT_ID)


def test_valid_delegated_collector_may_read_same_route_scoped_detail() -> None:
    client, _, details = client_with_fakes(DELEGATED_COLLECTOR_ID)

    response = client.get(
        f"/api/mobile/v1/collector/clients/{CLIENT_ID}/collection-location",
        headers=request_headers(),
    )

    assert response.status_code == 200
    assert response.json()["data"]["collection_location_status"] == "verified"
    assert details.request == (DELEGATED_COLLECTOR_ID, CLIENT_ID)


def test_unrelated_collector_gets_same_non_disclosing_not_found_response() -> None:
    client, _, details = client_with_fakes(UNRELATED_COLLECTOR_ID)

    response = client.get(
        f"/api/mobile/v1/collector/clients/{CLIENT_ID}/collection-location",
        headers=request_headers(),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Collection location is not available for this route."
    assert details.request == (UNRELATED_COLLECTOR_ID, CLIENT_ID)


def test_not_verified_payload_has_no_invented_address_or_photo() -> None:
    client, _, details = client_with_fakes(OWNER_COLLECTOR_ID)
    details.verified = CollectorClientDetailRecord(
        client_id=CLIENT_ID,
        collection_location_status="not_verified",
        display_address=None,
        landmark=None,
        photo_url=None,
        verified_at=None,
    )

    response = client.get(
        f"/api/mobile/v1/collector/clients/{CLIENT_ID}/collection-location",
        headers=request_headers(),
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "client_id": str(CLIENT_ID),
        "collection_location_status": "not_verified",
        "display_address": None,
        "landmark": None,
        "photo_url": None,
        "verified_at": None,
    }


def test_collection_location_requires_route_view_permission() -> None:
    client, _, details = client_with_fakes(
        OWNER_COLLECTOR_ID,
        permissions=("collection.create",),
    )

    response = client.get(
        f"/api/mobile/v1/collector/clients/{CLIENT_ID}/collection-location",
        headers=request_headers(),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Collector route permission is required."
    assert details.request is None
