from __future__ import annotations

from urllib.parse import quote
from uuid import UUID

import pytest

from test_client_onboarding_cif_selection_api import ACTOR_ID, HEADERS, _client


APPLICANT = UUID("44444444-4444-4444-8444-444444444444")
REFERENCE = "Office / MiXeD Case"
REVIEW = "client_onboarding.requirement.review"
VISIT = "client_onboarding.visit.record"


def _record():
    return {
        "applicant_id": APPLICANT, "application_reference": REFERENCE,
        "status": "under_verification", "full_name": "Synthetic Applicant",
        "phone_number": "00000000000", "email": None,
        "present_address": "Synthetic office test address", "client_id": None,
        "requirements": {
            "national_id": {"status": "passed", "evidence_reference": "external-national-id"},
            "tin_id": {"status": "failed", "evidence_reference": "external-tin"},
            "meralco_bill": {"status": "pending", "evidence_reference": "external-bill"},
            "collector_visit": {"status": "pending", "note": None, "evidence_reference": None},
        },
        "privacy_consent": True, "accuracy_declaration": True,
        "bypassed_requirements": [], "bypass_reason": None,
    }


def _url(scope="office", reference=REFERENCE):
    prefix = "management" if scope == "office" else "collector"
    suffix = "case" if scope == "office" else "visit-case"
    return f"/api/v1/{prefix}/onboarding/applicants/by-reference/{quote(reference, safe='')}/{suffix}"


def _case_client(*, scope="office", missing=False, denied=False, **options):
    from gilbic_backend.client_onboarding_api import client_onboarding_repository_dependency

    options.setdefault("role", "employee" if scope == "office" else "collector")
    options.setdefault("permissions", (REVIEW,) if scope == "office" else (VISIT,))
    client, _ = _client(**options)

    class Repository:
        def __init__(self):
            self.calls = []

        def get_case_by_reference(self, **kwargs):
            self.calls.append(kwargs)
            if denied:
                from gilbic_backend.client_onboarding_repository import ClientOnboardingAccessDenied
                raise ClientOnboardingAccessDenied("Persisted actor is no longer authorized.")
            if missing:
                return None
            record = _record()
            # The API still owns its explicit allowlist when repositories evolve.
            record["private_auth_data"] = "PRIVATE-SECRET"
            record["collector_visit"] = record["requirements"]["collector_visit"]
            return record

    repository = Repository()
    client.app.dependency_overrides[client_onboarding_repository_dependency] = lambda: repository
    return client, repository


@pytest.mark.parametrize("role", ["employee", "management"])
def test_office_lookup_returns_exact_case_projection_and_persisted_actor(role):
    client, repository = _case_client(role=role)
    response = client.get(_url(reference=f"  {REFERENCE.lower()}  "), headers=HEADERS)
    assert response.status_code == 200
    expected = _record()
    expected["applicant_id"] = str(APPLICANT)
    assert response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls == [{"actor_user_id": ACTOR_ID, "application_reference": REFERENCE.lower(), "scope": "office"}]


def test_collector_gets_visit_identity_only_not_email_id_evidence_or_eligibility_details():
    client, repository = _case_client(scope="collector")
    response = client.get(_url("collector"), headers=HEADERS)
    assert response.status_code == 200
    record = _record()
    assert response.json() == {
        "applicant_id": str(APPLICANT), "application_reference": REFERENCE,
        "status": "under_verification", "full_name": record["full_name"],
        "phone_number": record["phone_number"], "present_address": record["present_address"],
        "collector_visit": record["requirements"]["collector_visit"],
    }
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls[0]["scope"] == "collector"
    assert "external-national-id" not in response.text
    assert "PRIVATE-" not in response.text


@pytest.mark.parametrize("scope", ["office", "collector"])
@pytest.mark.parametrize("reference", ["Ref%_exact", "Ref' OR 1=1 --", "Office/2026/MiXeD", "Long" * 180])
def test_reference_is_only_outer_trimmed_no_format_or_uuid_fallback(scope, reference):
    client, repository = _case_client(scope=scope, missing=True)
    response = client.get(_url(scope, f" {reference} "), headers=HEADERS)
    assert response.status_code == 404
    assert response.json() == {"detail": "Office intake record is unavailable."}
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls[0]["application_reference"] == reference


@pytest.mark.parametrize("scope,role,permissions", [
    ("office", "collector", (REVIEW,)), ("office", "client", (REVIEW,)),
    ("office", "employee", ()), ("office", "management", ("client_onboarding.bypass",)),
    ("collector", "employee", (VISIT,)), ("collector", "management", (VISIT,)),
    ("collector", "collector", (REVIEW,)), ("collector", "collector", (VISIT + ".extra",)),
])
def test_role_and_exact_permission_are_required_before_case_read(scope, role, permissions):
    client, repository = _case_client(scope=scope, role=role, permissions=permissions)
    response = client.get(_url(scope), headers=HEADERS)
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls == []


@pytest.mark.parametrize("scope", ["office", "collector"])
@pytest.mark.parametrize("omitted,status", [("Authorization", 401), ("X-Device-Id", 400)])
def test_active_authenticated_device_is_required(scope, omitted, status):
    client, repository = _case_client(scope=scope)
    headers = {key: value for key, value in HEADERS.items() if key != omitted}
    response = client.get(_url(scope), headers=headers)
    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls == []


@pytest.mark.parametrize("scope", ["office", "collector"])
def test_blank_reference_fails_before_repository(scope):
    client, repository = _case_client(scope=scope)
    response = client.get(_url(scope, "  \t "), headers=HEADERS)
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls == []


@pytest.mark.parametrize("scope", ["office", "collector"])
def test_persisted_authorization_denial_is_no_store(scope):
    client, _ = _case_client(scope=scope, denied=True)
    response = client.get(_url(scope), headers=HEADERS)
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert "Synthetic Applicant" not in response.text
