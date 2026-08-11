from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.loan_renewal_execution_evidence_api import (
    loan_renewal_execution_evidence_repository_dependency,
)
from gilbic_backend.loan_renewal_execution_evidence_repository import (
    LoanRenewalExecutionEvidenceConflict,
    LoanRenewalExecutionEvidenceRecord,
    LoanRenewalExecutionReadinessRecord,
)
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
OLD_LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
NEW_LOAN_ID = UUID("55555555-5555-4555-8555-555555555555")
DISBURSEMENT_EVENT_ID = UUID("66666666-6666-4666-8666-666666666666")
EXECUTION_EVENT_ID = UUID("77777777-7777-4777-8777-777777777777")
RENEWAL_REQUEST_ID = UUID("88888888-8888-4888-8888-888888888888")


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
                "accounting.loan_renewal_execution.evidence.manage",
            ),
            device_registered=True,
        )


class FakeRenewalExecutionRepository:
    def __init__(self) -> None:
        self.record_request: dict[str, object] | None = None
        self.void_request: dict[str, object] | None = None
        self.error: Exception | None = None

    def list_readiness(self, **kwargs):
        if self.error is not None:
            raise self.error
        return (
            LoanRenewalExecutionReadinessRecord(
                disbursement_event_id=DISBURSEMENT_EVENT_ID,
                new_loan_id=NEW_LOAN_ID,
                new_loan_number="LN-NEW-0001",
                renewal_execution_event_id=EXECUTION_EVENT_ID,
                old_loan_id=OLD_LOAN_ID,
                old_loan_number="LN-OLD-0001",
                client_id=CLIENT_ID,
                client_code="C-0001",
                client_name="Test Borrower",
                renewal_request_id=RENEWAL_REQUEST_ID,
                renewal_request_status="approved",
                new_loan_type_code="REGULAR",
                new_loan_type_name="Regular",
                new_loan_calculation_mode="fixed_daily",
                new_loan_principal=Decimal("5000.00"),
                old_loan_principal=Decimal("5000.00"),
                release_business_date=date(2026, 8, 11),
                disbursed_at=datetime(2026, 8, 11, 2, 0, tzinfo=timezone.utc),
                cash_disbursed_amount=Decimal("2000.00"),
                settlement_amount=Decimal("3000.00"),
                other_deduction_amount=Decimal("0.00"),
                funding_account_system_key="cash_office",
                release_external_reference="RENEW-RELEASE-0001",
                execution_business_date=date(2026, 8, 11),
                executed_at=datetime(2026, 8, 11, 2, 5, tzinfo=timezone.utc),
                old_loan_settlement_amount=Decimal("3000.00"),
                execution_external_reference="RENEW-EXEC-0001",
                readiness_status="renewal_execution_evidence_ready",
                source_event_key=f"loan_renewal_execution:{EXECUTION_EVENT_ID}",
                journal_lines_enabled=False,
                automatic_source_posting=False,
            ),
        )

    def record(self, **kwargs) -> LoanRenewalExecutionEvidenceRecord:
        if self.error is not None:
            raise self.error
        self.record_request = kwargs
        return self._event(is_voided=False)

    def void(self, **kwargs) -> LoanRenewalExecutionEvidenceRecord:
        if self.error is not None:
            raise self.error
        self.void_request = kwargs
        return self._event(is_voided=True)

    @staticmethod
    def _event(*, is_voided: bool) -> LoanRenewalExecutionEvidenceRecord:
        voided_at = (
            datetime(2026, 8, 11, 3, 0, tzinfo=timezone.utc)
            if is_voided
            else None
        )
        return LoanRenewalExecutionEvidenceRecord(
            event_id=EXECUTION_EVENT_ID,
            old_loan_id=OLD_LOAN_ID,
            old_loan_number="LN-OLD-0001",
            new_loan_id=NEW_LOAN_ID,
            new_loan_number="LN-NEW-0001",
            disbursement_event_id=DISBURSEMENT_EVENT_ID,
            client_id=CLIENT_ID,
            client_code="C-0001",
            client_name="Test Borrower",
            renewal_request_id=RENEWAL_REQUEST_ID,
            business_date=date(2026, 8, 11),
            executed_at=datetime(2026, 8, 11, 2, 5, tzinfo=timezone.utc),
            old_loan_settlement_amount=Decimal("3000.00"),
            external_reference="RENEW-EXEC-0001",
            evidence_note="Office renewal execution",
            old_loan_principal_snapshot=Decimal("5000.00"),
            old_loan_date_released_snapshot=date(2026, 7, 12),
            old_loan_status_snapshot="active",
            new_loan_principal_snapshot=Decimal("5000.00"),
            new_loan_date_released_snapshot=date(2026, 8, 11),
            new_loan_status_snapshot="active",
            recorded_by_user_id=MANAGEMENT_USER_ID,
            recorded_at=datetime(2026, 8, 11, 2, 6, tzinfo=timezone.utc),
            is_voided=is_voided,
            voided_by_user_id=MANAGEMENT_USER_ID if is_voided else None,
            voided_at=voided_at,
            void_reason="Wrong execution reference" if is_voided else None,
        )


