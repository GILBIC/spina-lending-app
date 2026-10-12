"""Retained credit approval and consumption, inside the Treasury transaction."""

import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from psycopg.errors import ObjectNotInPrerequisiteState
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from .collector_surplus import (
    PREFIX,
    credit_change,
    independent,
    load,
    outcome,
    save,
    update,
)
from .treasury_authorization import (
    TreasuryConflict,
    TreasuryDenied,
    require_account,
    require_live_permission,
)
from .treasury_repository import identity, json_value


def available(conn):
    # The full migration installs this marker only with its operational and
    # accounting admission guards. Older deployments retain their blocker.
    return conn.execute(
        "SELECT to_regprocedure('treasury.collector_credit_application_ready()') "
        "IS NOT NULL AS available"
    ).fetchone()["available"]


def enabled():
    return (
        os.getenv("SPINA_COLLECTOR_SURPLUS_APPLICATION_ENABLED", "").lower() == "true"
    )


def lock_selection_accounts(conn, actor, receiving_account, application_id):
    """Discover both wallets before taking their existing sorted locks."""
    action = load(conn, "actions", application_id, lock=False)
    wallets = sorted({receiving_account, UUID(action["origin_account_id"])}, key=str)
    for wallet in wallets:
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,1))", (str(wallet),)
        )
    for wallet in wallets:
        require_application_account(conn, actor, wallet)
    return action


@contextmanager
def source_timezone(conn, approval):
    """Retain original digest serialization without changing any event instant."""
    previous = conn.execute("SHOW TIME ZONE").fetchone()["TimeZone"]
    selected = approval["source_timezone"]
    try:
        conn.execute("SELECT set_config('TimeZone',%s,true)", (selected,))
        yield
    finally:
        if conn.info.transaction_status != TransactionStatus.INERROR:
            conn.execute("SELECT set_config('TimeZone',%s,true)", (previous,))


def approval_snapshot(action):
    return dict(
        action,
        created_at=datetime.fromisoformat(action["created_at"])
        .astimezone(timezone.utc)
        .isoformat(),
    )


def require_application_account(conn, actor, wallet):
    """New accounting-backed consumption always requires a current private grant."""
    require_account(conn, actor, wallet, PREFIX + "settle", private=True)
    require_live_permission(conn, actor, PREFIX + "settle")
    if not conn.execute(
        "SELECT 1 FROM treasury.account_access WHERE account_id=%s AND user_id=%s "
        "AND enabled AND private_history AND %s=ANY(permissions) FOR SHARE",
        (wallet, actor.user_id, PREFIX + "settle"),
    ).fetchone():
        raise TreasuryDenied("Current private authority to both accounts is required.")


def require_read_scope(
    conn, actor, *, accounts=None, credit_id=None, remittance_id=None, approval=None
):
    """Check every retained application scope after computing a private read."""
    wallets = set()
    if approval:
        wallets.update(
            (UUID(approval["account_id"]), UUID(approval["origin_account_id"]))
        )
    if accounts or credit_id or remittance_id:
        rows = conn.execute(
            "SELECT a.account_id,(a.payload->>'origin_account_id')::uuid AS origin "
            "FROM treasury.collector_actions a WHERE a.payload->>'kind'='application' "
            "AND (a.account_id=ANY(%s::uuid[]) OR (a.payload->>'origin_account_id')::uuid=ANY(%s::uuid[]) OR a.credit_id=%s OR a.payload->>'remittance_id'=%s)",
            (
                accounts or [],
                accounts or [],
                credit_id,
                str(remittance_id) if remittance_id else None,
            ),
        ).fetchall()
        for row in rows:
            wallets.update((row["account_id"], row["origin"]))
    if not wallets:
        return
    require_live_permission(conn, actor, PREFIX + "view")
    for wallet in sorted(wallets, key=str):
        if not conn.execute(
            "SELECT 1 FROM treasury.account_access WHERE account_id=%s AND user_id=%s "
            "AND enabled AND private_history AND %s=ANY(permissions) FOR SHARE",
            (wallet, actor.user_id, PREFIX + "view"),
        ).fetchone():
            raise TreasuryDenied(
                "Current private authority to every contributing account is required."
            )


