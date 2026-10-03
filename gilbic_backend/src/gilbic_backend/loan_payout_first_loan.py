"""Office-witnessed final borrower receipt using the protected first-loan source."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from psycopg.types.json import Jsonb

from . import first_loan_repository as source
from .loan_payouts import (
    check_account,
    load,
    revalidate,
    source_command,
    verified_debit,
)
from .treasury_authorization import TreasuryConflict, TreasuryDenied
from .treasury_repository import json_value


def complete(service, conn, actor, account, command):
    row = load(conn, command.payout_id)
    check_account(account, row)
    if (
        row["source_kind"] != "first_loan"
        or row["version"] != command.payout_version
        or row["status"] != "recipient_confirmed"
        or command.borrower_confirmed is not True
        or Decimal(command.reviewed_amount) != row["amount"]
    ):
        raise TreasuryConflict(
            "The named borrower must acknowledge the whole net proceeds of the current first-loan payout."
        )
    revalidate(conn, actor, row)
    event = verified_debit(service, conn, account, row, row["event_id"])
    recipient = row["payload"]["recipient_confirmation"]
    service.evidence(conn, account["id"], UUID(recipient["evidence_id"]), {"recipient"})
    if (
        not max(
            event["effective_at"], datetime.fromisoformat(recipient["acknowledged_at"])
        )
        <= command.acknowledged_at
        <= service.clock()
    ):
        raise TreasuryConflict(
            "The actual borrower receipt time must follow the debit and cannot be in the future."
        )
    if row["destination"] == "borrower" and command.receipt_method != account["kind"]:
        raise TreasuryConflict(
            "The direct borrower's receipt must match the actual wallet or bank payout method."
        )
    evidence = service.evidence(conn, account["id"], command.evidence_id, {"recipient"})
    reviewed = source_command(row)
    snapshot = json_value(
        {
            "scope": "first_loan_payout_receipt",
            "payout_id": row["id"],
            "source_digest": row["source_digest"],
            "loan_id": row["loan_id"],
            "client_id": row["client_id"],
            "packet_hash": reviewed.packet_hash,
            "authorization_id": reviewed.authorization_id,
            "amount": command.reviewed_amount,
            "receipt_method": command.receipt_method,
            "acknowledged_at": command.acknowledged_at,
            "attestation": command.borrower_attestation,
            "event_id": row["event_id"],
            "destination": row["destination"],
        }
    )
    try:
        with conn.cursor() as cursor:
            loan = source._load(cursor, row["loan_id"])
            receipt = source.capture_evidence(
                cursor,
                actor_user_id=actor.user_id,
                client_id=row["client_id"],
                cif_version_id=loan["cif_version_id"],
                application_id=UUID(loan["packet"]["application"]["application_id"]),
                application_version_id=loan["application_version_id"],
                purpose="borrower_payout_received",
                subject_id=row["id"],
                review_snapshot=snapshot,
                content=service.store.read(
                    evidence["id"], evidence["sha256"], evidence["byte_count"]
                ),
                media_type=evidence["media_type"],
                request_id=command.request_id,
            )
            result = source.release_in_transaction(
                conn,
                cursor,
                actor_user_id=actor.user_id,
                registered_device_id=actor.registered_device_id,
                loan_id=row["loan_id"],
                packet_hash=reviewed.packet_hash,
                authorization_id=reviewed.authorization_id,
                contract_evidence_reference=reviewed.contract_evidence_reference,
                cash_evidence_reference=receipt.evidence_reference,
                cash_amount=command.reviewed_amount,
                borrower_confirmed=command.borrower_confirmed,
                request_id=command.request_id,
                payout_receipt={
                    "payout_id": row["id"],
                    "method": command.receipt_method,
                    "snapshot": snapshot,
                },
            )
    except source.FirstLoanAccessDenied as error:
        raise TreasuryDenied(str(error)) from error
    except (source.FirstLoanConflict, source.OfficeReviewEvidenceConflict) as error:
        raise TreasuryConflict(str(error)) from error
    payload = {
        **row["payload"],
        "borrower_handover_status": "confirmed",
        "borrower_receipt": {
            "evidence_id": str(command.evidence_id),
            "snapshot": snapshot,
            "office_evidence_reference": receipt.evidence_reference,
            "witness_id": str(actor.user_id),
        },
        "source_receipt": result["release"],
    }
    conn.execute(
        "update treasury.loan_payouts set status='completed',payload=%s,version=version+1 where id=%s",
        (Jsonb(json_value(payload)), row["id"]),
    )
    return (
        row["id"],
        row["version"] + 1,
        {"payout": json_value(load(conn, row["id"]))},
        "saved",
    )
