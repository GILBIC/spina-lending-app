"""Real transactional proofs on the guarded disposable local cluster only."""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import psycopg
import pytest
from gilbic_backend.account_repository import AccountContext
from gilbic_backend.employee_authorization import EmployeeAccessDenied
from gilbic_backend.employee_operations import EmployeeConflict
from gilbic_backend.employee_operations_models import ACTION_ADAPTER
from gilbic_backend.employee_operations_repository import (
    EmployeeTransaction,
    PostgresEmployeeOperationsRepository,
)
from gilbic_backend.employee_operations_workspace import build_workspace
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

from tools import run_stage5d17_disposable_postgres_validation as disposable

URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not URL, reason="Guarded disposable PostgreSQL is not configured"
)


@pytest.fixture
def database(monkeypatch):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = datetime(2026, 9, 20, 1, tzinfo=timezone.utc)
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)

    for module in (
        "employee_operations",
        "employee_operations_repository",
        "employee_operations_payroll",
    ):
        monkeypatch.setattr(f"gilbic_backend.{module}.datetime", FixedDatetime)
    if os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") != "1":
        raise RuntimeError("Employee proofs require explicitly disposable PostgreSQL")
    params = disposable._safe_local_connection_params(URL)
    if not re.fullmatch(r"spina_onboarding_[0-9a-f]{12}", params["dbname"]):
        raise RuntimeError(
            "Employee proofs require a generated onboarding disposable database"
        )
    disposable._clear_endpoint_environment()
    conn = psycopg.connect(make_conninfo(**params), row_factory=dict_row)
    try:
        users = {}
        for name, role in [
            ("owner", "management"),
            ("manager", "collector"),
            ("one", "collector"),
            ("two", "collector"),
        ]:
            uid, did = uuid4(), uuid4()
            conn.execute(
                "insert into core.users(id,username,full_name,status) values(%s,%s,%s,'active')",
                (uid, "synthetic-" + uid.hex, "Synthetic " + name),
            )
            conn.execute(
                "insert into core.devices(id,user_id,device_identifier_hash,platform,status) values(%s,%s,%s,'web','active')",
                (did, uid, uid.hex),
            )
            conn.execute(
                "insert into core.user_roles(user_id,role_id) select %s,id from core.roles where code=%s",
                (uid, role),
            )
            users[name] = AccountContext(
                uid,
                uuid4(),
                name,
                None,
                "Synthetic " + name,
                "active",
                (role,),
                (),
                True,
                did,
            )
        monkeypatch.setenv("SPINA_EMPLOYEE_OWNER_USER_ID", str(users["owner"].user_id))
        case = Case(conn, users)
        for name in ("manager", "one", "two"):
            employee = users[name].user_id
            case.call(
                "owner",
                "profile_save",
                id=employee,
                employee_id=employee,
                hire_date="2024-01-01",
                effective_from="2024-01-01",
                daily_rate="800.00",
                payout_method="cash",
                staff_manager=name == "manager",
                active=True,
                premium_pay_covered=True,
                holiday_pay_covered=True,
                tax_exempt=True,
                gp_partial_day_policy="prorated",
                classification_basis="Synthetic reviewed fixture classification",
            )
            case.call(
                "owner",
                "schedule_save",
                employee_id=employee,
                effective_from="2024-01-01",
                work_days=[1, 2, 3, 4, 5, 6],
                start_time="06:00",
                end_time="15:00",
                meal_minutes=60,
                reason="Synthetic agreed schedule",
            )
            case.call(
                "owner",
                "leave_balance_adjust",
                employee_id=employee,
                as_of="2026-09-01",
                minutes=2400,
                kind="opening",
                reason="Synthetic verified opening credits",
            )
        yield case
    finally:
        conn.rollback()
        conn.close()


