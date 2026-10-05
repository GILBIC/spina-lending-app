"""Exact Collector cash, liability reclassification and immutable posting proof."""

import os
from contextlib import contextmanager
from decimal import Decimal
from uuid import UUID, uuid4

import psycopg
import pytest
from collector_accounting_test_support import (
    FILE,
    MIGRATION,
    accepted,
    balances,
    confirmed,
    debited,
    post,
    prepare,
    recognized,
    reserved,
    reversed_return,
    review,
    source_case,
)
from test_treasury_receipt_accounting_postgres import install
from treasury_test_support import connect


@pytest.fixture
def collector_accounting(tmp_path, monkeypatch):
    assert os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") == "1"
    with connect() as conn:
        try:
            if MIGRATION.exists():
                install(conn, MIGRATION)
            yield source_case(conn, tmp_path, monkeypatch)
        finally:
            conn.rollback()


def test_actual_count_transfers_existing_custody_cash_and_recognizes_excess_once(
    collector_accounting,
):
    f = collector_accounting
    acceptance = accepted(f)
    source = UUID(acceptance["settlement"]["id"])
    assert balances(f)["1020"] == Decimal("100.00")
    prepared = prepare(f, "settlement", source)
    assert balances(f)["1020"] == Decimal("100.00")
    entry = post(f, prepared)
    assert post(f, prepared) == entry
    actual = balances(f)
    assert actual["1010"] == Decimal("110.00")
    assert actual["1020"] == Decimal("0.00")
    assert actual["2210"] == Decimal("-10.00")
    assert (
        f["conn"]
        .execute("SELECT count(*) AS n FROM accounting.collector_liability_postings")
        .fetchone()["n"]
        == 1
    )
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_credit_recognition_reclassifies_without_moving_cash(collector_accounting):
    f = collector_accounting
    acceptance = accepted(f)
    post(f, prepare(f, "settlement", UUID(acceptance["settlement"]["id"])))
    credit, entry = recognized(f, acceptance)
    post(f, prepare(f, "recognition", entry))
    actual = balances(f)
    assert actual["1010"] == Decimal("110.00")
    assert actual["2210"] == Decimal("0.00")
    assert actual["2220"] == Decimal("-10.00")
    assert credit["outstanding_amount"] == "10.00"
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_recognition_cannot_skip_the_original_count_cash_proof(collector_accounting):
    f = collector_accounting
    acceptance = accepted(f)
    _, entry = recognized(f, acceptance)
    with (
        pytest.raises(psycopg.Error, match="settlement|count") as rejected,
        f["conn"].transaction(),
    ):
        review(f, "recognition", entry)
    assert rejected.value.sqlstate == "55000"


def test_changed_request_does_not_create_second_preparation(collector_accounting):
    f = collector_accounting
    acceptance = accepted(f)
    source = UUID(acceptance["settlement"]["id"])
    request = uuid4()
    prepared = prepare(f, "settlement", source, request=request)
    assert prepare(f, "settlement", source, request=request)["id"] == prepared["id"]
    with pytest.raises(psycopg.Error), f["conn"].transaction():
        f["conn"].execute(
            "SELECT accounting.prepare_collector_liability('settlement',%s,%s,%s,%s)",
            (source, "f" * 64, request, f["actor"].user_id),
        )


def test_reservation_is_not_a_second_liability_or_cash_journal(collector_accounting):
    f = collector_accounting
    acceptance = accepted(f)
    post(f, prepare(f, "settlement", UUID(acceptance["settlement"]["id"])))
    credit, entry = recognized(f, acceptance)
    post(f, prepare(f, "recognition", entry))
    reservation = reserved(f, credit)
    assert reservation["credit"]["outstanding_amount"] == "10.00"
    assert reservation["credit"]["available_amount"] == "6.00"
    with pytest.raises(psycopg.Error, match="actual|debit"), f["conn"].transaction():
        review(f, "return_debit", UUID(reservation["action_record"]["id"]))
    actual = balances(f)
    assert actual["1010"] == Decimal("110.00")
    assert actual["2220"] == Decimal("-10.00")


