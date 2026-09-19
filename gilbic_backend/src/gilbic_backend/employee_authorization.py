"""Transactional access checks for employee records and additive responsibilities.

The owner is explicitly configured; primary display roles never confer ownership.
These helpers run inside the caller's transaction, including any audit writes.
"""

from __future__ import annotations

import os
from datetime import date
from uuid import UUID

from psycopg.types.json import Jsonb

from .account_repository import AccountContext


class EmployeeAccessDenied(RuntimeError):
    code = "employee_access_denied"


def configured_employee_owner_id() -> UUID | None:
    value = os.getenv("SPINA_EMPLOYEE_OWNER_USER_ID", "").strip()
    try:
        return UUID(value) if value else None
    except ValueError:
        return None


def is_employee_owner(actor: AccountContext) -> bool:
    owner_id = configured_employee_owner_id()
    return owner_id is not None and owner_id == actor.user_id


def require_employee_actor(cursor, actor: AccountContext) -> None:
    """Recheck account/device state under locks, including writes after login."""
    if actor.registered_device_id is None:
        raise EmployeeAccessDenied("An active staff account and device are required.")
    row = cursor.execute(
        """select u.id from core.users u join core.devices d on d.user_id=u.id
        where u.id=%s and d.id=%s and u.status='active' and d.status='active'
        and exists(select 1 from core.user_roles ur join core.roles r on r.id=ur.role_id
                   where ur.user_id=u.id and r.code in ('collector','employee','management'))
        for share of u,d""",
        (actor.user_id, actor.registered_device_id),
    ).fetchone()
    if row is None:
        raise EmployeeAccessDenied("An active staff account and device are required.")


def require_employee_action(
    cursor,
    *,
    actor: AccountContext,
    permission: str,
    subject_user_id: UUID | None = None,
) -> None:
    require_employee_actor(cursor, actor)
    if subject_user_id is not None and actor.user_id == subject_user_id:
        raise EmployeeAccessDenied("You cannot approve your own employee record.")
    if is_employee_owner(actor):
        return
    row = cursor.execute(
        """select rp.permission_code from core.user_roles ur
        join core.role_permissions rp on rp.role_id=ur.role_id
        where ur.user_id=%s and rp.permission_code=%s
        for share of ur,rp""",
        (actor.user_id, permission),
    ).fetchone()
    if row is None:
        raise EmployeeAccessDenied(
            "The required employee permission is no longer active."
        )


def configure_employee_responsibility(
    cursor,
    *,
    actor: AccountContext,
    target_user_id: UUID,
    enabled: bool,
) -> None:
    """Manage only the staff-manager responsibility, preserving base memberships.

    Enabling adds office Employee access alongside existing Collector access. Revoking
    the responsibility removes employee_manager only; base office/collector roles are
    not implicitly revoked by a payroll/profile edit.
    """
    if not is_employee_owner(actor):
        raise EmployeeAccessDenied(
            "Only the configured owner can change responsibilities."
        )
    require_employee_actor(cursor, actor)
    target = cursor.execute(
        "select id from core.users where id=%s and status='active' for update",
        (target_user_id,),
    ).fetchone()
    if target is None:
        raise EmployeeAccessDenied("An active employee account is required.")
    roles = cursor.execute(
        """select r.code from core.user_roles ur join core.roles r on r.id=ur.role_id
        where ur.user_id=%s for share of ur""",
        (target_user_id,),
    ).fetchall()
    role_codes = {row["code"] for row in roles}
    if enabled:
        if "management" in role_codes:
            raise EmployeeAccessDenied(
                "Remove unrestricted Management access before assigning combined staff duties."
            )
        if "collector" not in role_codes:
            raise EmployeeAccessDenied(
                "Combined staff duties require an existing Collector account."
            )
        available = cursor.execute(
            "select code from core.roles where code in ('employee','employee_manager')"
        ).fetchall()
        if {row["code"] for row in available} != {"employee", "employee_manager"}:
            raise EmployeeAccessDenied(
                "Employee responsibility setup is not available."
            )
        cursor.execute(
            """insert into core.user_roles(user_id,role_id)
            select %s,id from core.roles where code in ('employee','employee_manager')
            on conflict do nothing""",
            (target_user_id,),
        )
    else:
        cursor.execute(
            """delete from core.user_roles ur using core.roles r
            where ur.role_id=r.id and ur.user_id=%s and r.code='employee_manager'""",
            (target_user_id,),
        )
    cursor.execute(
        """insert into core.audit_logs(actor_user_id,action,target_type,target_id,details)
        values(%s,'employee.responsibility.change','user',%s,%s)""",
        (
            actor.user_id,
            target_user_id,
            Jsonb({"responsibility": "employee_manager", "enabled": enabled}),
        ),
    )


def save_employee_journal_draft(
    cursor,
    *,
    actor: AccountContext,
    posting_date: date,
    description: str,
    lines: list[dict[str, object]],
    entry_id: UUID | None = None,
) -> UUID:
    """Use existing accounting validation/ledger within the HR action transaction.

    The caller persists the returned link and idempotency result in that transaction.
    The established SQL functions validate balances and exact active posting accounts;
    this helper never posts, reverses or creates a second accounting ledger.
    """
    require_employee_action(
        cursor, actor=actor, permission="accounting.journal.prepare"
    )
    if entry_id is None:
        row = cursor.execute(
            """select accounting.create_manual_journal_draft(%s,%s,%s,%s::jsonb)
            as entry_id""",
            (posting_date, description, actor.user_id, Jsonb(lines)),
        ).fetchone()
        return UUID(str(row["entry_id"]))
    entry = cursor.execute(
        """select status,source_type,created_by_user_id from accounting.journal_entries
        where id=%s for update""",
        (entry_id,),
    ).fetchone()
    if entry is None or entry["status"] != "draft" or entry["source_type"] != "manual":
        raise EmployeeAccessDenied(
            "Only an existing manual journal draft can be prepared."
        )
    if not is_employee_owner(actor) and entry["created_by_user_id"] != actor.user_id:
        raise EmployeeAccessDenied(
            "Only the draft creator or owner can edit this preparation."
        )
    cursor.execute(
        "select accounting.update_manual_journal_draft(%s,%s,%s,%s,%s::jsonb)",
        (entry_id, posting_date, description, actor.user_id, Jsonb(lines)),
    )
    return entry_id
