"""Actual movement first; typed source execution never fabricates cash acknowledgment."""

from decimal import Decimal

from psycopg import sql

from .treasury_authorization import (
    TreasuryConflict,
    TreasuryDenied,
    is_owner,
    require_account,
)
from .treasury_repository import identity, json_value


def source_choices(conn, actor):
    # Existing salary/advance payment authority is owner-only, independently of
    # account-access grants. This projection does not expose payroll to delegates.
    from .collector_surplus import load, observed_debit

    result = []
    for item in conn.execute(
        "select id,account_id from treasury.collector_actions where payload->>'status'='reserved' order by created_at,id"
    ).fetchall():
        try:
            require_account(
                conn,
                actor,
                item["account_id"],
                "treasury.disbursement.record",
                lock=False,
            )
            require_account(
                conn,
                actor,
                item["account_id"],
                "treasury.collector_surplus.settle",
                lock=False,
            )
            row = load(conn, "actions", item["id"], lock=False)
            if observed_debit(conn, row["id"]):
                continue
            require_account(
                conn,
                actor,
                row["origin_account_id"],
                "treasury.collector_surplus.settle",
                lock=False,
            )
            if row["collector_user_id"] == str(actor.user_id):
                continue
            account = conn.execute(
                "select kind from treasury.accounts where id=%s", (item["account_id"],)
            ).fetchone()
            result.append(
                {
                    "id": row["id"],
                    "kind": "collector_custody_exception_return"
                    if row["kind"] == "exception_return"
                    else "collector_surplus_return",
                    "version": row["version"],
                    "payee_id": row["collector_user_id"],
                    "account_id": str(item["account_id"]),
                    "provider": account["kind"],
                    "amount": row["amount"],
                    "currency": "PHP",
                    "status": "reserved",
                    "supported": True,
                    "partial_supported": False,
                    "destination": row["destination"],
                }
            )
        except TreasuryDenied:
            continue
    if not is_owner(actor):
        return result
    for kind, table, amount_field, statuses in [
        ("payroll", "employee_payroll", "balance_due", ["approved", "partially_paid"]),
        ("salary_advance", "employee_advances", "amount", ["approved"]),
    ]:
        rows = conn.execute(
            sql.SQL("""select p.*,u.full_name as payee_name from core.{} p
            join core.users u on u.id=p.employee_id where p.status=any(%s) order by p.created_at,p.id""").format(
                sql.Identifier(table)
            ),
            (statuses,),
        ).fetchall()
        for row in rows:
            amount = row["payload"].get(amount_field)
            result.append(
                json_value(
                    {
                        "id": row["id"],
                        "kind": kind,
                        "version": row["version"],
                        "payee_id": row["employee_id"],
                        "payee_name": row["payee_name"],
                        "amount": amount,
                        "currency": "PHP",
                        "status": row["status"],
                        "supported": amount is not None,
                        "partial_supported": kind == "payroll",
                        "blocker": None
                        if amount is not None
                        else "Approved source amount is unavailable.",
                    }
                )
            )
    # The current first-loan cash-release contract includes borrower/office/signature
    # custody evidence. A wallet observation cannot mark that source released.
    office_permission = conn.execute(
        """select 1 from core.user_roles ur join core.role_permissions rp on rp.role_id=ur.role_id
        where ur.user_id=%s and rp.permission_code='client_onboarding.requirement.review' limit 1""",
        (actor.user_id,),
    ).fetchone()
    for row in (
        conn.execute(
            "select id,loan_number,client_id,principal,status from lending.loans where date_released is null and status='approved' order by id"
        ).fetchall()
        if office_permission
        else []
    ):
        result.append(
            json_value(
                {
                    "id": row["id"],
                    "kind": "loan_release",
                    "version": None,
                    "payee_id": row["client_id"],
                    "label": row["loan_number"],
                    "amount": row["principal"],
                    "currency": "PHP",
                    "status": row["status"],
                    "supported": False,
                    "blocker": "Existing Office release requires its protected signing and cash custody workflow; wallet execution is not represented.",
                }
            )
        )
    return result


