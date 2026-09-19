from __future__ import annotations

import importlib
from types import SimpleNamespace
from urllib.parse import quote

import pytest

from gilbic_backend.loan_application_information import LoanApplicationInformation
import test_loan_application_review_summary_api as summary


REFERENCE = "SYN-APP-REVIEW-001"
BASE_URL = f"/api/v1/management/clients/{summary.CLIENT_ID}/loan-applications/by-reference"


def _url(reference=REFERENCE):
    return f"{BASE_URL}/{quote(reference, safe='')}/review-summary"


class ReferenceRepository:
    def __init__(self, *, complete=True, error=None):
        self.calls = []
        self.error = error
        self.reference = REFERENCE
        self.loan_type_name = "Synthetic Working Capital"
        self.information = summary._information(complete=complete)

    def get_latest_by_reference(self, **payload):
        self.calls.append(payload)
        if self.error == "missing":
            return None
        if self.error == "access":
            module = importlib.import_module("gilbic_backend.loan_application_repository")
            raise module.LoanApplicationAccessDenied(
                "An active authorized office account is required."
            )
        return SimpleNamespace(
            id=summary.VERSION_ID,
            application_id=summary.APPLICATION_ID,
            application_reference=self.reference,
            client_id=summary.CLIENT_ID,
            cif_version_id=summary.CIF_ID,
            version_number=7,
            information=self.information,
            recorded_by_user_id=summary.ACTOR_ID,
            recorded_at=summary.RECORDED_AT,
            cif_version_number=2,
            requested_loan_type_name=self.loan_type_name,
            private_evidence_reference="PRIVATE-EVIDENCE",
            current_cif_full_name="PRIVATE-CURRENT-CIF",
            approval_status="PRIVATE-APPROVED",
            release_status="PRIVATE-RELEASED",
        )


def _client(monkeypatch, **kwargs):
    monkeypatch.setattr(summary, "SummaryRepository", ReferenceRepository)
    return summary._client(**kwargs)


@pytest.mark.parametrize("role", ["employee", "management"])
@pytest.mark.parametrize("complete", [True, False])
def test_reference_review_returns_saved_application_and_attached_source_metadata(
    monkeypatch, role, complete,
):
    client, repository = _client(monkeypatch, role=role, complete=complete)
    response = client.get(_url(), headers=summary.HEADERS)

    assert response.status_code == 200
    assert response.json() == {
        "client_id": str(summary.CLIENT_ID),
        "application_id": str(summary.APPLICATION_ID),
        "application_version_id": str(summary.VERSION_ID),
        "application_reference": REFERENCE,
        "cif_version_id": str(summary.CIF_ID),
        "version_number": 7,
        "information": {
            "request": {
                "requested_loan_type_id": "00000000-0000-0000-0000-0000000000a1",
                "purpose": "Synthetic working capital" if complete else None,
                "requested_amount": "3000.00",
                "requested_payment_arrangement": "Daily office collection",
                "requested_term": "60 calendar days",
                "preferred_first_payment_date": None,
            },
            "repayment": {
                "repayment_source": "Synthetic microbusiness",
                "source_details": "Synthetic sari-sari income declaration",
                "monthly_gross_income": "12000.00",
                "monthly_net_income": "8000.00",
                "has_existing_obligations": False,
                "obligations": [],
            },
        },
        "missing_fields": [] if complete else ["request.purpose"],
        "recorded_at": "2026-09-17T01:02:03Z",
        "review_scope": "loan_application_information_only",
        "cif_version_number": 2,
        "requested_loan_type_name": "Synthetic Working Capital",
    }
    assert response.headers["cache-control"] == "no-store"
    assert "PRIVATE-" not in response.text
    assert repository.calls == [{
        "actor_user_id": summary.ACTOR_ID,
        "client_id": summary.CLIENT_ID,
        "application_reference": REFERENCE,
    }]


