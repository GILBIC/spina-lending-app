from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.greenfield_regular_ledger_reconciliation_repository import (
    GreenfieldRegularLedgerReconciliationPreview,
)
from gilbic_backend.main import create_app
from gilbic_backend.renewal_treatment_readiness import (
    RenewalTreatmentEvidence,
    RenewalTreatmentInstallment,
    build_renewal_treatment_readiness,
)
from gilbic_backend.renewal_treatment_readiness_api import (
    renewal_treatment_readiness_repository_dependency,
)
from gilbic_backend.renewal_treatment_readiness_repository import (
    RenewalTreatmentReadinessRecord,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
OLD_LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
NEW_LOAN_ID = UUID("55555555-5555-4555-8555-555555555555")
EXECUTION_ID = UUID("66666666-6666-4666-8666-666666666666")
RELEASE_ID = UUID("77777777-7777-4777-8777-777777777777")
ANCHOR_POSTING_ID = UUID("88888888-8888-4888-8888-888888888888")
ANCHOR_JOURNAL_ID = UUID("99999999-9999-4999-8999-999999999999")
SCHEDULE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
REGISTRATION_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
RENEWAL_DATE = date(2026, 8, 31)
REVIEW_TOKEN = "a" * 64


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


def _source() -> GreenfieldRegularLedgerReconciliationPreview:
    return GreenfieldRegularLedgerReconciliationPreview(
        renewal_execution_event_id=EXECUTION_ID,
        renewal_disbursement_event_id=RELEASE_ID,
        old_loan_id=OLD_LOAN_ID,
        old_loan_number="OLD-001",
        new_loan_id=NEW_LOAN_ID,
        new_loan_number="NEW-001",
        client_id=CLIENT_ID,
        client_code="C-001",
        client_name="Test Borrower",
        target_date=RENEWAL_DATE,
        executed_at=datetime(2026, 8, 31, 2, 0, tzinfo=timezone.utc),
        old_loan_settlement_amount=Decimal("1000.00"),
        anchor_posting_id=ANCHOR_POSTING_ID,
        anchor_journal_entry_id=ANCHOR_JOURNAL_ID,
        anchor_entry_number="JE-202608-00000001",
        anchor_date=date(2026, 8, 1),
        initial_gross_carrying_amount=Decimal("2000.00"),
        initial_loan_component=Decimal("2000.00"),
        initial_accrued_interest_component=Decimal("0.00"),
        daily_eir=Decimal("0.001"),
        contractual_due_date=date(2026, 12, 29),
        rollforward_readiness_status="greenfield_regular_renewal_rollforward_target_ready",
        active_source_count=2,
        protected_complete_active_source_count=2,
        voided_posted_source_count=0,
        voided_unreversed_source_count=0,
        unprotected_posted_journal_count=0,
        reconciliation_readiness_status="greenfield_regular_ledger_reconciliation_candidate",
        exact_reconciliation_preview_enabled=True,
        reconciliation_policy_version="greenfield_regular_ledger_reconciliation_v1",
        accounting_carrying_amount_ready=True,
        journal_lines_enabled=False,
        automatic_source_posting=False,
        rollforward=None,
        reconciliation=None,
        renewal_boundary_eir_preview=None,
    )


def _readiness():
    return build_renewal_treatment_readiness(
        RenewalTreatmentEvidence(
            renewal_execution_event_id=EXECUTION_ID,
            old_loan_id=OLD_LOAN_ID,
            new_loan_id=NEW_LOAN_ID,
            client_id=CLIENT_ID,
            business_date=RENEWAL_DATE,
            execution_active=True,
            release_event_kind="renewal_release",
            release_business_date=RENEWAL_DATE,
            release_active=True,
            cash_disbursed_amount=Decimal("1000.00"),
            settlement_amount=Decimal("1000.00"),
            other_deduction_amount=Decimal("0.00"),
            new_loan_calculation_mode="fixed_daily",
            accounting_carrying_amount_ready=True,
            old_gross_carrying_amount=Decimal("2000.00"),
            original_daily_eir=Decimal("0.001"),
            schedule_id=SCHEDULE_ID,
            schedule_version=1,
            schedule_status="active",
            schedule_effective_from=RENEWAL_DATE,
            payment_frequency="daily",
            contract_reference="SIGNED-RENEWAL-001",
            contract_signed_date=RENEWAL_DATE,
            registration_id=REGISTRATION_ID,
            evidence_basis="signed_renewal_contract",
            evidence_reference="SIGNED-RENEWAL-001",
            installments=(
                RenewalTreatmentInstallment(1, date(2026, 9, 30), Decimal("600.00")),
                RenewalTreatmentInstallment(2, date(2026, 10, 30), Decimal("600.00")),
                RenewalTreatmentInstallment(3, date(2026, 11, 29), Decimal("600.00")),
                RenewalTreatmentInstallment(4, date(2026, 12, 29), Decimal("600.00")),
            ),
        )
    )


class FakeRepository:
    def load(self, *, renewal_execution_event_id: UUID):
        assert renewal_execution_event_id == EXECUTION_ID
        return RenewalTreatmentReadinessRecord(
            source=_source(),
            readiness=_readiness(),
            review_token=REVIEW_TOKEN,
        )


def _client() -> TestClient:
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts()
    app.dependency_overrides[
        renewal_treatment_readiness_repository_dependency
    ] = lambda: FakeRepository()
    return TestClient(app)


def test_management_can_read_nonclassifying_renewal_treatment_readiness() -> None:
    response = _client().get(
        f"/api/v1/management/accounting/renewals/{EXECUTION_ID}/treatment-readiness",
        headers={
            "Authorization": "Bearer management-token",
            "X-Device-Id": "management-device",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["renewal_execution_event_id"] == str(EXECUTION_ID)
    assert data["old_loan_number"] == "OLD-001"
    assert data["new_loan_number"] == "NEW-001"
    assert data["disposition"] == "renewal_accounting_treatment_review_ready"
    assert data["review_token"] == REVIEW_TOKEN
    assert data["old_gross_carrying_amount"] == "2000.00"
    assert data["contractual_cash_total"] == "2400.00"
    assert data["present_value_at_original_eir"] == "2227.92"
    assert data["present_value_change_percent"] == "11.3960"
    assert data["treatment_decision_required"] is True
    assert data["automatic_classification_enabled"] is False
    assert data["quantitative_threshold_decisive"] is False
    assert data["journal_lines_enabled"] is False
    assert data["automatic_source_posting"] is False
    assert data["read_only"] is True
    assert "does not apply an automatic 10% derecognition rule" in data["notice"]
