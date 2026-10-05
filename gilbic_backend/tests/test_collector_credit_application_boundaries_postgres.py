"""Credit application boundaries exercised through the retained operational flow."""

from contextlib import contextmanager
from decimal import Decimal
from uuid import UUID, uuid4

import psycopg
import pytest
from collector_accounting_test_support import (
    balances,
    command,
    other_paying_wallet,
    post,
    prepare,
    review,
)
from gilbic_backend.collector_surplus import load
from gilbic_backend.office_review_evidence_storage import EvidenceFileError
from gilbic_backend.treasury_authorization import TreasuryConflict, TreasuryDenied
from gilbic_backend.treasury_models import COMMAND_ADAPTER
from test_collector_credit_application_postgres import (
    _accept,
    _approve,
    _cash,
    _count,
    _credit,
)
from test_collector_credit_application_postgres import (
    collector_accounting as _collector_accounting,
)
from test_collector_credit_application_postgres import (
    credit_application as _credit_application,
)

collector_accounting = _collector_accounting
credit_application = _credit_application


def test_cancelled_approval_cannot_consume_a_previously_recorded_count(
    credit_application,
):
    f = credit_application
    action = _approve(f)
    count = _count(f, action, "96.00")
    command(
        f,
        "collector_surplus_action_cancel",
        action_id=action["id"],
        action_version=action["version"],
        evidence_id=f["evidence"],
        reason="Cancel before accepted physical handover",
    )
    with pytest.raises(TreasuryConflict), f["conn"].transaction():
        _accept(f, action, count)
    assert _credit(f)["available_amount"] == "10.00"
    assert _credit(f)["applied_amount"] == "0.00"
    assert _cash(f) == f["starting_cash"]


@pytest.mark.parametrize("amount", ["10.01", "100.01"])
def test_application_cannot_reserve_more_than_credit_or_obligation(
    credit_application, amount
):
    f = credit_application
    with pytest.raises(TreasuryConflict), f["conn"].transaction():
        _approve(f, amount)
    assert _credit(f)["available_amount"] == "10.00"
    assert _credit(f)["reserved_amount"] == "0.00"


def test_selected_count_cannot_be_accepted_without_the_selected_approval(
    credit_application,
):
    f = credit_application
    action = _approve(f)
    count = _count(f, action, "96.00")
    with pytest.raises(TreasuryConflict), f["conn"].transaction():
        command(
            f,
            "collector_count_accept",
            count_id=count["id"],
            count_version=count["version"],
            source_digest=count["source_digest"],
            physical_receipt_acknowledged=True,
        )
    assert _credit(f)["reserved_amount"] == "4.00"
    assert _cash(f) == f["starting_cash"]


def test_revoked_private_authority_prevents_acceptance(credit_application):
    f = credit_application
    action = _approve(f)
    count = _count(f, action, "96.00")
    f["conn"].execute(
        "UPDATE treasury.account_access SET private_history=false WHERE account_id=%s",
        (f["wallet"],),
    )
    with pytest.raises(TreasuryDenied), f["conn"].transaction():
        _accept(f, action, count)
    assert _credit(f)["reserved_amount"] == "4.00"
    assert _cash(f) == f["starting_cash"]


def test_failure_after_consumption_rolls_back_credit_cash_and_settlement(
    credit_application,
):
    f = credit_application
    action = _approve(f)
    count = _count(f, action, "96.00")
    f["conn"].execute(
        """CREATE FUNCTION pg_temp.reject_application_custody() RETURNS trigger
      LANGUAGE plpgsql AS $$ BEGIN IF NEW.id = '{}'::uuid AND NEW.status='received'
      THEN RAISE EXCEPTION 'synthetic custody failure'; END IF; RETURN NEW; END $$""".format(
            f["later"]
        )
    )
    f["conn"].execute(
        "CREATE TRIGGER synthetic_application_custody_failure BEFORE UPDATE ON lending.collection_remittances FOR EACH ROW EXECUTE FUNCTION pg_temp.reject_application_custody()"
    )
    with (
        pytest.raises(psycopg.Error, match="synthetic custody failure"),
        f["conn"].transaction(),
    ):
        _accept(f, action, count)
    assert _credit(f)["reserved_amount"] == "4.00"
    assert _credit(f)["applied_amount"] == "0.00"
    assert _cash(f) == f["starting_cash"]
    assert (
        not f["conn"]
        .execute("SELECT 1 FROM treasury.collector_credit_applications")
        .fetchone()
    )
    assert (
        not f["conn"]
        .execute(
            "SELECT 1 FROM treasury.collector_settlements WHERE remittance_id=%s",
            (f["later"],),
        )
        .fetchone()
    )


