"""Mixed physical-cash/recipient-wallet invariants on an isolated test database."""

from datetime import UTC, datetime
from uuid import uuid4

import psycopg
import pytest
from test_remittance_review_rejection_postgres import DATABASE_URL, _seed_collection

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="Disposable PostgreSQL required"
)


@pytest.fixture
def funded():
    info = psycopg.conninfo.conninfo_to_dict(DATABASE_URL)
    assert info.get("host") in {"127.0.0.1", "localhost", "::1"}
    assert (
        info.get("dbname", "").startswith("spina_treasury_validation_")
        or info.get("dbname") == "spina_treasury_test_20261002"
    )
    collector, recipient, cash = _seed_collection(
        suffix=uuid4().hex[:8], collection_date=datetime.now(UTC).date()
    )
    with psycopg.connect(DATABASE_URL) as conn:
        client, device = conn.execute(
            "select client_id,registered_device_id from lending.collection_transactions where id=%s",
            (cash,),
        ).fetchone()
        context, account, evidence, event, receipt = [uuid4() for _ in range(5)]
        conn.execute(
            "insert into treasury.contexts(id,kind,created_by) values(%s,'synthetic',%s)",
            (context, recipient),
        )
        conn.execute(
            "insert into treasury.accounts(id,ledger_context_id,kind,alias,ownership,custodian_user_id) values(%s,%s,'gcash','Synthetic funding','synthetic',%s)",
            (account, context, recipient),
        )
        conn.execute(
            "insert into treasury.evidence(id,account_id,uploaded_by,device_id,purpose,media_type,byte_count,sha256) values(%s,%s,%s,%s,'recipient','image/png',1,%s)",
            (evidence, account, collector, device, "a" * 64),
        )
        conn.execute(
            "insert into treasury.events(id,account_id,ledger_context_id,provider,reference,direction,amount,effective_at,recorded_by_user_id,verified_by_user_id,device_id,evidence_id,recipient_attestation,classification,reason) values(%s,%s,%s,'synthetic',%s,'credit',100,now(),%s,%s,%s,%s,'synthetic receipt','loan_payment','synthetic test')",
            (
                event,
                account,
                context,
                str(uuid4()),
                recipient,
                recipient,
                device,
                evidence,
            ),
        )
        conn.execute(
            "insert into treasury.receipts(id,event_id,account_id,ledger_context_id,client_id,amount,effective_at) values(%s,%s,%s,%s,%s,100,now())",
            (receipt, event, account, context, client),
        )
        conn.commit()
        yield conn, collector, recipient, cash, receipt, account, event
        conn.rollback()


def _copy(conn, cash, receipt, amount="100.00"):
    conn.execute(
        "select set_config('spina.treasury_receipt_id',%s,true)", (str(receipt),)
    )
    return conn.execute(
        """insert into lending.collection_transactions(
        idempotency_key,loan_id,client_id,collector_user_id,registered_device_id,
        route_entry_id,collection_date,entry_type,amount,recorded_at,device_sequence,
        note,previous_balance,official_balance,pass_count_after,receipt_number,details)
        select %s,loan_id,client_id,collector_user_id,registered_device_id,route_entry_id,
          collection_date,'payment',%s,now(),2,'Synthetic wallet payment',900,800,0,%s,'{}'::jsonb
        from lending.collection_transactions where id=%s returning id""",
        (uuid4(), amount, "SYN-" + uuid4().hex, cash),
    ).fetchone()[0]


def test_recorder_does_not_determine_cash_custody(funded):
    conn, collector, _, cash, receipt, account, _ = funded
    payment = _copy(conn, cash, receipt)
    rows = conn.execute(
        "select id,funding_source,funding_receipt_id,funding_account_id,collector_user_id from lending.collection_transactions where id=any(%s)",
        ([cash, payment],),
    ).fetchall()
    by_id = {r[0]: r[1:] for r in rows}
    assert by_id[cash] == ("collector_cash", None, None, collector)
    assert by_id[payment] == ("treasury_receipt", receipt, account, collector)


def test_existing_remittance_and_refund_readers_count_only_physical_cash(funded):
    from gilbic_backend.refund_due_repository import _collector_cash_held
    from gilbic_backend.remittance_repository import PostgresRemittanceRepository
    from psycopg.rows import dict_row

    conn, collector, _, cash, receipt, _, _ = funded
    payment = _copy(conn, cash, receipt)
    with conn.cursor(row_factory=dict_row) as cursor:
        items = PostgresRemittanceRepository._eligible_items(
            cursor,
            collector_user_id=collector,
            collection_date=datetime.now(UTC).date(),
            for_update=False,
        )
        assert [item.transaction_id for item in items] == [cash]
        assert all(item.transaction_id != payment for item in items)
        assert _collector_cash_held(cursor, collector_user_id=collector) == 100


def test_second_application_cannot_exceed_receipt(funded):
    conn, _, _, cash, receipt, _, _ = funded
    _copy(conn, cash, receipt)
    with pytest.raises(psycopg.Error, match="remaining funds"):
        _copy(conn, cash, receipt, "0.01")


def test_wallet_receipt_cannot_be_locked_into_remittance(funded):
    conn, _, _, cash, receipt, _, _ = funded
    payment = _copy(conn, cash, receipt)
    with pytest.raises(psycopg.Error, match="cash custody"):
        conn.execute(
            "update lending.collection_transactions set is_locked=true where id=%s",
            (payment,),
        )


def test_wallet_history_cannot_be_relabeled_as_physical_cash(funded):
    conn, _, _, cash, receipt, _, _ = funded
    payment = _copy(conn, cash, receipt)
    with pytest.raises(psycopg.Error, match="immutable"):
        conn.execute(
            "update lending.collection_transactions set funding_source='collector_cash',funding_receipt_id=null,funding_account_id=null where id=%s",
            (payment,),
        )


def test_corrected_receipt_is_not_new_spendable_money(funded):
    conn, _, recipient, cash, receipt, _, event = funded
    conn.execute(
        "insert into treasury.event_revisions(id,event_id,version,action,reason,actor_id) values(%s,%s,2,'correct','Synthetic correction',%s)",
        (uuid4(), event, recipient),
    )
    with pytest.raises(psycopg.Error, match="corrected"):
        _copy(conn, cash, receipt)


def test_rollback_removes_application_without_changing_actual_receipt(funded):
    conn, _, _, cash, receipt, _, _ = funded
    payment = _copy(conn, cash, receipt)
    conn.rollback()
    assert (
        conn.execute(
            "select count(*) from lending.collection_transactions where id=%s",
            (payment,),
        ).fetchone()[0]
        == 0
    )
    assert conn.execute(
        "select amount,applied_amount from treasury.receipts where id=%s", (receipt,)
    ).fetchone() == (100, 0)


def test_recipient_payment_notification_does_not_claim_collector_cash(funded):
    conn, _, recipient, cash, receipt, _, _ = funded
    conn.execute(
        "update lending.clients set user_id=%s where id=(select client_id from lending.collection_transactions where id=%s)",
        (recipient, cash),
    )
    payment = _copy(conn, cash, receipt)
    notices = conn.execute(
        "select title,message,metadata from core.activity_notifications where transaction_id=%s and recipient_user_id=%s",
        (payment, recipient),
    ).fetchall()
    assert len(notices) == 1
    title, message, metadata = notices[0]
    assert title == "Verified recipient funds applied"
    assert "not a Collector cash handover" in message
    assert metadata["funding_source"] == "treasury_receipt"
    assert "wallet_balance" not in metadata
    assert "account_id" not in metadata
