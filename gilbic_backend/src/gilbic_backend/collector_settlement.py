"""Count capture and atomic physical acceptance; no independent connection or allocator."""

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from .collector_surplus import (
    PREFIX,
    exception_change,
    load,
    outcome,
    require_enabled,
    save,
)
from .treasury_authorization import (
    TreasuryConflict,
    TreasuryDenied,
    require_account,
    require_live_permission,
)
from .treasury_repository import event_projection, identity, json_value


def source_snapshot(conn, remittance_id):
    row = conn.execute(
        "select * from lending.collection_remittances where id=%s for update",
        (remittance_id,),
    ).fetchone()
    if row is None:
        raise TreasuryDenied("Remittance is unavailable.")
    items = conn.execute(
        """select i.*,t.edit_version,t.is_voided,t.funding_source,t.remittance_id as current_remittance_id,
 t.is_locked,t.amount as current_amount,t.collection_date as current_date,t.assigned_collector_user_id
 from lending.collection_remittance_items i join lending.collection_transactions t on t.id=i.transaction_id
 where i.remittance_id=%s order by i.transaction_id for update of t""",
        (remittance_id,),
    ).fetchall()
    refunds = conn.execute(
        "select * from lending.collection_remittance_refund_due_release_items where remittance_id=%s order by release_id for share",
        (remittance_id,),
    ).fetchall()
    gross = sum((item["amount"] for item in items), Decimal("0.00"))
    refund = sum((item["amount_released"] for item in refunds), Decimal("0.00"))
    if gross - refund != row["total_amount"] or gross > Decimal("9999999999999999.99"):
        raise TreasuryConflict(
            "Remittance source totals conflict or exceed exact PHP capacity."
        )
    if any(
        item["funding_source"] != "collector_cash"
        or item["is_voided"]
        or not item["is_locked"]
        or item["current_remittance_id"] != row["id"]
        or item["current_amount"] != item["amount"]
        or item["current_date"] != item["collection_date"]
        for item in items
    ):
        raise TreasuryConflict(
            "Current protected physical source differs from the submitted snapshot."
        )
    if conn.execute(
        "select 1 from lending.collection_remittance_rejections where remittance_id=%s",
        (remittance_id,),
    ).fetchone():
        raise TreasuryConflict(
            "Rejected handover requires a new protected remittance, not acceptance."
        )
    snapshot = json_value(
        {"remittance": row, "items": items, "refund_due_releases": refunds}
    )
    digest = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return row, snapshot, digest, gross, refund