def test_full_service_retry_returns_same_acceptance_and_rechecks_private_scope(
    credit_application, monkeypatch
):
    f = credit_application
    action = _approve(f)
    count = _count(f, action, "96.00")
    monkeypatch.setenv("SPINA_TREASURY_ENABLED", "true")

    @contextmanager
    def borrowed():
        yield f["conn"]

    monkeypatch.setattr(f["service"], "connect", borrowed)
    account = (
        f["conn"]
        .execute("SELECT version FROM treasury.accounts WHERE id=%s", (f["wallet"],))
        .fetchone()
    )
    model = COMMAND_ADAPTER.validate_python(
        {
            "action": "collector_count_accept",
            "request_id": uuid4(),
            "account_id": f["wallet"],
            "expected_version": account["version"],
            "count_id": count["id"],
            "count_version": count["version"],
            "source_digest": count["source_digest"],
            "physical_receipt_acknowledged": True,
            "credit_application_id": action["id"],
            "credit_application_version": action["version"],
        }
    )
    first = f["service"].execute(f["actor"], model)
    assert f["service"].execute(f["actor"], model) == first
    assert _cash(f) == f["starting_cash"] + Decimal("96.00")
    assert _credit(f)["applied_amount"] == "4.00"
    assert (
        f["conn"]
        .execute("SELECT count(*) AS n FROM treasury.collector_credit_applications")
        .fetchone()["n"]
        == 1
    )
    f["conn"].execute(
        "UPDATE treasury.account_access SET private_history=false WHERE account_id=%s",
        (f["wallet"],),
    )
    with pytest.raises(TreasuryDenied), f["conn"].transaction():
        f["service"].execute(f["actor"], model)


def test_acceptance_keeps_the_original_recognition_digest_current(credit_application):
    f = credit_application
    row = (
        f["conn"]
        .execute(
            "SELECT source_id,source_digest,snapshot FROM accounting.collector_liability_preparations WHERE source_kind='recognition'"
        )
        .fetchone()
    )
    action = _approve(f)
    _accept(f, action, _count(f, action, "96.00"))
    actual = review(f, "recognition", row["source_id"])
    assert actual["source_digest"] == row["source_digest"]
    assert {k: v for k, v in actual.items() if k != "source_digest"} == row["snapshot"]


def test_later_source_recovery_is_retained_without_rejecting_the_real_application(
    credit_application,
):
    f = credit_application
    action = _approve(f)
    result = _accept(f, action, _count(f, action, "96.00"))
    prepared = prepare(f, "credit_application", UUID(result["application_entry"]["id"]))
    post(f, prepared)
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
    current = load(f["conn"], "credits", UUID(f["credit"]["id"]))
    command(
        f,
        "collector_surplus_resolve_source",
        credit_id=current["id"],
        credit_version=current["version"],
        source_id=f["remittance"],
        source_digest="a" * 64,
        amount="4.00",
        evidence_id=f["evidence"],
        reason="Later source evidence requires retained recovery review",
    )
    assert _credit(f)["frozen"] is True
    assert _credit(f)["applied_amount"] == "4.00"
    assert _cash(f) == f["starting_cash"] + Decimal("96.00")
    assert (
        f["conn"]
        .execute(
            "SELECT correction_pending FROM accounting.collector_liability_posting_status WHERE preparation_id=%s",
            (prepared["id"],),
        )
        .fetchone()["correction_pending"]
    )


def test_selected_approval_survives_connection_timezone_changes(credit_application):
    f = credit_application
    f["conn"].execute("SET LOCAL TIME ZONE 'UTC'")
    action = _approve(f)
    count = _count(f, action, "96.00")
    f["conn"].execute("SET LOCAL TIME ZONE 'Asia/Manila'")
    result = _accept(f, action, count)
    assert result["settlement"]["authorized_credit_amount"] == "4.00"
    assert result["count"] == count
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")


@pytest.mark.parametrize(
    "credit_application",
    [{"amount": "10.00", "post_recognition": False}],
    indirect=True,
)
def test_credit_without_current_posted_recognition_cannot_be_reserved(
    credit_application,
):
    f = credit_application
    with pytest.raises(TreasuryConflict, match="recognition"), f["conn"].transaction():
        _approve(f)
    assert _credit(f)["reserved_amount"] == "0.00"


def test_origin_evidence_bytes_are_required_for_a_different_receiving_wallet(
    credit_application,
):
    f = credit_application
    receiver = other_paying_wallet(f)
    original = f["store"].root / f"{f['evidence'].hex}.bin"
    original.write_bytes(b"Synthetic corrupt original recognition attachment")
    with pytest.raises(EvidenceFileError), f["conn"].transaction():
        _approve(receiver, request_source=f)
    assert _credit(f)["reserved_amount"] == "0.00"


