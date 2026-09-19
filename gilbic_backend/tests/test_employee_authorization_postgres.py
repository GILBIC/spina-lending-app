"""Real private-schema and responsibility proof in the guarded disposable runner."""

from datetime import date
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.employee_authorization import (
    EmployeeAccessDenied,
    configure_employee_responsibility,
    require_employee_action,
    require_employee_actor,
    save_employee_journal_draft,
)
from gilbic_backend.first_loan_repository import FirstLoanAccessDenied, _actor
from test_client_cif_review_confirmation_postgres import (
    DATABASE_URL,
    connection as connection,
    runtime_url as runtime_url,
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="Guarded disposable database required"
)


def _staff(connection, role):
    uid, did = uuid4(), uuid4()
    connection.execute(
        "insert into core.users(id,username,full_name) values(%s,%s,%s)",
        (uid, f"synthetic-employee-{uid.hex}", "Synthetic employee"),
    )
    connection.execute(
        "insert into core.devices(id,user_id,device_identifier_hash,platform) values(%s,%s,%s,'android')",
        (did, uid, did.hex),
    )
    connection.execute(
        "insert into core.user_roles(user_id,role_id) select %s,id from core.roles where code=%s",
        (uid, role),
    )
    return AccountContext(
        user_id=uid,
        auth_user_id=uuid4(),
        username="synthetic",
        email=None,
        full_name="Synthetic",
        status="active",
        roles=(role,),
        permissions=(),
        device_registered=True,
        registered_device_id=did,
    )


def _roles(connection, uid):
    return {
        r["code"]
        for r in connection.execute(
            "select r.code from core.user_roles ur join core.roles r on r.id=ur.role_id where ur.user_id=%s",
            (uid,),
        ).fetchall()
    }


def test_additive_responsibility_retains_collector_and_cannot_approve_loans(
    connection, monkeypatch
):
    owner = _staff(connection, "management")
    combined = _staff(connection, "collector")
    monkeypatch.setenv("SPINA_EMPLOYEE_OWNER_USER_ID", str(owner.user_id))
    with connection.cursor(row_factory=dict_row) as c:
        configure_employee_responsibility(
            c, actor=owner, target_user_id=combined.user_id, enabled=True
        )
        assert _roles(connection, combined.user_id) == {
            "collector",
            "employee",
            "employee_manager",
        }
        require_employee_action(
            c,
            actor=combined,
            permission="employee_operations.manage",
            subject_user_id=uuid4(),
        )
        with pytest.raises(EmployeeAccessDenied):
            require_employee_action(
                c,
                actor=combined,
                permission="employee_operations.manage",
                subject_user_id=combined.user_id,
            )
        with pytest.raises(FirstLoanAccessDenied):
            _actor(
                c,
                combined.user_id,
                combined.registered_device_id,
                "lending.first_loan.approve",
                management=True,
            )
        configure_employee_responsibility(
            c, actor=owner, target_user_id=combined.user_id, enabled=False
        )
        assert _roles(connection, combined.user_id) == {"collector", "employee"}
        with pytest.raises(EmployeeAccessDenied):
            require_employee_action(
                c,
                actor=combined,
                permission="employee_operations.manage",
                subject_user_id=uuid4(),
            )
    assert (
        connection.execute(
            "select count(*) as n from core.audit_logs where actor_user_id=%s and action='employee.responsibility.change'",
            (owner.user_id,),
        ).fetchone()["n"]
        == 2
    )


def test_management_is_not_implicitly_employee_owner(connection, monkeypatch):
    owner = _staff(connection, "management")
    other = _staff(connection, "management")
    monkeypatch.setenv("SPINA_EMPLOYEE_OWNER_USER_ID", str(owner.user_id))
    with connection.cursor(row_factory=dict_row) as c:
        with pytest.raises(EmployeeAccessDenied):
            require_employee_action(
                c,
                actor=other,
                permission="employee_operations.manage",
                subject_user_id=uuid4(),
            )
        with pytest.raises(EmployeeAccessDenied):
            configure_employee_responsibility(
                c, actor=other, target_user_id=uuid4(), enabled=True
            )


@pytest.mark.parametrize("revocation", ["account", "device"])
def test_persisted_revocation_beats_old_context(connection, monkeypatch, revocation):
    owner = _staff(connection, "management")
    monkeypatch.setenv("SPINA_EMPLOYEE_OWNER_USER_ID", str(owner.user_id))
    if revocation == "account":
        connection.execute(
            "update core.users set status='inactive' where id=%s", (owner.user_id,)
        )
    else:
        connection.execute(
            "update core.devices set status='revoked' where id=%s",
            (owner.registered_device_id,),
        )
    with (
        connection.cursor(row_factory=dict_row) as c,
        pytest.raises(EmployeeAccessDenied),
    ):
        require_employee_actor(c, owner)


def test_preparation_creates_existing_accounting_draft_and_reuses_it(
    connection, monkeypatch
):
    owner = _staff(connection, "management")
    combined = _staff(connection, "collector")
    monkeypatch.setenv("SPINA_EMPLOYEE_OWNER_USER_ID", str(owner.user_id))
    connection.execute(
        "insert into accounting.fiscal_periods(label,start_date,end_date,status) values(%s,'2036-01-01','2036-01-31','open')",
        (f"Synthetic HR {uuid4().hex}",),
    )
    lines = [
        {"account_code": "1010", "debit": "100.00", "credit": "0.00"},
        {"account_code": "3000", "debit": "0.00", "credit": "100.00"},
    ]
    with connection.cursor(row_factory=dict_row) as c:
        configure_employee_responsibility(
            c, actor=owner, target_user_id=combined.user_id, enabled=True
        )
        entry = save_employee_journal_draft(
            c,
            actor=combined,
            posting_date=date(2036, 1, 5),
            description="Synthetic payroll",
            lines=lines,
        )
        assert (
            save_employee_journal_draft(
                c,
                actor=combined,
                posting_date=date(2036, 1, 5),
                description="Synthetic correction",
                lines=lines,
                entry_id=entry,
            )
            == entry
        )
    row = connection.execute(
        "select status,entry_number,description from accounting.journal_entries where id=%s",
        (entry,),
    ).fetchone()
    assert row["status"] == "draft" and row["entry_number"] is None
    assert row["description"] == "Synthetic correction"
    assert (
        connection.execute(
            "select count(*) as n from accounting.journal_lines where journal_entry_id=%s",
            (entry,),
        ).fetchone()["n"]
        == 2
    )
    with pytest.raises(psycopg.Error, match="unknown|inactive|non-posting"):
        with connection.transaction(), connection.cursor(row_factory=dict_row) as c:
            save_employee_journal_draft(
                c,
                actor=combined,
                posting_date=date(2036, 1, 5),
                description="Invalid account",
                lines=[{**lines[0], "account_code": "NONEXISTENT"}, lines[1]],
            )
