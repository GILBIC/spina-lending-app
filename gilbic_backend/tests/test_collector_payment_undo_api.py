from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from gilbic_backend.auth_api import (
    account_repository_dependency,
    auth_client_dependency,
)
from gilbic_backend.collection_void_repository import (
    CollectionVoidForbidden,
    CollectionVoidRecord,
)
from gilbic_backend.main import create_app
from test_collection_correction_api import (
    CLIENT_ID,
    COLLECTOR_USER_ID,
    LOAN_ID,
    TRANSACTION_ID,
    FakeAccounts,
    FakeAuthClient,
    headers,
)

from gilbic_backend import collection_correction_api as api


class FakeUndo:
    request = None

    def void_unremitted(self, **kwargs):
        self.request = kwargs
        return CollectionVoidRecord(
            transaction_id=TRANSACTION_ID,
            receipt_number="R1",
            client_id=CLIENT_ID,
            client_code="C1",
            client_name="Borrower",
            loan_id=LOAN_ID,
            collector_user_id=COLLECTOR_USER_ID,
            collector_name="Collector",
            collection_date=date(2026, 10, 6),
            entry_type="payment",
            amount=Decimal("50.00"),
            covered_dates=(date(2026, 10, 6),),
            restored_balance=Decimal("5000.00"),
            state_version=2,
            reason=kwargs["reason"],
            voided_at=datetime(2026, 10, 6, 1, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize("prefix", ["/api/v1", "/api/mobile/v1"])
def test_undo_uses_authenticated_collector_and_server_business_date(
    monkeypatch, prefix
):
    app = create_app()
    repo = FakeUndo()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts()
    app.dependency_overrides[api.payment_undo_repository_dependency] = lambda: repo
    monkeypatch.setattr(api, "_undo_business_date", lambda: date(2026, 10, 6))
    with TestClient(app) as client:
        response = client.post(
            f"{prefix}/collector/collections/{TRANSACTION_ID}/undo-payment",
            headers=headers(),
            json={
                "reason": "Mistaken tap",
                "expected_route_revision": f"loan:{LOAN_ID}:v1",
            },
        )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["restored_balance"] == "5000.00"
    assert repo.request["actor_user_id"] == COLLECTOR_USER_ID
    assert repo.request["collector_business_date"] == date(2026, 10, 6)
    assert repo.request["collector_expected_route_revision"] == f"loan:{LOAN_ID}:v1"


def test_undo_requires_correction_permission():
    class ReadOnly(FakeAccounts):
        def get_context_for_device(self, **kwargs):
            return replace(super().get_context_for_device(**kwargs), permissions=())

    app = create_app()
    repo = FakeUndo()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: ReadOnly()
    app.dependency_overrides[api.payment_undo_repository_dependency] = lambda: repo
    with TestClient(app) as client:
        response = client.post(
            f"/api/mobile/v1/collector/collections/{TRANSACTION_ID}/undo-payment",
            headers=headers(),
            json={
                "reason": "Mistaken tap",
                "expected_route_revision": f"loan:{LOAN_ID}:v1",
            },
        )
    assert response.status_code == 403
    assert repo.request is None


def test_undo_reports_receipt_ownership_rejection():
    class Forbidden(FakeUndo):
        def void_unremitted(self, **kwargs):
            raise CollectionVoidForbidden("Only the original Collector may undo.")

    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts()
    app.dependency_overrides[api.payment_undo_repository_dependency] = lambda: (
        Forbidden()
    )
    with TestClient(app) as client:
        response = client.post(
            f"/api/mobile/v1/collector/collections/{TRANSACTION_ID}/undo-payment",
            headers=headers(),
            json={
                "reason": "Mistaken tap",
                "expected_route_revision": f"loan:{LOAN_ID}:v1",
            },
        )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "collection_void_forbidden"
