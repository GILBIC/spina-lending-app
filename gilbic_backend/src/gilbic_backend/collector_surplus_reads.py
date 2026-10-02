"""Server totals and current own/staff scope; no private-wallet projection."""

import os
from typing import Any
from uuid import UUID

from psycopg import sql

from .collector_surplus import PREFIX, TABLES, current_collector, enabled, load
from .treasury_authorization import (
    TreasuryConflict,
    TreasuryDenied,
    is_owner,
    readiness,
    require_account,
    require_actor,
)
from .treasury_repository import json_value

KINDS = {
    "credits",
    "cases",
    "actions",
    "requests",
    "counts",
    "exceptions",
    "remittances",
    "openings",
}
PRIVATE = {
    "source_snapshot",
    "evidence_id",
    "cancellation_evidence_id",
    "recipient_attestation",
    "holder_attestation",
    "reason",
    "source_id",
    "opening_version",
}
CAP_ACTIONS = {
    "receive": ["count_record", "count_accept", "exception_record"],
    "resolve": ["recognize", "opening_prepare", "opening_activate"],
    "settle": [
        "return_prepare",
        "return_record",
        "action_cancel",
        "return_reverse",
        "exception_return_prepare",
    ],
    "view": [],
}
TOTALS = {
    "credits": [
        "recognized_amount",
        "reclassified_amount",
        "returned_amount",
        "applied_amount",
        "outstanding_amount",
        "reserved_amount",
        "available_amount",
    ],
    "cases": ["received_excess_amount", "unidentified_amount"],
    "exceptions": [
        "retained_amount",
        "returned_amount",
        "included_amount",
        "remaining_held_amount",
        "reserved_amount",
        "available_amount",
    ],
    "actions": ["reserved_amount"],
}


OWN_ROW_FIELDS = {
    "id",
    "version",
    "account_id",
    "ledger_context_id",
    "collector_user_id",
    "created_at",
    "remittance_id",
    "recipient_user_id",
    "source_digest",
    "gross_obligation",
    "refund_due_total",
    "physical_cash_required",
    "counted_amount",
    "difference",
    "counted_at",
    "recorded_at",
    "disposition",
    "settlement_id",
    "opening_id",
    "opening_anchor_id",
    "received_excess_amount",
    "unidentified_amount",
    "status",
    "resolutions",
    "case_id",
    "origin_account_id",
    "recognized_amount",
    "reclassified_amount",
    "returned_amount",
    "applied_amount",
    "outstanding_amount",
    "reserved_amount",
    "available_amount",
    "frozen",
    "entries",
    "kind",
    "credit_id",
    "amount",
    "destination",
    "action_id",
    "event_id",
    "event_version",
    "reviewed_amount",
    "confirmation",
    "acknowledged_at",
    "exception_id",
    "collector_request_id",
    "paying_account_id",
    "acknowledgment_id",
    "acknowledgment",
    "holder_user_id",
    "retained_amount",
    "included_amount",
    "remaining_held_amount",
    "cutoff",
    "anchor_kind",
    "reversed_amount",
    "count_id",
    "physical_amount",
    "authorized_credit_amount",
    "accepted_at",
    "remittance_number",
    "collection_date",
    "total_amount",
    "submitted_at",
    "application_request_supported",
}


def redacted(row: Any) -> Any:
    if isinstance(row, list):
        return [redacted(item) for item in row]
    if isinstance(row, dict):
        if "id" in row and "collector_user_id" in row:
            safe = {
                key: redacted(value)
                for key, value in row.items()
                if key in OWN_ROW_FIELDS
            }
            if "entries" in row:
                safe["entries"] = [
                    {
                        key: item[key]
                        for key in ["id", "kind", "amount", "action_id", "created_at"]
                        if key in item
                    }
                    for item in row["entries"]
                ]
            if "resolutions" in row:
                safe["resolutions"] = [
                    {
                        key: item[key]
                        for key in ["id", "kind", "amount", "status", "created_at"]
                        if key in item
                    }
                    for item in row["resolutions"]
                ]
            return safe
        return {
            key: redacted(value) for key, value in row.items() if key not in PRIVATE
        }
    return row


