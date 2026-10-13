"""Transfer preview and commit share the collections Manila business clock."""

from contextlib import contextmanager
from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from gilbic_backend.account_repository import AccountContext

from gilbic_backend import area_management_api as api
from gilbic_backend import area_management_repository as repo
from gilbic_backend import collection_posting

ACTOR, CLIENT, OLD, NEW, OLD_OWNER, NEW_OWNER, DEVICE = [
    UUID(int=n) for n in range(1, 8)
]
NEXT_DAY = date(2026, 10, 10)


class Cursor:
    """Bounded synthetic SQL boundary; real repository chooses all SQL/branches."""

    def __init__(self):
        self.row = None
        self.queried_collection_dates = []
        self.updated_client = False
        self.inserted_pending = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, query, params=()):
        sql = " ".join(str(query).lower().split())
        if "select exists" in sql and "collection_transactions" in sql:
            self.queried_collection_dates.append(params[1])
            self.row = {"collected_today": params[1] == date(2026, 10, 9)}
        elif "as next_collection_date" in sql:
            self.row = {"next_collection_date": NEXT_DAY}
        elif "from lending.clients client" in sql:
            self.row = {
                "id": CLIENT,
                "area_uid": OLD,
                "area_path": "Old area",
                "status": "active",
            }
        elif "from lending.area_nodes" in sql:
            self.row = {"area_uid": NEW, "full_path": "New area", "is_active": True}
        elif "collector_area_owner" in sql:
            self.row = {
                "old_collector_user_id": OLD_OWNER,
                "new_collector_user_id": NEW_OWNER,
            }
        elif "select id, target_area_uid, effective_date" in sql:
            self.row = None
        elif sql.startswith("update lending.clients"):
            self.updated_client = True
        elif sql.startswith("insert into lending.client_area_pending_transfers"):
            self.inserted_pending = True
        elif sql.startswith(
            (
                "insert into lending.client_area_transfer_history",
                "insert into core.audit_logs",
            )
        ):
            pass
        else:
            raise AssertionError(f"Unexpected SQL: {sql}")
        return self

    def fetchone(self):
        return self.row


@pytest.mark.parametrize(
    "hour,want_date,want_timing,want_effective",
    [
        (15, date(2026, 10, 8), "immediate", "2026-10-08"),
        (16, date(2026, 10, 9), "next_collection_day", "2026-10-10"),
    ],
)
@pytest.mark.parametrize("host_day", [date(2026, 10, 8), date(2026, 10, 9)])
@pytest.mark.parametrize("operation", ["preview", "commit"])
def test_transfer_uses_manila_date_at_utc_boundary(
    monkeypatch, hour, want_date, want_timing, want_effective, host_day, operation
):
    instant = datetime(2026, 10, 8, hour, 30, tzinfo=UTC)

    class HostDate(date):
        @classmethod
        def today(cls):
            return host_day

    class ServerDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz)

    cursor = Cursor()

    class Connection:
        def cursor(self, **kwargs):
            return cursor

    @contextmanager
    def synthetic_connection():
        yield Connection()

    actor = AccountContext(
        ACTOR,
        ACTOR,
        "reviewer",
        None,
        "Synthetic Staff",
        "active",
        ("employee",),
        ("area.client.assign",),
        True,
        DEVICE,
    )
    app = FastAPI()
    app.include_router(api.create_area_management_router())
    app.dependency_overrides[api.area_staff_context] = lambda: actor
    monkeypatch.setattr(api, "date", HostDate, raising=False)
    monkeypatch.setattr(collection_posting, "datetime", ServerDatetime)
    monkeypatch.setattr(repo, "open_connection", synthetic_connection)
    with TestClient(app) as client:
        if operation == "preview":
            response = client.get(
                f"/api/v1/clients/{CLIENT}/area-transfer-preview",
                params={"target_area_id": str(NEW)},
            )
        else:
            response = client.post(
                f"/api/v1/clients/{CLIENT}/area-transfer",
                json={"target_area_id": str(NEW)},
            )
    assert response.status_code == 200, response.text
    value = response.json()["data"]
    assert value["timing"] == want_timing
    assert value["effective_date"] == want_effective
    assert cursor.queried_collection_dates == [want_date]
    assert cursor.updated_client is (
        operation == "commit" and want_timing == "immediate"
    )
    assert cursor.inserted_pending is (
        operation == "commit" and want_timing == "next_collection_day"
    )