def preview(service, conn, actor, remittance_id, command):
    account = require_account(conn, actor, command.account_id, PREFIX + "receive")
    require_live_permission(conn, actor, "remittance.receive")
    row, snapshot, digest, gross, refund = source_snapshot(conn, remittance_id)
    if (
        row["recipient_user_id"] != actor.user_id
        or account["kind"] != "physical_cash"
        or account["custodian_user_id"] != actor.user_id
    ):
        raise TreasuryDenied(
            "Exact designated recipient and their receiving physical-cash account are required."
        )
    if account["version"] != command.expected_version:
        raise TreasuryConflict("Receiving account changed; refresh and review.")
    blockers = []
    if row["status"] != "submitted":
        blockers.append(
            {
                "code": "remittance_not_pending",
                "message": "Only a current submitted remittance may be counted.",
            }
        )
    if command.credit_application_id:
        blockers.append(
            {
                "code": "collector_application_custody_unavailable",
                "message": "Protected retained-credit custody split is unavailable; no application assumed.",
            }
        )
    held = conn.execute(
        "select id from treasury.collector_exceptions where (payload->>'remittance_id')::uuid=%s and (payload->>'remaining_held_amount')::numeric>0 order by id for update",
        (remittance_id,),
    ).fetchall()
    retained_amount = Decimal("0.00")
    if command.retained_exception_id:
        retained = load(
            conn,
            "exceptions",
            command.retained_exception_id,
            command.retained_exception_version,
        )
        if (
            retained["account_id"] != str(account["id"])
            or retained["ledger_context_id"] != str(account["ledger_context_id"])
            or retained["holder_user_id"] != str(actor.user_id)
            or retained["collector_user_id"] != str(row["collector_user_id"])
            or retained["remittance_id"] != str(remittance_id)
        ):
            raise TreasuryDenied(
                "Select retained cash for this exact remittance, holder and account."
            )
        retained_amount = Decimal(retained["remaining_held_amount"])
        if (
            len(held) != 1
            or held[0]["id"] != command.retained_exception_id
            or retained_amount <= 0
            or retained_amount > gross - refund
            or Decimal(retained["reserved_amount"]) != 0
            or Decimal(retained["available_amount"]) != retained_amount
            or retained["source_digest"] != digest
        ):
            raise TreasuryConflict(
                "Retained cash changed, is reserved for return, or does not match the current source."
            )
        service.evidence(
            conn, account["id"], UUID(retained["evidence_id"]), {"recipient"}
        )
        original = conn.execute(
            "select * from treasury.events where id=%s for update",
            (UUID(retained["event_id"]),),
        ).fetchone()
        if (
            not original
            or original["account_id"] != account["id"]
            or original["ledger_context_id"] != account["ledger_context_id"]
            or original["provider"] != "physical_cash"
            or original["direction"] != "credit"
            or str(original["evidence_id"]) != retained["evidence_id"]
            or original["amount"] != Decimal(retained["retained_amount"])
        ):
            raise TreasuryConflict(
                "The original retained cash receipt is unavailable or changed."
            )
        projected = event_projection(conn, original)
        if (
            projected["corrected"]
            or projected["classification"] != "collector_retained_dispute"
        ):
            raise TreasuryConflict(
                "The original retained cash receipt requires investigation."
            )
        snapshot["retained_cash"] = {
            "exception_id": retained["id"],
            "exception_version": retained["version"],
            "amount": str(retained_amount),
            "event_id": retained["event_id"],
            "event_version": projected["version"],
            "evidence_id": retained["evidence_id"],
            "effective_at": original["effective_at"].isoformat(),
        }
        digest = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    elif held:
        blockers.append(
            {
                "code": "retained_cash_dispute",
                "message": "Select the current retained cash record for inclusion, or complete its evidenced return before full acceptance.",
            }
        )
    return json_value(
        {
            "collector_surplus_contract_version": 1,
            "actor_user_id": actor.user_id,
            "device_id": actor.registered_device_id,
            "account_id": account["id"],
            "account_version": account["version"],
            "ledger_context_id": account["ledger_context_id"],
            "remittance_id": row["id"],
            "remittance_number": row["remittance_number"],
            "collector_user_id": row["collector_user_id"],
            "recipient_user_id": row["recipient_user_id"],
            "status": row["status"],
            "collection_date": str(row["collection_date"]),
            "source_digest": digest,
            "gross_obligation": gross,
            "refund_due_total": refund,
            "authorized_credit_application": "0.00",
            "physical_cash_required": gross - refund - retained_amount,
            "retained_cash_amount": retained_amount,
            "retained_exception_id": command.retained_exception_id,
            "retained_exception_version": command.retained_exception_version,
            "source_snapshot": snapshot,
            "source_items": snapshot["items"],
            "refund_due_releases": snapshot["refund_due_releases"],
            "remittance_snapshot": snapshot["remittance"],
            "can_count": not blockers,
            "blockers": blockers,
        }
    )


