from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.renewal_treatment_accounting_target import (
    RenewalTreatmentAccountingEvidence,
    build_renewal_treatment_accounting_target,
)
from gilbic_backend.renewal_treatment_accounting_target_api import (
    renewal_treatment_accounting_target_repository_dependency,
)
from gilbic_backend.renewal_treatment_accounting_target_repository import (
    RenewalTreatmentAccountingTargetRecord,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
OLD_LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
NEW_LOAN_ID = UUID("55555555-5555-4555-8555-555555555555")
EXECUTION_ID = UUID("66666666-6666-4666-8666-666666666666")
DECISION_ID = UUID("77777777-7777-4777-8777-777777777777")
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
            permissions=("accounting.view",),
            device_registered=True,
        )


def _record() -> RenewalTreatmentAccountingTargetRecord:
    decision = SimpleNamespace(
        renewal_execution_event_id=EXECUTION_ID,
        decision_id=DECISION_ID,
        decision="modification_no_derecognition",
        decision_policy_version="renewal_treatment_decision_evidence_v1",
        reviewed_at=datetime(2026, 8, 31, 3, 0, tzinfo=timezone.utc),
        old_loan_id=OLD_LOAN_ID,
        old_loan_number="OLD-001",
        new_loan_id=NEW_LOAN_ID,
        new_loan_number="NEW-001",
        client_id=CLIENT_ID,
        client_code="C-001",
        client_name="Test Borrower",
        renewal_business_date=RENEWAL_DATE,
    )
    target = build_renewal_treatment_accounting_target(
        RenewalTreatmentAccountingEvidence(
            decision_id=DECISION_ID,
            renewal_execution_event_id=EXECUTION_ID,
            old_loan_id=OLD_LOAN_ID,
            new_loan_id=NEW_LOAN_ID,
            client_id=CLIENT_ID,
            decision="modification_no_derecognition",
            decision_active=True,
            old_gross_carrying_amount=Decimal("2000.00"),
            original_daily_eir=Decimal("0.001"),
            present_value_at_original_eir=Decimal("1800.00"),
            present_value_change_amount=Decimal("-200.00"),
        )
    )
    return RenewalTreatmentAccountingTargetRecord(decision=decision, target=target)  # type: ignore[arg-type]


class FakeRepository:
    def load(self, *, renewal_execution_event_id: UUID):
        assert renewal_execution_event_id == EXECUTION_ID
        return _record()


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts()
    app.dependency_overrides[
        renewal_treatment_accounting_target_repository_dependency
    ] = lambda: FakeRepository()
    return TestClient(app)


def test_management_can_read_modification_measurement_without_journal_coordinates() -> None:
    response = _client().get(
        f"/api/v1/management/accounting/renewals/{EXECUTION_ID}/treatment-accounting-target",
        headers={
            "Authorization": "Bearer management-token",
            "X-Device-Id": "management-device",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["renewal_execution_event_id"] == str(EXECUTION_ID)
    assert data["decision"] == "modification_no_derecognition"
    assert data["accounting_asset_loan_id"] == str(OLD_LOAN_ID)
    assert data["operational_renewal_loan_id"] == str(NEW_LOAN_ID)
    assert data["old_gross_carrying_amount"] == "2000.00"
    assert data["revised_gross_carrying_amount"] == "1800.00"
    assert data["modification_adjustment_amount"] == "200.00"
    assert data["modification_profit_or_loss"] == "loss"
    assert data["accounting_asset_continues"] is True
    assert data["treatment_journal_coordinates_ready"] is False
    assert data["journal_lines_enabled"] is False
    assert data["automatic_source_posting"] is False
    assert data["read_only"] is True
    assert "does not assign final General Ledger gain/loss accounts" in data["notice"]
