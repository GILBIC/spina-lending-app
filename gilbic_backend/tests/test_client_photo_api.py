from dataclasses import replace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from gilbic_backend.account_repository import AccountContext, DeviceRevoked
from gilbic_backend.auth_api import (
    account_repository_dependency,
    auth_client_dependency,
)
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.client_photo_api import (
    client_photo_repository_dependency,
    create_client_photo_router,
)
from gilbic_backend.client_photo_repository import (
    ClientPhotoConflict,
    ClientPhotoNotFound,
)
from test_client_photo import picture

CLIENT = UUID("11111111-1111-4111-8111-111111111111")
USER = UUID("22222222-2222-4222-8222-222222222222")
REQUEST = UUID("33333333-3333-4333-8333-333333333333")
PHOTO = UUID("44444444-4444-4444-8444-444444444444")
HEADERS = {"Authorization": "Bearer synthetic", "X-Device-Id": "synthetic-device"}
ACTOR = AccountContext(
    user_id=USER,
    auth_user_id=USER,
    username="synthetic",
    email="synthetic@example.test",
    full_name="Synthetic",
    status="active",
    roles=("employee",),
    permissions=("client_onboarding.requirement.review",),
    device_registered=True,
)


class Auth:
    def get_user(self, *, access_token):
        assert access_token == "synthetic"
        return AuthSession(
            auth_user_id=USER,
            email="synthetic@example.test",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class Accounts:
    actor = ACTOR
    error = None

    def get_context_for_device(self, **kwargs):
        if self.error:
            raise self.error
        assert kwargs == {"auth_user_id": USER, "device_identifier": "synthetic-device"}
        return self.actor


class Photos:
    calls = None
    error = None

    def _record(self, values):
        self.calls = values
        if self.error:
            raise self.error

    def get(self, **kwargs):
        self._record(kwargs)
        return {"client_id": str(CLIENT), "can_upload": True, "photo": None}

    def upload(self, **kwargs):
        self._record(kwargs)
        return {
            "client_id": str(CLIENT),
            "can_upload": True,
            "photo": {
                "photo_id": str(PHOTO),
                "version": 1,
                "content_type": "image/jpeg",
                "byte_size": len(kwargs["prepared"].content),
                "uploaded_at": "2026-10-10T01:00:00Z",
                "uploaded_by_user_id": str(USER),
                "content_url": f"/api/v1/clients/{CLIENT}/photo/content?photo_id={PHOTO}",
            },
        }

    def content(self, **kwargs):
        self._record(kwargs)
        return picture("JPEG"), "image/jpeg"


@pytest.fixture
def setup():
    app = FastAPI()
    app.include_router(create_client_photo_router())
    accounts, photos = Accounts(), Photos()
    app.dependency_overrides[auth_client_dependency] = lambda: Auth()
    app.dependency_overrides[account_repository_dependency] = lambda: accounts
    app.dependency_overrides[client_photo_repository_dependency] = lambda: photos
    with TestClient(app) as client:
        yield client, accounts, photos


@pytest.mark.parametrize("prefix", ["/api/v1", "/api/mobile/v1"])
def test_missing_photo_is_nonblocking_and_private(setup, prefix):
    client, _, photos = setup
    response = client.get(f"{prefix}/clients/{CLIENT}/photo", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["data"]["photo"] is None
    assert response.headers["cache-control"] == "no-store"
    assert photos.calls == {"actor": ACTOR, "client_id": CLIENT}


def test_upload_normalizes_image_and_preserves_exact_retry_identity(setup):
    client, _, photos = setup
    data = picture()
    response = client.post(
        f"/api/v1/clients/{CLIENT}/photo?request_id={REQUEST}&expected_version=0",
        headers={**HEADERS, "Content-Type": "image/png"},
        content=data,
    )
    assert response.status_code == 200
    assert response.json()["data"]["photo"]["version"] == 1
    assert response.headers["cache-control"] == "no-store"
    assert photos.calls["request_id"] == REQUEST
    assert photos.calls["expected_version"] == 0
    assert photos.calls["prepared"].content != data
    assert photos.calls["prepared"].content_type == "image/jpeg"


@pytest.mark.parametrize(
    "roles,permissions",
    [
        (("collector",), ("route.view",)),
        (("client",), ()),
        (("management",), ()),
        (("employee",), ()),
    ],
)
def test_only_authorized_office_can_upload(setup, roles, permissions):
    client, accounts, photos = setup
    accounts.actor = replace(ACTOR, roles=roles, permissions=permissions)
    response = client.post(
        f"/api/v1/clients/{CLIENT}/photo?request_id={REQUEST}&expected_version=0",
        headers={**HEADERS, "Content-Type": "image/png"},
        content=picture(),
    )
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert photos.calls is None


@pytest.mark.parametrize(
    "content,kind,status",
    [
        (b"bad", "image/jpeg", 400),
        (picture(), "image/svg+xml", 415),
        (b"x" * (5 * 1024 * 1024 + 1), "image/png", 413),
    ],
    ids=["corrupt", "unsupported", "too-large"],
)
def test_invalid_upload_never_reaches_storage(setup, content, kind, status):
    client, _, photos = setup
    response = client.post(
        f"/api/v1/clients/{CLIENT}/photo?request_id={REQUEST}&expected_version=0",
        headers={**HEADERS, "Content-Type": kind},
        content=content,
    )
    assert response.status_code == status
    assert photos.calls is None
    assert response.headers["cache-control"] == "no-store"


def test_private_download_uses_actor_and_exact_photo_identity(setup):
    client, _, photos = setup
    response = client.get(
        f"/api/v1/clients/{CLIENT}/photo/content?photo_id={PHOTO}", headers=HEADERS
    )
    assert response.status_code == 200
    assert response.content == picture("JPEG")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert photos.calls == {"actor": ACTOR, "client_id": CLIENT, "photo_id": PHOTO}


@pytest.mark.parametrize(
    "error,status",
    [
        (ClientPhotoNotFound("Photo unavailable."), 404),
        (ClientPhotoConflict("Refresh the client photo."), 409),
    ],
)
def test_access_and_conflict_errors_are_private(setup, error, status):
    client, _, photos = setup
    photos.error = error
    response = client.get(f"/api/v1/clients/{CLIENT}/photo", headers=HEADERS)
    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"


def test_revoked_device_never_reads_photo(setup):
    client, accounts, photos = setup
    accounts.error = DeviceRevoked("Revoked")
    response = client.get(f"/api/v1/clients/{CLIENT}/photo", headers=HEADERS)
    assert response.status_code == 403
    assert photos.calls is None


def test_invalid_client_path_does_not_echo_input(setup):
    client, _, _ = setup
    response = client.get("/api/v1/clients/private-name/photo", headers=HEADERS)
    assert response.status_code == 422
    assert "private-name" not in response.text
    assert response.headers["cache-control"] == "no-store"