@pytest.mark.parametrize("credit_application", ["100.00"], indirect=True)
def test_full_credit_with_actual_extra_cash_records_only_excess_in_cash_leg(
    credit_application,
):
    f = credit_application
    action = _approve(f, "100.00")
    result = _accept(f, action, _count(f, action, "2.00"))
    cash = prepare(f, "settlement", UUID(result["settlement"]["id"]))
    application = prepare(
        f, "credit_application", UUID(result["application_entry"]["id"])
    )
    assert {line["account_code"] for line in cash["snapshot"]["lines"]} == {
        "1010",
        "2210",
    }
    post(f, cash)
    post(f, application)
    assert result["settlement"]["physical_amount"] == "2.00"
    assert result["case"]["received_excess_amount"] == "2.00"
    assert _credit(f)["outstanding_amount"] == "0.00"
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")


@pytest.mark.parametrize(("physical", "excess"), [("96.00", "0.00"), ("98.00", "2.00")])
def test_cash_and_liability_are_two_exact_journals_without_double_receipt(
    credit_application, physical, excess
):
    f = credit_application
    action = _approve(f)
    result = _accept(f, action, _count(f, action, physical))
    cash = prepare(f, "settlement", UUID(result["settlement"]["id"]))
    application = prepare(
        f, "credit_application", UUID(result["application_entry"]["id"])
    )
    assert cash["snapshot"]["cash_event_id"] == result["settlement"]["event_id"]
    assert application["snapshot"]["cash_event_id"] is None
    assert [
        (r["account_code"], r["debit"], r["credit"])
        for r in application["snapshot"]["lines"]
    ] == [("2220", "4.00", "0.00"), ("1020", "0.00", "4.00")]
    assert cash["snapshot"]["source_facts"]["physical_principal"] == "96.00"
    cash_id, application_id = post(f, cash), post(f, application)
    assert cash_id != application_id
    assert post(f, application) == application_id
    actual = balances(f)
    assert actual["1010"] == f["starting_cash"] + Decimal(physical)
    assert actual["1020"] == Decimal("0.00")
    assert actual["2220"] == Decimal("-6.00")
    assert actual["2210"] == -Decimal(excess)
    rows = (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.collector_control_reconciliation(%s)", (f["day"],)
        )
        .fetchall()
    )
    assert all(
        row["difference"] == 0 and row["unregistered_line_count"] == 0 for row in rows
    )
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")


@pytest.mark.parametrize("credit_application", ["100.00"], indirect=True)
def test_all_credit_settlement_has_only_liability_journal_and_exact_coverage(
    credit_application,
):
    f = credit_application
    action = _approve(f, "100.00")
    result = _accept(f, action, _count(f, action, "0.00"))
    with pytest.raises(psycopg.Error), f["conn"].transaction():
        prepare(f, "settlement", UUID(result["settlement"]["id"]))
    application = prepare(
        f, "credit_application", UUID(result["application_entry"]["id"])
    )
    post(f, application)
    assert balances(f)["2220"] == balances(f)["1020"] == Decimal("0.00")
    assert _cash(f) == f["starting_cash"]
    for kind, source in [
        ("collector_entry", result["application_entry"]["id"]),
        ("collector_settlement", result["settlement"]["id"]),
        ("remittance_transfer", str(f["later"])),
    ]:
        assert (
            f["conn"]
            .execute(
                "SELECT accounting.collector_source_exact(%s,%s,%s) AS exact",
                (kind, source, f["day"]),
            )
            .fetchone()["exact"]
        )
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_consumption_facts_are_immutable_and_private(credit_application):
    f = credit_application
    action = _approve(f)
    result = _accept(f, action, _count(f, action, "96.00"))
    for statement in (
        "UPDATE treasury.collector_credit_applications SET amount=amount",
        "DELETE FROM treasury.collector_credit_applications",
        "TRUNCATE treasury.collector_credit_applications",
    ):
        with pytest.raises(psycopg.Error), f["conn"].transaction():
            f["conn"].execute(statement)
    assert (
        f["conn"]
        .execute(
            "SELECT treasury.collector_application_exact(%s) AS valid",
            (UUID(result["application_entry"]["id"]),),
        )
        .fetchone()["valid"]
    )
    assert (
        f["conn"]
        .execute(
            "SELECT relrowsecurity AS enabled FROM pg_class WHERE oid='treasury.collector_credit_applications'::regclass"
        )
        .fetchone()["enabled"]
    )
    assert (
        not f["conn"]
        .execute(
            "SELECT r.rolname FROM pg_roles r WHERE r.rolname IN ('anon','authenticated','service_role') AND has_table_privilege(r.oid,'treasury.collector_credit_applications','SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')"
        )
        .fetchall()
    )
    assert (
        not f["conn"]
        .execute(
            "SELECT p.proname FROM pg_proc p, LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) acl WHERE p.pronamespace='treasury'::regnamespace AND p.proname LIKE '%collector%application%' AND acl.grantee=0 AND acl.privilege_type='EXECUTE'"
        )
        .fetchall()
    )
