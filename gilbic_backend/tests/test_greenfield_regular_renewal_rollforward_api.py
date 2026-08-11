from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.greenfield_regular_eir_rollforward import (
    GreenfieldRegularRenewalRollForward,
)
from gilbic_backend.greenfield_regular_renewal_rollforward_api import (
    greenfield_regular_renewal_rollforward_repository_dependency,
)
from gilbic_backend.greenfield_regular_renewal_rollforward_repository import (
    GreenfieldRegularRenewalRollForwardError,
    GreenfieldRegularRenewalRollForwardPreview,
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
ANCHOR_DISBURSEMENT_ID = UUID("99999999-9999-4999-8999-999999999999")
ANCHOR_JOURNAL_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
SCHEDULE_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


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


class FakeRollForwardRepository:
    def __init__(self) -> None:
        self.request: dict[str, object] | None = None
        self.error: Exception | None = None

    def list_previews(self, **kwargs):
        self.request = kwargs
        if self.error is not None:
            raise self.error
        rollforward = GreenfieldRegularRenewalRollForward(
            loan_id=OLD_LOAN_ID,
            anchor_date=date(2026, 8, 1),
            target_date=date(2026, 8, 31),
            contractual_due_date=date(2026, 11, 29),
            daily_eir=Decimal("0.003137297107"),
            initial_gross_carrying_amount=Decimal("5000.00"),
            initial_accrued_interest_component=Decimal("0.00"),
            initial_loan_component=Decimal("5000.00"),
            source_event_count=2,
            allocation_count=2,
            disposition="greenfield_regular_renewal_rollforward_preview_ready",
            blocker_code=None,
            message="Read-only preview ready.",
            total_effective_interest_accrued=Decimal("472.35"),
            tail_effective_interest_accrued=Decimal("161.22"),
            gross_carrying_amount_at_target=Decimal("5272.35"),
            accrued_interest_component_at_target=Decimal("472.35"),
            loan_component_at_target=Decimal("4800.00"),
            allocations=(),
            tail_daily_accruals=(),
            measurement_preview_ready=True,
            accounting_carrying_amount_ready=False,
            journal_lines_enabled=False,
            automatic_source_posting=False,
        )
        return (
            GreenfieldRegularRenewalRollForwardPreview(
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
                execution_external_reference="RENEW-001",
                renewal_source_readiness_status="renewal_execution_evidence_ready",
                renewal_source_event_key=f"loan_renewal_execution:{EXECUTION_ID}",
                anchor_posting_id=ANCHOR_POSTING_ID,
                anchor_disbursement_event_id=ANCHOR_DISBURSEMENT_ID,
                anchor_journal_entry_id=ANCHOR_JOURNAL_ID,
                anchor_entry_number="JE-202608-00000001",
                anchor_date=date(2026, 8, 1),
                initial_gross_carrying_amount=Decimal("5000.00"),
                initial_loan_component=Decimal("5000.00"),
                initial_accrued_interest_component=Decimal("0.00"),
                daily_eir=Decimal("0.003137297107"),
                daily_eir_percent=Decimal("0.31372971"),
                contractual_due_date=date(2026, 11, 29),
                schedule_id=SCHEDULE_ID,
                contract_reference="CONTRACT-001",
                contract_evidence_reference="SIGNED-001",
                anchor_readiness_status="greenfield_regular_eir_anchor_ready",
                anchor_source_key=f"greenfield_regular_eir_anchor:{ANCHOR_POSTING_ID}",
                source_event_count_before_target=2,
                same_day_target_collection_count=0,
                readiness_status="greenfield_regular_renewal_rollforward_target_ready",
                target_source_key=f"greenfield_regular_renewal_rollforward:{EXECUTION_ID}",
                rollforward_policy_version="greenfield_regular_renewal_rollforward_v1",
                measurement_preview_enabled=True,
                accounting_carrying_amount_ready=False,
                journal_lines_enabled=False,
                automatic_source_posting=False,
                rollforward=rollforward,
            ),
        )


def client_with_fakes() -> tuple[TestClient, FakeRollForwardRepository]:
    repository = FakeRollForwardRepository()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts()
    app.dependency_overrides[
        greenfield_regular_renewal_rollforward_repository_dependency
    ] = lambda: repository
    return TestClient(app), repository


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer management-token",
        "X-Device-Id": "management-device",
    }


def test_management_can_read_greenfield_regular_renewal_rollforward_preview() -> None:
    client, repository = client_with_fakes()
    response = client.get(
        "/api/v1/management/accounting/renewals/regular-greenfield-rollforward/preview",
        params={
            "readiness_status": "greenfield_regular_renewal_rollforward_target_ready",
            "renewal_execution_event_id": str(EXECUTION_ID),
            "old_loan_id": str(OLD_LOAN_ID),
            "limit": 25,
        },
        headers=headers(),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["rollforward_policy_version"] == "greenfield_regular_renewal_rollforward_v1"
    assert data["measurement_preview_only"] is True
    assert data["accounting_carrying_amount_ready"] is False
    assert data["journal_lines_enabled"] is False
    assert data["automatic_source_posting"] is False
    target = data["renewal_targets"][0]
    assert target["renewal_execution_event_id"] == str(EXECUTION_ID)
    assert target["old_loan_id"] == str(OLD_LOAN_ID)
    assert target["new_loan_id"] == str(NEW_LOAN_ID)
    assert target["old_loan_settlement_amount"] == "3000.00"
    assert target["readiness_status"] == "greenfield_regular_renewal_rollforward_target_ready"
    assert target["accounting_carrying_amount_ready"] is False
    measured = target["rollforward"]
    assert measured["disposition"] == "greenfield_regular_renewal_rollforward_preview_ready"
    assert measured["gross_carrying_amount_at_target"] == "5272.35"
    assert measured["accrued_interest_component_at_target"] == "472.35"
    assert measured["loan_component_at_target"] == "4800.00"
    assert measured["measurement_preview_ready"] is True
    assert measured["accounting_carrying_amount_ready"] is False
    assert repository.request == {
        "readiness_status": "greenfield_regular_renewal_rollforward_target_ready",
        "renewal_execution_event_id": EXECUTION_ID,
        "old_loan_id": OLD_LOAN_ID,
        "limit": 25,
    }


def test_greenfield_rollforward_repository_error_is_fail_closed() -> None:
    client, repository = client_with_fakes()
    repository.error = GreenfieldRegularRenewalRollForwardError(
        "Greenfield Regular renewal roll-forward evidence is unavailable."
    )
    response = client.get(
        "/api/v1/management/accounting/renewals/regular-greenfield-rollforward/preview",
        headers=headers(),
    )
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "greenfield_regular_renewal_rollforward_error",
        "message": "Greenfield Regular renewal roll-forward evidence is unavailable.",
    }