class Case:
    def __init__(self, connection, users):
        self.connection, self.users = connection, users

    def call(self, actor, action, **fields):
        fields = dict(
            {
                "action": action,
                "request_id": str(uuid4()),
                "id": str(uuid4()),
                "expected_version": 0,
            },
            **fields,
        )
        command = ACTION_ADAPTER.validate_python(fields)
        with (
            self.connection.transaction(),
            self.connection.cursor(row_factory=dict_row) as cursor,
        ):
            result = PostgresEmployeeOperationsRepository.execute_in_transaction(
                cursor, actor=self.users[actor], command=command
            )
        return result

    def run(self, actor, payload):
        with (
            self.connection.transaction(),
            self.connection.cursor(row_factory=dict_row) as cursor,
        ):
            return PostgresEmployeeOperationsRepository.execute_in_transaction(
                cursor,
                actor=self.users[actor],
                command=ACTION_ADAPTER.validate_python(payload),
            )

    def record(self, domain, identity):
        return EmployeeTransaction(self.connection.cursor(), self.users["owner"]).get(
            domain, identity
        )

    def workspace(self, actor, request_id=None):
        return build_workspace(
            EmployeeTransaction(self.connection.cursor(), self.users[actor]), request_id
        )

    def week(self, name="one", start=date(2026, 9, 13), minutes=480):
        employee = self.users[name].user_id
        for n in range(7):
            day = start + timedelta(days=n)
            existing = self.connection.execute(
                "select id from core.employee_calendar where payload->>'work_date'=%s",
                (day.isoformat(),),
            ).fetchone()
            if not existing:
                self.call(
                    "owner",
                    "calendar_save",
                    work_date=day.isoformat(),
                    day_kind="ordinary",
                    source="Synthetic reviewed calendar",
                )
            if day.weekday() != 6:
                request = self.call(
                    name,
                    "correction_request",
                    employee_id=employee,
                    work_date=day.isoformat(),
                    clock_in=f"{day}T06:00:00+08:00",
                    clock_out=f"{day}T{15 if minutes == 480 else 11}:00:00+08:00",
                    unpaid_break_minutes=60,
                    reason="Synthetic verified historic attendance",
                )
                self.call(
                    "owner",
                    "request_decide",
                    id=request["id"],
                    employee_id=employee,
                    expected_version=1,
                    decision="approved",
                    reason="Synthetic verified correction",
                )
        for month in {start.replace(day=1), (start + timedelta(days=6)).replace(day=1)}:
            existing = self.connection.execute(
                "select id from core.employee_statutory_months where employee_id=%s and payload->>'month'=%s",
                (employee, month.isoformat()),
            ).fetchone()
            if not existing:
                self.call(
                    "owner",
                    "statutory_month_save",
                    employee_id=employee,
                    month=month.isoformat(),
                    sss_employee="0.00",
                    sss_employer="0.00",
                    philhealth_employee="0.00",
                    philhealth_employer="0.00",
                    pagibig_employee="0.00",
                    pagibig_employer="0.00",
                    employer_other="0.00",
                    prior_employee_deductions="0.00",
                    compensation_basis="Explicit synthetic zero fixture",
                    source="Synthetic reviewed monthly totals",
                )
        return employee

    def payroll(self, name="one", start=date(2026, 9, 13)):
        return self.call(
            "manager",
            "payroll_prepare",
            employee_id=self.users[name].user_id,
            week_start=start.isoformat(),
            reason="Synthetic weekly calculation",
        )


def test_private_workspace_and_owner_mapping_do_not_leak_coworker_wages(database):
    case = database
    own = case.workspace("one")
    manager = case.workspace("manager")
    owner = case.workspace("owner")
    assert len(own["profiles"]) == 1 and own["profiles"][0]["employee_id"] == str(
        case.users["one"].user_id
    )
    assert own["account_candidates"] == [] and not own["capabilities"]["can_configure"]
    assert (
        len(manager["profiles"]) == 3 and manager["capabilities"]["can_prepare_payroll"]
    )
    assert not manager["capabilities"]["can_record_payments"]
    assert (
        owner["actor"]["employee_id"] is None and len(owner["account_candidates"]) >= 4
    )
    roles = case.connection.execute(
        "select r.code from core.user_roles ur join core.roles r on r.id=ur.role_id where ur.user_id=%s",
        (case.users["manager"].user_id,),
    ).fetchall()
    assert {r["code"] for r in roles} == {"collector", "employee", "employee_manager"}


def test_attendance_retry_conflict_device_and_two_day_chain(database):
    case = database
    actor = case.users["one"]
    payload = {
        "action": "attendance_record",
        "request_id": str(uuid4()),
        "id": str(uuid4()),
        "expected_version": 0,
        "employee_id": str(actor.user_id),
        "event_type": "clock_in",
        "captured_at": "2026-09-18T06:00:00+08:00",
        "device_id": str(actor.registered_device_id),
        "previous_event_id": None,
        "sequence": 1,
        "offline": True,
    }
    result = case.run("one", payload)
    assert result["status"] == "accepted"
    assert case.run("one", payload)["replayed"]
    assert (
        case.workspace("one", UUID(payload["request_id"]))["last_result"]["id"]
        == payload["id"]
    )
    assert case.workspace("one")["attendance_days"][0]["status"] == "pending_review"
    with pytest.raises(EmployeeConflict):
        case.run("one", dict(payload, event_type="clock_out"))
    with pytest.raises(EmployeeAccessDenied):
        case.run("two", dict(payload, request_id=str(uuid4())))
    for suffix, kind, hour in [
        (1, "break_start", "12"),
        (2, "break_end", "13"),
        (3, "clock_out", "15"),
    ]:
        new = dict(
            payload,
            request_id=str(uuid4()),
            id=str(uuid4()),
            event_type=kind,
            captured_at=f"2026-09-18T{hour}:00:00+08:00",
            previous_event_id=payload["id"],
            sequence=suffix + 1,
        )
        case.run("one", new)
        payload = new
    assert case.workspace("one")["attendance_days"][0]["working_minutes"] == 480
    next_day = dict(
        payload,
        request_id=str(uuid4()),
        id=str(uuid4()),
        event_type="clock_in",
        captured_at="2026-09-19T06:00:00+08:00",
        previous_event_id=None,
        sequence=1,
    )
    assert case.run("one", next_day)["status"] == "accepted"
    case.connection.execute(
        "update core.devices set status='revoked' where id=%s",
        (actor.registered_device_id,),
    )
    with pytest.raises(EmployeeAccessDenied):
        case.run("one", next_day)


