from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.greenfield_regular_ledger_reconciliation import (
    GreenfieldRegularLedgerReconciliation,
)
from gilbic_backend.greenfield_regular_ledger_reconciliation_repository import (
    GreenfieldRegularLedgerReconciliationError,
    GreenfieldRegularLedgerReconciliationPreview,
)
from gilbic_backend.greenfield_regular_renewal_boundary_eir import (
    GreenfieldRegularRenewalBoundaryEirLine,
    GreenfieldRegularRenewalBoundaryEirPeriodProposal,
    GreenfieldRegularRenewalBoundaryEirPreview,
)
from gilbic_backend.greenfield_regular_renewal_rollforward_api import (
    greenfield_regular_ledger_reconciliation_repository_dependency,
)
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
OLD_LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
NEW_LOAN_ID = UUID("55555555-5555-4555-8555-555555555555")
EXECUTION_ID = UUID("66666666-6666-4666-8666-666666666666")
RENEWAL_DISBURSEMENT_ID = UUID("77777777-7777-4777-8777-777777777777")
ANCHOR_POSTING_ID = UUID("88888888-8888-4888-8888-888888888888")
ANCHOR_JOURNAL_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
FISCAL_PERIOD_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


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


class FakeRepository:
    def __init__(self) -> None:
        self.request: dict[str, object] | None = None
        self.error: Exception | None = None

    def list_previews(self, **kwargs):
        self.request = kwargs
        if self.error is not None:
            raise self.error
        reconciliation = GreenfieldRegularLedgerReconciliation(
            loan_id=OLD_LOAN_ID,
            anchor_date=date(2026, 8, 1),
            target_date=date(2026, 8, 31),
            disposition="greenfield_regular_ledger_reconciliation_blocked",
            blocker_code="renewal_boundary_eir_accrual_not_posted",
            message="Protected source journals reconcile; renewal-boundary EIR remains unposted.",
            expected_active_transaction_count=2,
            expected_journal_count=4,
            exact_posted_journal_count=4,
            ignored_voided_reversed_journal_count=0,
            unprotected_posted_journal_count=0,
            expected_loan_component_through_last_source=Decimal("4800.00"),
            expected_accrued_interest_through_last_source=Decimal("311.13"),
            ledger_loan_component_through_last_source=Decimal("4800.00"),
            ledger_accrued_interest_through_last_source=Decimal("311.13"),
            ledger_gross_carrying_through_last_source=Decimal("5111.13"),
            target_gross_carrying_amount=Decimal("5272.35"),
            target_accrued_interest_component=Decimal("472.35"),
            target_loan_component=Decimal("4800.00"),
            tail_effective_interest_accrued=Decimal("161.22"),
            protected_regular_journals_reconciled=True,
            target_ledger_reconciled=False,
            accounting_carrying_amount_ready=False,
            journal_lines_enabled=False,
            automatic_source_posting=False,
        )
        boundary_preview = GreenfieldRegularRenewalBoundaryEirPreview(
            renewal_execution_event_id=EXECUTION_ID,
            loan_id=OLD_LOAN_ID,
            target_date=date(2026, 8, 31),
            amount=Decimal("161.22"),
            disposition="renewal_boundary_eir_journal_preview_ready",
            blocker_code=None,
            message="Exact read-only renewal-boundary EIR coordinates are available.",
            period_proposals=(
                GreenfieldRegularRenewalBoundaryEirPeriodProposal(
                    fiscal_period_id=FISCAL_PERIOD_ID,
                    fiscal_period_label="August 2026",
                    accrual_start_date_inclusive=date(2026, 8, 21),
                    accrual_end_date_inclusive=date(2026, 8, 31),
                    posting_date=date(2026, 8, 31),
                    day_count=11,
                    amount=Decimal("161.22"),
                    source_type="regular_renewal_eir_accrual",
                    source_reference=(
                        f"{EXECUTION_ID}:fiscal_period:{FISCAL_PERIOD_ID}"
                    ),
                    source_event_key=(
                        "renewal_eir_accrual:"
                        f"{EXECUTION_ID}:fiscal_period:{FISCAL_PERIOD_ID}"
                    ),
                    proposed_lines=(
                        GreenfieldRegularRenewalBoundaryEirLine(
                            account_system_key="accrued_interest_receivable",
                            side="debit",
                            amount=Decimal("161.22"),
                        ),
                        GreenfieldRegularRenewalBoundaryEirLine(
                            account_system_key="interest_income_regular",
                            side="credit",
                            amount=Decimal("161.22"),
                        ),
                    ),
                ),
            ),
            total_debit=Decimal("161.22"),
            total_credit=Decimal("161.22"),
            balanced=True,
            posting_eligible=False,
            automatic_source_posting=False,
        )
        return (
            GreenfieldRegularLedgerReconciliationPreview(
                renewal_execution_event_id=EXECUTION_ID,
                renewal_disbursement_event_id=RENEWAL_DISBURSEMENT_ID,
                old_loan_id=OLD_LOAN_ID,
                old_loan_number="OLD-001",
                new_loan_id=NEW_LOAN_ID,
                new_loan_number="NEW-001",
                client_id=CLIENT_ID,
                client_code="C-001",
                client_name="Test Borrower",
                target_date=date(2026, 8, 31),
                executed_at=datetime(2026, 8, 31, 2, 0, tzinfo=timezone.utc),
                old_loan_settlement_amount=Decimal("3000.00"),
                anchor_posting_id=ANCHOR_POSTING_ID,
                anchor_journal_entry_id=ANCHOR_JOURNAL_ID,
                anchor_entry_number="JE-202608-00000001",
                anchor_date=date(2026, 8, 1),
                initial_gross_carrying_amount=Decimal("5000.00"),
                initial_loan_component=Decimal("5000.00"),
                initial_accrued_interest_component=Decimal("0.00"),
                daily_eir=Decimal("0.003137297107"),
                contractual_due_date=date(2026, 11, 29),
                rollforward_readiness_status="greenfield_regular_renewal_rollforward_target_ready",
                active_source_count=2,
                protected_complete_active_source_count=2,
                voided_posted_source_count=0,
                voided_unreversed_source_count=0,
                unprotected_posted_journal_count=0,
                reconciliation_readiness_status="greenfield_regular_ledger_reconciliation_candidate",
                exact_reconciliation_preview_enabled=True,
                reconciliation_policy_version="greenfield_regular_ledger_reconciliation_v1",
                accounting_carrying_amount_ready=False,
                journal_lines_enabled=False,
                automatic_source_posting=False,
                rollforward=None,
                reconciliation=reconciliation,
                renewal_boundary_eir_preview=boundary_preview,
            ),
        )


