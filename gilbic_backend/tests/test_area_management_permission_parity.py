from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.area_management_api import area_management_repository_dependency
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
DEVICE_IDENTIFIER = "spina-area-permission-device"


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "area-token"
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="staff@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def __init__(self, permissions: tuple[str, ...]) -> None:
        self.context = AccountContext(
            user_id=ACTOR_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username="employee.one",
            email="employee@example.com",
            full_name="Employee One",
            status="active",
            roles=("employee",),
            permissions=permissions,
            device_registered=True,
        )

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == DEVICE_IDENTIFIER
        return self.context


class FakeAreaRepository:
    def list_tree(self, *, include_inactive: bool = False):
        return ()

    def list_collectors(self):
        return ()

    def search_clients(self, query: str, *, limit: int = 20):
        return ()


def client_for(permissions: tuple[str, ...]) -> TestClient:
    app = create_app()
    accounts = FakeAccounts(permissions)
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: accounts
    app.dependency_overrides[area_management_repository_dependency] = (
        lambda: FakeAreaRepository()
    )
    return TestClient(app)


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer area-token",
        "X-Device-Id": DEVICE_IDENTIFIER,
    }


@pytest.mark.parametrize(
    "permission",
    ["area.collector.assign", "area.client.assign", "area.retire"],
)
def test_area_tree_read_is_available_to_any_area_permission(permission: str) -> None:
    response = client_for((permission,)).get("/api/v1/areas", headers=headers())

    assert response.status_code == 200


def test_area_tree_read_still_denies_staff_without_an_area_permission() -> None:
    response = client_for(()).get("/api/v1/areas", headers=headers())

    assert response.status_code == 403


def test_collector_choices_require_exact_collector_assignment_permission() -> None:
    response = client_for(("area.collector.assign",)).get(
        "/api/v1/areas/collectors",
        headers=headers(),
    )

    assert response.status_code == 200


def test_area_manage_alone_does_not_grant_collector_choices() -> None:
    response = client_for(("area.manage",)).get(
        "/api/v1/areas/collectors",
        headers=headers(),
    )

    assert response.status_code == 403


def test_client_search_requires_exact_client_assignment_permission() -> None:
    response = client_for(("area.client.assign",)).get(
        "/api/v1/areas/clients?q=Maria",
        headers=headers(),
    )

    assert response.status_code == 200


def test_area_manage_alone_does_not_grant_client_search() -> None:
    response = client_for(("area.manage",)).get(
        "/api/v1/areas/clients?q=Maria",
        headers=headers(),
    )

    assert response.status_code == 403