def test_manager_cannot_approve_own_request_and_future_leave_cancellation_restores_reservation(
    database,
):
    case = database
    employee = case.users["manager"].user_id
    request = case.call(
        "manager",
        "leave_request",
        employee_id=employee,
        work_date="2026-09-28",
        minutes=240,
        leave_kind="ordinary",
        reason="Synthetic planned leave",
    )
    with pytest.raises(EmployeeAccessDenied):
        case.call(
            "manager",
            "request_decide",
            id=request["id"],
            employee_id=employee,
            expected_version=1,
            decision="approved",
            reason="Cannot self approve",
        )
    case.call(
        "owner",
        "request_decide",
        id=request["id"],
        employee_id=employee,
        expected_version=1,
        decision="approved",
        reason="Owner reviewed",
    )
    balances = {
        x["employee_id"]: x for x in case.workspace("manager")["leave_balances"]
    }
    assert balances[str(employee)]["reserved_minutes"] == 240
    case.call(
        "owner",
        "request_decide",
        id=request["id"],
        employee_id=employee,
        expected_version=2,
        decision="cancelled",
        reason="Future plan cancelled",
    )
    balances = {
        x["employee_id"]: x for x in case.workspace("manager")["leave_balances"]
    }
    assert balances[str(employee)]["reserved_minutes"] == 0
    assert (
        len(
            [
                h
                for h in case.workspace("manager")["history"]
                if h["record_id"] == request["id"]
            ]
        )
        == 3
    )


def test_weekly_payroll_real_snapshot_stale_approval_partial_and_retry(database):
    case = database
    employee = case.week()
    payroll = case.payroll()
    pid = payroll["id"]
    row = case.record("payroll", pid)
    assert row["payload"]["net_pay"] == "5400.00"
    case.call(
        "manager",
        "payroll_approve",
        id=pid,
        employee_id=employee,
        expected_version=1,
        decision="approved",
        reason="Independent approved",
    )
    attempt = {
        "action": "payroll_payment",
        "request_id": str(uuid4()),
        "id": pid,
        "expected_version": 2,
        "employee_id": str(employee),
        "amount": "1000.00",
        "occurred_at": "2026-09-19T17:00:00+08:00",
        "payment_method": "cash",
        "reference": "",
        "settlement_evidence": "",
        "employee_acknowledgment": "Synthetic employee receipt",
        "result": "completed",
    }
    assert case.run("owner", attempt)["version"] == 3
    assert case.run("owner", attempt)["replayed"]
    assert case.record("payroll", pid)["status"] == "partially_paid"
    with pytest.raises(EmployeeConflict):
        case.run("owner", dict(attempt, request_id=str(uuid4())))
    with pytest.raises(EmployeeAccessDenied):
        case.run("manager", dict(attempt, request_id=str(uuid4()), expected_version=3))
    case.run(
        "owner",
        dict(attempt, request_id=str(uuid4()), expected_version=3, amount="4400.00"),
    )
    row = case.record("payroll", pid)
    assert row["status"] == "paid" and row["payload"]["balance_due"] == "0.00"
    assert (
        case.connection.execute(
            "select count(*) as n from core.employee_payments where employee_id=%s",
            (employee,),
        ).fetchone()["n"]
        == 2
    )
    with pytest.raises(EmployeeConflict):
        case.call(
            "owner",
            "payroll_prepare",
            id=pid,
            employee_id=employee,
            expected_version=4,
            week_start="2026-09-13",
            reason="Forbidden overwrite",
        )


def test_missing_inputs_block_instead_of_zero_pay_and_source_change_stales_unpaid(
    database,
):
    case = database
    employee = case.users["one"].user_id
    with pytest.raises(EmployeeConflict, match="calendar"):
        case.payroll()
    case.week()
    payroll = case.payroll()
    case.call(
        "manager",
        "payroll_approve",
        id=payroll["id"],
        employee_id=employee,
        expected_version=1,
        decision="approved",
        reason="Ready",
    )
    case.call(
        "one",
        "overtime_request",
        employee_id=employee,
        work_date="2026-09-18",
        minutes=60,
        reason="Previously missed work needs review",
    )
    assert case.record("payroll", payroll["id"])["status"] == "stale"


