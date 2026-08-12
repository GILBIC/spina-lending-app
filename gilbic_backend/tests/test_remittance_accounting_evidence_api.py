from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.remittance_accounting_api import (
    remittance_accounting_evidence_repository_dependency,
)
from gilbic_backend.remittance_accounting_repository import (
    RemittanceAccountingEvidenceConflict,
    RemittanceTransferEvidenceRecord,
    RemittanceTransferReadinessRecord,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
COLLECTOR_USER_ID = UUID("33333333-3333-4333-8333-333333333333")
RECIPIENT_USER_ID = UUID("44444444-4444-4444-8444-444444444444")
REMITTANCE_ID = UUID("55555555-5555-4555-8555-555555555555")
EVIDENCE_ID = UUID("66666666-6666-4666-8666-666666666666")


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
                "accounting.remittance_transfer.evidence.manage",
            ),
            device_registered=True,
        )


class FakeRepository:
    def __init__(self) -> None:
        self.record_request: dict[str, object] | None = None
        self.void_request: dict[str, object] | None = None
        self.error: Exception | None = None

    def list_readiness(self, **kwargs):
        if self.error is not None:
            raise self.error
        return (
            RemittanceTransferReadinessRecord(
                remittance_id=REMITTANCE_ID,
                remittance_number="REM-20260812-0001",
                collector_user_id=COLLECTOR_USER_ID,
                collector_name="Collector One",
                recipient_user_id=RECIPIENT_USER_ID,
                recipient_name="Office One",
                custody_user_id=RECIPIENT_USER_ID,
                custody_name="Office One",
                collection_date=date(2026, 8, 12),
                remittance_status="received",
                total_amount=Decimal("1500.00"),
                received_at=datetime(2026, 8, 12, 3, 0, tzinfo=timezone.utc),
                custody_transferred_at=datetime(
                    2026, 8, 12, 3, 0, tzinfo=timezone.utc
                ),
                transfer_evidence_id=EVIDENCE_ID,
                destination_account_system_key="cash_office",
                business_date=date(2026, 8, 12),
                transferred_at=datetime(2026, 8, 12, 3, 5, tzinfo=timezone.utc),
                external_reference="OFFICE-CASH-0001",
                readiness_status="transfer_coordinate_ready",
                source_event_key=f"remittance_transfer:{REMITTANCE_ID}",
                debit_account_system_key="cash_office",
                credit_account_system_key="cash_collector_custody",
                debit_amount=Decimal("1500.00"),
                credit_amount=Decimal("1500.00"),
                income_recognition=False,
                journal_lines_enabled=False,
                automatic_source_posting=False,
            ),
        )

    def record(self, **kwargs) -> RemittanceTransferEvidenceRecord:
        if self.error is not None:
            raise self.error
        self.record_request = kwargs
        return self._evidence(is_voided=False)

    def void(self, **kwargs) -> RemittanceTransferEvidenceRecord:
        if self.error is not None:
            raise self.error
        self.void_request = kwargs
        return self._evidence(is_voided=True)

    @staticmethod
    def _evidence(*, is_voided: bool) -> RemittanceTransferEvidenceRecord:
        return RemittanceTransferEvidenceRecord(
            evidence_id=EVIDENCE_ID,
            remittance_id=REMITTANCE_ID,
            remittance_number="REM-20260812-0001",
            destination_account_system_key="cash_office",
            business_date=date(2026, 8, 12),
            transferred_at=datetime(2026, 8, 12, 3, 5, tzinfo=timezone.utc),
            external_reference="OFFICE-CASH-0001",
            evidence_note="Counted into office cash",
            remittance_number_snapshot="REM-20260812-0001",
            collector_user_id_snapshot=COLLECTOR_USER_ID,
            recipient_user_id_snapshot=RECIPIENT_USER_ID,
            custody_user_id_snapshot=RECIPIENT_USER_ID,
            custody_transferred_at_snapshot=datetime(
                2026, 8, 12, 3, 0, tzinfo=timezone.utc
            ),
            collection_date_snapshot=date(2026, 8, 12),
            total_amount_snapshot=Decimal("1500.00"),
            recorded_by_user_id=MANAGEMENT_USER_ID,
            recorded_at=datetime(2026, 8, 12, 3, 6, tzinfo=timezone.utc),
            is_voided=is_voided,
            voided_by_user_id=MANAGEMENT_USER_ID if is_voided else None,
            voided_at=(
                datetime(2026, 8, 12, 3, 10, tzinfo=timezone.utc)
                if is_voided
                else None
            ),
            void_reason="Wrong destination reference" if is_voided else None,
        )


