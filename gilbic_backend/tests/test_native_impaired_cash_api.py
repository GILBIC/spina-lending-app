"""Dated cash reviews accept forecasts, never client accounting authority."""

from copy import deepcopy
from uuid import UUID

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

APPLICATION = UUID("409fcb29-fedd-4309-8f77-b51ee9b9af72")


class CashReviews(MemoryAssessments):
    review_impaired_cash = MemoryAssessments.prepare
    load_impaired_cash = MemoryAssessments.load_candidate


def cash_body():
    body = deepcopy(BODY)
    body.pop("risk_review")
    return body | {"confirm": True}


@pytest.mark.parametrize("base", [BASE, BASE.replace("/api/v1/", "/api/mobile/v1/")])
def test_impaired_cash_review_binds_real_application_and_exact_forecasts(base):
    repo = CashReviews()
    with client_for(repo) as client:
        response = client.post(
            base + f"/{PERIOD}/loans/{LOAN}/impaired-cash/{APPLICATION}/review",
            headers=HEADERS,
            json=cash_body(),
        )
    assert response.status_code == 200
    assert repo.writes[0]["actor_user_id"] == ACTOR
    assert repo.writes[0]["application_id"] == APPLICATION
    assert repo.writes[0]["scenarios"] == cash_body()["scenarios"]


@pytest.mark.parametrize(
    "extra,status",
    [
        ({"confirm": False}, 409),
        ({"confirm": "true"}, 422),
        ({"target_allowance": "1.00"}, 422),
        ({"daily_eir": "0.01"}, 422),
        ({"full_payoff": True}, 422),
        ({"stage_label": "stage_3_credit_impaired"}, 422),
        ({"actor_user_id": str(ACTOR)}, 422),
        ({"as_of_date": "2030-01-01"}, 422),
    ],
)
def test_impaired_cash_rejects_client_dates_targets_or_posting_authority(extra, status):
    repo = CashReviews()
    with client_for(repo) as client:
        response = client.post(
            BASE + f"/{PERIOD}/loans/{LOAN}/impaired-cash/{APPLICATION}/review",
            headers=HEADERS,
            json=cash_body() | extra,
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
def test_impaired_cash_review_requires_current_management_authority(
    role, permissions, status
):
    repo = CashReviews()
    with client_for(
        repo, FakeAccounts(role=role, permissions=permissions, status=status)
    ) as client:
        response = client.post(
            BASE + f"/{PERIOD}/loans/{LOAN}/impaired-cash/{APPLICATION}/review",
            headers=HEADERS,
            json=cash_body(),
        )
    assert response.status_code == 403
    assert repo.writes == []
