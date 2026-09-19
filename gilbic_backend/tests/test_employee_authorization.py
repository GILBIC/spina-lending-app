from types import SimpleNamespace
from datetime import date
from uuid import uuid4

import pytest

from gilbic_backend.employee_authorization import (
    EmployeeAccessDenied,
    configured_employee_owner_id,
    configure_employee_responsibility,
    is_employee_owner,
    require_employee_action,
    require_employee_actor,
    save_employee_journal_draft,
)


class Cursor:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append((query, params))
        return self

    def fetchone(self):
        return next(self.rows)

    def fetchall(self):
        return next(self.rows)


def actor():
    return SimpleNamespace(user_id=uuid4(), registered_device_id=uuid4())


@pytest.mark.parametrize("value", ["", "not-a-uuid"])
def test_owner_configuration_fails_closed(monkeypatch, value):
    monkeypatch.setenv("SPINA_EMPLOYEE_OWNER_USER_ID", value)
    assert configured_employee_owner_id() is None
    assert not is_employee_owner(actor())


def test_owner_is_explicit_identity_not_role(monkeypatch):
    owner = actor()
    monkeypatch.setenv("SPINA_EMPLOYEE_OWNER_USER_ID", str(owner.user_id))
    assert is_employee_owner(owner)
    assert not is_employee_owner(actor())


def test_stale_authenticated_context_cannot_bypass_revoked_device():
    with pytest.raises(EmployeeAccessDenied, match="active"):
        require_employee_actor(Cursor([None]), actor())


def test_permission_is_rechecked_in_transaction_not_taken_from_session(monkeypatch):
    monkeypatch.delenv("SPINA_EMPLOYEE_OWNER_USER_ID", raising=False)
    a = actor()
    a.permissions = ("employee_operations.manage",)
    with pytest.raises(EmployeeAccessDenied, match="permission"):
        require_employee_action(
            Cursor([{"id": a.user_id}, None]),
            actor=a,
            permission="employee_operations.manage",
        )


def test_even_configured_owner_cannot_approve_own_record(monkeypatch):
    a = actor()
    monkeypatch.setenv("SPINA_EMPLOYEE_OWNER_USER_ID", str(a.user_id))
    with pytest.raises(EmployeeAccessDenied, match="own"):
        require_employee_action(
            Cursor([{"id": a.user_id}]),
            actor=a,
            permission="employee_operations.manage",
            subject_user_id=a.user_id,
        )


def test_owner_can_approve_another_active_employee_without_role_inference(monkeypatch):
    a = actor()
    monkeypatch.setenv("SPINA_EMPLOYEE_OWNER_USER_ID", str(a.user_id))
    require_employee_action(
        Cursor([{"id": a.user_id}]),
        actor=a,
        permission="employee_operations.manage",
        subject_user_id=uuid4(),
    )


def test_narrow_manager_cannot_grant_responsibilities(monkeypatch):
    monkeypatch.delenv("SPINA_EMPLOYEE_OWNER_USER_ID", raising=False)
    with pytest.raises(EmployeeAccessDenied, match="owner"):
        configure_employee_responsibility(
            Cursor([]), actor=actor(), target_user_id=uuid4(), enabled=True
        )


def test_combined_role_refuses_management_membership(monkeypatch):
    a = actor()
    monkeypatch.setenv("SPINA_EMPLOYEE_OWNER_USER_ID", str(a.user_id))
    cursor = Cursor(
        [
            {"id": a.user_id},
            {"id": uuid4()},
            [{"code": "collector"}, {"code": "management"}],
        ]
    )
    with pytest.raises(EmployeeAccessDenied, match="Management"):
        configure_employee_responsibility(
            cursor, actor=a, target_user_id=uuid4(), enabled=True
        )
    assert not any(
        "insert into core.user_roles" in sql.lower() for sql, _ in cursor.calls
    )


def test_combined_responsibility_preserves_existing_memberships(monkeypatch):
    a = actor()
    target = uuid4()
    monkeypatch.setenv("SPINA_EMPLOYEE_OWNER_USER_ID", str(a.user_id))
    cursor = Cursor(
        [
            {"id": a.user_id},
            {"id": target},
            [{"code": "collector"}],
            [{"code": "employee"}, {"code": "employee_manager"}],
        ]
    )
    configure_employee_responsibility(
        cursor, actor=a, target_user_id=target, enabled=True
    )
    assert not any(
        "delete from core.user_roles" in sql.lower() for sql, _ in cursor.calls
    )
    inserts = [
        params
        for sql, params in cursor.calls
        if "insert into core.user_roles" in sql.lower()
    ]
    assert inserts and inserts[0][0] == target


def test_journal_preparation_uses_existing_ledger_in_same_transaction(monkeypatch):
    a = actor()
    entry_id = uuid4()
    monkeypatch.setenv("SPINA_EMPLOYEE_OWNER_USER_ID", str(a.user_id))
    cursor = Cursor([{"id": a.user_id}, {"entry_id": entry_id}])
    result = save_employee_journal_draft(
        cursor,
        actor=a,
        posting_date=date(2026, 9, 20),
        description="Payroll draft",
        lines=[
            {"account_code": "1010", "debit": "100.00", "credit": "0.00"},
            {"account_code": "3000", "debit": "0.00", "credit": "100.00"},
        ],
    )
    assert result == entry_id
    assert any(
        "accounting.create_manual_journal_draft" in sql for sql, _ in cursor.calls
    )
    assert not any("post_manual_journal_entry" in sql for sql, _ in cursor.calls)


def test_preparation_cannot_overwrite_posted_journal(monkeypatch):
    a = actor()
    monkeypatch.setenv("SPINA_EMPLOYEE_OWNER_USER_ID", str(a.user_id))
    cursor = Cursor(
        [
            {"id": a.user_id},
            {
                "status": "posted",
                "source_type": "manual",
                "created_by_user_id": a.user_id,
            },
        ]
    )
    with pytest.raises(EmployeeAccessDenied, match="draft"):
        save_employee_journal_draft(
            cursor,
            actor=a,
            posting_date=date(2026, 9, 20),
            description="Wrong overwrite",
            lines=[],
            entry_id=uuid4(),
        )


def test_manager_cannot_overwrite_another_preparers_draft(monkeypatch):
    monkeypatch.delenv("SPINA_EMPLOYEE_OWNER_USER_ID", raising=False)
    a = actor()
    cursor = Cursor(
        [
            {"id": a.user_id},
            {"permission_code": "accounting.journal.prepare"},
            {"status": "draft", "source_type": "manual", "created_by_user_id": uuid4()},
        ]
    )
    with pytest.raises(EmployeeAccessDenied, match="creator"):
        save_employee_journal_draft(
            cursor,
            actor=a,
            posting_date=date(2026, 9, 20),
            description="Wrong actor",
            lines=[],
            entry_id=uuid4(),
        )
