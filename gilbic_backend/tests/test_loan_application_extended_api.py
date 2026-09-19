"""Additive declared facts travel through the existing draft routes unchanged."""
from copy import deepcopy

import pytest

from test_loan_application_draft_api import (
    HEADERS as CREATE_HEADERS, URL as CREATE_URL, _body as create_body,
    _client as create_client,
)
from test_loan_application_append_draft_api import (
    HEADERS as APPEND_HEADERS, URL as APPEND_URL, _body as append_body,
    _client as append_client,
)
from test_loan_application_extended_information import _details


@pytest.mark.parametrize("append", [False, True])
def test_existing_draft_endpoint_preserves_additional_facts_and_limited_missing_fields(append):
    client, repository = append_client() if append else create_client()
    body = append_body() if append else create_body()
    body["information"]["details"] = _details()
    response = client.post(APPEND_URL if append else CREATE_URL,
                           headers=APPEND_HEADERS if append else CREATE_HEADERS, json=body)
    assert response.status_code == (200 if append else 201), response.text
    assert response.json()["information"]["details"] == _details()
    assert repository.calls[0]["information"].model_dump(mode="json")["details"] == _details()
    assert all(field.startswith(("request.", "repayment.")) for field in response.json()["missing_fields"])
    assert response.json()["review_scope"] == "loan_application_information_only"


@pytest.mark.parametrize("append", [False, True])
def test_legacy_requests_keep_legacy_response_shape(append):
    client, repository = append_client() if append else create_client()
    body = append_body() if append else create_body()
    response = client.post(APPEND_URL if append else CREATE_URL,
                           headers=APPEND_HEADERS if append else CREATE_HEADERS, json=body)
    assert response.status_code == (200 if append else 201)
    assert set(response.json()["information"]) == {"request", "repayment"}
    assert set(repository.calls[0]["information"].model_dump(mode="json")) == {"request", "repayment"}


@pytest.mark.parametrize("append", [False, True])
@pytest.mark.parametrize("changes", [
    {"schema_version": "1"}, {"schema_version": 2}, {"references": {}},
    {"employment": {"contact_number": 123}}, {"verified": True},
    {"references": [{"full_name": True}]},
])
def test_untyped_or_authoritative_claims_are_rejected_before_repository(append, changes):
    client, repository = append_client() if append else create_client()
    body = append_body() if append else create_body()
    body["information"]["details"] = {**deepcopy(_details()), **changes}
    response = client.post(APPEND_URL if append else CREATE_URL,
                           headers=APPEND_HEADERS if append else CREATE_HEADERS, json=body)
    assert response.status_code == 422, response.text
    assert repository.calls == []
