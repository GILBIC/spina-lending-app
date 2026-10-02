"""Same-transaction funding adapter for the existing protected loan allocators.

This module never manufactures a Collector actor, opens a database connection,
commits, or records a second account movement. The service owns receipt scope,
current grants, capacity and idempotency; existing loan engines remain authoritative.
"""

import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import wraps
from hashlib import sha256
from uuid import UUID, uuid5

from psycopg.rows import dict_row, tuple_row
from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
    PaymentAllocationIntent,
)
from spina_mobile_collections.service import CollectionRejected

from . import combined_collection_api as combined
from .collection_void_repository import PostgresCollectionVoidRepository
from .concurrent_receipt_collection_posting import (
    ConcurrentReceiptSafeCollectionPostingBridge,
)
from .contract_schedule_engine import OutstandingInstallment
from .treasury_authorization import TreasuryConflict

ZERO = Decimal("0.00")


def _protected_connection(fn):
    @wraps(fn)
    def call(conn, *args, **kwargs):
        # Existing protected engines use explicit dict cursors where needed and
        # ordinary tuple cursors elsewhere. Preserve their connection contract,
        # then restore the treasury service's mapping rows even on failure.
        previous = conn.row_factory
        conn.row_factory = tuple_row
        try:
            return fn(conn, *args, **kwargs)
        finally:
            conn.row_factory = previous

    return call


def _money(value):
    return format(Decimal(value).quantize(Decimal("0.01")), "f")


def _actor(actor):
    if actor.registered_device_id is None:
        raise TreasuryConflict("An active registered device is required.")
    return ActorContext(
        account_id=str(actor.user_id),
        device_id=str(actor.registered_device_id),
        registered_device_id=str(actor.registered_device_id),
        permissions=frozenset(actor.permissions),
    )


def _locks(conn, actor, command, *, reserve=False):
    bridge = ConcurrentReceiptSafeCollectionPostingBridge()
    storage_id = actor.registered_device_id
    sequence = 1
    with conn.cursor(row_factory=dict_row) as cursor:
        if reserve:
            # Serializes treasury allocation of this device's next sequence. The
            # official per-sequence locks below still arbitrate ordinary app writes.
            cursor.execute(
                "select pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"treasury-device:{storage_id}",),
            )
            cursor.execute(
                "select coalesce(max(device_sequence),0)+1 next_sequence from lending.collection_transactions where registered_device_id=%s",
                (storage_id,),
            )
            sequence = int(cursor.fetchone()["next_sequence"])
            for offset in range(3):
                bridge._lock_device_sequence(
                    cursor,
                    registered_device_id=storage_id,
                    device_sequence=sequence + offset,
                )
        for loan_id in sorted((item.loan_id for item in command.loans), key=str):
            bridge._lock_loan_date(
                cursor, loan_id=loan_id, collection_date=command.effective_date
            )
        bridge._verify_device(
            cursor, collector_user_id=actor.user_id, registered_device_id=storage_id
        )
    return sequence


def _loans(conn, receipt, command):
    selected = {item.loan_id: item.expected_version for item in command.loans}
    count = 2 if command.mode == "combined" else 1
    if len(selected) != count or len(command.loans) != count:
        raise TreasuryConflict("Select exactly the required distinct loans.")
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """select l.id,l.client_id,l.status,l.principal,l.daily_amount,l.date_released,
            t.calculation_mode,t.settings,t.daily_interest_per_1000,c.status client_status,
            s.remaining_balance,s.is_reconciled,s.state_version
            from lending.loans l join lending.loan_types t on t.id=l.loan_type_id
            join lending.clients c on c.id=l.client_id join lending.loan_collection_state s on s.loan_id=l.id
            where l.id=any(%s) and l.client_id=%s order by l.id for update of l,c,s""",
            (list(selected), receipt["client_id"]),
        )
        rows = cursor.fetchall()
    if len(rows) != count:
        raise TreasuryConflict(
            "The selected loans do not belong to this receipt borrower."
        )
    for row in rows:
        if int(row["state_version"]) != selected[row["id"]]:
            raise TreasuryConflict(
                "A selected loan changed; review the current allocation."
            )
        settings = row["settings"] if isinstance(row["settings"], dict) else {}
        enabled = ConcurrentReceiptSafeCollectionPostingBridge._setting_enabled
        if (
            row["status"] != "active"
            or row["client_status"] != "active"
            or not row["is_reconciled"]
            or not enabled(settings.get("mobile_collections_enabled"))
            or settings.get("mobile_balance_mode") != "direct_remaining_balance"
            or (
                row["calculation_mode"] == "seven_by_seven"
                and not enabled(settings.get("mobile_seven_by_seven_enabled"))
            )
        ):
            raise TreasuryConflict(
                "The selected loan is not ready for protected payment allocation."
            )
    return rows


