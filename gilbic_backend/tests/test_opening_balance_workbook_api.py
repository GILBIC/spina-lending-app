from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.opening_balance_workbook_api import (
    opening_balance_workbook_repository_dependency,
)
from gilbic_backend.opening_balance_workbook_repository import (
    OpeningBalanceWorkbook,
    OpeningBalanceWorkbookLine,
    OpeningBalanceWorkbookSummary,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
WORKBOOK_ID = UUID("55555555-5555-4555-8555-555555555555")


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="manager@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def __init__(self, *, can_manage: bool = True, role: str = "management") -> None:
        self.can_manage = can_manage
        self.role = role

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == "test-device"
        permissions = ("accounting.view",)
        if self.can_manage:
            permissions += ("accounting.cutover.manage",)
        return AccountContext(
            user_id=MANAGEMENT_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username="manager",
            email="manager@example.com",
            full_name="Management",
            status="active",
            roles=(self.role,),
            permissions=permissions,
            device_registered=True,
        )


class FakeWorkbookRepository:
    def __init__(self) -> None:
        self.created: tuple[date, UUID] | None = None
        self.line_update: tuple[UUID, str, Decimal | None, Decimal | None, str, str | None, UUID] | None = None
        self.policy_update: tuple[UUID, bool, str | None, UUID] | None = None
        self.status_update: tuple[UUID, str, UUID] | None = None
        self._has_workbook = False

    def load_workbook(self) -> OpeningBalanceWorkbook:
        return self._workbook()

    def create_workbook(
        self,
        *,
        actor_user_id: UUID,
        cutover_date: date,
    ) -> OpeningBalanceWorkbook:
        self.created = (cutover_date, actor_user_id)
        self._has_workbook = True
        return self._workbook()

    def update_line(
        self,
        *,
        actor_user_id: UUID,
        workbook_id: UUID,
        account_code: str,
        proposed_debit: Decimal | None,
        proposed_credit: Decimal | None,
        verification_status: str,
        evidence_note: str | None,
    ) -> OpeningBalanceWorkbook:
        self.line_update = (
            workbook_id,
            account_code,
            proposed_debit,
            proposed_credit,
            verification_status,
            evidence_note,
            actor_user_id,
        )
        self._has_workbook = True
        return self._workbook(
            debit=proposed_debit,
            credit=proposed_credit,
            verification_status=verification_status,
            evidence_note=evidence_note,
        )

    def update_policy(
        self,
        *,
        actor_user_id: UUID,
        workbook_id: UUID,
        confirmed: bool,
        policy_note: str | None,
    ) -> OpeningBalanceWorkbook:
        self.policy_update = (workbook_id, confirmed, policy_note, actor_user_id)
        self._has_workbook = True
        return self._workbook(policy_confirmed=confirmed, policy_note=policy_note)

    def set_status(
        self,
        *,
        actor_user_id: UUID,
        workbook_id: UUID,
        status: str,
    ) -> OpeningBalanceWorkbook:
        self.status_update = (workbook_id, status, actor_user_id)
        self._has_workbook = True
        return self._workbook(status=status)

    def _workbook(
        self,
        *,
        status: str = "draft",
        debit: Decimal | None = None,
        credit: Decimal | None = None,
        verification_status: str = "pending",
        evidence_note: str | None = None,
        policy_confirmed: bool = False,
        policy_note: str | None = None,
    ) -> OpeningBalanceWorkbook:
        workbook_id = WORKBOOK_ID if self._has_workbook else None
        return OpeningBalanceWorkbook(
            summary=OpeningBalanceWorkbookSummary(
                workbook_id=workbook_id,
                cutover_date=date(2026, 8, 8) if workbook_id else None,
                status=status if workbook_id else "source_review_required",
                line_count=11,
                source_reference_count=4,
                verified_line_count=1 if verification_status == "verified" else 0,
                pending_line_count=10 if verification_status == "verified" else 11,
                profit_loss_policy_confirmed=policy_confirmed,
                profit_loss_policy_note=policy_note,
                total_debit=debit or Decimal("0.00"),
                total_credit=credit or Decimal("0.00"),
                balance_variance=abs((debit or Decimal("0.00")) - (credit or Decimal("0.00"))),
                worksheet_balanced=False,
                ready_for_review=False,
                ready_to_post=False,
                opening_balance_posting_enabled=False,
                automatic_source_posting_enabled=False,
            ),
            lines=(
                OpeningBalanceWorkbookLine(
                    workbook_id=workbook_id,
                    account_code="1020",
                    system_key="cash_collector_custody",
                    account_name="Cash - Collector Custody",
                    account_type="asset",
                    normal_balance="debit",
                    source_reference_amount=Decimal("200.00"),
                    source_basis="collection_custody_reference",
                    requirement_type="reconciliation_required",
                    guidance="Reconcile to physical collector cash.",
                    proposed_debit=debit,
                    proposed_credit=credit,
                    verification_status=verification_status,
                    evidence_note=evidence_note,
                ),
            ),
        )


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Device-Id": "test-device",
    }


