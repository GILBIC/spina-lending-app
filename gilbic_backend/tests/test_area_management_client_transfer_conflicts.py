from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.area_management_api import (
    area_management_repository_dependency,
    area_staff_context,
    create_area_management_router,
)


ACTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
CLIENT_ID = UUID("66666666-6666-4666-8666-666666666666")
TARGET_AREA_ID = UUID("44444444-4444-4444-8444-444444444444")


class ConflictRepository:
    def __init__(self, conflict_code: str) -> None:
        self.conflict_code = conflict_code

    def preview_client_transfer(
        self,
        *,
        client_id: UUID,
        target_area_uid: UUID,
        as_of_date: date,
    ):
        assert client_id == CLIENT_ID
        assert target_area_uid == TARGET_AREA_ID
        assert isinstance(as_of_date, date)
        raise ValueError(self.conflict_code)


def _actor() -> AccountContext:
    return AccountContext(
        user_id=ACTOR_USER_ID,
        auth_user_id=AUTH_USER_ID,
        username="employee.one",
        email="employee@example.com",
        full_name="Employee One",
        status="active",
        roles=("employee",),
        permissions=("area.client.assign",),
        device_registered=True,
    )


def _client(conflict_code: str) -> TestClient:
    app = FastAPI()
    app.include_router(create_area_management_router())
    repository = ConflictRepository(conflict_code)
    app.dependency_overrides[area_staff_context] = _actor
    app.dependency_overrides[area_management_repository_dependency] = lambda: repository
    return TestClient(app)


def test_client_transfer_preview_preserves_next_collection_day_unavailable_code() -> None:
    client = _client("client_transfer_next_collection_day_unavailable")

    response = client.get(
        f"/api/v1/clients/{CLIENT_ID}/area-transfer-preview",
        params={"target_area_id": str(TARGET_AREA_ID)},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "client_transfer_next_collection_day_unavailable"
    assert "next scheduled collection day" in detail["message"].lower()
    assert "guess" not in detail["message"].lower()


def test_unknown_client_transfer_conflict_stays_generic_and_does_not_leak_raw_value_error() -> None:
    raw_error = "duplicate key value violates internal constraint"
    client = _client(raw_error)

    response = client.get(
        f"/api/v1/clients/{CLIENT_ID}/area-transfer-preview",
        params={"target_area_id": str(TARGET_AREA_ID)},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "area_conflict"
    assert raw_error.lower() not in str(detail).lower()