def _combined_body(actor, receipt, command, sequence=1):
    # Stable preview identity: request_id is intentionally absent from a read.
    return combined.CombinedPaymentRequest(
        client_transaction_id=receipt["id"],
        client_id=receipt["client_id"],
        collection_date=command.effective_date,
        recorded_at=datetime.now(UTC),
        device_id=str(actor.registered_device_id),
        device_sequence=sequence,
        cash_received_amount=Decimal(command.total_amount),
        extra_allocation_choice=command.extra_choice,
        regular_past_due_followup=command.regular_past_due_followup,
        legs=[
            combined.CombinedPaymentLeg(
                loan_id=item.loan_id,
                route_entry_id=item.loan_id,
                route_revision=f"loan:{item.loan_id}:v{item.expected_version}",
            )
            for item in command.loans
        ],
    )


def _regular_plan(conn, loan, command, amount):
    """Reuse the signed-schedule planner; only its database projection is adapted."""
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """select a.schedule_id,coalesce(s.active_borrower_extension_slots,0) slots
            from accounting.loan_contract_dpd_assessment a left join lending.loan_schedule_operational_state s
            on s.schedule_id=a.schedule_id where a.loan_id=%s""",
            (loan["id"],),
        )
        schedule = cursor.fetchone()
        if not schedule or not schedule["schedule_id"]:
            return None
        cursor.execute(
            """select i.id,i.installment_number,i.effective_due_date,i.contractual_amount,
            coalesce(sum(p.amount_applied) filter(where not t.is_voided),0) allocated_amount
            from lending.loan_contract_installments_operational i
            left join lending.loan_installment_payment_allocations p on p.installment_id=i.id
            left join lending.collection_transactions t on t.id=p.transaction_id
            where i.schedule_id=%s group by i.id,i.installment_number,i.effective_due_date,i.contractual_amount
            order by i.effective_due_date,i.installment_number,i.id""",
            (schedule["schedule_id"],),
        )
        installments = tuple(
            OutstandingInstallment(
                installment_id=r["id"],
                installment_number=r["installment_number"],
                due_date=r["effective_due_date"],
                contractual_amount=r["contractual_amount"],
                allocated_amount=r["allocated_amount"],
            )
            for r in cursor.fetchall()
        )
    plan = (
        ConcurrentReceiptSafeCollectionPostingBridge()._plan_applied_contract_payment(
            applied_amount=amount,
            installments=installments,
            collection_date=command.effective_date,
            allocation_intent=command.intent,
            active_borrower_extension_slots=int(schedule["slots"]),
        )
    )
    return [asdict(item) for item in plan]


