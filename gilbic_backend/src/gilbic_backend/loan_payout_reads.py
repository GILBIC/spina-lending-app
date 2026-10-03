"""Source-aware history remains available with entry disabled; own reads are narrow."""

from .loan_payout_acknowledgments import own_scope, projection
from .loan_payout_sources import current_source
from .loan_payouts import replay_authority
from .office_review_evidence_storage import EvidenceFileError
from .treasury_authorization import (
    TreasuryConflict,
    TreasuryDenied,
    readiness,
    require_account,
    require_actor,
    require_live_permission,
)
from .treasury_models import LoanPayoutPreview
from .treasury_repository import json_value


def staff_scope(conn, actor, kind):
    require_live_permission(
        conn,
        actor,
        "lending.first_loan.release" if kind == "first_loan" else "renewal.manage",
    )


def workspace(service, actor, *, account_id=None, mode="own", limit=50, offset=0):
    if (
        mode not in {"own", "staff"}
        or not 1 <= limit <= 100
        or not 0 <= offset <= 100000
    ):
        raise TreasuryConflict("Choose a valid payout page.")
    with service.connect() as conn, conn.transaction():
        require_actor(conn, actor)
        if mode == "staff":
            if account_id is None:
                raise TreasuryDenied("Select the authorized funding account.")
            require_account(conn, actor, account_id, "treasury.disbursement.record")
            query, params = "p.account_id=%s", (account_id,)
        else:
            if account_id is not None:
                raise TreasuryDenied(
                    "Own payout history carries no whole-account access."
                )
            query, params = (
                "(c.user_id=%s or (p.destination='collector' and p.collector_user_id=%s and lending.collector_area_owner(c.area)=%s))",
                (actor.user_id, actor.user_id, actor.user_id),
            )
        rows = conn.execute(
            "select p.* from treasury.loan_payouts p join lending.clients c on c.id=p.client_id where "
            + query
            + " order by p.created_at desc,p.id desc limit %s offset %s",
            (*params, limit + 1, offset),
        ).fetchall()
        items = []
        for row in rows[:limit]:
            stages = []
            if mode == "staff":
                try:
                    staff_scope(conn, actor, row["source_kind"])
                except TreasuryDenied:
                    continue
                item = json_value(row)
            else:
                for stage in ("recipient", "borrower_handover", "borrower"):
                    try:
                        own_scope(conn, actor, row, stage)
                        stages.append(stage)
                    except TreasuryDenied:
                        continue
                if not stages:
                    continue
                item = projection(row)
                # Opaque account/context IDs bind an exact submitted-result recovery,
                # without account aliases, references, balances or history.
                item.update(
                    account_id=str(row["account_id"]),
                    ledger_context_id=str(row["ledger_context_id"]),
                )
            blocker = None
            try:
                with conn.transaction():
                    replay_authority(
                        service, conn, actor, row, staff_authority=mode == "staff"
                    )
            except (TreasuryConflict, TreasuryDenied, EvidenceFileError) as error:
                blocker = (
                    str(error)
                    if mode == "staff"
                    else "This payout needs staff review before another acknowledgment."
                )
            item.update(
                blocker=blocker,
                stages=stages,
                funding_method=row["source_snapshot"].get("funding_method"),
            )
            items.append(item)
        return {
            "contract_version": 1,
            "actor": {
                "user_id": str(actor.user_id),
                "device_id": str(actor.registered_device_id),
            },
            "mode": mode,
            "account_id": str(account_id) if account_id else None,
            "enabled": readiness()["enabled"] and readiness()["owner_configured"],
            "items": items,
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
        }


def catalogue(service, actor, account_id):
    with service.connect() as conn, conn.transaction():
        account = require_account(
            conn, actor, account_id, "treasury.disbursement.record"
        )
        if account["kind"] not in {"gcash", "bank"}:
            raise TreasuryConflict("Choose the specific funding wallet or bank.")
        candidates = []
        try:
            staff_scope(conn, actor, "first_loan")
            candidates.extend(
                conn.execute("""select 'first_loan' as source_kind,a.loan_id as source_id,a.packet_hash,
                auth.id as authorization_id,'office-evidence:'||e.id::text as contract_evidence_reference
                from lending.first_loan_approvals a join lending.loans l on l.id=a.loan_id
                join lateral (select id from lending.first_loan_authorizations where loan_id=a.loan_id order by authorized_at desc,id desc limit 1) auth on true
                join lateral (select id from lending.office_review_evidence where subject_id=a.id and purpose='borrower_contract_signed' order by captured_at desc,id desc limit 1) e on true
                where l.status='approved' and not exists(select 1 from treasury.loan_payouts p where p.loan_id=l.id and p.status<>'cancelled')
                order by a.approved_at desc,a.id desc limit 100""").fetchall()
            )
        except TreasuryDenied:
            pass
        try:
            staff_scope(conn, actor, "renewal")
            candidates.extend(
                conn.execute("""select 'renewal' as source_kind,r.id as source_id from lending.client_renewal_requests r
                where r.status='approved' and r.client_decision='accepted' and r.activation_status<>'active'
                and r.cash_released_to_collector_at is null
                and not exists(select 1 from treasury.loan_payouts p where p.source_kind='renewal' and p.source_id=r.id and p.status<>'cancelled')
                order by r.submitted_at desc,r.id desc limit 100""").fetchall()
            )
        except TreasuryDenied:
            pass
        items = []
        for candidate in candidates:
            command = LoanPayoutPreview(
                **candidate,
                account_id=account_id,
                expected_version=account["version"],
                destination="borrower",
                recipient_reference="unselected",
            )
            try:
                with conn.transaction():
                    source = current_source(conn, actor, command)
                    if source["amount"] == "0.00":
                        continue
                    items.append(
                        json_value(
                            {
                                **candidate,
                                "amount": source["amount"],
                                "label": source["label"],
                            }
                        )
                    )
            except (TreasuryConflict, TreasuryDenied, EvidenceFileError):
                continue
        return {
            "contract_version": 1,
            "actor": {
                "user_id": str(actor.user_id),
                "device_id": str(actor.registered_device_id),
            },
            "account_id": str(account_id),
            "account_version": account["version"],
            "items": items,
        }