def settlement_action(service, conn, actor, account, command):
    from .treasury_models import SettlementPreview

    require_enabled()
    tag = command.action
    if tag == "collector_count_record":
        p = preview(
            service,
            conn,
            actor,
            command.remittance_id,
            SettlementPreview(
                account_id=account["id"],
                expected_version=account["version"],
                retained_exception_id=command.retained_exception_id,
                retained_exception_version=command.retained_exception_version,
            ),
        )
        if (
            not p["can_count"]
            or p["source_digest"] != command.source_digest
            or not command.review_acknowledged
            or command.counted_at > service.clock()
            or p["source_snapshot"].get("retained_cash") is not None
            and command.counted_at
            < datetime.fromisoformat(
                p["source_snapshot"]["retained_cash"]["effective_at"]
            )
        ):
            raise TreasuryConflict(
                "Review matching current source and actual count time."
            )
        service.evidence(conn, account["id"], command.evidence_id, {"recipient"})
        diff = Decimal(command.counted_amount) - Decimal(p["physical_cash_required"])
        disposition = "counted_short_rejected" if diff < 0 else "counted_ready"
        data = {
            key: p[key]
            for key in [
                "remittance_id",
                "collector_user_id",
                "recipient_user_id",
                "source_digest",
                "gross_obligation",
                "refund_due_total",
                "physical_cash_required",
                "retained_cash_amount",
                "retained_exception_id",
                "retained_exception_version",
            ]
        }
        data.update(
            counted_amount=command.counted_amount,
            difference=diff,
            counted_at=command.counted_at,
            recorded_at=service.clock(),
            disposition=disposition,
            source_snapshot=p["source_snapshot"],
            evidence_id=str(command.evidence_id),
            recipient_attestation=command.recipient_attestation,
        )
        count = save(
            conn,
            "counts",
            account,
            UUID(p["collector_user_id"]),
            identity(command.request_id, "count"),
            data,
        )
        return outcome(count, "count", disposition)
    count = load(conn, "counts", command.count_id, command.count_version)
    if count["account_id"] != str(account["id"]) or count["recipient_user_id"] != str(
        actor.user_id
    ):
        raise TreasuryDenied("Count belongs to another recipient or account.")
    p = preview(
        service,
        conn,
        actor,
        UUID(count["remittance_id"]),
        SettlementPreview(
            account_id=account["id"],
            expected_version=account["version"],
            credit_application_id=getattr(command, "credit_application_id", None),
            credit_application_version=getattr(
                command, "credit_application_version", None
            ),
            retained_exception_id=count.get("retained_exception_id"),
            retained_exception_version=count.get("retained_exception_version"),
        ),
    )
    if (
        p["source_digest"] != count["source_digest"]
        or command.source_digest != p["source_digest"]
    ):
        raise TreasuryConflict("Source changed since the actual count; review again.")
    service.evidence(conn, account["id"], UUID(count["evidence_id"]), {"recipient"})
    if tag == "collector_custody_exception_record":
        if count.get("retained_exception_id"):
            raise TreasuryConflict(
                "A short additional handover cannot create another retained-cash exception here."
            )
        if not p["can_count"]:
            raise TreasuryConflict("; ".join(b["message"] for b in p["blockers"]))
        if (
            count["disposition"] != "counted_short_rejected"
            or Decimal(command.retained_amount) > Decimal(count["counted_amount"])
            or command.retained_at > service.clock()
        ):
            raise TreasuryConflict(
                "Only a positive actually retained portion of this rejected short count is allowed."
            )
        service.evidence(conn, account["id"], command.evidence_id, {"recipient"})
        event, _ = service.record_verified_event(
            conn,
            actor,
            account,
            {
                "id": identity(command.request_id, "retained-event"),
                "provider": "physical_cash",
                "reference": "collector-dispute:" + count["id"],
                "direction": "credit",
                "amount": Decimal(command.retained_amount),
                "fee": Decimal("0.00"),
                "effective_at": command.retained_at,
                "evidence_id": command.evidence_id,
                "recipient_attestation": command.holder_attestation,
                "classification": "collector_retained_dispute",
                "reason": command.reason,
            },
        )
        row = save(
            conn,
            "exceptions",
            account,
            UUID(count["collector_user_id"]),
            identity(command.request_id, "exception"),
            {
                "count_id": count["id"],
                "remittance_id": count["remittance_id"],
                "holder_user_id": str(actor.user_id),
                "retained_amount": command.retained_amount,
                "returned_amount": "0.00",
                "included_amount": "0.00",
                "reserved_amount": "0.00",
                "remaining_held_amount": command.retained_amount,
                "available_amount": command.retained_amount,
                "status": "held_disputed",
                "event_id": str(event["id"]),
                "source_digest": count["source_digest"],
                "evidence_id": str(command.evidence_id),
                "reason": command.reason,
            },
        )
        return outcome(row, "exception", "custody_exception_recorded", count=count)
    if not p["can_count"]:
        raise TreasuryConflict("; ".join(b["message"] for b in p["blockers"]))
    if (
        count["disposition"] != "counted_ready"
        or not command.physical_receipt_acknowledged
    ):
        raise TreasuryConflict(
            "Short count cannot accept full custody; real receipt acknowledgment is required."
        )
    event = None
    if Decimal(count["counted_amount"]) > 0:
        event, _ = service.record_verified_event(
            conn,
            actor,
            account,
            {
                "id": identity(command.request_id, "cash-event"),
                "provider": "physical_cash",
                "reference": "collector-remittance:" + count["remittance_id"],
                "direction": "credit",
                "amount": Decimal(count["counted_amount"]),
                "fee": Decimal("0.00"),
                "effective_at": datetime.fromisoformat(count["counted_at"]),
                "evidence_id": UUID(count["evidence_id"]),
                "recipient_attestation": count["recipient_attestation"],
                "classification": "collector_counted_receipt",
                "reason": "Counted cash settlement; excess remains pending identification.",
            },
        )
    included = None
    if count.get("retained_exception_id"):
        retained = load(
            conn,
            "exceptions",
            UUID(count["retained_exception_id"]),
            count["retained_exception_version"],
        )
        included = exception_change(
            conn, retained, included_amount=Decimal(p["retained_cash_amount"])
        )
        conn.execute(
            "insert into treasury.source_links(id,event_id,ledger_context_id,source_kind,source_id,source_version,linked_amount) values(%s,%s,%s,'collector_remittance_physical',%s,1,%s)",
            (
                identity(UUID(retained["event_id"]), "remittance-portion"),
                UUID(retained["event_id"]),
                account["ledger_context_id"],
                UUID(count["remittance_id"]),
                Decimal(p["retained_cash_amount"]),
            ),
        )
    now = service.clock()
    conn.execute(
        "insert into lending.collection_remittance_reviews(remittance_id,reviewed_by_user_id,reviewed_at) values(%s,%s,%s) on conflict(remittance_id) do nothing",
        (UUID(count["remittance_id"]), actor.user_id, now),
    )
    conn.execute(
        "select set_config('spina.collector_count_accept',%s,true)",
        (count["remittance_id"],),
    )
    conn.execute(
        "update lending.collection_remittances set status='received',received_at=%s,received_by_user_id=%s,updated_at=%s where id=%s",
        (now, actor.user_id, now, UUID(count["remittance_id"])),
    )
    conn.execute("select set_config('spina.collector_count_accept','',true)")
    settlement = save(
        conn,
        "settlements",
        account,
        UUID(count["collector_user_id"]),
        identity(command.request_id, "settlement"),
        {
            "remittance_id": count["remittance_id"],
            "count_id": count["id"],
            "recipient_user_id": str(actor.user_id),
            "event_id": str(event["id"]) if event else None,
            "physical_amount": count["counted_amount"],
            "retained_cash_amount": p["retained_cash_amount"],
            "retained_exception_id": count.get("retained_exception_id"),
            "retained_exception_version": count.get("retained_exception_version"),
            "authorized_credit_amount": "0.00",
            "gross_obligation": count["gross_obligation"],
            "accepted_at": now,
        },
    )
    if event and Decimal(count["physical_cash_required"]) > 0:
        conn.execute(
            "insert into treasury.source_links(id,event_id,ledger_context_id,source_kind,source_id,source_version,linked_amount) values(%s,%s,%s,'collector_remittance_physical',%s,1,%s)",
            (
                identity(event["id"], "remittance-portion"),
                event["id"],
                account["ledger_context_id"],
                UUID(count["remittance_id"]),
                Decimal(count["physical_cash_required"]),
            ),
        )
    case = None
    if Decimal(count["difference"]) > 0:
        case = save(
            conn,
            "cases",
            account,
            UUID(count["collector_user_id"]),
            identity(command.request_id, "case"),
            {
                "settlement_id": settlement["id"],
                "opening_id": None,
                "received_excess_amount": count["difference"],
                "unidentified_amount": count["difference"],
                "source_digest": count["source_digest"],
                "status": "pending_identification",
                "resolutions": [],
            },
        )
    if case and event:
        conn.execute(
            "insert into treasury.source_links(id,event_id,ledger_context_id,source_kind,source_id,source_version,linked_amount) values(%s,%s,%s,'collector_excess_pending',%s,1,%s)",
            (
                identity(event["id"], "pending-portion"),
                event["id"],
                account["ledger_context_id"],
                UUID(case["id"]),
                Decimal(case["received_excess_amount"]),
            ),
        )
    return outcome(
        settlement,
        "settlement",
        "accepted_pending_identification" if case else "accepted_exact",
        count=count,
        case=case,
        exception=included,
    )


