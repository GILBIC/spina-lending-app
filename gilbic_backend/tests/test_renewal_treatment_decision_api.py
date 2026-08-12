from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.renewal_treatment_decision_api import (
    renewal_treatment_decision_repository_dependency,
)
from gilbic_backend.renewal_treatment_decision_repository import (
    RenewalTreatmentDecisionRecord,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
OLD_LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
NEW_LOAN_ID = UUID("55555555-5555-4555-8555-555555555555")
EXECUTION_ID = UUID("66666666-6666-4666-8666-666666666666")
DECISION_ID = UUID("77777777-7777-4777-8777-777777777777")
VOID_ID = UUID("88888888-8888-4888-8888-888888888888")
SCHEDULE_ID = UUID("99999999-9999-4999-8999-999999999999")
REVIEW_TOKEN = "a" * 64
RENEWAL_DATE = date(2026, 8, 31)


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "management-token"
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="management@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == "management-device"
        return AccountContext(
            user_id=MANAGEMENT_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username="management.one",
            email="management@example.com",
            full_name="Management One",
            status="active",
            roles=("management",),
            permissions=(
                "accounting.view",
                "accounting.renewal_treatment_decision.manage",
            ),
            device_registered=True,
        )


def _record(*, active: bool = True) -> RenewalTreatmentDecisionRecord:
    return RenewalTreatmentDecisionRecord(
        decision_id=DECISION_ID,
        renewal_execution_event_id=EXECUTION_ID,
        old_loan_id=OLD_LOAN_ID,
        old_loan_number="OLD-001",
        new_loan_id=NEW_LOAN_ID,
        new_loan_number="NEW-001",
        client_id=CLIENT_ID,
        client_code="C-001",
        client_name="Test Borrower",
        renewal_business_date=RENEWAL_DATE,
        readiness_review_token=REVIEW_TOKEN,
        readiness_policy_version="renewal_accounting_treatment_readiness_v1",
        decision="modification_no_derecognition",
        decision_policy_version="renewal_treatment_decision_evidence_v1",
        accounting_policy_reference="PFRS 9 renewal modification policy v1",
        qualitative_assessment={
            "legal_terms_reviewed": True,
            "borrower_identity_continues": True,
            "qualitative_conclusion": "same financial asset continues",
        },
        decision_rationale=(
            "Management reviewed the contractual and qualitative evidence and concluded "
            "that the existing financial asset continues without derecognition."
        ),
        supporting_evidence_reference="RENEWAL-REVIEW-001",
        old_gross_carrying_amount=Decimal("2000.00"),
        original_daily_eir=Decimal("0.001000000000"),
        renewal_cash_disbursed_amount=Decimal("1000.00"),
        renewal_settlement_amount=Decimal("1000.00"),
        renewal_other_deduction_amount=Decimal("0.00"),
        schedule_id=SCHEDULE_ID,
        schedule_version=1,
        contract_reference="SIGNED-RENEWAL-001",
        contract_evidence_reference="SIGNED-RENEWAL-001",
        installment_count=4,
        contractual_cash_total=Decimal("2400.00"),
        present_value_at_original_eir=Decimal("2227.92"),
        present_value_change_amount=Decimal("227.92"),
        present_value_change_percent=Decimal("11.396000"),
        reviewed_by_user_id=MANAGEMENT_USER_ID,
        reviewed_at=datetime(2026, 8, 31, 3, 0, tzinfo=timezone.utc),
        void_id=None if active else VOID_ID,
        void_reason=None if active else "correct reviewed policy evidence",
        voided_by_user_id=None if active else MANAGEMENT_USER_ID,
        voided_at=(
            None
            if active
            else datetime(2026, 8, 31, 4, 0, tzinfo=timezone.utc)
        ),
        is_active=active,
        automatic_classification_enabled=False,
        quantitative_threshold_decisive=False,
        journal_lines_enabled=False,
        automatic_source_posting=False,
    )


class FakeRepository:
    def __init__(self) -> None:
        self.record_calls: list[dict] = []
        self.void_calls: list[dict] = []

    def get_for_execution(self, *, renewal_execution_event_id: UUID, active_only: bool = False):
        assert renewal_execution_event_id == EXECUTION_ID
        assert active_only is False
        return (_record(),)

    def record(self, **kwargs):
        self.record_calls.append(kwargs)
        return _record()

    def void(self, **kwargs):
        self.void_calls.append(kwargs)
        return _record(active=False)


def _client(repository: FakeRepository) -> TestClient:
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts()
    app.dependency_overrides[
        renewal_treatment_decision_repository_dependency
    ] = lambda: repository
    return TestClient(app)


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer management-token",
        "X-Device-Id": "management-device",
    }


