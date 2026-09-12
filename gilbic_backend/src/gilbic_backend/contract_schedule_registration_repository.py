from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Sequence
from uuid import UUID

from psycopg.rows import dict_row

from .contract_schedule_engine import PaymentFrequency
from .contract_schedule_registration_service import (
    ContractEvidenceBasis,
    VerifiedScheduleInstallment,
    register_verified_contract_schedule,
)
from .contract_schedule_service import (
    ContractScheduleConflict,
    ContractScheduleNotReady,
)
from .database import open_connection


@dataclass(frozen=True, slots=True)
class ContractScheduleLoanContext:
    loan_id: UUID
    loan_number: str
    client_code: str
    client_name: str
    loan_type_name: str
    calculation_mode: str
    daily_interest_per_1000: Decimal
    principal: Decimal
    daily_amount: Decimal
    date_released: date
    due_date: date
    loan_status: str
    active_schedule_id: UUID | None
    active_schedule_version: int | None
    active_payment_frequency: str | None
    active_contract_reference: str | None


@dataclass(frozen=True, slots=True)
class SevenBySevenPricingComplianceReview:
    id: int
    loan_id: UUID
    terms_fingerprint: str
    applicability_review_ready: bool
    pricing_cap_review_ready: bool
    disclosure_ready: bool
    total_cost_cap_review_ready: bool
    evidence_reference: str
    review_note: str
    reviewed_by_user_id: UUID
    reviewed_at: datetime
    penalty_policy_version: str | None = None
    penalty_monthly_rate: Decimal | None = None
    penalty_proration_days: int | None = None
    penalty_rate_ceiling: Decimal | None = None
    lifetime_nonprincipal_cost_ceiling: Decimal | None = None
    counted_nonprincipal_cost_at_contract_lock: Decimal | None = None

    @property
    def ready(self) -> bool:
        return (
            self.applicability_review_ready
            and self.pricing_cap_review_ready
            and self.disclosure_ready
            and self.total_cost_cap_review_ready
        )

    @property
    def penalty_authority_ready(self) -> bool:
        return (
            self.ready
            and bool((self.penalty_policy_version or "").strip())
            and self.penalty_monthly_rate == Decimal("0.030000")
            and self.penalty_proration_days == 30
            and self.penalty_rate_ceiling is not None
            and self.penalty_rate_ceiling > Decimal("0")
            and self.lifetime_nonprincipal_cost_ceiling is not None
            and self.lifetime_nonprincipal_cost_ceiling >= Decimal("0")
            and self.counted_nonprincipal_cost_at_contract_lock is not None
            and self.counted_nonprincipal_cost_at_contract_lock >= Decimal("0")
            and self.counted_nonprincipal_cost_at_contract_lock
            <= self.lifetime_nonprincipal_cost_ceiling
        )


@dataclass(frozen=True, slots=True)
class VerifiedContractScheduleRegistration:
    schedule_id: UUID
    loan_id: UUID
    schedule_version: int
    status: str
    payment_frequency: str
    contract_reference: str
    contract_signed_date: date
    effective_from: date
    grace_days: int
    installment_count: int
    contractual_total: Decimal
    first_due_date: date
    last_due_date: date
    evidence_basis: str
    evidence_reference: str
    verification_note: str
    verified_by_user_id: UUID
    verified_at: datetime
    dpd_data_status: str
    days_past_due: int | None
    automatic_default_label_written: bool
    ecl_included: bool
    ecl_amount: Decimal | None
    ready_to_post: bool


class ContractScheduleRegistrationError(RuntimeError):
    code = "contract_schedule_registration_error"


class ContractScheduleRegistrationNotFound(ContractScheduleRegistrationError):
    code = "contract_schedule_registration_not_found"