def _single(conn, loan, command):
    amount = Decimal(command.total_amount)
    due, basis = combined._collectible_obligation(
        conn, loan=loan, collection_date=command.effective_date
    )
    intent = command.intent
    if command.extra_choice is not None:
        raise TreasuryConflict(
            "Single-loan allocation uses its explicit payment intent, not a combined-loan choice."
        )
    mode = loan["calculation_mode"]
    evidence = combined._authoritative_allocation_evidence(conn, loan=loan)
    if mode == "fixed_daily":
        if amount > Decimal(loan["remaining_balance"]):
            raise TreasuryConflict("Amount exceeds the protected remaining payoff.")
        plan = _regular_plan(conn, loan, command, amount)
        if plan is None and amount > due:
            raise TreasuryConflict(
                "Extra allocation requires an activated verified signed schedule."
            )
        if command.covered_dates:
            raise TreasuryConflict(
                "Regular allocation selects authoritative due rows; manual covered dates are not accepted here."
            )
        if amount < due and command.regular_past_due_followup is None:
            raise TreasuryConflict(
                "Choose the borrower Past Due reason for a partial Regular payment."
            )
        if amount >= due and command.regular_past_due_followup is not None:
            raise TreasuryConflict(
                "A Past Due follow-up is not applicable to this fully covered obligation."
            )
        return [
            {
                "loan_id": str(loan["id"]),
                "loan_type": "regular",
                "component": "regular_payment",
                "amount": _money(amount),
                "applied_amount": _money(amount),
                "unallocated_amount": "0.00",
                "covered_dates": [],
                "intent": intent.value,
                "entry_type": "payment",
                "evidence": evidence,
                "installments": plan or [],
                "collectible_basis": basis,
            }
        ]
    if mode != "seven_by_seven":
        raise TreasuryConflict(
            "This loan type has no protected treasury payment adapter."
        )
    if command.regular_past_due_followup is not None:
        raise TreasuryConflict(
            "Regular Past Due reasons do not apply to this 7x7 loan."
        )
    penalty, penalty_evidence = (
        combined._authoritative_seven_by_seven_penalty_obligation(
            conn,
            loan=loan,
            collection_date=command.effective_date,
            collectible_basis=basis,
        )
    )
    due += penalty
    scheduled = min(amount, due)
    extra = amount - scheduled
    choice = None
    if intent is PaymentAllocationIntent.NO_COLLECTION_VOLUNTARY:
        if due > 0:
            raise TreasuryConflict(
                "This loan has a collectible obligation; use the scheduled payment path."
            )
        scheduled = amount
        extra = ZERO
    elif extra > 0:
        if intent is PaymentAllocationIntent.EXTRA_AS_ADVANCE:
            choice = combined.CombinedExtraAllocationChoice.SEVEN_BY_SEVEN_ADVANCE
        elif intent is PaymentAllocationIntent.EXTRA_AS_PRINCIPAL_REDUCTION:
            choice = (
                combined.CombinedExtraAllocationChoice.SEVEN_BY_SEVEN_EXTRA_PRINCIPAL
            )
        else:
            raise TreasuryConflict(
                "Choose Advance or Principal Reduction for extra money."
            )
        if basis != "verified_schedule":
            raise TreasuryConflict(
                "7x7 extra allocation requires a verified signed schedule."
            )
    projection = combined._project_seven_by_seven_cash(
        conn,
        loan=loan,
        collection_date=command.effective_date,
        scheduled_amount=scheduled,
        extra_amount=extra,
        extra_choice=choice,
        penalty_collectible=penalty,
    )
    dates = (
        combined._seven_by_seven_advance_dates(
            conn,
            loan_id=loan["id"],
            collection_date=command.effective_date,
            amount=extra,
        )
        if choice is combined.CombinedExtraAllocationChoice.SEVEN_BY_SEVEN_ADVANCE
        else ()
    )
    if command.covered_dates and tuple(sorted(command.covered_dates)) != dates:
        raise TreasuryConflict(
            "Covered dates changed; review the authoritative advance allocation."
        )
    result = []
    for component, cash in [("scheduled", scheduled), ("extra", extra)]:
        if cash <= ZERO:
            continue
        advance = component == "extra" and bool(dates)
        component_intent = (
            intent
            if component == "extra"
            or intent is PaymentAllocationIntent.NO_COLLECTION_VOLUNTARY
            else PaymentAllocationIntent.SCHEDULED
        )
        result.append(
            {
                "loan_id": str(loan["id"]),
                "loan_type": "seven_by_seven",
                "component": f"seven_{component}",
                "amount": _money(cash),
                "applied_amount": _money(cash),
                "unallocated_amount": "0.00",
                "covered_dates": [d.isoformat() for d in dates] if advance else [],
                "intent": (
                    PaymentAllocationIntent.SCHEDULED if advance else component_intent
                ).value,
                "entry_type": "advance" if advance else "payment",
                "evidence": evidence,
                "penalty_evidence": penalty_evidence,
                "cash_projection": projection[component],
            }
        )
    return result


