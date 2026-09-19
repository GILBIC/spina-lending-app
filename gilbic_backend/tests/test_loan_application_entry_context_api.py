from __future__ import annotations

import importlib
from types import SimpleNamespace
from uuid import UUID

import pytest

import test_loan_application_review_summary_api as summary


URL = f"/api/v1/management/clients/{summary.CLIENT_ID}/loan-applications/entry-context"
TYPE_ID = UUID("77777777-7777-4777-8777-777777777777")
UNAVAILABLE = "No eligible current CIF is available for this application draft."


class EntryRepository:
    def __init__(self, *, complete=True, error=None):
        self.calls = []
        self.error = error
        self.loan_types = (SimpleNamespace(
            id=TYPE_ID, code="SYNTHETIC-WORKING", name="Synthetic Working Capital",
            interest_rate="PRIVATE-PRICING", settings={"secret": "PRIVATE-SETTINGS"},
        ),)

    def get_entry_context(self, **payload):
        self.calls.append(payload)
        module = importlib.import_module("gilbic_backend.loan_application_repository")
        if self.error == "conflict":
            raise module.LoanApplicationConflict(UNAVAILABLE)
        if self.error == "access":
            raise module.LoanApplicationAccessDenied(
                "An active authorized office account is required."
            )
        return SimpleNamespace(
            client_id=summary.CLIENT_ID,
            cif_version_id=summary.CIF_ID,
            cif_version_number=3,
            loan_types=self.loan_types,
            full_name="PRIVATE-NAME", phone_number="PRIVATE-PHONE",
            confirmed=True, approval_status="PRIVATE-APPROVED",
        )


def _client(monkeypatch, **kwargs):
    monkeypatch.setattr(summary, "SummaryRepository", EntryRepository)
    return summary._client(**kwargs)


@pytest.mark.parametrize("role", ["employee", "management"])
def test_entry_context_returns_only_current_cif_identity_and_type_choices(monkeypatch, role):
    client, repository = _client(monkeypatch, role=role)

    response = client.get(URL, headers=summary.HEADERS)

    assert response.status_code == 200
    assert response.json() == {
        "client_id": str(summary.CLIENT_ID),
        "cif_version_id": str(summary.CIF_ID),
        "cif_version_number": 3,
        "loan_types": [{
            "id": str(TYPE_ID), "code": "SYNTHETIC-WORKING", "name": "Synthetic Working Capital",
        }],
    }
    assert response.headers["cache-control"] == "no-store"
    assert "PRIVATE-" not in response.text
    assert repository.calls == [{"actor_user_id": summary.ACTOR_ID, "client_id": summary.CLIENT_ID}]


def test_empty_catalog_keeps_eligible_context_available(monkeypatch):
    client, repository = _client(monkeypatch)
    repository.loan_types = ()
    response = client.get(URL, headers=summary.HEADERS)
    assert response.status_code == 200
    assert response.json()["loan_types"] == []
    assert response.json()["cif_version_id"] == str(summary.CIF_ID)


@pytest.mark.parametrize("role", ["collector", "client", "unknown"])
def test_entry_context_denies_non_office_roles_even_with_permission(monkeypatch, role):
    client, repository = _client(monkeypatch, role=role)
    response = client.get(URL, headers=summary.HEADERS)
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls == []


def test_entry_context_requires_exact_review_permission(monkeypatch):
    client, repository = _client(
        monkeypatch, permissions=("client_onboarding.requirement.review.extra",),
    )
    response = client.get(URL, headers=summary.HEADERS)
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls == []


@pytest.mark.parametrize("omitted,expected", [("Authorization", 401), ("X-Device-Id", 400)])
def test_entry_context_requires_auth_and_device(monkeypatch, omitted, expected):
    client, repository = _client(monkeypatch)
    headers = {key: value for key, value in summary.HEADERS.items() if key != omitted}
    response = client.get(URL, headers=headers)
    assert response.status_code == expected
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls == []


@pytest.mark.parametrize("error", ["DeviceNotRegistered", "DeviceRevoked", "AccountDisabled"])
def test_entry_context_preserves_persisted_account_and_device_denials(monkeypatch, error):
    client, repository = _client(monkeypatch, account_error=error)
    response = client.get(URL, headers=summary.HEADERS)
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls == []


@pytest.mark.parametrize("error,status", [("conflict", 409), ("access", 403)])
def test_entry_context_failure_does_not_leak_identity_or_catalog(monkeypatch, error, status):
    client, repository = _client(monkeypatch, repository_error=error)
    response = client.get(URL, headers=summary.HEADERS)
    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"
    if error == "conflict":
        assert response.json() == {"detail": UNAVAILABLE}
    assert str(summary.CLIENT_ID) not in response.text
    assert str(summary.CIF_ID) not in response.text
    assert "PRIVATE-" not in response.text
    assert "loan_types" not in response.json()
    assert len(repository.calls) == 1


def test_entry_context_rejects_malformed_client_id_before_repository(monkeypatch):
    client, repository = _client(monkeypatch)
    response = client.get(URL.replace(str(summary.CLIENT_ID), "not-a-uuid"), headers=summary.HEADERS)
    assert response.status_code == 422
    assert repository.calls == []


@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE"])
def test_entry_context_exposes_no_mutation_method(monkeypatch, method):
    client, repository = _client(monkeypatch)
    assert client.request(method, URL, headers=summary.HEADERS).status_code == 405
    assert repository.calls == []


@pytest.mark.parametrize("surface", ["public", "client"])
def test_entry_context_has_no_self_service_alias(monkeypatch, surface):
    client, repository = _client(monkeypatch)
    response = client.get(URL.replace("/management/", f"/{surface}/"), headers=summary.HEADERS)
    assert response.status_code == 404
    assert repository.calls == []