def test_shortage_report_does_not_forfeit_until_owner_confirms_and_paid_reversal_links_adjustment(
    database,
):
    case = database
    employee = case.week()
    shortage = case.call(
        "manager",
        "shortage_report",
        employee_id=employee,
        work_date="2026-09-18",
        expected_cash="1000.00",
        accounted_cash="900.00",
        evidence="Synthetic count record",
    )
    payroll = case.payroll()
    assert case.record("payroll", payroll["id"])["payload"]["net_pay"] == "5400.00"
    with pytest.raises(EmployeeAccessDenied):
        case.call(
            "manager",
            "shortage_decide",
            id=shortage["id"],
            employee_id=employee,
            expected_version=1,
            decision="confirmed",
            reason="No authority",
            response_opportunity="Synthetic notice",
        )
    case.call(
        "one",
        "shortage_respond",
        id=shortage["id"],
        employee_id=employee,
        expected_version=1,
        explanation="Synthetic employee explanation",
    )
    case.call(
        "owner",
        "shortage_decide",
        id=shortage["id"],
        employee_id=employee,
        expected_version=2,
        decision="confirmed",
        reason="Owner finding",
        response_opportunity="Explanation considered",
    )
    case.call(
        "manager",
        "payroll_prepare",
        id=payroll["id"],
        employee_id=employee,
        expected_version=1,
        week_start="2026-09-13",
        reason="Refresh with confirmed benefit condition",
    )
    values = {
        x["code"]: x["amount"]
        for x in case.record("payroll", payroll["id"])["payload"]["components"]
    }
    assert values["performance_benefit"] == "0.00" and "lawful_recovery" not in values


def test_principal_approval_is_not_disbursement_and_reserved_payroll_prevents_double_repayment(
    database,
):
    case = database
    employee = case.week()
    advance = case.call(
        "one",
        "advance_request",
        employee_id=employee,
        amount="100.00",
        reason="Synthetic advance",
        installments=[{"due_date": "2026-09-26", "amount": "100.00"}],
        employee_acknowledgment="Employee agrees",
        payroll_authorization="Reviewed lawful agreed authorization",
    )
    case.call(
        "manager",
        "advance_decide",
        id=advance["id"],
        employee_id=employee,
        expected_version=1,
        decision="approved",
        reason="Approved principal only",
    )
    assert (
        case.record("advances", advance["id"])["payload"]["outstanding_amount"]
        == "0.00"
    )
    case.call(
        "owner",
        "advance_disburse",
        id=advance["id"],
        employee_id=employee,
        expected_version=2,
        occurred_at="2026-09-19T16:00:00+08:00",
        payment_method="cash",
        reference="Synthetic receipt",
        settlement_evidence="Owner counted transfer",
        employee_acknowledgment="Received100",
    )
    with pytest.raises(EmployeeConflict):
        case.call(
            "owner",
            "advance_repay",
            id=advance["id"],
            employee_id=employee,
            expected_version=3,
            amount="101.00",
            occurred_at="2026-09-20T08:00:00+08:00",
            reference="Over principal",
            settlement_evidence="Rejected",
        )
    # Reserve the principal through a synthetic reviewed approved snapshot. This
    # isolates the simultaneous financial-boundary test from future attendance.
    payroll = case.payroll()
    row = case.record("payroll", payroll["id"])
    p = row["payload"]
    p["advance_allocations"] = [
        {"advance_id": advance["id"], "version": 3, "amount": "100.00"}
    ]
    from psycopg.types.json import Jsonb

    case.connection.execute(
        "update core.employee_payroll set payload=%s,status='partially_paid' where id=%s",
        (Jsonb(p), payroll["id"]),
    )
    with pytest.raises(EmployeeConflict, match="reserved"):
        case.call(
            "owner",
            "advance_repay",
            id=advance["id"],
            employee_id=employee,
            expected_version=3,
            amount="100.00",
            occurred_at="2026-09-20T08:00:00+08:00",
            reference="Would duplicate payroll",
            settlement_evidence="Rejected",
        )


def test_immutable_evidence_and_private_schema_access(database):
    case = database
    employee = case.users["one"].user_id
    row = case.connection.execute(
        "select id from core.employee_leave_ledger where employee_id=%s", (employee,)
    ).fetchone()
    with pytest.raises(psycopg.errors.RaiseException), case.connection.transaction():
        case.connection.execute(
            "delete from core.employee_leave_ledger where id=%s", (row["id"],)
        )
    public = case.connection.execute(
        "select count(*) as n from pg_class c cross join lateral aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a where c.oid='core.employee_payroll'::regclass and a.grantee=0"
    ).fetchone()
    assert public["n"] == 0
    for role in ("anon", "authenticated"):
        if case.connection.execute(
            "select 1 from pg_roles where rolname=%s", (role,)
        ).fetchone():
            assert not case.connection.execute(
                "select has_table_privilege(%s,'core.employee_payroll','SELECT') as allowed",
                (role,),
            ).fetchone()["allowed"]


def pay_all(case, payroll, employee, version=1):
    approved = case.call(
        "owner",
        "payroll_approve",
        id=payroll["id"],
        employee_id=employee,
        expected_version=version,
        decision="approved",
        reason="Synthetic reviewed payroll",
    )
    row = case.record("payroll", payroll["id"])
    return case.call(
        "owner",
        "payroll_payment",
        id=payroll["id"],
        employee_id=employee,
        expected_version=approved["version"],
        amount=row["payload"]["net_pay"],
        occurred_at="2026-09-19T18:00:00+08:00",
        payment_method="cash",
        employee_acknowledgment="Synthetic receipt acknowledgment",
        result="completed",
    )