def test_real_return_transit_fee_confirmation_and_incoming_reversal_each_cash_once(
    collector_accounting,
):
    f = collector_accounting
    acceptance = accepted(f)
    original = prepare(f, "settlement", UUID(acceptance["settlement"]["id"]))
    post(f, original)
    credit, entry = recognized(f, acceptance)
    recognition = prepare(f, "recognition", entry)
    post(f, recognition)
    reservation = reserved(f, credit)
    debit = debited(f, reservation)
    action = UUID(debit["source_link"]["action_record"]["id"])
    debit_prepared = prepare(f, "return_debit", action)
    debit_journal = post(f, debit_prepared)
    actual = balances(f)
    assert actual["1010"] == Decimal("105.00")
    assert actual["1060"] == Decimal("4.00")
    assert actual["5240"] == Decimal("1.00")
    assert actual["2220"] == Decimal("-10.00")
    confirmation, entry = confirmed(f, reservation, debit)
    post(f, prepare(f, "return_confirmation", entry))
    actual = balances(f)
    assert actual["1010"] == Decimal("105.00")
    assert actual["1060"] == Decimal("0.00")
    assert actual["2220"] == Decimal("-6.00")
    _, entry = reversed_return(f, confirmation)
    post(f, prepare(f, "return_reversal", entry))
    assert post(f, debit_prepared) == debit_journal
    post(f, original)
    post(f, recognition)
    actual = balances(f)
    assert actual["1010"] == Decimal("106.00")
    assert actual["2220"] == Decimal("-7.00")
    assert actual["5240"] == Decimal("1.00")
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM accounting.collector_liability_posting_status WHERE NOT exact_posted OR correction_pending"
        )
        .fetchone()["n"]
        == 0
    )
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_current_private_scope_is_rechecked_before_post(collector_accounting):
    f = collector_accounting
    acceptance = accepted(f)
    prepared = prepare(f, "settlement", UUID(acceptance["settlement"]["id"]))
    f["conn"].execute(
        "UPDATE treasury.account_access SET enabled=false WHERE account_id=%s AND user_id=%s",
        (f["wallet"], f["actor"].user_id),
    )
    with pytest.raises(psycopg.Error), f["conn"].transaction():
        post(f, prepared)
    assert balances(f)["1020"] == Decimal("100.00")


def test_changed_cash_chart_cannot_post_retained_review(collector_accounting):
    f = collector_accounting
    acceptance = accepted(f)
    prepared = prepare(f, "settlement", UUID(acceptance["settlement"]["id"]))
    f["conn"].execute(
        "UPDATE accounting.accounts SET normal_balance='credit' WHERE code='1010'"
    )
    with pytest.raises(psycopg.Error), f["conn"].transaction():
        post(f, prepared)
    assert balances(f)["1020"] == Decimal("100.00")


def test_failure_writing_posting_audit_rolls_back_the_cash_journal(
    collector_accounting,
):
    f = collector_accounting
    acceptance = accepted(f)
    prepared = prepare(f, "settlement", UUID(acceptance["settlement"]["id"]))
    f["conn"].execute(
        "CREATE FUNCTION pg_temp.reject_collector_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic collector audit failure'; END $$"
    )
    f["conn"].execute(
        "CREATE TRIGGER synthetic_collector_audit_failure BEFORE INSERT ON accounting.collector_liability_postings FOR EACH ROW EXECUTE FUNCTION pg_temp.reject_collector_audit()"
    )
    with (
        pytest.raises(psycopg.Error, match="synthetic collector audit failure"),
        f["conn"].transaction(),
    ):
        post(f, prepared)
    assert balances(f)["1020"] == Decimal("100.00")
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM accounting.journal_entries WHERE source_type='collector_liability'"
        )
        .fetchone()["n"]
        == 0
    )


def test_posted_count_prevents_competing_legacy_remittance_journal(
    collector_accounting,
):
    f = collector_accounting
    acceptance = accepted(f)
    post(f, prepare(f, "settlement", UUID(acceptance["settlement"]["id"])))
    with (
        pytest.raises(psycopg.Error, match="Collector|collector|count"),
        f["conn"].transaction(),
    ):
        f["conn"].execute(
            "INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,description,source_type,source_reference,source_event_key,created_by_user_id) VALUES(%s,%s,'Synthetic duplicate remittance transfer','remittance_transfer',%s,%s,%s)",
            (
                f["period"],
                f["day"],
                str(f["remittance"]),
                "remittance_transfer:" + str(f["remittance"]),
                f["actor"].user_id,
            ),
        )