def link_employee_source(service, conn, actor, account, event, command):
    if not is_owner(actor):
        raise TreasuryDenied("Existing employee payout authority is owner-only.")
    if not command.source_id or command.source_version is None or not command.payee_id:
        raise TreasuryConflict(
            "Select a current approved source and its exact payee/version."
        )
    if not command.destination_confirmed or not command.destination_evidence_id:
        raise TreasuryConflict(
            "Actual debit is retained; independently verified destination settlement is required to complete this source."
        )
    evidence = service.evidence(
        conn, account["id"], command.destination_evidence_id, {"recipient"}
    )
    if account["kind"] not in {"gcash", "bank"}:
        raise TreasuryConflict(
            "This typed transfer adapter requires a wallet or bank account; no fictional cash acknowledgment is accepted."
        )
    conn.execute("select pg_advisory_xact_lock(hashtext('spina.employee_operations'))")
    table = "employee_payroll" if command.purpose == "payroll" else "employee_advances"
    source = conn.execute(
        sql.SQL("select * from core.{} where id=%s for update").format(
            sql.Identifier(table)
        ),
        (command.source_id,),
    ).fetchone()
    if source is None or source["employee_id"] != command.payee_id:
        raise TreasuryConflict(
            "The exact approved source/payee/version changed; the observed debit remains an exception."
        )
    linked = conn.execute(
        "select * from treasury.source_links where source_kind=%s and source_id=%s and event_id=%s",
        (command.purpose, command.source_id, event["id"]),
    ).fetchone()
    if linked:
        if (
            linked["linked_amount"] != Decimal(command.amount)
            or linked["source_version"] != command.source_version
        ):
            raise TreasuryConflict(
                "This actual debit is already linked with a different source amount."
            )
        return {
            "status": "completed",
            "source_id": str(command.source_id),
            "already_linked": True,
        }
    if source["version"] != command.source_version:
        raise TreasuryConflict(
            "The exact approved source version changed; the observed debit remains an exception."
        )
    contexts = conn.execute(
        "select ledger_context_id from treasury.source_links where source_kind=%s and source_id=%s for update",
        (command.purpose, command.source_id),
    ).fetchall()
    if any(
        row["ledger_context_id"] != account["ledger_context_id"] for row in contexts
    ):
        raise TreasuryConflict("This source already belongs to another ledger context.")
    from .employee_operations_models import AdvanceDisburse, PayrollPayment
    from .employee_operations_repository import PostgresEmployeeOperationsRepository

    settlement = f"Manually verified private destination evidence {evidence['id']} SHA256 {evidence['sha256']}; {command.recipient_attestation}"
    common = {
        "request_id": identity(event["id"], "source-execution"),
        "id": command.source_id,
        "expected_version": command.source_version,
        "employee_id": command.payee_id,
        "occurred_at": command.effective_at,
        "payment_method": account["kind"],
        "reference": command.reference,
        "settlement_evidence": settlement,
    }
    if command.purpose == "payroll":
        protected = PayrollPayment(
            action="payroll_payment",
            amount=command.amount,
            result="completed",
            **common,
        )
    else:
        if (
            Decimal(source["payload"].get("amount", "-1")) != Decimal(command.amount)
            or not command.payee_acknowledgment
        ):
            raise TreasuryConflict(
                "Advance execution needs the exact whole approved amount and real employee acknowledgment."
            )
        protected = AdvanceDisburse(
            action="advance_disburse",
            employee_acknowledgment=command.payee_acknowledgment,
            **common,
        )
    result = PostgresEmployeeOperationsRepository.execute_in_transaction(
        conn.cursor(), actor=actor, command=protected
    )
    if result.get("status") != "accepted" or result.get("id") != str(command.source_id):
        raise TreasuryConflict("The protected payout result is incomplete.")
    conn.execute(
        """insert into treasury.source_links(id,event_id,ledger_context_id,source_kind,source_id,source_version,linked_amount)
        values(%s,%s,%s,%s,%s,%s,%s)""",
        (
            identity(event["id"], "source-link"),
            event["id"],
            account["ledger_context_id"],
            command.purpose,
            command.source_id,
            command.source_version,
            Decimal(command.amount),
        ),
    )
    return {
        "status": "completed",
        "source_id": str(command.source_id),
        "source_version": result["version"],
        "request_id": result["request_id"],
    }


