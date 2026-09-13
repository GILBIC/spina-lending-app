from __future__ import annotations

from contextlib import AbstractContextManager
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

import gilbic_backend.area_management_repository as repository_module
from gilbic_backend.area_management_repository import PostgresAreaManagementRepository


class _Cursor(AbstractContextManager):
    def __init__(self, rows: list[dict[str, Any]], calls: list[tuple[str, tuple[Any, ...]]]):
        self._rows = rows
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        self._calls.append((" ".join(sql.lower().split()), tuple(params)))

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Connection(AbstractContextManager):
    def __init__(self, rows: list[dict[str, Any]], calls: list[tuple[str, tuple[Any, ...]]]):
        self._rows = rows
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self, *, row_factory=None):
        return _Cursor(self._rows, self._calls)


class _ConnectionFactory:
    def __init__(self, responses: list[list[dict[str, Any]]]):
        self._responses = list(responses)
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def __call__(self):
        assert self._responses, "Unexpected extra database connection."
        return _Connection(self._responses.pop(0), self.calls)


def _collector(user_id: UUID, name: str) -> dict[str, Any]:
    return {
        "collector_user_id": user_id,
        "collector_username": name.lower().replace(" ", "."),
        "collector_full_name": name,
    }


def test_list_tree_preserves_server_order_and_distinguishes_explicit_from_inherited_owner(monkeypatch) -> None:
    collector_a = UUID("00000000-0000-0000-0000-0000000000a1")
    cardona = UUID("00000000-0000-0000-0000-000000000101")
    calahan = UUID("00000000-0000-0000-0000-000000000102")
    balayong = UUID("00000000-0000-0000-0000-000000000103")
    legacy = UUID("00000000-0000-0000-0000-000000000104")
    rows = [
        {
            "area_uid": calahan,
            "parent_area_uid": cardona,
            "name": "Calahan",
            "full_path": "Cardona › Calahan",
            "depth": 1,
            "sort_order": 0,
            "is_active": True,
            "is_legacy_unmapped": False,
            "explicit_collector_user_id": collector_a,
            "explicit_collector_username": "collector.a",
            "explicit_collector_full_name": "Collector A",
            "effective_collector_user_id": collector_a,
            "effective_collector_username": "collector.a",
            "effective_collector_full_name": "Collector A",
            "effective_collector_source_area_uid": calahan,
            "direct_client_count": 2,
            "subtree_client_count": 5,
            "child_count": 2,
        },
        {
            "area_uid": balayong,
            "parent_area_uid": calahan,
            "name": "Balayong",
            "full_path": "Cardona › Calahan › Balayong",
            "depth": 2,
            "sort_order": 0,
            "is_active": True,
            "is_legacy_unmapped": False,
            "explicit_collector_user_id": None,
            "explicit_collector_username": None,
            "explicit_collector_full_name": None,
            "effective_collector_user_id": collector_a,
            "effective_collector_username": "collector.a",
            "effective_collector_full_name": "Collector A",
            "effective_collector_source_area_uid": calahan,
            "direct_client_count": 3,
            "subtree_client_count": 3,
            "child_count": 0,
        },
        {
            "area_uid": legacy,
            "parent_area_uid": None,
            "name": "OLD CARDONA / CALAHAN",
            "full_path": "OLD CARDONA / CALAHAN",
            "depth": 0,
            "sort_order": 9,
            "is_active": True,
            "is_legacy_unmapped": True,
            "explicit_collector_user_id": None,
            "explicit_collector_username": None,
            "explicit_collector_full_name": None,
            "effective_collector_user_id": None,
            "effective_collector_username": None,
            "effective_collector_full_name": None,
            "effective_collector_source_area_uid": None,
            "direct_client_count": 1,
            "subtree_client_count": 1,
            "child_count": 0,
        },
    ]
    factory = _ConnectionFactory([rows])
    monkeypatch.setattr(repository_module, "open_connection", factory)

    result = PostgresAreaManagementRepository().list_tree()

    assert [node.area_uid for node in result] == [calahan, balayong, legacy]
    assert result[0].explicit_collector is not None
    assert result[0].explicit_collector.user_id == collector_a
    assert result[1].explicit_collector is None
    assert result[1].effective_collector is not None
    assert result[1].effective_collector.user_id == collector_a
    assert result[1].effective_collector_source_area_uid == calahan
    assert result[2].is_legacy_unmapped is True
    assert result[0].subtree_client_count == 5
    assert result[1].direct_client_count == 3

    sql, params = factory.calls[0]
    assert "with recursive" in sql
    assert "parent_area_uid" in sql
    assert "lending.collector_area_owner" in sql
    assert params == (False,)


