from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.loan_disbursement_evidence_api import (
    loan_disbursement_evidence_repository_dependency,
)
from gilbic_backend.loan_disbursement_evidence_repository import (
    LoanDisbursementEvidenceConflict,
    LoanDisbursementEvidenceRecord,
    LoanDisbursementReadinessRecord,
)
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
EVENT_ID = UUID("55555555-5555-4555-8555-555555555555")


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
                "accounting.loan_disbursement.evidence.manage",
            ),
            device_registered=True,
        )


class FakeEvidenceRepository:
    def __init__(self) -> None:
        self.record_request: dict[str, object] | None = None
        self.void_request: dict[str, object] | None = None
        self.error: Exception | None = None

    def list_readiness(self, **kwargs):
        if self.error is not None:
            raise self.error
        return (
            LoanDisbursementReadinessRecord(
                loan_id=LOAN_ID,
                loan_number="LN-0001",
                client_id=CLIENT_ID,
                client_code="C-0001",
                client_name="Test Borrower",
                loan_type_code="REGULAR",
                loan_type_name="Regular",
                calculation_mode="fixed_daily",
                principal=Decimal("5000.00"),
                date_released=date(2026, 8, 11),
                loan_status="active",
                disbursement_event_id=EVENT_ID,
                event_kind="new_loan_release",
                business_date=date(2026, 8, 11),
                disbursed_at=datetime(2026, 8, 11, 2, 30, tzinfo=timezone.utc),
                cash_disbursed_amount=Decimal("5000.00"),
                settlement_amount=Decimal("0.00"),
                other_deduction_amount=Decimal("0.00"),
                funding_account_system_key="cash_office",
                external_reference="RELEASE-0001",
                readiness_status="source_evidence_ready",
                source_event_key=f"loan_disbursement:{EVENT_ID}",
                journal_lines_enabled=False,
                automatic_source_posting=False,
            ),
        )

    def record(self, **kwargs) -> LoanDisbursementEvidenceRecord:
        if self.error is not None:
            raise self.error
        self.record_request = kwargs
        return self._event(is_voided=False)

    def void(self, **kwargs) -> LoanDisbursementEvidenceRecord:
        if self.error is not None:
            raise self.error
        self.void_request = kwargs
        return self._event(is_voided=True)

    @staticmethod
    def _event(*, is_voided: bool) -> LoanDisbursementEvidenceRecord:
        voided_at = (
            datetime(2026, 8, 11, 3, 0, tzinfo=timezone.utc)
            if is_voided
            else None
        )
        return LoanDisbursementEvidenceRecord(
            event_id=EVENT_ID,
            loan_id=LOAN_ID,
            loan_number="LN-0001",
            client_id=CLIENT_ID,
            client_code="C-0001",
            client_name="Test Borrower",
            event_kind="new_loan_release",
            business_date=date(2026, 8, 11),
            disbursed_at=datetime(2026, 8, 11, 2, 30, tzinfo=timezone.utc),
            cash_disbursed_amount=Decimal("5000.00"),
            settlement_amount=Decimal("0.00"),
            other_deduction_amount=Decimal("0.00"),
            funding_account_system_key="cash_office",
            external_reference="RELEASE-0001",
            evidence_note="Cash released at office",
            principal_snapshot=Decimal("5000.00"),
            date_released_snapshot=date(2026, 8, 11),
            loan_status_snapshot="active",
            recorded_by_user_id=MANAGEMENT_USER_ID,
            recorded_at=datetime(2026, 8, 11, 2, 31, tzinfo=timezone.utc),
            is_voided=is_voided,
            voided_by_user_id=MANAGEMENT_USER_ID if is_voided else None,
            voided_at=voided_at,
            void_reason="Wrong release reference" if is_voided else None,
        )


def client_with_fakes() -> tuple[TestClient, FakeEvidenceRepository]:
    repository = FakeEvidenceRepository()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts()
    app.dependency_overrides[loan_disbursement_evidence_repository_dependency] = (
        lambda: repository
    )
    return TestClient(app), repository


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer management-token",
        "X-Device-Id": "management-device",
    }


def test_management_can_read_disbursement_source_readiness() -> None:
    client, _ = client_with_fakes()
    response = client.get(
        "/api/v1/management/accounting/loan-disbursements/readiness",
        headers=headers(),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["journal_lines_enabled"] is False
    assert data["automatic_source_posting"] is False
    assert data["events"][0]["readiness_status"] == "source_evidence_ready"
    assert data["events"][0]["source_event_key"] == f"loan_disbursement:{EVENT_ID}"


def test_management_can_register_explicit_disbursement_evidence() -> None:
    client, repository = client_with_fakes()
    response = client.post(
        "/api/v1/management/accounting/loan-disbursements",
        headers=headers(),
        json={
            "loan_id": str(LOAN_ID),
            "event_kind": "new_loan_release",
            "business_date": "2026-08-11",
            "disbursed_at": "2026-08-11T10:30:00+08:00",
            "cash_disbursed_amount": "5000.00",
            "settlement_amount": "0.00",
            "other_deduction_amount": "0.00",
            "funding_account_system_key": "cash_office",
            "external_reference": "RELEASE-0001",
            "evidence_note": "Cash released at office",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["event_id"] == str(EVENT_ID)
    assert data["cash_disbursed_amount"] == "5000.00"
    assert data["journal_lines_enabled"] is False
    assert data["automatic_source_posting"] is False
    assert repository.record_request is not None
    assert repository.record_request["actor_user_id"] == MANAGEMENT_USER_ID
    assert repository.record_request["loan_id"] == LOAN_ID


def test_management_can_void_unposted_disbursement_evidence() -> None:
    client, repository = client_with_fakes()
    response = client.post(
        f"/api/v1/management/accounting/loan-disbursements/{EVENT_ID}/void",
        headers=headers(),
        json={"reason": "Wrong release reference"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["is_voided"] is True
    assert repository.void_request is not None
    assert repository.void_request["event_id"] == EVENT_ID
    assert repository.void_request["actor_user_id"] == MANAGEMENT_USER_ID


def test_different_active_evidence_returns_conflict() -> None:
    client, repository = client_with_fakes()
    repository.error = LoanDisbursementEvidenceConflict(
        "This loan already has different active disbursement evidence."
    )
    response = client.post(
        "/api/v1/management/accounting/loan-disbursements",
        headers=headers(),
        json={
            "loan_id": str(LOAN_ID),
            "event_kind": "new_loan_release",
            "business_date": "2026-08-11",
            "disbursed_at": "2026-08-11T10:30:00+08:00",
            "cash_disbursed_amount": "5000.00",
            "funding_account_system_key": "cash_office",
            "external_reference": "RELEASE-0001",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "loan_disbursement_evidence_conflict"
