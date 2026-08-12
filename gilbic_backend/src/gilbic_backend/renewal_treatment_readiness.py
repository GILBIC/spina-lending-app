from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext
from uuid import UUID


MONEY = Decimal("0.01")
HUNDRED = Decimal("100")
POLICY_VERSION = "renewal_accounting_treatment_readiness_v1"


@dataclass(frozen=True, slots=True)
class RenewalTreatmentInstallment:
    installment_number: int
    due_date: date
    contractual_amount: Decimal


@dataclass(frozen=True, slots=True)
class RenewalTreatmentEvidence:
    renewal_execution_event_id: UUID
    old_loan_id: UUID
    new_loan_id: UUID
    client_id: UUID
    business_date: date
    execution_active: bool
    release_event_kind: str
    release_business_date: date
    release_active: bool
    cash_disbursed_amount: Decimal
    settlement_amount: Decimal
    other_deduction_amount: Decimal
    new_loan_calculation_mode: str
    accounting_carrying_amount_ready: bool
    old_gross_carrying_amount: Decimal | None
    original_daily_eir: Decimal | None
    schedule_id: UUID | None
    schedule_version: int | None
    schedule_status: str | None
    schedule_effective_from: date | None
    payment_frequency: str | None
    contract_reference: str | None
    contract_signed_date: date | None
    registration_id: UUID | None
    evidence_basis: str | None
    evidence_reference: str | None
    installments: tuple[RenewalTreatmentInstallment, ...]


@dataclass(frozen=True, slots=True)
class RenewalTreatmentReadiness:
    disposition: str
    blocker_code: str | None
    message: str
    policy_version: str
    old_gross_carrying_amount: Decimal | None
    original_daily_eir: Decimal | None
    renewal_cash_disbursed_amount: Decimal
    renewal_settlement_amount: Decimal
    renewal_other_deduction_amount: Decimal
    schedule_id: UUID | None
    schedule_version: int | None
    payment_frequency: str | None
    contract_reference: str | None
    contract_signed_date: date | None
    schedule_effective_from: date | None
    evidence_basis: str | None
    evidence_reference: str | None
    installment_count: int
    first_due_date: date | None
    last_due_date: date | None
    contractual_cash_total: Decimal | None
    present_value_at_original_eir: Decimal | None
    present_value_change_amount: Decimal | None
    present_value_change_percent: Decimal | None
    treatment_decision_required: bool
    automatic_classification_enabled: bool
    quantitative_threshold_decisive: bool
    journal_lines_enabled: bool
    automatic_source_posting: bool


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _blocked(
    evidence: RenewalTreatmentEvidence,
    *,
    code: str,
    message: str,
    contractual_cash_total: Decimal | None = None,
) -> RenewalTreatmentReadiness:
    installments = evidence.installments
    return RenewalTreatmentReadiness(
        disposition="renewal_accounting_treatment_review_blocked",
        blocker_code=code,
        message=message,
        policy_version=POLICY_VERSION,
        old_gross_carrying_amount=(
            None
            if evidence.old_gross_carrying_amount is None
            else _money(evidence.old_gross_carrying_amount)
        ),
        original_daily_eir=evidence.original_daily_eir,
        renewal_cash_disbursed_amount=_money(evidence.cash_disbursed_amount),
        renewal_settlement_amount=_money(evidence.settlement_amount),
        renewal_other_deduction_amount=_money(evidence.other_deduction_amount),
        schedule_id=evidence.schedule_id,
        schedule_version=evidence.schedule_version,
        payment_frequency=evidence.payment_frequency,
        contract_reference=evidence.contract_reference,
        contract_signed_date=evidence.contract_signed_date,
        schedule_effective_from=evidence.schedule_effective_from,
        evidence_basis=evidence.evidence_basis,
        evidence_reference=evidence.evidence_reference,
        installment_count=len(installments),
        first_due_date=min((item.due_date for item in installments), default=None),
        last_due_date=max((item.due_date for item in installments), default=None),
        contractual_cash_total=(
            None if contractual_cash_total is None else _money(contractual_cash_total)
        ),
        present_value_at_original_eir=None,
        present_value_change_amount=None,
        present_value_change_percent=None,
        treatment_decision_required=True,
        automatic_classification_enabled=False,
        quantitative_threshold_decisive=False,
        journal_lines_enabled=False,
        automatic_source_posting=False,
    )


