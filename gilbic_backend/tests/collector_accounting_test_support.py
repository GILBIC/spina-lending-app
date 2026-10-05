"""Actual operational Collector sources and existing protected collection proof."""

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore
from gilbic_backend.treasury_models import COMMAND_ADAPTER, SettlementPreview
from gilbic_backend.treasury_repository import TreasuryService
from psycopg.rows import tuple_row
from test_legacy_source_completeness_postgres import _post_regular
from test_regular_journal_posting_postgres import _create_collection
from treasury_test_support import actor, grant_live

from gilbic_backend import (
    collector_settlement,
    collector_surplus,
    treasury_disbursements,
)

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
MIGRATION = SQL_ROOT / "0152_add_collector_liability_accounting.sql"
FILE = b"%PDF-1.4\nSynthetic Collector accounting evidence\n%%EOF"
MANILA = timezone(timedelta(hours=8))


def source_case(conn, tmp_path, monkeypatch, *, historical_days=0):
    manager, collector = actor(conn), actor(conn, "collector")
    permissions = (
        "treasury.view",
        "treasury.account.manage",
        "treasury.disbursement.record",
        "treasury.collector_surplus.view",
        "treasury.collector_surplus.receive",
        "treasury.collector_surplus.resolve",
        "treasury.collector_surplus.settle",
        "remittance.receive",
    )
    grant_live(conn, manager.user_id, *permissions)
    monkeypatch.setenv("SPINA_COLLECTOR_SURPLUS_ENABLED", "true")
    monkeypatch.setenv("SPINA_EMPLOYEE_OWNER_USER_ID", str(manager.user_id))
    now = datetime.now(MANILA) - timedelta(days=historical_days, seconds=2)
    day = now.date()
    book = conn.execute(
        "SELECT accounting.configure_book_identity('synthetic','Synthetic Collector accounting book','test:collector-book',%s,%s) AS id",
        ("a" * 64, manager.user_id),
    ).fetchone()["id"]
    period_row = conn.execute(
        "SELECT id,status FROM accounting.fiscal_periods WHERE %s BETWEEN start_date AND end_date",
        (day,),
    ).fetchone()
    if period_row:
        assert period_row["status"] == "open"
        period = period_row["id"]
    else:
        period = conn.execute(
            "SELECT accounting.create_fiscal_period('Synthetic Collector accounting day',%s,%s,%s) AS id",
            (day, datetime.now(MANILA).date(), manager.user_id),
        ).fetchone()["id"]
    context, wallet, evidence, remittance = (uuid4() for _ in range(4))
    conn.execute(
        "INSERT INTO treasury.contexts(id,kind,created_by) VALUES(%s,'synthetic',%s)",
        (context, manager.user_id),
    )
    conn.execute(
        "INSERT INTO treasury.accounts(id,ledger_context_id,kind,alias,ownership,custodian_user_id) VALUES(%s,%s,'physical_cash','Synthetic count receiving cash','synthetic',%s)",
        (wallet, context, manager.user_id),
    )
    conn.execute(
        "INSERT INTO treasury.account_access(account_id,user_id,permissions,private_history,granted_by) VALUES(%s,%s,%s,true,%s)",
        (wallet, manager.user_id, list(permissions), manager.user_id),
    )
    store = PrivateEvidenceStore(tmp_path / "private")
    store.put(evidence, FILE, "application/pdf")
    conn.execute(
        "INSERT INTO treasury.evidence(id,account_id,uploaded_by,device_id,purpose,media_type,byte_count,sha256) VALUES(%s,%s,%s,%s,'recipient','application/pdf',%s,%s)",
        (
            evidence,
            wallet,
            manager.user_id,
            manager.registered_device_id,
            len(FILE),
            hashlib.sha256(FILE).hexdigest(),
        ),
    )
    loan_type = conn.execute(
        "INSERT INTO lending.loan_types(code,name,term_days,calculation_mode) VALUES(%s,'Synthetic Regular',120,'fixed_daily') RETURNING id",
        (uuid4().hex,),
    ).fetchone()["id"]
    client = conn.execute(
        "INSERT INTO lending.clients(client_code,full_name) VALUES(%s,'Synthetic Collector source borrower') RETURNING id",
        (uuid4().hex,),
    ).fetchone()["id"]
    loan = conn.execute(
        "INSERT INTO lending.loans(loan_number,client_id,loan_type_id,principal,daily_amount,date_released,due_date,status) VALUES(%s,%s,%s,1000,10,%s,%s,'active') RETURNING id",
        (
            uuid4().hex,
            client,
            loan_type,
            day - timedelta(days=1),
            day + timedelta(days=119),
        ),
    ).fetchone()["id"]
    suffix = uuid4().hex
    with conn.cursor(row_factory=tuple_row) as cursor:
        transaction = _create_collection(
            cursor,
            suffix=suffix,
            loan_id=loan,
            client_id=client,
            actor_id=collector.user_id,
            device_id=collector.registered_device_id,
            sequence=1,
            collection_date=day,
        )
        _post_regular(
            {
                "conn": cursor,
                "actor": manager.user_id,
                "client": client,
                "loan": loan,
                "period": period,
                "start": day,
            },
            transaction,
        )
    conn.execute(
        "INSERT INTO lending.collection_remittances(id,remittance_number,collector_user_id,recipient_user_id,collection_date,status,transaction_count,payment_count,unable_to_pay_count,covered_payment_count,client_count,total_amount,note,submitted_at) VALUES(%s,%s,%s,%s,%s,'submitted',1,1,0,0,1,100,'Synthetic retained handover',%s)",
        (remittance, remittance.hex, collector.user_id, manager.user_id, day, now),
    )
    conn.execute(
        "INSERT INTO lending.collection_remittance_items(remittance_id,transaction_id,client_id,loan_id,collection_date,entry_type,amount,receipt_number,transaction_snapshot) SELECT %s,id,client_id,loan_id,collection_date,entry_type,amount,receipt_number,to_jsonb(t) FROM lending.collection_transactions t WHERE id=%s",
        (remittance, transaction),
    )
    conn.execute(
        "UPDATE lending.collection_transactions SET remittance_id=%s,is_locked=true,locked_at=%s,locked_by_user_id=%s WHERE id=%s",
        (remittance, now, collector.user_id, transaction),
    )
    mapping = conn.execute(
        "SELECT accounting.configure_treasury_cash_mapping(%s,'1010',0,%s,'test:collector-cash-map',%s,%s) AS id",
        (wallet, uuid4(), "b" * 64, manager.user_id),
    ).fetchone()["id"]
    return {
        "conn": conn,
        "actor": manager,
        "collector": collector,
        "book": book,
        "period": period,
        "day": day,
        "now": now,
        "wallet": wallet,
        "context": context,
        "evidence": evidence,
        "remittance": remittance,
        "transaction": transaction,
        "mapping": mapping,
        "store": store,
        "service": TreasuryService(store=store),
    }