def _credit(service, conn, actor, credit_id):
    credit = load(conn, "credits", credit_id)
    independent(actor, credit)
    require_application_account(conn, actor, UUID(credit["account_id"]))
    if (
        credit["frozen"]
        or not credit.get("case_id")
        or credit.get("opening_anchor_id")
        or Decimal(credit["reclassified_amount"]) != 0
        or not conn.execute(
            "SELECT treasury.collector_application_credit_valid(%s) AS valid",
            (credit_id,),
        ).fetchone()["valid"]
    ):
        raise TreasuryConflict(
            "Current original Collector credit evidence is required."
        )
    try:
        with conn.transaction():
            recognition = conn.execute(
                "SELECT accounting.collector_liability_prerequisite('recognition',"
                "(SELECT id FROM treasury.collector_entries WHERE credit_id=%s "
                "AND payload->>'kind'='recognition'),"
                "(clock_timestamp() AT TIME ZONE 'Asia/Manila')::date) AS proof",
                (credit_id,),
            ).fetchone()["proof"]
    except ObjectNotInPrerequisiteState:
        raise TreasuryConflict(
            "Current exact posted recognition is required before applying credit."
        ) from None
    for evidence in recognition["evidence"]:
        service.store.read(
            UUID(evidence["id"]), evidence["sha256"], evidence["byte_count"]
        )
    return credit


def _book_scope(conn, *wallets):
    try:
        with conn.transaction():
            for wallet in sorted(set(wallets), key=str):
                conn.execute(
                    "SELECT accounting.require_book_treasury_account(%s)", (wallet,)
                )
    except ObjectNotInPrerequisiteState:
        raise TreasuryConflict(
            "Both accounts require the same configured accounting book and compatible ownership."
        ) from None


def reserve(service, conn, actor, account, command, credit, request):
    from .collector_settlement import preview
    from .treasury_models import SettlementPreview

    if not enabled():
        return outcome(
            credit,
            "credit",
            "blocked_adapter",
            blocked=True,
            request=request,
            source_account_id=credit["account_id"],
            blockers=[
                {
                    "code": "collector_application_disabled",
                    "message": "New Collector credit applications are disabled.",
                }
            ],
        )
    try:
        _book_scope(conn, account["id"], UUID(credit["account_id"]))
    except TreasuryConflict as error:
        return outcome(
            credit,
            "credit",
            "blocked_adapter",
            blocked=True,
            request=request,
            source_account_id=credit["account_id"],
            blockers=[
                {"code": "collector_application_book_required", "message": str(error)}
            ],
        )
    current = _credit(service, conn, actor, UUID(credit["id"]))
    if current["version"] != command.credit_version:
        raise TreasuryConflict("Collector credit changed; review its current version.")
    require_application_account(conn, actor, account["id"])
    review = preview(
        service,
        conn,
        actor,
        command.remittance_id,
        SettlementPreview(
            account_id=account["id"], expected_version=account["version"]
        ),
    )
    amount = Decimal(command.amount)
    if (
        not review["can_count"]
        or review["source_digest"] != command.source_digest
        or review["collector_user_id"] != current["collector_user_id"]
        or Decimal(review["refund_due_total"]) != 0
        or not 0 < amount <= Decimal(review["gross_obligation"])
    ):
        raise TreasuryConflict(
            "Exact pending custody without refunds or disputes is required."
        )
    if conn.execute(
        "SELECT 1 FROM treasury.collector_actions WHERE payload->>'kind'='application' "
        "AND payload->>'remittance_id'=%s AND payload->>'status'<>'cancelled'",
        (str(command.remittance_id),),
    ).fetchone():
        raise TreasuryConflict(
            "This remittance already has a reserved or applied credit."
        )
    current = credit_change(conn, current, reserved_amount=amount)
    request = update(conn, "requests", request, {"status": "approved"})
    approved = save(
        conn,
        "actions",
        account,
        UUID(current["collector_user_id"]),
        identity(command.request_id, "action"),
        {
            "kind": "application",
            "credit_id": current["id"],
            "exception_id": None,
            "collector_request_id": request["id"],
            "origin_account_id": current["account_id"],
            "paying_account_id": str(account["id"]),
            "remittance_id": str(command.remittance_id),
            "recipient_user_id": str(actor.user_id),
            "approved_by_user_id": str(actor.user_id),
            "source_digest": command.source_digest,
            "source_timezone": conn.execute("SHOW TIME ZONE").fetchone()["TimeZone"],
            "amount": amount,
            "destination": None,
            "status": "reserved",
            "event_id": None,
            "event_version": None,
            "acknowledgment_id": None,
            "evidence_id": str(command.evidence_id),
            "reason": command.reason,
        },
    )
    return outcome(
        approved,
        "action_record",
        "reserved",
        credit=current,
        request=request,
        source_account_id=current["account_id"],
    )