def build_renewal_treatment_readiness(
    evidence: RenewalTreatmentEvidence,
) -> RenewalTreatmentReadiness:
    if (
        not evidence.accounting_carrying_amount_ready
        or evidence.old_gross_carrying_amount is None
        or evidence.old_gross_carrying_amount <= 0
    ):
        return _blocked(
            evidence,
            code="authoritative_old_carrying_amount_required",
            message=(
                "Protected old-loan accounting must reconcile to an authoritative "
                "renewal-date carrying amount before renewal treatment can be reviewed."
            ),
        )

    if evidence.original_daily_eir is None or evidence.original_daily_eir <= 0:
        return _blocked(
            evidence,
            code="original_eir_required",
            message=(
                "The protected original effective interest rate is required before "
                "modified contractual cash flows can be measured."
            ),
        )

    if not evidence.execution_active:
        return _blocked(
            evidence,
            code="renewal_execution_evidence_not_active",
            message="Active authoritative renewal execution evidence is required.",
        )

    if (
        not evidence.release_active
        or evidence.release_event_kind != "renewal_release"
        or evidence.release_business_date != evidence.business_date
    ):
        return _blocked(
            evidence,
            code="renewal_release_evidence_mismatch",
            message=(
                "The linked renewal release must be active and must match the "
                "authoritative renewal execution business date."
            ),
        )

    if evidence.new_loan_calculation_mode != "fixed_daily":
        return _blocked(
            evidence,
            code="regular_fixed_daily_new_loan_required",
            message=(
                "This treatment-readiness path currently supports only the verified "
                "Regular fixed-daily renewal flow."
            ),
        )

    if evidence.other_deduction_amount != 0:
        return _blocked(
            evidence,
            code="renewal_deductions_require_policy_review",
            message=(
                "Renewal deductions require separate accounting-policy evidence before "
                "modification or derecognition treatment can be assessed."
            ),
        )

    if (
        evidence.schedule_id is None
        or evidence.schedule_version is None
        or evidence.schedule_status != "active"
        or evidence.registration_id is None
    ):
        return _blocked(
            evidence,
            code="verified_renewal_contract_schedule_required",
            message=(
                "Exactly one active verified contractual schedule for the new renewal "
                "loan is required."
            ),
        )

    if evidence.evidence_basis != "signed_renewal_contract":
        return _blocked(
            evidence,
            code="signed_renewal_contract_evidence_required",
            message=(
                "The active renewal schedule must be registered from signed renewal "
                "contract evidence."
            ),
        )

    if evidence.schedule_effective_from != evidence.business_date:
        return _blocked(
            evidence,
            code="renewal_schedule_effective_date_mismatch",
            message=(
                "The verified renewal schedule effective date must match the renewal "
                "execution business date."
            ),
        )

    if (
        evidence.contract_signed_date is None
        or evidence.contract_signed_date > evidence.business_date
    ):
        return _blocked(
            evidence,
            code="renewal_contract_signature_date_invalid",
            message=(
                "Signed renewal-contract evidence must exist no later than the renewal "
                "execution business date."
            ),
        )

    if not evidence.installments:
        return _blocked(
            evidence,
            code="renewal_contract_installments_required",
            message="Verified future renewal contractual cash flows are required.",
        )

    if any(item.due_date <= evidence.business_date for item in evidence.installments):
        return _blocked(
            evidence,
            code="renewal_contract_cash_flow_ordering_invalid",
            message=(
                "All renewal contractual cash flows used for treatment review must fall "
                "strictly after the renewal execution business date."
            ),
        )

    if any(item.contractual_amount <= 0 for item in evidence.installments):
        return _blocked(
            evidence,
            code="renewal_contract_cash_flow_amount_invalid",
            message="Every verified renewal contractual installment must be positive.",
        )

    contractual_total = sum(
        (item.contractual_amount for item in evidence.installments), Decimal("0")
    )
    if contractual_total <= 0:
        return _blocked(
            evidence,
            code="renewal_contract_cash_flow_amount_invalid",
            message="Verified renewal contractual cash flows must have a positive total.",
        )

    original_rate = evidence.original_daily_eir
    carrying = evidence.old_gross_carrying_amount
    with localcontext() as context:
        context.prec = 42
        present_value = Decimal("0")
        for item in sorted(
            evidence.installments,
            key=lambda installment: (installment.due_date, installment.installment_number),
        ):
            day_count = item.due_date - evidence.business_date
            present_value += item.contractual_amount / (
                (Decimal("1") + original_rate) ** day_count.days
            )

    present_value = _money(present_value)
    carrying = _money(carrying)
    change_amount = _money(present_value - carrying)
    change_percent = (
        (abs(present_value - carrying) / carrying) * HUNDRED
    ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return RenewalTreatmentReadiness(
        disposition="renewal_accounting_treatment_review_ready",
        blocker_code=None,
        message=(
            "Evidence is ready for an explicit accounting-policy decision between "
            "modification without derecognition and derecognition/new-asset recognition. "
            "No quantitative threshold automatically decides the treatment."
        ),
        policy_version=POLICY_VERSION,
        old_gross_carrying_amount=carrying,
        original_daily_eir=original_rate,
        renewal_cash_disbursed_amount=_money(evidence.cash_disbursed_amount),
        renewal_settlement_amount=_money(evidence.settlement_amount),
        renewal_other_deduction_amount=_money(evidence.other_deduction_amount),
        schedule_id=evidence.schedule_id,
        schedule_version=evidence.schedule_version,
        payment_frequency=evidence.payment_frequency,
        contract_reference=evidence.contract_reference,
        contract_signed_date=evidence.contract_signed_date,
        schedule_effective_from=evidence.schedule_effective_from,
        evidence_basis=evidence.evidence_basis,
        evidence_reference=evidence.evidence_reference,
        installment_count=len(evidence.installments),
        first_due_date=min(item.due_date for item in evidence.installments),
        last_due_date=max(item.due_date for item in evidence.installments),
        contractual_cash_total=_money(contractual_total),
        present_value_at_original_eir=present_value,
        present_value_change_amount=change_amount,
        present_value_change_percent=change_percent,
        treatment_decision_required=True,
        automatic_classification_enabled=False,
        quantitative_threshold_decisive=False,
        journal_lines_enabled=False,
        automatic_source_posting=False,
    )
