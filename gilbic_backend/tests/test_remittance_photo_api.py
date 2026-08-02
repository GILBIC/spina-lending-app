from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.remittance_photo_api import remittance_photo_repository_dependency
from gilbic_backend.remittance_photo_repository import (
    RemittancePhotoLocked,
    RemittancePhotoRecord,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
COLLECTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
REMITTANCE_ID = UUID("33333333-3333-4333-8333-333333333333")
PHOTO_ID = UUID("44444444-4444-4444-8444-444444444444")
UPLOADED_AT = datetime(2026, 8, 2, 8, tzinfo=timezone.utc)
JPEG_BYTES = b"\xff\xd8\xff\xe0test-photo"


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "collector-token"
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="collector@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def __init__(self, *, permissions: tuple[str, ...]) -> None:
        self.permissions = permissions

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == "device-one"
        return AccountContext(
            user_id=COLLECTOR_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username="collector.one",
            email="collector@example.com",
            full_name="Collector One",
            status="active",
            roles=("collector",),
            permissions=self.permissions,
            device_registered=True,
        )


class FakePhotos:
    def __init__(self) -> None:
        self.upload_request: dict[str, object] | None = None
        self.view_request: dict[str, object] | None = None
        self.error: Exception | None = None

    def upload(self, **kwargs) -> RemittancePhotoRecord:
        if self.error is not None:
            raise self.error
        self.upload_request = kwargs
        return RemittancePhotoRecord(
            photo_id=PHOTO_ID,
            remittance_id=REMITTANCE_ID,
            version=1,
            uploaded_by_user_id=COLLECTOR_USER_ID,
            original_filename="handover.jpg",
            content_type="image/jpeg",
            byte_size=len(JPEG_BYTES),
            sha256_hex="a" * 64,
            uploaded_at=UPLOADED_AT,
        )

    def latest_for_actor(self, **kwargs) -> RemittancePhotoRecord:
        self.view_request = kwargs
        return RemittancePhotoRecord(
            photo_id=PHOTO_ID,
            remittance_id=REMITTANCE_ID,
            version=1,
            uploaded_by_user_id=COLLECTOR_USER_ID,
            original_filename="handover.jpg",
            content_type="image/jpeg",
            byte_size=len(JPEG_BYTES),
            sha256_hex="a" * 64,
            uploaded_at=UPLOADED_AT,
            photo_data=JPEG_BYTES,
        )


def client_with_fakes(
    *,
    permissions: tuple[str, ...],
) -> tuple[TestClient, FakePhotos]:
    photos = FakePhotos()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        permissions=permissions
    )
    app.dependency_overrides[remittance_photo_repository_dependency] = lambda: photos
    return TestClient(app), photos


def headers(*, content_type: str | None = None) -> dict[str, str]:
    values = {
        "Authorization": "Bearer collector-token",
        "X-Device-Id": "device-one",
    }
    if content_type:
        values["Content-Type"] = content_type
    return values


def test_original_collector_can_upload_optional_handover_photo() -> None:
    client, photos = client_with_fakes(permissions=("remittance.create",))

    response = client.post(
        f"/api/mobile/v1/collector/remittances/{REMITTANCE_ID}/handover-photo",
        headers={
            **headers(content_type="image/jpeg"),
            "X-File-Name": "handover.jpg",
        },
        content=JPEG_BYTES,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["photo_id"] == str(PHOTO_ID)
    assert data["version"] == 1
    assert data["photo_url"].endswith(
        f"/remittances/{REMITTANCE_ID}/handover-photo"
    )
    assert photos.upload_request is not None
    assert photos.upload_request["actor_user_id"] == COLLECTOR_USER_ID
    assert photos.upload_request["photo_data"] == JPEG_BYTES


def test_collector_or_selected_recipient_can_view_private_photo() -> None:
    client, photos = client_with_fakes(permissions=("remittance.view",))

    response = client.get(
        f"/api/mobile/v1/remittances/{REMITTANCE_ID}/handover-photo",
        headers=headers(),
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/jpeg")
    assert response.headers["x-photo-version"] == "1"
    assert response.content == JPEG_BYTES
    assert photos.view_request == {
        "remittance_id": REMITTANCE_ID,
        "actor_user_id": COLLECTOR_USER_ID,
        "include_data": True,
    }


def test_photo_upload_is_rejected_after_recipient_acceptance() -> None:
    client, photos = client_with_fakes(permissions=("remittance.create",))
    photos.error = RemittancePhotoLocked(
        "The handover photo is locked after the recipient accepts the remittance."
    )

    response = client.post(
        f"/api/v1/collector/remittances/{REMITTANCE_ID}/handover-photo",
        headers=headers(content_type="image/jpeg"),
        content=JPEG_BYTES,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "remittance_photo_locked"
