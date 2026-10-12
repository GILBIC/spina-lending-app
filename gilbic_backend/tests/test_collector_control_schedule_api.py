from datetime import date

import pytest
from test_accounting_book_api import ACTOR, HEADERS, FakeAccounts
from test_collector_liability_accounting_api import BASE, client_for


def schedule_client(accounts=None):
    client, repo = client_for(accounts)
    repo.control_schedule = lambda actor, **values: repo.invoke(
        "control_schedule", actor, **values
    )
    return client, repo


@pytest.mark.parametrize("mobile", [False, True])
def test_schedule_is_private_read_only_and_accepts_view_without_journal_manage(mobile):
    client, repo = schedule_client(FakeAccounts(permissions=("accounting.view",)))
    base = BASE.replace("/api/v1/", "/api/mobile/v1/") if mobile else BASE
    response = client.get(
        f"{base}/control-schedule?as_of=2026-09-30&limit=20&offset=40",
        headers=HEADERS,
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert repo.calls == [
        (
            "control_schedule",
            ACTOR,
            {"as_of": date(2026, 9, 30), "limit": 20, "offset": 40},
        )
    ]


@pytest.mark.parametrize(
    "query", ["as_of=2026-02-30", "limit=0", "limit=501", "offset=-1"]
)
def test_schedule_rejects_invalid_cutoff_and_pagination(query):
    client, repo = schedule_client()
    response = client.get(f"{BASE}/control-schedule?{query}", headers=HEADERS)
    assert response.status_code == 422
    assert repo.calls == []


@pytest.mark.parametrize(
    "accounts",
    [
        FakeAccounts(role="collector"),
        FakeAccounts(permissions=()),
        FakeAccounts(status="inactive"),
    ],
)
def test_schedule_requires_current_management_accounting_view(accounts):
    client, repo = schedule_client(accounts)
    assert client.get(f"{BASE}/control-schedule", headers=HEADERS).status_code == 403
    assert repo.calls == []
