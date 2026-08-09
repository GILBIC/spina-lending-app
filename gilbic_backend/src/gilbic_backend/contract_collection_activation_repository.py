from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Literal
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection


MONEY = Decimal("0.01")
ActivationAction = Literal["activate", "deactivate"]


class ContractCollectionActivationError(RuntimeError):
    code = "contract_collection_activation_error"


class ContractCollectionActivationNotFound(ContractCollectionActivationError):
    code = "contract_collection_activation_loan_not_found"


class ContractCollectionActivationConflict(ContractCollectionActivationError):
    code = "contract_collection_activation_conflict"


@dataclass(frozen=True, slots=True)
class ContractCollectionActivationPreview:
    loan_id: UUID
    loan_number: str
    client_name: str
    loan_type_name: str
    loan_status: str
    remaining_balance: Decimal
    mobile_collections_enabled: bool
    mobile_balance_mode: str
    schedule_id: UUID | None
    schedule_version: int | None
    payment_frequency: str
    contract_reference: str
    dpd_data_status: str
    contractual_schedule_total: Decimal
    allocated_schedule_total: Decimal
    registration_id: int | None
    automatic_default_label_written: bool
    ecl_included: bool
    ecl_amount: Decimal | None
    ready_to_post: bool
    activation_event_id: int | None
    activation_action: str
    activation_schedule_id: UUID | None
    activation_note: str
    activated_by_user_id: UUID | None
    activation_acted_at: datetime | None

    @property
    def unpaid_contractual_amount(self) -> Decimal:
        return _money(self.contractual_schedule_total - self.allocated_schedule_total)

    @property
    def schedule_verified(self) -> bool:
        return self.schedule_id is not None and self.registration_id is not None

    @property
    def accounting_safe(self) -> bool:
        return not (
            self.automatic_default_label_written
            or self.ecl_included
            or self.ecl_amount is not None
            or self.ready_to_post
        )

    @property
    def balance_reconciled(self) -> bool:
        return (
            self.dpd_data_status == "ready"
            and self.remaining_balance == self.unpaid_contractual_amount
        )

    @property
    def is_active(self) -> bool:
        return self.activation_action == "activate"

    @property
    def active_for_current_schedule(self) -> bool:
        return (
            self.is_active
            and self.schedule_id is not None
            and self.activation_schedule_id == self.schedule_id
        )

    @property
    def blockers(self) -> tuple[str, ...]:
        values: list[str] = []
        if self.loan_status != "active":
            values.append("Loan is not active.")
        if not self.mobile_collections_enabled:
            values.append("Mobile collections are disabled for this loan type.")
        if self.mobile_balance_mode != "direct_remaining_balance":
            values.append("Loan type is not using direct remaining-balance collection mode.")
        if self.schedule_id is None:
            values.append("Signed-contract schedule has not been registered.")
        elif self.registration_id is None:
            values.append("Current schedule is not backed by verified signed-contract evidence.")
        if self.dpd_data_status != "ready":
            values.append(
                "Contract schedule/payment allocation is not DPD-ready "
                f"({self.dpd_data_status})."
            )
        if self.schedule_verified and not self.balance_reconciled:
            values.append(
                "Operational remaining balance does not match the unpaid contractual schedule."
            )
        if not self.accounting_safe:
            values.append("Protected Default/ECL/posting state is not safe for activation.")
        if self.is_active and not self.active_for_current_schedule:
            values.append(
                "An older schedule is still marked active; deactivate it before activating the current schedule."
            )
        return tuple(values)

    @property
    def can_activate(self) -> bool:
        return not self.is_active and not self.blockers

    @property
    def can_deactivate(self) -> bool:
        return self.is_active