def test_current_source_inventory_clears_matched_unpaid_liability_only(
    collector_accounting,
):
    f = collector_accounting
    acceptance = accepted(f)
    settlement = UUID(acceptance["settlement"]["id"])
    case = UUID(acceptance["case"]["id"])
    post(f, prepare(f, "settlement", settlement))
    credit, entry = recognized(f, acceptance)
    post(f, prepare(f, "recognition", entry))
    rows = (
        f["conn"]
        .execute(
            "SELECT source_type,source_id FROM accounting.period_source_blockers(%s)",
            (f["period"],),
        )
        .fetchall()
    )
    identities = {(row["source_type"], row["source_id"]) for row in rows}
    assert ("collector_settlement", settlement) not in identities
    assert ("collector_case", case) not in identities
    assert ("collector_credit", UUID(credit["id"])) not in identities
    assert ("collector_entry", entry) not in identities
    assert ("remittance_transfer", f["remittance"]) not in identities
    # This fixture deliberately does not manufacture unrelated loan assessments or tax evidence.
    assert ("tax_percentage", f["transaction"]) in identities
    assert any(kind == "loan_control_balance" for kind, _ in identities)


def test_later_operational_revision_remains_recordable_and_reopens_source_coverage(
    collector_accounting,
):
    f = collector_accounting
    acceptance = accepted(f)
    prepared = prepare(f, "settlement", UUID(acceptance["settlement"]["id"]))
    journal = post(f, prepared)
    event = UUID(prepared["snapshot"]["cash_event_id"])
    f["conn"].execute(
        "INSERT INTO treasury.event_revisions(id,event_id,version,action,classification,reason,actor_id) VALUES(%s,%s,2,'correct',NULL,'Synthetic subsequent source correction',%s)",
        (uuid4(), event, f["actor"].user_id),
    )
    status = (
        f["conn"]
        .execute(
            "SELECT exact_posted,correction_pending FROM accounting.collector_liability_posting_status WHERE preparation_id=%s",
            (prepared["id"],),
        )
        .fetchone()
    )
    assert status == {"exact_posted": True, "correction_pending": True}
    assert post(f, prepared) == journal
    blockers = (
        f["conn"]
        .execute(
            "SELECT source_type,source_id FROM accounting.period_source_blockers(%s)",
            (f["period"],),
        )
        .fetchall()
    )
    assert {"source_type": "treasury_event", "source_id": event} in blockers
    assert {
        "source_type": "collector_accounting_correction",
        "source_id": prepared["source_id"],
    } in blockers
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_matched_unpaid_credit_and_reserved_return_reconcile_without_liability_settlement(
    collector_accounting,
):
    f = collector_accounting
    acceptance = accepted(f)
    post(f, prepare(f, "settlement", UUID(acceptance["settlement"]["id"])))
    credit, entry = recognized(f, acceptance)
    post(f, prepare(f, "recognition", entry))
    reserved(f, credit)
    actual = (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.collector_control_reconciliation(%s)", (f["day"],)
        )
        .fetchall()
    )
    assert all(
        row["difference"] == 0 and row["unregistered_line_count"] == 0 for row in actual
    )
    payable = next(row for row in actual if row["account_code"] == "2220")
    assert payable["source_balance"] == payable["ledger_balance"] == Decimal("-10.00")


def test_offsetting_unregistered_collector_lines_are_blockers_even_with_zero_net_balance(
    collector_accounting,
):
    f = collector_accounting
    journal = (
        f["conn"]
        .execute(
            "INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,description,source_type,created_by_user_id) VALUES(%s,%s,'Synthetic unattributed control lines','manual',%s) RETURNING id",
            (f["period"], f["day"], f["actor"].user_id),
        )
        .fetchone()["id"]
    )
    f["conn"].execute(
        "INSERT INTO accounting.journal_lines(journal_entry_id,line_number,account_id,description,debit,credit) SELECT %s,leg.n,a.id,'Synthetic unmatched controls',leg.debit,leg.credit FROM accounting.accounts a CROSS JOIN (VALUES(1,5,0),(2,0,5)) leg(n,debit,credit) WHERE a.code='2220'",
        (journal,),
    )
    f["conn"].execute(
        "SELECT accounting.post_journal_entry(%s,%s)", (journal, f["actor"].user_id)
    )
    actual = (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.collector_control_reconciliation(%s) WHERE account_code='2220'",
            (f["day"],),
        )
        .fetchone()
    )
    assert actual["difference"] == 0 and actual["unregistered_line_count"] == 2
    assert (
        f["conn"]
        .execute(
            "SELECT 1 FROM accounting.period_source_blockers(%s) WHERE reason='collector_control_lines_unregistered'",
            (f["period"],),
        )
        .fetchone()
    )


