"""Current transaction-level actor, borrower, context and account authorization."""

import os

from psycopg import sql

from .employee_authorization import configured_employee_owner_id


class TreasuryDenied(RuntimeError):
    code = "treasury_access_denied"


class TreasuryConflict(RuntimeError):
    code = "treasury_conflict"


class TreasuryUnavailable(RuntimeError):
    code = "treasury_unavailable"


def readiness():
    enabled = os.getenv("SPINA_TREASURY_ENABLED", "").strip().lower() == "true"
    configured = configured_employee_owner_id() is not None
    return {
        "enabled": enabled,
        "owner_configured": configured,
        "blockers": ([] if enabled else ["Treasury entry is disabled."])
        + ([] if configured else ["Owner identity is not configured."]),
    }


def require_entry():
    state = readiness()
    if not state["enabled"] or not state["owner_configured"]:
        raise TreasuryUnavailable(
            "Treasury entry is disabled or owner identity is unconfigured."
        )


def is_owner(actor):
    return configured_employee_owner_id() == actor.user_id


def require_actor(conn, actor):
    if actor.registered_device_id is None:
        raise TreasuryDenied("An active registered account and device are required.")
    row = conn.execute(
        """select u.id from core.users u join core.devices d on d.user_id=u.id
        where u.id=%s and d.id=%s and u.status='active' and d.status='active'
        for share of u,d""",
        (actor.user_id, actor.registered_device_id),
    ).fetchone()
    if row is None:
        raise TreasuryDenied("An active registered account and device are required.")


def require_account(conn, actor, account_id, permission, *, lock=True, private=False):
    require_actor(conn, actor)
    account = conn.execute(
        sql.SQL("select * from treasury.accounts where id=%s for update")
        if lock
        else sql.SQL("select * from treasury.accounts where id=%s for share"),
        (account_id,),
    ).fetchone()
    if account is None:
        raise TreasuryDenied("The treasury account is unavailable.")
    if not account["active"]:
        raise TreasuryDenied("The treasury account is inactive.")
    context_owner = conn.execute(
        "select created_by from treasury.contexts where id=%s",
        (account["ledger_context_id"],),
    ).fetchone()
    if is_owner(actor) and context_owner["created_by"] == actor.user_id:
        return account
    grant = conn.execute(
        """select g.* from treasury.account_access g
        where g.account_id=%s and g.user_id=%s and g.enabled
        and %s=any(g.permissions) for share of g""",
        (account_id, actor.user_id, permission),
    ).fetchone()
    live_permission = conn.execute(
        """select rp.permission_code from core.user_roles ur
        join core.role_permissions rp on rp.role_id=ur.role_id where ur.user_id=%s and rp.permission_code=%s
        order by ur.role_id for share of ur,rp""",
        (actor.user_id, permission),
    ).fetchone()
    if (
        grant is None
        or live_permission is None
        or (private and not grant["private_history"])
    ):
        raise TreasuryDenied("Current permission and account scope are required.")
    account["_private_history"] = grant["private_history"]
    return account


def require_owner(conn, actor):
    require_actor(conn, actor)
    if not is_owner(actor):
        raise TreasuryDenied(
            "Only the configured owner may configure treasury accounts."
        )


def require_live_permission(conn, actor, permission):
    require_actor(conn, actor)
    if (
        conn.execute(
            """select 1 from core.user_roles ur join core.role_permissions rp on rp.role_id=ur.role_id
        where ur.user_id=%s and rp.permission_code=%s for share of ur,rp""",
            (actor.user_id, permission),
        ).fetchone()
        is None
    ):
        raise TreasuryDenied("Current protected source permission is required.")


def require_borrower(
    conn, actor, client_id, loan_ids, *, staff_permission=None, account_id=None
):
    require_actor(conn, actor)
    client = conn.execute(
        "select * from lending.clients where id=%s for share", (client_id,)
    ).fetchone()
    if client is None:
        raise TreasuryDenied("The borrower or claim is unavailable.")
    roles = {
        row["code"]
        for row in conn.execute(
            """select r.code from core.user_roles ur join core.roles r on r.id=ur.role_id
        where ur.user_id=%s for share of ur,r""",
            (actor.user_id,),
        ).fetchall()
    }
    if client["user_id"] != actor.user_id:
        if staff_permission is None or account_id is None:
            raise TreasuryDenied("The borrower or claim is unavailable.")
        require_account(conn, actor, account_id, staff_permission)
        # Current assigned route, never the claimed reporter's identity.
        conn.execute(
            """select id from lending.collector_area_assignments where is_active
            and lending.area_path_contains(area,%s,true) order by id for share""",
            (client["area"] or "",),
        ).fetchall()
        conn.execute(
            """select id from lending.collector_area_access_grants where visiting_collector_user_id=%s
            and revoked_at is null order by id for share""",
            (actor.user_id,),
        ).fetchall()
        assigned = conn.execute(
            """select lending.collector_area_owner(%s)=%s or
            lending.collector_has_active_delegated_area_access(%s,%s) as allowed""",
            (client["area"] or "", actor.user_id, actor.user_id, client["area"] or ""),
        ).fetchone()
        if (
            (
                staff_permission == "treasury.proof.submit.assigned"
                or "collector" in roles
            )
            and not is_owner(actor)
            and not assigned["allowed"]
        ):
            raise TreasuryDenied("Current borrower assignment is required.")
    elif "client" not in roles and not is_owner(actor):
        raise TreasuryDenied("Current Client own-borrower authority is required.")
    if len(set(loan_ids)) != len(loan_ids):
        raise TreasuryConflict("Loan intentions must be distinct.")
    rows = conn.execute(
        "select id from lending.loans where client_id=%s and id=any(%s) for share",
        (client_id, loan_ids),
    ).fetchall()
    if len(rows) != len(loan_ids):
        raise TreasuryDenied("The borrower or loan is unavailable.")
    return client
