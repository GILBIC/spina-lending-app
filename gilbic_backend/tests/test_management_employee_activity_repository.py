from __future__ import annotations

from gilbic_backend.management_employee_activity import EmployeeActivityDomain
from gilbic_backend.management_employee_activity_registry import (
    visible_employee_activity_domains,
)


def test_registry_exposes_only_domains_with_an_owning_view_permission() -> None:
    visible = visible_employee_activity_domains(
        frozenset(
            {
                "employee.activity.review",
                "accounting.view",
                "remittance.view",
            }
        )
    )

    assert [domain.code for domain in visible] == [
        EmployeeActivityDomain.ACCOUNTING,
        EmployeeActivityDomain.REMITTANCE_OPERATIONS,
    ]
    assert all(
        domain.required_permission != "employee.activity.review" for domain in visible
    )


def test_registry_does_not_advertise_unimplemented_sensitive_domains() -> None:
    visible = visible_employee_activity_domains(
        frozenset(
            {
                "employee.activity.review",
                "accounting.view",
                "support.manage",
                "remittance.view",
                "account.manage",
            }
        )
    )

    codes = {domain.code for domain in visible}
    assert EmployeeActivityDomain.HR not in codes
    assert EmployeeActivityDomain.PAYROLL not in codes
    assert EmployeeActivityDomain.ADMINISTRATION not in codes


def test_registry_requires_the_exact_domain_permission() -> None:
    visible = visible_employee_activity_domains(
        frozenset(
            {
                "employee.activity.review",
                "accounting.journal.manage",
                "support.view",
                "remittance.receive",
            }
        )
    )

    assert visible == ()