def _body(*, confirm: bool) -> dict[str, object]:
    return {
        "expected_review_token": REVIEW_TOKEN,
        "decision": "modification_no_derecognition",
        "accounting_policy_reference": "PFRS 9 renewal modification policy v1",
        "qualitative_assessment": {
            "legal_terms_reviewed": True,
            "borrower_identity_continues": True,
            "qualitative_conclusion": "same financial asset continues",
        },
        "decision_rationale": (
            "Management reviewed the contractual and qualitative evidence and concluded "
            "that the existing financial asset continues without derecognition."
        ),
        "supporting_evidence_reference": "RENEWAL-REVIEW-001",
        "confirm": confirm,
    }


def test_management_can_list_immutable_decision_evidence() -> None:
    repository = FakeRepository()
    response = _client(repository).get(
        f"/api/v1/management/accounting/renewals/{EXECUTION_ID}/treatment-decisions",
        headers=_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["decisions"]) == 1
    decision = data["decisions"][0]
    assert decision["decision"] == "modification_no_derecognition"
    assert decision["present_value_change_percent"] == "11.396000"
    assert decision["automatic_classification_enabled"] is False
    assert decision["quantitative_threshold_decisive"] is False
    assert decision["journal_lines_enabled"] is False
    assert decision["automatic_source_posting"] is False
    assert decision["evidence_only"] is True
    assert decision["treatment_journal_coordinates_enabled"] is False


def test_record_requires_explicit_management_confirmation() -> None:
    repository = FakeRepository()
    response = _client(repository).post(
        f"/api/v1/management/accounting/renewals/{EXECUTION_ID}/treatment-decisions",
        headers=_headers(),
        json=_body(confirm=False),
    )

    assert response.status_code == 409
    assert repository.record_calls == []
    assert response.json()["detail"]["code"] == (
        "renewal_treatment_decision_confirmation_required"
    )


def test_management_records_explicit_evidence_only_decision() -> None:
    repository = FakeRepository()
    response = _client(repository).post(
        f"/api/v1/management/accounting/renewals/{EXECUTION_ID}/treatment-decisions",
        headers=_headers(),
        json=_body(confirm=True),
    )

    assert response.status_code == 200
    assert len(repository.record_calls) == 1
    call = repository.record_calls[0]
    assert call["renewal_execution_event_id"] == EXECUTION_ID
    assert call["actor_user_id"] == MANAGEMENT_USER_ID
    assert call["expected_review_token"] == REVIEW_TOKEN
    assert call["decision"] == "modification_no_derecognition"
    data = response.json()["data"]
    assert data["is_active"] is True
    assert data["automatic_classification_enabled"] is False
    assert data["journal_lines_enabled"] is False
    assert data["automatic_source_posting"] is False
    assert "evidence only" in response.json()["notice"]


def test_void_requires_confirmation_and_preserves_original_history() -> None:
    repository = FakeRepository()
    client = _client(repository)
    unconfirmed = client.post(
        f"/api/v1/management/accounting/renewal-treatment-decisions/{DECISION_ID}/void",
        headers=_headers(),
        json={"reason": "correct reviewed evidence", "confirm": False},
    )
    assert unconfirmed.status_code == 409
    assert repository.void_calls == []

    confirmed = client.post(
        f"/api/v1/management/accounting/renewal-treatment-decisions/{DECISION_ID}/void",
        headers=_headers(),
        json={"reason": "correct reviewed evidence", "confirm": True},
    )
    assert confirmed.status_code == 200
    assert len(repository.void_calls) == 1
    assert confirmed.json()["data"]["decision_id"] == str(DECISION_ID)
    assert confirmed.json()["data"]["is_active"] is False
    assert confirmed.json()["data"]["void_id"] == str(VOID_ID)
    assert "original reviewed decision remains immutable" in confirmed.json()["notice"]
