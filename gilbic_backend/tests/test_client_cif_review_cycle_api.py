from uuid import UUID

import pytest

import test_client_cif_review_summary_api as summary


NEXT_ID = UUID("88888888-8888-4888-8888-888888888888")
URL = f"/api/v1/management/clients/{summary.CLIENT_ID}/cif/review-cycles"
INFORMATION = {
    "full_name": "Synthetic CIF Borrower",
    "phone_number": "09170000000",
    "email": None,
    "present_address": "Synthetic office review address",
}


class CycleRepository(summary.SummaryRepository):
    def begin_review_cycle(self, **payload):
        record = super().get_review_summary(client_id=payload["client_id"])
        self.calls = [payload]
        record.id = NEXT_ID
        record.version_number = 2
        for field, value in payload["corrected_information"].items():
            setattr(record, field, value)
        return record


@pytest.mark.parametrize(
    "kwargs",
    [
        {"role": "collector"},
        {"role": "client"},
        {"role": "unknown"},
        {"permissions": ()},
        {"account_error": "AccountDisabled"},
        {"account_error": "DeviceRevoked"},
    ],
)
def test_successor_route_retains_office_and_persisted_device_authority(
    monkeypatch, kwargs
):
    monkeypatch.setattr(summary, "SummaryRepository", CycleRepository)
    client, repository = summary._client(**kwargs)
    response = client.post(
        URL,
        headers=summary.HEADERS,
        json={
            "cif_version_id": str(summary.CIF_ID),
            "expected_information": INFORMATION,
            "corrected_information": INFORMATION,
            "reason": "Applicant correction",
        },
    )
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls == []


def test_successor_delegates_and_returns_optional_identity_without_changing_legacy_fields(
    monkeypatch,
):
    monkeypatch.setattr(summary, "SummaryRepository", CycleRepository)
    client, repository = summary._client()
    identity = {
        "birth_date": "1990-01-02",
        "birth_place": "Synthetic town",
        "civil_status": None,
        "citizenship": None,
    }
    response = client.post(
        URL,
        headers=summary.HEADERS,
        json={
            "cif_version_id": str(summary.CIF_ID),
            "expected_information": INFORMATION,
            "corrected_information": {**INFORMATION, "identity_information": identity},
            "reason": "Applicant supplied identity facts",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["identity_information"] == identity
    assert repository.calls[0]["expected_information"] == INFORMATION
    assert (
        repository.calls[0]["corrected_information"]["identity_information"] == identity
    )


@pytest.mark.parametrize("role", ["employee", "management"])
def test_office_can_start_exact_successor_review_cycle(monkeypatch, role):
    monkeypatch.setattr(summary, "SummaryRepository", CycleRepository)
    client, repository = summary._client(role=role)
    corrected = {**INFORMATION, "phone_number": "09172222222"}
    response = client.post(
        URL,
        headers=summary.HEADERS,
        json={
            "cif_version_id": str(summary.CIF_ID),
            "expected_information": INFORMATION,
            "corrected_information": corrected,
            "reason": "Applicant reported a correction",
        },
    )
    assert response.status_code == 201
    assert response.json()["cif_version_id"] == str(NEXT_ID)
    assert response.json()["version_number"] == 2
    assert response.json()["phone_number"] == "09172222222"
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls == [
        {
            "actor_user_id": summary.ACTOR_ID,
            "client_id": summary.CLIENT_ID,
            "cif_version_id": summary.CIF_ID,
            "expected_information": INFORMATION,
            "corrected_information": corrected,
            "reason": "Applicant reported a correction",
        }
    ]
