from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .database import open_connection

MONEY = Decimal("0.01")
ZERO = Decimal("0.00")


class RefundDueError(RuntimeError):
    code = "refund_due_error"


class RefundDueNotFound(RefundDueError):
    code = "refund_due_not_found"


class RefundDueInvalid(RefundDueError):
    code = "refund_due_invalid"


class RefundDueApprovalIdempotencyMismatch(RefundDueError):
    code = "refund_due_approval_idempotency_mismatch"


class RefundDueReleaseIdempotencyMismatch(RefundDueError):
    code = "refund_due_release_idempotency_mismatch"


class RefundDueReleaseNotApproved(RefundDueError):
    code = "refund_due_release_not_approved"


class RefundDueReleaseExceedsOutstanding(RefundDueError):
    code = "refund_due_release_exceeds_outstanding"


class RefundDueReleaseCollectorMismatch(RefundDueError):
    code = "refund_due_release_collector_mismatch"


class RefundDueReleaseCashUnavailable(RefundDueError):
    code = "refund_due_release_cash_unavailable"


@dataclass(frozen=True, slots=True)
class RefundDueApprovalRequest:
    idempotency_key: UUID
    actor_user_id: UUID
    adjustment_id: UUID
    approved_amount: Decimal
    reason: str
    authority_reference: str
    canonical_request_hash: str

    @classmethod
    def canonical(
        cls,
        *,
        idempotency_key: UUID,
        actor_user_id: UUID,
        adjustment_id: UUID,
        approved_amount: Decimal,
        reason: str,
        authority_reference: str,
    ) -> RefundDueApprovalRequest:
        amount = _positive_money(approved_amount, "Approval amount")
        normalized_reason = _required_text(reason, "Approval reason")
        normalized_reference = _required_text(
            authority_reference,
            "Authority reference",
        )
        payload = {
            "actor_user_id": str(actor_user_id),
            "adjustment_id": str(adjustment_id),
            "approved_amount": _money_text(amount),
            "authority_reference": normalized_reference,
            "idempotency_key": str(idempotency_key),
            "reason": normalized_reason,
        }
        return cls(
            idempotency_key=idempotency_key,
            actor_user_id=actor_user_id,
            adjustment_id=adjustment_id,
            approved_amount=amount,
            reason=normalized_reason,
            authority_reference=normalized_reference,
            canonical_request_hash=_canonical_hash(payload),
        )


@dataclass(frozen=True, slots=True)
class RefundDueReleaseRequest:
    idempotency_key: UUID
    actor_user_id: UUID
    approval_id: UUID
    released_amount: Decimal
    released_at: datetime
    evidence_reference: str
    evidence_digest: str
    canonical_request_hash: str

    @classmethod
    def canonical(
        cls,
        *,
        idempotency_key: UUID,
        actor_user_id: UUID,
        approval_id: UUID,
        released_amount: Decimal,
        released_at: datetime,
        evidence_reference: str,
        evidence_digest: str,
    ) -> RefundDueReleaseRequest:
        amount = _positive_money(released_amount, "Released amount")
        if released_at.tzinfo is None or released_at.utcoffset() is None:
            raise RefundDueInvalid("Physical release time must include a timezone.")
        normalized_at = released_at.astimezone(timezone.utc)
        normalized_reference = _required_text(
            evidence_reference,
            "Release evidence reference",
        )
        normalized_digest = evidence_digest.strip().lower()
        if len(normalized_digest) != 64 or any(
            character not in "0123456789abcdef" for character in normalized_digest
        ):
            raise RefundDueInvalid(
                "Release evidence digest must be a lowercase or uppercase SHA-256 hex digest."
            )
        payload = {
            "actor_user_id": str(actor_user_id),
            "approval_id": str(approval_id),
            "evidence_digest": normalized_digest,
            "evidence_reference": normalized_reference,
            "idempotency_key": str(idempotency_key),
            "released_amount": _money_text(amount),
            "released_at": normalized_at.isoformat(),
        }
        return cls(
            idempotency_key=idempotency_key,
            actor_user_id=actor_user_id,
            approval_id=approval_id,
            released_amount=amount,
            released_at=normalized_at,
            evidence_reference=normalized_reference,
            evidence_digest=normalized_digest,
            canonical_request_hash=_canonical_hash(payload),
        )


