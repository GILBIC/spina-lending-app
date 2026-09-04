from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.cif_api import cif_repository_dependency
from gilbic_backend.cif_repository import (
    CifClientSummary,
    CifConflict,
    CifReverificationRecord,
    ClientInformationFormRecord,
)
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
DEVICE_ID = UUID("33333333-3333-4333-8333-333333333333")
CLIENT_ID = UUID("44444444-4444-4444-8444-444444444444")
CIF_ID = UUID("55555555-5555-4555-8555-555555555555")
REQUIREMENT_ID = UUID("66666666-6666-4666-8666-666666666666")
NOW = datetime(2026, 9, 4, 1, 0, tzinfo=UTC)


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "cif-token"
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="office@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def __init__(self, *, role: str, permissions: tuple[str, ...]) -> None:
        self.context = AccountContext(
            user_id=ACTOR_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username="office.one",
            email="office@example.com",
            full_name="Office One",
            status="active",
            roles=(role,),
            permissions=permissions,
            device_registered=True,
            registered_device_id=DEVICE_ID,
        )

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == "office-device"
        return self.context


class FakeCifRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.error: Exception | None = None

    def _result(self, name: str, kwargs: dict[str, object], value):
        self.calls.append((name, kwargs))
        if self.error is not None:
            raise self.error
        return value

    def search_clients(self, **kwargs):
        return self._result(
            "search_clients",
            kwargs,
            (
                CifClientSummary(
                    client_id=CLIENT_ID,
                    client_code="CIF-001",
                    client_name="Safe Client",
                    area="Rizal",
                    client_status="active",
                    active_cif_id=CIF_ID,
                    active_cif_number="CIF-0000000001",
                    active_cif_status="Active",
                    active_cif_expires_at=NOW + timedelta(days=365),
                    is_eligible_for_new_credit=True,
                ),
            ),
        )

    def list_for_client(self, **kwargs):
        return self._result("list_for_client", kwargs, (_record(),))

    def list_reverification_for_client(self, **kwargs):
        return self._result(
            "list_reverification_for_client",
            kwargs,
            (_requirement(),),
        )

    def get(self, **kwargs):
        return self._result("get", kwargs, _record())

    def create_draft(self, **kwargs):
        return self._result("create_draft", kwargs, _record())

    def update_draft(self, **kwargs):
        return self._result("update_draft", kwargs, _record())

    def verify(self, **kwargs):
        return self._result("verify", kwargs, _record(verified=True))

    def activate(self, **kwargs):
        return self._result("activate", kwargs, _record(active=True, verified=True))

    def open_reverification(self, **kwargs):
        return self._result("open_reverification", kwargs, _requirement())


def _record(
    *,
    active: bool = False,
    verified: bool = False,
) -> ClientInformationFormRecord:
    return ClientInformationFormRecord(
        cif_id=CIF_ID,
        cif_number="CIF-0000000001",
        client_id=CLIENT_ID,
        client_code="CIF-001",
        client_name="Safe Client",
        form_version=1,
        lifecycle_state="active" if active else "draft",
        public_status="Active" if active else "Draft",
        effective_at=NOW if active else None,
        expires_at=(NOW + timedelta(days=365 * 5)) if active else None,
        supersedes_cif_id=None,
        legal_full_name="Safe Client",
        birth_date=date(1990, 1, 2),
        place_of_birth="Rizal",
        nationality="Filipino",
        civil_status="single",
        phone_number="09170000000",
        email="safe@example.com",
        present_address={"line1": "Safe present", "province": "Rizal"},
        permanent_address={"line1": "Safe permanent", "province": "Rizal"},
        same_as_present_address=False,
        livelihood_profile={"kind": "self_employed"},
        privacy_notice_version="privacy-v1",
        privacy_acknowledged_at=NOW,
        has_client_signature=True,
        prepared_by_user_id=ACTOR_USER_ID,
        verified_by_user_id=ACTOR_USER_ID if verified else None,
        verified_at=NOW if verified else None,
        approved_by_user_id=ACTOR_USER_ID if active else None,
        approved_at=NOW if active else None,
        form_schema_version="1",
        source_digest="a" * 64 if verified else None,
        has_open_reverification=False,
        is_eligible_for_new_credit=active,
        created_at=NOW,
        updated_at=NOW,
    )


def _requirement() -> CifReverificationRecord:
    return CifReverificationRecord(
        requirement_id=REQUIREMENT_ID,
        client_id=CLIENT_ID,
        source_cif_id=CIF_ID,
        reason="address_change",
        severity="standard",
        status="open",
        note="Address change requires review.",
        opened_by_user_id=ACTOR_USER_ID,
        opened_at=NOW,
        resolved_by_user_id=None,
        resolved_at=None,
        resolution_cif_id=None,
        resolution_note="",
    )


def _draft_json() -> dict[str, object]:
    return {
        "legal_full_name": "Safe Client",
        "birth_date": "1990-01-02",
        "place_of_birth": "Rizal",
        "nationality": "Filipino",
        "civil_status": "single",
        "phone_number": "09170000000",
        "email": "safe@example.com",
        "present_address": {"line1": "Safe present", "province": "Rizal"},
        "permanent_address": {"line1": "Safe permanent", "province": "Rizal"},
        "same_as_present_address": False,
        "livelihood_profile": {"kind": "self_employed"},
        "privacy_notice_version": "privacy-v1",
        "privacy_acknowledged_at": NOW.isoformat(),
        "client_signature_reference": "restricted-signature://safe",
        "client_signature_digest": "1" * 64,
        "form_schema_version": "1",
    }