class PostgresContractCollectionActivationRepository:
    """Management-only explicit activation around verified contractual collection.

    The repository never creates schedules, allocates payments, changes balances,
    classifies Default/ECL, or posts journals. It only appends immutable activation
    events after rechecking the current protected readiness state in one transaction.
    """

    def list_previews(self) -> tuple[ContractCollectionActivationPreview, ...]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(self._preview_sql() + " order by lower(client.full_name), loan.loan_number")
                return tuple(self._preview_from_row(row) for row in cursor.fetchall())

    def get_preview(self, *, loan_id: UUID) -> ContractCollectionActivationPreview:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                return self._load_preview_cursor(cursor, loan_id=loan_id)

    def activate(
        self,
        *,
        loan_id: UUID,
        acted_by_user_id: UUID,
        activation_note: str,
    ) -> ContractCollectionActivationPreview:
        note = _clean_note(activation_note)
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                self._lock_loan(cursor, loan_id=loan_id)
                preview = self._load_preview_cursor(cursor, loan_id=loan_id)
                if preview.is_active:
                    raise ContractCollectionActivationConflict(
                        "This loan already has an active contractual collection event."
                    )
                if preview.blockers:
                    raise ContractCollectionActivationConflict(" ".join(preview.blockers))
                if preview.schedule_id is None:
                    raise ContractCollectionActivationConflict(
                        "A verified current schedule is required before activation."
                    )
                cursor.execute(
                    """
                    insert into lending.loan_contract_collection_activation_events (
                        loan_id,
                        schedule_id,
                        event_action,
                        activation_note,
                        acted_by_user_id
                    ) values (%s, %s, 'activate', %s, %s)
                    """,
                    (loan_id, preview.schedule_id, note, acted_by_user_id),
                )
                return self._load_preview_cursor(cursor, loan_id=loan_id)

    def deactivate(
        self,
        *,
        loan_id: UUID,
        acted_by_user_id: UUID,
        activation_note: str,
    ) -> ContractCollectionActivationPreview:
        note = _clean_note(activation_note)
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                self._lock_loan(cursor, loan_id=loan_id)
                preview = self._load_preview_cursor(cursor, loan_id=loan_id)
                if not preview.is_active or preview.activation_schedule_id is None:
                    raise ContractCollectionActivationConflict(
                        "This loan does not currently have an active contractual collection event."
                    )
                cursor.execute(
                    """
                    insert into lending.loan_contract_collection_activation_events (
                        loan_id,
                        schedule_id,
                        event_action,
                        activation_note,
                        acted_by_user_id
                    ) values (%s, %s, 'deactivate', %s, %s)
                    """,
                    (
                        loan_id,
                        preview.activation_schedule_id,
                        note,
                        acted_by_user_id,
                    ),
                )
                return self._load_preview_cursor(cursor, loan_id=loan_id)

    @staticmethod
    def _lock_loan(cursor: Any, *, loan_id: UUID) -> None:
        cursor.execute(
            "select id from lending.loans where id = %s for update",
            (loan_id,),
        )
        if cursor.fetchone() is None:
            raise ContractCollectionActivationNotFound("Loan not found.")

    def _load_preview_cursor(
        self,
        cursor: Any,
        *,
        loan_id: UUID,
    ) -> ContractCollectionActivationPreview:
        cursor.execute(self._preview_sql() + " and loan.id = %s", (loan_id,))
        row = cursor.fetchone()
        if row is None:
            raise ContractCollectionActivationNotFound("Loan not found.")
        return self._preview_from_row(row)

    @staticmethod
    def _preview_sql() -> str:
        return """
            select
                loan.id as loan_id,
                loan.loan_number,
                client.full_name as client_name,
                loan_type.name as loan_type_name,
                loan.status as loan_status,
                coalesce(state.remaining_balance, loan.principal)::numeric(18,2)
                    as remaining_balance,
                lower(coalesce(loan_type.settings->>'mobile_collections_enabled', ''))
                    in ('true', '1', 'yes', 'on') as mobile_collections_enabled,
                coalesce(loan_type.settings->>'mobile_balance_mode', '')
                    as mobile_balance_mode,
                assessment.schedule_id,
                assessment.schedule_version,
                coalesce(assessment.payment_frequency, '') as payment_frequency,
                coalesce(assessment.contract_reference, '') as contract_reference,
                coalesce(assessment.dpd_data_status, 'contract_schedule_required')
                    as dpd_data_status,
                coalesce(assessment.contractual_schedule_total, 0)::numeric(18,2)
                    as contractual_schedule_total,
                coalesce(assessment.allocated_schedule_total, 0)::numeric(18,2)
                    as allocated_schedule_total,
                registration.id as registration_id,
                coalesce(assessment.automatic_default_label_written, false)
                    as automatic_default_label_written,
                coalesce(assessment.ecl_included, false) as ecl_included,
                assessment.ecl_amount,
                coalesce(assessment.ready_to_post, false) as ready_to_post,
                activation.event_id as activation_event_id,
                coalesce(activation.event_action, '') as activation_action,
                activation.schedule_id as activation_schedule_id,
                coalesce(activation.activation_note, '') as activation_note,
                activation.acted_by_user_id as activated_by_user_id,
                activation.acted_at as activation_acted_at
            from lending.loans loan
            join lending.clients client
              on client.id = loan.client_id
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
            where loan.status = 'active'
        """

    @staticmethod
    def _preview_from_row(row: dict[str, Any]) -> ContractCollectionActivationPreview:
        return ContractCollectionActivationPreview(
            loan_id=row["loan_id"],
            loan_number=str(row["loan_number"]),
            client_name=str(row["client_name"]),
            loan_type_name=str(row["loan_type_name"]),
            loan_status=str(row["loan_status"]),
            remaining_balance=_money(row["remaining_balance"]),
            mobile_collections_enabled=bool(row["mobile_collections_enabled"]),
            mobile_balance_mode=str(row["mobile_balance_mode"] or ""),
            schedule_id=row["schedule_id"],
            schedule_version=(
                int(row["schedule_version"])
                if row["schedule_version"] is not None
                else None
            ),
            payment_frequency=str(row["payment_frequency"] or ""),
            contract_reference=str(row["contract_reference"] or ""),
            dpd_data_status=str(row["dpd_data_status"] or "contract_schedule_required"),
            contractual_schedule_total=_money(row["contractual_schedule_total"]),
            allocated_schedule_total=_money(row["allocated_schedule_total"]),
            registration_id=(
                int(row["registration_id"])
                if row["registration_id"] is not None
                else None
            ),
            automatic_default_label_written=bool(
                row["automatic_default_label_written"]
            ),
            ecl_included=bool(row["ecl_included"]),
            ecl_amount=(
                _money(row["ecl_amount"]) if row["ecl_amount"] is not None else None
            ),
            ready_to_post=bool(row["ready_to_post"]),
            activation_event_id=(
                int(row["activation_event_id"])
                if row["activation_event_id"] is not None
                else None
            ),
            activation_action=str(row["activation_action"] or ""),
            activation_schedule_id=row["activation_schedule_id"],
            activation_note=str(row["activation_note"] or ""),
            activated_by_user_id=row["activated_by_user_id"],
            activation_acted_at=row["activation_acted_at"],
        )


def _money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def _clean_note(value: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ContractCollectionActivationConflict("Activation note is required.")
    if len(normalized) > 1000:
        raise ContractCollectionActivationConflict(
            "Activation note must be 1000 characters or fewer."
        )
    return normalized