def test_list_tree_inactive_visibility_is_explicit(monkeypatch) -> None:
    inactive = UUID("00000000-0000-0000-0000-000000000201")
    row = {
        "area_uid": inactive,
        "parent_area_uid": None,
        "name": "Retired Area",
        "full_path": "Retired Area",
        "depth": 0,
        "sort_order": 0,
        "is_active": False,
        "is_legacy_unmapped": False,
        "explicit_collector_user_id": None,
        "explicit_collector_username": None,
        "explicit_collector_full_name": None,
        "effective_collector_user_id": None,
        "effective_collector_username": None,
        "effective_collector_full_name": None,
        "effective_collector_source_area_uid": None,
        "direct_client_count": 0,
        "subtree_client_count": 0,
        "child_count": 0,
    }
    factory = _ConnectionFactory([[], [row]])
    monkeypatch.setattr(repository_module, "open_connection", factory)
    repo = PostgresAreaManagementRepository()

    assert repo.list_tree() == ()
    shown = repo.list_tree(include_inactive=True)
    assert len(shown) == 1
    assert shown[0].is_active is False
    assert factory.calls[0][1] == (False,)
    assert factory.calls[1][1] == (True,)


def test_list_collectors_queries_active_collector_accounts_only(monkeypatch) -> None:
    collector_a = UUID("00000000-0000-0000-0000-0000000000a1")
    rows = [{**_collector(collector_a, "Collector A")}]
    factory = _ConnectionFactory([rows])
    monkeypatch.setattr(repository_module, "open_connection", factory)

    result = PostgresAreaManagementRepository().list_collectors()

    assert len(result) == 1
    assert result[0].user_id == collector_a
    assert result[0].full_name == "Collector A"
    sql, _ = factory.calls[0]
    assert "role.code = 'collector'" in sql
    assert "account.status = 'active'" in sql


def test_search_clients_returns_only_operational_identity_and_area_context(monkeypatch) -> None:
    client_id = UUID("00000000-0000-0000-0000-000000000301")
    area_uid = UUID("00000000-0000-0000-0000-000000000302")
    collector_a = UUID("00000000-0000-0000-0000-0000000000a1")
    rows = [
        {
            "client_id": client_id,
            "client_code": "C-0001",
            "full_name": "Ana Client",
            "area_uid": area_uid,
            "area_path": "Cardona › Calahan › Balayong",
            "effective_collector_user_id": collector_a,
            "effective_collector_username": "collector.a",
            "effective_collector_full_name": "Collector A",
        }
    ]
    factory = _ConnectionFactory([rows])
    monkeypatch.setattr(repository_module, "open_connection", factory)

    result = PostgresAreaManagementRepository().search_clients("Ana", limit=10)

    assert len(result) == 1
    client = result[0]
    assert client.client_id == client_id
    assert client.client_code == "C-0001"
    assert client.area_uid == area_uid
    assert client.area_path == "Cardona › Calahan › Balayong"
    assert client.effective_collector is not None
    assert client.effective_collector.user_id == collector_a
    assert not hasattr(client, "national_id")
    assert not hasattr(client, "meralco")
    assert not hasattr(client, "evidence")

    sql, params = factory.calls[0]
    for forbidden in ("national_id", "meralco", "onboarding", "evidence", "photo"):
        assert forbidden not in sql
    assert "lending.collector_area_owner" in sql
    assert params == ("%Ana%", "%Ana%", 10)


def test_effective_collector_delegates_precedence_to_database_function(monkeypatch) -> None:
    collector_a = UUID("00000000-0000-0000-0000-0000000000a1")
    factory = _ConnectionFactory([[{"collector_user_id": collector_a}]])
    monkeypatch.setattr(repository_module, "open_connection", factory)

    result = PostgresAreaManagementRepository().effective_collector(
        "Cardona › Calahan › Balayong"
    )

    assert result == collector_a
    sql, params = factory.calls[0]
    assert "lending.collector_area_owner" in sql
    assert params == ("Cardona › Calahan › Balayong",)
