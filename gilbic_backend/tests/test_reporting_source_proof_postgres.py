"""First-book funding must be reviewable only with its exact protected audit."""

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from test_initial_capital_funding_postgres import _post, _record
from test_period_close_postgres import _body
from test_reporting_policy_postgres import book_db as _book_db
from test_reporting_policy_postgres import liabilities as _liabilities
from test_reporting_policy_postgres import reporting_db as _reporting_db

book_db = _book_db
liabilities = _liabilities
reporting_db = _reporting_db

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"


@pytest.fixture
def source_reporting(reporting_db):
    f = reporting_db
    f["conn"].execute(
        _body((SQL_ROOT / "0161_add_journal_disclosure_reviews.sql").read_text())
    )
    migration = SQL_ROOT / "0170_add_reporting_source_proof.sql"
    if migration.exists():
        f["conn"].execute(_body(migration.read_text()))
    return f


def capital(f):
    evidence = _record(
        f["conn"],
        actor_id=f["actor"],
        key=uuid4(),
        funding_date=f["day"],
        amount="123.45",
        cash_code="1010",
        suffix=uuid4().hex,
    )
    journal = (
        f["conn"]
        .execute(
            "SELECT accounting.prepare_initial_capital_funding_journal(%s,%s)",
            (evidence, f["actor"]),
        )
        .fetchone()[0]
    )
    _post(
        f["conn"],
        evidence_id=evidence,
        actor_id=f["actor"],
        token="b" * 64,
        digest="a" * 64,
        amount="123.45",
        cash_code="1010",
        posting_date=f["day"],
        period_id=f["period"],
    )
    return journal


def status(f, journal):
    return (
        f["conn"]
        .execute("SELECT accounting.journal_disclosure_source_status(%s)", (journal,))
        .fetchone()[0]
    )


def test_first_capital_has_exact_reportable_source_without_prior_books(
    source_reporting,
):
    f = source_reporting
    assert status(f, capital(f)) == "current"


def test_funding_report_rechecks_chart_semantics_but_keeps_retired_history(
    source_reporting,
):
    f = source_reporting
    journal = capital(f)
    f["conn"].execute(
        "UPDATE accounting.accounts SET is_active=false,name='Retired capital' WHERE code='3000'"
    )
    assert status(f, journal) == "current"
    f["conn"].execute(
        "UPDATE accounting.accounts SET account_type='liability' WHERE code='3000'"
    )
    assert status(f, journal) == "source_correction_required"


def test_missing_posted_identity_remains_blocked(source_reporting):
    assert status(source_reporting, uuid4()) == "posted_journal_required"


def test_remittance_and_authentic_reversal_keep_both_historical_legs(source_reporting):
    import test_remittance_transfer_journal_lifecycle_postgres as helpers

    f = source_reporting
    conn = f["conn"]
    suffix = uuid4().hex[:10]
    remittance = helpers._create_received_remittance(
        conn,
        suffix=suffix,
        collector_id=helpers._create_user(conn, suffix),
        recipient_id=f["actor"],
        business_date=f["day"],
    )
    evidence = helpers._record_evidence(
        conn, remittance_id=remittance, actor_id=f["actor"], business_date=f["day"]
    )
    key = f"remittance_transfer:{remittance}"
    prepared = conn.execute(
        "SELECT accounting.create_remittance_transfer_journal_draft(%s,%s,%s,%s,%s,%s,'cash_office','cash_collector_custody',1500.00,'remittance_transfer_coordinates_v1','remittance_transfer_journal_draft_v1')",
        (remittance, f["actor"], "a" * 64, evidence, key, f["day"]),
    ).fetchone()[0]
    journal = conn.execute(
        "SELECT journal_entry_id FROM accounting.remittance_transfer_journal_preparations WHERE id=%s",
        (prepared,),
    ).fetchone()[0]
    posted = conn.execute(
        "SELECT accounting.post_remittance_transfer_journal(%s,%s,%s,%s,%s,%s,1500.00,'remittance_transfer_journal_posting_v1')",
        (prepared, f["actor"], "b" * 64, journal, key, "a" * 64),
    ).fetchone()[0]
    assert status(f, journal) == "current"
    reversal = conn.execute(
        "SELECT accounting.reverse_posted_remittance_transfer(%s,%s,%s,'Synthetic retained correction')",
        (posted, f["actor"], f["day"]),
    ).fetchone()[0]
    reversed_journal = conn.execute(
        "SELECT reversal_journal_entry_id FROM accounting.remittance_transfer_journal_reversals WHERE id=%s",
        (reversal,),
    ).fetchone()[0]
    assert status(f, journal) == "current"
    assert status(f, reversed_journal) == "current"


def test_protected_ecl_chain_retains_exact_historical_disclosure_proof(
    source_reporting,
):
    import test_ecl_a5_writeoff_recovery_postgres as helpers

    f = source_reporting
    conn = f["conn"]
    suffix = uuid4().hex[:10]
    case = helpers.a5._case(conn, suffix, period_id=f["period"])
    review = helpers._writeoff_review(conn, case, suffix)
    measurement = helpers._full_loss_measurement(conn, case)
    helpers.a5._remeasure(conn, case, measurement, "6" * 64)
    writeoff = helpers._post_writeoff(
        conn,
        case,
        review_id=review,
        measurement=measurement,
        gross=helpers._gross(conn, case[1]),
        token="8" * 64,
    )
    posted_at = conn.execute(
        "SELECT posted_at FROM accounting.ecl_accounting_writeoffs WHERE id=%s",
        (writeoff,),
    ).fetchone()[0]
    transaction = helpers.recovery_helpers._collection(
        conn,
        loan_id=case[1],
        actor_user_id=case[0],
        device_id=helpers.recovery_helpers._device(conn, case[0], suffix),
        suffix=suffix,
        device_sequence=1,
        accepted_at=posted_at + timedelta(seconds=1),
    )
    recovery_review = helpers._recovery_review(conn, case, transaction, suffix)
    helpers._post_recovery(
        conn,
        case,
        review_id=recovery_review,
        transaction_id=transaction,
        token="c" * 64,
    )
    journals = conn.execute(
        "SELECT DISTINCT j.id,j.source_type FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id WHERE l.loan_id=%s ORDER BY j.source_type",
        (case[1],),
    ).fetchall()
    assert {
        "loan_disbursement",
        "ecl_allowance",
        "ecl_allowance_remeasurement",
        "ecl_writeoff",
        "ecl_post_writeoff_recovery",
    } <= {row[1] for row in journals}
    assert {source: status(f, journal) for journal, source in journals} == {
        source: "current" for _, source in journals
    }
    # A semantic account mutation must never retain the historical green label.
    conn.execute(
        "UPDATE accounting.accounts SET normal_balance='credit' WHERE code='5000'"
    )
    assert all(
        status(f, journal) == "source_correction_required"
        for journal, source in journals
        if source
        in {
            "ecl_allowance",
            "ecl_allowance_remeasurement",
            "ecl_post_writeoff_recovery",
        }
    )
