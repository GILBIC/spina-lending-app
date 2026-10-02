"""Recipient funding must reuse the actual protected loan posting transaction."""

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from gilbic_backend.treasury_models import AllocationPreview, ReceiptApply
from psycopg.rows import dict_row
from test_combined_collection_renewal_workflow_postgres import (
    DATABASE_URL,
    _setup_combined_case,
)

from gilbic_backend import treasury_collection_posting as adapter

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="Disposable PostgreSQL required"
)


@pytest.fixture
def receipt_case(monkeypatch):
    info = psycopg.conninfo.conninfo_to_dict(DATABASE_URL)
    assert info.get("host") in {"127.0.0.1", "localhost", "::1"} and (
        info.get("dbname", "").startswith("spina_treasury_validation_")
        or info.get("dbname") == "spina_treasury_test_20261002"
    )
    case = _setup_combined_case(
        verified_regular_schedule=True, verified_seven_schedule=True
    )
    monkeypatch.setattr(
        adapter.combined, "_current_business_date", lambda: date(2097, 8, 2)
    )
    actor = SimpleNamespace(
        user_id=case.collector_id,
        registered_device_id=case.device_id,
        permissions=("treasury.payment.apply",),
    )
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        context, account, evidence, event, receipt_id = [uuid4() for _ in range(5)]
        conn.execute(
            "insert into treasury.contexts(id,kind,created_by) values(%s,'synthetic',%s)",
            (context, actor.user_id),
        )
        conn.execute(
            "insert into treasury.accounts(id,ledger_context_id,kind,alias,ownership,custodian_user_id) values(%s,%s,'gcash','Synthetic adapter','synthetic',%s)",
            (account, context, actor.user_id),
        )
        conn.execute(
            "insert into treasury.evidence(id,account_id,uploaded_by,device_id,purpose,media_type,byte_count,sha256) values(%s,%s,%s,%s,'recipient','image/png',1,%s)",
            (evidence, account, actor.user_id, actor.registered_device_id, "a" * 64),
        )
        conn.execute(
            "insert into treasury.events(id,account_id,ledger_context_id,provider,reference,direction,amount,effective_at,recorded_by_user_id,verified_by_user_id,device_id,evidence_id,recipient_attestation,classification,reason) values(%s,%s,%s,'synthetic',%s,'credit',2000,%s,%s,%s,%s,%s,'synthetic receipt','borrower_receipt','synthetic')",
            (
                event,
                account,
                context,
                str(uuid4()),
                datetime(2097, 8, 2, tzinfo=UTC),
                actor.user_id,
                actor.user_id,
                actor.registered_device_id,
                evidence,
            ),
        )
        receipt = conn.execute(
            "insert into treasury.receipts(id,event_id,account_id,ledger_context_id,client_id,amount,effective_at) values(%s,%s,%s,%s,%s,2000,%s) returning *",
            (
                receipt_id,
                event,
                account,
                context,
                case.client_id,
                datetime(2097, 8, 2, tzinfo=UTC),
            ),
        ).fetchone()
        conn.commit()
        yield conn, case, actor, receipt
        conn.rollback()


def _input(conn, case, **changes):
    rows = conn.execute(
        "select loan_id,state_version from lending.loan_collection_state where loan_id=any(%s) order by loan_id",
        ([case.regular_loan_id, case.seven_loan_id],),
    ).fetchall()
    result = {
        "mode": "combined",
        "total_amount": "100.00",
        "loans": [
            {"loan_id": r["loan_id"], "expected_version": r["state_version"]}
            for r in rows
        ],
        "effective_date": "2097-08-02",
        "expected_version": 1,
    }
    result.update(changes)
    return result


def test_combined_preview_uses_server_split_and_apply_keeps_actual_wallet_receipt(
    receipt_case,
):
    conn, case, actor, receipt = receipt_case
    inputs = _input(conn, case)
    preview = adapter.preview_allocation(
        conn, actor, receipt, AllocationPreview(**inputs)
    )
    assert preview["can_apply"], preview
    assert sum(Decimal(r["amount"]) for r in preview["allocations"]) == 100
    command = ReceiptApply(
        **inputs,
        action="receipt_apply",
        request_id=uuid4(),
        account_id=receipt["account_id"],
        receipt_id=receipt["id"],
        digest=preview["digest"],
    )
    result = adapter.apply_receipt(conn, actor, receipt, command)
    assert result["status"] == "recorded" and result["amount"] == "100.00"
    rows = conn.execute(
        "select amount,funding_source,funding_receipt_id,collector_user_id from lending.collection_transactions where id=any(%s)",
        ([__import__("uuid").UUID(value) for value in result["transaction_ids"]],),
    ).fetchall()
    assert len(rows) == 2 and all(
        r["funding_source"] == "treasury_receipt"
        and r["funding_receipt_id"] == receipt["id"]
        and r["collector_user_id"] == actor.user_id
        for r in rows
    )
    assert (
        conn.execute(
            "select count(*) n from treasury.events where id=%s", (receipt["event_id"],)
        ).fetchone()["n"]
        == 1
    )


