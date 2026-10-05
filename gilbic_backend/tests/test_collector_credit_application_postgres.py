"""0157 behavioral verification using actual Collector actions and cash facts."""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from collector_accounting_test_support import (
    SQL_ROOT,
    accepted,
    balances,
    command,
    post,
    prepare,
)
from gilbic_backend.collector_settlement import preview, source_snapshot
from gilbic_backend.treasury_authorization import TreasuryConflict
from gilbic_backend.treasury_models import SettlementPreview
from psycopg.rows import tuple_row
from test_collector_liability_accounting_postgres import (
    collector_accounting as _collector_accounting,
)
from test_legacy_source_completeness_postgres import _post_regular
from test_regular_journal_posting_postgres import _create_collection
from test_treasury_receipt_accounting_postgres import install

collector_accounting = _collector_accounting
MIGRATION = SQL_ROOT / "0157_add_collector_credit_applications.sql"


@pytest.fixture
def credit_application(collector_accounting, request, monkeypatch):
    f = collector_accounting
    monkeypatch.setenv("SPINA_COLLECTOR_SURPLUS_APPLICATION_ENABLED", "true")
    if (
        MIGRATION.exists()
        and not f["conn"]
        .execute(
            "SELECT to_regprocedure('treasury.collector_credit_application_ready()') IS NOT NULL AS available"
        )
        .fetchone()["available"]
    ):
        install(f["conn"], MIGRATION)
    settings = getattr(request, "param", "10.00")
    credit_amount = Decimal(
        settings["amount"] if isinstance(settings, dict) else settings
    )
    received = accepted(f, format(Decimal("100.00") + credit_amount, ".2f"))
    post(f, prepare(f, "settlement", UUID(received["settlement"]["id"])))
    case = received["case"]
    credit = command(
        f,
        "collector_surplus_recognize",
        case_id=case["id"],
        case_version=case["version"],
        source_digest=case["source_digest"],
        source_review_acknowledged=True,
        amount=format(credit_amount, ".2f"),
        evidence_id=f["evidence"],
        reason="Synthetic independent recognition of the actual retained excess",
    )["credit"]
    entry = (
        f["conn"]
        .execute(
            "SELECT id FROM treasury.collector_entries WHERE credit_id=%s AND payload->>'kind'='recognition'",
            (UUID(credit["id"]),),
        )
        .fetchone()["id"]
    )
    if not isinstance(settings, dict) or settings.get("post_recognition", True):
        post(f, prepare(f, "recognition", entry))
    later = _later_protected_remittance(f)
    return {
        **f,
        "credit": credit,
        "later": later,
        "starting_cash": Decimal("100.00") + credit_amount,
    }


def _later_protected_remittance(f):
    """A new real collection on a separate loan; no altered old source or clock."""
    conn = f["conn"]
    client = conn.execute(
        "INSERT INTO lending.clients(client_code,full_name) VALUES(%s,'Synthetic later remittance borrower') RETURNING id",
        (uuid4().hex,),
    ).fetchone()["id"]
    loan = conn.execute(
        """INSERT INTO lending.loans(loan_number,client_id,loan_type_id,principal,daily_amount,date_released,due_date,status)
        SELECT %s,%s,l.loan_type_id,l.principal,l.daily_amount,l.date_released,l.due_date,'active'
        FROM lending.loans l JOIN lending.collection_transactions t ON t.loan_id=l.id WHERE t.id=%s RETURNING id""",
        (uuid4().hex, client, f["transaction"]),
    ).fetchone()["id"]
    with conn.cursor(row_factory=tuple_row) as cursor:
        transaction = _create_collection(
            cursor,
            suffix=uuid4().hex,
            loan_id=loan,
            client_id=client,
            actor_id=f["collector"].user_id,
            device_id=f["collector"].registered_device_id,
            sequence=2,
            collection_date=f["day"],
        )
        _post_regular(
            {
                "conn": cursor,
                "actor": f["actor"].user_id,
                "client": client,
                "loan": loan,
                "period": f["period"],
                "start": f["day"],
            },
            transaction,
        )
    remittance = uuid4()
    conn.execute(
        """INSERT INTO lending.collection_remittances(id,remittance_number,collector_user_id,
        recipient_user_id,collection_date,status,transaction_count,payment_count,unable_to_pay_count,
        covered_payment_count,client_count,total_amount,note,submitted_at)
        VALUES(%s,%s,%s,%s,%s,'submitted',1,1,0,0,1,100,'Synthetic later credit application',clock_timestamp())""",
        (
            remittance,
            remittance.hex,
            f["collector"].user_id,
            f["actor"].user_id,
            f["day"],
        ),
    )
    conn.execute(
        """INSERT INTO lending.collection_remittance_items(remittance_id,transaction_id,client_id,
        loan_id,collection_date,entry_type,amount,receipt_number,transaction_snapshot)
        SELECT %s,id,client_id,loan_id,collection_date,entry_type,amount,receipt_number,to_jsonb(t)
        FROM lending.collection_transactions t WHERE id=%s""",
        (remittance, transaction),
    )
    conn.execute(
        "UPDATE lending.collection_transactions SET remittance_id=%s,is_locked=true,locked_at=clock_timestamp(),locked_by_user_id=%s WHERE id=%s",
        (remittance, f["actor"].user_id, transaction),
    )
    return remittance