def review_selection(
    service, conn, actor, account, remittance, digest, gross, refund, command
):
    if not available(conn) or not enabled():
        raise TreasuryConflict(
            "Protected Collector credit application is not installed."
        )
    action = load(
        conn,
        "actions",
        command.credit_application_id,
        command.credit_application_version,
    )
    independent(actor, action)
    if (
        action["kind"] != "application"
        or action["status"] != "reserved"
        or action["account_id"] != str(account["id"])
        or action["paying_account_id"] != str(account["id"])
        or action["ledger_context_id"] != str(account["ledger_context_id"])
        or action.get("remittance_id") != str(remittance["id"])
        or action.get("recipient_user_id") != str(actor.user_id)
        or action["collector_user_id"] != str(remittance["collector_user_id"])
        or action.get("source_digest") != digest
        or action["event_id"] is not None
    ):
        raise TreasuryConflict("The exact current reserved application is required.")
    credit = _credit(service, conn, actor, UUID(action["credit_id"]))
    amount = Decimal(action["amount"])
    if (
        credit["account_id"] != action["origin_account_id"]
        or credit["ledger_context_id"] != action["ledger_context_id"]
        or credit["collector_user_id"] != action["collector_user_id"]
        or not 0 < amount <= gross
        or refund != 0
        or Decimal(credit["reserved_amount"]) < amount
        or Decimal(credit["outstanding_amount"]) < amount
    ):
        raise TreasuryConflict("Reserved credit capacity or source scope changed.")
    request = load(conn, "requests", UUID(action["collector_request_id"]))
    if (
        request["kind"] != "application"
        or request["status"] != "approved"
        or request["credit_id"] != credit["id"]
        or request["remittance_id"] != action["remittance_id"]
        or request["source_digest"] != digest
        or Decimal(request["amount"]) != amount
        or request["collector_user_id"] != action["collector_user_id"]
    ):
        raise TreasuryConflict("Original Collector request no longer matches approval.")
    require_application_account(conn, actor, account["id"])
    service.evidence(conn, account["id"], UUID(action["evidence_id"]), {"recipient"})
    _book_scope(conn, account["id"], UUID(credit["account_id"]))
    selected = json_value(approval_snapshot(action))
    review_digest = hashlib.sha256(
        json.dumps(
            {"remittance_source_digest": digest, "approved_application": selected},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return selected, review_digest


def consume(
    service, conn, actor, account, command, count, approval, settlement, accepted_at
):
    """Record only the liability discharge; the caller owns actual cash recording."""
    action = load(conn, "actions", UUID(approval["id"]), approval["version"])
    if approval_snapshot(action) != approval or action["status"] != "reserved":
        raise TreasuryConflict("Reviewed application changed before acceptance.")
    credit = _credit(service, conn, actor, UUID(action["credit_id"]))
    amount = Decimal(action["amount"])
    credit = credit_change(conn, credit, reserved_amount=-amount, applied_amount=amount)
    entry = save(
        conn,
        "entries",
        account,
        UUID(action["collector_user_id"]),
        identity(command.request_id, "application-entry"),
        {
            "credit_id": credit["id"],
            "kind": "application",
            "amount": amount,
            "action_id": action["id"],
            "settlement_id": settlement["id"],
            "accepted_at": accepted_at,
            "evidence_id": count["evidence_id"],
            "reason": "Reserved Collector credit consumed at accepted custody settlement.",
        },
    )
    conn.execute(
        "INSERT INTO treasury.collector_credit_applications "
        "(id,action_id,credit_id,settlement_id,count_id,remittance_id,origin_account_id,"
        "account_id,ledger_context_id,collector_user_id,amount,accepted_at,approval_snapshot) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            UUID(entry["id"]),
            UUID(action["id"]),
            UUID(credit["id"]),
            UUID(settlement["id"]),
            UUID(count["id"]),
            UUID(count["remittance_id"]),
            UUID(credit["account_id"]),
            account["id"],
            account["ledger_context_id"],
            UUID(action["collector_user_id"]),
            amount,
            accepted_at,
            Jsonb(approval),
        ),
    )
    action = update(conn, "actions", action, {"status": "applied"})
    return {
        "credit": credit,
        "action_record": action,
        "application_entry": entry,
        "source_account_id": credit["account_id"],
    }