def own_mode(conn, actor):
    roles = {
        row["code"]
        for row in conn.execute(
            "select r.code from core.user_roles ur join core.roles r on r.id=ur.role_id where ur.user_id=%s for share of ur,r",
            (actor.user_id,),
        ).fetchall()
    }
    if "collector" in roles and not is_owner(actor):
        return True
    if "client" in roles and not is_owner(actor):
        raise TreasuryDenied(
            "Collector liability history is unavailable to Client accounts."
        )
    return False


def scoped_accounts(conn, actor):
    result = []
    candidates = conn.execute(
        """select a.* from treasury.accounts a join treasury.contexts c on c.id=a.ledger_context_id
      left join treasury.account_access g on g.account_id=a.id and g.user_id=%s and g.enabled
      where a.active and ((%s and c.created_by=%s) or g.user_id is not null) order by a.id""",
        (actor.user_id, is_owner(actor), actor.user_id),
    ).fetchall()
    for account in candidates:
        perms = []
        for permission in ["view", "receive", "resolve", "settle"]:
            try:
                require_account(
                    conn, actor, account["id"], PREFIX + permission, lock=False
                )
            except TreasuryDenied:
                continue
            if permission == "receive":
                if (
                    account["kind"] != "physical_cash"
                    or account["custodian_user_id"] != actor.user_id
                ):
                    continue
                if not conn.execute(
                    "select 1 from core.user_roles ur join core.role_permissions rp on rp.role_id=ur.role_id where ur.user_id=%s and rp.permission_code='remittance.receive'",
                    (actor.user_id,),
                ).fetchone():
                    continue
            perms.append(permission)
        if perms:
            result.append(
                {
                    "id": str(account["id"]),
                    "ledger_context_id": str(account["ledger_context_id"]),
                    "kind": account["kind"],
                    "alias": account["alias"],
                    "version": account["version"],
                    "custodian_user_id": str(account["custodian_user_id"]),
                    "actions": [cap for perm in perms for cap in CAP_ACTIONS[perm]]
                    + ["evidence_upload"],
                    "_permissions": perms,
                }
            )
    return result


def scope(
    conn, actor, account_id=None, collector_user_id=None, kind="credits", mode=None
):
    require_actor(conn, actor)
    if mode == "own":
        current_collector(conn, actor, actor.user_id)
        if collector_user_id and collector_user_id != actor.user_id:
            raise TreasuryDenied("Only own Collector records are available.")
        return True, [], actor.user_id
    own = own_mode(conn, actor)
    accounts = scoped_accounts(conn, actor) if not own or mode != "own" else []
    if own and accounts and mode != "own":
        own = False
    if mode == "staff" and own:
        raise TreasuryDenied("Current scoped staff authority is required.")
    if own:
        current_collector(conn, actor, actor.user_id)
        if collector_user_id and collector_user_id != actor.user_id:
            raise TreasuryDenied("Only own Collector records are available.")
        return True, [], actor.user_id
    required = {
        "counts": {"receive", "view"},
        "settlements": {"receive", "view"},
        "remittances": {"receive", "view"},
        "exceptions": {"receive", "settle", "view"},
        "cases": {"resolve", "settle", "view"},
        "credits": {"resolve", "settle", "view"},
        "requests": {"settle", "view"},
        "actions": {"settle", "view"},
        "openings": {"resolve", "view"},
        "acknowledgments": {"settle", "view"},
        "entries": {"resolve", "settle", "view"},
        "resolutions": {"resolve", "view"},
    }[kind]
    accounts = [row for row in accounts if required.intersection(row["_permissions"])]
    if account_id:
        accounts = [row for row in accounts if row["id"] == str(account_id)]
    if not accounts:
        raise TreasuryDenied("Current scoped Collector surplus permission is required.")
    return False, accounts, collector_user_id