def _preview(conn, actor, receipt, command, *, locks=True):
    if locks:
        _locks(conn, actor, command)
    combined._validate_current_route_date(command.effective_date)
    amount = Decimal(command.total_amount)
    remaining = (
        receipt["amount"] - receipt["applied_amount"] - receipt["refunded_amount"]
    )
    if command.expected_version != receipt["version"] or amount > remaining:
        raise TreasuryConflict(
            "Receipt version or available funds changed; review again."
        )
    loans = _loans(conn, receipt, command)
    if command.mode == "combined":
        if (
            command.covered_dates
            or command.intent is not PaymentAllocationIntent.SCHEDULED
        ):
            raise TreasuryConflict(
                "Combined payment uses its reviewed server split and explicit combined extra choice."
            )
        preview = combined._allocation_preview(
            conn,
            _combined_body(actor, receipt, command),
            collector_account_id=actor.user_id,
            authorized_client_id=receipt["client_id"],
        )
        if preview["extra_choice_required"]:
            raise TreasuryConflict(
                "Choose Advance or Principal Reduction for the extra amount."
            )
        if preview["regular_past_due_followup_required"] != (
            command.regular_past_due_followup is not None
        ):
            raise TreasuryConflict(
                "Review the required Regular Past Due reason before applying."
            )
        allocations = [
            {
                "loan_id": leg["loan_id"],
                "loan_type": leg["loan_type"],
                "component": leg["loan_type"],
                "amount": leg["total_amount"],
                "applied_amount": leg["total_amount"],
                "unallocated_amount": "0.00",
                "covered_dates": leg["projected_covered_dates"],
                "intent": command.intent.value,
                "server_evidence": leg,
            }
            for leg in preview["legs"]
            if Decimal(leg["total_amount"]) > 0
        ]
    else:
        preview = None
        allocations = _single(conn, loans[0], command)
    body = {
        "mode": command.mode,
        "total_amount": command.total_amount,
        "effective_date": command.effective_date.isoformat(),
        "loans": [
            {"loan_id": str(item.loan_id), "expected_version": item.expected_version}
            for item in command.loans
        ],
        "allocations": allocations,
        "blockers": [],
        "can_apply": True,
    }
    evidence = dict(
        body,
        receipt_id=str(receipt["id"]),
        receipt_version=receipt["version"],
        remaining_amount=_money(remaining),
        extra_choice=command.extra_choice.value if command.extra_choice else None,
        regular_past_due_followup=command.regular_past_due_followup.model_dump(
            mode="json"
        )
        if command.regular_past_due_followup
        else None,
        combined_hash=preview["allocation_hash"] if preview else None,
    )
    body["digest"] = sha256(
        json.dumps(
            evidence, sort_keys=True, separators=(",", ":"), default=str
        ).encode()
    ).hexdigest()
    # Full exact planner evidence participates in the digest, but its internal
    # projections are not required as independently editable client input.
    return body, preview


@_protected_connection
def preview_allocation(conn, actor, receipt, command):
    try:
        return _preview(conn, actor, receipt, command)[0]
    except (TreasuryConflict, CollectionRejected) as error:
        return {
            "mode": command.mode,
            "total_amount": command.total_amount,
            "effective_date": command.effective_date.isoformat(),
            "loans": [
                {
                    "loan_id": str(item.loan_id),
                    "expected_version": item.expected_version,
                }
                for item in command.loans
            ],
            "allocations": [],
            "digest": None,
            "can_apply": False,
            "blockers": [
                {
                    "code": getattr(error, "code", "treasury_conflict"),
                    "message": str(error),
                }
            ],
        }