class ContractScheduleRegistrationConflict(ContractScheduleRegistrationError):
    code = "contract_schedule_registration_conflict"


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def build_7x7_penalty_policy_schedule_settings(
    *,
    review: SevenBySevenPricingComplianceReview,
) -> dict[str, object]:
    """Freeze exact reviewed penalty authority into immutable signed schedule settings."""

    if not review.penalty_authority_ready:
        raise ContractScheduleRegistrationConflict(
            "The latest exact-term 7x7 review has no complete signed penalty authority."
        )
    assert review.penalty_policy_version is not None
    assert review.penalty_monthly_rate is not None
    assert review.penalty_proration_days is not None
    assert review.penalty_rate_ceiling is not None
    assert review.lifetime_nonprincipal_cost_ceiling is not None
    assert review.counted_nonprincipal_cost_at_contract_lock is not None
    return {
        "seven_by_seven_penalty_policy": {
            "policy_version": review.penalty_policy_version.strip(),
            "review_id": review.id,
            "terms_fingerprint": review.terms_fingerprint,
            "contractual_monthly_rate": _decimal_text(review.penalty_monthly_rate),
            "proration_days": review.penalty_proration_days,
            "legal_rate_ceiling": _decimal_text(review.penalty_rate_ceiling),
            "lifetime_nonprincipal_cost_ceiling": _decimal_text(
                review.lifetime_nonprincipal_cost_ceiling
            ),
            "counted_nonprincipal_cost_at_contract_lock": _decimal_text(
                review.counted_nonprincipal_cost_at_contract_lock
            ),
        }
    }


