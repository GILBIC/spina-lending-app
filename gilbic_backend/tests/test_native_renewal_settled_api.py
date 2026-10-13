"""Old-segment zero review binds the exact protected renewal identity."""

from uuid import uuid4

import pytest
from test_elapsed_period_assessment_api import (
    BASE,
    BODY,
    HEADERS,
    LOAN,
    PERIOD,
    MemoryAssessments,
    client_for,
)


class RenewedAssessments(MemoryAssessments):
    prepare_renewed = MemoryAssessments.prepare


def request_body():
    return {
        "expected_book_id": BODY["expected_book_id"],
        "source_digest": BODY["source_digest"],
        "renewal_review_id": str(uuid4()),
        "review_rationale": "Reviewed exact protected renewal and zero old-segment exposure.",
        "confirm": True,
    }


@pytest.mark.parametrize("base", [BASE, BASE.replace("/api/v1/", "/api/mobile/v1/")])
def test_renewal_zero_review_uses_separate_identity_and_explicit_confirmation(base):
    repo = RenewedAssessments()
    body = request_body()
    with client_for(repo) as client:
        response = client.post(
            base + f"/{PERIOD}/loans/{LOAN}/prepare-renewed", headers=HEADERS, json=body
        )
    assert response.status_code == 200
    assert str(repo.writes[0]["renewal_review_id"]) == body["renewal_review_id"]
    assert "payoff_review_id" not in repo.writes[0]


@pytest.mark.parametrize(
    "change,status",
    [
        ({"confirm": False}, 409),
        ({"confirm": "true"}, 422),
        ({"renewal_review_id": "invalid"}, 422),
        ({"payoff_review_id": str(uuid4())}, 422),
        ({"scenarios": []}, 422),
        ({"gross_carrying_amount": "0.00"}, 422),
        ({"review_rationale": "short"}, 422),
    ],
)
def test_renewal_zero_review_cannot_supply_settlement_values(change, status):
    repo = RenewedAssessments()
    with client_for(repo) as client:
        response = client.post(
            BASE + f"/{PERIOD}/loans/{LOAN}/prepare-renewed",
            headers=HEADERS,
            json=request_body() | change,
        )
    assert response.status_code == status
    assert repo.writes == []
