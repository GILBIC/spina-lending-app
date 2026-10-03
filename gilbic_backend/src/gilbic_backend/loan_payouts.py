"""Reviewed payout identity shared by Treasury and protected loan completion."""

import hashlib
import json
from dataclasses import replace
from decimal import Decimal
from uuid import UUID

from psycopg.types.json import Jsonb

from .loan_payout_sources import current_source
from .treasury_authorization import TreasuryConflict, require_account, require_entry
from .treasury_models import LoanPayoutPreview
from .treasury_repository import identity, json_value


def preview_in_transaction(service, conn, actor, account, command):
    if account["kind"] not in {"gcash", "bank"}:
        raise TreasuryConflict(
            "Select the specific wallet or bank that actually funds this payout."
        )
    if account["version"] != command.expected_version:
        raise TreasuryConflict(
            "The funding account changed; review its current version."
        )
    source = current_source(conn, actor, command)
    if Decimal(source["amount"]) <= 0:
        raise TreasuryConflict(
            "A payout requires positive net proceeds; zero-net renewal uses its protected settlement workflow."
        )
    snapshot = json_value(
        {
            **command.model_dump(exclude={"request_id", "action", "source_digest"}),
            "ledger_context_id": account["ledger_context_id"],
            "source": source,
            "funding_method": account["kind"],
        }
    )
    digest = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "contract_version": 1,
        "actor": {
            "user_id": str(actor.user_id),
            "device_id": str(actor.registered_device_id),
        },
        "ledger_context_id": str(account["ledger_context_id"]),
        "source_kind": command.source_kind,
        "source_id": str(command.source_id),
        "destination": command.destination,
        "recipient_reference": command.recipient_reference,
        "amount": source["amount"],
        "payee_id": source["payee_id"],
        "payee_name": source["payee_name"],
        "client_id": source["client_id"],
        "collector_user_id": source["collector_user_id"],
        "label": source["label"],
        "account_id": str(account["id"]),
        "account_version": account["version"],
        "source_digest": digest,
        "source_snapshot": snapshot,
    }


def preview(service, actor, command):
    require_entry()
    with service.connect() as conn, conn.transaction():
        account = require_account(
            conn, actor, command.account_id, "treasury.disbursement.record"
        )
        return preview_in_transaction(service, conn, actor, account, command)


def load(conn, payout_id, *, lock=True):
    row = conn.execute(
        "select * from treasury.loan_payouts where id=%s for update"
        if lock
        else "select * from treasury.loan_payouts where id=%s",
        (payout_id,),
    ).fetchone()
    if row is None:
        raise TreasuryConflict("The reviewed loan payout is unavailable.")
    return row


def source_command(row):
    return LoanPayoutPreview.model_validate(
        {
            key: value
            for key, value in row["source_snapshot"].items()
            if key not in {"source", "ledger_context_id", "funding_method"}
        }
    )


def revalidate(conn, actor, row, *, staff_authority=True):
    kind = conn.execute(
        "select kind from treasury.accounts where id=%s", (row["account_id"],)
    ).fetchone()["kind"]
    if row["source_snapshot"].get("funding_method", kind) != kind:
        raise TreasuryConflict(
            "The original funding account method changed; review the retained payout."
        )
    source = current_source(
        conn,
        actor,
        source_command(row),
        released=row["status"] in {"completed", "cancelled"},
        staff_authority=staff_authority,
    )
    if source != row["source_snapshot"]["source"]:
        raise TreasuryConflict(
            "The approved source or its current destination changed; the original payout remains recorded."
        )


