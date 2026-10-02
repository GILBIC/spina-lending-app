"""Explicit adapter blockers and independently evidenced opening liability anchors."""

import hashlib
from decimal import Decimal
from uuid import UUID

from .collector_surplus import independent, load, outcome, save, update
from .treasury_authorization import TreasuryConflict, require_owner
from .treasury_repository import identity


def resolution_action(service, conn, actor, account, command):
    tag = command.action
    if tag == "collector_surplus_resolve_source":
        kind = "cases" if command.case_id else "credits"
        row = load(
            conn,
            kind,
            command.case_id or command.credit_id,
            command.case_version or command.credit_version,
        )
        independent(actor, row)
        if str(account["id"]) != row["account_id"]:
            raise TreasuryConflict("Exact originating account is required.")
        service.evidence(
            conn, account["id"], command.evidence_id, {"recipient", "correction"}
        )
        if kind == "cases" and command.source_digest != row["source_digest"]:
            raise TreasuryConflict("Source digest changed.")
        recovery = kind == "credits" and (
            Decimal(row["returned_amount"])
            + Decimal(row["applied_amount"])
            + Decimal(row["reserved_amount"])
            > 0
        )
        if recovery:
            row = update(
                conn, kind, row, {"frozen": True, "status": "recovery_required"}
            )
        return outcome(
            row,
            "case" if kind == "cases" else "credit",
            "recovery_required" if recovery else "blocked_adapter",
            blocked=True,
            blockers=[
                {
                    "code": "collector_historical_source_unavailable",
                    "message": "Protected historical source correction and received-cash attribution are unavailable. Actual cash, payout and borrower evidence remain unchanged.",
                }
            ],
        )
    require_owner(conn, actor)
    if account["kind"] != "physical_cash":
        raise TreasuryConflict(
            "Opening Collector liabilities require an evidenced physical-cash opening."
        )
    if tag == "collector_surplus_opening_prepare":
        if (
            not command.overlap_review_acknowledged
            or actor.user_id == command.collector_user_id
        ):
            raise TreasuryConflict("Independent overlap/source review is required.")
        opening = conn.execute(
            "select * from treasury.opening_positions where id=%s and account_id=%s for update",
            (command.opening_id, account["id"]),
        ).fetchone()
        if (
            not opening
            or opening["version"] != command.opening_version
            or opening["status"] != "active"
            or Decimal(command.amount) > opening["amount"]
        ):
            raise TreasuryConflict(
                "Exact active opening/version and supported amount are required."
            )
        if not conn.execute(
            "select 1 from core.users u join core.user_roles ur on ur.user_id=u.id join core.roles r on r.id=ur.role_id where u.id=%s and u.status='active' and r.code='collector' for share of u,ur,r",
            (command.collector_user_id,),
        ).fetchone():
            raise TreasuryConflict("Current actual Collector is required.")
        opening_capacity(
            conn, account, opening, command.collector_user_id, Decimal(command.amount)
        )
        service.evidence(conn, account["id"], command.evidence_id, {"opening"})
        row = save(
            conn,
            "openings",
            account,
            command.collector_user_id,
            identity(command.request_id, "anchor"),
            {
                "anchor_kind": command.anchor_kind,
                "opening_id": str(command.opening_id),
                "opening_version": command.opening_version,
                "amount": command.amount,
                "cutoff": opening["cutoff"],
                "status": "draft",
                "evidence_id": str(command.evidence_id),
                "reason": command.reason,
            },
        )
        return outcome(row, "opening_anchor", "opening_prepared")
    row = load(conn, "openings", command.anchor_id, command.anchor_version)
    if row["account_id"] != str(account["id"]) or row["status"] != "draft":
        raise TreasuryConflict("Current draft opening anchor is required.")
    opening = conn.execute(
        "select * from treasury.opening_positions where id=%s and account_id=%s for update",
        (UUID(row["opening_id"]), account["id"]),
    ).fetchone()
    if (
        not opening
        or opening["version"] != row["opening_version"]
        or opening["status"] != "active"
    ):
        raise TreasuryConflict("Opening changed before anchor activation.")
    opening_capacity(
        conn,
        account,
        opening,
        UUID(row["collector_user_id"]),
        Decimal(row["amount"]),
        UUID(row["id"]),
    )
    service.evidence(conn, account["id"], UUID(row["evidence_id"]), {"opening"})
    row = update(conn, "openings", row, {"status": "active"})
    if row.get("anchor_kind", "credit") == "pending_excess":
        digest = hashlib.sha256(
            (
                row["id"] + row["opening_id"] + row["cutoff"] + row["evidence_id"]
            ).encode()
        ).hexdigest()
        case = save(
            conn,
            "cases",
            account,
            UUID(row["collector_user_id"]),
            identity(command.request_id, "opening-case"),
            {
                "settlement_id": None,
                "opening_id": row["opening_id"],
                "opening_anchor_id": row["id"],
                "received_excess_amount": row["amount"],
                "unidentified_amount": row["amount"],
                "source_digest": digest,
                "status": "pending_identification",
                "resolutions": [],
            },
        )
        return outcome(row, "opening_anchor", "opening_activated", case=case)
    credit = save(
        conn,
        "credits",
        account,
        UUID(row["collector_user_id"]),
        identity(command.request_id, "opening-credit"),
        {
            "case_id": None,
            "opening_anchor_id": row["id"],
            "origin_account_id": row["account_id"],
            "recognized_amount": row["amount"],
            "reclassified_amount": "0.00",
            "returned_amount": "0.00",
            "applied_amount": "0.00",
            "reserved_amount": "0.00",
            "outstanding_amount": row["amount"],
            "available_amount": row["amount"],
            "frozen": False,
            "status": "outstanding",
            "entries": [],
        },
    )
    save(
        conn,
        "entries",
        account,
        UUID(row["collector_user_id"]),
        identity(command.request_id, "opening-entry"),
        {
            "credit_id": credit["id"],
            "kind": "opening",
            "amount": row["amount"],
            "action_id": None,
            "evidence_id": row["evidence_id"],
        },
    )
    return outcome(row, "opening_anchor", "opening_activated", credit=credit)


def opening_capacity(conn, account, opening, collector, amount, anchor_id=None):
    # Account and opening row are already held; all new acceptance/anchors take
    # the same account lock before source rows, so this recheck is serializable.
    overlaps = conn.execute(
        """select 1 from treasury.collector_settlements s join treasury.collector_counts c on c.id=s.count_id
      where s.account_id=%s and s.collector_user_id=%s and (c.payload->>'counted_at')::timestamptz<=%s limit 1""",
        (account["id"], collector, opening["cutoff"]),
    ).fetchone()
    if overlaps:
        raise TreasuryConflict(
            "Opening overlaps actually received pre-cutoff Collector cash, even if entered later."
        )
    used = conn.execute(
        """select coalesce(sum((payload->>'amount')::numeric),0) as used from treasury.collector_openings
       where opening_id=%s and (%s::uuid is null or id<>%s)""",
        (opening["id"], anchor_id, anchor_id),
    ).fetchone()["used"]
    if used + amount > opening["amount"]:
        raise TreasuryConflict(
            "Combined opening liabilities exceed the evidenced opening cash capacity."
        )
