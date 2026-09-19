"""Scoped projections. Capability flags guide clients; commands recheck authority."""

from datetime import date, datetime
from decimal import Decimal

from .employee_authorization import configured_employee_owner_id, is_employee_owner
from .employee_operations import MANILA, EmployeeConflict
from .employee_operations_repository import TABLES, plain


def capabilities(tx):
    owner = is_employee_owner(tx.actor)
    manager = tx.manager()
    profile = tx.profile(tx.actor.user_id, required=False)
    own = bool(profile and profile["payload"]["active"])
    return {
        "can_self_service": own,
        "can_manage_staff": owner or manager,
        "can_configure": owner,
        "can_prepare_payroll": owner or manager or tx.backup("prepare_payroll"),
        "can_approve_payroll": owner or manager or tx.backup("approve_payroll"),
        "can_record_payments": owner,
        "can_assign_tasks": owner or manager or tx.backup("assign_tasks"),
        "can_review_requests": owner or manager or tx.backup("review_requests"),
        "can_review_shortages": owner,
        "can_prepare_accounting": owner or manager,
        "can_view_statutory": owner or manager,
        "can_report_shortage": owner or manager or own,
        "can_record_advances": owner,
    }


def allowed(tx, domain, row, caps):
    own = row["employee_id"] == str(tx.actor.user_id)
    owner = is_employee_owner(tx.actor)
    status = row["status"]
    actions = []
    simple = {
        "profiles": "profile_save",
        "backups": "backup_save",
        "calendar": "calendar_save",
        "statutory_months": "statutory_month_save",
    }
    if domain in simple and owner:
        return [simple[domain]]
    if domain == "requests":
        if status == "pending" and (own or caps["can_review_requests"]):
            actions = ["request_decide"]
        elif status == "approved" and not own and caps["can_review_requests"]:
            p = row["payload"]
            effective = p.get("work_date", p.get("effective_from", p.get("as_of", "")))
            if effective > tx.today.isoformat():
                actions = ["request_decide"]
    elif domain == "tasks":
        assigner = owner or row["created_by"] == str(tx.actor.user_id)
        if own or assigner:
            actions = ["task_progress"]
        if assigner and status not in ("done", "cancelled"):
            actions.append("task_save")
    elif domain == "advances":
        if own and status not in ("rejected", "repaid"):
            actions.append("advance_terms")
        if (
            not own
            and status in ("requested", "terms_pending")
            and (owner or tx.manager() or tx.backup("approve_advances"))
        ):
            actions.append("advance_decide")
        if owner and status == "approved":
            actions.append("advance_disburse")
        if owner and status == "disbursed":
            actions.append("advance_repay")
    elif domain == "shortages":
        if own and status in ("reported", "responded"):
            actions = ["shortage_respond"]
        if owner and not own and status in ("reported", "responded", "confirmed"):
            actions.append("shortage_decide")
    elif domain == "payroll":
        if (
            caps["can_prepare_payroll"]
            and status in ("draft", "rejected", "stale", "approved")
            and Decimal(row["payload"].get("paid_amount", "0")) == 0
            and not row["payload"].get("original_payroll_id")
        ):
            actions.append("payroll_prepare")
        if not own and caps["can_approve_payroll"] and status == "draft":
            actions.append("payroll_approve")
        if owner and status in ("approved", "partially_paid"):
            actions.append("payroll_payment")
        if owner and status in ("paid", "partially_paid"):
            actions.append("payroll_adjustment")
    elif (
        domain == "accounting_preparations"
        and caps["can_prepare_accounting"]
        and (owner or row["created_by"] == str(tx.actor.user_id))
    ):
        actions = ["accounting_prepare"]
    return actions