def detail(service, conn, actor, kind, target, mode=None):
    require_actor(conn, actor)
    row = load(conn, kind, target, lock=False)
    own, accounts, _collector = scope(conn, actor, kind=kind, mode=mode)
    if own:
        current_collector(conn, actor, row["collector_user_id"])
        row = redacted(row)
    elif row["account_id"] not in {a["id"] for a in accounts}:
        raise TreasuryDenied("Collector record is outside current account scope.")
    if kind == "credits":
        entries = conn.execute(
            "select id from treasury.collector_entries where credit_id=%s order by created_at,id",
            (target,),
        ).fetchall()
        row["entries"] = []
        for item in entries:
            entry = load(conn, "entries", item["id"], lock=False)
            if entry["account_id"] != row["account_id"] and not own:
                try:
                    require_account(
                        conn,
                        actor,
                        UUID(entry["account_id"]),
                        "treasury.disbursement.record",
                        lock=False,
                    )
                except TreasuryDenied:
                    entry = redacted(entry)
            row["entries"].append(entry)
    if kind == "cases":
        entries = conn.execute(
            "select id from treasury.collector_resolutions where case_id=%s order by created_at,id",
            (target,),
        ).fetchall()
        row["resolutions"] = [
            load(conn, "resolutions", item["id"], lock=False) for item in entries
        ]
    if kind == "actions":
        ack = conn.execute(
            "select id from treasury.collector_acknowledgments where action_id=%s order by record_sequence desc limit 1",
            (target,),
        ).fetchone()
        row["acknowledgment"] = (
            load(conn, "acknowledgments", ack["id"], lock=False) if ack else None
        )
    if own:
        row = redacted(row)
    return row


