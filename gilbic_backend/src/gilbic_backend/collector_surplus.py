"""Collector liabilities; caller-owned Treasury transaction, current scope and capacity."""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg import sql
from psycopg.types.json import Jsonb

from .treasury_authorization import (
    TreasuryConflict,
    TreasuryDenied,
    TreasuryUnavailable,
    require_account,
    require_actor,
)
from .treasury_repository import identity, json_value

PREFIX = "treasury.collector_surplus."
OWN = {
    "collector_surplus_return_request",
    "collector_surplus_application_request",
    "collector_surplus_return_acknowledge",
    "collector_custody_exception_return_acknowledge",
}
PERMISSIONS = {
    "collector_count_record": PREFIX + "receive",
    "collector_count_accept": PREFIX + "receive",
    "collector_surplus_recognize": PREFIX + "resolve",
    "collector_surplus_resolve_source": PREFIX + "resolve",
    "collector_surplus_opening_prepare": PREFIX + "resolve",
    "collector_surplus_opening_activate": PREFIX + "resolve",
    "collector_custody_exception_record": PREFIX + "receive",
    **{
        name: PREFIX + "settle"
        for name in [
            "collector_surplus_return_prepare",
            "collector_surplus_return_record",
            "collector_surplus_return_reverse",
            "collector_surplus_action_cancel",
            "collector_surplus_application_prepare",
            "collector_custody_exception_return_prepare",
        ]
    },
    **{name: "collector_surplus_own" for name in OWN},
}
TABLES = {
    name: "collector_" + name
    for name in [
        "counts",
        "settlements",
        "cases",
        "credits",
        "requests",
        "actions",
        "acknowledgments",
        "exceptions",
        "openings",
        "entries",
        "resolutions",
    ]
}
SLOTS = [
    "count",
    "settlement",
    "case",
    "credit",
    "request",
    "action_record",
    "acknowledgment",
    "exception",
    "opening_anchor",
]


def enabled():
    return os.getenv("SPINA_COLLECTOR_SURPLUS_ENABLED", "").strip().lower() == "true"


def require_enabled():
    if not enabled():
        raise TreasuryUnavailable("Collector surplus entry is disabled.")


def load(conn, kind, target, version=None, lock=True) -> dict[str, Any]:
    query = (
        sql.SQL("select * from treasury.{} where id=%s for update")
        if lock
        else sql.SQL("select * from treasury.{} where id=%s")
    )
    row = conn.execute(query.format(sql.Identifier(TABLES[kind])), (target,)).fetchone()
    if row is None:
        raise TreasuryDenied("Collector record is unavailable.")
    if version is not None and row["version"] != version:
        raise TreasuryConflict("Collector record changed; review its current version.")
    return dict(
        row["payload"],
        id=str(row["id"]),
        version=row["version"],
        account_id=str(row["account_id"]),
        ledger_context_id=str(row["ledger_context_id"]),
        collector_user_id=str(row["collector_user_id"]),
        created_at=row["created_at"].isoformat(),
    )


def save(conn, kind, account, collector, target, data):
    data = json_value(data)
    conn.execute(
        sql.SQL(
            "insert into treasury.{}(id,account_id,ledger_context_id,collector_user_id,payload) values(%s,%s,%s,%s,%s)"
        ).format(sql.Identifier(TABLES[kind])),
        (target, account["id"], account["ledger_context_id"], collector, Jsonb(data)),
    )
    return load(conn, kind, target)


def update(conn, kind, row, changes):
    data = {
        k: v
        for k, v in row.items()
        if k
        not in {
            "id",
            "version",
            "account_id",
            "ledger_context_id",
            "collector_user_id",
            "created_at",
        }
    }
    data.update(json_value(changes))
    conn.execute(
        sql.SQL(
            "update treasury.{} set payload=%s,version=version+1 where id=%s"
        ).format(sql.Identifier(TABLES[kind])),
        (Jsonb(data), UUID(row["id"])),
    )
    return load(conn, kind, UUID(row["id"]))


def outcome(row, slot, disposition, *, blocked: bool = False, **extra: Any):
    detail = {
        "collector_surplus_contract_version": 1,
        "disposition": disposition,
        "source_account_id": None,
        "blockers": [],
        **{key: None for key in SLOTS},
    }
    detail.update(extra)
    detail[slot] = row
    return UUID(row["id"]), row["version"], detail, "blocked" if blocked else "saved"


def current_collector(conn, actor, collector):
    require_actor(conn, actor)
    if str(actor.user_id) != str(collector):
        raise TreasuryDenied(
            "Only the exact original Collector may request or acknowledge this credit."
        )
    if not conn.execute(
        "select 1 from core.user_roles ur join core.roles r on r.id=ur.role_id where ur.user_id=%s and r.code='collector' for share of ur,r",
        (actor.user_id,),
    ).fetchone():
        raise TreasuryDenied("Current Collector role is required.")


