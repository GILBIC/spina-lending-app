import logging
from urllib.parse import quote

import pytest
from test_client_onboarding_case_api import APPLICANT, REFERENCE, _case_client
from test_client_onboarding_cif_selection_api import ACTOR_ID, HEADERS, _client

BASE = "/api/v1/management/onboarding/applicants"
ITEM_KEYS = {
    "applicant_id",
    "intake_reference",
    "client_id",
    "full_name",
    "phone_number",
    "intake_status",
    "created_at",
    "updated_at",
}
APP_KEYS = {
    "application_id",
    "application_reference",
    "client_id",
    "created_at",
    "application_version_id",
    "version_number",
    "recorded_at",
}


def _url(applications):
    return (
        BASE + "/by-reference/" + quote(REFERENCE, safe="") + "/applications"
        if applications
        else BASE
    )


def _finder(*, denied=False, missing=False, unpromoted=False, failed=False, **options):
    from gilbic_backend.client_onboarding_api import (
        client_onboarding_repository_dependency,
    )

    client, _ = _client(**options)

    class ReadsOnly:
        def _read(self, kwargs, applications):
            self.calls.append(kwargs)
            if failed:
                raise RuntimeError("PRIVATE-DATABASE-ERROR")
            if denied:
                from gilbic_backend.client_onboarding_repository import (
                    ClientOnboardingAccessDenied,
                )

                raise ClientOnboardingAccessDenied("PRIVATE-DENIAL")
            if missing:
                return None
            item = dict.fromkeys(APP_KEYS if applications else ITEM_KEYS)
            item.update({"private_evidence": "PRIVATE-SECRET", "client_id": None})
            if not applications:
                item.update(
                    applicant_id=APPLICANT,
                    intake_reference=REFERENCE,
                    full_name="Synthetic name",
                    phone_number="00000000000",
                    intake_status="under_verification",
                )
            result = {
                "items": [] if unpromoted else [item],
                "next_cursor": None,
                "has_more": False,
                "as_of": "2026-10-04T00:00:00Z",
                "private_draft": "PRIVATE-DRAFT",
            }
            if applications:
                result["intake"] = {
                    "applicant_id": APPLICANT,
                    "intake_reference": REFERENCE,
                    "client_id": None,
                    "intake_status": "under_verification",
                    "private_evidence": "PRIVATE-SECRET",
                }
            return result

        def search_office_cases(self, **kwargs):
            return self._read(kwargs, False)

        def list_office_applications(self, **kwargs):
            return self._read(kwargs, True)

    repository = ReadsOnly()
    repository.calls = []
    client.app.dependency_overrides[client_onboarding_repository_dependency] = lambda: (
        repository
    )
    return client, repository


@pytest.mark.parametrize("applications", [False, True])
@pytest.mark.parametrize("role", ["employee", "management"])
def test_protected_reads_use_current_actor_and_allowlisted_projection(
    role, applications
):
    client, repository = _finder(role=role)
    response = client.get(_url(applications), headers=HEADERS)
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"items", "next_cursor", "has_more", "as_of"} | (
        {"intake"} if applications else set()
    )
    assert set(payload["items"][0]) == (APP_KEYS if applications else ITEM_KEYS)
    assert repository.calls[0]["actor_user_id"] == ACTOR_ID
    assert repository.calls[0]["limit"] == 25
    assert "PRIVATE-" not in response.text
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("applications", [False, True])
@pytest.mark.parametrize(
    "options,status",
    [
        ({"permissions": ()}, 403),
        ({"role": "client"}, 403),
        ({"role": "collector"}, 403),
        ({"account_error": "AccountDisabled"}, 403),
        ({"account_error": "DeviceRevoked"}, 403),
        ({"denied": True}, 403),
    ],
)
def test_current_authorization_denies_both_reads_without_private_details(
    applications, options, status
):
    client, repository = _finder(**options)
    response = client.get(_url(applications), headers=HEADERS)
    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"
    assert "PRIVATE-" not in response.text
    if not options.get("denied"):
        assert not repository.calls


