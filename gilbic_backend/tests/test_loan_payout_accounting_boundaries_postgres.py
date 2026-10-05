"""Actual protected payout admission and retained transit boundaries."""

from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from test_first_loan_postgres import (
    private_fixture_configuration as _private_fixture_configuration,
)
from test_loan_payout_accounting_postgres import (
    balances,
    complete_borrower,
    confirm,
    coordinates,
    debit,
    post_stage,
    prepare_operational,
)
from test_loan_payout_accounting_postgres import payout_accounting as _payout_accounting
from test_loan_payout_accounting_postgres import payout_database as _payout_database
from test_treasury_receipt_accounting_postgres import mapping

private_fixture_configuration = _private_fixture_configuration
payout_accounting = _payout_accounting
payout_database = _payout_database


def retained(f, payout, stage="debit"):
    source = coordinates(f, payout, stage)
    prep = (
        f["conn"]
        .execute(
            "SELECT accounting.prepare_loan_payout_accounting(%s,%s,%s,%s,%s) AS id",
            (payout, stage, source["source_digest"], uuid4(), f["actor"].user_id),
        )
        .fetchone()["id"]
    )
    return (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.loan_payout_accounting_preparations WHERE id=%s",
            (prep,),
        )
        .fetchone()
    )


def post(f, prep):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.post_loan_payout_accounting(%s,%s,%s,%s) AS id",
            (
                prep["id"],
                prep["source_digest"],
                prep["confirmation_token"],
                f["actor"].user_id,
            ),
        )
        .fetchone()["id"]
    )


def actual(f, *, fee="2.00"):
    _, prepared = prepare_operational(f, destination="collector")
    debit(f, prepared, fee=fee)
    return prepared


def status(f, payout, stage="debit"):
    return (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.loan_payout_accounting_posting_status WHERE payout_id=%s AND stage=%s",
            (payout, stage),
        )
        .fetchone()
    )


def correction(f, payout):
    f["conn"].execute(
        "INSERT INTO treasury.event_revisions(id,event_id,version,action,reason,actor_id) SELECT %s,event_id,2,'correct','Synthetic late actual correction',%s FROM treasury.loan_payouts WHERE id=%s",
        (uuid4(), f["actor"].user_id, payout),
    )


@pytest.mark.parametrize(
    "change",
    [
        "mapping",
        "private_permission",
        "management_permission",
        "cash_chart",
        "fee_chart",
        "correction",
    ],
)
def test_changed_payout_review_cannot_post_any_money(payout_accounting, change):
    f = payout_accounting
    payout = actual(f)["target_id"]
    prep = retained(f, payout)
    conn = f["conn"]
    if change == "mapping":
        mapping(f, version=1, reference="test:replacement-payout-mapping")
    elif change == "private_permission":
        conn.execute(
            "UPDATE treasury.account_access SET private_history=false WHERE account_id=%s",
            (f["wallet"],),
        )
    elif change == "management_permission":
        conn.execute(
            "DELETE FROM core.role_permissions WHERE permission_code='accounting.journal.manage'"
        )
    elif change in {"cash_chart", "fee_chart"}:
        conn.execute(
            "UPDATE accounting.accounts SET normal_balance='credit' WHERE code=%s",
            ("1030" if change == "cash_chart" else "5240",),
        )
    else:
        correction(f, payout)
    with pytest.raises(psycopg.Error), conn.transaction():
        post(f, prep)
    assert balances(f) == {}


def test_exact_request_and_confirmation_cannot_be_reinterpreted(payout_accounting):
    f = payout_accounting
    payout = actual(f)["target_id"]
    prep = retained(f, payout)
    args = (
        payout,
        "debit",
        prep["source_digest"],
        prep["request_id"],
        f["actor"].user_id,
    )
    query = "SELECT accounting.prepare_loan_payout_accounting(%s,%s,%s,%s,%s) AS id"
    assert f["conn"].execute(query, args).fetchone()["id"] == prep["id"]
    with pytest.raises(psycopg.Error, match="retry"), f["conn"].transaction():
        f["conn"].execute(query, args[:1] + ("completion",) + args[2:])
    for key in ("source_digest", "confirmation_token"):
        with (
            pytest.raises(psycopg.Error, match="confirmation"),
            f["conn"].transaction(),
        ):
            post(f, prep | {key: "0" * 64})


def test_late_actual_correction_keeps_original_cash_once_and_requires_review(
    payout_accounting,
):
    f = payout_accounting
    payout = actual(f)["target_id"]
    prep = retained(f, payout)
    entry = post(f, prep)
    correction(f, payout)
    assert post(f, prep) == entry
    current = status(f, payout)
    assert current["exact_posted"] is True and current["correction_pending"] is True
    row = (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.loan_payout_transit_reconciliation(%s) WHERE payout_id=%s",
            (current["posting_date"], payout),
        )
        .fetchone()
    )
    assert row["expected_transit"] == row["ledger_transit"] == 1000
    assert row["requires_review"] is True
    assert balances(f) == {
        "1030": Decimal(-1002),
        "1050": Decimal(1000),
        "5240": Decimal(2),
    }