def independent(actor, row):
    if str(actor.user_id) == row["collector_user_id"]:
        raise TreasuryDenied("Collector credit requires independent approval.")


def own_target(conn, actor, command):
    kind = "exceptions" if hasattr(command, "exception_id") else "credits"
    row = load(
        conn,
        kind,
        getattr(command, "exception_id", None) or command.credit_id,
        lock=False,
    )
    current_collector(conn, actor, row["collector_user_id"])
    return row


def affected_accounts(conn, actor, command):
    account_id = getattr(command, "account_id", None)
    origin = None
    if command.action in OWN:
        origin = own_target(conn, actor, command)["account_id"]
        account_id = UUID(origin)
    elif command.action in {
        "collector_surplus_return_prepare",
        "collector_surplus_application_prepare",
    }:
        origin = load(conn, "credits", command.credit_id, lock=False)["account_id"]
    elif command.action == "collector_custody_exception_return_prepare":
        origin = load(conn, "exceptions", command.exception_id, lock=False)[
            "account_id"
        ]
    elif command.action in {
        "collector_surplus_return_record",
        "collector_surplus_return_reverse",
        "collector_surplus_action_cancel",
    }:
        origin = load(conn, "actions", command.action_id, lock=False)[
            "origin_account_id"
        ]
    elif command.action == "disbursement_record" and command.purpose.startswith(
        "collector_"
    ):
        origin = load(conn, "actions", command.source_id, lock=False)[
            "origin_account_id"
        ]
    return account_id, sorted(
        {account_id, UUID(origin) if origin else account_id}, key=str
    )


def own_account(conn, actor, account_id):
    require_actor(conn, actor)
    row = conn.execute(
        "select * from treasury.accounts where id=%s and active for update",
        (account_id,),
    ).fetchone()
    if not row:
        raise TreasuryDenied("Origin account is inactive or unavailable.")
    return row


def require_replay_accounts(conn, actor, permissions):
    require_actor(conn, actor)
    accounts = sorted(permissions, key=str)
    for account_id in accounts:
        conn.execute(
            "select pg_advisory_xact_lock(hashtextextended(%s,1))", (str(account_id),)
        )
    for account_id in accounts:
        for permission in sorted(permissions[account_id]):
            require_account(conn, actor, account_id, permission)


def replay_scope(service, conn, actor, row):
    detail = row["result"]["result"]
    if row["permission"] == "collector_surplus_own":
        target = detail.get("credit") or detail.get("exception")
        if not target:
            action = detail.get("action_record")
            target = load(
                conn,
                "credits" if action.get("credit_id") else "exceptions",
                UUID(action.get("credit_id") or action["exception_id"]),
                lock=False,
            )
        current_collector(conn, actor, target["collector_user_id"])
        own_account(conn, actor, row["account_id"])
        from .collector_surplus_reads import redacted

        return redacted(row["result"])
    origin = detail.get("source_account_id") or (detail.get("action_record") or {}).get(
        "origin_account_id"
    )
    if row["action"] in {
        "collector_count_record",
        "collector_count_accept",
        "collector_custody_exception_record",
    }:
        from .treasury_authorization import require_live_permission

        require_live_permission(conn, actor, "remittance.receive")
        count = detail.get("count")
        if count and count["recipient_user_id"] != str(actor.user_id):
            raise TreasuryDenied("Exact recipient authority is required on recovery.")
    evidence_ids = set()

    def collect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key.endswith("evidence_id") and item:
                    evidence_ids.add(item)
                else:
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(detail)
    credit = detail.get("credit")
    if credit and credit.get("case_id"):
        entries = conn.execute(
            "select payload from treasury.collector_entries where credit_id=%s and payload->>'kind'='recognition'",
            (UUID(credit["id"]),),
        ).fetchall()
        resolutions = conn.execute(
            "select payload from treasury.collector_resolutions where payload->>'credit_id'=%s and payload->>'kind'='collector_credit'",
            (credit["id"],),
        ).fetchall()
        if not entries or not resolutions:
            raise TreasuryDenied("Original recognition evidence facts are unavailable.")
        for original in [*entries, *resolutions]:
            collect(original["payload"])
    elif credit and credit.get("opening_anchor_id"):
        collect(load(conn, "openings", UUID(credit["opening_anchor_id"]), lock=False))
    event_ids = set()
    for slot in ["action_record", "exception", "settlement"]:
        if detail.get(slot, {}) and detail[slot].get("event_id"):
            event_ids.add(detail[slot]["event_id"])
    for event_id in event_ids:
        event = conn.execute(
            "select evidence_id,account_id from treasury.events where id=%s",
            (UUID(event_id),),
        ).fetchone()
        if not event:
            raise TreasuryDenied("Original actual movement evidence is unavailable.")
        evidence_ids.add(str(event["evidence_id"]))
    permissions = {row["account_id"]: {row["permission"]}}
    if origin and str(origin) != str(row["account_id"]):
        permissions.setdefault(UUID(origin), set()).add(PREFIX + "settle")
    evidence_rows = []
    for evidence_id in sorted(evidence_ids):
        evidence = conn.execute(
            "select * from treasury.evidence where id=%s", (UUID(evidence_id),)
        ).fetchone()
        if not evidence:
            raise TreasuryDenied("Current private source evidence is unavailable.")
        if evidence["account_id"] != row["account_id"]:
            permissions.setdefault(evidence["account_id"], set()).add(PREFIX + "settle")
        evidence_rows.append(evidence)
    require_replay_accounts(conn, actor, permissions)
    for evidence in evidence_rows:
        service.evidence(
            conn,
            evidence["account_id"],
            evidence["id"],
            {"recipient", "opening", "correction"},
        )
    return row["result"]