def test_recovery_cannot_repeat_and_survives_recalculation_until_case_reversed(
    database,
):
    case = database
    employee = case.week(start=date(2026, 9, 6))
    original = case.payroll(start=date(2026, 9, 6))
    pay_all(case, original, employee)
    case.week()
    shortage = case.call(
        "manager",
        "shortage_report",
        employee_id=employee,
        work_date="2026-09-18",
        expected_cash="1000.00",
        accounted_cash="900.00",
        evidence="Synthetic actual accountable money",
    )
    case.call(
        "owner",
        "shortage_decide",
        id=shortage["id"],
        employee_id=employee,
        expected_version=1,
        decision="confirmed",
        reason="Individual actual loss reviewed",
        response_opportunity="Employee response considered",
    )
    current = case.payroll()
    payload = {
        "employee_id": employee,
        "original_payroll_id": original["id"],
        "component": "lawful_recovery",
        "amount": "-100.00",
        "reason": "Separate reviewed loss recovery",
        "lawful_basis": "Synthetic professional-reviewed legal basis",
        "responsibility_evidence": "Synthetic actual responsibility",
        "employee_response": "Synthetic response considered",
        "maximum_authorized_recovery": "100.00",
        "shortage_id": shortage["id"],
    }
    case.call("owner", "payroll_adjustment", **payload)
    assert case.record("payroll", current["id"])["payload"]["net_pay"] == "4700.00"
    with pytest.raises(EmployeeConflict, match="unrecovered"):
        case.call("owner", "payroll_adjustment", **payload)
    row = case.record("payroll", current["id"])
    case.call(
        "owner",
        "payroll_prepare",
        id=current["id"],
        employee_id=employee,
        expected_version=row["version"],
        week_start="2026-09-13",
        reason="Recalculate preserves lawful allocation",
    )
    assert case.record("payroll", current["id"])["payload"]["net_pay"] == "4700.00"
    case.call(
        "owner",
        "shortage_decide",
        id=shortage["id"],
        employee_id=employee,
        expected_version=2,
        decision="reversed",
        reason="Evidence proves no actual shortage",
        response_opportunity="Employee explanation accepted",
    )
    row = case.record("payroll", current["id"])
    case.call(
        "owner",
        "payroll_prepare",
        id=current["id"],
        employee_id=employee,
        expected_version=row["version"],
        week_start="2026-09-13",
        reason="Restore benefits and remove invalid recovery",
    )
    assert case.record("payroll", current["id"])["payload"]["net_pay"] == "5400.00"


def test_leave_conversion_settles_once_and_historic_13th_month_needs_real_inputs(
    database,
):
    case = database
    employee = case.users["one"].user_id
    with pytest.raises(EmployeeConflict, match="historic"):
        case.call(
            "owner",
            "payroll_prepare",
            employee_id=employee,
            week_start="2026-09-19",
            payroll_kind="thirteenth_month",
            reason="No fabricated past earnings",
        )
    case.call(
        "owner",
        "payroll_history_import",
        employee_id=employee,
        year=2026,
        through_date="2026-09-19",
        basic_earned="96000.00",
        taxable_earned="96000.00",
        tax_withheld="0.00",
        thirteenth_paid="0.00",
        other_benefits_paid="0.00",
        source="Synthetic reviewed prior payslips",
    )
    thirteenth = case.call(
        "owner",
        "payroll_prepare",
        employee_id=employee,
        week_start="2026-09-19",
        payroll_kind="thirteenth_month",
        reason="Verified eligible basic salary /12",
    )
    assert case.record("payroll", thirteenth["id"])["payload"]["net_pay"] == "8000.00"
    before = case.workspace("one")["leave_balances"][0]["available_minutes"]
    request = case.call(
        "one",
        "leave_conversion_request",
        employee_id=employee,
        as_of="2026-09-19",
        minutes=480,
        reason="Convert eligible unused credits",
    )
    case.call(
        "manager",
        "request_decide",
        id=request["id"],
        employee_id=employee,
        expected_version=1,
        decision="approved",
        reason="Eligible credits verified",
    )
    payroll = case.call(
        "manager",
        "payroll_prepare",
        employee_id=employee,
        week_start="2026-09-19",
        payroll_kind="leave_conversion",
        leave_conversion_request_id=request["id"],
        withholding_override="0.00",
        withholding_basis="Synthetic reviewed tax treatment",
        reason="Unused leave conversion",
    )
    assert case.record("payroll", payroll["id"])["payload"]["net_pay"] == "800.00"
    pay_all(case, payroll, employee)
    assert case.record("requests", request["id"])["status"] == "settled"
    assert (
        case.workspace("one")["leave_balances"][0]["available_minutes"] == before - 480
    )
    with pytest.raises(EmployeeConflict):
        case.call(
            "manager",
            "payroll_prepare",
            employee_id=employee,
            week_start="2026-09-20",
            payroll_kind="leave_conversion",
            leave_conversion_request_id=request["id"],
            withholding_override="0.00",
            withholding_basis="No duplicate",
            reason="Attempt duplicate conversion",
        )