def build_workspace(tx, request_id=None):
    caps = capabilities(tx)
    owner = is_employee_owner(tx.actor)
    manager = tx.manager()
    actor_id = str(tx.actor.user_id)
    any_review = any(
        caps[k]
        for k in (
            "can_manage_staff",
            "can_review_requests",
            "can_prepare_payroll",
            "can_approve_payroll",
            "can_assign_tasks",
        )
    ) or tx.backup("approve_advances")
    profile = tx.profile(tx.actor.user_id, required=False)
    result = {
        "contract_version": 1,
        "actor": {
            "user_id": actor_id,
            "device_id": str(tx.actor.registered_device_id),
            "is_owner": owner,
            "is_staff_manager": manager,
            "employee_id": actor_id if profile else None,
        },
        "capabilities": caps,
        "account_candidates": [],
        "setup_missing": [],
        "attendance_days": [],
        "leave_balances": [],
        "history": [],
        "last_result": None,
    }
    if configured_employee_owner_id() is None:
        result["setup_missing"].append(
            "The real owner account must be configured privately"
        )
    if not profile and not owner:
        result["setup_missing"].append("No employee profile is mapped to this account")
    visible_ids = set()
    visible_keys = set()
    for domain in TABLES:
        visible = []
        for record in tx.all(domain):
            own = record["employee_id"] == actor_id
            if domain in ("profiles", "schedules", "tasks"):
                show = own or any_review
            elif domain in ("requests", "leave_ledger", "attendance"):
                show = own or caps["can_review_requests"] or owner or manager
            elif domain == "shortages":
                show = own or owner or manager or caps["can_prepare_payroll"]
            elif domain in ("payroll", "payments", "payroll_history"):
                show = own or caps["can_prepare_payroll"] or caps["can_approve_payroll"]
            elif domain == "advances":
                show = (
                    own
                    or owner
                    or manager
                    or tx.backup("approve_advances")
                    or caps["can_prepare_payroll"]
                )
            elif domain == "calendar":
                show = True
            elif domain == "backups":
                show = owner or record["payload"]["user_id"] == actor_id
            elif domain in ("statutory_months", "statutory_remittances"):
                show = own or caps["can_view_statutory"]
            elif domain == "accounting_preparations":
                show = caps["can_prepare_accounting"]
            else:
                show = False
            if not show:
                continue
            record["allowed_actions"] = allowed(tx, domain, record, caps)
            history_visible = True
            if domain == "profiles":
                if not (
                    own
                    or owner
                    or manager
                    or caps["can_prepare_payroll"]
                    or caps["can_approve_payroll"]
                ):
                    record["payload"] = {
                        k: record["payload"][k] for k in ("full_name", "active")
                    }
                    history_visible = False
                record["payload"].update(
                    is_self=own,
                    can_review=not own and caps["can_review_requests"],
                    can_approve_payroll=not own and caps["can_approve_payroll"],
                    can_approve_advance=not own
                    and (owner or manager or tx.backup("approve_advances")),
                )
            visible.append(record)
            if history_visible:
                visible_ids.add(record["id"])
                visible_keys.add((domain, record["id"], record["employee_id"]))
        result[domain] = visible
    for profile in result["profiles"]:
        employee_id = profile["employee_id"]
        if not tx.all("schedules", employee_id):
            result["setup_missing"].append(
                f"{profile['payload']['full_name']}: effective schedule needed"
            )
        dates = {
            datetime.fromisoformat(r["payload"]["captured_at"])
            .astimezone(MANILA)
            .date()
            for r in result["attendance"]
            if r["employee_id"] == employee_id
        }
        dates.update(
            date.fromisoformat(r["payload"]["work_date"])
            for r in result["requests"]
            if r["employee_id"] == employee_id
            and r["payload"]["request_kind"] == "correction"
            and r["status"] == "approved"
        )
        result["attendance_days"].extend(
            tx.attendance(employee_id, d) for d in sorted(dates)
        )
        if employee_id == actor_id or caps["can_review_requests"] or owner:
            try:
                result["leave_balances"].append(tx.leave_balance(employee_id, tx.today))
            except EmployeeConflict as error:
                result["setup_missing"].append(
                    f"{profile['payload']['full_name']}: {error}"
                )
    if owner:
        result["account_candidates"] = plain(
            tx.cursor.execute("""select u.id as user_id,u.full_name,u.username,
            array_agg(r.code order by r.code) as roles from core.users u
            join core.user_roles ur on ur.user_id=u.id join core.roles r on r.id=ur.role_id
            where u.status='active' group by u.id having bool_or(r.code in ('collector','employee','management'))
            order by u.full_name,u.id""").fetchall()
        )
    if visible_ids:
        # Include only summaries/history of records already authorized above.
        history = tx.cursor.execute(
            """select record_id,employee_id,domain,version,action,actor_user_id,created_at,
            after_state->'payload' as payload,after_state->>'status' as status
            from core.employee_history where record_id=any(%s::uuid[]) order by id""",
            (list(visible_ids),),
        ).fetchall()
        result["history"] = [
            row
            for row in plain(history)
            if (row["domain"], row["record_id"], row["employee_id"]) in visible_keys
        ]
    if request_id:
        receipt = tx.cursor.execute(
            """select result from core.employee_action_receipts where request_id=%s
            and actor_user_id=%s and actor_device_id=%s""",
            (request_id, tx.actor.user_id, tx.actor.registered_device_id),
        ).fetchone()
        if receipt:
            result["last_result"] = receipt["result"]
    return result
