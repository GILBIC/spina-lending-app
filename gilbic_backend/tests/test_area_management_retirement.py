from __future__ import annotations

import inspect
from contextlib import AbstractContextManager
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

import gilbic_backend.area_management_repository as repository_module
from gilbic_backend.area_management_repository import PostgresAreaManagementRepository


AREA_UID = UUID("00000000-0000-0000-0000-000000000601")
PARENT_UID = UUID("00000000-0000-0000-0000-000000000602")
ACTOR_UID = UUID("00000000-0000-0000-0000-0000000000a1")


class _Cursor(AbstractContextManager):
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        self.calls.append((" ".join(sql.lower().split()), tuple(params)))


class _Connection(AbstractContextManager):
    def __init__(self, cursor: _Cursor) -> None:
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self, *, row_factory=None):
        return self._cursor


def _preview(**overrides):
    values = {
        "area_uid": AREA_UID,
        "full_path": "Cardona › Calahan",
        "is_active": True,
        "active_direct_client_count": 0,
        "active_subtree_client_count": 0,
        "active_collector_assignment_count": 0,
        "pending_transfer_target_count": 0,
        "descendant_count": 0,
        "active_descendant_count": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _install_connection(monkeypatch: pytest.MonkeyPatch) -> _Cursor:
    cursor = _Cursor()
    monkeypatch.setattr(
        repository_module,
        "open_connection",
        lambda: _Connection(cursor),
    )
    return cursor


def test_retirement_lifecycle_interfaces_are_present() -> None:
    repository = PostgresAreaManagementRepository()

    for method_name in ("preview_retirement", "retire_area", "reactivate_area"):
        assert callable(getattr(repository, method_name))


def test_preview_retirement_returns_the_repository_operational_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = _preview(
        active_direct_client_count=1,
        active_subtree_client_count=2,
        active_collector_assignment_count=1,
        pending_transfer_target_count=1,
        descendant_count=3,
        active_descendant_count=2,
    )
    seen: list[tuple[UUID, bool]] = []

    def fake_preview(cursor, area_uid: UUID, *, for_update: bool):
        seen.append((area_uid, for_update))
        return expected

    monkeypatch.setattr(
        repository_module,
        "_retirement_preview",
        fake_preview,
        raising=False,
    )
    _install_connection(monkeypatch)

    result = PostgresAreaManagementRepository().preview_retirement(area_uid=AREA_UID)

    assert result is expected
    assert seen == [(AREA_UID, False)]


@pytest.mark.parametrize(
    "blocking_field",
    [
        "active_subtree_client_count",
        "active_collector_assignment_count",
        "pending_transfer_target_count",
        "active_descendant_count",
    ],
)
def test_retire_area_rejects_each_operational_blocker(
    monkeypatch: pytest.MonkeyPatch,
    blocking_field: str,
) -> None:
    blocked = _preview(**{blocking_field: 1})
    monkeypatch.setattr(
        repository_module,
        "_retirement_preview",
        lambda cursor, area_uid, *, for_update: blocked,
        raising=False,
    )
    cursor = _install_connection(monkeypatch)

    with pytest.raises(ValueError):
        PostgresAreaManagementRepository().retire_area(
            actor_user_id=ACTOR_UID,
            area_uid=AREA_UID,
        )

    assert not any("update lending.area_nodes" in sql for sql, _params in cursor.calls)


def test_retire_area_inactivates_clear_node_without_deleting_and_audits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear = _preview(descendant_count=2)
    monkeypatch.setattr(
        repository_module,
        "_retirement_preview",
        lambda cursor, area_uid, *, for_update: clear,
        raising=False,
    )
    audits: list[dict[str, Any]] = []
    monkeypatch.setattr(
        repository_module,
        "_write_area_audit",
        lambda cursor, **kwargs: audits.append(kwargs),
    )
    cursor = _install_connection(monkeypatch)

    result = PostgresAreaManagementRepository().retire_area(
        actor_user_id=ACTOR_UID,
        area_uid=AREA_UID,
    )

    assert result == AREA_UID
    assert any(
        "update lending.area_nodes" in sql and "set is_active = false" in sql
        for sql, _params in cursor.calls
    )
    assert not any("delete from lending.area_nodes" in sql for sql, _params in cursor.calls)
    assert audits == [
        {
            "actor_user_id": ACTOR_UID,
            "action": "area.retired",
            "target_type": "area",
            "target_id": AREA_UID,
            "details": {
                "area_path": "Cardona › Calahan",
                "descendant_count": 2,
            },
        }
    ]


def test_reactivate_area_fails_closed_when_parent_is_inactive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = iter(
        [
            {
                "area_uid": AREA_UID,
                "parent_area_uid": PARENT_UID,
                "full_path": "Cardona › Calahan",
                "is_active": False,
            },
            {
                "area_uid": PARENT_UID,
                "parent_area_uid": None,
                "full_path": "Cardona",
                "is_active": False,
            },
        ]
    )
    monkeypatch.setattr(
        repository_module,
        "_node_by_uid",
        lambda cursor, area_uid, *, for_update=False: next(rows),
    )
    cursor = _install_connection(monkeypatch)

    with pytest.raises(ValueError):
        PostgresAreaManagementRepository().reactivate_area(
            actor_user_id=ACTOR_UID,
            area_uid=AREA_UID,
        )

    assert not any("update lending.area_nodes" in sql for sql, _params in cursor.calls)


def test_reactivate_area_updates_only_current_area_state_and_audits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = iter(
        [
            {
                "area_uid": AREA_UID,
                "parent_area_uid": PARENT_UID,
                "full_path": "Cardona › Calahan",
                "is_active": False,
            },
            {
                "area_uid": PARENT_UID,
                "parent_area_uid": None,
                "full_path": "Cardona",
                "is_active": True,
            },
        ]
    )
    monkeypatch.setattr(
        repository_module,
        "_node_by_uid",
        lambda cursor, area_uid, *, for_update=False: next(rows),
    )
    audits: list[dict[str, Any]] = []
    monkeypatch.setattr(
        repository_module,
        "_write_area_audit",
        lambda cursor, **kwargs: audits.append(kwargs),
    )
    cursor = _install_connection(monkeypatch)

    result = PostgresAreaManagementRepository().reactivate_area(
        actor_user_id=ACTOR_UID,
        area_uid=AREA_UID,
    )

    assert result == AREA_UID
    assert any(
        "update lending.area_nodes" in sql and "set is_active = true" in sql
        for sql, _params in cursor.calls
    )
    assert audits == [
        {
            "actor_user_id": ACTOR_UID,
            "action": "area.reactivated",
            "target_type": "area",
            "target_id": AREA_UID,
            "details": {"area_path": "Cardona › Calahan"},
        }
    ]


def test_retirement_source_contract_is_hierarchy_safe_and_history_preserving() -> None:
    source = inspect.getsource(repository_module).lower()

    for method_name in ("_retirement_preview", "preview_retirement", "retire_area", "reactivate_area"):
        assert f"def {method_name}" in source

    assert "with recursive" in source
    assert "lending.clients" in source
    assert "lending.collector_area_assignments" in source
    assert "lending.client_area_pending_transfers" in source
    assert "set is_active = false" in source
    assert "set is_active = true" in source
    assert 'action="area.retired"' in source
    assert 'action="area.reactivated"' in source
    assert "delete from lending.area_nodes" not in source

    for forbidden in (
        "update lending.collection_transactions",
        "delete from lending.collection_transactions",
        "update lending.collection_remittances",
        "delete from lending.collection_remittances",
        "update accounting.",
        "delete from accounting.",
    ):
        assert forbidden not in source
