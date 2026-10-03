"""Recipient-only attestations. No wallet history or arbitrary recipient authority."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from psycopg.types.json import Jsonb

from .loan_payouts import load, replay_authority, verified_debit
from .treasury_authorization import TreasuryConflict, TreasuryDenied, require_actor
from .treasury_repository import json_value


def own_scope(conn, actor, row, stage):
    require_actor(conn, actor)
    borrower = conn.execute(
        "select user_id,area,status from lending.clients where id=%s for share",
        (row["client_id"],),
    ).fetchone()
    collector = stage == "borrower_handover" or (
        stage == "recipient" and row["destination"] == "collector"
    )
    role = "collector" if collector else "client"
    expected = row["collector_user_id"] if collector else borrower["user_id"]
    if (
        borrower["status"] != "active"
        or actor.user_id != expected
        or not conn.execute(
            """select 1 from core.user_roles ur join core.roles r on r.id=ur.role_id
                where ur.user_id=%s and r.code=%s for share of ur,r""",
            (actor.user_id, role),
        ).fetchone()
    ):
        raise TreasuryDenied(
            "Only the current named recipient or borrower may acknowledge this payout."
        )
    if collector and (
        row["destination"] != "collector"
        or conn.execute(
            "select lending.collector_area_owner(%s) as id",
            (borrower["area"] or "",),
        ).fetchone()["id"]
        != actor.user_id
    ):
        raise TreasuryDenied(
            "Only the current assigned Collector may record this handover."
        )


def own_account(conn, actor, payout_id, stage, *, lock=True):
    row = load(conn, payout_id, lock=False)
    own_scope(conn, actor, row, stage)
    account = conn.execute(
        "select * from treasury.accounts where id=%s for update"
        if lock
        else "select * from treasury.accounts where id=%s",
        (row["account_id"],),
    ).fetchone()
    if account is None or not account["active"]:
        raise TreasuryDenied("The payout funding account is unavailable.")
    return account


def projection(row):
    return json_value(
        {
            key: row[key]
            for key in (
                "id",
                "version",
                "source_kind",
                "status",
                "amount",
                "destination",
            )
        }
        | {
            "label": row["source_snapshot"]["source"]["label"],
            "acknowledgments": {
                stage: {
                    key: value[key]
                    for key in (
                        "received",
                        "reviewed_amount",
                        "receipt_method",
                        "acknowledged_at",
                    )
                }
                for stage, value in row["payload"].get("acknowledgments", {}).items()
            },
            "borrower_handover_status": row["payload"].get(
                "borrower_handover_status", "pending"
            ),
        }
    )


def replay(service, conn, actor, outcome):
    row = load(conn, UUID(outcome["result"]["target_id"]))
    own_scope(conn, actor, row, outcome["result"]["result"]["stage"])
    replay_authority(service, conn, actor, row, staff_authority=False)
    return outcome["result"]


def acknowledge(service, conn, actor, account, command):
    row = load(conn, command.payout_id)
    own_scope(conn, actor, row, command.stage)
    if (
        row["version"] != command.payout_version
        or row["status"] != "recipient_confirmed"
    ):
        raise TreasuryConflict(
            "Review the current payout with verified destination receipt first."
        )
    replay_authority(service, conn, actor, row, staff_authority=False)
    event = verified_debit(service, conn, account, row, row["event_id"])
    acknowledgments = dict(row["payload"].get("acknowledgments", {}))
    if command.stage in acknowledgments and acknowledgments[command.stage]["received"]:
        raise TreasuryConflict(
            "This stage already has an actual receipt acknowledgment."
        )
    prior = (
        "recipient"
        if command.stage == "borrower_handover"
        else "borrower_handover"
        if command.stage == "borrower" and row["destination"] == "collector"
        else None
    )
    if prior and not acknowledgments.get(prior, {}).get("received"):
        raise TreasuryConflict(
            "The preceding actual receipt or handover must be acknowledged first."
        )
    earliest = (
        datetime.fromisoformat(acknowledgments[prior]["acknowledged_at"])
        if prior
        else event["effective_at"]
    )
    if (
        Decimal(command.reviewed_amount) != row["amount"]
        or not earliest <= command.acknowledged_at <= service.clock()
    ):
        raise TreasuryConflict(
            "The actual amount and receipt time must match the payout and preceding handover."
        )
    if (
        command.stage == "recipient" or row["destination"] == "borrower"
    ) and command.receipt_method != account["kind"]:
        raise TreasuryConflict(
            "Recipient acknowledgment must use the actual wallet or bank method."
        )
    if (
        command.stage == "borrower"
        and prior
        and command.receipt_method != acknowledgments[prior]["receipt_method"]
    ):
        raise TreasuryConflict(
            "The borrower's receipt method must match the actual handover."
        )
    acknowledgments[command.stage] = json_value(
        {
            "received": command.received,
            "reviewed_amount": command.reviewed_amount,
            "receipt_method": command.receipt_method,
            "acknowledged_at": command.acknowledged_at,
            "attestation": command.attestation,
            "actor_user_id": actor.user_id,
            "device_id": actor.registered_device_id,
        }
    )
    payload = {**row["payload"], "acknowledgments": acknowledgments}
    conn.execute(
        "update treasury.loan_payouts set payload=%s,version=version+1 where id=%s",
        (Jsonb(payload), row["id"]),
    )
    return (
        row["id"],
        row["version"] + 1,
        {"payout": projection(load(conn, row["id"])), "stage": command.stage},
        "saved",
    )
