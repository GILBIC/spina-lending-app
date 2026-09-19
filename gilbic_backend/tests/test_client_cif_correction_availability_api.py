from __future__ import annotations

import pytest

import test_client_cif_review_summary_api as summary


URL = f"{summary.URL}?include_correction_availability=true"


class AvailabilityRepository(summary.SummaryRepository):
    def __init__(self, *, available=True, **kwargs):
        super().__init__(**kwargs)
        self.available = available
        self.options = []

    def get_review_summary(self, *, client_id, **options):
        self.options.append(options)
        record = super().get_review_summary(client_id=client_id)
        record.can_correct_information = self.available
        return record


def _client(monkeypatch, **kwargs):
    # Reuse existing auth/device fixtures while replacing only the external read.
    monkeypatch.setattr(summary, "SummaryRepository", AvailabilityRepository)
    return summary._client(**kwargs)


@pytest.mark.parametrize("role", ["employee", "management"])
@pytest.mark.parametrize("available", [True, False])
def test_opt_in_returns_only_review_information_and_strict_availability(
    monkeypatch, role, available,
):
    client, repository = _client(monkeypatch, role=role, available=available)

    response = client.get(URL, headers=summary.HEADERS)

    assert response.status_code == 200
    assert response.json() == {
        "client_id": str(summary.CLIENT_ID),
        "cif_version_id": str(summary.CIF_ID),
        "version_number": 1,
        "status": "draft",
        "full_name": "Synthetic CIF Borrower",
        "phone_number": "09170000000",
        "email": None,
        "present_address": "Synthetic office review address",
        "liveness_status": "pending",
        "review_scope": "cif_information_only",
        "can_correct_information": available,
    }
    assert type(response.json()["can_correct_information"]) is bool
    assert response.headers["cache-control"] == "no-store"
    assert "PRIVATE-" not in response.text
    assert repository.calls == [summary.CLIENT_ID]
    assert repository.options == [{"include_correction_availability": True}]


@pytest.mark.parametrize("query", ["", "?include_correction_availability=false"])
def test_default_and_false_keep_existing_payload_and_repository_call(monkeypatch, query):
    client, repository = _client(monkeypatch)
    response = client.get(summary.URL + query, headers=summary.HEADERS)
    assert response.status_code == 200
    assert "can_correct_information" not in response.json()
    assert repository.calls == [summary.CLIENT_ID]
    assert repository.options == [{}]


@pytest.mark.parametrize("available", [None, "true", 1])
def test_untrusted_or_absent_availability_cannot_enable_correction(monkeypatch, available):
    client, repository = _client(monkeypatch, available=available)
    response = client.get(URL, headers=summary.HEADERS)
    assert response.status_code == 200
    assert response.json()["can_correct_information"] is False
    assert repository.calls == [summary.CLIENT_ID]


@pytest.mark.parametrize("role", ["collector", "client", "unknown"])
def test_availability_retains_office_role_gate(monkeypatch, role):
    client, repository = _client(monkeypatch, role=role)
    response = client.get(URL, headers=summary.HEADERS)
    assert response.status_code == 403
    assert repository.calls == []


def test_availability_requires_exact_review_permission(monkeypatch):
    client, repository = _client(
        monkeypatch, permissions=("client_onboarding.requirement.review.extra",),
    )
    response = client.get(URL, headers=summary.HEADERS)
    assert response.status_code == 403
    assert repository.calls == []


@pytest.mark.parametrize("omitted,status", [("Authorization", 401), ("X-Device-Id", 400)])
def test_availability_requires_authentication_and_device(monkeypatch, omitted, status):
    client, repository = _client(monkeypatch)
    headers = {key: value for key, value in summary.HEADERS.items() if key != omitted}
    assert client.get(URL, headers=headers).status_code == status
    assert repository.calls == []


@pytest.mark.parametrize("error", ["DeviceNotRegistered", "DeviceRevoked", "AccountDisabled"])
def test_availability_preserves_persisted_account_and_device_denials(monkeypatch, error):
    client, repository = _client(monkeypatch, account_error=error)
    assert client.get(URL, headers=summary.HEADERS).status_code == 403
    assert repository.calls == []


@pytest.mark.parametrize("value", ["", "maybe", "2"])
def test_malformed_availability_query_is_rejected_before_read(monkeypatch, value):
    client, repository = _client(monkeypatch)
    response = client.get(
        f"{summary.URL}?include_correction_availability={value}",
        headers=summary.HEADERS,
    )
    assert response.status_code == 422
    assert repository.calls == []


def test_unavailable_cif_keeps_existing_conflict_boundary(monkeypatch):
    client, repository = _client(monkeypatch, conflict=True)
    response = client.get(URL, headers=summary.HEADERS)
    assert response.status_code == 409
    assert response.json() == {"detail": "No eligible current CIF is available."}
    assert repository.calls == [summary.CLIENT_ID]
