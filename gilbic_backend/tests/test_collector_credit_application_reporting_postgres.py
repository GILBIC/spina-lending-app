"""Cash classification, private scopes and complete retained application evidence."""

from decimal import Decimal
from uuid import UUID

import pytest
from collector_accounting_test_support import other_paying_wallet, post, prepare
from gilbic_backend.collector_control_schedule import load_collector_control_schedule
from gilbic_backend.collector_liability_accounting_repository import (
    PostgresCollectorLiabilityAccountingRepository,
)
from gilbic_backend.collector_surplus_reads import detail, workspace
from gilbic_backend.remittance_settlement_projection import attach_settlement_splits
from gilbic_backend.reporting_evidence_repository import read_internal_collector_cash
from gilbic_backend.treasury_authorization import TreasuryDenied
from test_collector_credit_application_postgres import (
    _accept,
    _approve,
    _count,
)
from test_collector_credit_application_postgres import (
    collector_accounting as _collector_accounting,
)
from test_collector_credit_application_postgres import (
    credit_application as _credit_application,
)

collector_accounting = _collector_accounting
credit_application = _credit_application


def test_retained_application_reads_require_both_private_wallets(credit_application):
    f = credit_application
    receiver = other_paying_wallet(f)
    action = _approve(receiver, request_source=f)
    count = _count(receiver, action, "96.00")
    result = _accept(receiver, action, count)
    f["conn"].execute(
        "UPDATE treasury.account_access SET private_history=false WHERE account_id=%s",
        (f["wallet"],),
    )
    for kind, row in (
        ("counts", count),
        ("actions", action),
        ("credits", f["credit"]),
        ("entries", result["application_entry"]),
        ("settlements", result["settlement"]),
    ):
        with pytest.raises(TreasuryDenied), f["conn"].transaction():
            detail(f["service"], f["conn"], f["actor"], kind, UUID(row["id"]))
    for kind in ("credits", "counts", "actions"):
        with pytest.raises(TreasuryDenied), f["conn"].transaction():
            workspace(
                f["service"],
                f["conn"],
                f["actor"],
                kind,
                account_id=receiver["wallet"],
                limit=1,
                offset=999,
            )
    own = detail(
        f["service"],
        f["conn"],
        f["collector"],
        "credits",
        UUID(f["credit"]["id"]),
        mode="own",
    )
    assert own["applied_amount"] == "4.00"
    assert "evidence_id" not in str(own)


@pytest.mark.parametrize(
    ("credit_application", "physical"),
    [("10.00", "98.00"), ("100.00", "0.00")],
    indirect=["credit_application"],
)
def test_history_and_notification_distinguish_actual_cash_from_credit(
    credit_application, physical
):
    f = credit_application
    amount = "4.00" if physical == "98.00" else "100.00"
    action = _approve(f, amount)
    _accept(f, action, _count(f, action, physical))
    rows = [{"id": f["later"]}]
    with f["conn"].cursor() as cursor:
        attach_settlement_splits(cursor, rows)
    split = rows[0]["settlement_split"]
    assert split["physical_amount"] == physical
    assert split["authorized_credit_amount"] == amount
    assert split["gross_obligation"] == "100.00"
    assert set(split) == {
        "physical_amount",
        "authorized_credit_amount",
        "gross_obligation",
        "physical_cash_required",
        "excess_amount",
    }
    notice = (
        f["conn"]
        .execute(
            "SELECT title,message FROM core.user_notifications WHERE remittance_id=%s",
            (f["later"],),
        )
        .fetchone()
    )
    assert notice["title"] == "Remittance settled"
    assert f"Actual cash received: PHP {physical}" in notice["message"]
    assert f"credit applied: PHP {amount}" in notice["message"]


def test_only_the_physical_principal_is_an_internal_cash_handover(credit_application):
    f = credit_application
    action = _approve(f)
    result = _accept(f, action, _count(f, action, "98.00"))
    cash = prepare(f, "settlement", UUID(result["settlement"]["id"]))
    credit = prepare(f, "credit_application", UUID(result["application_entry"]["id"]))
    cash_id, credit_id = post(f, cash), post(f, credit)
    with f["conn"].cursor() as cursor:
        proof = read_internal_collector_cash(cursor, f["period"])
    assert sorted(
        row["internal_principal"]
        for row in proof.values()
        if row["journal_entry_id"] == str(cash_id)
    ) == [Decimal("-96.00"), Decimal("96.00")]
    # The credit is paid out of cash already in custody. It is not another
    # internal handover or wallet cash event, but its selected-cash use is proven.
    application = [
        row for row in proof.values() if row["journal_entry_id"] == str(credit_id)
    ]
    assert len(application) == 1
    assert application[0]["source_kind"] == "credit_application"
    assert application[0]["internal_principal"] == Decimal("0.00")
    repository = PostgresCollectorLiabilityAccountingRepository()
    for preparation in (cash, credit):
        public = repository._public_review(f["conn"], preparation["snapshot"])
        assert public["custody_split"] == {
            "gross_obligation": "100.00",
            "authorized_credit_amount": "4.00",
            "physical_amount": "98.00",
            "physical_cash_required": "96.00",
            "excess_amount": "2.00",
        }
        assert not {
            "application",
            "evidence",
            "source_facts",
            "account_ids",
        }.intersection(public)


@pytest.mark.parametrize("credit_application", ["100.00"], indirect=True)
def test_zero_cash_receiving_wallet_is_authorized_before_schedule_pagination(
    credit_application,
):
    f = credit_application
    receiver = other_paying_wallet(f)
    action = _approve(receiver, "100.00", request_source=f)
    _accept(receiver, action, _count(receiver, action, "0.00"))
    f["conn"].execute(
        "UPDATE treasury.account_access SET private_history=false WHERE account_id=%s",
        (receiver["wallet"],),
    )
    with pytest.raises(TreasuryDenied), f["conn"].transaction():
        load_collector_control_schedule(f["conn"], f["actor"], limit=1, offset=999)


def test_cash_posting_alone_does_not_clear_application_source_coverage(
    credit_application,
):
    f = credit_application
    action = _approve(f)
    result = _accept(f, action, _count(f, action, "96.00"))
    settlement, entry = (
        UUID(result["settlement"]["id"]),
        UUID(result["application_entry"]["id"]),
    )
    post(f, prepare(f, "settlement", settlement))

    def exact(kind, source):
        return (
            f["conn"]
            .execute(
                "SELECT accounting.collector_source_exact(%s,%s,%s) AS exact",
                (kind, source, f["day"]),
            )
            .fetchone()["exact"]
        )

    assert exact("treasury_event", UUID(result["settlement"]["event_id"]))
    assert not exact("collector_settlement", settlement)
    assert not exact("collector_entry", entry)
    assert not exact("remittance_transfer", f["later"])
    post(f, prepare(f, "credit_application", entry))
    assert exact("collector_settlement", settlement)
    assert exact("collector_entry", entry)
    assert exact("remittance_transfer", f["later"])
    evidence = (
        f["conn"]
        .execute(
            "SELECT accounting.period_review_additional_evidence(%s) AS value",
            (f["period"],),
        )
        .fetchone()["value"]
    )
    assert "collector_liability" in evidence
    assert evidence["collector_credit_applications"][0]["id"] == str(entry)