def credit_change(conn, credit, **deltas):
    if credit["frozen"]:
        raise TreasuryConflict("Credit is frozen pending source recovery decision.")
    changes: dict[str, Any] = {
        key: Decimal(credit[key]) + Decimal(value) for key, value in deltas.items()
    }
    for key in [
        "recognized_amount",
        "reclassified_amount",
        "returned_amount",
        "applied_amount",
        "reserved_amount",
    ]:
        changes.setdefault(key, Decimal(credit[key]))
    changes["outstanding_amount"] = (
        changes["recognized_amount"]
        - changes["reclassified_amount"]
        - changes["returned_amount"]
        - changes["applied_amount"]
    )
    changes["available_amount"] = (
        changes["outstanding_amount"] - changes["reserved_amount"]
    )
    if changes["available_amount"] < 0:
        raise TreasuryConflict("Credit capacity is already reserved or settled.")
    changes["status"] = (
        "settled" if changes["outstanding_amount"] == 0 else "outstanding"
    )
    return update(conn, "credits", credit, changes)


def action(service, conn, actor, account, command):
    from .collector_settlement import settlement_action
    from .collector_surplus_resolution import resolution_action

    require_enabled()
    tag = command.action
    if (
        tag.startswith("collector_count_")
        or tag == "collector_custody_exception_record"
    ):
        return settlement_action(service, conn, actor, account, command)
    if tag in {
        "collector_surplus_resolve_source",
        "collector_surplus_opening_prepare",
        "collector_surplus_opening_activate",
    }:
        return resolution_action(service, conn, actor, account, command)
    if tag == "collector_surplus_recognize":
        case = load(conn, "cases", command.case_id, command.case_version)
        independent(actor, case)
        if (
            str(account["id"]) != case["account_id"]
            or command.source_digest != case["source_digest"]
            or not command.source_review_acknowledged
        ):
            raise TreasuryConflict(
                "Review the same receiving account and complete source evidence."
            )
        service.evidence(conn, account["id"], command.evidence_id, {"recipient"})
        amount = Decimal(command.amount)
        remaining = Decimal(case["unidentified_amount"]) - amount
        if remaining < 0:
            raise TreasuryConflict("Recognition exceeds unidentified excess.")
        case = update(
            conn,
            "cases",
            case,
            {
                "unidentified_amount": remaining,
                "status": "resolved" if remaining == 0 else "pending_identification",
            },
        )
        data = {
            "case_id": case["id"],
            "opening_anchor_id": None,
            "origin_account_id": str(account["id"]),
            "recognized_amount": amount,
            "reclassified_amount": "0.00",
            "returned_amount": "0.00",
            "applied_amount": "0.00",
            "reserved_amount": "0.00",
            "outstanding_amount": amount,
            "available_amount": amount,
            "frozen": False,
            "status": "outstanding",
            "entries": [],
        }
        credit = save(
            conn,
            "credits",
            account,
            UUID(case["collector_user_id"]),
            identity(command.request_id, "credit"),
            data,
        )
        save(
            conn,
            "entries",
            account,
            UUID(case["collector_user_id"]),
            identity(command.request_id, "credit-entry"),
            {
                "credit_id": credit["id"],
                "kind": "recognition",
                "amount": amount,
                "action_id": None,
                "evidence_id": str(command.evidence_id),
                "reason": command.reason,
            },
        )
        save(
            conn,
            "resolutions",
            account,
            UUID(case["collector_user_id"]),
            identity(command.request_id, "resolution"),
            {
                "case_id": case["id"],
                "kind": "collector_credit",
                "credit_id": credit["id"],
                "amount": amount,
                "evidence_id": str(command.evidence_id),
                "reason": command.reason,
            },
        )
        return outcome(credit, "credit", "recognized", case=case)
    if tag in {
        "collector_surplus_return_request",
        "collector_surplus_application_request",
    }:
        credit = load(conn, "credits", command.credit_id, command.credit_version)
        current_collector(conn, actor, credit["collector_user_id"])
        if credit["frozen"] or Decimal(command.amount) > Decimal(
            credit["available_amount"]
        ):
            raise TreasuryConflict("Requested amount exceeds current available credit.")
        data = {
            "kind": "return" if tag.endswith("return_request") else "application",
            "credit_id": credit["id"],
            "amount": command.amount,
            "destination": command.destination.model_dump()
            if hasattr(command, "destination")
            else None,
            "remittance_id": str(command.remittance_id)
            if hasattr(command, "remittance_id")
            else None,
            "source_digest": getattr(command, "source_digest", None),
            "status": "requested",
            "reason": command.reason,
        }
        if data["remittance_id"]:
            from .collector_settlement import source_snapshot

            remittance, _snapshot, digest, _gross, _refund = source_snapshot(
                conn, command.remittance_id
            )
            if (
                str(remittance["collector_user_id"]) != credit["collector_user_id"]
                or remittance["status"] != "submitted"
            ):
                raise TreasuryDenied(
                    "Future application is limited to this Collector's current pending remittance."
                )
            if digest != command.source_digest:
                raise TreasuryConflict(
                    "Future application source changed; review its exact current digest."
                )
        request = save(
            conn,
            "requests",
            account,
            actor.user_id,
            identity(command.request_id, "request"),
            data,
        )
        return outcome(request, "request", "requested", credit=credit)
    if tag in {
        "collector_surplus_return_prepare",
        "collector_surplus_application_prepare",
        "collector_custody_exception_return_prepare",
    }:
        return prepare(service, conn, actor, account, command)
    if tag in {
        "collector_surplus_return_acknowledge",
        "collector_custody_exception_return_acknowledge",
    }:
        return acknowledge(service, conn, actor, account, command)
    if tag == "collector_surplus_return_record":
        return settle(service, conn, actor, account, command)
    if tag == "collector_surplus_return_reverse":
        return reverse_return(service, conn, actor, account, command)
    if tag == "collector_surplus_action_cancel":
        row = load(conn, "actions", command.action_id, command.action_version)
        independent(actor, row)
        check_account(account, row)
        require_account(conn, actor, UUID(row["origin_account_id"]), PREFIX + "settle")
        if (
            row["status"] != "reserved"
            or row["event_id"]
            or observed_debit(conn, row["id"])
        ):
            raise TreasuryConflict(
                "An observed or uncertain debit cannot be cancelled."
            )
        service.evidence(conn, account["id"], command.evidence_id, {"recipient"})
        if row["credit_id"]:
            target = credit_change(
                conn,
                load(conn, "credits", UUID(row["credit_id"])),
                reserved_amount=-Decimal(row["amount"]),
            )
        else:
            target = exception_change(
                conn,
                load(conn, "exceptions", UUID(row["exception_id"])),
                reserved_amount=-Decimal(row["amount"]),
            )
        row = update(
            conn,
            "actions",
            row,
            {
                "status": "cancelled",
                "cancellation_evidence_id": str(command.evidence_id),
                "cancellation_reason": command.reason,
            },
        )
        return outcome(
            row,
            "action_record",
            "cancelled",
            credit=target if row["credit_id"] else None,
            exception=None if row["credit_id"] else target,
            source_account_id=row["origin_account_id"],
        )
    raise TreasuryConflict("Unknown Collector surplus phase.")