def _cash(f):
    return (
        f["conn"]
        .execute(
            "SELECT coalesce(sum(signed_amount),0) AS amount FROM treasury.movement_lines WHERE account_id=%s",
            (f["wallet"],),
        )
        .fetchone()["amount"]
    )


def _credit(f):
    return (
        f["conn"]
        .execute(
            "SELECT payload FROM treasury.collector_credits WHERE id=%s",
            (UUID(f["credit"]["id"]),),
        )
        .fetchone()["payload"]
    )


def _approve(f, amount="4.00", *, request_source=None):
    credit = f["credit"]
    _, _, digest, _, _ = source_snapshot(f["conn"], f["later"])
    request = command(
        request_source or f,
        "collector_surplus_application_request",
        who=f["collector"],
        credit_id=credit["id"],
        credit_version=credit["version"],
        remittance_id=f["later"],
        source_digest=digest,
        amount=amount,
        reason="Apply my actual retained credit to this exact later remittance",
    )["request"]
    result = command(
        f,
        "collector_surplus_application_prepare",
        credit_id=credit["id"],
        credit_version=credit["version"],
        collector_request_id=request["id"],
        collector_request_version=request["version"],
        remittance_id=f["later"],
        source_digest=digest,
        amount=amount,
        evidence_id=f["evidence"],
        reason="Independent approval of the exact future custody split",
    )
    assert result["disposition"] == "reserved", result["blockers"]
    action = result["action_record"]
    assert action["kind"] == "application" and action["event_id"] is None
    return action


def _count(f, action, amount, *, counted_at=None):
    account = (
        f["conn"]
        .execute("SELECT * FROM treasury.accounts WHERE id=%s", (f["wallet"],))
        .fetchone()
    )
    review = preview(
        f["service"],
        f["conn"],
        f["actor"],
        f["later"],
        SettlementPreview(
            account_id=f["wallet"],
            expected_version=account["version"],
            credit_application_id=action["id"],
            credit_application_version=action["version"],
        ),
    )
    assert review["can_count"], review["blockers"]
    assert review["authorized_credit_application"] == action["amount"]
    assert Decimal(review["physical_cash_required"]) == Decimal("100.00") - Decimal(
        action["amount"]
    )
    return command(
        f,
        "collector_count_record",
        remittance_id=f["later"],
        source_digest=review["source_digest"],
        counted_amount=amount,
        counted_at=counted_at or f["service"].clock(),
        evidence_id=f["evidence"],
        recipient_attestation="Actual physical cash counted separately from approved credit",
        review_acknowledged=True,
        credit_application_id=action["id"],
        credit_application_version=action["version"],
    )["count"]


def _accept(f, action, count):
    return command(
        f,
        "collector_count_accept",
        count_id=count["id"],
        count_version=count["version"],
        source_digest=count["source_digest"],
        physical_receipt_acknowledged=True,
        credit_application_id=action["id"],
        credit_application_version=action["version"],
    )


def test_actual_application_approval_reserves_without_consuming_credit_or_posting_money(
    credit_application,
):
    f = credit_application
    before = balances(f)
    _approve(f)
    current = _credit(f)
    assert current["outstanding_amount"] == "10.00"
    assert current["reserved_amount"] == "4.00"
    assert current["available_amount"] == "6.00"
    assert current["applied_amount"] == "0.00"
    assert _cash(f) == f["starting_cash"]
    assert balances(f) == before