@pytest.mark.parametrize(
    "operation",
    [
        "UPDATE accounting.accounts SET code=code||'x' WHERE code='2220'",
        "UPDATE accounting.accounts SET normal_balance='debit' WHERE code='2210'",
        "DELETE FROM accounting.accounts WHERE code='1060'",
    ],
)
def test_collector_control_semantics_cannot_drop_out_of_inventory(
    collector_accounting, operation
):
    with (
        pytest.raises(psycopg.Error) as rejected,
        collector_accounting["conn"].transaction(),
    ):
        collector_accounting["conn"].execute(operation)
    assert rejected.value.sqlstate == "55000"


@pytest.mark.parametrize(
    "operation",
    [
        "TRUNCATE accounting.journal_lines",
        "TRUNCATE accounting.collector_liability_postings CASCADE",
        "UPDATE accounting.collector_liability_preparations SET source_digest=repeat('f',64)",
        "DELETE FROM accounting.collector_liability_postings",
    ],
)
def test_posted_collector_proof_cannot_be_erased_or_rewritten(
    collector_accounting, operation
):
    f = collector_accounting
    acceptance = accepted(f)
    prepared = prepare(f, "settlement", UUID(acceptance["settlement"]["id"]))
    post(f, prepared)
    with pytest.raises(psycopg.Error), f["conn"].transaction():
        f["conn"].execute(operation)
    assert (
        f["conn"]
        .execute(
            "SELECT exact_posted FROM accounting.collector_liability_posting_status WHERE preparation_id=%s",
            (prepared["id"],),
        )
        .fetchone()["exact_posted"]
    )


def test_repository_rechecks_evidence_bytes_but_completed_retry_keeps_original_journal(
    collector_accounting, tmp_path
):
    from gilbic_backend.collector_liability_accounting_repository import (
        PostgresCollectorLiabilityAccountingRepository,
    )
    from gilbic_backend.treasury_authorization import TreasuryUnavailable

    f = collector_accounting
    acceptance = accepted(f)
    source_id = UUID(acceptance["settlement"]["id"])

    @contextmanager
    def connection():
        with f["conn"].transaction():
            yield f["conn"]

    repo = PostgresCollectorLiabilityAccountingRepository(
        connection_factory=connection, evidence_store=f["store"]
    )
    reviewed = repo.review(f["actor"], source_kind="settlement", source_id=source_id)
    assert "source_facts" not in reviewed and "evidence" not in reviewed
    prepared = repo.prepare(
        f["actor"],
        source_kind="settlement",
        source_id=source_id,
        source_digest=reviewed["source_digest"],
        request_id=uuid4(),
    )["preparation"]
    evidence_path = tmp_path / "private" / f"{f['evidence'].hex}.bin"
    evidence_path.write_bytes(b"changed retained source file")
    with pytest.raises(TreasuryUnavailable, match="evidence"):
        repo.post(
            f["actor"],
            preparation_id=prepared["id"],
            source_digest=prepared["source_digest"],
            confirmation_token=prepared["confirmation_token"],
        )
    assert (
        f["conn"]
        .execute("SELECT count(*) AS n FROM accounting.collector_liability_postings")
        .fetchone()["n"]
        == 0
    )
    evidence_path.write_bytes(FILE)
    posted = repo.post(
        f["actor"],
        preparation_id=prepared["id"],
        source_digest=prepared["source_digest"],
        confirmation_token=prepared["confirmation_token"],
    )
    assert posted["posting"]["exact_posted"] is True
    evidence_path.unlink()
    assert (
        repo.post(
            f["actor"],
            preparation_id=prepared["id"],
            source_digest=prepared["source_digest"],
            confirmation_token=prepared["confirmation_token"],
        )["journal_entry_id"]
        == posted["journal_entry_id"]
    )


def test_private_collector_proofs_and_entrypoints_deny_unprivileged_role(
    collector_accounting,
):
    from psycopg import sql

    conn = collector_accounting["conn"]
    role = sql.Identifier("collector_accounting_probe_" + uuid4().hex)
    conn.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(role))
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA accounting TO {}").format(role))
    for statement in (
        "SELECT * FROM accounting.collector_liability_preparations",
        "SELECT * FROM accounting.collector_liability_postings",
        "SELECT * FROM accounting.collector_liability_posting_status",
        "SELECT accounting.collector_liability_coordinates(NULL,NULL)",
        "SELECT accounting.prepare_collector_liability(NULL,NULL,NULL,NULL,NULL)",
        "SELECT accounting.post_collector_liability(NULL,NULL,NULL,NULL)",
        "SELECT * FROM accounting.collector_control_movements()",
    ):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute(sql.SQL("SET LOCAL ROLE {}").format(role))
            conn.execute(statement)