@dataclass(frozen=True, slots=True)
class RefundDueApprovalRecord:
    approval_id: UUID
    idempotency_key: UUID
    adjustment_id: UUID
    loan_id: UUID
    client_id: UUID
    approved_amount: Decimal
    released_amount: Decimal
    remaining_approved_amount: Decimal
    approved_by_user_id: UUID
    reason: str
    authority_reference: str
    approved_at: datetime


@dataclass(frozen=True, slots=True)
class RefundDueReleaseRecord:
    release_id: UUID
    idempotency_key: UUID
    approval_id: UUID
    adjustment_id: UUID
    loan_id: UUID
    client_id: UUID
    assigned_collector_user_id: UUID
    released_amount: Decimal
    approval_released_amount: Decimal
    approval_remaining_amount: Decimal
    adjustment_outstanding_refund_due: Decimal
    released_by_user_id: UUID
    released_at: datetime
    evidence_reference: str
    evidence_digest: str


class PostgresRefundDueRepository:
    def approve(
        self,
        *,
        idempotency_key: UUID,
        actor_user_id: UUID,
        adjustment_id: UUID,
        approved_amount: Decimal,
        reason: str,
        authority_reference: str,
    ) -> RefundDueApprovalRecord:
        request = RefundDueApprovalRequest.canonical(
            idempotency_key=idempotency_key,
            actor_user_id=actor_user_id,
            adjustment_id=adjustment_id,
            approved_amount=approved_amount,
            reason=reason,
            authority_reference=authority_reference,
        )
        try:
            return self._approve_in_transaction(request)
        except RefundDueError:
            raise
        except psycopg.Error as error:
            raise RefundDueInvalid(_database_message(error)) from error

    def release(
        self,
        *,
        idempotency_key: UUID,
        actor_user_id: UUID,
        approval_id: UUID,
        released_amount: Decimal,
        released_at: datetime,
        evidence_reference: str,
        evidence_digest: str,
    ) -> RefundDueReleaseRecord:
        request = RefundDueReleaseRequest.canonical(
            idempotency_key=idempotency_key,
            actor_user_id=actor_user_id,
            approval_id=approval_id,
            released_amount=released_amount,
            released_at=released_at,
            evidence_reference=evidence_reference,
            evidence_digest=evidence_digest,
        )
        try:
            return self._release_in_transaction(request)
        except RefundDueError:
            raise
        except psycopg.Error as error:
            raise RefundDueInvalid(_database_message(error)) from error

    def _approve_in_transaction(
        self,
        request: RefundDueApprovalRequest,
    ) -> RefundDueApprovalRecord:
        with open_connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    _advisory_lock(
                        cursor, f"refund-due-approval:{request.idempotency_key}"
                    )
                    existing = _approval_by_key(cursor, request.idempotency_key)
                    if existing is not None:
                        if (
                            existing["canonical_request_hash"]
                            != request.canonical_request_hash
                        ):
                            raise RefundDueApprovalIdempotencyMismatch(
                                "This Refund Due approval key was already used for different data."
                            )
                        return _approval_from_payload(existing["result_payload"])

                    _advisory_lock(
                        cursor, f"refund-due-adjustment:{request.adjustment_id}"
                    )
                    context = cursor.execute(
                        """
                        select
                            adjustment.loan_id,
                            transaction.client_id,
                            exists (
                                select 1
                                from lending.seven_by_seven_extra_principal_reversals reversal
                                where reversal.adjustment_id = adjustment.id
                            ) as is_reversed
                        from lending.seven_by_seven_extra_principal_adjustments adjustment
                        join lending.collection_transactions transaction
                          on transaction.id = adjustment.transaction_id
                        where adjustment.id = %s
                        for update of adjustment, transaction
                        """,
                        (request.adjustment_id,),
                    ).fetchone()
                    if context is None:
                        raise RefundDueNotFound(
                            "The originating Extra Principal adjustment was not found."
                        )
                    if context["is_reversed"]:
                        raise RefundDueInvalid(
                            "A reversed Extra Principal adjustment has no active Refund Due to approve."
                        )

                    due_rows = cursor.execute(
                        """
                        select
                            status.installment_id,
                            greatest(
                                status.active_classified_amount - status.approved_amount,
                                0
                            )::numeric(18,2) as available_to_approve
                        from lending.loan_unused_advance_refund_due_status status
                        join lending.loan_contract_installments installment
                          on installment.id = status.installment_id
                        join lending.loan_unused_advance_refund_dues refund
                          on refund.adjustment_id = status.adjustment_id
                         and refund.installment_id = status.installment_id
                        where status.adjustment_id = %s
                        order by installment.due_date, installment.installment_number,
                                 status.installment_id
                        for update of refund
                        """,
                        (request.adjustment_id,),
                    ).fetchall()
                    available = sum(
                        (Decimal(row["available_to_approve"]) for row in due_rows),
                        start=ZERO,
                    )
                    if request.approved_amount > available:
                        raise RefundDueInvalid(
                            "Approval amount exceeds the active unapproved Refund Due."
                        )

                    approval_id = uuid4()
                    approved_at = datetime.now(timezone.utc)
                    result = RefundDueApprovalRecord(
                        approval_id=approval_id,
                        idempotency_key=request.idempotency_key,
                        adjustment_id=request.adjustment_id,
                        loan_id=context["loan_id"],
                        client_id=context["client_id"],
                        approved_amount=request.approved_amount,
                        released_amount=ZERO,
                        remaining_approved_amount=request.approved_amount,
                        approved_by_user_id=request.actor_user_id,
                        reason=request.reason,
                        authority_reference=request.authority_reference,
                        approved_at=approved_at,
                    )
                    result_payload = _approval_payload(result)
                    cursor.execute(
                        "select set_config('spina.refund_due_approval_write', 'on', true)"
                    )
                    cursor.execute(
                        """
                        insert into lending.loan_unused_advance_refund_due_approvals (
                            id, idempotency_key, canonical_request_hash, adjustment_id,
                            loan_id, client_id, approved_amount, approved_by_user_id,
                            reason, authority_reference, approved_at, result_payload
                        ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            approval_id,
                            request.idempotency_key,
                            request.canonical_request_hash,
                            request.adjustment_id,
                            context["loan_id"],
                            context["client_id"],
                            request.approved_amount,
                            request.actor_user_id,
                            request.reason,
                            request.authority_reference,
                            approved_at,
                            Jsonb(result_payload),
                        ),
                    )
                    remaining = request.approved_amount
                    for row in due_rows:
                        amount = min(remaining, Decimal(row["available_to_approve"]))
                        if amount <= ZERO:
                            continue
                        cursor.execute(
                            """
                            insert into lending.loan_unused_advance_refund_due_approval_items (
                                approval_id, adjustment_id, installment_id, amount_approved
                            ) values (%s, %s, %s, %s)
                            """,
                            (
                                approval_id,
                                request.adjustment_id,
                                row["installment_id"],
                                amount,
                            ),
                        )
                        remaining -= amount
                    if remaining != ZERO:
                        raise RefundDueInvalid(
                            "Refund Due approval allocation did not reconcile."
                        )
                    _write_audit(
                        cursor,
                        actor_user_id=request.actor_user_id,
                        action="lending.refund_due.approved",
                        target_type="refund_due_approval",
                        target_id=approval_id,
                        details=result_payload,
                        created_at=approved_at,
                    )
                    return result

    def _release_in_transaction(
        self,
        request: RefundDueReleaseRequest,
    ) -> RefundDueReleaseRecord:
        with open_connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=dict_row) as cursor:
                    _advisory_lock(
                        cursor, f"refund-due-release:{request.idempotency_key}"
                    )
                    existing = _release_by_key(cursor, request.idempotency_key)
                    if existing is not None:
                        if (
                            existing["canonical_request_hash"]
                            != request.canonical_request_hash
                        ):
                            raise RefundDueReleaseIdempotencyMismatch(
                                "This Refund Due release key was already used for different data."
                            )
                        return _release_from_payload(existing["result_payload"])

                    approval_identity = cursor.execute(
                        """
                        select adjustment_id
                        from lending.loan_unused_advance_refund_due_approvals
                        where id = %s
                        """,
                        (request.approval_id,),
                    ).fetchone()
                    if approval_identity is None:
                        raise RefundDueReleaseNotApproved(
                            "The Refund Due approval was not found."
                        )
                    adjustment_id = approval_identity["adjustment_id"]

                    # Reversal and physical release share this lock. Acquire it
                    # before loading any release decision state so a waiter must
                    # re-read is_reversed after the winning transaction commits.
                    _advisory_lock(cursor, f"refund-due-adjustment:{adjustment_id}")
                    approval = cursor.execute(
                        """
                        select
                            approval.*,
                            lending.collector_area_owner(client.area)
                                as assigned_collector_user_id,
                            exists (
                                select 1
                                from lending.seven_by_seven_extra_principal_reversals reversal
                                where reversal.adjustment_id = approval.adjustment_id
                            ) as is_reversed
                        from lending.loan_unused_advance_refund_due_approvals approval
                        join lending.clients client on client.id = approval.client_id
                        where approval.id = %s
                        for update of approval, client
                        """,
                        (request.approval_id,),
                    ).fetchone()
                    if approval is None:
                        raise RefundDueReleaseNotApproved(
                            "The Refund Due approval was not found."
                        )
                    if approval["is_reversed"]:
                        raise RefundDueReleaseNotApproved(
                            "The Refund Due approval is no longer active."
                        )
                    if request.released_at < approval["approved_at"]:
                        raise RefundDueReleaseNotApproved(
                            "Physical release time cannot precede Management approval."
                        )
                    assigned_collector = approval["assigned_collector_user_id"]
                    if (
                        assigned_collector is None
                        or assigned_collector != request.actor_user_id
                    ):
                        raise RefundDueReleaseCollectorMismatch(
                            "Only the client's currently assigned Collector may release this Refund Due."
                        )

                    item_rows = cursor.execute(
                        """
                        select
                            item.installment_id,
                            greatest(
                                item.amount_approved - coalesce((
                                    select sum(released.amount_released)
                                    from lending.loan_unused_advance_refund_due_release_items released
                                    where released.approval_id = item.approval_id
                                      and released.adjustment_id = item.adjustment_id
                                      and released.installment_id = item.installment_id
                                ), 0),
                                0
                            )::numeric(18,2) as available_to_release
                        from lending.loan_unused_advance_refund_due_approval_items item
                        join lending.loan_contract_installments installment
                          on installment.id = item.installment_id
                        where item.approval_id = %s
                        order by installment.due_date, installment.installment_number,
                                 item.installment_id
                        for update of item
                        """,
                        (request.approval_id,),
                    ).fetchall()
                    available = sum(
                        (Decimal(row["available_to_release"]) for row in item_rows),
                        start=ZERO,
                    )
                    if request.released_amount > available:
                        raise RefundDueReleaseExceedsOutstanding(
                            "Physical release exceeds the approved unreleased Refund Due."
                        )
                    cash_held = _collector_cash_held(
                        cursor,
                        collector_user_id=assigned_collector,
                    )
                    if request.released_amount > cash_held:
                        raise RefundDueReleaseCashUnavailable(
                            "Collector cash held is insufficient for this physical Refund Due release."
                        )

                    prior_released = Decimal(approval["approved_amount"]) - available
                    adjustment_outstanding = _adjustment_outstanding(
                        cursor,
                        adjustment_id=adjustment_id,
                    )
                    release_id = uuid4()
                    result = RefundDueReleaseRecord(
                        release_id=release_id,
                        idempotency_key=request.idempotency_key,
                        approval_id=request.approval_id,
                        adjustment_id=adjustment_id,
                        loan_id=approval["loan_id"],
                        client_id=approval["client_id"],
                        assigned_collector_user_id=assigned_collector,
                        released_amount=request.released_amount,
                        approval_released_amount=prior_released
                        + request.released_amount,
                        approval_remaining_amount=available - request.released_amount,
                        adjustment_outstanding_refund_due=(
                            adjustment_outstanding - request.released_amount
                        ),
                        released_by_user_id=request.actor_user_id,
                        released_at=request.released_at,
                        evidence_reference=request.evidence_reference,
                        evidence_digest=request.evidence_digest,
                    )
                    result_payload = _release_payload(result)
                    cursor.execute(
                        "select set_config('spina.refund_due_release_write', 'on', true)"
                    )
                    cursor.execute(
                        """
                        insert into lending.loan_unused_advance_refund_due_releases (
                            id, idempotency_key, canonical_request_hash, approval_id,
                            loan_id, client_id, assigned_collector_user_id,
                            released_amount, released_by_user_id, released_at,
                            evidence_reference, evidence_digest, result_payload
                        ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            release_id,
                            request.idempotency_key,
                            request.canonical_request_hash,
                            request.approval_id,
                            approval["loan_id"],
                            approval["client_id"],
                            assigned_collector,
                            request.released_amount,
                            request.actor_user_id,
                            request.released_at,
                            request.evidence_reference,
                            request.evidence_digest,
                            Jsonb(result_payload),
                        ),
                    )
                    remaining = request.released_amount
                    for row in item_rows:
                        amount = min(remaining, Decimal(row["available_to_release"]))
                        if amount <= ZERO:
                            continue
                        cursor.execute(
                            """
                            insert into lending.loan_unused_advance_refund_due_release_items (
                                release_id, approval_id, adjustment_id,
                                installment_id, amount_released
                            ) values (%s, %s, %s, %s, %s)
                            """,
                            (
                                release_id,
                                request.approval_id,
                                adjustment_id,
                                row["installment_id"],
                                amount,
                            ),
                        )
                        remaining -= amount
                    if remaining != ZERO:
                        raise RefundDueInvalid(
                            "Refund Due release allocation did not reconcile."
                        )
                    _write_audit(
                        cursor,
                        actor_user_id=request.actor_user_id,
                        action="lending.refund_due.released",
                        target_type="refund_due_release",
                        target_id=release_id,
                        details=result_payload,
                        created_at=datetime.now(timezone.utc),
                    )
                    return result


