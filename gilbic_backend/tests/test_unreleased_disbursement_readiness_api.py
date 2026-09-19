from dataclasses import replace
from uuid import UUID

from test_loan_disbursement_evidence_api import client_with_fakes, headers


def test_readiness_keeps_unreleased_date_null_alongside_released_legacy_loan():
    client, repository = client_with_fakes()
    released = repository.list_readiness()[0]
    pending = replace(
        released,
        loan_id=UUID("66666666-6666-4666-8666-666666666666"),
        loan_number="FIRST-UNRELEASED",
        date_released=None,
        loan_status="approved_pending_docs",
        disbursement_event_id=None,
        event_kind=None,
        business_date=None,
        disbursed_at=None,
        cash_disbursed_amount=None,
        settlement_amount=None,
        other_deduction_amount=None,
        funding_account_system_key=None,
        external_reference=None,
        readiness_status="missing_disbursement_evidence",
        source_event_key=None,
    )
    repository.list_readiness = lambda **kwargs: (pending, released)

    response = client.get(
        "/api/v1/management/accounting/loan-disbursements/readiness",
        headers=headers(),
    )

    assert response.status_code == 200
    items = response.json()["data"]["events"]
    assert items[0]["date_released"] is None
    assert items[0]["loan_status"] == "approved_pending_docs"
    assert items[0]["disbursement_event_id"] is None
    assert items[0]["business_date"] is None
    assert items[0]["cash_disbursed_amount"] is None
    assert items[1]["date_released"] == "2026-08-11"
    assert items[1]["loan_status"] == "active"
    assert items[1]["cash_disbursed_amount"] == "5000.00"