def check_account(account, row):
    if (
        str(account["id"]) != row["paying_account_id"]
        or str(account["ledger_context_id"]) != row["ledger_context_id"]
    ):
        raise TreasuryDenied("The exact paying account/context is required.")


def exception_change(conn, row, **deltas):
    changes: dict[str, Any] = {
        key: Decimal(row[key]) + Decimal(value) for key, value in deltas.items()
    }
    for key in ["returned_amount", "included_amount", "reserved_amount"]:
        changes.setdefault(key, Decimal(row[key]))
    changes["remaining_held_amount"] = (
        Decimal(row["retained_amount"])
        - changes["returned_amount"]
        - changes["included_amount"]
    )
    changes["available_amount"] = (
        changes["remaining_held_amount"] - changes["reserved_amount"]
    )
    if changes["available_amount"] < 0:
        raise TreasuryConflict("Retained cash capacity is already reserved or settled.")
    changes["status"] = (
        "included_in_settlement"
        if changes["remaining_held_amount"] == 0 and changes["included_amount"] > 0
        else "returned"
        if changes["remaining_held_amount"] == 0
        else "partly_returned"
        if changes["returned_amount"]
        else "held_disputed"
    )
    return update(conn, "exceptions", row, changes)


def prepare(service, conn, actor, account, command):
    exception = command.action == "collector_custody_exception_return_prepare"
    kind = "exceptions" if exception else "credits"
    row = load(
        conn,
        kind,
        command.exception_id if exception else command.credit_id,
        command.exception_version if exception else command.credit_version,
    )
    independent(actor, row)
    origin = require_account(conn, actor, UUID(row["account_id"]), PREFIX + "settle")
    if origin["ledger_context_id"] != account["ledger_context_id"]:
        raise TreasuryDenied("Cross-context settlement is not permitted.")
    service.evidence(conn, account["id"], command.evidence_id, {"recipient"})
    amount = Decimal(command.amount)
    request = None
    if not exception:
        request = load(
            conn,
            "requests",
            command.collector_request_id,
            command.collector_request_version,
        )
        if (
            request["credit_id"] != row["id"]
            or request["status"] != "requested"
            or request["amount"] != command.amount
        ):
            raise TreasuryConflict(
                "Exact current Collector request/amount is required."
            )
        if command.action == "collector_surplus_application_prepare":
            if (
                request["kind"] != "application"
                or request["remittance_id"] != str(command.remittance_id)
                or request["source_digest"] != command.source_digest
            ):
                raise TreasuryConflict("Exact future application request is required.")
            return outcome(
                row,
                "credit",
                "blocked_adapter",
                blocked=True,
                request=request,
                blockers=[
                    {
                        "code": "collector_application_custody_unavailable",
                        "message": "Legacy remittance custody does not support separately authorized retained credit. No reservation or settlement occurred.",
                    }
                ],
            )
        if (
            request["kind"] != "return"
            or request["destination"] != command.destination.model_dump()
        ):
            raise TreasuryConflict("Destination must match the Collector's request.")
        row = credit_change(conn, row, reserved_amount=amount)
        request = update(conn, "requests", request, {"status": "approved"})
    else:
        if (
            account["kind"] != "physical_cash"
            or str(account["id"]) != row["account_id"]
        ):
            raise TreasuryDenied(
                "Retained disputed cash must be returned from its actual holder account."
            )
        row = exception_change(conn, row, reserved_amount=amount)
    destination = (
        command.destination.model_dump()
        if not exception
        else {"kind": "physical_cash", "recipient_reference": None}
    )
    if destination["kind"] != account["kind"]:
        raise TreasuryConflict(
            "Requested destination and paying account provider differ."
        )
    data = {
        "kind": "exception_return" if exception else "return",
        "credit_id": None if exception else row["id"],
        "exception_id": row["id"] if exception else None,
        "collector_request_id": request["id"] if request else None,
        "origin_account_id": row["account_id"],
        "paying_account_id": str(account["id"]),
        "amount": amount,
        "destination": destination,
        "status": "reserved",
        "event_id": None,
        "event_version": None,
        "acknowledgment_id": None,
        "evidence_id": str(command.evidence_id),
        "reason": command.reason,
    }
    approved = save(
        conn,
        "actions",
        account,
        UUID(row["collector_user_id"]),
        identity(command.request_id, "action"),
        data,
    )
    return outcome(
        approved,
        "action_record",
        "reserved",
        exception=row if exception else None,
        credit=None if exception else row,
        source_account_id=row["account_id"],
        request=request,
    )