def test_modified_review_digest_cannot_write_any_official_receipt(receipt_case):
    conn, case, actor, receipt = receipt_case
    command = ReceiptApply(
        **_input(conn, case),
        action="receipt_apply",
        request_id=uuid4(),
        account_id=receipt["account_id"],
        receipt_id=receipt["id"],
        digest="0" * 64,
    )
    with pytest.raises(Exception, match="review|Review|changed"):
        adapter.apply_receipt(conn, actor, receipt, command)
    assert (
        conn.execute(
            "select count(*) n from lending.collection_transactions where funding_receipt_id=%s",
            (receipt["id"],),
        ).fetchone()["n"]
        == 0
    )


@pytest.mark.parametrize(
    "kind,amount,intent",
    [
        ("regular", "50.00", "scheduled"),
        ("regular", "100.00", "extra_as_advance"),
        ("regular", "100.00", "extra_as_principal_reduction"),
        ("seven", "21.00", "scheduled"),
        ("seven", "42.00", "extra_as_advance"),
        ("seven", "42.00", "extra_as_principal_reduction"),
    ],
)
def test_single_loan_uses_exact_protected_allocation(
    receipt_case, kind, amount, intent
):
    conn, case, actor, receipt = receipt_case
    loan_id = case.regular_loan_id if kind == "regular" else case.seven_loan_id
    inputs = _input(
        conn,
        case,
        mode="single",
        loans=[{"loan_id": loan_id, "expected_version": 0}],
        total_amount=amount,
        intent=intent,
    )
    preview = adapter.preview_allocation(
        conn, actor, receipt, AllocationPreview(**inputs)
    )
    assert preview["can_apply"], preview
    command = ReceiptApply(
        **inputs,
        action="receipt_apply",
        request_id=uuid4(),
        account_id=receipt["account_id"],
        receipt_id=receipt["id"],
        digest=preview["digest"],
    )
    result = adapter.apply_receipt(conn, actor, receipt, command)
    assert result["status"] == "recorded" and result["amount"] == amount
    assert conn.execute(
        "select sum(applied_amount) total from lending.collection_transactions where funding_receipt_id=%s and not is_voided",
        (receipt["id"],),
    ).fetchone()["total"] == Decimal(amount)


def test_failure_after_first_combined_component_rolls_back_every_receipt(
    receipt_case, monkeypatch
):
    conn, case, actor, receipt = receipt_case
    inputs = _input(conn, case)
    preview = adapter.preview_allocation(
        conn, actor, receipt, AllocationPreview(**inputs)
    )
    assert preview["can_apply"]
    command = ReceiptApply(
        **inputs,
        action="receipt_apply",
        request_id=uuid4(),
        account_id=receipt["account_id"],
        receipt_id=receipt["id"],
        digest=preview["digest"],
    )
    original = adapter.ConcurrentReceiptSafeCollectionPostingBridge.post_collection
    calls = []

    def fail_second(self, connection, posting_actor, posting):
        calls.append(posting.loan_id)
        if len(calls) == 2:
            raise RuntimeError("Synthetic downstream failure")
        return original(self, connection, posting_actor, posting)

    monkeypatch.setattr(
        adapter.ConcurrentReceiptSafeCollectionPostingBridge,
        "post_collection",
        fail_second,
    )
    with pytest.raises(RuntimeError, match="Synthetic downstream"), conn.transaction():
        adapter.apply_receipt(conn, actor, receipt, command)
    assert len(calls) == 2
    assert (
        conn.execute(
            "select count(*) n from lending.collection_transactions where funding_receipt_id=%s",
            (receipt["id"],),
        ).fetchone()["n"]
        == 0
    )


def test_stale_or_wrong_borrower_loan_is_blocked_before_official_post(receipt_case):
    conn, case, actor, receipt = receipt_case
    inputs = _input(conn, case)
    inputs["loans"][0]["expected_version"] = 999
    preview = adapter.preview_allocation(
        conn, actor, receipt, AllocationPreview(**inputs)
    )
    assert not preview["can_apply"] and "changed" in preview["blockers"][0]["message"]
    inputs["loans"][0]["loan_id"] = uuid4()
    preview = adapter.preview_allocation(
        conn, actor, receipt, AllocationPreview(**inputs)
    )
    assert not preview["can_apply"] and "borrower" in preview["blockers"][0]["message"]


def test_protected_application_reversal_does_not_refund_wallet_money(receipt_case):
    conn, case, actor, receipt = receipt_case
    inputs = _input(conn, case)
    preview = adapter.preview_allocation(
        conn, actor, receipt, AllocationPreview(**inputs)
    )
    command = ReceiptApply(
        **inputs,
        action="receipt_apply",
        request_id=uuid4(),
        account_id=receipt["account_id"],
        receipt_id=receipt["id"],
        digest=preview["digest"],
    )
    result = adapter.apply_receipt(conn, actor, receipt, command)
    application = {"id": uuid4(), "source_result": result}
    reversed_result = adapter.reverse_application(
        conn,
        actor,
        receipt,
        application,
        SimpleNamespace(request_id=uuid4(), reason="Synthetic allocation correction"),
    )
    assert reversed_result["status"] == "reversed"
    assert (
        conn.execute(
            "select count(*) n from lending.collection_transactions where funding_receipt_id=%s and not is_voided",
            (receipt["id"],),
        ).fetchone()["n"]
        == 0
    )
    assert conn.execute(
        "select amount,refunded_amount from treasury.receipts where id=%s",
        (receipt["id"],),
    ).fetchone() == {"amount": Decimal("2000.00"), "refunded_amount": Decimal("0.00")}