def client_with_fakes() -> tuple[TestClient, FakeRenewalExecutionRepository]:
    repository = FakeRenewalExecutionRepository()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts()
    app.dependency_overrides[loan_renewal_execution_evidence_repository_dependency] = (
        lambda: repository
    )
    return TestClient(app), repository


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer management-token",
        "X-Device-Id": "management-device",
    }


def test_management_can_read_renewal_execution_source_readiness() -> None:
    client, _ = client_with_fakes()
    response = client.get(
        "/api/v1/management/accounting/loan-renewals/readiness",
        headers=headers(),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["journal_lines_enabled"] is False
    assert data["automatic_source_posting"] is False
    assert data["events"][0]["readiness_status"] == "renewal_execution_evidence_ready"
    assert data["events"][0]["source_event_key"] == (
        f"loan_renewal_execution:{EXECUTION_EVENT_ID}"
    )
    assert data["events"][0]["old_loan_id"] == str(OLD_LOAN_ID)
    assert data["events"][0]["new_loan_id"] == str(NEW_LOAN_ID)


def test_management_can_register_explicit_renewal_execution_evidence() -> None:
    client, repository = client_with_fakes()
    response = client.post(
        "/api/v1/management/accounting/loan-renewals",
        headers=headers(),
        json={
            "old_loan_id": str(OLD_LOAN_ID),
            "new_loan_id": str(NEW_LOAN_ID),
            "disbursement_event_id": str(DISBURSEMENT_EVENT_ID),
            "business_date": "2026-08-11",
            "executed_at": "2026-08-11T10:05:00+08:00",
            "old_loan_settlement_amount": "3000.00",
            "external_reference": "RENEW-EXEC-0001",
            "evidence_note": "Office renewal execution",
            "renewal_request_id": str(RENEWAL_REQUEST_ID),
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["event_id"] == str(EXECUTION_EVENT_ID)
    assert data["old_loan_settlement_amount"] == "3000.00"
    assert data["journal_lines_enabled"] is False
    assert data["automatic_source_posting"] is False
    assert repository.record_request is not None
    assert repository.record_request["actor_user_id"] == MANAGEMENT_USER_ID
    assert repository.record_request["old_loan_id"] == OLD_LOAN_ID
    assert repository.record_request["new_loan_id"] == NEW_LOAN_ID
    assert repository.record_request["renewal_request_id"] == RENEWAL_REQUEST_ID


def test_management_can_void_unposted_renewal_execution_evidence() -> None:
    client, repository = client_with_fakes()
    response = client.post(
        f"/api/v1/management/accounting/loan-renewals/{EXECUTION_EVENT_ID}/void",
        headers=headers(),
        json={"reason": "Wrong execution reference"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["is_voided"] is True
    assert repository.void_request is not None
    assert repository.void_request["event_id"] == EXECUTION_EVENT_ID
    assert repository.void_request["actor_user_id"] == MANAGEMENT_USER_ID


def test_different_active_renewal_execution_evidence_returns_conflict() -> None:
    client, repository = client_with_fakes()
    repository.error = LoanRenewalExecutionEvidenceConflict(
        "This new loan already has different active renewal execution evidence."
    )
    response = client.post(
        "/api/v1/management/accounting/loan-renewals",
        headers=headers(),
        json={
            "old_loan_id": str(OLD_LOAN_ID),
            "new_loan_id": str(NEW_LOAN_ID),
            "disbursement_event_id": str(DISBURSEMENT_EVENT_ID),
            "business_date": "2026-08-11",
            "executed_at": "2026-08-11T10:05:00+08:00",
            "old_loan_settlement_amount": "3000.00",
            "external_reference": "RENEW-EXEC-0001",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == (
        "loan_renewal_execution_evidence_conflict"
    )