def client_with_fakes(
    *,
    can_manage: bool = True,
    role: str = "management",
) -> tuple[TestClient, FakeWorkbookRepository]:
    app = create_app()
    repository = FakeWorkbookRepository()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        can_manage=can_manage,
        role=role,
    )
    app.dependency_overrides[opening_balance_workbook_repository_dependency] = (
        lambda: repository
    )
    return TestClient(app), repository


def test_management_can_view_non_posting_workbook_source_state() -> None:
    client, _ = client_with_fakes()

    response = client.get(
        "/api/mobile/v1/management/financial-accounting/opening-balance-workbook",
        headers=headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"]["workbook_id"] is None
    assert data["summary"]["ready_to_post"] is False
    assert data["summary"]["opening_balance_posting_enabled"] is False
    assert data["summary"]["automatic_source_posting_enabled"] is False
    assert data["lines"][0]["source_reference_amount"] == "200.00"


def test_management_can_initialize_workbook_for_controlled_cutover_date() -> None:
    client, repository = client_with_fakes()

    response = client.post(
        "/api/mobile/v1/management/financial-accounting/opening-balance-workbook",
        headers=headers(),
        json={"cutover_date": "2026-08-08"},
    )

    assert response.status_code == 201
    assert response.json()["data"]["summary"]["workbook_id"] == str(WORKBOOK_ID)
    assert repository.created == (date(2026, 8, 8), MANAGEMENT_USER_ID)


def test_management_can_verify_explicit_zero_line_with_evidence() -> None:
    client, repository = client_with_fakes()
    repository._has_workbook = True

    response = client.put(
        f"/api/v1/management/financial-accounting/opening-balance-workbook/{WORKBOOK_ID}/lines/1020",
        headers=headers(),
        json={
            "debit": 0,
            "credit": None,
            "verification_status": "verified",
            "evidence_note": "Count reconciled to zero.",
        },
    )

    assert response.status_code == 200
    assert repository.line_update == (
        WORKBOOK_ID,
        "1020",
        Decimal("0"),
        None,
        "verified",
        "Count reconciled to zero.",
        MANAGEMENT_USER_ID,
    )


def test_verified_line_without_evidence_is_rejected_before_repository() -> None:
    client, repository = client_with_fakes()
    repository._has_workbook = True

    response = client.put(
        f"/api/v1/management/financial-accounting/opening-balance-workbook/{WORKBOOK_ID}/lines/1020",
        headers=headers(),
        json={
            "debit": 200,
            "credit": None,
            "verification_status": "verified",
            "evidence_note": "",
        },
    )

    assert response.status_code == 422
    assert repository.line_update is None


def test_cutover_permission_is_required_for_workbook_writes() -> None:
    client, repository = client_with_fakes(can_manage=False)

    response = client.post(
        "/api/v1/management/financial-accounting/opening-balance-workbook",
        headers=headers(),
        json={"cutover_date": "2026-08-08"},
    )

    assert response.status_code == 403
    assert repository.created is None


def test_non_management_role_is_denied() -> None:
    client, _ = client_with_fakes(role="client", can_manage=False)

    response = client.get(
        "/api/v1/management/financial-accounting/opening-balance-workbook",
        headers=headers(),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "management_role_required"
