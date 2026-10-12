"""Risk identity and forecast inputs cross the API without client authority."""

from copy import deepcopy

import pytest
from test_elapsed_period_assessment_api import (
    ACTOR,
    BASE,
    BODY,
    HEADERS,
    LOAN,
    PERIOD,
    PERMISSIONS,
    FakeAccounts,
    MemoryAssessments,
    client_for,
)


class RiskAssessments(MemoryAssessments):
    prepare_risk = MemoryAssessments.prepare


def risk_body():
    result = deepcopy(BODY)
    result.pop("risk_review")
    return result | {"credit_risk_review_id": 10, "confirm": True}


@pytest.mark.parametrize("base", [BASE, BASE.replace("/api/v1/", "/api/mobile/v1/")])
def test_retained_risk_preparation_preserves_identity_and_exact_receipts(base):
    repo = RiskAssessments()
    with client_for(repo) as client:
        response = client.post(
            base + f"/{PERIOD}/loans/{LOAN}/prepare-risk",
            headers=HEADERS,
            json=risk_body(),
        )
    assert response.status_code == 200
    assert repo.writes[0]["actor_user_id"] == ACTOR
    assert repo.writes[0]["credit_risk_review_id"] == 10
    assert (
        repo.writes[0]["scenarios"][0]["expected_cash_flows"][0]["amount"]
        == "9999999999999999.99"
    )


@pytest.mark.parametrize(
    "field,value,status",
    [
        ("credit_risk_review_id", True, 422),
        ("credit_risk_review_id", "10", 422),
        ("credit_risk_review_id", 0, 422),
        ("credit_risk_review_id", 1.5, 422),
        ("credit_risk_review_id", 9007199254740992, 422),
        ("confirm", "true", 422),
        ("confirm", False, 409),
        ("stage_label", "stage_2_lifetime", 422),
        ("default_label", False, 422),
        ("actor_user_id", str(ACTOR), 422),
        ("risk_review", BODY["risk_review"], 422),
    ],
)
def test_risk_preparation_rejects_inferred_or_client_owned_authority(
    field, value, status
):
    repo = RiskAssessments()
    with client_for(repo) as client:
        response = client.post(
            BASE + f"/{PERIOD}/loans/{LOAN}/prepare-risk",
            headers=HEADERS,
            json=risk_body() | {field: value},
        )
    assert response.status_code == status
    assert repo.writes == []


@pytest.mark.parametrize(
    "role,permissions,status",
    [
        ("client", PERMISSIONS, "active"),
        ("management", (), "active"),
        ("management", PERMISSIONS, "inactive"),
    ],
)
def test_risk_preparation_requires_current_authority(role, permissions, status):
    repo = RiskAssessments()
    with client_for(
        repo, FakeAccounts(role=role, permissions=permissions, status=status)
    ) as client:
        response = client.post(
            BASE + f"/{PERIOD}/loans/{LOAN}/prepare-risk",
            headers=HEADERS,
            json=risk_body(),
        )
    assert response.status_code == 403
    assert repo.writes == []