@pytest.mark.parametrize(
    "reference",
    ["  \tLoan/  MiXeD Case\t ", "Other-" + "long" * 100, "Literal%_' OR 1=1 --"],
)
def test_reference_delegation_only_trims_edges(monkeypatch, reference):
    client, repository = _client(monkeypatch)
    repository.reference = reference.strip()
    response = client.get(_url(reference), headers=summary.HEADERS)
    assert response.status_code == 200
    assert response.json()["application_reference"] == reference.strip()
    assert repository.calls[0]["application_reference"] == reference.strip()


def test_nullable_catalog_name_and_exact_large_decimal_are_preserved(monkeypatch):
    client, repository = _client(monkeypatch)
    repository.loan_type_name = None
    repository.information = LoanApplicationInformation(
        request={"requested_amount": "9007199254740993.01"},
    )
    response = client.get(_url(), headers=summary.HEADERS)
    assert response.status_code == 200
    assert response.json()["requested_loan_type_name"] is None
    assert response.json()["information"]["request"]["requested_amount"] == "9007199254740993.01"
    assert "request.requested_loan_type_id" in response.json()["missing_fields"]


@pytest.mark.parametrize("role", ["collector", "client", "unknown"])
def test_non_office_actor_is_denied_even_with_review_permission(monkeypatch, role):
    client, repository = _client(monkeypatch, role=role)
    response = client.get(_url(), headers=summary.HEADERS)
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls == []


def test_exact_review_permission_is_required(monkeypatch):
    client, repository = _client(
        monkeypatch, permissions=("client_onboarding.requirement.review.extra",),
    )
    response = client.get(_url(), headers=summary.HEADERS)
    assert response.status_code == 403
    assert repository.calls == []


@pytest.mark.parametrize("omitted,expected", [("Authorization", 401), ("X-Device-Id", 400)])
def test_reference_review_requires_auth_and_device(monkeypatch, omitted, expected):
    client, repository = _client(monkeypatch)
    headers = {key: value for key, value in summary.HEADERS.items() if key != omitted}
    response = client.get(_url(), headers=headers)
    assert response.status_code == expected
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls == []


@pytest.mark.parametrize("error", ["DeviceNotRegistered", "DeviceRevoked", "AccountDisabled"])
def test_reference_review_preserves_persisted_access_denials(monkeypatch, error):
    client, repository = _client(monkeypatch, account_error=error)
    response = client.get(_url(), headers=summary.HEADERS)
    assert response.status_code == 403
    assert repository.calls == []


@pytest.mark.parametrize("error,status", [("missing", 404), ("access", 403)])
def test_repository_failure_boundary_is_private_and_not_cached(monkeypatch, error, status):
    client, repository = _client(monkeypatch, repository_error=error)
    response = client.get(_url(), headers=summary.HEADERS)
    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"
    if error == "missing":
        assert response.json() == {"detail": "Application review is unavailable."}
    assert REFERENCE not in response.text
    assert str(summary.CLIENT_ID) not in response.text
    assert "PRIVATE-" not in response.text
    assert len(repository.calls) == 1


@pytest.mark.parametrize("reference", ["", "  \t "])
def test_blank_reference_does_not_read_repository(monkeypatch, reference):
    client, repository = _client(monkeypatch)
    response = client.get(_url(reference), headers=summary.HEADERS)
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls == []


def test_malformed_client_id_is_rejected_before_read(monkeypatch):
    client, repository = _client(monkeypatch)
    response = client.get(_url().replace(str(summary.CLIENT_ID), "not-a-uuid"), headers=summary.HEADERS)
    assert response.status_code == 422
    assert repository.calls == []


@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE"])
def test_reference_review_exposes_no_mutation_method(monkeypatch, method):
    client, repository = _client(monkeypatch)
    assert client.request(method, _url(), headers=summary.HEADERS).status_code == 405
    assert repository.calls == []


@pytest.mark.parametrize("surface", ["public", "client"])
def test_reference_review_has_no_self_service_alias(monkeypatch, surface):
    client, repository = _client(monkeypatch)
    response = client.get(_url().replace("/management/", f"/{surface}/"), headers=summary.HEADERS)
    assert response.status_code == 404
    assert repository.calls == []