def test_collector_receipt_cannot_create_borrower_receivable(payout_accounting):
    f = payout_accounting
    prepared = actual(f)
    post_stage(f, prepared["target_id"], "debit")
    confirm(f, prepared["target_id"])
    with (
        pytest.raises(psycopg.Error, match="borrower completion|intermediary"),
        f["conn"].transaction(),
    ):
        coordinates(f, prepared["target_id"], "completion")
    current = status(f, prepared["target_id"])
    assert current["exact_posted"] is True and current["correction_pending"] is False
    row = (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.loan_payout_transit_reconciliation(%s) WHERE payout_id=%s",
            (current["posting_date"], prepared["target_id"]),
        )
        .fetchone()
    )
    assert row["expected_transit"] == row["ledger_transit"] == 1000
    assert row["difference"] == 0 and row["requires_review"] is False
    assert "1100" not in balances(f)


def test_completion_requires_prior_exact_cash_audit_and_preserves_it(payout_accounting):
    f = payout_accounting
    prepared = actual(f, fee="0.00")
    confirm(f, prepared["target_id"])
    complete_borrower(f, prepared)
    with pytest.raises(psycopg.Error, match="prior debit"), f["conn"].transaction():
        coordinates(f, prepared["target_id"], "completion")
    post_stage(f, prepared["target_id"], "debit")
    original = status(f, prepared["target_id"])
    post_stage(f, prepared["target_id"], "completion")
    assert status(f, prepared["target_id"]) == original
    assert balances(f) == {
        "1030": Decimal(-1000),
        "1050": Decimal(0),
        "1100": Decimal(1000),
    }


@pytest.mark.parametrize("code", ["1030", "5240"])
def test_semantic_chart_drift_marks_retained_payout_pending(payout_accounting, code):
    f = payout_accounting
    payout = actual(f)["target_id"]
    post_stage(f, payout, "debit")
    f["conn"].execute(
        "UPDATE accounting.accounts SET normal_balance='credit' WHERE code=%s", (code,)
    )
    assert status(f, payout)["correction_pending"] is True


def test_display_rename_and_retirement_keep_historical_payout_exact(payout_accounting):
    f = payout_accounting
    payout = actual(f)["target_id"]
    post_stage(f, payout, "debit")
    f["conn"].execute(
        "UPDATE accounting.accounts SET is_active=false,name='Retired synthetic payout chart' WHERE code IN('1030','1050','5240')"
    )
    assert status(f, payout)["correction_pending"] is False


@pytest.mark.parametrize(
    "table",
    [
        "loan_payout_accounting_preparations",
        "loan_payout_accounting_postings",
        "journal_lines",
    ],
)
def test_payout_evidence_and_cash_proof_cannot_be_truncated(payout_accounting, table):
    f = payout_accounting
    post_stage(f, actual(f)["target_id"], "debit")
    with (
        pytest.raises(psycopg.Error, match="immutable|protected|Protected|payout"),
        f["conn"].transaction(),
    ):
        f["conn"].execute(
            sql.SQL("TRUNCATE accounting.{} CASCADE").format(sql.Identifier(table))
        )


def test_native_source_key_cannot_admit_an_arbitrary_manual_journal(payout_accounting):
    f = payout_accounting
    payout = actual(f)["target_id"]
    prep = retained(f, payout)
    with pytest.raises(psycopg.Error, match="exact reviewed"), f["conn"].transaction():
        f["conn"].execute(
            "INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,description,source_type,source_reference,source_event_key,created_by_user_id) VALUES(%s,%s,'Synthetic manual bypass','treasury_loan_payout',%s,%s,%s)",
            (
                f["period"],
                prep["snapshot"]["posting_date"],
                str(payout),
                prep["snapshot"]["source_event_key"],
                f["actor"].user_id,
            ),
        )


