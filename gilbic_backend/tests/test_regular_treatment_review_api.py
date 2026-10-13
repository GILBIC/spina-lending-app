from uuid import uuid4

import pytest
from test_accounting_book_api import ACTOR, HEADERS, FakeAccounts
from test_treasury_application_accounting_api import (
    APPLICATION,
    BASE,
    MemoryApplications,
    client_for,
)


class Treatments(MemoryApplications):
    def payoff_candidate(self, actor, **values):
        return self.invoke("payoff_candidate", actor, **values)

    def review_payoff(self, actor, **values):
        return self.invoke("review_payoff", actor, **values)

    def closed_term_candidate(self, actor, **values):
        return self.invoke("closed_term_candidate", actor, **values)

    def review_closed_term(self, actor, **values):
        return self.invoke("review_closed_term", actor, **values)


@pytest.mark.parametrize(
    "kind,treatment",
    [
        ("payoff", "full_contractual_payoff_no_rebate"),
        ("closed-term", "original_eir_through_maturity_no_extension"),
    ],
)
def test_retained_treatment_requires_explicit_confirmation_and_server_actor(
    kind, treatment
):
    repo = Treatments()
    client, _ = client_for(repository=repo)
    path = f"{BASE}/applications/{APPLICATION}/{kind}-review"
    body = {
        "source_digest": "a" * 64,
        "request_id": str(uuid4()),
        "treatment": treatment,
        "contract_evidence_reference": "SIGNED-CONTRACT",
        "review_rationale": "I reviewed the exact signed original contractual treatment.",
    }
    assert client.post(path, headers=HEADERS, json=body).status_code == 409
    assert (
        client.post(path, headers=HEADERS, json=body | {"confirm": "true"}).status_code
        == 422
    )
    assert repo.calls == []
    response = client.post(path, headers=HEADERS, json=body | {"confirm": True})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert repo.calls[0][1] == ACTOR
    assert repo.calls[0][2]["treatment"] == treatment


@pytest.mark.parametrize(
    "kind,treatment",
    [
        ("payoff", "full_contractual_payoff_no_rebate"),
        ("closed-term", "original_eir_through_maturity_no_extension"),
    ],
)
@pytest.mark.parametrize(
    "extra",
    [
        {"cash_amount": "1.00"},
        {"rate": "0.01"},
        {"account_code": "4030"},
        {"actor_user_id": str(uuid4())},
    ],
)
def test_treatment_never_accepts_invented_financial_coordinates(kind, treatment, extra):
    repo = Treatments()
    client, _ = client_for(repository=repo)
    response = client.post(
        f"{BASE}/applications/{APPLICATION}/{kind}-review",
        headers=HEADERS,
        json={
            "source_digest": "a" * 64,
            "request_id": str(uuid4()),
            "treatment": treatment,
            "contract_evidence_reference": "SIGNED-CONTRACT",
            "review_rationale": "I reviewed the exact original contractual treatment.",
            "confirm": True,
        }
        | extra,
    )
    assert response.status_code == 422
    assert repo.calls == []


@pytest.mark.parametrize("kind", ["payoff", "closed-term"])
def test_treatment_requires_current_management_authority_even_on_read(kind):
    repo = Treatments()
    client, _ = client_for(
        accounts=FakeAccounts(permissions=("accounting.view",)), repository=repo
    )
    assert (
        client.get(
            f"{BASE}/applications/{APPLICATION}/{kind}-review", headers=HEADERS
        ).status_code
        == 403
    )
    assert repo.calls == []