def workspace(
    service,
    conn,
    actor,
    kind="credits",
    account_id=None,
    collector_user_id=None,
    limit=50,
    offset=0,
    export=False,
    mode=None,
):
    if kind not in KINDS or not 1 <= limit <= 100 or not 0 <= offset <= 100000:
        raise TreasuryDenied("Invalid bounded Collector projection.")
    own, accounts, collector = scope(
        conn, actor, account_id, collector_user_id, kind, mode
    )
    account_ids = [UUID(row["id"]) for row in accounts]
    if (
        own
        and account_id
        and not conn.execute(
            "select 1 from treasury.accounts where id=%s and active", (account_id,)
        ).fetchone()
    ):
        raise TreasuryDenied("Account is unavailable.")
    params = []
    clauses = []
    if kind == "remittances":
        table = sql.SQL("lending.collection_remittances")
        order = sql.SQL("submitted_at desc,id desc")
        if own:
            clauses.append(sql.SQL("collector_user_id=%s"))
            params.append(collector)
        else:
            clauses.append(sql.SQL("recipient_user_id=%s"))
            params.append(actor.user_id)
    else:
        table = sql.SQL("treasury.{}").format(sql.Identifier(TABLES[kind]))
        order = sql.SQL("created_at desc,id desc")
        if own:
            clauses.append(sql.SQL("collector_user_id=%s"))
            params.append(collector)
        else:
            clauses.append(sql.SQL("account_id=any(%s)"))
            params.append(account_ids)
        if own and account_id:
            clauses.append(sql.SQL("account_id=%s"))
            params.append(account_id)
    if collector and not own:
        clauses.append(sql.SQL("collector_user_id=%s"))
        params.append(collector)
    where = sql.SQL(" and ").join(clauses)
    count_row = conn.execute(
        sql.SQL("select count(*) as n from {} where {}").format(table, where),
        tuple(params),
    ).fetchone()
    total_count = count_row["n"]
    paging = sql.SQL("") if export else sql.SQL(" limit %s offset %s")
    rows = conn.execute(
        sql.SQL("select * from {} where {} order by {}{}").format(
            table, where, order, paging
        ),
        tuple(params) if export else (*params, limit, offset),
    ).fetchall()
    if kind == "remittances":
        from .collector_settlement import source_snapshot

        items = []
        for row in rows:
            item = json_value(
                {
                    key: row[key]
                    for key in [
                        "id",
                        "remittance_number",
                        "collector_user_id",
                        "recipient_user_id",
                        "collection_date",
                        "status",
                        "total_amount",
                        "submitted_at",
                    ]
                }
            )
            item["remittance_id"] = str(row["id"])
            item.update(source_digest=None, application_request_supported=False)
            if row["status"] == "submitted":
                try:
                    _source, _snapshot, digest, gross, refund = source_snapshot(
                        conn, row["id"]
                    )
                    item.update(
                        source_digest=digest,
                        gross_obligation=format(gross, ".2f"),
                        refund_due_total=format(refund, ".2f"),
                        physical_cash_required=format(gross - refund, ".2f"),
                        application_request_supported=True,
                    )
                except TreasuryConflict:
                    pass
            items.append(item)
    else:
        items = [load(conn, kind, row["id"], lock=False) for row in rows]
    totals = {}
    for key in TOTALS.get(kind, []):
        expr = (
            sql.SQL(
                "case when payload->>'status' in ('reserved','debited_confirmation_pending') then (payload->>'amount')::numeric else 0 end"
            )
            if kind == "actions"
            else sql.SQL("(payload->>{})::numeric").format(sql.Literal(key))
        )
        amount = conn.execute(
            sql.SQL("select coalesce(sum({}),0) as amount from {} where {}").format(
                expr, table, where
            ),
            tuple(params),
        ).fetchone()["amount"]
        totals[key] = format(amount, ".2f")
    if own:
        items = redacted(items)
    caps = {
        key: False
        for key in [
            "view",
            "count_record",
            "count_accept",
            "recognize",
            "return_prepare",
            "return_record",
            "action_cancel",
            "return_reverse",
            "return_request",
            "return_acknowledge",
            "application_request",
            "application_prepare",
            "resolve_source",
            "opening_prepare",
            "opening_activate",
            "exception_record",
            "exception_return_prepare",
            "exception_acknowledge",
        ]
    }
    caps["view"] = True
    if enabled() and readiness()["enabled"] and readiness()["owner_configured"]:
        if own:
            for key in [
                "return_request",
                "return_acknowledge",
                "application_request",
                "exception_acknowledge",
            ]:
                caps[key] = True
        else:
            for account in accounts:
                for key in account["actions"]:
                    if key in caps:
                        caps[key] = True
            if not is_owner(actor):
                caps["opening_prepare"] = caps["opening_activate"] = False
    choices = []
    if not own:
        if is_owner(actor):
            query = "select distinct u.id,u.full_name from core.users u join core.user_roles ur on ur.user_id=u.id join core.roles r on r.id=ur.role_id where u.status='active' and r.code='collector' order by u.id"
            args = ()
        else:
            query = "select distinct u.id,u.full_name from lending.collection_remittances r join core.users u on u.id=r.collector_user_id where r.recipient_user_id=%s and u.status='active' order by u.id"
            args = (actor.user_id,)
        choices = [
            {"id": str(row["id"]), "full_name": row["full_name"]}
            for row in conn.execute(query, args).fetchall()
        ]
    opening_choices = []
    if not own and is_owner(actor):
        opening_choices = json_value(
            conn.execute(
                "select p.id,p.account_id,p.version,p.cutoff,p.amount,p.status from treasury.opening_positions p join treasury.accounts a on a.id=p.account_id where p.status='active' and a.kind='physical_cash' and a.id=any(%s) order by p.cutoff,p.id",
                (account_ids,),
            ).fetchall()
        )
    for account in accounts:
        account.pop("_permissions", None)
    state = readiness()
    return {
        "collector_surplus_contract_version": 1,
        "actor": {
            "user_id": str(actor.user_id),
            "device_id": str(actor.registered_device_id),
        },
        "mode": "own" if own else "staff",
        "readiness": {
            "enabled": enabled(),
            "treasury_ready": state["enabled"] and state["owner_configured"],
            "application_enabled": os.getenv(
                "SPINA_COLLECTOR_SURPLUS_APPLICATION_ENABLED", ""
            ).lower()
            == "true",
            "application_supported": False,
            "historical_correction_supported": False,
            "gl_supported": False,
            "blockers": [
                {
                    "code": "collector_application_custody_unavailable",
                    "message": "Application custody adapter is unavailable.",
                },
                {
                    "code": "collector_historical_source_unavailable",
                    "message": "Historical correction adapter is unavailable.",
                },
                {
                    "code": "collector_gl_mapping_unavailable",
                    "message": "Collector liability GL mapping is not configured; no automatic posting.",
                },
            ],
        },
        "capabilities": caps,
        "accounts": accounts,
        "collector_choices": choices,
        "opening_choices": opening_choices,
        "kind": kind,
        "items": items,
        "total_count": total_count,
        "totals": totals,
        "has_more": False if export else offset + limit < total_count,
        "limit": limit,
        "offset": offset,
    }