def guard_legacy_receive(cursor, remittance_id):
    from .collector_surplus import enabled
    from .remittance_repository import RemittanceError

    class CollectorCountRequired(RemittanceError):
        code = "collector_count_required"

    if enabled():
        raise CollectorCountRequired(
            "Update required: review and record the actual physical count before receiving this remittance."
        )
    cursor.execute("select to_regclass('treasury.collector_counts') as relation")
    row = cursor.fetchone()
    exists = row["relation"] if isinstance(row, dict) else row[0]
    if exists:
        cursor.execute(
            "select 1 from treasury.collector_counts where remittance_id=%s limit 1",
            (remittance_id,),
        )
        if cursor.fetchone():
            raise CollectorCountRequired(
                "Counted remittance requires its retained source-aware settlement workflow."
            )


def guard_legacy_rejection(cursor, remittance_id):
    from .remittance_repository import RemittanceError

    class RetainedCashRequired(RemittanceError):
        code = "retained_cash_dispute_requires_resolution"

    cursor.execute("select to_regclass('treasury.collector_exceptions') as relation")
    row = cursor.fetchone()
    exists = row["relation"] if isinstance(row, dict) else row[0]
    if exists:
        cursor.execute(
            "select 1 from treasury.collector_exceptions where (payload->>'remittance_id')::uuid=%s and (payload->>'remaining_held_amount')::numeric>0",
            (remittance_id,),
        )
        if cursor.fetchone():
            raise RetainedCashRequired(
                "Disputed cash remains physically held; return it through the evidenced workflow before asserting cash responsibility returned."
            )


def receiving_contract(service, conn, actor, remittance_id):
    from .collector_surplus import enabled
    from .treasury_authorization import require_actor

    require_actor(conn, actor)
    require_live_permission(conn, actor, "remittance.receive")
    row = conn.execute(
        "select id,recipient_user_id from lending.collection_remittances where id=%s for share",
        (remittance_id,),
    ).fetchone()
    if not row or row["recipient_user_id"] != actor.user_id:
        raise TreasuryDenied("Exact designated recipient is required.")
    exists = conn.execute(
        "select to_regclass('treasury.collector_counts') as relation"
    ).fetchone()["relation"]
    retained = bool(
        exists
        and conn.execute(
            "select 1 from treasury.collector_counts where remittance_id=%s limit 1",
            (remittance_id,),
        ).fetchone()
    )
    required = enabled() or retained
    return {
        "collector_surplus_contract_version": 1,
        "remittance_id": str(remittance_id),
        "recipient_user_id": str(actor.user_id),
        "count_required": required,
        "legacy_receive_allowed": not required,
    }
