from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from gilbic_backend.account_repository import (
    AccountContext,
    DeviceNotRegistered,
    DeviceRevoked,
)
from gilbic_backend.area_management_api import (
    area_management_repository_dependency,
    create_area_management_router,
)
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
AREA_ID = UUID("33333333-3333-4333-8333-333333333333")
OTHER_AREA_ID = UUID("44444444-4444-4444-8444-444444444444")
COLLECTOR_ID = UUID("55555555-5555-4555-8555-555555555555")
CLIENT_ID = UUID("66666666-6666-4666-8666-666666666666")
DEVICE_IDENTIFIER = "spina-area-device"


def account_context(
    *,
    role: str = "employee",
    permissions: tuple[str, ...] = ("area.manage",),
) -> AccountContext:
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
    def __init__(self) -> None:
        self.context = account_context()
        self.device_error: Exception | None = None
        self.checked_device: str | None = None

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        self.checked_device = device_identifier
        if self.device_error is not None:
            raise self.device_error
        return self.context


@dataclass
class FakeAreaRepository:
    created_name: str | None = None
    retired: UUID | None = None
    reactivated: UUID | None = None
    assigned: tuple[UUID, UUID] | None = None
    conflict: Exception | None = None

    def list_tree(self, *, include_inactive: bool = False):
        return ()

    def list_collectors(self):
        return ()

    def search_clients(self, query: str, *, limit: int = 20):
        return ()

    def create_area(
        self,
        *,
        actor_user_id: UUID,
        parent_area_uid: UUID | None,
        name: str,
    ) -> UUID:
        assert actor_user_id == ACTOR_USER_ID
        assert parent_area_uid is None
        if self.conflict is not None:
            raise self.conflict
        self.created_name = name
        return AREA_ID

    def rename_area(self, *, actor_user_id: UUID, area_uid: UUID, name: str) -> UUID:
        assert actor_user_id == ACTOR_USER_ID
        assert area_uid == AREA_ID
        self.created_name = name
        return area_uid

    def preview_move(self, *, area_uid: UUID, new_parent_area_uid: UUID | None):
        return SimpleNamespace(
            area_uid=area_uid,
            old_parent_area_uid=None,
            new_parent_area_uid=new_parent_area_uid,
            old_path="Cardona",
            new_path="Rizal › Cardona",
            affected_node_count=1,
        )

    def move_area(
        self,
        *,
        actor_user_id: UUID,
        area_uid: UUID,
        new_parent_area_uid: UUID | None,
    ):
        return self.preview_move(
            area_uid=area_uid,
            new_parent_area_uid=new_parent_area_uid,
        )

    def reorder_siblings(
        self,
        *,
        actor_user_id: UUID,
        parent_area_uid: UUID | None,
        ordered_area_uids: tuple[UUID, ...],
    ):
        assert actor_user_id == ACTOR_USER_ID
        return ordered_area_uids

    def assign_collector(
        self,
        *,
        actor_user_id: UUID,
        area_uid: UUID,
        collector_user_id: UUID,
    ) -> UUID:
        assert actor_user_id == ACTOR_USER_ID
        self.assigned = (area_uid, collector_user_id)
        return collector_user_id

    def remove_collector_assignment(
        self,
        *,
        actor_user_id: UUID,
        area_uid: UUID,
    ) -> UUID:
        assert actor_user_id == ACTOR_USER_ID
        return COLLECTOR_ID

    def preview_client_transfer(
        self,
        *,
        client_id: UUID,
        target_area_uid: UUID,
        as_of_date,
    ):
        return SimpleNamespace(
            client_id=client_id,
            old_area_uid=AREA_ID,
            old_area_path="Cardona",
            new_area_uid=target_area_uid,
            new_area_path="Rizal › Cardona",
            old_effective_collector_user_id=COLLECTOR_ID,
            new_effective_collector_user_id=COLLECTOR_ID,
            effective_date=as_of_date,
            timing="immediate",
        )

    def schedule_client_transfer(
        self,
        *,
        actor_user_id: UUID,
        client_id: UUID,
        target_area_uid: UUID,
        as_of_date,
    ):
        return self.preview_client_transfer(
            client_id=client_id,
            target_area_uid=target_area_uid,
            as_of_date=as_of_date,
        )

    def preview_retirement(self, *, area_uid: UUID):
        return SimpleNamespace(
            area_uid=area_uid,
            full_path="Cardona",
            is_active=True,
            active_direct_client_count=0,
            active_subtree_client_count=0,
            active_collector_assignment_count=0,
            pending_transfer_target_count=0,
            descendant_count=0,
            active_descendant_count=0,
        )

    def retire_area(self, *, actor_user_id: UUID, area_uid: UUID) -> UUID:
        assert actor_user_id == ACTOR_USER_ID
        self.retired = area_uid
        return area_uid

    def reactivate_area(self, *, actor_user_id: UUID, area_uid: UUID) -> UUID:
        assert actor_user_id == ACTOR_USER_ID
        self.reactivated = area_uid
        return area_uid


def client_with_fakes():
    auth = FakeAuthClient()
    accounts = FakeAccounts()
    repository = FakeAreaRepository()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: auth
    app.dependency_overrides[account_repository_dependency] = lambda: accounts
    app.dependency_overrides[area_management_repository_dependency] = lambda: repository
    return TestClient(app), accounts, repository


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer area-token",
        "X-Device-Id": DEVICE_IDENTIFIER,
    }


