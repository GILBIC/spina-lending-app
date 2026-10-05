"""A later real application consumes the remaining funds and prior EIR proof."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from gilbic_backend.treasury_claims import claim_action
from gilbic_backend.treasury_models import AllocationPreview, ReceiptApply
from gilbic_backend.treasury_repository import TreasuryService
from test_treasury_application_accounting_postgres import (
    application_db as _application_db,
)
from treasury_application_accounting_test_support import (
    application_coordinates,
    application_post,
    application_prepare,
    create_application_source,
)

from gilbic_backend import treasury_collection_posting as allocation

application_db = _application_db


def next_application(f, monkeypatch):
    conn = f["conn"]
    day = f["day"] + timedelta(days=1)
    actor = replace(f["actor"], permissions=("treasury.payment.apply",))
    monkeypatch.setattr(allocation.combined, "_current_business_date", lambda: day)
    receipt = conn.execute(
        "SELECT * FROM treasury.receipts WHERE id=%s", (f["receipt"],)
    ).fetchone()
    state = conn.execute(
        "SELECT state_version FROM lending.loan_collection_state WHERE loan_id=%s",
        (f["loan"],),
    ).fetchone()
    inputs = {
        "mode": "single",
        "total_amount": "50.00",
        "loans": [{"loan_id": f["loan"], "expected_version": state["state_version"]}],
        "effective_date": day,
        "expected_version": receipt["version"],
    }
    preview = allocation.preview_allocation(
        conn, actor, receipt, AllocationPreview(**inputs)
    )
    assert preview["can_apply"], preview
    command = ReceiptApply(
        **inputs,
        action="receipt_apply",
        request_id=uuid4(),
        account_id=f["wallet"],
        receipt_id=f["receipt"],
        digest=preview["digest"],
    )
    account = conn.execute(
        "SELECT * FROM treasury.accounts WHERE id=%s", (f["wallet"],)
    ).fetchone()
    _, _, payload, _ = claim_action(TreasuryService(), conn, actor, account, command)
    return f | {
        "application": UUID(payload["application_id"]),
        "transaction": UUID(payload["application"]["transaction_ids"][0]),
        "day": day,
    }


def test_two_operational_applications_consume_one_cash_receipt_and_prior_posted_eir(
    application_db, monkeypatch
):
    first = create_application_source(application_db, monkeypatch)
    first_prep = application_prepare(first)
    first_journal = application_post(first, first_prep)
    second = next_application(first, monkeypatch)
    assert application_post(first, first_prep) == first_journal
    source = application_coordinates(second)
    assert Decimal(source["liability_remaining"]) == Decimal("97.25")
    second_journal = application_post(second, application_prepare(second))
    assert second_journal != first_journal
    conn = first["conn"]
    assert (
        conn.execute(
            "SELECT count(*) AS n FROM accounting.treasury_receipt_postings WHERE receipt_id=%s",
            (first["receipt"],),
        ).fetchone()["n"]
        == 1
    )
    assert (
        conn.execute(
            "SELECT count(*) AS n FROM accounting.treasury_application_posting_status WHERE receipt_id=%s AND exact_posted AND NOT correction_pending",
            (first["receipt"],),
        ).fetchone()["n"]
        == 2
    )
    balances = {
        row["code"]: row["amount"]
        for row in conn.execute(
            "SELECT a.code,sum(l.debit-l.credit) AS amount FROM accounting.journal_lines l JOIN accounting.accounts a ON a.id=l.account_id JOIN accounting.journal_entries j ON j.id=l.journal_entry_id WHERE j.status='posted' AND l.client_id=%s GROUP BY a.code",
            (first["client"],),
        ).fetchall()
    }
    assert balances["1030"] == Decimal("147.25")
    assert balances["2200"] == Decimal("-47.25")
    assert balances["1110"] == Decimal(
        str(source["measurement"]["closing_7x7_loan_component"])
    )
    assert balances["1120"] == Decimal(
        str(source["measurement"]["closing_accrued_eir_interest"])
    )
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