def client_with_fakes() -> tuple[TestClient, FakeRepository]:
    repository = FakeRepository()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts()
    app.dependency_overrides[
        remittance_accounting_evidence_repository_dependency
    ] = lambda: repository
    return TestClient(app), repository


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer management-token",
        "X-Device-Id": "management-device",
    }


def test_management_can_review_asset_to_asset_remittance_coordinate() -> None:
    client, _ = client_with_fakes()
    response = client.get(
        "/api/v1/management/accounting/remittance-transfers/readiness",
        headers=headers(),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["income_recognition"] is False
    assert data["journal_lines_enabled"] is False
    assert data["automatic_source_posting"] is False
    row = data["remittances"][0]
    assert row["readiness_status"] == "transfer_coordinate_ready"
    assert row["debit_account_system_key"] == "cash_office"
    assert row["credit_account_system_key"] == "cash_collector_custody"
    assert row["debit_amount"] == "1500.00"
    assert row["credit_amount"] == "1500.00"
    assert row["income_recognition"] is False


def test_management_can_register_explicit_office_destination_evidence() -> None:
    client, repository = client_with_fakes()
    response = client.post(
        "/api/v1/management/accounting/remittance-transfers/evidence",
        headers=headers(),
        json={
            "remittance_id": str(REMITTANCE_ID),
            "destination_account_system_key": "cash_office",
            "business_date": "2026-08-12",
            "transferred_at": "2026-08-12T11:05:00+08:00",
            "external_reference": "OFFICE-CASH-0001",
            "evidence_note": "Counted into office cash",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["evidence_id"] == str(EVIDENCE_ID)
    assert data["destination_account_system_key"] == "cash_office"
    assert data["income_recognition"] is False
    assert data["journal_lines_enabled"] is False
    assert repository.record_request is not None
    assert repository.record_request["actor_user_id"] == MANAGEMENT_USER_ID
    assert repository.record_request["remittance_id"] == REMITTANCE_ID


def test_destination_is_restricted_to_office_or_bank_gcash() -> None:
    client, _ = client_with_fakes()
    response = client.post(
        "/api/v1/management/accounting/remittance-transfers/evidence",
        headers=headers(),
        json={
            "remittance_id": str(REMITTANCE_ID),
            "destination_account_system_key": "cash_collector_custody",
            "business_date": "2026-08-12",
            "transferred_at": "2026-08-12T11:05:00+08:00",
            "external_reference": "BAD-DESTINATION",
        },
    )
    assert response.status_code == 422


def test_management_can_void_unposted_destination_evidence() -> None:
    client, repository = client_with_fakes()
    response = client.post(
        f"/api/v1/management/accounting/remittance-transfers/evidence/{EVIDENCE_ID}/void",
        headers=headers(),
        json={"reason": "Wrong destination reference"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["is_voided"] is True
    assert repository.void_request is not None
    assert repository.void_request["evidence_id"] == EVIDENCE_ID


def test_different_active_destination_evidence_returns_conflict() -> None:
    client, repository = client_with_fakes()
    repository.error = RemittanceAccountingEvidenceConflict(
        "This remittance already has different active destination evidence."
    )
    response = client.post(
        "/api/v1/management/accounting/remittance-transfers/evidence",
        headers=headers(),
        json={
            "remittance_id": str(REMITTANCE_ID),
            "destination_account_system_key": "cash_bank_gcash",
            "business_date": "2026-08-12",
            "transferred_at": "2026-08-12T11:05:00+08:00",
            "external_reference": "BANK-DEP-0001",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "remittance_accounting_evidence_conflict"
