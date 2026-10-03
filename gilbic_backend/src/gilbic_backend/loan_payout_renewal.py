"""Final renewal activation after independent receipt and Management proof review."""

from decimal import Decimal
from uuid import UUID

from psycopg.types.json import Jsonb

from .loan_payouts import check_account, load, replay_authority
from .renewal_workflow_api import _renewal_row
from .treasury_authorization import TreasuryConflict, require_live_permission
from .treasury_repository import json_value


def complete(service, conn, actor, account, command):
    require_live_permission(conn, actor, "renewal.manage")
    row = load(conn, command.payout_id)
    check_account(account, row)
    if (
        row["source_kind"] != "renewal"
        or row["version"] != command.payout_version
        or row["status"] != "recipient_confirmed"
        or not command.proof_review_confirmed
        or Decimal(command.reviewed_amount) != row["amount"]
    ):
        raise TreasuryConflict(
            "Review the current funded renewal, exact net proceeds and actual borrower receipt proof."
        )
    replay_authority(service, conn, actor, row)
    renewal = _renewal_row(conn.cursor(), request_id=row["renewal_request_id"])
    acknowledgment = row["payload"].get("acknowledgments", {}).get("borrower", {})
    if not acknowledgment.get("received") or acknowledgment.get("actor_user_id") != str(
        renewal["borrower_user_id"]
    ):
        raise TreasuryConflict(
            "The named borrower must independently confirm the actual proceeds first."
        )
    from dataclasses import replace

    from .loan_payout_acknowledgments import own_scope

    # Every positive attestation still belongs to an active, authorized actor/device.
    for stage in (
        ("recipient", "borrower_handover", "borrower")
        if row["destination"] == "collector"
        else ("borrower",)
    ):
        attestation = row["payload"].get("acknowledgments", {}).get(stage, {})
        if not attestation.get("received"):
            raise TreasuryConflict(
                "Every required independent receipt and handover must be confirmed."
            )
        own_scope(
            conn,
            replace(
                actor,
                user_id=UUID(attestation["actor_user_id"]),
                registered_device_id=UUID(attestation["device_id"]),
            ),
            row,
            stage,
        )
    if (
        str(renewal["old_loan_status"]).lower() != "paid"
        or Decimal(renewal["remaining_balance"] or 0) != 0
    ):
        raise TreasuryConflict(
            "Complete the controlled old-loan settlement before renewal activation."
        )
    service.evidence(conn, account["id"], command.evidence_id, {"recipient"})
    source = row["source_snapshot"]["source"]
    conn.execute(
        """update lending.client_renewal_requests set renewal_offset_amount=%s,net_release_amount=%s,
        new_loan_id=%s,amount_locked_at=coalesce(amount_locked_at,now()),handover_proof_status='approved',
        activation_status='active',updated_at=now() where id=%s""",
        (
            Decimal(source["offset_amount"]),
            row["amount"],
            row["loan_id"],
            row["renewal_request_id"],
        ),
    )
    payload = {
        **row["payload"],
        "borrower_handover_status": "confirmed",
        "proof_review": json_value(
            {
                "evidence_id": command.evidence_id,
                "reviewed_by": actor.user_id,
                "device_id": actor.registered_device_id,
                "reviewed_at": service.clock(),
                "reason": command.reason,
            }
        ),
    }
    conn.execute(
        "update treasury.loan_payouts set status='completed',payload=%s,version=version+1 where id=%s",
        (Jsonb(payload), row["id"]),
    )
    return (
        row["id"],
        row["version"] + 1,
        {"payout": json_value(load(conn, row["id"]))},
        "saved",
    )
