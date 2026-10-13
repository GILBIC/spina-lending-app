from uuid import uuid4

import pytest
from test_accounting_book_api import HEADERS, FakeAccounts
from test_loan_payout_accounting_api import BASE, PAYOUT, MemoryPayouts, client_for


class Renewals(MemoryPayouts):
    def renewal_measurement_review(self, actor, **values):
        return self.invoke("renewal_measurement_review", actor, **values)

    def retain_renewal_measurement(self, actor, **values):
        return self.invoke("retain_renewal_measurement", actor, **values)


def body():
    return {
        "request_id": str(uuid4()),
        "source_digest": "a" * 64,
        "evidence_id": str(uuid4()),
        "confirm": True,
        "review": {
            "decision": "modification_no_derecognition",
            "accounting_policy_reference": "test:explicit-policy",
            "qualitative_assessment": {
                "cash_flow_terms_reviewed": True,
                "substantial_change_assessed": True,
                "signed_contract_reviewed": True,
                "decision_basis": "Explicit substantive test assessment of signed contractual changes.",
            },
            "decision_rationale": "Explicit qualitative and quantitative retained treatment review.",
            "settlement_consideration": "980.00",
            "settlement_rebate": "20.00",
            "settlement_basis": "Signed old-asset settlement and rebate are independently reviewed.",
        },
    }


@pytest.mark.parametrize("mobile", [False, True])
def test_renewal_review_is_private_read_only_and_explicit(mobile):
    repository = Renewals()
    client, _ = client_for(repository=repository)
    prefix = BASE.replace("/api/v1/", "/api/mobile/v1/") if mobile else BASE
    path = f"{prefix}/payouts/{PAYOUT}/renewal-measurement"
    assert client.get(path).status_code == 401
    assert not repository.calls
    response = client.get(path, headers=HEADERS)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls[0][0] == "renewal_measurement_review"
    response = client.post(path, headers=HEADERS, json=body())
    assert response.status_code == 200
    values = repository.calls[-1][2]
    assert values["review"]["decision"] == "modification_no_derecognition"
    assert values["review"]["settlement_consideration"] == "980.00"
    assert "confirm" not in values


@pytest.mark.parametrize(
    "change",
    [
        "confirm",
        "decision",
        "qualitative",
        "contract",
        "fair_value",
        "actor",
        "carrying",
    ],
)
def test_renewal_review_rejects_missing_choice_or_invented_source_values(change):
    repository = Renewals()
    client, _ = client_for(repository=repository)
    payload = body()
    if change == "confirm":
        payload["confirm"] = False
    elif change == "decision":
        payload["review"].pop("decision")
    elif change == "qualitative":
        payload["review"]["qualitative_assessment"]["substantial_change_assessed"] = (
            False
        )
    elif change == "fair_value":
        payload["review"]["decision"] = "derecognition"
    elif change == "contract":
        payload["review"]["qualitative_assessment"].pop("signed_contract_reviewed")
    elif change == "actor":
        payload["actor_user_id"] = str(uuid4())
    else:
        payload["review"]["old_gross_carrying"] = "1.00"
    response = client.post(
        f"{BASE}/payouts/{PAYOUT}/renewal-measurement", headers=HEADERS, json=payload
    )
    assert response.status_code in {409, 422}
    assert not repository.calls


def test_renewal_review_rejects_collector_role():
    repository = Renewals()
    client, _ = client_for(
        accounts=FakeAccounts(role="collector"), repository=repository
    )
    assert (
        client.post(
            f"{BASE}/payouts/{PAYOUT}/renewal-measurement", headers=HEADERS, json=body()
        ).status_code
        == 403
    )
    assert not repository.calls