def _client() -> tuple[TestClient, FakeRepository]:
    repository = FakeRepository()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts()
    app.dependency_overrides[
        greenfield_regular_ledger_reconciliation_repository_dependency
    ] = lambda: repository
    return TestClient(app), repository


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer management-token",
        "X-Device-Id": "management-device",
    }


def test_management_can_read_greenfield_regular_ledger_reconciliation() -> None:
    client, repository = _client()
    response = client.get(
        "/api/v1/management/accounting/renewals/regular-greenfield-ledger-reconciliation/preview",
        params={
            "reconciliation_readiness_status": "greenfield_regular_ledger_reconciliation_candidate",
            "renewal_execution_event_id": str(EXECUTION_ID),
            "old_loan_id": str(OLD_LOAN_ID),
            "limit": 25,
        },
        headers=_headers(),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["reconciliation_policy_version"] == "greenfield_regular_ledger_reconciliation_v1"
    assert data["read_only"] is True
    assert data["journal_lines_enabled"] is False
    assert data["automatic_source_posting"] is False
    target = data["renewal_targets"][0]
    assert target["reconciliation_readiness_status"] == "greenfield_regular_ledger_reconciliation_candidate"
    assert target["accounting_carrying_amount_ready"] is False
    result = target["reconciliation"]
    assert result["protected_regular_journals_reconciled"] is True
    assert result["blocker_code"] == "renewal_boundary_eir_accrual_not_posted"
    assert result["tail_effective_interest_accrued"] == "161.22"
    assert result["accounting_carrying_amount_ready"] is False

    boundary = target["renewal_boundary_eir_preview"]
    assert boundary["disposition"] == "renewal_boundary_eir_journal_preview_ready"
    assert boundary["amount"] == "161.22"
    assert boundary["total_debit"] == "161.22"
    assert boundary["total_credit"] == "161.22"
    assert boundary["balanced"] is True
    assert boundary["posting_eligible"] is False
    assert boundary["automatic_source_posting"] is False
    proposal = boundary["period_proposals"][0]
    assert proposal["fiscal_period_id"] == str(FISCAL_PERIOD_ID)
    assert proposal["posting_date"] == "2026-08-31"
    assert proposal["source_type"] == "regular_renewal_eir_accrual"
    assert proposal["source_event_key"] == (
        f"renewal_eir_accrual:{EXECUTION_ID}:fiscal_period:{FISCAL_PERIOD_ID}"
    )
    assert proposal["proposed_lines"] == [
        {
            "account_system_key": "accrued_interest_receivable",
            "side": "debit",
            "amount": "161.22",
        },
        {
            "account_system_key": "interest_income_regular",
            "side": "credit",
            "amount": "161.22",
        },
    ]
    assert repository.request == {
        "reconciliation_readiness_status": "greenfield_regular_ledger_reconciliation_candidate",
        "renewal_execution_event_id": EXECUTION_ID,
        "old_loan_id": OLD_LOAN_ID,
        "limit": 25,
    }


def test_greenfield_regular_ledger_reconciliation_error_fails_closed() -> None:
    client, repository = _client()
    repository.error = GreenfieldRegularLedgerReconciliationError(
        "Protected Regular ledger reconciliation is unavailable."
    )
    response = client.get(
        "/api/v1/management/accounting/renewals/regular-greenfield-ledger-reconciliation/preview",
        headers=_headers(),
    )
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "greenfield_regular_ledger_reconciliation_error",
        "message": "Protected Regular ledger reconciliation is unavailable.",
    }