def outgoing_action(service, conn, actor, account, command):
    if command.action == "transfer_record":
        return transfer(service, conn, actor, account, command)
    if command.reference is None and (
        not is_owner(actor)
        or command.purpose != "unclassified"
        or command.source_id
        or command.receipt_id
        or command.payee_id
    ):
        raise TreasuryDenied(
            "Missing-reference observations are owner-only unresolved items; no business or loan credit is permitted."
        )
    if command.direction == "credit" and (
        command.fee != "0.00"
        or command.purpose
        not in {"unclassified", "personal", "owner_contribution", "deposit"}
    ):
        raise TreasuryConflict(
            "A generic observed credit cannot approve a borrower payment or outgoing business source."
        )
    if command.purpose in {
        "personal",
        "owner_contribution",
        "owner_withdrawal",
        "deposit",
        "unclassified",
    } and not is_owner(actor):
        raise TreasuryDenied(
            "Personal and unclassified whole-account observations require the configured owner."
        )
    business = command.purpose in {
        "loan_release",
        "renewal",
        "payroll",
        "salary_advance",
        "expense",
        "refund",
    }
    collector_action = {}
    if command.purpose.startswith("collector_"):
        from .collector_surplus import PREFIX, debit_authority, require_enabled

        require_enabled()
        require_account(conn, actor, account["id"], PREFIX + "settle")
        if not command.source_id or command.source_version is None:
            raise TreasuryConflict(
                "Exact approved Collector action/version is required."
            )
        collector_action = debit_authority(service, conn, actor, account, command)
    event, new = service.record_verified_event(
        conn,
        actor,
        account,
        {
            "id": identity(command.request_id, "outgoing"),
            "provider": command.provider,
            "reference": command.reference,
            "direction": command.direction,
            "amount": Decimal(command.amount),
            "fee": Decimal(command.fee),
            "effective_at": command.effective_at,
            "evidence_id": command.evidence_id,
            "recipient_attestation": command.recipient_attestation,
            "classification": "unresolved_reference"
            if command.reference is None
            else "verified_unclassified"
            if business or command.purpose.startswith("collector_")
            else command.purpose,
            "reason": command.reason,
        },
    )
    link = {"status": "not_applicable"}
    if command.purpose.startswith("collector_"):
        from .collector_surplus import link_debit

        try:
            with conn.transaction():
                link = link_debit(service, conn, actor, account, event, command)
        except TreasuryConflict as error:
            link = {
                "status": "blocked",
                "blocker": str(error),
                "source_id": str(command.source_id),
                "source_version": command.source_version,
                "observed_event_id": str(event["id"]),
                "action_record": collector_action,
            }
    if business:
        # A failed source-link savepoint must not erase a real independently verified
        # debit. It remains a visible exception, never a paid business record.
        try:
            with conn.transaction():
                if command.purpose in {"payroll", "salary_advance"}:
                    link = link_employee_source(
                        service, conn, actor, account, event, command
                    )
                elif command.purpose == "refund" and command.receipt_id:
                    receipt = conn.execute(
                        "select * from treasury.receipts where id=%s and account_id=%s for update",
                        (command.receipt_id, account["id"]),
                    ).fetchone()
                    if receipt is None or receipt["amount"] - receipt[
                        "applied_amount"
                    ] - receipt["refunded_amount"] < Decimal(command.amount):
                        raise TreasuryConflict(
                            "Protected application reversal or current unapplied refund capacity is required."
                        )
                    existing = conn.execute(
                        "select 1 from treasury.source_links where event_id=%s and source_kind='receipt_refund'",
                        (event["id"],),
                    ).fetchone()
                    if not existing:
                        conn.execute(
                            "update treasury.receipts set refunded_amount=refunded_amount+%s,version=version+1 where id=%s",
                            (Decimal(command.amount), receipt["id"]),
                        )
                        conn.execute(
                            """insert into treasury.source_links(id,event_id,ledger_context_id,source_kind,source_id,source_version,linked_amount)
                            values(%s,%s,%s,'receipt_refund',%s,%s,%s)""",
                            (
                                identity(event["id"], "refund-link"),
                                event["id"],
                                account["ledger_context_id"],
                                receipt["id"],
                                receipt["version"],
                                Decimal(command.amount),
                            ),
                        )
                    link = {
                        "status": "actual_refund_recorded",
                        "receipt_id": str(receipt["id"]),
                        "blocker": "This actual provider debit does not certify an existing cash-only borrower refund acknowledgment.",
                    }
                else:
                    raise TreasuryConflict(
                        "The existing source has no safe wallet-execution contract; use its protected workflow. Actual debit remains an unclassified exception."
                    )
        except (TreasuryConflict, TreasuryDenied, ValueError) as error:
            link = {"status": "blocked", "blocker": str(error)}
        except Exception as error:
            # Existing employee source guards are domain exceptions, not a successful
            # source completion. Database/programming errors still roll back everything.
            from .employee_authorization import EmployeeAccessDenied
            from .employee_operations import EmployeeConflict

            if not isinstance(error, (EmployeeConflict, EmployeeAccessDenied)):
                raise
            link = {"status": "blocked", "blocker": str(error)}
    event_result = json_value(event)
    event_result.update(
        status="verified_unresolved_reference"
        if command.reference is None
        else "verified_credit"
        if command.direction == "credit"
        else "debited_destination_unconfirmed"
        if not command.destination_confirmed or link.get("status") == "blocked"
        else "verified_debit",
        requested_purpose=command.purpose,
        source_link=link,
    )
    return (
        event["id"],
        event["version"],
        {"event": event_result, "source_link": link, "new_movement": new},
        "saved",
    )


