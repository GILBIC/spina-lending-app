from __future__ import annotations

from datetime import date
from typing import Any, Literal, Sequence
from uuid import UUID

from .contract_schedule_engine import ContractInstallment, PaymentFrequency
from .contract_schedule_service import ContractScheduleConflict, store_contract_schedule
from .seven_by_seven_signed_schedule import SevenBySevenSignedInstallment


ContractEvidenceBasis = Literal[
    "signed_contract",
    "signed_renewal_contract",
    "signed_restructure_contract",
]

_ALLOWED_EVIDENCE_BASES = {
    "signed_contract",
    "signed_renewal_contract",
    "signed_restructure_contract",
}


VerifiedScheduleInstallment = ContractInstallment | SevenBySevenSignedInstallment


def register_verified_contract_schedule(
    cursor: Any,
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
    supersede_active: bool = False,
) -> UUID:
    """Register one explicitly verified signed-contract schedule.

    This function intentionally requires a human confirmation and documentary
    evidence reference. It never derives terms from legacy SPINA defaults. A
    schedule that already has installment allocations cannot be superseded by
    this stage because those historical allocations must first be reconciled by
    a dedicated restructure workflow.

    Component-bearing schedule rows (currently the signed 7x7 model) are stored
    with principal/interest components on the initial immutable installment-row
    insert. They are never initialized by a follow-up UPDATE.
    """

    if not confirmed:
        raise ContractScheduleConflict(
            "Explicit confirmation is required before registering a verified contract schedule."
        )

    normalized_basis = str(evidence_basis).strip().lower()
    if normalized_basis not in _ALLOWED_EVIDENCE_BASES:
        raise ContractScheduleConflict("Unsupported signed-contract evidence basis.")

    normalized_reference = evidence_reference.strip()
    normalized_note = " ".join(verification_note.split())
    if not normalized_reference:
        raise ContractScheduleConflict("Signed-contract evidence reference is required.")
    if not normalized_note:
        raise ContractScheduleConflict("Contract verification note is required.")

    for installment in installments:
        principal_component = getattr(installment, "principal_component", None)
        interest_component = getattr(installment, "interest_component", None)
        if (principal_component is None) != (interest_component is None):
            raise ContractScheduleConflict(
                "Contractual principal and interest components must be supplied together."
            )

    if supersede_active:
        cursor.execute(
            """
            select schedule.id
            from lending.loan_contract_schedules schedule
            where schedule.loan_id = %s
              and schedule.status = 'active'
            for update
            """,
            (loan_id,),
        )
        active = cursor.fetchone()
        if active is not None:
            active_schedule_id = active[0]
            cursor.execute(
                """
                select count(*)
                from lending.loan_contract_installments installment
                join lending.loan_installment_payment_allocations allocation
                  on allocation.installment_id = installment.id
                where installment.schedule_id = %s
                """,
                (active_schedule_id,),
            )
            allocation_count = int(cursor.fetchone()[0])
            if allocation_count > 0:
                raise ContractScheduleConflict(
                    "The active schedule already has payment allocations. "
                    "Use the controlled restructure/reallocation workflow before superseding it."
                )

    schedule_id = store_contract_schedule(
        cursor,
        loan_id=loan_id,
        payment_frequency=payment_frequency,
        contract_reference=contract_reference,
        contract_signed_date=contract_signed_date,
        effective_from=effective_from,
        grace_days=grace_days,
        installments=installments,  # type: ignore[arg-type]
        created_by_user_id=verified_by_user_id,
        supersede_active=supersede_active,
    )

    cursor.execute(
        """
        insert into lending.loan_contract_schedule_registrations (
            schedule_id,
            evidence_basis,
            evidence_reference,
            verification_note,
            verified_by_user_id
        )
        values (%s, %s, %s, %s, %s)
        """,
        (
            schedule_id,
            normalized_basis,
            normalized_reference,
            normalized_note,
            verified_by_user_id,
        ),
    )
    return schedule_id