def observed_debit(conn, action_id):
    return conn.execute(
        """select e.* from treasury.outcomes o join treasury.events e
          on e.id=(o.result->'result'->'event'->>'id')::uuid
          where o.action='disbursement_record'
          and o.result->'result'->'source_link'->>'source_id'=%s
          and o.result->'result'->'source_link'->>'status'='blocked'
          order by o.created_at limit 1""",
        (str(action_id),),
    ).fetchone()


def debit_authority(service, conn, actor, account, command):
    row = load(conn, "actions", command.source_id)
    independent(actor, row)
    check_account(account, row)
    require_account(conn, actor, UUID(row["origin_account_id"]), PREFIX + "settle")
    require_account(conn, actor, account["id"], PREFIX + "settle")
    service.evidence(conn, account["id"], UUID(row["evidence_id"]), {"recipient"})
    expected = (
        "exception_return"
        if command.purpose == "collector_custody_exception_return"
        else "return"
    )
    if (
        row["kind"] != expected
        or row["status"] != "reserved"
        or row["event_id"]
        or command.direction != "debit"
        or str(command.payee_id) != row["collector_user_id"]
    ):
        raise TreasuryConflict(
            "One current independently approved Collector return is required."
        )
    retained = observed_debit(conn, row["id"])
    if retained:
        for key in [
            "provider",
            "reference",
            "direction",
            "effective_at",
            "evidence_id",
        ]:
            if str(retained[key]) != str(getattr(command, key)):
                if key == "effective_at" and retained[key] == command.effective_at:
                    continue
                raise TreasuryConflict(
                    "This action retains an actual debit; only explicit reconciliation of that exact event is permitted."
                )
        if retained["amount"] != Decimal(command.amount) or retained["fee"] != Decimal(
            command.fee
        ):
            raise TreasuryConflict(
                "Retained debit principal/fee cannot be replaced by a second payout."
            )
    claimed = conn.execute(
        """select coalesce(o.result->'result'->'source_link'->>'source_id',o.result->'result'->'source_link'->'action_record'->>'id') as source_id
        from treasury.outcomes o join treasury.events e on e.id=(o.result->'result'->'event'->>'id')::uuid
        where o.action='disbursement_record' and e.account_id=%s and e.provider=%s and e.reference=%s
        and coalesce(o.result->'result'->'source_link'->>'source_id',o.result->'result'->'source_link'->'action_record'->>'id') is not null limit 1""",
        (account["id"], command.provider, command.reference),
    ).fetchone()
    if claimed and claimed["source_id"] != row["id"]:
        raise TreasuryConflict(
            "This actual event is retained for another Collector action."
        )
    linked = conn.execute(
        """select l.source_id from treasury.source_links l join treasury.events e on e.id=l.event_id
        where e.account_id=%s and e.provider=%s and e.reference=%s limit 1""",
        (account["id"], command.provider, command.reference),
    ).fetchone()
    if linked and str(linked["source_id"]) != row["id"]:
        raise TreasuryConflict("This actual event is already linked to another source.")
    return row