@pytest.mark.parametrize("applications", [False, True])
@pytest.mark.parametrize(
    "omitted,status", [("Authorization", 401), ("X-Device-Id", 400)]
)
def test_authentication_and_device_required(applications, omitted, status):
    client, repository = _finder()
    response = client.get(
        _url(applications), headers={k: v for k, v in HEADERS.items() if k != omitted}
    )
    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"
    assert not repository.calls


@pytest.mark.parametrize(
    "params",
    [
        {"q": "ab"},
        {"q": "x" * 201},
        {"status": "approved"},
        {"limit": "0"},
        {"limit": "101"},
        {"limit": "1.5"},
        {"cursor": "x" * 2049},
        {"unknown": "PRIVATE-INPUT"},
        {"q": ["abc", "def"]},
    ],
)
def test_invalid_search_shapes_are_private_and_do_not_broaden_reads(params):
    client, repository = _finder()
    response = client.get(BASE, params=params, headers=HEADERS)
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert "PRIVATE-INPUT" not in response.text
    assert not repository.calls


def test_trimmed_query_and_filters_are_forwarded_explicitly():
    client, repository = _finder()
    assert (
        client.get(
            BASE,
            params={"q": "  Alice  ", "status": "under_verification", "limit": "100"},
            headers=HEADERS,
        ).status_code
        == 200
    )
    assert repository.calls == [
        {
            "actor_user_id": ACTOR_ID,
            "q": "Alice",
            "status": "under_verification",
            "limit": 100,
            "cursor": None,
        }
    ]


def test_unpromoted_intake_has_verified_context_and_empty_applications():
    client, repository = _finder(unpromoted=True)
    response = client.get(_url(True), headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["intake"] == {
        "applicant_id": str(APPLICANT),
        "intake_reference": REFERENCE,
        "client_id": None,
        "intake_status": "under_verification",
    }
    assert repository.calls[0]["application_reference"] == REFERENCE


def test_missing_exact_intake_returns_private_404():
    client, _ = _finder(missing=True)
    response = client.get(_url(True), headers=HEADERS)
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("applications", [False, True])
def test_unexpected_read_failure_is_private_and_no_store(applications):
    from fastapi.testclient import TestClient

    client, _ = _finder(failed=True)
    response = TestClient(client.app, raise_server_exceptions=False).get(
        _url(applications), headers=HEADERS
    )
    assert response.status_code == 500
    assert response.headers.get("cache-control") == "no-store"
    assert response.text == "Internal Server Error"


def test_encoded_slash_case_route_still_reaches_existing_reader():
    client, repository = _case_client()
    response = client.get(
        BASE + "/by-reference/" + quote(REFERENCE, safe="") + "/case", headers=HEADERS
    )
    assert response.status_code == 200
    assert repository.calls[0]["application_reference"] == REFERENCE


def test_uvicorn_access_log_does_not_record_search_terms_or_intake_reference(caplog):
    client, _ = _finder()
    client.get(BASE, headers=HEADERS)  # Construct the real middleware stack.
    logger = logging.getLogger("uvicorn.access")
    with caplog.at_level(logging.INFO, logger="uvicorn.access"):
        logger.info(
            '%s - "%s %s HTTP/%s" %d',
            "127.0.0.1",
            "GET",
            BASE + "?q=PRIVATE-PHONE",
            "1.1",
            200,
        )
        logger.info(
            '%s - "%s %s HTTP/%s" %d',
            "127.0.0.1",
            "GET",
            BASE + "/by-reference/PRIVATE-NAME/applications?cursor=PRIVATE-CURSOR",
            "1.1",
            200,
        )
    messages = [r.getMessage() for r in caplog.records if r.name == "uvicorn.access"]
    assert len(messages) == 2
    assert all("PRIVATE-" not in message for message in messages)
