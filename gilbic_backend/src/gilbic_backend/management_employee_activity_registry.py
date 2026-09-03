from __future__ import annotations

from dataclasses import dataclass

from .management_employee_activity import (
    EmployeeActivityCode,
    EmployeeActivityDomain,
)


@dataclass(frozen=True, slots=True)
class EmployeeActivityDomainSpec:
    code: EmployeeActivityDomain
    required_permission: str
    activity_codes: tuple[EmployeeActivityCode, ...]


REGISTERED_EMPLOYEE_ACTIVITY_DOMAINS = (
    EmployeeActivityDomainSpec(
        code=EmployeeActivityDomain.ACCOUNTING,
        required_permission="accounting.view",
        activity_codes=(EmployeeActivityCode.ACCOUNTING_JOURNAL_PREPARED,),
    ),
    EmployeeActivityDomainSpec(
        code=EmployeeActivityDomain.CRM_SUPPORT,
        required_permission="support.manage",
        activity_codes=(
            EmployeeActivityCode.SUPPORT_ANSWERED,
            EmployeeActivityCode.SUPPORT_RESOLVED,
        ),
    ),
    EmployeeActivityDomainSpec(
        code=EmployeeActivityDomain.REMITTANCE_OPERATIONS,
        required_permission="remittance.view",
        activity_codes=(EmployeeActivityCode.REMITTANCE_SUBMITTED,),
    ),
)


def visible_employee_activity_domains(
    permissions: frozenset[str],
) -> tuple[EmployeeActivityDomainSpec, ...]:
    return tuple(
        domain
        for domain in REGISTERED_EMPLOYEE_ACTIVITY_DOMAINS
        if domain.required_permission in permissions
    )