def link_debit(service, conn, actor, account, event, command):
    row = load(conn, "actions", command.source_id, command.source_version)
    independent(actor, row)
    check_account(account, row)
    require_account(conn, actor, UUID(row["origin_account_id"]), PREFIX + "settle")
    require_account(conn, actor, account["id"], PREFIX + "settle")
    if row["credit_id"] and load(conn, "credits", UUID(row["credit_id"]))["frozen"]:
        raise TreasuryConflict(
            "Collector source recovery is unresolved; the actual debit remains unclassified."
        )
    expected = (
        "exception_return"
        if command.purpose == "collector_custody_exception_return"
        else "return"
    )
    if (
        row["kind"] != expected
        or row["status"] != "reserved"
        or command.direction != "debit"
        or command.amount != row["amount"]
        or str(command.payee_id) != row["collector_user_id"]
    ):
        raise TreasuryConflict(
            "The verified debit does not match one current approved Collector return."
        )
    if conn.execute(
        "select 1 from treasury.source_links where event_id=%s", (event["id"],)
    ).fetchone():
        raise TreasuryConflict("This event is already linked to another source.")
    row = update(
        conn,
        "actions",
        row,
        {
            "status": "debited_confirmation_pending",
            "event_id": str(event["id"]),
            "event_version": 1,
        },
    )
    conn.execute(
        "insert into treasury.source_links(id,event_id,ledger_context_id,source_kind,source_id,source_version,linked_amount) values(%s,%s,%s,%s,%s,%s,%s)",
        (
            identity(event["id"], "collector-return-link"),
            event["id"],
            account["ledger_context_id"],
            command.purpose,
            UUID(row["id"]),
            command.source_version,
            Decimal(row["amount"]),
        ),
    )
    return {
        "status": "confirmation_pending",
        "source_id": row["id"],
        "source_version": command.source_version,
        "observed_event_id": str(event["id"]),
        "disposition": "return_debited_confirmation_pending",
        "action_record": row,
    }


def acknowledge(service, conn, actor, account, command):
    target = own_target(conn, actor, command)
    kind = "exceptions" if hasattr(command, "exception_id") else "credits"
    target = load(
        conn,
        kind,
        UUID(target["id"]),
        command.exception_version if kind == "exceptions" else command.credit_version,
    )
    row = load(conn, "actions", command.action_id, command.action_version)
    if (
        row["collector_user_id"] != str(actor.user_id)
        or (row.get("credit_id") or row.get("exception_id")) != target["id"]
    ):
        raise TreasuryDenied("Only the original Collector can acknowledge this return.")
    if (
        row["status"] != "debited_confirmation_pending"
        or row["event_id"] != str(command.event_id)
        or row["event_version"] != command.event_version
        or row["amount"] != command.reviewed_amount
        or command.acknowledged_at > service.clock()
    ):
        raise TreasuryConflict(
            "Review the exact actual return event and principal before acknowledgment."
        )
    ack = save(
        conn,
        "acknowledgments",
        account,
        actor.user_id,
        identity(command.request_id, "ack"),
        {
            "action_id": row["id"],
            "event_id": row["event_id"],
            "event_version": row["event_version"],
            "reviewed_amount": row["amount"],
            "confirmation": command.confirmation,
            "acknowledged_at": command.acknowledged_at,
            "recorded_at": service.clock(),
            "reason": command.reason,
        },
    )
    return outcome(
        ack,
        "acknowledgment",
        "acknowledged_" + command.confirmation,
        action_record=row,
        exception=target if kind == "exceptions" else None,
        credit=None if kind == "exceptions" else target,
    )


