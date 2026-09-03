from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID


class EmployeeActivityDomain(StrEnum):
    ACCOUNTING = "accounting"
    HR = "hr"
    PAYROLL = "payroll"
    CRM_SUPPORT = "crm_support"
    REMITTANCE_OPERATIONS = "remittance_operations"
    ADMINISTRATION = "administration"


class EmployeeActivityStatus(StrEnum):
    NO_ACTIVITY = "no_activity"
    IN_PROGRESS = "in_progress"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    NEEDS_ATTENTION = "needs_attention"


class EmployeeActivityCode(StrEnum):
    ACCOUNTING_JOURNAL_PREPARED = "accounting.journal.prepared"
    SUPPORT_ANSWERED = "support.answered"
    SUPPORT_RESOLVED = "support.resolved"
    REMITTANCE_SUBMITTED = "remittance.submitted"


class EmployeeActivityNavigationCode(StrEnum):
    GENERAL_JOURNALS = "management.general_journals"
    SUPPORT_REQUESTS = "management.support_requests"
    REMITTANCE_REVIEW = "management.remittance_review"


@dataclass(frozen=True, slots=True)
class EmployeeActivityRow:
    employee_user_id: UUID
    employee_name: str
    function_labels: tuple[str, ...]
    completed_count: int
    in_progress_count: int
    awaiting_review_count: int
    needs_attention_count: int
    total_visible_count: int
    last_activity_at: datetime | None
    last_activity_domain: EmployeeActivityDomain | None
    status: EmployeeActivityStatus
    status_message: str


@dataclass(frozen=True, slots=True)
class EmployeeActivityItem:
    employee_user_id: UUID
    activity_code: EmployeeActivityCode
    domain: EmployeeActivityDomain
    occurred_at: datetime
    business_date: date
    record_type: str
    record_id: UUID
    display_reference: str
    summary: str
    workflow_state: str
    status: EmployeeActivityStatus
    maker_name: str | None
    checker_name: str | None
    navigation_code: EmployeeActivityNavigationCode | None


@dataclass(frozen=True, slots=True)
class EmployeeActivityPage:
    date_from: date
    date_to: date
    generated_at: datetime
    available_domains: tuple[EmployeeActivityDomain, ...]
    rows: tuple[EmployeeActivityRow, ...]
    total_count: int


@dataclass(frozen=True, slots=True)
class EmployeeActivityTimeline:
    employee_user_id: UUID
    employee_name: str
    function_labels: tuple[str, ...]
    date_from: date
    date_to: date
    generated_at: datetime
    available_domains: tuple[EmployeeActivityDomain, ...]
    items: tuple[EmployeeActivityItem, ...]
    total_count: int