def _approval_by_key(cursor: Any, idempotency_key: UUID) -> Any:
    return cursor.execute(
        """
        select canonical_request_hash, result_payload
        from lending.loan_unused_advance_refund_due_approvals
        where idempotency_key = %s
        for update
        """,
        (idempotency_key,),
    ).fetchone()


def _release_by_key(cursor: Any, idempotency_key: UUID) -> Any:
    return cursor.execute(
        """
        select canonical_request_hash, result_payload
        from lending.loan_unused_advance_refund_due_releases
        where idempotency_key = %s
        for update
        """,
        (idempotency_key,),
    ).fetchone()


def _collector_cash_held(cursor: Any, *, collector_user_id: UUID) -> Decimal:
    row = cursor.execute(
        """
        with receipt_cash as (
            select coalesce(sum(transaction.amount), 0)::numeric(18,2) as amount
            from lending.collection_transactions transaction
            where transaction.collector_user_id = %s
              and transaction.entry_type <> 'pass'
              and transaction.is_voided = false
              and transaction.remittance_id is null
              and transaction.is_locked = false
        ), released_cash as (
            select coalesce(sum(greatest(
                release.released_amount - coalesce((
                    select sum(custody.amount_released)
                    from lending.collection_remittance_refund_due_release_items custody
                    join lending.collection_remittances remittance
                      on remittance.id = custody.remittance_id
                    where custody.release_id = release.id
                      and not exists (
                          select 1
                          from lending.collection_remittance_rejections rejection
                          where rejection.remittance_id = remittance.id
                      )
                ), 0),
                0
            )), 0)::numeric(18,2) as amount
            from lending.loan_unused_advance_refund_due_releases release
            where release.assigned_collector_user_id = %s
        )
        select greatest(receipt_cash.amount - released_cash.amount, 0)::numeric(18,2)
            as cash_held
        from receipt_cash cross join released_cash
        """,
        (collector_user_id, collector_user_id),
    ).fetchone()
    return Decimal(row["cash_held"])