def command(f, tag, *, who=None, **values):
    account = (
        f["conn"]
        .execute("SELECT * FROM treasury.accounts WHERE id=%s", (f["wallet"],))
        .fetchone()
    )
    own = tag.endswith(("request", "acknowledge"))
    payload = dict(action=tag, request_id=uuid4(), **values)
    if not own:
        payload.update(account_id=f["wallet"], expected_version=account["version"])
    model = COMMAND_ADAPTER.validate_python(payload)
    handler = (
        treasury_disbursements.outgoing_action
        if tag == "disbursement_record"
        else collector_surplus.action
    )
    return handler(f["service"], f["conn"], who or f["actor"], account, model)[2]


def accepted(f, amount="110.00"):
    account = (
        f["conn"]
        .execute("SELECT * FROM treasury.accounts WHERE id=%s", (f["wallet"],))
        .fetchone()
    )
    preview = collector_settlement.preview(
        f["service"],
        f["conn"],
        f["actor"],
        f["remittance"],
        SettlementPreview(account_id=f["wallet"], expected_version=account["version"]),
    )
    count = command(
        f,
        "collector_count_record",
        remittance_id=f["remittance"],
        source_digest=preview["source_digest"],
        counted_amount=amount,
        counted_at=f["now"],
        evidence_id=f["evidence"],
        recipient_attestation="Synthetic actual cash counted",
        review_acknowledged=True,
    )["count"]
    return command(
        f,
        "collector_count_accept",
        count_id=count["id"],
        count_version=count["version"],
        source_digest=count["source_digest"],
        physical_receipt_acknowledged=True,
    )