def settle(service, conn, actor, account, command):
    row = load(conn, "actions", command.action_id, command.action_version)
    independent(actor, row)
    check_account(account, row)
    ack = load(
        conn,
        "acknowledgments",
        command.acknowledgment_id,
        command.acknowledgment_version,
    )
    latest = conn.execute(
        "select id from treasury.collector_acknowledgments where action_id=%s order by record_sequence desc limit 1",
        (UUID(row["id"]),),
    ).fetchone()
    if (
        row["status"] != "debited_confirmation_pending"
        or not latest
        or str(latest["id"]) != ack["id"]
        or ack["action_id"] != row["id"]
        or ack["confirmation"] != "received"
        or row["event_id"] != str(command.event_id)
        or row["event_version"] != command.event_version
        or ack["event_id"] != row["event_id"]
    ):
        raise TreasuryConflict(
            "Exact independent received acknowledgment is required; unconfirmed debit remains reserved."
        )
    event = conn.execute(
        "select * from treasury.events where id=%s and account_id=%s",
        (command.event_id, account["id"]),
    ).fetchone()
    if (
        not event
        or conn.execute(
            "select 1 from treasury.event_revisions where event_id=%s",
            (command.event_id,),
        ).fetchone()
    ):
        raise TreasuryConflict(
            "Return event was revised; retain reservation for recovery."
        )
    service.evidence(conn, account["id"], event["evidence_id"], {"recipient"})
    amount = Decimal(row["amount"])
    if row["credit_id"]:
        target = credit_change(
            conn,
            load(conn, "credits", UUID(row["credit_id"])),
            reserved_amount=-amount,
            returned_amount=amount,
        )
        save(
            conn,
            "entries",
            account,
            UUID(row["collector_user_id"]),
            identity(command.request_id, "return-entry"),
            {
                "credit_id": target["id"],
                "kind": "return",
                "amount": amount,
                "action_id": row["id"],
            },
        )
        slot = "credit"
        disposition = "paid"
    else:
        target = exception_change(
            conn,
            load(conn, "exceptions", UUID(row["exception_id"])),
            reserved_amount=-amount,
            returned_amount=amount,
        )
        slot = "exception"
        disposition = "exception_returned"
    row = update(
        conn, "actions", row, {"status": "paid", "acknowledgment_id": ack["id"]}
    )
    return outcome(
        row,
        "action_record",
        disposition,
        acknowledgment=ack,
        source_account_id=row["origin_account_id"],
        credit=target if slot == "credit" else None,
        exception=target if slot == "exception" else None,
    )


def reverse_return(service, conn, actor, account, command):
    row = load(conn, "actions", command.action_id, command.action_version)
    independent(actor, row)
    check_account(account, row)
    require_account(conn, actor, account["id"], "treasury.disbursement.record")
    require_account(conn, actor, UUID(row["origin_account_id"]), PREFIX + "settle")
    if row["kind"] != "return" or row["status"] not in {"paid", "partly_reversed"}:
        raise TreasuryConflict(
            "Only a previously paid Collector return can be reopened by an actual incoming reversal."
        )
    reversed_amount = Decimal(row.get("reversed_amount", "0.00"))
    amount = Decimal(command.amount)
    if amount > Decimal(row["amount"]) - reversed_amount:
        raise TreasuryConflict(
            "Actual incoming reversal exceeds the remaining previously paid principal."
        )
    credit = load(conn, "credits", UUID(row["credit_id"]))
    if credit["frozen"]:
        raise TreasuryConflict(
            "Conflicting source recovery requires an independent decision before credit is reopened."
        )
    event, _ = service.record_verified_event(
        conn,
        actor,
        account,
        {
            "id": identity(command.request_id, "collector-reversal"),
            "provider": command.provider,
            "reference": command.reference,
            "direction": "credit",
            "amount": amount,
            "fee": Decimal("0.00"),
            "effective_at": command.effective_at,
            "evidence_id": command.evidence_id,
            "recipient_attestation": command.recipient_attestation,
            "classification": "collector_return_reversal",
            "reason": command.reason,
        },
    )
    if conn.execute(
        "select 1 from treasury.source_links where event_id=%s", (event["id"],)
    ).fetchone():
        raise TreasuryConflict(
            "Actual incoming event is already attributed to a source."
        )
    conn.execute(
        "insert into treasury.source_links(id,event_id,ledger_context_id,source_kind,source_id,source_version,linked_amount) values(%s,%s,%s,'collector_surplus_return_reversal',%s,%s,%s)",
        (
            identity(event["id"], "reversal-link"),
            event["id"],
            account["ledger_context_id"],
            UUID(row["id"]),
            row["version"],
            amount,
        ),
    )
    credit = credit_change(conn, credit, returned_amount=-amount)
    save(
        conn,
        "entries",
        account,
        UUID(row["collector_user_id"]),
        identity(command.request_id, "reversal-entry"),
        {
            "credit_id": credit["id"],
            "kind": "return_reversal",
            "amount": amount,
            "action_id": row["id"],
            "incoming_event_id": str(event["id"]),
            "evidence_id": str(command.evidence_id),
        },
    )
    row = update(
        conn,
        "actions",
        row,
        {
            "reversed_amount": reversed_amount + amount,
            "status": "reversed"
            if reversed_amount + amount == Decimal(row["amount"])
            else "partly_reversed",
        },
    )
    return outcome(
        row,
        "action_record",
        "return_reversed",
        credit=credit,
        incoming_event=json_value(event),
        source_account_id=row["origin_account_id"],
    )


