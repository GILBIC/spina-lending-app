from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from .renewal_treatment_accounting_target import (
    RenewalTreatmentAccountingEvidence,
    RenewalTreatmentAccountingTarget,
    build_renewal_treatment_accounting_target,
)
from .renewal_treatment_decision_repository import (
    PostgresRenewalTreatmentDecisionRepository,
    RenewalTreatmentDecisionError,
    RenewalTreatmentDecisionRecord,
)


@dataclass(frozen=True, slots=True)
class RenewalTreatmentAccountingTargetRecord:
    decision: RenewalTreatmentDecisionRecord
    target: RenewalTreatmentAccountingTarget


class RenewalTreatmentAccountingTargetError(RuntimeError):
    code = "renewal_treatment_accounting_target_error"


class RenewalTreatmentAccountingTargetNotFound(RenewalTreatmentAccountingTargetError):
    code = "renewal_treatment_accounting_target_not_found"


class RenewalTreatmentAccountingTargetConflict(RenewalTreatmentAccountingTargetError):
    code = "renewal_treatment_accounting_target_conflict"


class PostgresRenewalTreatmentAccountingTargetRepository:
    def __init__(
        self,
        *,
        decision_repository: PostgresRenewalTreatmentDecisionRepository | None = None,
    ) -> None:
        self._decision_repository = (
            decision_repository or PostgresRenewalTreatmentDecisionRepository()
        )

    def load(
        self,
        *,
        renewal_execution_event_id: UUID,
    ) -> RenewalTreatmentAccountingTargetRecord:
        try:
            decisions = self._decision_repository.get_for_execution(
                renewal_execution_event_id=renewal_execution_event_id,
                active_only=True,
            )
        except RenewalTreatmentDecisionError as error:
            raise RenewalTreatmentAccountingTargetConflict(str(error)) from error

        if not decisions:
            raise RenewalTreatmentAccountingTargetNotFound(
                "No active reviewed renewal treatment decision was found for this renewal execution."
            )
        if len(decisions) != 1:
            raise RenewalTreatmentAccountingTargetConflict(
                "Exactly one active reviewed renewal treatment decision is required."
            )

        decision = decisions[0]
        evidence = RenewalTreatmentAccountingEvidence(
            decision_id=decision.decision_id,
            renewal_execution_event_id=decision.renewal_execution_event_id,
            old_loan_id=decision.old_loan_id,
            new_loan_id=decision.new_loan_id,
            client_id=decision.client_id,
            decision=decision.decision,
            decision_active=decision.is_active,
            old_gross_carrying_amount=decision.old_gross_carrying_amount,
            original_daily_eir=decision.original_daily_eir,
            present_value_at_original_eir=decision.present_value_at_original_eir,
            present_value_change_amount=decision.present_value_change_amount,
        )
        return RenewalTreatmentAccountingTargetRecord(
            decision=decision,
            target=build_renewal_treatment_accounting_target(evidence),
        )