def test_task_only_backup_cannot_read_other_salary_history(database):
    case = database
    employee = case.users["one"].user_id
    case.call(
        "owner",
        "backup_save",
        user_id=employee,
        starts_on="2026-09-01",
        ends_on="2026-10-01",
        duties=["assign_tasks"],
        reason="Named limited temporary assignment authority",
    )
    workspace = case.workspace("one")
    assert (
        workspace["capabilities"]["can_assign_tasks"]
        and not workspace["capabilities"]["can_prepare_payroll"]
    )
    other_profiles = [
        p for p in workspace["profiles"] if p["employee_id"] != str(employee)
    ]
    assert other_profiles and all(
        "daily_rate" not in p["payload"] for p in other_profiles
    )
    assert not [
        h
        for h in workspace["history"]
        if h["domain"] == "profiles" and h["record_id"] != str(employee)
    ]


def test_cross_month_statutory_allocations_include_prior_deductions_and_do_not_repeat_full_month(
    database,
):
    case = database
    employee = case.week(start=date(2026, 8, 30))
    for month, prior in [("2026-08-01", "250.00"), ("2026-09-01", "0.00")]:
        row = case.connection.execute(
            "select id,version,payload from core.employee_statutory_months where employee_id=%s and payload->>'month'=%s",
            (employee, month),
        ).fetchone()
        p = row["payload"]
        p.update(sss_employee="300.00", prior_employee_deductions=prior)
        case.call(
            "owner",
            "statutory_month_save",
            id=row["id"],
            employee_id=employee,
            expected_version=row["version"],
            **p,
        )
    payroll = case.payroll(start=date(2026, 8, 30))
    row = case.record("payroll", payroll["id"])
    allocations = {
        a["month"]: a["amount"] for a in row["payload"]["statutory_allocations"]
    }
    assert allocations == {"2026-08-01": "50.00", "2026-09-01": "50.00"}
    pay_all(case, payroll, employee)
    case.week(start=date(2026, 9, 6))
    next_pay = case.payroll(start=date(2026, 9, 6))
    assert (
        case.record("payroll", next_pay["id"])["payload"]["statutory_allocations"][0][
            "amount"
        ]
        == "70.00"
    )


def test_create_commands_cannot_reset_approved_requests_confirmed_shortages_or_disbursed_principal(
    database,
):
    case = database
    employee = case.users["one"].user_id
    request_fields = {
        "employee_id": employee,
        "work_date": "2026-09-28",
        "minutes": 60,
        "leave_kind": "ordinary",
        "reason": "Synthetic approved request",
    }
    request = case.call("one", "leave_request", **request_fields)
    case.call(
        "owner",
        "request_decide",
        id=request["id"],
        employee_id=employee,
        expected_version=1,
        decision="approved",
        reason="Approved",
    )
    with pytest.raises(EmployeeConflict, match="creates a new"):
        case.call(
            "one",
            "leave_request",
            id=request["id"],
            expected_version=2,
            **request_fields,
        )
    assert case.record("requests", request["id"])["status"] == "approved"
    shortage_fields = {
        "employee_id": employee,
        "work_date": "2026-09-18",
        "expected_cash": "1000.00",
        "accounted_cash": "900.00",
        "evidence": "Synthetic cash evidence",
    }
    shortage = case.call("one", "shortage_report", **shortage_fields)
    case.call(
        "owner",
        "shortage_decide",
        id=shortage["id"],
        employee_id=employee,
        expected_version=1,
        decision="confirmed",
        reason="Reviewed",
        response_opportunity="Employee heard",
    )
    with pytest.raises(EmployeeConflict, match="creates a new"):
        case.call(
            "one",
            "shortage_report",
            id=shortage["id"],
            expected_version=2,
            **shortage_fields,
        )
    assert case.record("shortages", shortage["id"])["status"] == "confirmed"
    advance_fields = {
        "employee_id": employee,
        "amount": "300.00",
        "reason": "Synthetic advance",
        "installments": [{"due_date": "2026-09-26", "amount": "300.00"}],
        "employee_acknowledgment": "Employee agrees",
        "payroll_authorization": "Reviewed authorization",
    }
    advance = case.call("one", "advance_request", **advance_fields)
    case.call(
        "owner",
        "advance_decide",
        id=advance["id"],
        employee_id=employee,
        expected_version=1,
        decision="approved",
        reason="Reviewed",
    )
    case.call(
        "owner",
        "advance_disburse",
        id=advance["id"],
        employee_id=employee,
        expected_version=2,
        occurred_at="2026-09-19T16:00:00+08:00",
        payment_method="cash",
        reference="Synthetic disbursement",
        settlement_evidence="Cash received",
        employee_acknowledgment="Received300",
    )
    with pytest.raises(EmployeeConflict, match="creates a new"):
        case.call(
            "one",
            "advance_request",
            id=advance["id"],
            expected_version=3,
            **advance_fields,
        )
    assert (
        case.record("advances", advance["id"])["payload"]["outstanding_amount"]
        == "300.00"
    )


