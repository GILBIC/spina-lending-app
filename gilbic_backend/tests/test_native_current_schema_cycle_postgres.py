"""Combined native history, current cash application, statements and close.

The root runner restores the preserved synthetic October 5 origin. This test
adds supported facts and rolls them back; original source dates stay unchanged.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from gilbic_backend.financial_statements_api import _pack_payload
from gilbic_backend.financial_statements_repository import (
    PostgresFinancialStatementsRepository,
)
from psycopg.rows import dict_row, tuple_row
from psycopg.types.json import Jsonb
from test_native_regular_historical_postgres import (
    actual_first_application,
    money,
    post_prefix,
)
from test_native_regular_historical_postgres import (
    dated_native as _dated_native,
)
from test_reporting_policy_postgres import policy
from test_treasury_receipt_accounting_postgres import install
from test_v1_tax_liability_postgres import _post as post_tax_liability

dated_native = _dated_native


def synthetic_tax_rule(f, tax_type, day):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.record_v1_tax_rule_evidence(%s,%s,%s,%s,%s,NULL,'taxable',0.01,NULL,%s,%s,%s,%s,%s,NULL) AS id",
            (
                f["actor_id"],
                uuid4(),
                tax_type,
                "synthetic-native-" + uuid4().hex,
                day,
                "Explicit synthetic test policy; no real taxpayer or statutory rate asserted",
                "test:synthetic-native-tax-policy",
                "test:retained-native-tax-policy",
                "a" * 64,
                "Synthetic validation assumes a one-percent rate only to exercise the retained calculation and protected posting.",
            ),
        )
        .fetchone()["id"]
    )


def retain_native_dst(
    f, *, disbursement_event_id=None, principal=Decimal(1000), period_id=None
):
    conn = f["conn"]
    if disbursement_event_id is None:
        source = conn.execute(
            "SELECT d.id,l.due_date-l.date_released AS days FROM lending.first_loan_releases r "
            "JOIN lending.loan_disbursement_events d ON d.id=r.disbursement_event_id "
            "JOIN lending.loans l ON l.id=r.loan_id WHERE r.funding_payout_id=%s",
            (f["payout_id"],),
        ).fetchone()
    else:
        source = conn.execute(
            "SELECT d.id,l.due_date-l.date_released AS days FROM lending.loan_disbursement_events d "
            "JOIN lending.loans l ON l.id=d.loan_id WHERE d.id=%s AND d.loan_id=%s",
            (disbursement_event_id, f["loan_id"]),
        ).fetchone()
    due = money(principal * Decimal("0.01") * min(source["days"], 365) / 365)
    rule = synthetic_tax_rule(f, "documentary_stamp_tax", f["release_day"])
    evidence = conn.execute(
        "SELECT accounting.record_v1_dst_evidence(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL) AS id",
        (
            f["actor_id"],
            uuid4(),
            f["loan_id"],
            source["id"],
            rule,
            principal,
            source["days"],
            due,
            "test:preserved-native-debt-instrument",
            "b" * 64,
            "test:synthetic-native-dst-calculation",
            "c" * 64,
            "Exact captured principal and signed term under the explicitly synthetic one-percent test policy.",
        ),
    ).fetchone()["id"]
    conn.execute(
        "SELECT accounting.prepare_v1_tax_liability_journal(%s,%s,%s)",
        ("documentary_stamp_tax", evidence, f["actor_id"]),
    )
    digest = conn.execute(
        "SELECT calculation_digest AS evidence_digest FROM accounting.v1_dst_evidence WHERE id=%s",
        (evidence,),
    ).fetchone()["evidence_digest"]
    conn.row_factory = tuple_row
    try:
        arguments = {
            "tax_type": "documentary_stamp_tax",
            "evidence_id": evidence,
            "actor_id": f["actor_id"],
            "evidence_digest": digest,
            "tax_due": str(due),
            "expense_code": "5310",
            "posting_date": f["release_day"],
            "period_id": period_id or f["period_id"],
        }
        posted = post_tax_liability(conn, **arguments)
        assert post_tax_liability(conn, **arguments) == posted
    finally:
        conn.row_factory = dict_row
    return due


def retain_application_tax(f, period, application):
    conn = f["conn"]
    transaction = conn.execute(
        "SELECT p.transaction_id,t.amount FROM accounting.treasury_application_postings p "
        "JOIN lending.collection_transactions t ON t.id=p.transaction_id WHERE p.application_id=%s",
        (application,),
    ).fetchone()
    # Retain the contract allocation independently from the PFRS EIR split.
    taxable = money(
        conn.execute(
            "SELECT sum(a.amount_applied*i.interest_component/i.contractual_amount) AS amount "
            "FROM lending.loan_installment_payment_allocations a JOIN lending.loan_contract_installments i ON i.id=a.installment_id "
            "WHERE a.transaction_id=%s",
            (transaction["transaction_id"],),
        ).fetchone()["amount"]
    )
    due = money(taxable * Decimal("0.01"))
    rule = synthetic_tax_rule(f, "percentage_tax_lending", f["today"])
    evidence = conn.execute(
        "SELECT accounting.record_v1_percentage_tax_evidence(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL) AS id",
        (
            f["actor_id"],
            uuid4(),
            transaction["transaction_id"],
            rule,
            transaction["amount"],
            taxable,
            transaction["amount"] - taxable,
            due,
            "test:independent-contract-allocation",
            "d" * 64,
            "Synthetic test policy uses the allocated signed contractual interest, independently from accounting EIR.",
        ),
    ).fetchone()["id"]
    conn.execute(
        "SELECT accounting.prepare_v1_tax_liability_journal(%s,%s,%s)",
        ("percentage_tax_lending", evidence, f["actor_id"]),
    )
    digest = conn.execute(
        "SELECT allocation_digest AS evidence_digest FROM accounting.v1_percentage_tax_evidence WHERE id=%s",
        (evidence,),
    ).fetchone()["evidence_digest"]
    conn.row_factory = tuple_row
    try:
        arguments = {
            "tax_type": "percentage_tax_lending",
            "evidence_id": evidence,
            "actor_id": f["actor_id"],
            "evidence_digest": digest,
            "tax_due": str(due),
            "expense_code": "5300",
            "posting_date": f["today"],
            "period_id": period,
        }
        posted = post_tax_liability(conn, **arguments)
        assert post_tax_liability(conn, **arguments) == posted
    finally:
        conn.row_factory = dict_row
    return due


def assess_current_cash_cutoff(f, period):
    conn, cutoff = f["conn"], f["today"]
    source = conn.execute(
        "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS value",
        (period, f["loan_id"]),
    ).fetchone()["value"]
    assert source["ready"], source["blockers"]
    assert Decimal(str(source["eir"]["incremental_interest"])) == 0
    flows = [
        {
            "cash_date": row["due_date"],
            "amount": str(money(Decimal(str(row["remaining_amount"])))),
        }
        for row in source["snapshot"]["contractual_cash_flows"]
        if Decimal(str(row["remaining_amount"])) > 0
    ]
    assert flows and all(
        date.fromisoformat(row["cash_date"]) >= cutoff for row in flows
    )
    evidence = conn.execute(
        "SELECT accounting.record_ecl_forward_looking_evidence(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL) AS id",
        (
            "native-current-" + uuid4().hex,
            "Synthetic current forecast publication",
            "Explicit synthetic retained source",
            cutoff - timedelta(days=30),
            cutoff,
            cutoff,
            cutoff + timedelta(days=180),
            datetime.now(timezone.utc),
            cutoff,
            "Current synthetic scenario assumes the outstanding signed installments are received on their original dates.",
            f["actor_id"],
        ),
    ).fetchone()["id"]
    risk = {
        "as_of_date": cutoff.isoformat(),
        "stage_label": "stage_1_12_month",
        "default_label": False,
        "write_off_label": "none",
        "recovery_label": "none",
        "primary_evidence_basis": "contractual_dpd",
        "evidence_reference": "test:current-native-signed-schedule",
        "review_note": "Current protected cash and remaining signed installments were explicitly reviewed.",
    }
    scenarios = [
        {
            "scenario_key": name,
            "probability": probability,
            "evidence_reference": "test:current-native-" + name,
            "management_rationale": "Synthetic scenario retains the remaining signed dates and exact unpaid amounts.",
            "forward_evidence_ids": [str(evidence)],
            "expected_cash_flows": flows,
        }
        for name, probability in (("base", "0.7"), ("alternative", "0.3"))
    ]
    preparation = conn.execute(
        "SELECT accounting.prepare_elapsed_loan_period_assessment(%s,%s,%s,%s,%s,%s,%s) AS id",
        (
            period,
            f["loan_id"],
            f["actor_id"],
            source["source_digest"],
            Jsonb(risk),
            Jsonb(scenarios),
            "Current cash is recognized once, and remaining signed contractual flows form explicit synthetic scenario inputs.",
        ),
    ).fetchone()["id"]
    reviewed = conn.execute(
        "SELECT confirmation_digest,measurement_snapshot FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
        (preparation,),
    ).fetchone()
    assert Decimal(str(reviewed["measurement_snapshot"]["ecl_amount"])) == 0
    query = "SELECT accounting.post_elapsed_loan_period_assessment(%s,%s,%s) AS id"
    args = (preparation, f["actor_id"], reviewed["confirmation_digest"])
    audit = conn.execute(query, args).fetchone()["id"]
    assert conn.execute(query, args).fetchone()["id"] == audit
    return source


def close_period(f, period):
    conn = f["conn"]
    blockers = conn.execute(
        "SELECT * FROM accounting.period_source_blockers(%s)", (period,)
    ).fetchall()
    assert blockers == [], blockers
    assert (
        conn.execute(
            "SELECT accounting.set_fiscal_period_status(%s,'review',%s) AS status",
            (period, f["actor_id"]),
        ).fetchone()["status"]
        == "review"
    )
    prepare_sql = "SELECT accounting.prepare_period_close(%s,%s) AS id"
    prepared = conn.execute(prepare_sql, (period, f["actor_id"])).fetchone()["id"]
    assert (
        conn.execute(prepare_sql, (period, f["actor_id"])).fetchone()["id"] == prepared
    )
    confirmation = conn.execute(
        "SELECT p.close_digest,p.net_income,f.end_date FROM accounting.period_close_preparations p "
        "JOIN accounting.fiscal_periods f ON f.id=p.fiscal_period_id WHERE p.id=%s",
        (prepared,),
    ).fetchone()
    query = "SELECT accounting.post_period_close(%s,%s,%s,%s,%s,'3100',%s,'period_close_retained_earnings_v1') AS id"
    args = (
        period,
        f["actor_id"],
        uuid4().hex * 2,
        confirmation["close_digest"],
        confirmation["net_income"],
        confirmation["end_date"],
    )
    with pytest.raises(psycopg.Error), conn.transaction():
        conn.execute(query, args[:4] + (confirmation["net_income"] + 1,) + args[5:])
    posted = conn.execute(query, args).fetchone()["id"]
    assert conn.execute(query, args).fetchone()["id"] == posted
    assert (
        conn.execute(
            "SELECT count(*) AS n FROM accounting.period_close_postings WHERE fiscal_period_id=%s",
            (period,),
        ).fetchone()["n"]
        == 1
    )
    assert (
        conn.execute(
            "SELECT status FROM accounting.fiscal_periods WHERE id=%s", (period,)
        ).fetchone()["status"]
        == "closed"
    )
    return confirmation


def retained_cash_policy(f, period):
    conn = f["conn"]
    book = conn.execute(
        "SELECT id FROM accounting.book_identity WHERE singleton"
    ).fetchone()["id"]
    conn.row_factory = tuple_row
    try:
        selected = policy(f | {"book": book, "period": period, "actor": f["actor_id"]})
    finally:
        conn.row_factory = dict_row
    cash = conn.execute(
        "SELECT l.id,l.debit-l.credit AS amount FROM accounting.journal_entries j "
        "JOIN accounting.journal_lines l ON l.journal_entry_id=j.id "
        "JOIN accounting.accounts a ON a.id=l.account_id WHERE j.status='posted' "
        "AND j.fiscal_period_id=%s AND a.code IN('1010','1020','1030')",
        (period,),
    ).fetchall()
    for line in cash:
        conn.execute(
            "SELECT accounting.retain_cash_flow_classification(%s,%s,%s,%s,%s)",
            (
                uuid4(),
                book,
                selected,
                Jsonb(
                    {
                        "journal_line_id": str(line["id"]),
                        "expected_amount": str(line["amount"]),
                        "expected_version": 0,
                        "allocations": [
                            {"category": "operating", "amount": str(line["amount"])}
                        ],
                        "evidence_reference": "test:preserved-native-lending-cash",
                        "evidence_digest": "c" * 64,
                        "reviewed": True,
                    }
                ),
                f["actor_id"],
            ),
        )


def report(f, period):
    with f["conn"].cursor(row_factory=dict_row) as cursor:
        return _pack_payload(
            PostgresFinancialStatementsRepository().read_statement_pack(
                cursor,
                period_id=period,
                actor_user_id=f["actor_id"],
            )
        )


def post_application(f, application):
    conn = f["conn"]
    source = conn.execute(
        "SELECT accounting.treasury_application_coordinates(%s) AS value",
        (application,),
    ).fetchone()["value"]
    prepared = conn.execute(
        "SELECT accounting.prepare_treasury_application(%s,%s,%s,%s) AS id",
        (application, source["source_digest"], uuid4(), f["actor_id"]),
    ).fetchone()["id"]
    confirmation = conn.execute(
        "SELECT source_digest,confirmation_token FROM accounting.treasury_application_preparations WHERE id=%s",
        (prepared,),
    ).fetchone()
    query = "SELECT accounting.post_treasury_application(%s,%s,%s,%s) AS id"
    args = (
        prepared,
        confirmation["source_digest"],
        confirmation["confirmation_token"],
        f["actor_id"],
    )
    journal = conn.execute(query, args).fetchone()["id"]
    assert conn.execute(query, args).fetchone()["id"] == journal
    return source, journal


def test_native_tax_admission_requires_protected_claim_and_exact_chart(dated_native):
    f = dated_native
    conn = f["conn"]
    retain_native_dst(f)
    posted = conn.execute(
        "SELECT p.journal_entry_id FROM accounting.v1_tax_liability_preparations p "
        "JOIN accounting.v1_dst_evidence e ON e.id=p.evidence_id WHERE e.loan_id=%s",
        (f["loan_id"],),
    ).fetchone()["journal_entry_id"]
    assert conn.execute(
        "SELECT accounting.native_loan_ancillary_tax_exact(%s,%s) AS exact",
        (posted, f["loan_id"]),
    ).fetchone()["exact"]
    with pytest.raises(RuntimeError), conn.transaction():
        conn.execute("UPDATE accounting.accounts SET code='5311' WHERE code='5310'")
        assert not conn.execute(
            "SELECT accounting.native_loan_ancillary_tax_exact(%s,%s) AS exact",
            (posted, f["loan_id"]),
        ).fetchone()["exact"]
        assert not conn.execute(
            "SELECT accounting.regular_original_origin(%s,%s) AS value",
            (f["loan_id"], f["cutoff"]),
        ).fetchone()["value"]["ready"]
        raise RuntimeError("Rollback the synthetic chart mutation")
    journal = conn.execute(
        "INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,description,source_type,created_by_user_id) "
        "VALUES(%s,%s,'Synthetic unclaimed tax-looking journal','manual',%s) RETURNING id",
        (f["period_id"], f["release_day"], f["actor_id"]),
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO accounting.journal_lines(journal_entry_id,line_number,account_id,debit,credit,loan_id,client_id) "
        "SELECT %s,x.n,a.id,x.dr,x.cr,%s,%s FROM (VALUES(1,'5310',1,0),(2,'2100',0,1)) x(n,code,dr,cr) "
        "JOIN accounting.accounts a ON a.code=x.code",
        (journal, f["loan_id"], f["client_id"]),
    )
    conn.execute(
        "SELECT accounting.post_journal_entry(%s,%s)", (journal, f["actor_id"])
    )
    assert not conn.execute(
        "SELECT accounting.native_loan_ancillary_tax_exact(%s,%s) AS exact",
        (journal, f["loan_id"]),
    ).fetchone()["exact"]
    source = conn.execute(
        "SELECT accounting.regular_original_origin(%s,%s) AS value",
        (f["loan_id"], f["cutoff"]),
    ).fetchone()["value"]
    assert not source["ready"]
    assert "unrecognized_original_loan_control_journal" in source["blockers"]


def test_preserved_native_prefix_close_then_actual_receipt_application_and_reports(
    dated_native,
    monkeypatch,
    tmp_path,
):
    f = dated_native
    conn = f["conn"]
    # The imported historical fixture replays the native origin extension.
    # Restore its following chronological dispatcher in this same transaction.
    install(
        conn,
        Path(__file__).resolve().parents[1]
        / "sql/0165_add_regular_chronological_cash.sql",
    )
    assert conn.execute(
        "SELECT to_regprocedure('accounting.prepare_period_close_before_bounded_admission(uuid,uuid)') IS NOT NULL AS installed"
    ).fetchone()["installed"], (
        "The restored native fixture must include current close admission"
    )
    original = conn.execute(
        "SELECT to_jsonb(l) AS loan FROM lending.loans l WHERE id=%s", (f["loan_id"],)
    ).fetchone()["loan"]
    # Product configuration is part of the retained financial source. Complete
    # this setup before review; the later actual cash workflow must not change it.
    conn.execute(
        "UPDATE lending.loan_types SET settings=settings||%s "
        "WHERE id=(SELECT loan_type_id FROM lending.loans WHERE id=%s)",
        (
            Jsonb(
                {
                    "mobile_collections_enabled": True,
                    "mobile_balance_mode": "direct_remaining_balance",
                    "mobile_contract_schedule_allocation_enabled": True,
                }
            ),
            f["loan_id"],
        ),
    )
    post_prefix(f)
    dst = retain_native_dst(f)
    assert conn.execute(
        "SELECT accounting.period_elapsed_loan_assessment_exact(%s,%s) AS exact",
        (f["period_id"], f["loan_id"]),
    ).fetchone()["exact"], (
        "A separate exact protected tax expense must preserve the loan measurement"
    )
    retained_cash_policy(f, f["period_id"])
    prefix_close = close_period(f, f["period_id"])
    with localcontext() as context:
        context.prec = 50
        prefix_interest = money(
            Decimal(1000)
            * ((1 + f["rate"]) ** (f["cutoff"] - f["release_day"]).days - 1)
        )
        current_interest = money(
            Decimal(1000)
            * ((1 + f["rate"]) ** (f["today"] - f["release_day"]).days - 1)
        )
    # The preserved provider debit includes its separately evidenced PHP2 fee.
    assert prefix_close["net_income"] == prefix_interest - Decimal(2) - dst
    prefix_report = report(f, f["period_id"])
    assert prefix_report["financial_position"]["balanced"]
    assert (
        prefix_report["reporting_supplement"]["cash_flows"]["closing_cash"]
        == "-1002.00"
    )
    current = conn.execute(
        "INSERT INTO accounting.fiscal_periods(label,start_date,end_date,status) VALUES(%s,%s,%s,'open') RETURNING id",
        (
            "Native combined current " + uuid4().hex,
            f["cutoff"] + timedelta(days=1),
            f["today"],
        ),
    ).fetchone()["id"]
    applied = actual_first_application(f, monkeypatch, tmp_path)
    source, _ = post_application(f, applied["application_id"])
    assert (
        Decimal(source["measurement"]["incremental_interest"])
        == current_interest - prefix_interest
    )
    assert not {"1010", "1020", "1030", "1050"}.intersection(
        line["account_code"] for line in source["lines"]
    )
    percentage_tax = retain_application_tax(f, current, applied["application_id"])
    assess_current_cash_cutoff(f, current)
    retained_cash_policy(f, current)
    current_close = close_period(f, current)
    assert (
        current_close["net_income"]
        == current_interest - prefix_interest - percentage_tax
    )
    current_report = report(f, current)
    assert current_report["financial_position"]["balanced"]
    cash = current_report["reporting_supplement"]["cash_flows"]
    assert cash["opening_cash"] == "-1002.00"
    assert Decimal(cash["closing_cash"]) == applied["receipt_amount"] - 1002
    assert cash["reconciled"]
    assert (
        conn.execute(
            "SELECT count(*) AS n FROM treasury.events WHERE account_id=%s",
            (applied["wallet_id"],),
        ).fetchone()["n"]
        == 1
    )
    assert conn.execute(
        "SELECT sum(l.credit-l.debit) AS amount FROM accounting.journal_entries j "
        "JOIN accounting.journal_lines l ON l.journal_entry_id=j.id JOIN accounting.accounts a ON a.id=l.account_id "
        "WHERE j.status='posted' AND a.code='2200' AND l.client_id=%s",
        (f["client_id"],),
    ).fetchone()["amount"] == Decimal(50)
    assert conn.execute(
        "SELECT date_released,due_date FROM lending.loans WHERE id=%s", (f["loan_id"],)
    ).fetchone() == {
        key: date.fromisoformat(original[key]) for key in ("date_released", "due_date")
    }
    assert conn.execute(
        "SELECT accounting.period_elapsed_loan_assessment_exact(%s,%s) AS exact",
        (f["period_id"], f["loan_id"]),
    ).fetchone()["exact"]
    historical_review = conn.execute(
        "SELECT accounting.period_review_manifest_state(%s) AS value", (f["period_id"],)
    ).fetchone()["value"]
    assert historical_review["current"], historical_review
    with pytest.raises(RuntimeError), conn.transaction():
        conn.execute(
            "UPDATE lending.loan_types SET settings=settings||%s "
            "WHERE id=(SELECT loan_type_id FROM lending.loans WHERE id=%s)",
            (
                Jsonb({"mobile_contract_schedule_allocation_enabled": False}),
                f["loan_id"],
            ),
        )
        changed = conn.execute(
            "SELECT accounting.period_review_manifest_state(%s) AS value",
            (f["period_id"],),
        ).fetchone()["value"]
        assert not changed["current"], (
            "Changed retained product policy must remain visible"
        )
        raise RuntimeError("Rollback the synthetic policy change")
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
