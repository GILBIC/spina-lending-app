"""Strict public commands for the employee domain; money crosses HTTP as decimal text."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    TypeAdapter,
)
from pydantic_core import PydanticCustomError


def _money_text(value: object) -> object:
    if not isinstance(value, str):
        raise PydanticCustomError(
            "value_error",
            "Value error, Money must be a decimal string, never a JSON number",
        )
    return value


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include its UTC offset")
    return value


Money = Annotated[
    Decimal,
    BeforeValidator(_money_text, json_schema_input_type=str),
    Field(ge=0, max_digits=14, decimal_places=2),
]
SignedMoney = Annotated[
    Decimal,
    BeforeValidator(_money_text, json_schema_input_type=str),
    Field(max_digits=14, decimal_places=2),
]
Timestamp = Annotated[datetime, AfterValidator(_aware)]
Note = Annotated[str, Field(min_length=1, max_length=2000)]
Day = Annotated[int, Field(ge=1, le=7)]
Minutes = Annotated[int, Field(ge=0, le=1440)]
ClockTime = Annotated[str, Field(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")]
Method = Literal["cash", "gcash", "bank"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Command(StrictModel):
    request_id: UUID
    id: UUID
    expected_version: int = Field(ge=0)


class EmployeeCommand(Command):
    employee_id: UUID


class ProfileSave(EmployeeCommand):
    action: Literal["profile_save"]
    hire_date: date
    effective_from: date
    daily_rate: Money
    payout_method: Method
    staff_manager: bool
    active: bool
    premium_pay_covered: bool
    holiday_pay_covered: bool
    tax_exempt: bool
    gp_partial_day_policy: Literal["prorated", "full_day"]
    classification_basis: Note
    ordinary_leave_days_per_year: int = Field(default=5, ge=5, le=365)
    leave_eligible_from: date | None = None


class ScheduleSave(EmployeeCommand):
    action: Literal["schedule_save"]
    effective_from: date
    work_days: list[Day] = Field(min_length=1, max_length=6)
    start_time: ClockTime
    end_time: ClockTime
    meal_minutes: Minutes
    reason: Note


class BackupSave(Command):
    action: Literal["backup_save"]
    user_id: UUID
    starts_on: date
    ends_on: date
    duties: list[
        Literal[
            "review_requests",
            "approve_payroll",
            "approve_advances",
            "assign_tasks",
            "prepare_payroll",
        ]
    ] = Field(max_length=5)
    reason: Note


class CalendarSave(Command):
    action: Literal["calendar_save"]
    work_date: date
    day_kind: Literal[
        "ordinary",
        "special_working",
        "special_nonworking",
        "regular_holiday",
        "double_regular_holiday",
    ]
    source: Note


class StatutoryMonthSave(EmployeeCommand):
    action: Literal["statutory_month_save"]
    month: date
    sss_employee: Money
    sss_employer: Money
    philhealth_employee: Money
    philhealth_employer: Money
    pagibig_employee: Money
    pagibig_employer: Money
    employer_other: Money
    compensation_basis: Note
    source: Note
    prior_employee_deductions: Money | None = None


class StatutoryRemittance(Command):
    action: Literal["statutory_remittance"]
    month: date
    agency: Literal["sss", "philhealth", "pagibig", "bir"]
    amount: Money
    occurred_at: Timestamp
    reference: Note
    settlement_evidence: Note


class AttendanceRecord(EmployeeCommand):
    action: Literal["attendance_record"]
    event_type: Literal["clock_in", "break_start", "break_end", "clock_out"]
    captured_at: Timestamp
    device_id: UUID
    previous_event_id: UUID | None
    sequence: int = Field(ge=1)
    offline: bool


class CorrectionRequest(EmployeeCommand):
    action: Literal["correction_request"]
    work_date: date
    clock_in: Timestamp
    clock_out: Timestamp
    unpaid_break_minutes: Minutes
    reason: Note


class LeaveRequest(EmployeeCommand):
    action: Literal["leave_request"]
    work_date: date
    minutes: Minutes
    leave_kind: Literal[
        "ordinary",
        "maternity",
        "paternity",
        "solo_parent",
        "vawc",
        "special_women",
        "unpaid",
    ]
    reason: Note
    eligibility_evidence: str = Field(default="", max_length=2000)


class ShiftRequest(EmployeeCommand):
    action: Literal["shift_request"]
    effective_from: date
    work_days: list[Day] = Field(min_length=1, max_length=6)
    start_time: ClockTime
    end_time: ClockTime
    meal_minutes: Minutes
    reason: Note


class OvertimeRequest(EmployeeCommand):
    action: Literal["overtime_request"]
    work_date: date
    minutes: Minutes
    reason: Note


class LeaveConversionRequest(EmployeeCommand):
    action: Literal["leave_conversion_request"]
    as_of: date
    minutes: int = Field(ge=1, le=1000000)
    reason: Note


class RequestDecide(EmployeeCommand):
    action: Literal["request_decide"]
    decision: Literal["approved", "rejected", "cancelled"]
    reason: Note
    paid_minutes: Minutes | None = None


class LeaveBalanceAdjust(EmployeeCommand):
    action: Literal["leave_balance_adjust"]
    as_of: date
    minutes: int = Field(ge=-1000000, le=1000000)
    kind: Literal["opening", "correction"]
    reason: Note


class TaskSave(EmployeeCommand):
    action: Literal["task_save"]
    description: Note
    due_date: date
    notes: str = Field(default="", max_length=2000)
    related_client_id: UUID | None = None
    related_application_id: UUID | None = None


class TaskProgress(EmployeeCommand):
    action: Literal["task_progress"]
    status: Literal["todo", "in_progress", "done", "cancelled"]
    reason: Note


class Installment(StrictModel):
    due_date: date
    amount: Money


class AdvanceRequest(EmployeeCommand):
    action: Literal["advance_request"]
    amount: Money
    reason: Note
    installments: list[Installment] = Field(min_length=1, max_length=104)
    employee_acknowledgment: Note
    payroll_authorization: Note


class AdvanceTerms(EmployeeCommand):
    action: Literal["advance_terms"]
    installments: list[Installment] = Field(min_length=1, max_length=104)
    employee_acknowledgment: Note
    payroll_authorization: Note
    reason: Note


class AdvanceDecide(EmployeeCommand):
    action: Literal["advance_decide"]
    decision: Literal["approved", "rejected"]
    reason: Note


class AdvanceDisburse(EmployeeCommand):
    action: Literal["advance_disburse"]
    occurred_at: Timestamp
    payment_method: Method
    reference: Note
    settlement_evidence: Note
    employee_acknowledgment: Note


class AdvanceRepay(EmployeeCommand):
    action: Literal["advance_repay"]
    amount: Money
    occurred_at: Timestamp
    reference: Note
    settlement_evidence: Note


class ShortageReport(EmployeeCommand):
    action: Literal["shortage_report"]
    work_date: date
    expected_cash: Money
    accounted_cash: Money
    evidence: Note


class ShortageRespond(EmployeeCommand):
    action: Literal["shortage_respond"]
    explanation: Note


class ShortageDecide(EmployeeCommand):
    action: Literal["shortage_decide"]
    decision: Literal["confirmed", "dismissed", "reversed"]
    reason: Note
    response_opportunity: Note


class PayrollPrepare(EmployeeCommand):
    action: Literal["payroll_prepare"]
    week_start: date
    payroll_kind: Literal[
        "weekly", "thirteenth_month", "separation", "leave_conversion"
    ] = "weekly"
    leave_conversion_request_id: UUID | None = None
    withholding_override: Money | None = None
    withholding_basis: str = Field(default="", max_length=2000)
    unworked_holiday_dates: list[date] = Field(default_factory=list, max_length=7)
    unworked_holiday_basis: str = Field(default="", max_length=2000)
    reason: Note


class PayrollHistoryImport(EmployeeCommand):
    action: Literal["payroll_history_import"]
    year: int = Field(ge=2000, le=2200)
    through_date: date
    basic_earned: Money
    taxable_earned: Money
    tax_withheld: Money
    thirteenth_paid: Money
    other_benefits_paid: Money
    source: Note


class PayrollApprove(EmployeeCommand):
    action: Literal["payroll_approve"]
    decision: Literal["approved", "rejected"]
    reason: Note


class PayrollPayment(EmployeeCommand):
    action: Literal["payroll_payment"]
    amount: Money
    occurred_at: Timestamp
    payment_method: Method
    reference: str = Field(default="", max_length=2000)
    settlement_evidence: str = Field(default="", max_length=2000)
    employee_acknowledgment: str = Field(default="", max_length=2000)
    result: Literal["completed", "pending", "failed"]


class PayrollAdjustment(EmployeeCommand):
    action: Literal["payroll_adjustment"]
    original_payroll_id: UUID
    component: Literal[
        "basic_pay",
        "leave_pay",
        "overtime",
        "premium_pay",
        "performance_benefit",
        "tax",
        "statutory",
        "advance_repayment",
        "lawful_recovery",
        "other",
    ]
    amount: SignedMoney
    reason: Note
    lawful_basis: str = Field(default="", max_length=2000)
    responsibility_evidence: str = Field(default="", max_length=2000)
    employee_response: str = Field(default="", max_length=2000)
    maximum_authorized_recovery: Money | None = None
    shortage_id: UUID | None = None


class AccountingLine(StrictModel):
    account_code: Annotated[str, Field(min_length=1, max_length=100)]
    debit: Money
    credit: Money


class AccountingPrepare(Command):
    action: Literal["accounting_prepare"]
    preparation_kind: Literal["journal", "reconciliation"]
    description: Note
    as_of: date
    evidence: Note
    lines: list[AccountingLine] = Field(default_factory=list, max_length=100)
    statement_balance: Money | None = None
    ledger_balance: Money | None = None


EmployeeAction = Annotated[
    ProfileSave
    | ScheduleSave
    | BackupSave
    | CalendarSave
    | StatutoryMonthSave
    | StatutoryRemittance
    | AttendanceRecord
    | CorrectionRequest
    | LeaveRequest
    | ShiftRequest
    | OvertimeRequest
    | LeaveConversionRequest
    | RequestDecide
    | LeaveBalanceAdjust
    | TaskSave
    | TaskProgress
    | AdvanceRequest
    | AdvanceTerms
    | AdvanceDecide
    | AdvanceDisburse
    | AdvanceRepay
    | ShortageReport
    | ShortageRespond
    | ShortageDecide
    | PayrollPrepare
    | PayrollApprove
    | PayrollPayment
    | PayrollAdjustment
    | PayrollHistoryImport
    | AccountingPrepare,
    Field(discriminator="action"),
]

ACTION_ADAPTER = TypeAdapter(EmployeeAction)