@_protected_connection
def apply_receipt(conn, actor, receipt, command):
    sequence = _locks(conn, actor, command, reserve=True)
    preview, combined_preview = _preview(conn, actor, receipt, command, locks=False)
    if preview["digest"] != command.digest:
        raise TreasuryConflict(
            "The protected allocation changed; review again before applying."
        )
    conn.execute(
        "select set_config('spina.treasury_receipt_id',%s,true)", (str(receipt["id"]),)
    )
    bridge = ConcurrentReceiptSafeCollectionPostingBridge()
    storage_actor = _actor(actor)
    if command.mode == "combined":
        body = _combined_body(actor, receipt, command, sequence)
        result = combined._post_reviewed_components(
            conn,
            storage_actor,
            body,
            command.request_id,
            combined_preview,
            bridge=bridge,
        )
        result_legs = result.get("legs")
        if not isinstance(result_legs, list) or not all(
            isinstance(item, dict) and isinstance(item.get("transaction_id"), str)
            for item in result_legs
        ):
            raise TreasuryConflict(
                "Protected combined payment returned incomplete receipt evidence."
            )
        ids = [item["transaction_id"] for item in result_legs]
    else:
        ids = []
        revisions = {
            str(item.loan_id): f"loan:{item.loan_id}:v{item.expected_version}"
            for item in command.loans
        }
        for index, item in enumerate(preview["allocations"]):
            dates = tuple(date.fromisoformat(value) for value in item["covered_dates"])
            entry = CollectionEntryType(item["entry_type"])
            posting = CollectionCommand(
                idempotency_key=uuid5(command.request_id, item["component"]),
                route_entry_id=item["loan_id"],
                client_id=str(receipt["client_id"]),
                loan_id=item["loan_id"],
                collection_date=command.effective_date,
                entry_type=entry,
                recorded_at=datetime.now(UTC),
                device_id=storage_actor.device_id,
                device_sequence=sequence + index,
                amount=Decimal(item["amount"]),
                covered_dates=dates or (command.effective_date,),
                advance_from=dates[0] if dates else None,
                advance_until=dates[-1] if dates else None,
                route_revision=revisions[item["loan_id"]],
                payment_allocation_intent=PaymentAllocationIntent(item["intent"]),
                note="Verified recipient-account funds; not Collector cash",
                past_due_followup=command.regular_past_due_followup.to_input()
                if command.regular_past_due_followup
                else None,
            )
            posted = bridge.post_collection(conn, storage_actor, posting)
            if not posted.server_transaction_id or not posted.route_revision:
                raise TreasuryConflict(
                    "Protected payment returned incomplete receipt evidence."
                )
            ids.append(posted.server_transaction_id)
            revisions[item["loan_id"]] = posted.route_revision
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """select id,amount,applied_amount,unallocated_amount,funding_receipt_id from lending.collection_transactions
            where id=any(%s) and not is_voided""",
            ([UUID(value) for value in ids],),
        )
        saved = cursor.fetchall()
    if (
        len(saved) != len(ids)
        or any(
            row["funding_receipt_id"] != receipt["id"]
            or row["unallocated_amount"] != 0
            or row["applied_amount"] != row["amount"]
            for row in saved
        )
        or sum((row["amount"] for row in saved), ZERO) != Decimal(command.total_amount)
    ):
        raise TreasuryConflict(
            "Protected receipt allocation did not reconcile; no application was confirmed."
        )
    conn.execute("select set_config('spina.treasury_receipt_id','',true)")
    return {
        "status": "recorded",
        "transaction_ids": ids,
        "amount": command.total_amount,
    }


@_protected_connection
def reverse_application(conn, actor, receipt, application, command):
    ids = [UUID(value) for value in application["source_result"]["transaction_ids"]]
    if not ids or len(set(ids)) != len(ids):
        raise TreasuryConflict("Application evidence is invalid.")
    conn.execute("select set_config('spina.treasury_application_reversal','on',true)")
    repo = PostgresCollectionVoidRepository()
    for transaction_id in reversed(ids):
        # Funding identity is immutable. Read it without a row lock, then let
        # the existing void path acquire its advisory lock before row locks.
        # It rechecks existence/status under that lock and owns principal review.
        with conn.cursor(row_factory=dict_row) as cursor:
            row = cursor.execute(
                "select funding_receipt_id,is_voided from lending.collection_transactions where id=%s",
                (transaction_id,),
            ).fetchone()
        if (
            row is None
            or row["funding_receipt_id"] != receipt["id"]
            or row["is_voided"]
        ):
            raise TreasuryConflict(
                "Application source changed; protected reversal review is required."
            )
        repo.void_unremitted(
            actor_user_id=actor.user_id,
            transaction_id=transaction_id,
            reason=command.reason,
            idempotency_key=uuid5(command.request_id, str(transaction_id)),
            connection=conn,
        )
        if not conn.execute(
            "select is_voided from lending.collection_transactions where id=%s",
            (transaction_id,),
        ).fetchone()[0]:
            raise TreasuryConflict(
                "This source needs its separate protected reversal approval before funds can be released."
            )
    conn.execute("select set_config('spina.treasury_application_reversal','',true)")
    return {"status": "reversed", "application_id": str(application["id"])}