def test_balanced_native_journal_without_retained_audit_cannot_commit(
    payout_accounting,
):
    f = payout_accounting
    payout = actual(f)["target_id"]
    prep = retained(f, payout)
    with (
        pytest.raises(psycopg.Error, match="immutable.*audit"),
        f["conn"].transaction(),
    ):
        f["conn"].execute(
            "SELECT set_config('accounting.loan_payout_accounting_post',%s,true)",
            (str(prep["id"]),),
        )
        entry = (
            f["conn"]
            .execute(
                "INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,description,source_type,source_reference,source_event_key,created_by_user_id) VALUES(%s,%s,'Synthetic manual bypass','treasury_loan_payout',%s,%s,%s) RETURNING id",
                (
                    f["period"],
                    prep["snapshot"]["posting_date"],
                    str(payout),
                    prep["snapshot"]["source_event_key"],
                    f["actor"].user_id,
                ),
            )
            .fetchone()["id"]
        )
        f["conn"].execute(
            "INSERT INTO accounting.journal_lines(journal_entry_id,line_number,account_id,description,debit,credit,client_id,loan_id) SELECT %s,x.line_number,x.account_id,'Synthetic exact lines without native audit',x.debit,x.credit,x.client_id,x.loan_id FROM accounting.loan_payout_accounting_preparations p CROSS JOIN LATERAL jsonb_to_recordset(p.snapshot->'lines') x(line_number INT,account_id UUID,debit NUMERIC,credit NUMERIC,client_id UUID,loan_id UUID) WHERE p.id=%s",
            (entry, prep["id"]),
        )
        f["conn"].execute(
            "SELECT accounting.post_journal_entry(%s,%s)", (entry, f["actor"].user_id)
        )
        f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
    assert balances(f) == {}


def test_unprivileged_role_has_no_raw_payout_accounting_surface(payout_accounting):
    f = payout_accounting
    role = "payout_probe_" + uuid4().hex
    f["conn"].execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
    for function in (
        "accounting.loan_payout_coordinates(uuid,text)",
        "accounting.post_loan_payout_accounting(uuid,text,text,uuid)",
        "accounting.loan_payout_accounting_origin(uuid,text)",
    ):
        assert (
            f["conn"]
            .execute(
                "SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed",
                (role, function),
            )
            .fetchone()["allowed"]
            is False
        )
    for table in (
        "loan_payout_accounting_preparations",
        "loan_payout_accounting_postings",
        "loan_payout_accounting_posting_status",
    ):
        assert (
            f["conn"]
            .execute(
                "SELECT has_table_privilege(%s,%s,'SELECT') AS allowed",
                (role, "accounting." + table),
            )
            .fetchone()["allowed"]
            is False
        )


def test_completed_payout_clears_only_exact_event_and_release_obligations(
    payout_accounting,
):
    f = payout_accounting
    prepared = actual(f, fee="0.00")
    payout = prepared["target_id"]
    event = (
        f["conn"]
        .execute("SELECT event_id FROM treasury.loan_payouts WHERE id=%s", (payout,))
        .fetchone()["event_id"]
    )
    assert (
        f["conn"]
        .execute(
            "SELECT 1 FROM accounting.period_initial_source_blockers(%s) WHERE source_type='treasury_event' AND source_id=%s",
            (f["period"], event),
        )
        .fetchone()
    )
    f["conn"].commit()
    post_stage(f, payout, "debit")
    assert (
        f["conn"]
        .execute(
            "SELECT 1 FROM accounting.period_initial_source_blockers(%s) WHERE source_type='treasury_event' AND source_id=%s",
            (f["period"], event),
        )
        .fetchone()
        is None
    )
    f["conn"].commit()
    confirm(f, payout)
    complete_borrower(f, prepared)
    release = (
        f["conn"]
        .execute(
            "SELECT disbursement_event_id FROM lending.first_loan_releases WHERE funding_payout_id=%s",
            (payout,),
        )
        .fetchone()["disbursement_event_id"]
    )
    assert (
        f["conn"]
        .execute(
            "SELECT 1 FROM accounting.period_legacy_source_blockers(%s) WHERE source_type='loan_disbursement' AND source_id=%s",
            (f["period"], release),
        )
        .fetchone()
    )
    post_stage(f, payout, "completion")
    assert (
        f["conn"]
        .execute(
            "SELECT 1 FROM accounting.period_legacy_source_blockers(%s) WHERE source_type='loan_disbursement' AND source_id=%s",
            (f["period"], release),
        )
        .fetchone()
        is None
    )
    with pytest.raises(psycopg.Error, match="payout|Payout"), f["conn"].transaction():
        f["conn"].execute(
            "INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,description,source_type,source_reference,source_event_key,created_by_user_id) SELECT %s,business_date,'Synthetic duplicate legacy cash','loan_disbursement',id::text,'loan_disbursement:'||id::text,%s FROM lending.loan_disbursement_events WHERE id=%s",
            (f["period"], f["actor"].user_id, release),
        )


def test_native_payout_cannot_be_manually_reversed(payout_accounting):
    f = payout_accounting
    payout = actual(f)["target_id"]
    entry = post_stage(f, payout, "debit")
    with (
        pytest.raises(psycopg.Error, match="reversal|Reversal"),
        f["conn"].transaction(),
    ):
        f["conn"].execute(
            "INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,description,source_type,reversal_of_entry_id,created_by_user_id) SELECT fiscal_period_id,posting_date,'Synthetic manual reversal','manual',id,%s FROM accounting.journal_entries WHERE id=%s",
            (f["actor"].user_id, entry),
        )