def build_7x7_pricing_compliance_terms_fingerprint(
    *,
    context: ContractScheduleLoanContext,
    payment_frequency: PaymentFrequency,
    contract_reference: str,
    contract_signed_date: date,
    effective_from: date,
    grace_days: int,
    agreed_daily_payment: Decimal,
    installments: Sequence[VerifiedScheduleInstallment],
) -> str:
    rows: list[dict[str, object]] = []
    for installment in installments:
        principal_component = getattr(installment, "principal_component", None)
        interest_component = getattr(installment, "interest_component", None)
        rows.append(
            {
                "installment_number": installment.installment_number,
                "due_date": installment.due_date.isoformat(),
                "contractual_amount": _decimal_text(installment.contractual_amount),
                "principal_component": (
                    _decimal_text(principal_component)
                    if principal_component is not None
                    else None
                ),
                "interest_component": (
                    _decimal_text(interest_component)
                    if interest_component is not None
                    else None
                ),
            }
        )
    payload = {
        "loan_id": str(context.loan_id),
        "principal": _decimal_text(context.principal),
        "daily_interest_per_1000": _decimal_text(context.daily_interest_per_1000),
        "payment_frequency": payment_frequency,
        "contract_reference": contract_reference,
        "contract_signed_date": contract_signed_date.isoformat(),
        "effective_from": effective_from.isoformat(),
        "grace_days": grace_days,
        "agreed_daily_payment": _decimal_text(agreed_daily_payment),
        "installments": rows,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class PostgresContractScheduleRegistrationRepository:
    def load_loan_context(self, *, loan_id: UUID) -> ContractScheduleLoanContext:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        loan.id as loan_id,
                        loan.loan_number,
                        client.client_code,
                        client.full_name as client_name,
                        loan_type.name as loan_type_name,
                        loan_type.calculation_mode,
                        coalesce(loan_type.daily_interest_per_1000, 0)::numeric(18,2)
                            as daily_interest_per_1000,
                        loan.principal,
                        loan.daily_amount,
                        loan.date_released,
                        loan.due_date,
                        loan.status as loan_status,
                        schedule.id as active_schedule_id,
                        schedule.schedule_version as active_schedule_version,
                        schedule.payment_frequency as active_payment_frequency,
                        schedule.contract_reference as active_contract_reference
                    from lending.loans loan
                    join lending.clients client
                      on client.id = loan.client_id
                    join lending.loan_types loan_type
                      on loan_type.id = loan.loan_type_id
                    left join lending.loan_contract_schedules schedule
                      on schedule.loan_id = loan.id
                     and schedule.status = 'active'
                    where loan.id = %s
                    """,
                    (loan_id,),
                )
                row = cursor.fetchone()
        if row is None:
            raise ContractScheduleRegistrationNotFound("The loan does not exist.")
        return ContractScheduleLoanContext(**row)

    def record_7x7_pricing_compliance_review(
        self,
        *,
        loan_id: UUID,
        terms_fingerprint: str,
        applicability_review_ready: bool,
        pricing_cap_review_ready: bool,
        disclosure_ready: bool,
        total_cost_cap_review_ready: bool,
        evidence_reference: str,
        review_note: str,
        reviewed_by_user_id: UUID,
        penalty_policy_version: str | None = None,
        penalty_monthly_rate: Decimal | None = None,
        penalty_proration_days: int | None = None,
        penalty_rate_ceiling: Decimal | None = None,
        lifetime_nonprincipal_cost_ceiling: Decimal | None = None,
        counted_nonprincipal_cost_at_contract_lock: Decimal | None = None,
    ) -> SevenBySevenPricingComplianceReview:
        normalized_fingerprint = terms_fingerprint.strip().lower()
        normalized_reference = " ".join(evidence_reference.split())
        normalized_note = " ".join(review_note.split())
        if len(normalized_fingerprint) != 64 or any(
            char not in "0123456789abcdef" for char in normalized_fingerprint
        ):
            raise ContractScheduleRegistrationConflict(
                "The exact 7x7 pricing/compliance terms fingerprint is invalid."
            )
        if not normalized_reference or not normalized_note:
            raise ContractScheduleRegistrationConflict(
                "Pricing/compliance review evidence reference and note are required."
            )

        normalized_policy_version = (
            " ".join(penalty_policy_version.split())
            if penalty_policy_version is not None
            else None
        )
        penalty_values = (
            normalized_policy_version,
            penalty_monthly_rate,
            penalty_proration_days,
            penalty_rate_ceiling,
            lifetime_nonprincipal_cost_ceiling,
            counted_nonprincipal_cost_at_contract_lock,
        )
        has_any_penalty_authority = any(value is not None for value in penalty_values)
        has_all_penalty_authority = all(value is not None for value in penalty_values)
        if has_any_penalty_authority and not has_all_penalty_authority:
            raise ContractScheduleRegistrationConflict(
                "The exact 7x7 penalty authority must be supplied as one complete reviewed tuple."
            )
        if has_all_penalty_authority:
            assert normalized_policy_version is not None
            assert penalty_monthly_rate is not None
            assert penalty_proration_days is not None
            assert penalty_rate_ceiling is not None
            assert lifetime_nonprincipal_cost_ceiling is not None
            assert counted_nonprincipal_cost_at_contract_lock is not None
            if not normalized_policy_version:
                raise ContractScheduleRegistrationConflict(
                    "The exact 7x7 penalty policy version cannot be blank."
                )
            if penalty_monthly_rate != Decimal("0.030000"):
                raise ContractScheduleRegistrationConflict(
                    "The approved 7x7 contractual penalty rate is 3% per month."
                )
            if penalty_proration_days != 30:
                raise ContractScheduleRegistrationConflict(
                    "The approved 7x7 penalty proration basis is a fixed 30-day month."
                )
            if penalty_rate_ceiling <= Decimal("0"):
                raise ContractScheduleRegistrationConflict(
                    "The exact terms-bound legal penalty-rate ceiling must be greater than zero."
                )
            if lifetime_nonprincipal_cost_ceiling < Decimal("0"):
                raise ContractScheduleRegistrationConflict(
                    "The lifetime non-principal cost ceiling cannot be negative."
                )
            if counted_nonprincipal_cost_at_contract_lock < Decimal("0"):
                raise ContractScheduleRegistrationConflict(
                    "Counted non-principal cost at contract lock cannot be negative."
                )
            if (
                counted_nonprincipal_cost_at_contract_lock
                > lifetime_nonprincipal_cost_ceiling
            ):
                raise ContractScheduleRegistrationConflict(
                    "Counted non-principal cost at contract lock cannot exceed the lifetime ceiling."
                )

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                row = cursor.execute(
                    """
                    insert into lending.seven_by_seven_pricing_compliance_reviews (
                        loan_id,
                        terms_fingerprint,
                        applicability_review_ready,
                        pricing_cap_review_ready,
                        disclosure_ready,
                        total_cost_cap_review_ready,
                        evidence_reference,
                        review_note,
                        reviewed_by_user_id,
                        penalty_policy_version,
                        penalty_monthly_rate,
                        penalty_proration_days,
                        penalty_rate_ceiling,
                        lifetime_nonprincipal_cost_ceiling,
                        counted_nonprincipal_cost_at_contract_lock
                    ) values (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s
                    )
                    returning *
                    """,
                    (
                        loan_id,
                        normalized_fingerprint,
                        applicability_review_ready,
                        pricing_cap_review_ready,
                        disclosure_ready,
                        total_cost_cap_review_ready,
                        normalized_reference,
                        normalized_note,
                        reviewed_by_user_id,
                        normalized_policy_version,
                        penalty_monthly_rate,
                        penalty_proration_days,
                        penalty_rate_ceiling,
                        lifetime_nonprincipal_cost_ceiling,
                        counted_nonprincipal_cost_at_contract_lock,
                    ),
                ).fetchone()
        if row is None:
            raise ContractScheduleRegistrationConflict(
                "7x7 pricing/compliance review evidence could not be reloaded."
            )
        return SevenBySevenPricingComplianceReview(**row)

    def require_7x7_pricing_compliance_ready(
        self,
        *,
        loan_id: UUID,
        terms_fingerprint: str,
    ) -> SevenBySevenPricingComplianceReview:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                row = cursor.execute(
                    """
                    select *
                    from lending.seven_by_seven_pricing_compliance_reviews
                    where loan_id = %s
                      and terms_fingerprint = %s
                    order by reviewed_at desc, id desc
                    limit 1
                    """,
                    (loan_id, terms_fingerprint.strip().lower()),
                ).fetchone()
        if row is None:
            raise ContractScheduleRegistrationConflict(
                "The exact proposed 7x7 terms have no pricing/compliance readiness review."
            )
        review = SevenBySevenPricingComplianceReview(**row)
        if not review.ready:
            raise ContractScheduleRegistrationConflict(
                "The latest exact-term 7x7 pricing/compliance review is not fully ready for contract lock."
            )
        return review

    def register_schedule(
        self,
        *,
        loan_id: UUID,
        payment_frequency: PaymentFrequency,
        contract_reference: str,
        contract_signed_date: date,
        effective_from: date,
        grace_days: int,
        installments: Sequence[VerifiedScheduleInstallment],
        evidence_basis: ContractEvidenceBasis,
        evidence_reference: str,
        verification_note: str,
        verified_by_user_id: UUID,
        confirmed: bool,
        supersede_active: bool,
        agreed_daily_payment: Decimal | None = None,
        schedule_settings: dict[str, object] | None = None,
    ) -> VerifiedContractScheduleRegistration:
        try:
            with open_connection() as connection:
                with connection.cursor() as cursor:
                    schedule_id = register_verified_contract_schedule(
                        cursor,
                        loan_id=loan_id,
                        payment_frequency=payment_frequency,
                        contract_reference=contract_reference,
                        contract_signed_date=contract_signed_date,
                        effective_from=effective_from,
                        grace_days=grace_days,
                        installments=installments,
                        evidence_basis=evidence_basis,
                        evidence_reference=evidence_reference,
                        verification_note=verification_note,
                        verified_by_user_id=verified_by_user_id,
                        agreed_daily_payment=agreed_daily_payment,
                        schedule_settings=schedule_settings,
                        confirmed=confirmed,
                        supersede_active=supersede_active,
                    )
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        select
                            schedule.id as schedule_id,
                            schedule.loan_id,
                            schedule.schedule_version,
                            schedule.status,
                            schedule.payment_frequency,
                            schedule.contract_reference,
                            schedule.contract_signed_date,
                            schedule.effective_from,
                            schedule.grace_days,
                            (
                                select count(*)::integer
                                from lending.loan_contract_installments installment
                                where installment.schedule_id = schedule.id
                            ) as installment_count,
                            (
                                select coalesce(sum(installment.contractual_amount), 0)::numeric(18,2)
                                from lending.loan_contract_installments installment
                                where installment.schedule_id = schedule.id
                            ) as contractual_total,
                            (
                                select min(installment.due_date)
                                from lending.loan_contract_installments installment
                                where installment.schedule_id = schedule.id
                            ) as first_due_date,
                            (
                                select max(installment.due_date)
                                from lending.loan_contract_installments installment
                                where installment.schedule_id = schedule.id
                            ) as last_due_date,
                            registration.evidence_basis,
                            registration.evidence_reference,
                            registration.verification_note,
                            registration.verified_by_user_id,
                            registration.verified_at,
                            assessment.dpd_data_status,
                            assessment.days_past_due,
                            assessment.automatic_default_label_written,
                            assessment.ecl_included,
                            assessment.ecl_amount,
                            assessment.ready_to_post
                        from lending.loan_contract_schedules schedule
                        join lending.loan_contract_schedule_registrations registration
                          on registration.schedule_id = schedule.id
                        join accounting.loan_contract_dpd_assessment assessment
                          on assessment.loan_id = schedule.loan_id
                        where schedule.id = %s
                        """,
                        (schedule_id,),
                    )
                    row = cursor.fetchone()
                if row is None:
                    raise ContractScheduleRegistrationConflict(
                        "Verified schedule registration could not be reloaded."
                    )
                return VerifiedContractScheduleRegistration(**row)
        except ContractScheduleNotReady as exc:
            raise ContractScheduleRegistrationNotFound(str(exc)) from exc
        except ContractScheduleConflict as exc:
            raise ContractScheduleRegistrationConflict(str(exc)) from exc