def replay_authority(service, conn, actor, row, *, staff_authority=True):
    from .loan_payout_acknowledgments import own_scope
    from .loan_payout_reads import staff_scope

    if row["status"] == "cancelled":
        from .loan_payout_reads import staff_scope

        if staff_authority:
            staff_scope(conn, actor, row["source_kind"])
        return
    revalidate(conn, actor, row, staff_authority=staff_authority)
    for stage, acknowledgment in row["payload"].get("acknowledgments", {}).items():
        if acknowledgment.get("received"):
            own_scope(
                conn,
                replace(
                    actor,
                    user_id=UUID(acknowledgment["actor_user_id"]),
                    registered_device_id=UUID(acknowledgment["device_id"]),
                ),
                row,
                stage,
            )
    if row["event_id"]:
        account = conn.execute(
            "select * from treasury.accounts where id=%s", (row["account_id"],)
        ).fetchone()
        verified_debit(service, conn, account, row, row["event_id"])
    for key in ("recipient_confirmation", "borrower_receipt", "proof_review"):
        receipt = row["payload"].get(key)
        if not receipt:
            continue
        reviewer = replace(
            actor,
            user_id=UUID(
                receipt["witness_id"]
                if key == "borrower_receipt"
                else receipt["reviewed_by"]
            ),
            registered_device_id=UUID(receipt["device_id"]),
        )
        require_account(
            conn,
            reviewer,
            row["account_id"],
            "treasury.disbursement.record",
            lock=False,
        )
        staff_scope(conn, reviewer, row["source_kind"])
        service.evidence(
            conn, row["account_id"], UUID(receipt["evidence_id"]), {"recipient"}
        )
        if key == "borrower_receipt" and row["source_kind"] == "first_loan":
            from .first_loan_repository import require_evidence
            from .office_review_evidence_repository import OfficeReviewEvidenceConflict

            try:
                require_evidence(
                    conn.cursor(),
                    evidence_reference=receipt["office_evidence_reference"],
                    actor_user_id=UUID(receipt["witness_id"]),
                    client_id=row["client_id"],
                    purpose="borrower_payout_received",
                    subject_id=row["id"],
                    review_snapshot=receipt["snapshot"],
                )
            except OfficeReviewEvidenceConflict as error:
                raise TreasuryConflict(str(error)) from error


