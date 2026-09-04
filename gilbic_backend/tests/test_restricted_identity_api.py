from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.restricted_identity_api import (
    restricted_identity_repository_dependency,
)
from gilbic_backend.restricted_identity_repository import (
    RestrictedEvidenceRecord,
    RestrictedIdentityConflict,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
DEVICE_ID = UUID("33333333-3333-4333-8333-333333333333")
CLIENT_ID = UUID("44444444-4444-4444-8444-444444444444")
CIF_ID = UUID("55555555-5555-4555-8555-555555555555")
EVIDENCE_ID = UUID("66666666-6666-4666-8666-666666666666")
REQUEST_ID = UUID("77777777-7777-4777-8777-777777777777")
NOW = datetime(2026, 9, 4, 2, 0, tzinfo=UTC)


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "restricted-token"
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="management@example.com",
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
            username="management.one",
            email="management@example.com",
            full_name="Management One",
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
        assert device_identifier == "management-device"
        return self.context


class FakeRestrictedRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.error: Exception | None = None

    def _result(self, name: str, kwargs: dict[str, object], value):
        self.calls.append((name, kwargs))
        if self.error is not None:
            raise self.error
        return value

    def list_for_cif(self, **kwargs):
        return self._result("list_for_cif", kwargs, (_record(),))

    def record(self, **kwargs):
        return self._result("record", kwargs, _record())

    def review(self, **kwargs):
        return self._result("review", kwargs, _record(reviewed=True))


def _record(*, reviewed: bool = False) -> RestrictedEvidenceRecord:
    return RestrictedEvidenceRecord(
        evidence_id=EVIDENCE_ID,
        client_id=CLIENT_ID,
        cif_id=CIF_ID,
        evidence_type="national_id_check",
        verification_method="approved-adapter",
        verification_outcome="verified",
        checked_at=NOW,
        document_date=date(2026, 9, 1),
        document_expires_at=date(2031, 9, 1),
        masked_reference="****-****-1234",
        external_evidence_reference="restricted://evidence/synthetic",
        evidence_digest="a" * 64,
        retention_class="identity_verification",
        retain_until=date(2036, 9, 1),
        legal_hold=False,
        recorded_by_user_id=ACTOR_USER_ID,
        recorded_at=NOW,
        supersedes_evidence_id=None,
        review_decision="approved" if reviewed else None,
        review_note="Independent review." if reviewed else None,
        reviewed_by_user_id=ACTOR_USER_ID if reviewed else None,
        reviewed_at=NOW if reviewed else None,
        is_superseded=False,
    )


def _evidence_json() -> dict[str, object]:
    return {
        "client_id": str(CLIENT_ID),
        "evidence_type": "national_id_check",
        "verification_method": "approved-adapter",
        "verification_outcome": "verified",
        "checked_at": NOW.isoformat(),
        "document_date": "2026-09-01",
        "document_expires_at": "2031-09-01",
        "masked_reference": "****-****-1234",
        "external_evidence_reference": "restricted://evidence/synthetic",
        "evidence_digest": "a" * 64,
        "retention_class": "identity_verification",
        "retain_until": "2036-09-01",
        "legal_hold": False,
        "supersedes_evidence_id": None,
    }


def _client(
    *,
    role: str = "management",
    permissions: tuple[str, ...] = ("identity_evidence.view",),
) -> tuple[TestClient, FakeAccounts, FakeRestrictedRepository]:
    accounts = FakeAccounts(role=role, permissions=permissions)
    repository = FakeRestrictedRepository()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: accounts
    app.dependency_overrides[restricted_identity_repository_dependency] = (
        lambda: repository
    )
    return TestClient(app), accounts, repository


def _headers(*, purpose: str = "compliance_review") -> dict[str, str]:
    return {
        "Authorization": "Bearer restricted-token",
        "X-Device-Id": "management-device",
        "X-Access-Purpose": purpose,
        "X-Request-Id": str(REQUEST_ID),
    }


def test_management_with_exact_permission_can_view_restricted_allowlist() -> None:
    client, _, repository = _client()

    response = client.get(
        f"/api/v1/management/cifs/{CIF_ID}/verification-evidence",
        headers=_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data[0]["evidence_id"] == str(EVIDENCE_ID)
    assert data[0]["masked_reference"] == "****-****-1234"
    assert data[0]["external_evidence_reference"] == "restricted://evidence/synthetic"
    assert repository.calls == [
        (
            "list_for_cif",
            {
                "actor_user_id": ACTOR_USER_ID,
                "registered_device_id": DEVICE_ID,
                "request_id": REQUEST_ID,
                "purpose_code": "compliance_review",
                "cif_id": CIF_ID,
            },
        )
    ]


def test_employee_is_denied_even_with_restricted_permission() -> None:
    client, _, repository = _client(
        role="employee",
        permissions=("identity_evidence.view",),
    )

    response = client.get(
        f"/api/v1/management/cifs/{CIF_ID}/verification-evidence",
        headers=_headers(),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "management_role_required"
    assert repository.calls == []


def test_registered_device_purpose_request_id_and_exact_permission_are_required() -> None:
    client, accounts, repository = _client()

    no_purpose = _headers()
    no_purpose.pop("X-Access-Purpose")
    response = client.get(
        f"/api/v1/management/cifs/{CIF_ID}/verification-evidence",
        headers=no_purpose,
    )
    assert response.status_code == 400

    no_request_id = _headers()
    no_request_id.pop("X-Request-Id")
    response = client.get(
        f"/api/v1/management/cifs/{CIF_ID}/verification-evidence",
        headers=no_request_id,
    )
    assert response.status_code == 400

    accounts.context = AccountContext(
        user_id=ACTOR_USER_ID,
        auth_user_id=AUTH_USER_ID,
        username="management.one",
        email="management@example.com",
        full_name="Management One",
        status="active",
        roles=("management",),
        permissions=(),
        device_registered=True,
        registered_device_id=DEVICE_ID,
    )
    response = client.get(
        f"/api/v1/management/cifs/{CIF_ID}/verification-evidence",
        headers=_headers(),
    )
    assert response.status_code == 403

    accounts.context = AccountContext(
        user_id=ACTOR_USER_ID,
        auth_user_id=AUTH_USER_ID,
        username="management.one",
        email="management@example.com",
        full_name="Management One",
        status="active",
        roles=("management",),
        permissions=("identity_evidence.view",),
        device_registered=True,
        registered_device_id=None,
    )
    response = client.get(
        f"/api/v1/management/cifs/{CIF_ID}/verification-evidence",
        headers=_headers(),
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "registered_device_required"
    assert repository.calls == []


def test_record_body_rejects_raw_identity_and_credential_fields() -> None:
    client, _, repository = _client(
        permissions=("identity_evidence.record",),
    )

    for forbidden_field, value in (
        ("raw_content", "base64"),
        ("raw_document", "bytes"),
        ("otp", "123456"),
        ("mpin", "0000"),
        ("password", "secret"),
        ("national_id_number", "123456789012"),
        ("provider_payload", {"secret": "value"}),
        ("phone_contacts", ["09170000000"]),
    ):
        body = _evidence_json()
        body[forbidden_field] = value
        response = client.post(
            f"/api/v1/management/cifs/{CIF_ID}/verification-evidence",
            headers=_headers(purpose="cif_verification"),
            json=body,
        )
        assert response.status_code == 422
    assert repository.calls == []


def test_management_can_record_and_review_with_separate_permissions() -> None:
    client, accounts, repository = _client(
        permissions=("identity_evidence.record",),
    )

    response = client.post(
        f"/api/v1/management/cifs/{CIF_ID}/verification-evidence",
        headers=_headers(purpose="cif_verification"),
        json=_evidence_json(),
    )
    assert response.status_code == 200
    assert repository.calls[-1][0] == "record"
    assert repository.calls[-1][1]["client_id"] == CLIENT_ID
    assert repository.calls[-1][1]["cif_id"] == CIF_ID

    accounts.context = AccountContext(
        user_id=ACTOR_USER_ID,
        auth_user_id=AUTH_USER_ID,
        username="management.one",
        email="management@example.com",
        full_name="Management One",
        status="active",
        roles=("management",),
        permissions=("identity_evidence.review",),
        device_registered=True,
        registered_device_id=DEVICE_ID,
    )
    response = client.post(
        f"/api/v1/management/verification-evidence/{EVIDENCE_ID}/review",
        headers=_headers(),
        json={
            "decision": "approved",
            "review_note": "Independent review complete.",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["review_decision"] == "approved"
    assert repository.calls[-1][0] == "review"


def test_restricted_conflict_maps_to_stable_http_409() -> None:
    client, _, repository = _client(
        permissions=("identity_evidence.review",),
    )
    repository.error = RestrictedIdentityConflict(
        "Restricted evidence reviewer must differ from the recorder."
    )

    response = client.post(
        f"/api/v1/management/verification-evidence/{EVIDENCE_ID}/review",
        headers=_headers(),
        json={
            "decision": "approved",
            "review_note": "Attempt",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "restricted_identity_conflict",
        "message": "Restricted evidence reviewer must differ from the recorder.",
    }
