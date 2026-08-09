from __future__ import annotations

from decimal import Decimal
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from spina_mobile_collections.contracts import CollectionCommand
from spina_mobile_collections.service import CollectionRejected

from .contract_collection_posting import (
    ContractAwareCrossCollectorCollectionPostingBridge,
    ContractCollectionGate,
)


class PerLoanContractAwareCrossCollectorCollectionPostingBridge(
    ContractAwareCrossCollectorCollectionPostingBridge
):
    """Use Stage 5E.4.6A immutable per-loan activation as the only live switch.

    A loan with no activation history stays on the existing official collection
    path. Once Management has explicitly activated contractual collection, a later
    deactivation blocks mobile collection instead of silently reverting the loan to
    legacy date-based handling. Active loans must still pass every signed-contract,
    DPD-readiness, balance-reconciliation, operational-mode, and accounting guard.
    """

    def _load_contract_gate(
        self,
        connection: Connection[Any],
        *,
        command: CollectionCommand,
    ) -> ContractCollectionGate | None:
        loan_id = self._uuid(command.loan_id, "loan")
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                select
                    coalesce(activation.event_action, '') as activation_action,
                    activation.schedule_id as activation_schedule_id,
                    lower(coalesce(loan_type.settings->>'mobile_collections_enabled', ''))
                        in ('true', '1', 'yes', 'on') as mobile_collections_enabled,
                    coalesce(loan_type.settings->>'mobile_balance_mode', '')
                        as mobile_balance_mode,
                    coalesce(state.remaining_balance, loan.principal)::numeric(18,2)
                        as remaining_balance,
                    assessment.schedule_id,
                    assessment.schedule_version,
                    assessment.payment_frequency,
                    assessment.contract_reference,
                    assessment.dpd_data_status,
                    assessment.contractual_schedule_total,
                    assessment.allocated_schedule_total,
                    assessment.automatic_default_label_written,
                    assessment.ecl_included,
                    assessment.ecl_amount,
                    assessment.ready_to_post,
                    registration.id as registration_id
                from lending.loans loan
                join lending.loan_types loan_type
                  on loan_type.id = loan.loan_type_id
                left join lending.loan_collection_state state
                  on state.loan_id = loan.id
                left join accounting.loan_contract_dpd_assessment assessment
                  on assessment.loan_id = loan.id
                left join lending.loan_contract_schedule_registrations registration
                  on registration.schedule_id = assessment.schedule_id
                left join lending.loan_contract_collection_activation_state activation
                  on activation.loan_id = loan.id
                where loan.id = %s
                """,
                (loan_id,),
            )
            row = cursor.fetchone()

        # No activation history means the loan remains on the established official path.
        if row is None or not str(row["activation_action"] or ""):
            return None
        if str(row["activation_action"]) == "deactivate":
            raise CollectionRejected(
                "Contractual mobile collection is deactivated for this loan. "
                "Management must reactivate it before another mobile collection is saved.",
                code="contract_collection_deactivated",
            )
        if str(row["activation_action"]) != "activate":
            raise CollectionRejected(
                "This loan has an unknown contractual collection activation state.",
                code="contract_activation_state_invalid",
            )

        if not bool(row["mobile_collections_enabled"]):
            raise CollectionRejected(
                "This loan was activated for contractual collection, but mobile "
                "collections are no longer enabled for its loan type.",
                code="contract_activation_operational_mode_changed",
            )
        if str(row["mobile_balance_mode"] or "") != "direct_remaining_balance":
            raise CollectionRejected(
                "This loan was activated for contractual collection, but its balance "
                "mode is no longer compatible. Ask Management to review it.",
                code="contract_activation_operational_mode_changed",
            )
        if row["schedule_id"] is None or row["registration_id"] is None:
            raise CollectionRejected(
                "This activated loan no longer has a verified active signed-contract "
                "schedule. Ask Management to review it.",
                code="contract_schedule_not_verified",
            )
        if row["activation_schedule_id"] != row["schedule_id"]:
            raise CollectionRejected(
                "The loan activation belongs to an older contractual schedule. "
                "Management must deactivate it and review the current schedule.",
                code="contract_activation_schedule_changed",
            )
        if str(row["dpd_data_status"]) != "ready":
            raise CollectionRejected(
                "This activated loan's contractual schedule is no longer ready for "
                "automatic payment allocation. Ask Management to reconcile it.",
                code="contract_schedule_allocation_not_ready",
            )
        if (
            bool(row["automatic_default_label_written"])
            or bool(row["ecl_included"])
            or row["ecl_amount"] is not None
            or bool(row["ready_to_post"])
        ):
            raise CollectionRejected(
                "The contractual collection gate detected an unsafe accounting state.",
                code="contract_schedule_accounting_guard",
            )

        remaining_balance = self._money(row["remaining_balance"])
        unpaid_contractual_amount = self._money(
            Decimal(row["contractual_schedule_total"])
            - Decimal(row["allocated_schedule_total"])
        )
        if remaining_balance != unpaid_contractual_amount:
            raise CollectionRejected(
                "The operational balance does not match the unpaid signed-contract "
                "schedule. Reconcile the loan before contractual collection continues.",
                code="contract_balance_not_reconciled",
            )

        return ContractCollectionGate(
            loan_id=loan_id,
            schedule_id=row["schedule_id"],
            schedule_version=int(row["schedule_version"]),
            payment_frequency=str(row["payment_frequency"]),
            contract_reference=str(row["contract_reference"]),
            remaining_balance=remaining_balance,
            unpaid_contractual_amount=unpaid_contractual_amount,
        )