def add_zero_pass(f):
    """Append a real no-cash source row before the immutable count snapshot."""
    source = (
        f["conn"]
        .execute(
            """INSERT INTO lending.collection_transactions
        (idempotency_key,loan_id,client_id,collector_user_id,registered_device_id,route_entry_id,
         collection_date,entry_type,amount,recorded_at,device_sequence,note,previous_balance,
         official_balance,pass_count_after,receipt_number,details)
        SELECT %s,loan_id,client_id,collector_user_id,registered_device_id,route_entry_id,
         collection_date,'pass',0,recorded_at,2,'Synthetic no-cash constituent',official_balance,
         official_balance,1,%s,'{}'::jsonb FROM lending.collection_transactions WHERE id=%s RETURNING id""",
            (uuid4(), uuid4().hex, f["transaction"]),
        )
        .fetchone()["id"]
    )
    f["conn"].execute(
        "INSERT INTO lending.collection_remittance_items(remittance_id,transaction_id,client_id,loan_id,collection_date,entry_type,amount,receipt_number,transaction_snapshot) SELECT %s,id,client_id,loan_id,collection_date,entry_type,amount,receipt_number,to_jsonb(t) FROM lending.collection_transactions t WHERE id=%s",
        (f["remittance"], source),
    )
    f["conn"].execute(
        "UPDATE lending.collection_remittances SET transaction_count=2,unable_to_pay_count=1 WHERE id=%s",
        (f["remittance"],),
    )
    f["conn"].execute(
        "UPDATE lending.collection_transactions SET remittance_id=%s,is_locked=true,locked_at=%s,locked_by_user_id=%s WHERE id=%s",
        (f["remittance"], f["now"], f["actor"].user_id, source),
    )
    return source


def recognized(f, acceptance):
    case = acceptance["case"]
    credit = command(
        f,
        "collector_surplus_recognize",
        case_id=case["id"],
        case_version=case["version"],
        source_digest=case["source_digest"],
        source_review_acknowledged=True,
        amount="10.00",
        evidence_id=f["evidence"],
        reason="Synthetic independent review identifies actual Collector excess",
    )["credit"]
    entry = (
        f["conn"]
        .execute(
            "SELECT id FROM treasury.collector_entries WHERE credit_id=%s AND payload->>'kind'='recognition'",
            (UUID(credit["id"]),),
        )
        .fetchone()["id"]
    )
    return credit, entry


def reserved(f, credit, amount="4.00", *, request_source=None):
    request = command(
        request_source or f,
        "collector_surplus_return_request",
        who=f["collector"],
        credit_id=credit["id"],
        credit_version=credit["version"],
        amount=amount,
        destination={"kind": "physical_cash", "recipient_reference": None},
        reason="Return my actual retained excess",
    )["request"]
    return command(
        f,
        "collector_surplus_return_prepare",
        credit_id=credit["id"],
        credit_version=credit["version"],
        collector_request_id=request["id"],
        collector_request_version=request["version"],
        amount=amount,
        destination=request["destination"],
        evidence_id=f["evidence"],
        reason="Independent review of exact Collector request",
    )


def other_paying_wallet(f):
    wallet, evidence = uuid4(), uuid4()
    f["conn"].execute(
        "INSERT INTO treasury.accounts(id,ledger_context_id,kind,alias,ownership,custodian_user_id) SELECT %s,ledger_context_id,kind,'Synthetic separate paying cash',ownership,custodian_user_id FROM treasury.accounts WHERE id=%s",
        (wallet, f["wallet"]),
    )
    f["conn"].execute(
        "INSERT INTO treasury.account_access(account_id,user_id,permissions,private_history,granted_by) SELECT %s,user_id,permissions,private_history,granted_by FROM treasury.account_access WHERE account_id=%s AND user_id=%s",
        (wallet, f["wallet"], f["actor"].user_id),
    )
    f["store"].put(evidence, FILE, "application/pdf")
    f["conn"].execute(
        "INSERT INTO treasury.evidence(id,account_id,uploaded_by,device_id,purpose,media_type,byte_count,sha256) SELECT %s,%s,uploaded_by,device_id,purpose,media_type,byte_count,sha256 FROM treasury.evidence WHERE id=%s",
        (evidence, wallet, f["evidence"]),
    )
    mapping = (
        f["conn"]
        .execute(
            "SELECT accounting.configure_treasury_cash_mapping(%s,'1010',0,%s,'test:separate-collector-paying-cash',%s,%s) AS id",
            (wallet, uuid4(), "c" * 64, f["actor"].user_id),
        )
        .fetchone()["id"]
    )
    return f | {"wallet": wallet, "evidence": evidence, "mapping": mapping}