def _adjustment_outstanding(cursor: Any, *, adjustment_id: UUID) -> Decimal:
    row = cursor.execute(
        """
        select coalesce(sum(status.outstanding_refund_due), 0)::numeric(18,2)
            as outstanding
        from lending.loan_unused_advance_refund_due_status status
        where status.adjustment_id = %s
        """,
        (adjustment_id,),
    ).fetchone()
    return Decimal(row["outstanding"])


def _write_audit(
    cursor: Any,
    *,
    actor_user_id: UUID,
    action: str,
    target_type: str,
    target_id: UUID,
    details: dict[str, object],
    created_at: datetime,
) -> None:
    cursor.execute(
        """
        insert into core.audit_logs (
            actor_user_id, action, target_type, target_id, details, created_at
        ) values (%s, %s, %s, %s, %s, %s)
        """,
        (actor_user_id, action, target_type, target_id, Jsonb(details), created_at),
    )


def _approval_payload(record: RefundDueApprovalRecord) -> dict[str, object]:
    return {
        "approval_id": str(record.approval_id),
        "idempotency_key": str(record.idempotency_key),
        "adjustment_id": str(record.adjustment_id),
        "loan_id": str(record.loan_id),
        "client_id": str(record.client_id),
        "approved_amount": _money_text(record.approved_amount),
        "released_amount": _money_text(record.released_amount),
        "remaining_approved_amount": _money_text(record.remaining_approved_amount),
        "approved_by_user_id": str(record.approved_by_user_id),
        "reason": record.reason,
        "authority_reference": record.authority_reference,
        "approved_at": record.approved_at.isoformat(),
    }