def action(service, conn, actor, account, command):
    if command.action == "loan_payout_cancel":
        row = load(conn, command.payout_id)
        check_account(account, row)
        if (
            row["version"] != command.payout_version
            or row["status"] != "prepared"
            or row["event_id"]
        ):
            raise TreasuryConflict(
                "Only an unchanged unfunded payout preparation can be cancelled."
            )
        # A failed link still leaves an actual debit requiring investigation.
        if conn.execute(
            """select 1 from treasury.outcomes where action='disbursement_record'
            and result->'result'->'source_link'->>'requested_payout_id'=%s limit 1""",
            (str(row["id"]),),
        ).fetchone():
            raise TreasuryConflict(
                "An observed debit references this payout; reconcile it before replacing the preparation."
            )
        from .loan_payout_reads import staff_scope

        staff_scope(conn, actor, row["source_kind"])
        conn.execute(
            "update treasury.loan_payouts set status='cancelled',payload=%s,version=version+1 where id=%s",
            (Jsonb({"reason": command.reason}), row["id"]),
        )
        return (
            row["id"],
            row["version"] + 1,
            {"payout": json_value(load(conn, row["id"]))},
            "saved",
        )
    if command.action == "loan_payout_acknowledge":
        from .loan_payout_acknowledgments import acknowledge

        return acknowledge(service, conn, actor, account, command)
    if command.action == "loan_payout_renewal_complete":
        from .loan_payout_renewal import complete

        return complete(service, conn, actor, account, command)
    if command.action == "loan_payout_recipient_confirm":
        return confirm_recipient(service, conn, actor, account, command)
    if command.action == "loan_payout_first_loan_complete":
        from .loan_payout_first_loan import complete

        return complete(service, conn, actor, account, command)
    reviewed = preview_in_transaction(service, conn, actor, account, command)
    if reviewed["source_digest"] != command.source_digest:
        raise TreasuryConflict("The reviewed payout source or destination changed.")
    source = reviewed["source_snapshot"]["source"]
    existing = conn.execute(
        "select id from treasury.loan_payouts where source_kind=%s and source_id=%s and status<>'cancelled' for update",
        (command.source_kind, command.source_id),
    ).fetchone()
    if existing:
        raise TreasuryConflict(
            "This source already has an active payout. Recover that exact payout before starting another."
        )
    target = identity(command.request_id, "loan-payout")
    conn.execute(
        """insert into treasury.loan_payouts(id,account_id,ledger_context_id,source_kind,source_id,
        loan_id,renewal_request_id,client_id,collector_user_id,destination,recipient_reference,amount,
        source_digest,source_snapshot,prepared_by,prepared_device_id)
        values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            target,
            account["id"],
            account["ledger_context_id"],
            command.source_kind,
            command.source_id,
            UUID(source["loan_id"]),
            command.source_id if command.source_kind == "renewal" else None,
            UUID(source["client_id"]),
            UUID(source["collector_user_id"]) if source["collector_user_id"] else None,
            command.destination,
            command.recipient_reference,
            Decimal(source["amount"]),
            command.source_digest,
            Jsonb(reviewed["source_snapshot"]),
            actor.user_id,
            actor.registered_device_id,
        ),
    )
    return target, 1, {"payout": json_value(load(conn, target))}, "saved"


def check_account(account, row):
    if (
        row["account_id"] != account["id"]
        or row["ledger_context_id"] != account["ledger_context_id"]
    ):
        raise TreasuryConflict(
            "This payout belongs to a different funding account or context."
        )


def verified_debit(service, conn, account, row, event_id):
    event = conn.execute(
        "select * from treasury.events where id=%s for update", (event_id,)
    ).fetchone()
    if (
        event is None
        or event["account_id"] != account["id"]
        or event["ledger_context_id"] != account["ledger_context_id"]
        or event["direction"] != "debit"
        or event["amount"] != row["amount"]
        or not event["reference"]
    ):
        raise TreasuryConflict("The exact verified payout debit is required.")
    if conn.execute(
        "select 1 from treasury.event_revisions where event_id=%s and action='correct'",
        (event_id,),
    ).fetchone():
        raise TreasuryConflict("A corrected debit cannot fund this payout.")
    service.evidence(conn, account["id"], event["evidence_id"], {"recipient"})
    return event


def link_debit(service, conn, actor, account, event, command):
    if not command.source_id or command.source_version is None:
        raise TreasuryConflict("Select the exact reviewed loan payout and version.")
    row = load(conn, command.source_id)
    check_account(account, row)
    expected_purpose = (
        "loan_release" if row["source_kind"] == "first_loan" else "renewal"
    )
    expected_payee = (
        row["collector_user_id"]
        if row["destination"] == "collector"
        else row["client_id"]
    )
    if (
        command.purpose != expected_purpose
        or command.source_version != row["version"]
        or row["status"] != "prepared"
        or row["event_id"] is not None
        or command.payee_id != expected_payee
        or Decimal(command.amount) != row["amount"]
    ):
        raise TreasuryConflict(
            "The current unfunded payout, exact recipient and whole approved net proceeds are required."
        )
    revalidate(conn, actor, row)
    verified_debit(service, conn, account, row, event["id"])
    if conn.execute(
        "select 1 from treasury.source_links where event_id=%s", (event["id"],)
    ).fetchone():
        raise TreasuryConflict("This debit already funds a protected source.")
    conn.execute(
        """insert into treasury.source_links(id,event_id,ledger_context_id,source_kind,source_id,source_version,linked_amount)
        values(%s,%s,%s,'loan_payout_funding',%s,%s,%s)""",
        (
            identity(event["id"], "source-link"),
            event["id"],
            account["ledger_context_id"],
            row["id"],
            row["version"],
            row["amount"],
        ),
    )
    conn.execute(
        """update treasury.loan_payouts set status='debited',event_id=%s,version=version+1,
        payload=%s where id=%s""",
        (event["id"], Jsonb({"borrower_handover_status": "pending"}), row["id"]),
    )
    return {
        "status": "funded_pending_recipient",
        "payout_id": str(row["id"]),
        "payout_version": row["version"] + 1,
        "destination": row["destination"],
    }


def confirm_recipient(service, conn, actor, account, command):
    row = load(conn, command.payout_id)
    check_account(account, row)
    if row["version"] != command.payout_version or row["status"] != "debited":
        raise TreasuryConflict(
            "Review the current funded payout awaiting recipient confirmation."
        )
    revalidate(conn, actor, row)
    event = verified_debit(service, conn, account, row, row["event_id"])
    if (
        Decimal(command.reviewed_amount) != row["amount"]
        or not event["effective_at"] <= command.acknowledged_at <= service.clock()
    ):
        raise TreasuryConflict(
            "Recipient evidence must match the exact net amount and actual receipt time after the debit."
        )
    service.evidence(conn, account["id"], command.evidence_id, {"recipient"})
    payload = {
        **row["payload"],
        "recipient_confirmation": json_value(
            {
                "evidence_id": command.evidence_id,
                "received": command.received,
                "acknowledged_at": command.acknowledged_at,
                "reviewed_amount": command.reviewed_amount,
                "attestation": command.recipient_attestation,
                "reviewed_by": actor.user_id,
                "device_id": actor.registered_device_id,
            }
        ),
    }
    conn.execute(
        "update treasury.loan_payouts set status=%s,payload=%s,version=version+1 where id=%s",
        (
            "recipient_confirmed" if command.received else "debited",
            Jsonb(payload),
            row["id"],
        ),
    )
    return (
        row["id"],
        row["version"] + 1,
        {"payout": json_value(load(conn, row["id"]))},
        "saved",
    )
