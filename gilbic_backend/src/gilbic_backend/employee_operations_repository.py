"""Transactional private employee records and explicit domain transitions.

The application serializes this small three-person ledger with one advisory lock;
row versions and immutable receipts still detect stale clients and retries.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4
from typing import Literal, NotRequired, TypeVar, TypedDict, cast, overload

from psycopg import Cursor, sql
from psycopg.rows import DictRow, dict_row
from psycopg.types.json import Jsonb

from .account_repository import AccountContext
from .database import open_connection
from .employee_authorization import (
    EmployeeAccessDenied,
    is_employee_owner,
    require_employee_actor,
    require_employee_action,
    configure_employee_responsibility,
)
from .employee_operations import (
    AttendanceEvent,
    EmployeeConflict,
    MANILA,
    attendance_day,
    leave_accrual_minutes,
    money_text,
)
from . import employee_operations_models as commands
from .employee_operations_models import EmployeeAction

TABLES = {
    "profiles": "employee_profiles",
    "schedules": "employee_schedules",
    "backups": "employee_backups",
    "calendar": "employee_calendar",
    "statutory_months": "employee_statutory_months",
    "statutory_remittances": "employee_statutory_remittances",
    "attendance": "employee_attendance_events",
    "requests": "employee_requests",
    "leave_ledger": "employee_leave_ledger",
    "tasks": "employee_tasks",
    "advances": "employee_advances",
    "shortages": "employee_shortages",
    "payroll": "employee_payroll",
    "payments": "employee_payments",
    "payroll_history": "employee_payroll_history",
    "accounting_preparations": "employee_accounting_preparations",
}
ENVELOPE = {"action", "request_id", "id", "expected_version", "employee_id"}
REQUEST_ACTIONS = {
    "correction_request": "correction",
    "leave_request": "leave",
    "shift_request": "shift",
    "overtime_request": "overtime",
    "leave_conversion_request": "leave_conversion",
}
SOURCE_DOMAINS = (
    "profiles",
    "schedules",
    "calendar",
    "statutory_months",
    "attendance",
    "requests",
    "leave_ledger",
    "advances",
    "shortages",
    "payroll_history",
)


# The envelope is shared across the private tables. Payloads retain their domain's
# validated JSON fields; dict_row is the single dynamic database boundary.
class EmployeeRecord(TypedDict):
    id: str
    employee_id: str | None
    version: int
    status: str
    payload: DictRow
    created_by: str
    created_at: str
    updated_at: str
    allowed_actions: NotRequired[list[str]]


CommandType = TypeVar("CommandType", bound=commands.Command)
RecordIdentity = UUID | str


@overload
def plain(value: DictRow) -> DictRow: ...


@overload
def plain(value: list[DictRow]) -> list[DictRow]: ...


@overload
def plain(value: object) -> object: ...


def plain(value: object) -> object:
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, (UUID, date, datetime)):
        return value.isoformat() if isinstance(value, (date, datetime)) else str(value)
    if isinstance(value, Decimal):
        return money_text(value)
    return value


def _day(value: str) -> date:
    return date.fromisoformat(value)


class EmployeeTransaction:
    def __init__(
        self,
        cursor: Cursor[DictRow],
        actor: AccountContext,
        command: EmployeeAction | None = None,
    ):
        self.cursor, self.actor, self._command = cursor, actor, command
        self.today = datetime.now(MANILA).date()

    @property
    def command(self) -> EmployeeAction:
        if self._command is None:
            raise EmployeeConflict("A command is required for an employee action")
        return self._command

    def command_as(self, model: type[CommandType]) -> CommandType:
        command = self.command
        if not isinstance(command, model):
            raise EmployeeConflict("The employee action does not match its handler")
        return command

    def all(
        self, domain: str, employee_id: RecordIdentity | None = None
    ) -> list[EmployeeRecord]:
        query = sql.SQL("select * from {}").format(
            sql.Identifier("core", TABLES[domain])
        )
        params: tuple[RecordIdentity, ...] = ()
        if employee_id is not None:
            query += sql.SQL(" where employee_id=%s")
            params = (employee_id,)
        return [
            cast(EmployeeRecord, plain(row))
            for row in self.cursor.execute(
                query + sql.SQL(" order by created_at,id"), params
            ).fetchall()
        ]

    @overload
    def get(
        self, domain: str, identity: RecordIdentity, *, required: Literal[True] = True
    ) -> EmployeeRecord: ...

    @overload
    def get(
        self, domain: str, identity: RecordIdentity, *, required: Literal[False]
    ) -> EmployeeRecord | None: ...

    @overload
    def get(
        self, domain: str, identity: RecordIdentity, *, required: bool
    ) -> EmployeeRecord | None: ...

    def get(
        self, domain: str, identity: RecordIdentity, *, required: bool = True
    ) -> EmployeeRecord | None:
        row = self.cursor.execute(
            sql.SQL("select * from {} where id=%s for update").format(
                sql.Identifier("core", TABLES[domain])
            ),
            (identity,),
        ).fetchone()
        if row is None and required:
            raise EmployeeConflict("The requested employee record does not exist")
        return cast(EmployeeRecord, plain(row)) if row else None

    def owner(self):
        if not is_employee_owner(self.actor):
            raise EmployeeAccessDenied(
                "Only the explicitly configured owner may perform this action"
            )

    @overload
    def profile(
        self, employee_id: RecordIdentity, *, required: Literal[True] = True
    ) -> EmployeeRecord: ...

    @overload
    def profile(
        self, employee_id: RecordIdentity, *, required: Literal[False]
    ) -> EmployeeRecord | None: ...

    def profile(
        self, employee_id: RecordIdentity, *, required: bool = True
    ) -> EmployeeRecord | None:
        row = self.get("profiles", employee_id, required=required)
        if required and row is not None and not row["payload"]["active"]:
            raise EmployeeConflict("The employee profile is inactive")
        return row

    def manager(self):
        profile = self.profile(self.actor.user_id, required=False)
        if (
            not profile
            or not profile["payload"]["active"]
            or not profile["payload"]["staff_manager"]
        ):
            return False
        try:
            require_employee_action(
                self.cursor, actor=self.actor, permission="employee_operations.manage"
            )
        except EmployeeAccessDenied:
            return False
        return True

    def backup(self, duty):
        return any(
            row["payload"]["user_id"] == str(self.actor.user_id)
            and row["payload"]["starts_on"]
            <= self.today.isoformat()
            <= row["payload"]["ends_on"]
            and duty in row["payload"]["duties"]
            for row in self.all("backups")
        )

    def staff(self, duty="review_requests", subject=None):
        if subject is not None and str(subject) == str(self.actor.user_id):
            raise EmployeeAccessDenied("You cannot approve or review your own record")
        if is_employee_owner(self.actor):
            return
        if not (self.manager() or self.backup(duty)):
            raise EmployeeAccessDenied(
                "This action requires an active, explicitly assigned staff responsibility"
            )

    def own(self, employee_id):
        self.profile(employee_id)
        if str(employee_id) != str(self.actor.user_id):
            raise EmployeeAccessDenied(
                "This action is only available for your own employee record"
            )

    def version(self, row):
        if (
            row["employee_id"] is not None
            and isinstance(self.command, commands.EmployeeCommand)
            and row["employee_id"] != str(self.command.employee_id)
        ):
            raise EmployeeAccessDenied("The record does not belong to that employee")
        if row["version"] != self.command.expected_version:
            raise EmployeeConflict(
                "The record changed; refresh and review the current version"
            )

    def save(
        self,
        domain: str,
        identity: RecordIdentity,
        employee_id: RecordIdentity | None,
        payload: DictRow,
        status: str,
        *,
        expected: int | None = None,
    ) -> EmployeeRecord:
        before = self.get(domain, identity, required=False)
        current = 0 if before is None else before["version"]
        expected = self.command.expected_version if expected is None else expected
        if current != expected:
            raise EmployeeConflict(
                "The record changed; refresh and review the current version"
            )
        if before and before["employee_id"] != (
            str(employee_id) if employee_id else None
        ):
            raise EmployeeAccessDenied(
                "An existing record cannot change employee identity"
            )
        if before:
            self.cursor.execute(
                sql.SQL("""update {} set version=version+1,status=%s,payload=%s,
                                 updated_at=clock_timestamp() where id=%s""").format(
                    sql.Identifier("core", TABLES[domain])
                ),
                (status, Jsonb(plain(payload)), identity),
            )
        else:
            self.cursor.execute(
                sql.SQL("""insert into {}(id,employee_id,version,status,payload,created_by)
                                 values(%s,%s,1,%s,%s,%s)""").format(
                    sql.Identifier("core", TABLES[domain])
                ),
                (
                    identity,
                    employee_id,
                    status,
                    Jsonb(plain(payload)),
                    self.actor.user_id,
                ),
            )
        after = self.get(domain, identity)
        self.cursor.execute(
            """insert into core.employee_history(record_id,domain,employee_id,version,action,
                            actor_user_id,actor_device_id,request_id,before_state,after_state)
                            values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                identity,
                domain,
                employee_id,
                after["version"],
                self.command.action,
                self.actor.user_id,
                self.actor.registered_device_id,
                self.command.request_id,
                Jsonb(before) if before else None,
                Jsonb(after),
            ),
        )
        return after

    def invalidate(self, employee_id=None):
        # Paid snapshots remain untouched; future corrections are separate records.
        for row in self.all("payroll", employee_id):
            if (
                row["status"] == "approved"
                and Decimal(row["payload"].get("paid_amount", "0")) == 0
            ):
                self.save(
                    "payroll",
                    row["id"],
                    row["employee_id"],
                    row["payload"],
                    "stale",
                    expected=row["version"],
                )

    def fingerprint(self, employee_id, payroll_id=None):
        sources = {
            domain: [
                (r["id"], r["version"])
                for r in self.all(domain)
                if r["employee_id"] in (None, str(employee_id))
            ]
            for domain in SOURCE_DOMAINS
        }
        sources["reserved_payroll"] = [
            (r["id"], r["version"])
            for r in self.all("payroll", employee_id)
            if r["id"] != str(payroll_id)
            and r["status"] in ("approved", "partially_paid", "paid")
        ]
        encoded = json.dumps(sources, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest(), sources

    def effective_profile(self, employee_id, on_date):
        row = self.cursor.execute(
            """select payload,profile_version from core.employee_profile_versions
            where employee_id=%s and effective_from<=%s order by effective_from desc,profile_version desc limit 1""",
            (employee_id, on_date),
        ).fetchone()
        if row is None:
            raise EmployeeConflict(f"No reviewed effective wage/profile on {on_date}")
        return row["payload"]

    def schedule(self, employee_id, on_date):
        rows = [
            r
            for r in self.all("schedules", employee_id)
            if r["status"] == "active"
            and r["payload"]["effective_from"] <= on_date.isoformat()
        ]
        if not rows:
            raise EmployeeConflict(f"No assigned effective schedule on {on_date}")
        return max(rows, key=lambda r: (r["payload"]["effective_from"], r["version"]))[
            "payload"
        ]

    def attendance(self, employee_id, work_date):
        corrections = [
            r
            for r in self.all("requests", employee_id)
            if r["status"] == "approved"
            and r["payload"]["request_kind"] == "correction"
            and r["payload"]["work_date"] == work_date.isoformat()
        ]
        if corrections:
            p = max(corrections, key=lambda r: r["updated_at"])["payload"]
            minutes = (
                int(
                    (
                        datetime.fromisoformat(p["clock_out"])
                        - datetime.fromisoformat(p["clock_in"])
                    ).total_seconds()
                    / 60
                )
                - p["unpaid_break_minutes"]
            )
            return {
                "employee_id": str(employee_id),
                "work_date": work_date.isoformat(),
                "working_minutes": minutes,
                "unpaid_break_minutes": p["unpaid_break_minutes"],
                "status": "accepted",
                "event_ids": [],
                "issues": [],
            }
        rows = [
            r
            for r in self.all("attendance", employee_id)
            if datetime.fromisoformat(r["payload"]["captured_at"])
            .astimezone(MANILA)
            .date()
            == work_date
        ]
        result = attendance_day(rows, work_date)
        result["employee_id"] = str(employee_id)
        return result

    def leave_balance(self, employee_id, as_of):
        profile = self.profile(employee_id)
        hire = _day(profile["payload"]["hire_date"])
        ledger = self.all("leave_ledger", employee_id)
        openings = [
            r
            for r in ledger
            if r["payload"]["kind"] == "opening"
            and r["payload"]["as_of"] <= as_of.isoformat()
        ]
        if not openings:
            raise EmployeeConflict(
                "Verified ordinary leave opening balance is required, including an explicit zero"
            )
        opening = max(openings, key=lambda r: r["payload"]["as_of"])
        since = _day(opening["payload"]["as_of"])
        allowance = profile["payload"].get("ordinary_leave_days_per_year", 5)
        eligible_from = (
            _day(profile["payload"]["leave_eligible_from"])
            if profile["payload"].get("leave_eligible_from")
            else None
        )
        accrued = max(
            0,
            leave_accrual_minutes(
                hire, as_of, annual_days=allowance, eligible_from=eligible_from
            )
            - leave_accrual_minutes(
                hire, since, annual_days=allowance, eligible_from=eligible_from
            ),
        )
        opening_minutes = opening["payload"]["minutes"]
        adjustments = sum(
            r["payload"]["minutes"]
            for r in ledger
            if r["payload"]["kind"] != "opening"
            and since.isoformat() <= r["payload"]["as_of"] <= as_of.isoformat()
        )
        requests = [
            r for r in self.all("requests", employee_id) if r["status"] == "approved"
        ]
        used = sum(
            r["payload"]["minutes"]
            for r in requests
            if r["payload"]["request_kind"] == "leave"
            and r["payload"]["leave_kind"] == "ordinary"
            and since.isoformat() <= r["payload"]["work_date"] <= as_of.isoformat()
        )
        reserved = sum(
            r["payload"]["minutes"]
            for r in requests
            if (
                r["payload"]["request_kind"] == "leave"
                and r["payload"]["leave_kind"] == "ordinary"
                and r["payload"]["work_date"] > as_of.isoformat()
            )
            or r["payload"]["request_kind"] == "leave_conversion"
        )
        eligible = (
            (as_of >= eligible_from)
            if eligible_from
            else leave_accrual_minutes(hire, as_of) >= 2400
        )
        return {
            "employee_id": str(employee_id),
            "as_of": as_of.isoformat(),
            "accrued_minutes": accrued,
            "opening_minutes": opening_minutes,
            "used_minutes": used,
            "reserved_minutes": reserved,
            "available_minutes": max(
                0, opening_minutes + accrued + adjustments - used - reserved
            )
            if eligible
            else 0,
            "eligible": eligible,
        }

    def command_payload(self):
        return self.command.model_dump(mode="json", exclude=ENVELOPE)

    def execute(self):
        c = self.command
        if c.action in REQUEST_ACTIONS or c.action in (
            "attendance_record",
            "advance_request",
        ):
            if not isinstance(c, commands.EmployeeCommand):
                raise EmployeeConflict("This action requires an employee identity")
            self.own(c.employee_id)
        create_domains = {
            **{name: "requests" for name in REQUEST_ACTIONS},
            "advance_request": "advances",
            "shortage_report": "shortages",
            "attendance_record": "attendance",
            "leave_balance_adjust": "leave_ledger",
            "payroll_history_import": "payroll_history",
            "statutory_remittance": "statutory_remittances",
            "schedule_save": "schedules",
            "payroll_adjustment": "payroll",
        }
        if c.action in create_domains and (
            c.expected_version != 0
            or self.get(create_domains[c.action], c.id, required=False)
        ):
            raise EmployeeConflict(
                "This action creates a new record; existing decisions and financial balances cannot be replaced"
            )
        if c.action in REQUEST_ACTIONS:
            return self.submit_request()
        method = getattr(self, "do_" + c.action, None)
        if method is None:
            from .employee_operations_payroll import execute_payroll_command

            return execute_payroll_command(self)
        return method()

    def do_profile_save(self):
        c = self.command_as(commands.ProfileSave)
        self.owner()
        if c.id != c.employee_id or c.daily_rate <= 0 or c.hire_date > self.today:
            raise EmployeeConflict(
                "Profile identity, actual positive daily wage and actual service date are required"
            )
        before = self.get("profiles", c.id, required=False)
        if before is None or before["payload"]["staff_manager"] != c.staff_manager:
            configure_employee_responsibility(
                self.cursor,
                actor=self.actor,
                target_user_id=c.employee_id,
                enabled=c.staff_manager,
            )
        user = self.cursor.execute(
            "select full_name from core.users where id=%s and status='active'",
            (c.employee_id,),
        ).fetchone()
        if user is None:
            raise EmployeeConflict("Select an existing active employee account")
        p = self.command_payload()
        p["full_name"] = user["full_name"]
        row = self.save(
            "profiles", c.id, c.employee_id, p, "active" if c.active else "inactive"
        )
        self.cursor.execute(
            """insert into core.employee_profile_versions(employee_id,profile_version,effective_from,payload)
                              values(%s,%s,%s,%s)""",
            (c.employee_id, row["version"], c.effective_from, Jsonb(p)),
        )
        self.invalidate(c.employee_id)
        return row

    @staticmethod
    def validate_schedule(p):
        if len(set(p["work_days"])) != len(p["work_days"]):
            raise EmployeeConflict("Working days cannot repeat")
        start = datetime.strptime(p["start_time"], "%H:%M")
        end = datetime.strptime(p["end_time"], "%H:%M")
        duration = int((end - start).total_seconds() / 60)
        if duration <= 0 or duration - p["meal_minutes"] != 480:
            raise EmployeeConflict(
                "The ordinary schedule must contain eight working hours plus its meal period"
            )

    def do_schedule_save(self):
        c = self.command_as(commands.ScheduleSave)
        self.owner()
        self.profile(c.employee_id)
        p = self.command_payload()
        self.validate_schedule(p)
        if self.get("schedules", c.id, required=False):
            raise EmployeeConflict(
                "Preserve the previous schedule; create a new effective schedule version"
            )
        row = self.save("schedules", c.id, c.employee_id, p, "active")
        self.invalidate(c.employee_id)
        return row

    def do_backup_save(self):
        c = self.command_as(commands.BackupSave)
        self.owner()
        if c.ends_on < c.starts_on or c.user_id == self.actor.user_id:
            raise EmployeeConflict(
                "Choose an independent backup and a valid effective date range"
            )
        user = self.cursor.execute(
            "select id from core.users where id=%s and status='active'", (c.user_id,)
        ).fetchone()
        if not user:
            raise EmployeeConflict("The backup must be a named active account")
        return self.save("backups", c.id, None, self.command_payload(), "active")

    def do_calendar_save(self):
        c = self.command_as(commands.CalendarSave)
        self.owner()
        row = self.save("calendar", c.id, None, self.command_payload(), "reviewed")
        self.invalidate()
        return row

    def do_statutory_month_save(self):
        c = self.command_as(commands.StatutoryMonthSave)
        self.owner()
        self.profile(c.employee_id)
        if c.month.day != 1:
            raise EmployeeConflict("Month must use its first calendar day")
        row = self.save(
            "statutory_months", c.id, c.employee_id, self.command_payload(), "reviewed"
        )
        self.invalidate(c.employee_id)
        return row

    def do_statutory_remittance(self):
        c = self.command_as(commands.StatutoryRemittance)
        self.owner()
        if c.month.day != 1 or c.amount <= 0:
            raise EmployeeConflict(
                "A valid month and actual positive remittance are required"
            )
        if any(
            r["payload"]["agency"] == c.agency
            and r["payload"]["month"] == c.month.isoformat()
            and r["payload"]["reference"].strip().casefold()
            == c.reference.strip().casefold()
            for r in self.all("statutory_remittances")
        ):
            raise EmployeeConflict(
                "This agency/month remittance reference is already recorded"
            )
        return self.save(
            "statutory_remittances", c.id, None, self.command_payload(), "completed"
        )

    def do_attendance_record(self):
        c = self.command_as(commands.AttendanceRecord)
        self.own(c.employee_id)
        if c.device_id != self.actor.registered_device_id:
            raise EmployeeAccessDenied(
                "Attendance belongs to a different registered device"
            )
        if c.expected_version != 0 or self.get("attendance", c.id, required=False):
            raise EmployeeConflict(
                "Attendance is immutable; retry with the original request ID or submit a correction"
            )
        p = self.command_payload()
        p["received_at"] = datetime.now(timezone.utc).isoformat()
        work_date = c.captured_at.astimezone(MANILA).date()
        rows = [
            r
            for r in self.all("attendance", c.employee_id)
            if datetime.fromisoformat(r["payload"]["captured_at"])
            .astimezone(MANILA)
            .date()
            == work_date
        ]
        preview_events: list[AttendanceEvent] = [*rows, {"id": str(c.id), "payload": p}]
        preview = attendance_day(preview_events, work_date)
        event_issues = [
            issue
            for issue in preview["issues"]
            if not issue.startswith("Incomplete attendance;")
        ]
        row = self.save(
            "attendance",
            c.id,
            c.employee_id,
            p,
            "pending_review" if event_issues else "accepted",
        )
        self.invalidate(c.employee_id)
        return row

    def submit_request(self):
        c = self.command
        if not isinstance(
            c,
            (
                commands.CorrectionRequest,
                commands.LeaveRequest,
                commands.ShiftRequest,
                commands.OvertimeRequest,
                commands.LeaveConversionRequest,
            ),
        ):
            raise EmployeeConflict("This action requires an employee request")
        self.own(c.employee_id)
        p = self.command_payload()
        p["request_kind"] = REQUEST_ACTIONS[c.action]
        if c.action == "correction_request":
            if (
                c.clock_in.astimezone(MANILA).date() != c.work_date
                or c.clock_out.astimezone(MANILA).date() != c.work_date
            ):
                raise EmployeeConflict(
                    "Corrected timestamps must belong to the selected work date"
                )
            minutes = (
                c.clock_out - c.clock_in
            ).total_seconds() / 60 - c.unpaid_break_minutes
            if minutes <= 0 or minutes > 1440:
                raise EmployeeConflict("The correction must contain valid working time")
        if c.action == "shift_request":
            self.validate_schedule(p)
            if c.effective_from < self.today:
                raise EmployeeConflict(
                    "A shift change must be approved before it takes effect"
                )
        if (
            isinstance(
                c,
                (
                    commands.LeaveRequest,
                    commands.OvertimeRequest,
                    commands.LeaveConversionRequest,
                ),
            )
            and c.minutes <= 0
        ):
            raise EmployeeConflict("Requested minutes must be positive")
        if c.action == "leave_request" and c.minutes > 480:
            raise EmployeeConflict(
                "Use one request per scheduled day, up to eight hours"
            )
        if c.action == "leave_request" and c.leave_kind == "ordinary":
            if (
                self.leave_balance(c.employee_id, c.work_date)["available_minutes"]
                < c.minutes
            ):
                raise EmployeeConflict("Insufficient eligible ordinary leave balance")
        row = self.save("requests", c.id, c.employee_id, p, "pending")
        self.invalidate(c.employee_id)
        return row

    def do_request_decide(self):
        c = self.command_as(commands.RequestDecide)
        row = self.get("requests", c.id)
        self.version(row)
        p = row["payload"]
        kind = p["request_kind"]
        if (
            c.decision == "cancelled"
            and row["status"] == "pending"
            and str(c.employee_id) == str(self.actor.user_id)
        ):
            self.own(c.employee_id)
        else:
            self.staff(subject=c.employee_id)
        if row["status"] == "approved" and c.decision == "cancelled":
            effective = p.get("work_date", p.get("effective_from", p.get("as_of", "")))
            if effective <= self.today.isoformat():
                raise EmployeeConflict(
                    "Past or current approved time requires a correction, not silent cancellation"
                )
            if kind == "shift" and p.get("schedule_id"):
                schedule = self.get("schedules", p["schedule_id"])
                self.save(
                    "schedules",
                    schedule["id"],
                    c.employee_id,
                    schedule["payload"],
                    "cancelled",
                    expected=schedule["version"],
                )
            if kind == "leave_conversion" and any(
                r["status"] in ("approved", "partially_paid", "paid")
                and r["payload"].get("leave_conversion_request_id") == str(c.id)
                for r in self.all("payroll", c.employee_id)
            ):
                raise EmployeeConflict(
                    "An approved or paid conversion settlement must be corrected before cancellation"
                )
        elif row["status"] != "pending":
            raise EmployeeConflict(
                "This request has already been decided; submit a correction or linked payroll adjustment"
            )
        if c.decision == "approved":
            if kind == "leave":
                schedule = self.schedule(c.employee_id, _day(p["work_date"]))
                if _day(p["work_date"]).isoweekday() not in schedule["work_days"]:
                    raise EmployeeConflict(
                        "Leave must correspond to an assigned working day"
                    )
                if (
                    p["leave_kind"] == "ordinary"
                    and self.leave_balance(c.employee_id, _day(p["work_date"]))[
                        "available_minutes"
                    ]
                    < p["minutes"]
                ):
                    raise EmployeeConflict(
                        "Insufficient eligible ordinary leave credits"
                    )
                if p["leave_kind"] not in ("ordinary", "unpaid") and not p.get(
                    "eligibility_evidence"
                ):
                    raise EmployeeConflict(
                        "Special leave needs its own reviewed eligibility evidence"
                    )
                if (
                    p["leave_kind"] not in ("ordinary", "unpaid")
                    and c.paid_minutes is None
                ):
                    raise EmployeeConflict(
                        "Special leave needs explicit reviewed employer-paid minutes; agency benefits are assessed separately"
                    )
                paid = (
                    0
                    if p["leave_kind"] == "unpaid"
                    else (
                        c.paid_minutes if c.paid_minutes is not None else p["minutes"]
                    )
                )
                if paid > p["minutes"]:
                    raise EmployeeConflict("Paid leave cannot exceed requested time")
                p["paid_minutes"] = paid
                others = [
                    r
                    for r in self.all("requests", c.employee_id)
                    if r["status"] == "approved"
                    and r["payload"]["request_kind"] == "leave"
                    and r["payload"]["work_date"] == p["work_date"]
                ]
                worked = self.attendance(c.employee_id, _day(p["work_date"]))
                known_work = (
                    worked["working_minutes"] if worked["status"] == "accepted" else 0
                )
                if (
                    known_work
                    + paid
                    + sum(r["payload"].get("paid_minutes", 0) for r in others)
                    > 480
                ):
                    raise EmployeeConflict(
                        "Leave overlaps approved working time or another leave request"
                    )
            elif kind == "shift":
                if _day(p["effective_from"]) < self.today:
                    raise EmployeeConflict(
                        "The requested effective date has already passed"
                    )
                schedule_id = uuid4()
                self.save(
                    "schedules",
                    schedule_id,
                    c.employee_id,
                    {k: v for k, v in p.items() if k != "request_kind"},
                    "active",
                    expected=0,
                )
                p["schedule_id"] = str(schedule_id)
            elif kind == "leave_conversion":
                if (
                    self.leave_balance(c.employee_id, _day(p["as_of"]))[
                        "available_minutes"
                    ]
                    < p["minutes"]
                ):
                    raise EmployeeConflict(
                        "Insufficient eligible credits for conversion"
                    )
        p["decision_reason"] = c.reason
        p["decided_by"] = str(self.actor.user_id)
        result = self.save("requests", c.id, c.employee_id, p, c.decision)
        self.invalidate(c.employee_id)
        return result

    def do_leave_balance_adjust(self):
        c = self.command_as(commands.LeaveBalanceAdjust)
        self.owner()
        self.profile(c.employee_id)
        if c.kind == "opening" and any(
            r["payload"]["kind"] == "opening"
            for r in self.all("leave_ledger", c.employee_id)
        ):
            raise EmployeeConflict(
                "Opening balance already exists; use a traceable correction"
            )
        if c.kind == "opening" and c.minutes < 0:
            raise EmployeeConflict("An opening balance cannot be negative")
        row = self.save(
            "leave_ledger", c.id, c.employee_id, self.command_payload(), "recorded"
        )
        self.invalidate(c.employee_id)
        return row

    def do_task_save(self):
        c = self.command_as(commands.TaskSave)
        self.staff("assign_tasks")
        self.profile(c.employee_id)
        existing = self.get("tasks", c.id, required=False)
        if (
            existing
            and existing["created_by"] != str(self.actor.user_id)
            and not is_employee_owner(self.actor)
        ):
            raise EmployeeAccessDenied(
                "Only the assigner or owner can change this task"
            )
        if existing and existing["status"] in ("done", "cancelled"):
            raise EmployeeConflict("Reopen the task with a reason before editing it")
        return self.save(
            "tasks",
            c.id,
            c.employee_id,
            self.command_payload(),
            existing["status"] if existing else "todo",
        )

    def do_task_progress(self):
        c = self.command_as(commands.TaskProgress)
        row = self.get("tasks", c.id)
        self.version(row)
        own = row["employee_id"] == str(self.actor.user_id)
        assigner = row["created_by"] == str(self.actor.user_id) or is_employee_owner(
            self.actor
        )
        if not own and not assigner:
            raise EmployeeAccessDenied(
                "Only the assignee, assigner or owner can change task progress"
            )
        if (
            row["status"] in ("done", "cancelled") or c.status == "cancelled"
        ) and not assigner:
            raise EmployeeAccessDenied(
                "Only the assigner or owner can reopen or cancel the task"
            )
        p = row["payload"]
        p["progress_reason"] = c.reason
        return self.save("tasks", c.id, c.employee_id, p, c.status)

    @staticmethod
    def validate_installments(installments, amount):
        dates = [i["due_date"] for i in installments]
        if len(set(dates)) != len(dates) or dates != sorted(dates):
            raise EmployeeConflict("Installment dates must be distinct and increasing")
        if (
            any(Decimal(i["amount"]) <= 0 for i in installments)
            or sum((Decimal(i["amount"]) for i in installments), Decimal(0)) != amount
        ):
            raise EmployeeConflict(
                "Positive principal-only installments must equal the agreed principal"
            )

    def do_advance_request(self):
        c = self.command_as(commands.AdvanceRequest)
        self.own(c.employee_id)
        p = self.command_payload()
        self.validate_installments(p["installments"], c.amount)
        if c.amount <= 0 or any(
            _day(i["due_date"]) < self.today for i in p["installments"]
        ):
            raise EmployeeConflict(
                "A positive actual advance and prospective agreed repayment dates are required"
            )
        p.update(
            disbursed_amount="0.00",
            repaid_amount="0.00",
            outstanding_amount="0.00",
            repayment_history=[],
        )
        return self.save("advances", c.id, c.employee_id, p, "requested")

    def do_advance_terms(self):
        c = self.command_as(commands.AdvanceTerms)
        self.own(c.employee_id)
        row = self.get("advances", c.id)
        self.version(row)
        if row["status"] in ("rejected", "repaid", "terms_pending"):
            raise EmployeeConflict(
                "This advance cannot be rescheduled while completed or while another terms proposal awaits review"
            )
        if any(
            r["status"] == "partially_paid"
            and any(
                a["advance_id"] == str(c.id)
                for a in r["payload"].get("advance_allocations", [])
            )
            for r in self.all("payroll", c.employee_id)
        ):
            raise EmployeeConflict(
                "Complete or reconcile the partially paid payroll before changing its reserved advance terms"
            )
        p = row["payload"]
        terms = self.command_payload()
        principal = (
            Decimal(p["outstanding_amount"])
            if Decimal(p["disbursed_amount"]) > 0
            else Decimal(p["amount"])
        )
        self.validate_installments(terms["installments"], principal)
        p["prior_status"] = row["status"]
        p["proposed_terms"] = terms
        result = self.save("advances", c.id, c.employee_id, p, "terms_pending")
        self.invalidate(c.employee_id)
        return result

    def do_advance_decide(self):
        c = self.command_as(commands.AdvanceDecide)
        self.staff("approve_advances", c.employee_id)
        row = self.get("advances", c.id)
        self.version(row)
        if row["status"] not in ("requested", "terms_pending"):
            raise EmployeeConflict("This advance is not awaiting approval")
        p = row["payload"]
        status = c.decision
        if row["status"] == "terms_pending":
            if c.decision == "approved":
                p.update(p.pop("proposed_terms"))
                p["terms_repaid_base"] = p["repaid_amount"]
            else:
                p.pop("proposed_terms", None)
            status = p.pop("prior_status")
        p["decision_reason"] = c.reason
        p["approved_by"] = str(self.actor.user_id)
        result = self.save("advances", c.id, c.employee_id, p, status)
        self.invalidate(c.employee_id)
        return result

    def do_advance_disburse(self):
        c = self.command_as(commands.AdvanceDisburse)
        self.owner()
        row = self.get("advances", c.id)
        self.version(row)
        if (
            row["status"] != "approved"
            or Decimal(row["payload"]["disbursed_amount"]) != 0
        ):
            raise EmployeeConflict(
                "Only an approved, undisbursed advance can be disbursed"
            )
        p = row["payload"]
        p["disbursed_amount"] = p["amount"]
        p["outstanding_amount"] = p["amount"]
        p["disbursed_at"] = c.occurred_at.isoformat()
        payment = self.command_payload()
        payment.update(
            advance_id=str(c.id),
            amount=p["amount"],
            recorded_by=str(self.actor.user_id),
            payment_kind="advance_disbursement",
        )
        self.save(
            "payments", c.request_id, c.employee_id, payment, "completed", expected=0
        )
        result = self.save("advances", c.id, c.employee_id, p, "disbursed")
        self.invalidate(c.employee_id)
        return result

    def do_advance_repay(self):
        c = self.command_as(commands.AdvanceRepay)
        self.owner()
        row = self.get("advances", c.id)
        self.version(row)
        if (
            row["status"] != "disbursed"
            or c.amount <= 0
            or c.amount > Decimal(row["payload"]["outstanding_amount"])
        ):
            raise EmployeeConflict(
                "Repayment must be positive and no greater than outstanding disbursed principal"
            )
        reserved = sum(
            (
                Decimal(a["amount"])
                for payroll in self.all("payroll", c.employee_id)
                if payroll["status"] in ("approved", "partially_paid")
                for a in payroll["payload"].get("advance_allocations", [])
                if a["advance_id"] == str(c.id)
            ),
            Decimal(0),
        )
        if c.amount > Decimal(row["payload"]["outstanding_amount"]) - reserved:
            raise EmployeeConflict(
                "This principal is reserved by approved payroll; reconcile that payroll before accepting an external repayment"
            )
        if any(
            p["payload"].get("payment_kind") == "advance_repayment"
            and p["payload"].get("advance_id") == str(c.id)
            and p["status"] == "completed"
            and p["payload"]["reference"].strip().casefold()
            == c.reference.strip().casefold()
            for p in self.all("payments", c.employee_id)
        ):
            raise EmployeeConflict(
                "This external advance repayment reference is already recorded"
            )
        p = row["payload"]
        p["repaid_amount"] = money_text(Decimal(p["repaid_amount"]) + c.amount)
        p["outstanding_amount"] = money_text(
            Decimal(p["outstanding_amount"]) - c.amount
        )
        p["repayment_history"].append(
            {
                "amount": money_text(c.amount),
                "occurred_at": c.occurred_at.isoformat(),
                "reference": c.reference,
                "source": "external",
            }
        )
        payment = self.command_payload()
        payment.update(
            advance_id=str(c.id),
            recorded_by=str(self.actor.user_id),
            payment_kind="advance_repayment",
        )
        self.save(
            "payments", c.request_id, c.employee_id, payment, "completed", expected=0
        )
        result = self.save(
            "advances",
            c.id,
            c.employee_id,
            p,
            "repaid" if Decimal(p["outstanding_amount"]) == 0 else "disbursed",
        )
        self.invalidate(c.employee_id)
        return result

    def do_shortage_report(self):
        c = self.command_as(commands.ShortageReport)
        self.profile(c.employee_id)
        if str(c.employee_id) != str(self.actor.user_id) and not (
            is_employee_owner(self.actor) or self.manager()
        ):
            raise EmployeeAccessDenied(
                "Reporting another employee's cash discrepancy requires the owner or active staff manager"
            )
        if c.accounted_cash >= c.expected_cash:
            raise EmployeeConflict(
                "A discrepancy requires expected cash above accounted cash"
            )
        p = self.command_payload()
        p["shortage_amount"] = money_text(c.expected_cash - c.accounted_cash)
        result = self.save("shortages", c.id, c.employee_id, p, "reported")
        self.invalidate(c.employee_id)
        return result

    def do_shortage_respond(self):
        c = self.command_as(commands.ShortageRespond)
        self.own(c.employee_id)
        row = self.get("shortages", c.id)
        self.version(row)
        if row["status"] not in ("reported", "responded"):
            raise EmployeeConflict("This case has already been decided")
        p = row["payload"]
        p["explanation"] = c.explanation
        return self.save("shortages", c.id, c.employee_id, p, "responded")

    def do_shortage_decide(self):
        c = self.command_as(commands.ShortageDecide)
        self.owner()
        row = self.get("shortages", c.id)
        self.version(row)
        if str(c.employee_id) == str(self.actor.user_id):
            raise EmployeeAccessDenied(
                "An independent reviewer must decide their own cash case"
            )
        if c.decision == "reversed" and row["status"] != "confirmed":
            raise EmployeeConflict("Only a confirmed shortage can be reversed")
        if c.decision != "reversed" and row["status"] not in ("reported", "responded"):
            raise EmployeeConflict("This shortage already has a decision")
        p = row["payload"]
        p.update(
            decision_reason=c.reason,
            response_opportunity=c.response_opportunity,
            decided_by=str(self.actor.user_id),
        )
        result = self.save("shortages", c.id, c.employee_id, p, c.decision)
        self.invalidate(c.employee_id)
        return result

    def do_accounting_prepare(self):
        c = self.command_as(commands.AccountingPrepare)
        if not (is_employee_owner(self.actor) or self.manager()):
            raise EmployeeAccessDenied(
                "Accounting preparation requires the owner or active staff manager"
            )
        p = self.command_payload()
        previous = self.get("accounting_preparations", c.id, required=False)
        if (
            previous
            and previous["created_by"] != str(self.actor.user_id)
            and not is_employee_owner(self.actor)
        ):
            raise EmployeeAccessDenied(
                "Only the preparer or owner can update this accounting preparation"
            )
        if c.preparation_kind == "journal":
            from .employee_authorization import save_employee_journal_draft

            if len(p["lines"]) < 2 or sum(
                (Decimal(i["debit"]) for i in p["lines"]), Decimal(0)
            ) != sum((Decimal(i["credit"]) for i in p["lines"]), Decimal(0)):
                raise EmployeeConflict(
                    "A journal draft requires balanced debit and credit lines"
                )
            entry_id = save_employee_journal_draft(
                self.cursor,
                actor=self.actor,
                posting_date=c.as_of,
                description=c.description,
                lines=p["lines"],
                entry_id=UUID(previous["payload"]["journal_entry_id"])
                if previous and previous["payload"].get("journal_entry_id")
                else None,
            )
            p["journal_entry_id"] = str(entry_id)
        elif c.statement_balance is None or c.ledger_balance is None:
            raise EmployeeConflict(
                "Reconciliation preparation requires statement and ledger balances"
            )
        return self.save("accounting_preparations", c.id, None, p, "draft")


class PostgresEmployeeOperationsRepository:
    def workspace(self, *, actor: AccountContext, request_id=None):
        from .employee_operations_workspace import build_workspace

        with open_connection() as connection:
            with (
                connection.transaction(),
                connection.cursor(row_factory=dict_row) as cursor,
            ):
                cursor.execute(
                    "select pg_advisory_xact_lock(hashtext('spina.employee_operations'))"
                )
                require_employee_actor(cursor, actor)
                return build_workspace(EmployeeTransaction(cursor, actor), request_id)

    def execute(self, *, actor: AccountContext, command: EmployeeAction):
        with open_connection() as connection:
            with (
                connection.transaction(),
                connection.cursor(row_factory=dict_row) as cursor,
            ):
                return self.execute_in_transaction(cursor, actor=actor, command=command)

    @staticmethod
    def execute_in_transaction(
        cursor, *, actor: AccountContext, command: EmployeeAction
    ):
        cursor.execute(
            "select pg_advisory_xact_lock(hashtext('spina.employee_operations'))"
        )
        require_employee_actor(cursor, actor)
        payload = command.model_dump(mode="json")
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        receipt = cursor.execute(
            "select * from core.employee_action_receipts where request_id=%s",
            (command.request_id,),
        ).fetchone()
        if receipt:
            if (
                str(receipt["actor_user_id"]) != str(actor.user_id)
                or str(receipt["actor_device_id"]) != str(actor.registered_device_id)
                or receipt["body_sha256"] != digest
            ):
                raise EmployeeConflict(
                    "The request identity was already used with different content, account or device"
                )
            return dict(receipt["result"], replayed=True)
        row = EmployeeTransaction(cursor, actor, command).execute()
        result = {
            "request_id": str(command.request_id),
            "id": str(row["id"]),
            "version": row["version"],
            "status": "pending_review"
            if row["status"] in ("pending", "pending_review")
            else "accepted",
            "replayed": False,
            "message": "Recorded; refresh the workspace for the authoritative state",
        }
        cursor.execute(
            """insert into core.employee_action_receipts(request_id,actor_user_id,actor_device_id,body_sha256,result)
                          values(%s,%s,%s,%s,%s)""",
            (
                command.request_id,
                actor.user_id,
                actor.registered_device_id,
                digest,
                Jsonb(result),
            ),
        )
        return result