def test_cross_domain_uuid_collision_does_not_expose_profile_history(database):
    case = database
    employee = case.users["one"].user_id
    other = case.users["two"].user_id
    case.call(
        "one",
        "leave_request",
        id=other,
        employee_id=employee,
        work_date="2026-09-28",
        minutes=60,
        leave_kind="ordinary",
        reason="Own request with colliding domain UUID",
    )
    workspace = case.workspace("one")
    collision = [h for h in workspace["history"] if h["record_id"] == str(other)]
    assert collision and all(
        h["domain"] == "requests" and h["employee_id"] == str(employee)
        for h in collision
    )
    assert all("daily_rate" not in h["payload"] for h in collision)


def test_external_payment_reference_cannot_be_reapplied_with_a_fresh_request_id(
    database,
):
    case = database
    employee = case.week()
    payroll = case.payroll()
    case.call(
        "owner",
        "payroll_approve",
        id=payroll["id"],
        employee_id=employee,
        expected_version=1,
        decision="approved",
        reason="Approved",
    )
    payment = {
        "id": payroll["id"],
        "employee_id": employee,
        "amount": "100.00",
        "occurred_at": "2026-09-19T18:00:00+08:00",
        "payment_method": "gcash",
        "reference": "SYN-TRANSFER-ONLY-ONCE",
        "settlement_evidence": "Owner verified receiving evidence",
        "result": "completed",
    }
    case.call("owner", "payroll_payment", expected_version=2, **payment)
    with pytest.raises(EmployeeConflict, match="reference"):
        case.call("owner", "payroll_payment", expected_version=3, **payment)
    assert case.record("payroll", payroll["id"])["payload"]["paid_amount"] == "100.00"


def test_annual_drafts_respect_reserved_payroll_and_paid_basic_corrections(database):
    case = database
    employee = case.week()
    weekly = case.payroll()
    pay_all(case, weekly, employee)
    case.call(
        "owner",
        "payroll_history_import",
        employee_id=employee,
        year=2026,
        through_date="2026-09-12",
        basic_earned="10000.00",
        taxable_earned="10000.00",
        tax_withheld="0.00",
        thirteenth_paid="0.00",
        other_benefits_paid="0.00",
        source="Synthetic verified opening history excluding later corrections",
    )
    adjustment = case.call(
        "owner",
        "payroll_adjustment",
        employee_id=employee,
        original_payroll_id=weekly["id"],
        component="basic_pay",
        amount="800.00",
        reason="Underpaid basic salary correction",
    )
    pay_all(case, adjustment, employee)
    annual = case.call(
        "owner",
        "payroll_prepare",
        employee_id=employee,
        week_start="2026-09-19",
        payroll_kind="thirteenth_month",
        reason="Eligible basic includes correction",
    )
    assert case.record("payroll", annual["id"])["payload"]["net_pay"] == "1300.00"
    separation = case.call(
        "owner",
        "payroll_prepare",
        employee_id=employee,
        week_start="2026-09-19",
        payroll_kind="separation",
        reason="Concurrent annual facts draft",
    )
    case.call(
        "owner",
        "payroll_approve",
        id=annual["id"],
        employee_id=employee,
        expected_version=1,
        decision="approved",
        reason="Reserves 13thmonth amount",
    )
    with pytest.raises(EmployeeConflict, match="changed"):
        case.call(
            "owner",
            "payroll_approve",
            id=separation["id"],
            employee_id=employee,
            expected_version=1,
            decision="approved",
            reason="Must not double reserve same benefit",
        )


def test_repeated_advance_terms_are_reviewed_without_losing_state(database):
    case = database
    employee = case.users["one"].user_id
    advance = case.call(
        "one",
        "advance_request",
        employee_id=employee,
        amount="100.00",
        reason="Synthetic principal",
        installments=[{"due_date": "2026-09-26", "amount": "100.00"}],
        employee_acknowledgment="Agreed",
        payroll_authorization="Reviewed authorization",
    )
    terms = {
        "employee_id": employee,
        "id": advance["id"],
        "installments": [{"due_date": "2026-10-03", "amount": "100.00"}],
        "employee_acknowledgment": "Agreed changed date",
        "payroll_authorization": "Reviewed same principal",
        "reason": "Requested date change",
    }
    case.call("one", "advance_terms", expected_version=1, **terms)
    with pytest.raises(EmployeeConflict, match="proposal"):
        case.call("one", "advance_terms", expected_version=2, **terms)
    case.call(
        "manager",
        "advance_decide",
        id=advance["id"],
        employee_id=employee,
        expected_version=2,
        decision="approved",
        reason="Terms reviewed",
    )
    row = case.record("advances", advance["id"])
    assert (
        row["status"] == "requested"
        and row["payload"]["installments"][0]["due_date"] == "2026-10-03"
    )