def source_changed(service, conn, account, command, detail):
    if command.action not in {
        "collector_count_accept",
        "collector_surplus_recognize",
        "collector_surplus_return_prepare",
        "collector_surplus_return_record",
        "collector_surplus_return_reverse",
        "collector_surplus_action_cancel",
        "collector_surplus_opening_activate",
        "collector_custody_exception_record",
        "collector_custody_exception_return_prepare",
        "collector_surplus_resolve_source",
    }:
        return
    if detail["disposition"] == "blocked_adapter":
        return
    basis = (
        detail.get("count")
        or detail.get("exception")
        or detail.get("credit")
        or detail.get("case")
        or detail.get("opening_anchor")
    )
    effective = source_effective(conn, basis)
    accounts = {account["id"]}
    if detail.get("source_account_id"):
        accounts.add(UUID(detail["source_account_id"]))
    for account_id in sorted(accounts, key=str):
        conn.execute(
            "update treasury.accounts set collector_source_watermark=collector_source_watermark+1,version=version+1 where id=%s",
            (account_id,),
        )
        service.flag_late(conn, account_id, effective)


def source_effective(conn, row):
    from datetime import datetime

    if row.get("counted_at"):
        return datetime.fromisoformat(row["counted_at"])
    if row.get("cutoff"):
        return datetime.fromisoformat(row["cutoff"])
    if row.get("count_id"):
        return source_effective(
            conn, load(conn, "counts", UUID(row["count_id"]), lock=False)
        )
    if row.get("settlement_id"):
        return source_effective(
            conn, load(conn, "settlements", UUID(row["settlement_id"]), lock=False)
        )
    if row.get("case_id"):
        return source_effective(
            conn, load(conn, "cases", UUID(row["case_id"]), lock=False)
        )
    if row.get("opening_anchor_id"):
        return source_effective(
            conn, load(conn, "openings", UUID(row["opening_anchor_id"]), lock=False)
        )
    raise TreasuryConflict("Original dated Collector source is unavailable.")


def source_summary(conn, account_id):
    if not conn.execute(
        "select to_regclass('treasury.collector_cases') as relation"
    ).fetchone()["relation"]:
        return {"as_of": "current", "available": False}

    def total(kind, key):
        return format(
            conn.execute(
                sql.SQL(
                    "select coalesce(sum((payload->>{})::numeric),0) as amount from treasury.{} where account_id=%s"
                ).format(sql.Literal(key), sql.Identifier(TABLES[kind])),
                (account_id,),
            ).fetchone()["amount"],
            ".2f",
        )

    pending = total("cases", "unidentified_amount")
    outstanding = total("credits", "outstanding_amount")
    held = total("exceptions", "remaining_held_amount")
    reserved = total("credits", "reserved_amount")
    recovery = conn.execute(
        """select count(*) as n,coalesce(sum((payload->>'outstanding_amount')::numeric),0) as amount
        from treasury.collector_credits where account_id=%s
        and ((payload->>'frozen')::boolean or payload->>'status'='recovery_required')""",
        (account_id,),
    ).fetchone()
    return {
        "as_of": "current",
        "available": True,
        "pending_identification_amount": pending,
        "collector_outstanding_amount": outstanding,
        "collector_reserved_amount": reserved,
        "held_dispute_amount": held,
        "collector_recovery_count": recovery["n"],
        "collector_recovery_amount": format(recovery["amount"], ".2f"),
        "source_resolved": pending == "0.00" and held == "0.00" and recovery["n"] == 0,
        "gl_posting_available": False,
        "message": "Cash close does not settle unidentified sources, Collector liabilities, frozen source recovery or disputed custody. Protected liability GL mapping is unavailable.",
    }
