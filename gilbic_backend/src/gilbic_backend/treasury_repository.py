"""Caller-owned transactions; operational movements, private outcomes and cutoffs.

Lock order: current user/device, request advisory key, account UUID order, receipt,
claim/source, loan state via protected adapter, reconciliation. No self HTTP calls.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid5

from psycopg import errors, sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .database import connect_database
from .office_review_evidence_storage import PrivateEvidenceStore
from .treasury_authorization import (
    TreasuryConflict,
    TreasuryDenied,
    TreasuryUnavailable,
    is_owner,
    readiness,
    require_account,
    require_actor,
    require_entry,
    require_live_permission,
    require_owner,
)
from .treasury_models import TreasuryResult, command_hash

NAMESPACE = UUID("af840d3a-e744-42b8-b7d1-823fdf207d31")
PERMISSIONS = {
    "account_configure": "treasury.account.manage",
    "account_grant": "treasury.account.manage",
    "opening_prepare": "treasury.account.manage",
    "opening_activate": "treasury.account.manage",
    "claim_review": "treasury.proof.review",
    "receipt_verify": "treasury.receipt.verify",
    "receipt_apply": "treasury.payment.apply",
    "disbursement_record": "treasury.disbursement.record",
    "transfer_record": "treasury.transfer.record",
    "movement_classify": "treasury.adjust",
    "movement_correct": "treasury.adjust",
    "receipt_application_reverse": "treasury.adjust",
    "reconciliation_observe": "treasury.reconcile",
    "reconciliation_match": "treasury.reconcile",
    "reconciliation_close": "treasury.reconcile",
    "reconciliation_supersede": "treasury.adjust",
}


def identity(request_id, suffix):
    return uuid5(NAMESPACE, f"{request_id}:{suffix}")


def json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, ".2f")
    if isinstance(value, (UUID, date, datetime)):
        return str(value) if isinstance(value, UUID) else value.isoformat()
    if isinstance(value, dict):
        return {
            key: json_value(item)
            for key, item in value.items()
            if not key.startswith("_")
        }
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return value


def expected_balance(opening, lines, cutoff):
    if opening is None or cutoff < opening["cutoff"]:
        return None
    return opening["amount"] + sum(
        (
            line["signed_amount"]
            for line in lines
            if opening["cutoff"] < line["effective_at"] <= cutoff
        ),
        Decimal("0.00"),
    )


def event_projection(conn, event):
    revisions = conn.execute(
        "select * from treasury.event_revisions where event_id=%s order by version",
        (event["id"],),
    ).fetchall()
    result: dict[str, Any] = dict(
        event,
        original_classification=event["classification"],
        version=1 + len(revisions),
        revisions=revisions,
        corrected=any(row["action"] == "correct" for row in revisions),
    )
    for row in revisions:
        if row["action"] == "classify":
            result["classification"] = row["classification"]
    return result


def account_snapshot(conn, account_id, cutoff=None):
    cutoff = cutoff or datetime.now(timezone.utc)
    account = conn.execute(
        "select * from treasury.accounts where id=%s", (account_id,)
    ).fetchone()
    opening = conn.execute(
        "select * from treasury.opening_positions where account_id=%s and status='active'",
        (account_id,),
    ).fetchone()
    lines = conn.execute(
        "select signed_amount,effective_at from treasury.movement_lines where account_id=%s and effective_at<=%s",
        (account_id, cutoff),
    ).fetchall()
    balance = expected_balance(opening, lines, cutoff)
    latest = conn.execute(
        "select max(verified_at) as verified_at from treasury.events where account_id=%s",
        (account_id,),
    ).fetchone()
    return json_value(
        {
            "available": balance is not None,
            "opening_id": opening["id"] if opening else None,
            "opening_cutoff": opening["cutoff"] if opening else None,
            "cutoff": cutoff,
            "expected_balance": balance,
            "movement_watermark": account["movement_watermark"],
            "last_verified_at": latest["verified_at"],
            "message": None
            if balance is not None
            else "Opening position not supplied.",
        }
    )


class TreasuryService:
    def __init__(
        self, connection_factory=None, store=None, collection_adapter=None, clock=None
    ):
        self.connection_factory = connection_factory or connect_database
        self._store = store
        self.collection_adapter = collection_adapter
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def store(self):
        if self._store is None:
            self._store = PrivateEvidenceStore()
        return self._store

    def connect(self):
        conn = self.connection_factory()
        conn.row_factory = dict_row
        return conn

    def evidence(self, conn, account_id, evidence_id, purposes):
        row = conn.execute(
            "select * from treasury.evidence where id=%s and account_id=%s",
            (evidence_id, account_id),
        ).fetchone()
        if row is None or row["purpose"] not in purposes:
            raise TreasuryDenied(
                "Matching recipient-side private evidence is required."
            )
        self.store.read(row["id"], row["sha256"], row["byte_count"])
        return row

    def replay(self, conn, actor, request_id, payload_hash=None):
        row = conn.execute(
            "select * from treasury.outcomes where request_id=%s", (request_id,)
        ).fetchone()
        if row is None:
            return None
        if (
            row["actor_id"] != actor.user_id
            or row["device_id"] != actor.registered_device_id
        ):
            raise TreasuryDenied("The private command result is unavailable.")
        if payload_hash is not None and row["payload_hash"] != payload_hash:
            raise TreasuryConflict(
                "This request identity belongs to a different unchanged command."
            )
        if row["action"] in {
            "account_configure",
            "account_grant",
            "opening_prepare",
            "opening_activate",
        }:
            require_owner(conn, actor)
        if row["action"].startswith("collector_"):
            from .collector_surplus import replay_scope

            return replay_scope(self, conn, actor, row)
        detail = row["result"]["result"]
        source_link = detail.get("source_link", {})
        collector_return = source_link.get("action_record")
        if (
            not collector_return
            and source_link.get("source_id")
            and detail.get("event", {})
            .get("requested_purpose", "")
            .startswith("collector_")
        ):
            from .collector_surplus import load

            collector_return = load(
                conn, "actions", UUID(source_link["source_id"]), lock=False
            )
        if collector_return:
            from .collector_surplus import require_replay_accounts

            account_permissions = {
                row["account_id"]: {
                    row["permission"],
                    "treasury.collector_surplus.settle",
                }
            }
            account_permissions.setdefault(
                UUID(collector_return["origin_account_id"]), set()
            ).add("treasury.collector_surplus.settle")
            require_replay_accounts(conn, actor, account_permissions)
        if row["permission"] == "claim_own":
            from .treasury_claims import get_claim

            get_claim(self, conn, actor, UUID(row["result"]["target_id"]))
        else:
            require_account(
                conn,
                actor,
                row["account_id"],
                row["permission"],
                private=row["action"].startswith("reconciliation")
                or row["action"].startswith("movement_")
                or row["result"]["result"].get("evidence", {}).get("purpose")
                == "statement",
            )
        self.require_source_authority(
            conn, actor, row["action"], row["result"]["result"].get("application_id")
        )
        current_return = None
        if collector_return:
            from .collector_surplus import check_account, independent, load

            current_return = load(
                conn, "actions", UUID(collector_return["id"]), lock=False
            )
            independent(actor, current_return)
            check_account(
                {
                    "id": row["account_id"],
                    "ledger_context_id": UUID(
                        row["result"]["result"]["ledger_context_id"]
                    ),
                },
                current_return,
            )
            require_account(
                conn, actor, row["account_id"], "treasury.collector_surplus.settle"
            )
            require_account(
                conn,
                actor,
                UUID(collector_return["origin_account_id"]),
                "treasury.collector_surplus.settle",
            )
        # Private files must still be intact on recovery; no successful phantom file.
        detail = row["result"]["result"]
        if detail.get("receipt", {}).get("client_id"):
            from .treasury_authorization import require_borrower

            require_borrower(
                conn,
                actor,
                UUID(detail["receipt"]["client_id"]),
                [],
                staff_permission=row["permission"],
                account_id=row["account_id"],
            )
        if detail.get("claim", {}).get("id"):
            from .treasury_claims import get_claim

            get_claim(self, conn, actor, UUID(detail["claim"]["id"]))
        evidence_ids = set()

        def collect_evidence(value):
            if isinstance(value, dict):
                if value.get("evidence_id"):
                    evidence_ids.add(value["evidence_id"])
                for item in value.values():
                    collect_evidence(item)
            elif isinstance(value, list):
                for item in value:
                    collect_evidence(item)

        collect_evidence(detail)
        if current_return is not None:
            evidence_ids.add(current_return["evidence_id"])
        if detail.get("evidence", {}).get("id"):
            evidence_ids.add(detail["evidence"]["id"])
        event_id = detail.get("event", {}).get("id") or detail.get("receipt", {}).get(
            "event_id"
        )
        if event_id:
            event_evidence = conn.execute(
                "select evidence_id from treasury.events where id=%s and account_id=%s",
                (UUID(event_id), row["account_id"]),
            ).fetchone()
            if event_evidence:
                evidence_ids.add(str(event_evidence["evidence_id"]))
        for evidence_id in evidence_ids:
            self.evidence(
                conn,
                row["account_id"],
                UUID(evidence_id),
                {"claim", "recipient", "statement", "opening", "correction"},
            )
        return row["result"]

    def save_result(
        self,
        conn,
        actor,
        request_id,
        action,
        account,
        permission,
        payload_hash,
        target_id,
        version,
        detail,
        status: Literal["saved", "blocked"] = "saved",
    ):
        if permission == "collector_surplus_own":
            from .collector_surplus_reads import redacted

            detail = redacted(detail)
        enriched = dict(
            detail,
            actor_user_id=str(actor.user_id),
            device_id=str(actor.registered_device_id),
            account_id=str(account["id"]),
            ledger_context_id=str(account["ledger_context_id"]),
        )
        result = TreasuryResult(
            request_id=request_id,
            action=action,
            status=status,
            target_id=target_id,
            version=version,
            result=json_value(enriched),
        ).model_dump(mode="json")
        conn.execute(
            """insert into core.audit_logs(actor_user_id,action,target_type,target_id,details)
            values(%s,%s,'treasury',%s,%s)""",
            (
                actor.user_id,
                "treasury." + action,
                target_id,
                Jsonb(
                    {
                        "request_id": str(request_id),
                        "account_id": str(account["id"]),
                        "ledger_context_id": str(account["ledger_context_id"]),
                        "status": status,
                    }
                ),
            ),
        )
        conn.execute(
            """insert into treasury.outcomes(request_id,actor_id,device_id,account_id,action,payload_hash,permission,result)
            values(%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                request_id,
                actor.user_id,
                actor.registered_device_id,
                account["id"],
                action,
                payload_hash,
                permission,
                Jsonb(result),
            ),
        )
        return result

    def execute(self, actor, command):
        require_entry()
        try:
            with self.connect() as conn, conn.transaction():
                require_actor(conn, actor)
                conn.execute(
                    "select pg_advisory_xact_lock(hashtextextended(%s,0))",
                    (str(command.request_id),),
                )
                from .collector_surplus import (
                    OWN,
                    affected_accounts,
                    own_account,
                    require_enabled,
                )
                from .collector_surplus import (
                    PERMISSIONS as surplus_permissions,
                )

                surplus = command.action in surplus_permissions
                if surplus:
                    require_enabled()
                permission = (surplus_permissions if surplus else PERMISSIONS)[
                    command.action
                ]
                account_id = getattr(command, "account_id", None)
                involved_accounts = [account_id]
                if surplus or (
                    command.action == "disbursement_record"
                    and command.purpose.startswith("collector_")
                ):
                    account_id, involved_accounts = affected_accounts(
                        conn, actor, command
                    )
                self.require_source_authority(
                    conn,
                    actor,
                    command.action,
                    getattr(command, "application_id", None),
                )
                if command.action in {
                    "account_configure",
                    "account_grant",
                    "opening_prepare",
                    "opening_activate",
                }:
                    require_owner(conn, actor)
                # Account create also serializes an absent row across request IDs.
                for involved in involved_accounts:
                    conn.execute(
                        "select pg_advisory_xact_lock(hashtextextended(%s,1))",
                        (str(involved),),
                    )
                if len(involved_accounts) > 1:
                    for involved in involved_accounts:
                        require_account(
                            conn, actor, involved, "treasury.collector_surplus.settle"
                        )
                if command.action == "transfer_record":
                    for transfer_account_id in sorted(
                        [command.account_id, command.other_account_id], key=str
                    ):
                        require_account(conn, actor, transfer_account_id, permission)
                account = (
                    None
                    if command.action == "account_configure"
                    else own_account(conn, actor, account_id)
                    if command.action in OWN
                    else require_account(
                        conn,
                        actor,
                        account_id,
                        permission,
                        private=command.action.startswith("reconciliation")
                        or command.action.startswith("movement_"),
                    )
                )
                result = self.replay(
                    conn, actor, command.request_id, command_hash(command)
                )
                if result is not None:
                    return result
                if (
                    account is not None
                    and command.action
                    not in {"receipt_apply", "receipt_application_reverse"}
                    and command.action not in OWN
                    and account["version"] != command.expected_version
                ):
                    raise TreasuryConflict(
                        "The account changed; refresh and review the exact version."
                    )
                if surplus:
                    from .collector_surplus import action as surplus_action

                    target, version, detail, status = surplus_action(
                        self, conn, actor, account, command
                    )
                    from .collector_surplus import source_changed

                    source_changed(self, conn, account, command, detail)
                elif command.action == "account_configure":
                    target, version, detail, status = self.configure_account(
                        conn, actor, command
                    )
                    account = conn.execute(
                        "select * from treasury.accounts where id=%s",
                        (command.account_id,),
                    ).fetchone()
                elif command.action == "account_grant":
                    target, version, detail, status = self.grant_account(
                        conn, actor, account, command
                    )
                elif command.action in {
                    "opening_prepare",
                    "opening_activate",
                    "movement_classify",
                    "movement_correct",
                }:
                    target, version, detail, status = self.ledger_action(
                        conn, actor, account, command
                    )
                elif command.action in {
                    "claim_review",
                    "receipt_verify",
                    "receipt_apply",
                    "receipt_application_reverse",
                }:
                    from .treasury_claims import claim_action

                    target, version, detail, status = claim_action(
                        self, conn, actor, account, command
                    )
                elif command.action in {"disbursement_record", "transfer_record"}:
                    from .treasury_disbursements import outgoing_action

                    target, version, detail, status = outgoing_action(
                        self, conn, actor, account, command
                    )
                else:
                    from .treasury_reconciliation import reconciliation_action

                    target, version, detail, status = reconciliation_action(
                        self, conn, actor, account, command
                    )
                return self.save_result(
                    conn,
                    actor,
                    command.request_id,
                    command.action,
                    account,
                    permission,
                    command_hash(command),
                    target,
                    version,
                    detail,
                    status,
                )
        except (
            errors.UniqueViolation,
            errors.CheckViolation,
            errors.ForeignKeyViolation,
        ) as error:
            raise TreasuryConflict(
                "The treasury identity, context or amount conflicts; refresh and review."
            ) from error

    def require_source_authority(self, conn, actor, action, application_id=None):
        if action == "receipt_application_reverse":
            require_live_permission(conn, actor, "collection.void.unremitted")
            if (
                application_id
                and conn.execute(
                    """select 1 from treasury.applications a
                join lending.seven_by_seven_extra_principal_adjustments p
                  on a.source_result->'transaction_ids' ? p.transaction_id::text
                where a.id=%s limit 1""",
                    (application_id,),
                ).fetchone()
            ):
                require_live_permission(conn, actor, "lending.extra_principal.reverse")

    def configure_account(self, conn, actor, command):
        context = conn.execute(
            "select * from treasury.contexts where id=%s for share",
            (command.ledger_context_id,),
        ).fetchone()
        if context is None:
            conn.execute(
                "insert into treasury.contexts(id,kind,created_by) values(%s,%s,%s)",
                (command.ledger_context_id, command.context, actor.user_id),
            )
        elif (
            context["kind"] != command.context or context["created_by"] != actor.user_id
        ):
            raise TreasuryConflict("The account belongs to a different ledger context.")
        expected_ownership = {
            "synthetic": {"synthetic"},
            "corporate_legal": {"corporate"},
            "owner_operations": {"owner_personal", "owner_business"},
        }
        if command.ownership not in expected_ownership[command.context]:
            raise TreasuryConflict(
                "Legal holder classification conflicts with the ledger context."
            )
        old = conn.execute(
            "select * from treasury.accounts where id=%s for update",
            (command.account_id,),
        ).fetchone()
        if old is None:
            if command.expected_version != 0:
                raise TreasuryConflict(
                    "New account configuration requires version zero."
                )
            conn.execute(
                """insert into treasury.accounts(id,ledger_context_id,kind,alias,ownership,custodian_user_id,
                masked_identifier,payment_instructions,designated_receiving,active) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    command.account_id,
                    command.ledger_context_id,
                    command.kind,
                    command.alias,
                    command.ownership,
                    command.custodian_user_id,
                    command.masked_identifier,
                    command.payment_instructions,
                    command.designated_receiving,
                    command.active,
                ),
            )
        else:
            if old["version"] != command.expected_version:
                raise TreasuryConflict("The account configuration changed.")
            for key in ["ledger_context_id", "kind", "ownership", "custodian_user_id"]:
                if old[key] != getattr(command, key):
                    raise TreasuryConflict(
                        "Account identity/custody cannot be relabeled; use an evidenced transfer or separately reviewed account."
                    )
            conn.execute(
                """update treasury.accounts set alias=%s,masked_identifier=%s,payment_instructions=%s,
                designated_receiving=%s,active=%s,version=version+1 where id=%s""",
                (
                    command.alias,
                    command.masked_identifier,
                    command.payment_instructions,
                    command.designated_receiving,
                    command.active,
                    command.account_id,
                ),
            )
        row = conn.execute(
            "select * from treasury.accounts where id=%s", (command.account_id,)
        ).fetchone()
        return row["id"], row["version"], {"account": json_value(row)}, "saved"

    def grant_account(self, conn, actor, account, command):
        conn.execute(
            """insert into treasury.account_access(account_id,user_id,permissions,private_history,enabled,granted_by)
          values(%s,%s,%s,%s,%s,%s) on conflict(account_id,user_id) do update set permissions=excluded.permissions,
          private_history=excluded.private_history,enabled=excluded.enabled,granted_by=excluded.granted_by,updated_at=now()""",
            (
                account["id"],
                command.user_id,
                command.permissions,
                command.private_history,
                command.enabled,
                actor.user_id,
            ),
        )
        row = self.bump_account(conn, account["id"])
        return row["id"], row["version"], {"account": json_value(row)}, "saved"

    def bump_account(self, conn, account_id, movement=False):
        return conn.execute(
            """update treasury.accounts set version=version+1,
             movement_watermark=movement_watermark+%s where id=%s returning *""",
            (1 if movement else 0, account_id),
        ).fetchone()

    def flag_late(self, conn, account_id, effective_at):
        conn.execute(
            "update treasury.reconciliations set requires_review=true where account_id=%s and closed_at is not null and cutoff>=%s",
            (account_id, effective_at),
        )

    def record_verified_event(self, conn, actor, account, event):
        if event["effective_at"] > self.clock():
            raise TreasuryConflict(
                "A future transaction cannot be certified as already received or debited."
            )
        if event["provider"] != account["kind"]:
            raise TreasuryConflict(
                "The verified transaction namespace must match the real receiving account provider."
            )
        self.evidence(conn, account["id"], event["evidence_id"], {"recipient"})
        old = conn.execute(
            "select * from treasury.events where account_id=%s and provider=%s and reference=%s",
            (account["id"], event["provider"], event["reference"]),
        ).fetchone()
        if old:
            if conn.execute(
                "select 1 from treasury.event_revisions where event_id=%s and action='correct'",
                (old["id"],),
            ).fetchone():
                raise TreasuryConflict(
                    "This external identity retains a correction; it cannot be reused without a linked investigation."
                )
            for key in ["direction", "amount", "fee", "effective_at"]:
                if old[key] != event[key]:
                    raise TreasuryConflict(
                        "This external transaction already has conflicting retained evidence."
                    )
            return old, False
        row = conn.execute(
            """insert into treasury.events(id,account_id,ledger_context_id,provider,reference,direction,
            amount,fee,effective_at,recorded_by_user_id,reported_by_user_id,verified_by_user_id,assigned_collector_user_id,
            device_id,evidence_id,recipient_attestation,classification,reason)
            values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning *""",
            (
                event["id"],
                account["id"],
                account["ledger_context_id"],
                event["provider"],
                event["reference"],
                event["direction"],
                event["amount"],
                event["fee"],
                event["effective_at"],
                actor.user_id,
                event.get("reported_by_user_id"),
                actor.user_id,
                event.get("assigned_collector_user_id"),
                actor.registered_device_id,
                event["evidence_id"],
                event["recipient_attestation"],
                event["classification"],
                event["reason"],
            ),
        ).fetchone()
        sign = Decimal(1) if event["direction"] == "credit" else Decimal(-1)
        for component, amount in [
            ("principal", event["amount"] * sign),
            ("fee", -event["fee"]),
        ]:
            if amount:
                conn.execute(
                    """insert into treasury.movement_lines(id,event_id,account_id,ledger_context_id,component,signed_amount,effective_at,evidence_id)
                    values(%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        identity(event["id"], component),
                        row["id"],
                        account["id"],
                        account["ledger_context_id"],
                        component,
                        amount,
                        row["effective_at"],
                        row["evidence_id"],
                    ),
                )
        self.bump_account(conn, account["id"], True)
        self.flag_late(conn, account["id"], event["effective_at"])
        return row, True

    def ledger_action(self, conn, actor, account, command):
        if command.action == "opening_prepare":
            self.evidence(conn, account["id"], command.evidence_id, {"opening"})
            if any(
                value is not None and Decimal(value) > Decimal(command.amount)
                for value in [
                    command.personal_amount,
                    command.third_party_amount,
                    command.transit_amount,
                ]
            ):
                raise TreasuryConflict(
                    "Opening subsets cannot exceed the observed opening."
                )
            active = conn.execute(
                "select * from treasury.opening_positions where account_id=%s and status='active'",
                (account["id"],),
            ).fetchone()
            if active and active["cutoff"] != command.cutoff:
                raise TreasuryConflict(
                    "An opening revision must retain its evidenced coverage cutoff."
                )
            target = identity(command.request_id, "opening")
            row = conn.execute(
                """insert into treasury.opening_positions(id,account_id,ledger_context_id,cutoff,amount,
                personal_amount,third_party_amount,transit_amount,evidence_id,reason,status,supersedes_id,created_by)
                values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'draft',%s,%s) returning *""",
                (
                    target,
                    account["id"],
                    account["ledger_context_id"],
                    command.cutoff,
                    Decimal(command.amount),
                    command.personal_amount,
                    command.third_party_amount,
                    command.transit_amount,
                    command.evidence_id,
                    command.reason,
                    active["id"] if active else None,
                    actor.user_id,
                ),
            ).fetchone()
            self.bump_account(conn, account["id"])
            return (
                target,
                row["version"],
                {
                    "opening": json_value(row),
                    "impact": account_snapshot(conn, account["id"], command.cutoff),
                },
                "saved",
            )
        if command.action == "opening_activate":
            row = conn.execute(
                "select * from treasury.opening_positions where id=%s and account_id=%s for update",
                (command.opening_id, account["id"]),
            ).fetchone()
            if (
                row is None
                or row["version"] != command.opening_version
                or row["status"] != "draft"
            ):
                raise TreasuryConflict(
                    "The counted opening changed; review the current draft."
                )
            self.evidence(conn, account["id"], row["evidence_id"], {"opening"})
            active = conn.execute(
                "select * from treasury.opening_positions where account_id=%s and status='active' for update",
                (account["id"],),
            ).fetchone()
            if (active["id"] if active else None) != row["supersedes_id"]:
                raise TreasuryConflict("The active opening changed after the draft.")
            if active:
                conn.execute(
                    "update treasury.opening_positions set status='superseded',version=version+1 where id=%s",
                    (active["id"],),
                )
            elif conn.execute(
                "select 1 from treasury.events where account_id=%s and effective_at>%s limit 1",
                (account["id"], row["cutoff"]),
            ).fetchone():
                raise TreasuryConflict(
                    "Existing later history requires a reviewed reconstruction, not a second opening."
                )
            row = conn.execute(
                "update treasury.opening_positions set status='active',version=version+1 where id=%s returning *",
                (row["id"],),
            ).fetchone()
            self.bump_account(conn, account["id"], True)
            self.flag_late(conn, account["id"], row["cutoff"])
            return (
                row["id"],
                row["version"],
                {
                    "opening": json_value(row),
                    "balance": account_snapshot(conn, account["id"]),
                },
                "saved",
            )
        event = conn.execute(
            "select * from treasury.events where id=%s and account_id=%s",
            (command.event_id, account["id"]),
        ).fetchone()
        if (
            command.action == "movement_classify"
            and command.classification != "unclassified"
            and not is_owner(actor)
        ):
            raise TreasuryDenied(
                "Personal account-purpose classifications require the configured owner."
            )
        if event is None:
            raise TreasuryDenied("The movement is unavailable.")
        revisions = conn.execute(
            "select * from treasury.event_revisions where event_id=%s order by version",
            (event["id"],),
        ).fetchall()
        current_version = 1 + len(revisions)
        if current_version != command.event_version:
            raise TreasuryConflict("The movement version changed.")
        if any(row["action"] == "correct" for row in revisions):
            raise TreasuryConflict(
                "The original observation already has a retained correction."
            )
        correction = command.action == "movement_correct"
        if correction:
            self.evidence(conn, account["id"], command.evidence_id, {"correction"})
            if (
                conn.execute(
                    """select 1 from treasury.applications a join treasury.receipts r on r.id=a.receipt_id
                 where r.event_id=%s and a.status='active' limit 1""",
                    (event["id"],),
                ).fetchone()
                or conn.execute(
                    "select 1 from treasury.source_links where event_id=%s limit 1",
                    (event["id"],),
                ).fetchone()
            ):
                raise TreasuryConflict(
                    "Protected source/application reversal is required before correcting this observation."
                )
            receipt = conn.execute(
                "select * from treasury.receipts where event_id=%s for update",
                (event["id"],),
            ).fetchone()
            if receipt and receipt["refunded_amount"]:
                raise TreasuryConflict(
                    "Actual refunds require protected investigation before an observation correction."
                )
            amount = conn.execute(
                "select sum(signed_amount) as amount from treasury.movement_lines where event_id=%s",
                (event["id"],),
            ).fetchone()["amount"]
            conn.execute(
                """insert into treasury.movement_lines(id,event_id,account_id,ledger_context_id,component,signed_amount,effective_at,evidence_id)
               values(%s,%s,%s,%s,'correction',%s,%s,%s)""",
                (
                    identity(command.request_id, "correction"),
                    event["id"],
                    account["id"],
                    account["ledger_context_id"],
                    -amount,
                    event["effective_at"],
                    command.evidence_id,
                ),
            )
            self.flag_late(conn, account["id"], event["effective_at"])
        conn.execute(
            """insert into treasury.event_revisions(id,event_id,version,action,classification,reason,evidence_id,actor_id)
            values(%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                identity(command.request_id, "revision"),
                event["id"],
                current_version + 1,
                "correct" if correction else "classify",
                None if correction else command.classification,
                command.reason,
                command.evidence_id if correction else None,
                actor.user_id,
            ),
        )
        self.bump_account(conn, account["id"], True)
        return (
            event["id"],
            current_version + 1,
            {
                "event": json_value(event_projection(conn, event)),
                "correction": correction,
            },
            "saved",
        )

    def request_result(self, actor, request_id):
        with self.connect() as conn, conn.transaction():
            require_actor(conn, actor)
            return self.replay(conn, actor, request_id)

    def workspace(self, actor):
        from .treasury_claims import list_claims

        with self.connect() as conn, conn.transaction():
            require_actor(conn, actor)
            accounts = []
            capabilities = {
                action: False
                for action in [
                    *PERMISSIONS,
                    "claim_submit",
                    "claim_version",
                    "evidence_upload",
                ]
            }
            if is_owner(actor):
                candidates = conn.execute(
                    """select a.* from treasury.accounts a join treasury.contexts c on c.id=a.ledger_context_id
                    where c.created_by=%s order by a.alias,a.id""",
                    (actor.user_id,),
                ).fetchall()
                capabilities.update({action: True for action in PERMISSIONS})
            else:
                candidates = conn.execute(
                    """select a.*,g.private_history,g.permissions as account_permissions from treasury.accounts a
                   join treasury.account_access g on g.account_id=a.id where g.user_id=%s and g.enabled and a.active order by a.alias,a.id""",
                    (actor.user_id,),
                ).fetchall()
            live_permissions = {
                row["permission_code"]
                for row in conn.execute(
                    """select distinct rp.permission_code from core.user_roles ur
               join core.role_permissions rp on rp.role_id=ur.role_id where ur.user_id=%s""",
                    (actor.user_id,),
                ).fetchall()
            }
            for account in candidates:
                actions = [
                    action
                    for action, permission in PERMISSIONS.items()
                    if is_owner(actor)
                    or permission in live_permissions
                    and permission in account.get("account_permissions", [])
                    and action
                    not in {
                        "account_configure",
                        "account_grant",
                        "opening_prepare",
                        "opening_activate",
                    }
                    and (
                        not action.startswith("reconciliation")
                        or account.get("private_history", False)
                    )
                ]
                actions = [
                    action
                    for action in actions
                    if action != "receipt_application_reverse"
                    or "collection.void.unremitted" in live_permissions
                ]
                private = is_owner(actor) or (
                    account.get("private_history", False)
                    and "treasury.view" in live_permissions
                    and "treasury.view" in account.get("account_permissions", [])
                )
                context_row = conn.execute(
                    "select kind from treasury.contexts where id=%s",
                    (account["ledger_context_id"],),
                ).fetchone()
                if context_row is None:
                    raise TreasuryDenied("The account context is unavailable.")
                context = context_row["kind"]
                projection = {
                    key: account[key]
                    for key in [
                        "id",
                        "ledger_context_id",
                        "kind",
                        "currency",
                        "alias",
                        "ownership",
                        "masked_identifier",
                        "version",
                        "active",
                    ]
                }
                surplus_upload = is_owner(actor) or any(
                    "treasury.collector_surplus." + suffix in live_permissions
                    and "treasury.collector_surplus." + suffix
                    in account.get("account_permissions", [])
                    for suffix in ["receive", "resolve", "settle"]
                )
                evidence_purposes = []
                for purpose, upload_permission in {
                    "recipient": "treasury.receipt.verify",
                    "opening": "treasury.account.manage",
                    "statement": "treasury.reconcile",
                    "correction": "treasury.adjust",
                }.items():
                    if (
                        is_owner(actor)
                        or upload_permission in live_permissions
                        and upload_permission in account.get("account_permissions", [])
                        and (
                            purpose != "statement"
                            or account.get("private_history", False)
                        )
                        and purpose != "opening"
                    ):
                        evidence_purposes.append(purpose)
                if surplus_upload and "recipient" not in evidence_purposes:
                    evidence_purposes.append("recipient")
                projection.update(
                    evidence_purposes=evidence_purposes,
                    context=context,
                    actions=actions,
                    balance=account_snapshot(conn, account["id"]) if private else None,
                    payment_instructions=account["payment_instructions"]
                    if account["designated_receiving"]
                    else "",
                )
                if surplus_upload or any(
                    PERMISSIONS[action]
                    in {
                        "treasury.receipt.verify",
                        "treasury.account.manage",
                        "treasury.reconcile",
                        "treasury.adjust",
                    }
                    for action in actions
                ):
                    projection["actions"].append("evidence_upload")
                    capabilities["evidence_upload"] = True
                if account["designated_receiving"] and (
                    is_owner(actor)
                    or "treasury.proof.submit.assigned" in live_permissions
                    and "treasury.proof.submit.assigned"
                    in account.get("account_permissions", [])
                ):
                    projection["actions"] += ["claim_submit", "claim_version"]
                    capabilities["claim_submit"] = capabilities["claim_version"] = True
                accounts.append(json_value(projection))
                for action in actions:
                    capabilities[action] = True
            own_client = conn.execute(
                """select c.id from lending.clients c where c.user_id=%s and c.status='active'
              and exists(select 1 from core.user_roles ur join core.roles r on r.id=ur.role_id where ur.user_id=%s and r.code='client')""",
                (actor.user_id, actor.user_id),
            ).fetchone()
            if own_client:
                capabilities["claim_submit"] = capabilities["claim_version"] = True
                existing = {row["id"] for row in accounts}
                for row in conn.execute(
                    "select a.*,c.kind as context from treasury.accounts a join treasury.contexts c on c.id=a.ledger_context_id where a.active and a.designated_receiving order by a.alias,a.id"
                ).fetchall():
                    if str(row["id"]) not in existing:
                        accounts.append(
                            json_value(
                                {
                                    key: row[key]
                                    for key in [
                                        "id",
                                        "ledger_context_id",
                                        "context",
                                        "kind",
                                        "currency",
                                        "alias",
                                        "version",
                                        "active",
                                    ]
                                }
                                | {
                                    "actions": ["claim_submit", "claim_version"],
                                    "balance": None,
                                    "payment_instructions": row["payment_instructions"],
                                }
                            )
                        )
            state = readiness()
            if not state["enabled"] or not state["owner_configured"]:
                capabilities = {action: False for action in capabilities}
                for account in accounts:
                    account["actions"] = []
            from .treasury_disbursements import source_choices

            return dict(
                contract_version=1,
                actor={
                    "user_id": str(actor.user_id),
                    "device_id": str(actor.registered_device_id),
                },
                **state,
                capabilities=capabilities,
                accounts=accounts,
                claims=list_claims(self, conn, actor, limit=50, offset=0)["items"],
                source_choices=source_choices(conn, actor),
                borrower_choices=self.borrower_choices(conn, actor, accounts),
                staff_choices=json_value(
                    conn.execute("""select distinct u.id as user_id,u.full_name as name from core.users u
                            join core.user_roles ur on ur.user_id=u.id join core.roles r on r.id=ur.role_id
                            where u.status='active' and r.code<>'client' order by u.full_name,u.id""").fetchall()
                )
                if is_owner(actor)
                else [],
            )

    def borrower_choices(self, conn, actor, accounts):
        from .treasury_authorization import require_borrower

        receipt_staff = any(
            "receipt_verify" in account["actions"] for account in accounts
        )
        candidates = conn.execute(
            """select c.id as client_id,c.full_name as name from lending.clients c where c.status='active'
            and (%s or c.user_id=%s or lending.collector_area_owner(coalesce(c.area,''))=%s
              or lending.collector_has_active_delegated_area_access(%s,coalesce(c.area,''))) order by c.full_name,c.id""",
            (receipt_staff, actor.user_id, actor.user_id, actor.user_id),
        ).fetchall()
        result = []
        for client in candidates:
            allowed = []
            for account in accounts:
                permission = (
                    "treasury.receipt.verify"
                    if "receipt_verify" in account["actions"]
                    else "treasury.proof.submit.assigned"
                    if "claim_submit" in account["actions"]
                    else None
                )
                if permission is None:
                    continue
                try:
                    require_borrower(
                        conn,
                        actor,
                        client["client_id"],
                        [],
                        staff_permission=permission,
                        account_id=UUID(account["id"]),
                    )
                    allowed.append(account["id"])
                except TreasuryDenied:
                    continue
            if allowed:
                loans = conn.execute(
                    """select l.id as loan_id,l.loan_number,t.code as loan_type,s.state_version as expected_version
                   from lending.loans l join lending.loan_types t on t.id=l.loan_type_id left join lending.loan_collection_state s on s.loan_id=l.id
                   where l.client_id=%s order by l.loan_number,l.id""",
                    (client["client_id"],),
                ).fetchall()
                result.append(
                    json_value(dict(client, allowed_account_ids=allowed, loans=loans))
                )
        return result

    def instructions(self, actor):
        with self.connect() as conn, conn.transaction():
            require_actor(conn, actor)
            rows = conn.execute("""select id as account_id,version as account_version,alias,kind,currency,payment_instructions
                from treasury.accounts where active and designated_receiving order by alias,id""").fetchall()
            return {"items": json_value(rows), "total_count": len(rows)}

    def list_records(self, actor, account_id, kind, limit=50, offset=0):
        if kind not in {"events", "receipts", "reconciliations", "claims", "openings"}:
            raise TreasuryDenied("The treasury collection is unavailable.")
        with self.connect() as conn, conn.transaction():
            require_account(
                conn, actor, account_id, "treasury.view", private=kind != "claims"
            )
            if kind == "claims":
                from .treasury_claims import list_claims

                return list_claims(
                    self, conn, actor, account_id=account_id, limit=limit, offset=offset
                )
            # kind is the closed set above, never an arbitrary client table name.
            table = "opening_positions" if kind == "openings" else kind
            rows = conn.execute(
                sql.SQL(
                    "select * from treasury.{} where account_id=%s order by {},id limit %s offset %s"
                ).format(
                    sql.Identifier(table),
                    sql.Identifier(
                        "effective_at" if kind in {"events", "receipts"} else "cutoff"
                    ),
                ),
                (account_id, limit, offset),
            ).fetchall()
            if kind == "events":
                rows = [event_projection(conn, row) for row in rows]
            count_row = conn.execute(
                sql.SQL(
                    "select count(*) as count from treasury.{} where account_id=%s"
                ).format(sql.Identifier(table)),
                (account_id,),
            ).fetchone()
            if count_row is None:
                raise TreasuryUnavailable(
                    "The complete authorized count is unavailable."
                )
            total = count_row["count"]
            totals = {"balance": account_snapshot(conn, account_id)}
            if kind == "receipts":
                sums = conn.execute(
                    """select coalesce(sum(amount-applied_amount-refunded_amount),0) as unapplied_amount,
                    coalesce(sum(applied_amount),0) as applied_amount,coalesce(sum(refunded_amount),0) as refunded_amount
                    from treasury.receipts where account_id=%s and not exists(select 1 from treasury.event_revisions v
                     where v.event_id=receipts.event_id and v.action='correct')""",
                    (account_id,),
                ).fetchone()
                totals.update(json_value(sums))
            return {
                "items": json_value(rows),
                "total_count": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(rows) < total,
                "totals": totals,
            }

    def preview_receipt_application(self, actor, receipt_id, command):
        from .treasury_claims import allocation_preview, receipt_for_application

        with self.connect() as conn, conn.transaction():
            require_actor(conn, actor)
            initial = conn.execute(
                "select account_id from treasury.receipts where id=%s", (receipt_id,)
            ).fetchone()
            if initial is None:
                raise TreasuryDenied("The receipt is unavailable.")
            account = require_account(
                conn, actor, initial["account_id"], "treasury.payment.apply"
            )
            receipt = receipt_for_application(
                conn, account, receipt_id, command.expected_version
            )
            from .treasury_authorization import require_borrower

            require_borrower(
                conn,
                actor,
                receipt["client_id"],
                [item.loan_id for item in command.loans],
                staff_permission="treasury.payment.apply",
                account_id=account["id"],
            )
            return allocation_preview(self, conn, actor, account, receipt, command)

    def list_claims(self, actor, account_id=None, client_id=None, limit=50, offset=0):
        from .treasury_claims import list_claims

        with self.connect() as conn, conn.transaction():
            require_actor(conn, actor)
            return list_claims(self, conn, actor, account_id, client_id, limit, offset)

    def get_claim(self, actor, claim_id):
        from .treasury_claims import get_claim

        with self.connect() as conn, conn.transaction():
            require_actor(conn, actor)
            return get_claim(self, conn, actor, claim_id)

    def claim_content(self, actor, claim_id, version):
        from .treasury_claims import get_claim

        with self.connect() as conn, conn.transaction():
            require_actor(conn, actor)
            claim = get_claim(self, conn, actor, claim_id)
            chosen = next(
                (row for row in claim["history"] if row["version"] == version), None
            )
            if chosen is None:
                raise TreasuryDenied("The exact private claim version is unavailable.")
            return chosen, self.store.read(
                UUID(chosen["evidence_id"]), chosen["sha256"], chosen["byte_count"]
            )

    def evidence_content(self, actor, evidence_id):
        with self.connect() as conn, conn.transaction():
            require_actor(conn, actor)
            row = conn.execute(
                "select * from treasury.evidence where id=%s", (evidence_id,)
            ).fetchone()
            if row is None or row["purpose"] == "claim":
                raise TreasuryDenied(
                    "Use the exact authorized claim version to read its evidence."
                )
            permissions = {
                "recipient": "treasury.receipt.verify",
                "opening": "treasury.account.manage",
                "statement": "treasury.reconcile",
                "correction": "treasury.adjust",
            }
            try:
                require_account(
                    conn,
                    actor,
                    row["account_id"],
                    permissions[row["purpose"]],
                    private=row["purpose"] == "statement",
                )
            except TreasuryDenied:
                if row["purpose"] != "recipient":
                    raise
                permitted = False
                for suffix in ["receive", "resolve", "settle"]:
                    try:
                        require_account(
                            conn,
                            actor,
                            row["account_id"],
                            "treasury.collector_surplus." + suffix,
                        )
                        permitted = True
                        break
                    except TreasuryDenied:
                        continue
                if not permitted:
                    raise TreasuryDenied(
                        "Current scoped recipient-evidence authority is required."
                    )
            if row["purpose"] == "recipient" and not is_owner(actor):
                events = conn.execute(
                    "select * from treasury.events where evidence_id=%s", (evidence_id,)
                ).fetchall()
                if not events and row["uploaded_by"] != actor.user_id:
                    raise TreasuryDenied(
                        "Unlinked recipient evidence is restricted to its current authorized uploader."
                    )
                for event in events:
                    projected = event_projection(conn, event)
                    if projected["classification"] in {
                        "personal",
                        "owner_contribution",
                        "owner_withdrawal",
                        "deposit",
                        "unclassified",
                        "unresolved_reference",
                    }:
                        require_account(
                            conn,
                            actor,
                            row["account_id"],
                            "treasury.view",
                            private=True,
                        )
                    elif event["direction"] == "debit":
                        require_account(
                            conn,
                            actor,
                            row["account_id"],
                            "treasury.disbursement.record",
                        )
            return json_value(row), self.store.read(
                row["id"], row["sha256"], row["byte_count"]
            )

    def receipt_detail(self, actor, receipt_id):
        with self.connect() as conn, conn.transaction():
            require_actor(conn, actor)
            row = conn.execute(
                """select r.*,e.verified_at,e.reference,e.provider from treasury.receipts r
                join treasury.events e on e.id=r.event_id where r.id=%s""",
                (receipt_id,),
            ).fetchone()
            if row is None:
                raise TreasuryDenied("The receipt is unavailable.")
            from .treasury_authorization import require_borrower

            client = conn.execute(
                "select user_id from lending.clients where id=%s", (row["client_id"],)
            ).fetchone()
            if client is None:
                raise TreasuryDenied("The receipt borrower is unavailable.")
            may_apply = False
            if client["user_id"] == actor.user_id:
                require_borrower(conn, actor, row["client_id"], [])
            else:
                try:
                    require_account(
                        conn, actor, row["account_id"], "treasury.payment.apply"
                    )
                    permission = "treasury.payment.apply"
                    may_apply = True
                except TreasuryDenied:
                    require_account(
                        conn, actor, row["account_id"], "treasury.receipt.verify"
                    )
                    permission = "treasury.receipt.verify"
                require_borrower(
                    conn,
                    actor,
                    row["client_id"],
                    [],
                    staff_permission=permission,
                    account_id=row["account_id"],
                )
            row["remaining_amount"] = (
                row["amount"] - row["applied_amount"] - row["refunded_amount"]
            )
            row["verification"] = "manually_verified"
            row["loan_choices"] = []
            if may_apply:
                row["loan_choices"] = conn.execute(
                    """select l.id as loan_id,l.loan_number,t.code as loan_type,s.state_version as expected_version
                    from lending.loans l join lending.loan_types t on t.id=l.loan_type_id join lending.loan_collection_state s on s.loan_id=l.id
                    where l.client_id=%s and l.status='active' order by l.loan_number,l.id""",
                    (row["client_id"],),
                ).fetchall()
            return json_value(row)

    def reconciliation_detail(self, actor, reconciliation_id):
        from .treasury_reconciliation import get_session, preview_reconciliation

        with self.connect() as conn, conn.transaction():
            require_actor(conn, actor)
            initial = conn.execute(
                "select account_id from treasury.reconciliations where id=%s",
                (reconciliation_id,),
            ).fetchone()
            if initial is None:
                raise TreasuryDenied("The reconciliation is unavailable.")
            account = require_account(
                conn, actor, initial["account_id"], "treasury.reconcile", private=True
            )
            row = get_session(conn, account, reconciliation_id)
            return (
                json_value(row)
                if row["closed_at"]
                else preview_reconciliation(conn, account, row)
            )

    def reconciliation_export(self, actor, reconciliation_id):
        from .treasury_reconciliation import get_session, preview_reconciliation

        with self.connect() as conn, conn.transaction():
            require_actor(conn, actor)
            initial = conn.execute(
                "select account_id from treasury.reconciliations where id=%s",
                (reconciliation_id,),
            ).fetchone()
            if initial is None:
                raise TreasuryDenied("The reconciliation is unavailable.")
            account = require_account(
                conn, actor, initial["account_id"], "treasury.reconcile", private=True
            )
            row = get_session(conn, account, reconciliation_id)
            self.evidence(conn, account["id"], row["evidence_id"], {"statement"})
            events = conn.execute(
                """select * from treasury.events where account_id=%s and %s<effective_at and effective_at<=%s
                order by effective_at,id""",
                (account["id"], row["coverage_start"], row["cutoff"]),
            ).fetchall()
            ledger = []
            for event in events:
                self.evidence(conn, account["id"], event["evidence_id"], {"recipient"})
                projected = event_projection(conn, event)
                projected["movement_lines"] = conn.execute(
                    "select * from treasury.movement_lines where event_id=%s order by component,id",
                    (event["id"],),
                ).fetchall()
                projected["source_links"] = conn.execute(
                    "select * from treasury.source_links where event_id=%s order by id",
                    (event["id"],),
                ).fetchall()
                projected["receipts"] = conn.execute(
                    "select * from treasury.receipts where event_id=%s order by id",
                    (event["id"],),
                ).fetchall()
                ledger.append(projected)
            current = preview_reconciliation(conn, account, row)
            return json_value(
                {
                    "contract_version": 1,
                    "account": {
                        key: account[key]
                        for key in [
                            "id",
                            "ledger_context_id",
                            "kind",
                            "alias",
                            "currency",
                        ]
                    },
                    "reconciliation": dict(row, current_review=current),
                    "ledger": ledger,
                    "exceptions": {
                        key: current[key]
                        for key in [
                            "blockers",
                            "unmatched_observation_ids",
                            "unmatched_event_ids",
                            "purpose_exception_event_ids",
                            "incomplete_transfer_ids",
                        ]
                    },
                    "generated_at": self.clock(),
                    "message": "Private account statement. Reconciliation does not approve loan-purpose, destination or General Ledger exceptions.",
                }
            )


PostgresTreasuryRepository = TreasuryService