def test_tasks_shift_changes_and_full_five_day_conversion_request(database):
    case = database
    employee = case.users["one"].user_id
    task = case.call(
        "manager",
        "task_save",
        employee_id=employee,
        description="Synthetic office task",
        due_date="2026-09-21",
    )
    case.call(
        "one",
        "task_progress",
        id=task["id"],
        employee_id=employee,
        expected_version=1,
        status="done",
        reason="Completed actual work",
    )
    with pytest.raises(EmployeeAccessDenied):
        case.call(
            "one",
            "task_progress",
            id=task["id"],
            employee_id=employee,
            expected_version=2,
            status="todo",
            reason="Cannot silently reopen",
        )
    case.call(
        "manager",
        "task_progress",
        id=task["id"],
        employee_id=employee,
        expected_version=2,
        status="todo",
        reason="Assigner reopens with reason",
    )
    shift = case.call(
        "one",
        "shift_request",
        employee_id=employee,
        effective_from="2026-09-21",
        work_days=[1, 2, 3, 4, 5, 6],
        start_time="07:00",
        end_time="16:00",
        meal_minutes=60,
        reason="Employee requests later start",
    )
    case.call(
        "manager",
        "request_decide",
        id=shift["id"],
        employee_id=employee,
        expected_version=1,
        decision="approved",
        reason="Approved prospective shift",
    )
    tx = EmployeeTransaction(case.connection.cursor(), case.users["owner"])
    assert tx.schedule(employee, date(2026, 9, 20))["start_time"] == "06:00"
    assert tx.schedule(employee, date(2026, 9, 21))["start_time"] == "07:00"
    request = case.call(
        "one",
        "leave_conversion_request",
        employee_id=employee,
        as_of="2026-09-20",
        minutes=2400,
        reason="All five eligible unused days",
    )
    assert case.record("requests", request["id"])["payload"]["minutes"] == 2400


def test_special_leave_requires_its_own_explicit_payment_review(database):
    case = database
    employee = case.users["one"].user_id
    request = case.call(
        "one",
        "leave_request",
        employee_id=employee,
        work_date="2026-09-28",
        minutes=480,
        leave_kind="maternity",
        reason="Synthetic special leave",
        eligibility_evidence="Synthetic reviewed entitlement document",
    )
    with pytest.raises(EmployeeConflict, match="employer-paid"):
        case.call(
            "owner",
            "request_decide",
            id=request["id"],
            employee_id=employee,
            expected_version=1,
            decision="approved",
            reason="Missing payable employer component",
        )
    case.call(
        "owner",
        "request_decide",
        id=request["id"],
        employee_id=employee,
        expected_version=1,
        decision="approved",
        paid_minutes=0,
        reason="Agency benefit reviewed separately; zero ordinary payroll component in this synthetic case",
    )
    assert case.record("requests", request["id"])["payload"]["paid_minutes"] == 0


def test_restricted_backup_cannot_use_payroll_or_request_duties_for_accounting_or_other_shortages(
    database,
):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from gilbic_backend.employee_operations_api import (
        create_employee_operations_router,
        employee_operations_context,
        employee_operations_repository_dependency,
    )

    case = database
    employee = case.users["one"].user_id
    other = case.users["two"].user_id
    case.call(
        "owner",
        "backup_save",
        user_id=employee,
        starts_on="2026-09-01",
        ends_on="2026-10-01",
        duties=["prepare_payroll", "review_requests"],
        reason="Two limited backup duties",
    )
    accounting = {
        "preparation_kind": "reconciliation",
        "description": "Synthetic supporting reconciliation",
        "as_of": "2026-09-19",
        "evidence": "Synthetic statement",
        "statement_balance": "100.00",
        "ledger_balance": "100.00",
    }
    shortage = {
        "employee_id": other,
        "work_date": "2026-09-19",
        "expected_cash": "100.00",
        "accounted_cash": "90.00",
        "evidence": "Synthetic count evidence",
    }
    with pytest.raises(EmployeeAccessDenied):
        case.call("one", "accounting_prepare", **accounting)
    with pytest.raises(EmployeeAccessDenied):
        case.call("one", "shortage_report", **shortage)

    class TransactionRepository:
        def execute(self, *, actor, command):
            with (
                case.connection.transaction(),
                case.connection.cursor(row_factory=dict_row) as cursor,
            ):
                return PostgresEmployeeOperationsRepository.execute_in_transaction(
                    cursor, actor=actor, command=command
                )

    app = FastAPI()
    app.include_router(create_employee_operations_router())
    app.dependency_overrides[employee_operations_context] = lambda: case.users["one"]
    app.dependency_overrides[employee_operations_repository_dependency] = (
        TransactionRepository
    )
    with TestClient(app) as client:
        for action, fields in (
            ("accounting_prepare", accounting),
            ("shortage_report", shortage),
        ):
            payload = {
                "action": action,
                "id": str(uuid4()),
                "request_id": str(uuid4()),
                "expected_version": 0,
                **fields,
            }
            if "employee_id" in payload:
                payload["employee_id"] = str(payload["employee_id"])
            response = client.post("/api/v1/employee-operations/actions", json=payload)
            assert response.status_code == 403
            assert response.json()["detail"]["code"] == "employee_access_denied"
    assert case.workspace("one")["capabilities"]["can_prepare_accounting"] is False
    assert (
        case.call("manager", "accounting_prepare", **accounting)["status"] == "accepted"
    )
    assert (
        case.call("one", "shortage_report", **dict(shortage, employee_id=employee))[
            "status"
        ]
        == "accepted"
    )