def test_unconsumed_application_cancellation_releases_only_its_reservation(
    credit_application,
):
    f = credit_application
    before = balances(f)
    action = _approve(f)
    command(
        f,
        "collector_surplus_action_cancel",
        action_id=action["id"],
        action_version=action["version"],
        evidence_id=f["evidence"],
        reason="Collector request cancelled before any custody settlement",
    )
    current = _credit(f)
    assert current["outstanding_amount"] == current["available_amount"] == "10.00"
    assert current["reserved_amount"] == current["applied_amount"] == "0.00"
    assert _cash(f) == f["starting_cash"] and balances(f) == before


@pytest.mark.parametrize(("physical", "excess"), [("96.00", "0.00"), ("98.00", "2.00")])
def test_actual_accepted_count_consumes_credit_once_and_records_only_physical_cash(
    credit_application, physical, excess
):
    f = credit_application
    before = balances(f)
    action = _approve(f)
    result = _accept(f, action, _count(f, action, physical))
    settlement = result["settlement"]
    assert settlement["physical_amount"] == physical
    assert settlement["authorized_credit_amount"] == "4.00"
    assert settlement["gross_obligation"] == "100.00"
    assert _cash(f) == f["starting_cash"] + Decimal(physical)
    assert balances(f) == before  # operational acceptance never posts monetary GL
    current = _credit(f)
    assert current["applied_amount"] == "4.00"
    assert current["reserved_amount"] == "0.00"
    assert current["outstanding_amount"] == current["available_amount"] == "6.00"
    entries = (
        f["conn"]
        .execute(
            "SELECT payload FROM treasury.collector_entries WHERE credit_id=%s AND payload->>'kind'='application'",
            (UUID(f["credit"]["id"]),),
        )
        .fetchall()
    )
    assert len(entries) == 1
    assert entries[0]["payload"]["amount"] == "4.00"
    assert entries[0]["payload"]["action_id"] == action["id"]
    links = (
        f["conn"]
        .execute(
            "SELECT source_kind,linked_amount FROM treasury.source_links WHERE event_id=%s ORDER BY source_kind",
            (UUID(settlement["event_id"]),),
        )
        .fetchall()
    )
    assert {r["source_kind"]: r["linked_amount"] for r in links} == {
        "collector_remittance_physical": Decimal("96.00"),
        **({"collector_excess_pending": Decimal(excess)} if Decimal(excess) else {}),
    }
    if Decimal(excess):
        assert result["case"]["received_excess_amount"] == excess
    else:
        assert result["case"] is None
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_short_physical_count_does_not_consume_the_approved_credit(credit_application):
    f = credit_application
    action = _approve(f)
    count = _count(f, action, "95.00")
    assert count["disposition"] == "counted_short_rejected"
    with pytest.raises(TreasuryConflict), f["conn"].transaction():
        _accept(f, action, count)
    current = _credit(f)
    assert current["applied_amount"] == "0.00" and current["reserved_amount"] == "4.00"
    assert _cash(f) == f["starting_cash"]
    assert (
        f["conn"]
        .execute(
            "SELECT status FROM lending.collection_remittances WHERE id=%s",
            (f["later"],),
        )
        .fetchone()["status"]
        == "submitted"
    )


@pytest.mark.parametrize("credit_application", ["100.00"], indirect=True)
def test_all_credit_acceptance_retains_zero_cash_without_fabricating_an_event(
    credit_application,
):
    f = credit_application
    before = balances(f)
    events_before = (
        f["conn"].execute("SELECT count(*) AS n FROM treasury.events").fetchone()["n"]
    )
    action = _approve(f, "100.00")
    result = _accept(f, action, _count(f, action, "0.00"))
    assert result["settlement"]["event_id"] is None
    assert result["settlement"]["physical_amount"] == "0.00"
    assert result["settlement"]["authorized_credit_amount"] == "100.00"
    assert result["case"] is None
    assert _credit(f)["outstanding_amount"] == "0.00"
    assert (
        f["conn"].execute("SELECT count(*) AS n FROM treasury.events").fetchone()["n"]
        == events_before
    )
    assert _cash(f) == f["starting_cash"] and balances(f) == before
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