def _approval_from_payload(payload: Any) -> RefundDueApprovalRecord:
    value = dict(payload or {})
    try:
        return RefundDueApprovalRecord(
            approval_id=UUID(value["approval_id"]),
            idempotency_key=UUID(value["idempotency_key"]),
            adjustment_id=UUID(value["adjustment_id"]),
            loan_id=UUID(value["loan_id"]),
            client_id=UUID(value["client_id"]),
            approved_amount=Decimal(value["approved_amount"]),
            released_amount=Decimal(value["released_amount"]),
            remaining_approved_amount=Decimal(value["remaining_approved_amount"]),
            approved_by_user_id=UUID(value["approved_by_user_id"]),
            reason=str(value["reason"]),
            authority_reference=str(value["authority_reference"]),
            approved_at=datetime.fromisoformat(value["approved_at"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise RefundDueInvalid(
            "Stored Refund Due approval result evidence is invalid."
        ) from error


def _release_payload(record: RefundDueReleaseRecord) -> dict[str, object]:
    return {
        "release_id": str(record.release_id),
        "idempotency_key": str(record.idempotency_key),
        "approval_id": str(record.approval_id),
        "adjustment_id": str(record.adjustment_id),
        "loan_id": str(record.loan_id),
        "client_id": str(record.client_id),
        "assigned_collector_user_id": str(record.assigned_collector_user_id),
        "released_amount": _money_text(record.released_amount),
        "approval_released_amount": _money_text(record.approval_released_amount),
        "approval_remaining_amount": _money_text(record.approval_remaining_amount),
        "adjustment_outstanding_refund_due": _money_text(
            record.adjustment_outstanding_refund_due
        ),
        "released_by_user_id": str(record.released_by_user_id),
        "released_at": record.released_at.isoformat(),
        "evidence_reference": record.evidence_reference,
        "evidence_digest": record.evidence_digest,
    }


def _release_from_payload(payload: Any) -> RefundDueReleaseRecord:
    value = dict(payload or {})
    try:
        return RefundDueReleaseRecord(
            release_id=UUID(value["release_id"]),
            idempotency_key=UUID(value["idempotency_key"]),
            approval_id=UUID(value["approval_id"]),
            adjustment_id=UUID(value["adjustment_id"]),
            loan_id=UUID(value["loan_id"]),
            client_id=UUID(value["client_id"]),
            assigned_collector_user_id=UUID(value["assigned_collector_user_id"]),
            released_amount=Decimal(value["released_amount"]),
            approval_released_amount=Decimal(value["approval_released_amount"]),
            approval_remaining_amount=Decimal(value["approval_remaining_amount"]),
            adjustment_outstanding_refund_due=Decimal(
                value["adjustment_outstanding_refund_due"]
            ),
            released_by_user_id=UUID(value["released_by_user_id"]),
            released_at=datetime.fromisoformat(value["released_at"]),
            evidence_reference=str(value["evidence_reference"]),
            evidence_digest=str(value["evidence_digest"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise RefundDueInvalid(
            "Stored Refund Due release result evidence is invalid."
        ) from error


def _canonical_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _positive_money(value: Decimal, label: str) -> Decimal:
    amount = Decimal(value)
    exponent = amount.as_tuple().exponent
    if (
        not amount.is_finite()
        or not isinstance(exponent, int)
        or amount <= ZERO
        or exponent < -2
    ):
        raise RefundDueInvalid(
            f"{label} must be positive money with at most two decimals."
        )
    return amount.quantize(MONEY)


def _money_text(value: Decimal) -> str:
    return format(Decimal(value).quantize(MONEY), "f")


def _required_text(value: str, label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise RefundDueInvalid(f"{label} is required.")
    return normalized


def _advisory_lock(cursor: Any, key: str) -> None:
    cursor.execute(
        "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (f"gilbic:{key}",),
    )


def _database_message(error: psycopg.Error) -> str:
    return str(error).split("CONTEXT:", 1)[0].strip() or "Refund Due operation failed."