def transfer(service, conn, actor, account, command):
    other = require_account(
        conn, actor, command.other_account_id, "treasury.transfer.record"
    )
    if (
        other["version"] != command.other_account_version
        or other["ledger_context_id"] != account["ledger_context_id"]
    ):
        raise TreasuryConflict(
            "Transfer accounts changed or belong to different contexts."
        )
    if (
        account["id"] == other["id"]
        or command.leg == "destination"
        and command.fee != "0.00"
    ):
        raise TreasuryConflict(
            "Transfer legs require distinct tracked accounts and separately evidenced source-side fees."
        )
    source = account if command.leg == "source" else other
    destination = other if command.leg == "source" else account
    existing = conn.execute(
        "select * from treasury.transfers where id=%s for update",
        (command.transfer_id,),
    ).fetchone()
    if existing and (
        existing["source_account_id"] != source["id"]
        or existing["destination_account_id"] != destination["id"]
        or existing["amount"] != Decimal(command.amount)
        or existing["ledger_context_id"] != account["ledger_context_id"]
    ):
        raise TreasuryConflict(
            "The correlated transfer has different retained account/amount evidence."
        )
    event, new = service.record_verified_event(
        conn,
        actor,
        account,
        {
            "id": identity(command.request_id, "transfer-event"),
            "provider": command.provider,
            "reference": command.reference,
            "direction": "debit" if command.leg == "source" else "credit",
            "amount": Decimal(command.amount),
            "fee": Decimal(command.fee),
            "effective_at": command.effective_at,
            "evidence_id": command.evidence_id,
            "recipient_attestation": command.recipient_attestation,
            "classification": "account_transfer",
            "reason": command.reason,
        },
    )
    if not existing:
        conn.execute(
            """insert into treasury.transfers(id,ledger_context_id,source_account_id,destination_account_id,amount)
            values(%s,%s,%s,%s,%s)""",
            (
                command.transfer_id,
                account["ledger_context_id"],
                source["id"],
                destination["id"],
                Decimal(command.amount),
            ),
        )
    column = "source_event_id" if command.leg == "source" else "destination_event_id"
    old = existing[column] if existing else None
    if old and old != event["id"]:
        raise TreasuryConflict(
            "This transfer side already has a different actual event."
        )
    row = conn.execute(
        sql.SQL(
            "update treasury.transfers set {}=%s,version=version+1 where id=%s returning *"
        ).format(sql.Identifier(column)),
        (event["id"], command.transfer_id),
    ).fetchone()
    row["status"] = (
        "completed"
        if row["source_event_id"] and row["destination_event_id"]
        else "in_transit"
        if row["source_event_id"]
        else "destination_received_source_unconfirmed"
    )
    row["transit_amount"] = (
        row["amount"]
        if row["source_event_id"] and not row["destination_event_id"]
        else Decimal("0.00")
    )
    return (
        row["id"],
        row["version"],
        {"transfer": json_value(row), "event": json_value(event), "new_movement": new},
        "saved",
    )
