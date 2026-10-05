import pytest
from fastapi.testclient import TestClient
from gilbic_backend.auth_api import (
    account_repository_dependency,
    auth_client_dependency,
)
from gilbic_backend.main import create_app
from gilbic_backend.period_close_api import period_close_repository_dependency
from test_financial_statements import PERIOD_ID, FakeAccounts, FakeAuthClient, headers


class SourceCoverage:
    calls = 0

    def source_coverage(self, fiscal_period_id, *, actor, limit, offset):
        self.calls += 1
        assert fiscal_period_id == PERIOD_ID
        return {
            "comprehensive_source_coverage": False,
            "source_families": ["treasury", "collector"],
            "blocker_count": 1,
            "limit": limit,
            "offset": offset,
            "blockers": [
                {
                    "source_type": "treasury_event",
                    "source_id": str(PERIOD_ID),
                    "effective_date": "2026-10-05",
                    "amount": "100.00",
                    "reason": "treasury_gl_mapping_required",
                }
            ],
        }


def source_client(role="management", can_view=True):
    app = create_app()
    fake = SourceCoverage()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        role=role, can_view=can_view
    )
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[period_close_repository_dependency] = lambda: fake
    return TestClient(app), fake


@pytest.mark.parametrize("prefix", ["/api/v1", "/api/mobile/v1"])
def test_management_gets_exact_source_blockers_with_pagination(prefix):
    client, fake = source_client()
    response = client.get(
        f"{prefix}/management/financial-accounting/period-close/{PERIOD_ID}/source-blockers",
        headers=headers(),
        params={"limit": 20, "offset": 0},
    )
    assert response.status_code == 200
    data = response.json()["data"]["source_coverage"]
    assert data["comprehensive_source_coverage"] is False
    assert data["blockers"][0]["amount"] == "100.00"
    assert data["limit"] == 20
    assert fake.calls == 1


@pytest.mark.parametrize("role,can_view", [("collector", True), ("management", False)])
def test_source_evidence_requires_management_and_accounting_view(role, can_view):
    client, fake = source_client(role, can_view)
    response = client.get(
        f"/api/v1/management/financial-accounting/period-close/{PERIOD_ID}/source-blockers",
        headers=headers(),
    )
    assert response.status_code == 403
    assert fake.calls == 0