def debited(f, reservation, fee="1.00"):
    action = reservation["action_record"]
    return command(
        f,
        "disbursement_record",
        purpose="collector_surplus_return",
        source_id=action["id"],
        source_version=action["version"],
        payee_id=f["collector"].user_id,
        amount=action["amount"],
        fee=fee,
        provider="physical_cash",
        reference=uuid4().hex,
        effective_at=f["now"],
        evidence_id=f["evidence"],
        recipient_attestation="Actual separately evidenced return cash and fee",
        reason="Synthetic observed actual return",
    )


def confirmed(f, reservation, debit):
    action = debit["source_link"]["action_record"]
    credit = reservation["credit"]
    ack = command(
        f,
        "collector_surplus_return_acknowledge",
        who=f["collector"],
        credit_id=credit["id"],
        credit_version=credit["version"],
        action_id=action["id"],
        action_version=action["version"],
        event_id=action["event_id"],
        event_version=action["event_version"],
        reviewed_amount=action["amount"],
        confirmation="received",
        acknowledged_at=f["now"],
        reason="I independently received the exact actual return",
    )["acknowledgment"]
    result = command(
        f,
        "collector_surplus_return_record",
        action_id=action["id"],
        action_version=action["version"],
        event_id=action["event_id"],
        event_version=action["event_version"],
        acknowledgment_id=ack["id"],
        acknowledgment_version=ack["version"],
        reason="Current independent receipt confirmed",
    )
    entry = (
        f["conn"]
        .execute(
            "SELECT id FROM treasury.collector_entries WHERE payload->>'action_id'=%s AND payload->>'kind'='return'",
            (action["id"],),
        )
        .fetchone()["id"]
    )
    return result, entry


def reversed_return(f, confirmation, amount="1.00"):
    action = confirmation["action_record"]
    result = command(
        f,
        "collector_surplus_return_reverse",
        action_id=action["id"],
        action_version=action["version"],
        amount=amount,
        provider="physical_cash",
        reference=uuid4().hex,
        effective_at=f["now"],
        evidence_id=f["evidence"],
        recipient_attestation="Actual incoming returned principal received",
        reason="Synthetic verified incoming reversal",
    )
    event = result["incoming_event"]
    entry = (
        f["conn"]
        .execute(
            "SELECT id FROM treasury.collector_entries WHERE payload->>'incoming_event_id'=%s",
            (event["id"],),
        )
        .fetchone()["id"]
    )
    return result, entry


def review(f, kind, source_id):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.collector_liability_coordinates(%s,%s) AS source",
            (kind, source_id),
        )
        .fetchone()["source"]
    )


def prepare(f, kind, source_id, *, request=None):
    source = review(f, kind, source_id)
    identifier = (
        f["conn"]
        .execute(
            "SELECT accounting.prepare_collector_liability(%s,%s,%s,%s,%s) AS id",
            (
                kind,
                source_id,
                source["source_digest"],
                request or uuid4(),
                f["actor"].user_id,
            ),
        )
        .fetchone()["id"]
    )
    return (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.collector_liability_preparations WHERE id=%s",
            (identifier,),
        )
        .fetchone()
    )


def post(f, prepared):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.post_collector_liability(%s,%s,%s,%s) AS id",
            (
                prepared["id"],
                prepared["source_digest"],
                prepared["confirmation_token"],
                f["actor"].user_id,
            ),
        )
        .fetchone()["id"]
    )


def balances(f):
    return {
        row["code"]: row["amount"]
        for row in f["conn"]
        .execute(
            "SELECT a.code,sum(l.debit-l.credit) AS amount FROM accounting.journal_lines l JOIN accounting.journal_entries j ON j.id=l.journal_entry_id JOIN accounting.accounts a ON a.id=l.account_id WHERE j.status='posted' AND j.fiscal_period_id=%s GROUP BY a.code",
            (f["period"],),
        )
        .fetchall()
    }