def _client(
    *,
    role: str,
    permissions: tuple[str, ...],
) -> tuple[TestClient, FakeAccounts, FakeCifRepository]:
    accounts = FakeAccounts(role=role, permissions=permissions)
    repository = FakeCifRepository()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: accounts
    app.dependency_overrides[cif_repository_dependency] = lambda: repository
    return TestClient(app), accounts, repository


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer cif-token",
        "X-Device-Id": "office-device",
    }


def test_employee_with_view_permission_can_search_and_read_safe_cif_payload() -> None:
    client, _, repository = _client(role="employee", permissions=("cif.view",))

    response = client.get(
        "/api/v1/management/cif-clients?q=CIF-001",
        headers=_headers(),
    )
    assert response.status_code == 200
    assert response.json()["data"][0]["client_id"] == str(CLIENT_ID)

    response = client.get(
        f"/api/v1/management/clients/{CLIENT_ID}/cifs",
        headers=_headers(),
    )
    assert response.status_code == 200
    payload_text = str(response.json()).lower()
    for forbidden in (
        "external_evidence_reference",
        "evidence_digest",
        "masked_reference",
        "verification_outcome",
        "utility_proof",
        "residence_visit",
        "client_signature_reference",
        "client_signature_digest",
    ):
        assert forbidden not in payload_text
    assert [name for name, _ in repository.calls] == [
        "search_clients",
        "list_for_client",
        "list_reverification_for_client",
    ]


def test_employee_with_prepare_permission_can_create_and_update_draft() -> None:
    client, _, repository = _client(
        role="employee",
        permissions=("cif.prepare",),
    )

    response = client.post(
        f"/api/v1/management/clients/{CLIENT_ID}/cifs",
        headers=_headers(),
        json=_draft_json(),
    )
    assert response.status_code == 200
    create_call = repository.calls[-1]
    assert create_call[0] == "create_draft"
    assert create_call[1]["actor_user_id"] == ACTOR_USER_ID

    response = client.patch(
        f"/api/v1/management/cifs/{CIF_ID}",
        headers=_headers(),
        json={
            "expected_updated_at": NOW.isoformat(),
            "draft": _draft_json(),
        },
    )
    assert response.status_code == 200
    assert repository.calls[-1][0] == "update_draft"


def test_management_only_action_rejects_employee_even_with_forged_permission() -> None:
    client, _, repository = _client(
        role="employee",
        permissions=("cif.verify",),
    )

    response = client.post(
        f"/api/v1/management/cifs/{CIF_ID}/verify",
        headers=_headers(),
        json={
            "expected_updated_at": NOW.isoformat(),
            "review_note": "Attempt",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "management_role_required"
    assert repository.calls == []


def test_collector_is_rejected_even_with_cif_view_permission() -> None:
    client, _, repository = _client(
        role="collector",
        permissions=("cif.view",),
    )

    response = client.get(
        "/api/v1/management/cif-clients?q=CIF-001",
        headers=_headers(),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "office_role_required"
    assert repository.calls == []


def test_exact_permission_and_strict_body_are_required() -> None:
    client, accounts, repository = _client(
        role="management",
        permissions=("cif.view",),
    )
    accounts.context = AccountContext(
        user_id=ACTOR_USER_ID,
        auth_user_id=AUTH_USER_ID,
        username="management.one",
        email="management@example.com",
        full_name="Management One",
        status="active",
        roles=("management",),
        permissions=("cif.prepare",),
        device_registered=True,
        registered_device_id=DEVICE_ID,
    )

    body = _draft_json()
    body["raw_identity_document"] = "forbidden"
    response = client.post(
        f"/api/v1/management/clients/{CLIENT_ID}/cifs",
        headers=_headers(),
        json=body,
    )
    assert response.status_code == 422
    assert repository.calls == []

    accounts.context = AccountContext(
        user_id=ACTOR_USER_ID,
        auth_user_id=AUTH_USER_ID,
        username="management.one",
        email="management@example.com",
        full_name="Management One",
        status="active",
        roles=("management",),
        permissions=("cif.view",),
        device_registered=True,
        registered_device_id=DEVICE_ID,
    )
    response = client.post(
        f"/api/v1/management/clients/{CLIENT_ID}/cifs",
        headers=_headers(),
        json=_draft_json(),
    )
    assert response.status_code == 403
    assert repository.calls == []


def test_repository_conflict_maps_to_stable_http_409() -> None:
    client, _, repository = _client(
        role="management",
        permissions=("cif.approve",),
    )
    repository.error = CifConflict("The verified CIF source changed.")

    response = client.post(
        f"/api/v1/management/cifs/{CIF_ID}/activate",
        headers=_headers(),
        json={
            "expected_source_digest": "a" * 64,
            "review_note": "Approve current source.",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "cif_conflict",
        "message": "The verified CIF source changed.",
    }