def test_area_management_router_exposes_the_approved_plan1_surface_once() -> None:
    router = create_area_management_router()
    routes = {
        (method, route.path)
        for route in router.routes
        for method in (getattr(route, "methods", None) or ())
    }
    expected = {
        ("GET", "/api/v1/areas"),
        ("GET", "/api/v1/areas/collectors"),
        ("GET", "/api/v1/areas/clients"),
        ("GET", "/api/v1/areas/{area_id}/move-preview"),
        ("GET", "/api/v1/areas/{area_id}/retirement-preview"),
        ("GET", "/api/v1/clients/{client_id}/area-transfer-preview"),
        ("POST", "/api/v1/areas"),
        ("PATCH", "/api/v1/areas/{area_id}"),
        ("POST", "/api/v1/areas/{area_id}/move"),
        ("POST", "/api/v1/areas/reorder"),
        ("PUT", "/api/v1/areas/{area_id}/collector"),
        ("DELETE", "/api/v1/areas/{area_id}/collector"),
        ("POST", "/api/v1/clients/{client_id}/area-transfer"),
        ("POST", "/api/v1/areas/{area_id}/retire"),
        ("POST", "/api/v1/areas/{area_id}/reactivate"),
    }
    assert expected <= routes
    for method, path in expected:
        assert sum(
            1
            for route in router.routes
            if route.path == path
            and method in (getattr(route, "methods", None) or set())
        ) == 1


def test_area_management_requires_device_header_and_rejects_invalid_devices() -> None:
    client, accounts, _ = client_with_fakes()

    missing = client.get(
        "/api/v1/areas",
        headers={"Authorization": "Bearer area-token"},
    )
    assert missing.status_code == 400
    assert missing.json()["detail"] == "X-Device-Id is required."

    for error in (
        DeviceNotRegistered("This device is not registered."),
        DeviceRevoked("This device has been revoked."),
    ):
        accounts.device_error = error
        response = client.get("/api/v1/areas", headers=headers())
        assert response.status_code == 403


@pytest.mark.parametrize("role", ["collector", "client"])
def test_non_staff_roles_fail_even_if_area_permission_is_injected(role: str) -> None:
    client, accounts, _ = client_with_fakes()
    accounts.context = account_context(role=role, permissions=("area.manage",))

    response = client.get("/api/v1/areas", headers=headers())

    assert response.status_code == 403


def test_employee_area_manage_can_mutate_structure_but_cannot_retire() -> None:
    client, accounts, repository = client_with_fakes()
    accounts.context = account_context(
        role="employee",
        permissions=("area.manage", "area.retire"),
    )

    create = client.post(
        "/api/v1/areas",
        headers=headers(),
        json={"parent_area_id": None, "name": "Cardona"},
    )
    rename = client.patch(
        f"/api/v1/areas/{AREA_ID}",
        headers=headers(),
        json={"name": "Cardona Renamed"},
    )
    move = client.post(
        f"/api/v1/areas/{AREA_ID}/move",
        headers=headers(),
        json={"new_parent_area_id": str(OTHER_AREA_ID)},
    )
    reorder = client.post(
        "/api/v1/areas/reorder",
        headers=headers(),
        json={
            "parent_area_id": None,
            "ordered_area_ids": [str(AREA_ID), str(OTHER_AREA_ID)],
        },
    )
    retire = client.post(f"/api/v1/areas/{AREA_ID}/retire", headers=headers())

    assert create.status_code in {200, 201}
    assert rename.status_code == 200
    assert move.status_code == 200
    assert reorder.status_code == 200
    assert repository.created_name == "Cardona Renamed"
    assert retire.status_code == 403
    assert repository.retired is None


def test_employee_collector_assignment_requires_exact_permission() -> None:
    client, accounts, repository = client_with_fakes()
    accounts.context = account_context(
        role="employee",
        permissions=("area.collector.assign",),
    )

    response = client.put(
        f"/api/v1/areas/{AREA_ID}/collector",
        headers=headers(),
        json={"collector_user_id": str(COLLECTOR_ID)},
    )

    assert response.status_code == 200
    assert repository.assigned == (AREA_ID, COLLECTOR_ID)


def test_management_area_retire_can_retire_and_reactivate() -> None:
    client, accounts, repository = client_with_fakes()
    accounts.context = account_context(
        role="management",
        permissions=("area.retire",),
    )

    retired = client.post(f"/api/v1/areas/{AREA_ID}/retire", headers=headers())
    reactivated = client.post(
        f"/api/v1/areas/{AREA_ID}/reactivate",
        headers=headers(),
    )

    assert retired.status_code == 200
    assert reactivated.status_code == 200
    assert repository.retired == AREA_ID
    assert repository.reactivated == AREA_ID


def test_area_request_models_forbid_unknown_fields() -> None:
    client, accounts, _ = client_with_fakes()
    accounts.context = account_context(role="employee", permissions=("area.manage",))

    response = client.post(
        "/api/v1/areas",
        headers=headers(),
        json={
            "parent_area_id": None,
            "name": "Cardona",
            "unexpected": "must not be accepted",
        },
    )

    assert response.status_code == 422


def test_repository_conflict_is_409_and_does_not_leak_sql_details() -> None:
    client, accounts, repository = client_with_fakes()
    accounts.context = account_context(role="employee", permissions=("area.manage",))
    repository.conflict = ValueError(
        "duplicate key value violates unique constraint lending_area_nodes_full_path_lower_uidx"
    )

    response = client.post(
        "/api/v1/areas",
        headers=headers(),
        json={"parent_area_id": None, "name": "Cardona"},
    )

    assert response.status_code == 409
    detail = str(response.json()["detail"]).lower()
    assert "duplicate key" not in detail
    assert "constraint" not in detail
    assert "lending_area_nodes" not in detail
