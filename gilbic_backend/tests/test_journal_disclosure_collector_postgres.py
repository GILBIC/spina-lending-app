"""Credit settled from custody cash remains distinct from physical remittance."""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from collector_accounting_test_support import post, prepare
from gilbic_backend.financial_reporting import cash_flow_statement
from gilbic_backend.journal_disclosure_repository import read_journal_disclosures
from gilbic_backend.reporting_evidence_repository import read_internal_collector_cash
from psycopg.rows import dict_row, tuple_row
from psycopg.types.json import Jsonb
from test_collector_credit_application_postgres import _accept, _approve, _count
from test_collector_credit_application_postgres import (
    collector_accounting as _collector_accounting,
)
from test_collector_credit_application_postgres import (
    credit_application as _credit_application,
)
from test_journal_disclosure_postgres import financing_policy, retain
from test_reporting_policy_postgres import policy

collector_accounting = _collector_accounting
credit_application = _credit_application


@pytest.mark.parametrize(
    ("credit_application", "applied", "physical", "receipts", "closing"),
    [
        ("10.00", "4.00", "98.00", "212.00", "208.00"),
        ("100.00", "100.00", "0.00", "300.00", "200.00"),
    ],
    indirect=["credit_application"],
)
def test_approved_credit_is_a_custody_payment_without_a_second_cash_receipt(
    credit_application, applied, physical, receipts, closing
):
    f = credit_application
    conn = f["conn"]
    action = _approve(f, applied)
    acceptance = _accept(f, action, _count(f, action, physical))
    if Decimal(physical):
        post(f, prepare(f, "settlement", UUID(acceptance["settlement"]["id"])))
    application = post(
        f, prepare(f, "credit_application", UUID(acceptance["application_entry"]["id"]))
    )
    conn.row_factory = tuple_row
    evidence = f | {"actor": f["actor"].user_id}
    evidence["policy"] = policy(evidence)
    disclosure_policy = financing_policy(evidence, codes=[])
    conn.row_factory = dict_row
    with conn.cursor() as cursor:
        proofs = read_internal_collector_cash(cursor, f["period"])
    lines = conn.execute(
        "SELECT l.id AS journal_line_id,l.journal_entry_id,a.code AS account_code,"
        "l.debit-l.credit AS amount,j.source_type,j.entry_number FROM accounting.journal_lines l "
        "JOIN accounting.journal_entries j ON j.id=l.journal_entry_id "
        "JOIN accounting.accounts a ON a.id=l.account_id "
        "WHERE j.status='posted' AND j.fiscal_period_id=%s AND a.code IN('1010','1020','1030')",
        (f["period"],),
    ).fetchall()
    for line in lines:
        proof = proofs.get(line["journal_line_id"])
        principal = proof["internal_principal"] if proof else Decimal(0)
        external = line["amount"] - principal
        allocations = []
        if principal:
            allocations.append(
                {"category": "internal", "amount": format(principal, ".2f")}
            )
        if external:
            allocations.append(
                {"category": "operating", "amount": format(external, ".2f")}
            )
        line.update(allocations=allocations, collector_cash=proof)
        conn.execute(
            "SELECT accounting.retain_cash_flow_classification(%s,%s,%s,%s,%s)",
            (
                uuid4(),
                f["book"],
                evidence["policy"],
                Jsonb(
                    {
                        "journal_line_id": str(line["journal_line_id"]),
                        "expected_amount": format(line["amount"], ".2f"),
                        "expected_version": 0,
                        "allocations": allocations,
                        "reviewed": True,
                        "evidence_reference": "test:actual-custody-use",
                        "evidence_digest": "a" * 64,
                    }
                ),
                evidence["actor"],
            ),
        )
    result = cash_flow_statement(
        policy={"cash_definition_valid": True},
        opening_cash=Decimal(0),
        closing_cash=Decimal(closing),
        lines=lines,
    )
    assert result["reconciled"]
    assert result["categories"]["operating"] == {
        "receipts": receipts,
        "payments": applied,
        "net": closing,
    }
    with conn.cursor() as cursor:
        report = read_journal_disclosures(cursor, f["period"], evidence["actor"])
    journal = next(
        row for row in report["journals"] if row["journal_entry_id"] == str(application)
    )
    assert journal["source_status"] == "current"
    debit = next(row for row in journal["lines"] if row["account_code"] == "2220")
    credit = next(row for row in journal["lines"] if row["account_code"] == "1020")
    payload = {
        "journal_entry_id": str(application),
        "expected_version": 0,
        "source_digest": journal["source_digest"],
        "reviewed": True,
        "reason": "Collector credit paid using cash already held in custody.",
        "evidence_reference": "test:credit-approval",
        "evidence_digest": "b" * 64,
        "components": [
            {
                "debit_line_id": debit["id"],
                "credit_line_id": credit["id"],
                "classification": "cash_operating",
                "amount": applied,
                "evidence_reference": "test:credit-approval",
                "evidence_digest": "b" * 64,
            }
        ],
    }
    with conn.cursor(row_factory=tuple_row) as cursor:
        retain(evidence | {"conn": cursor}, disclosure_policy, payload)
    with conn.cursor() as cursor:
        report = read_journal_disclosures(cursor, f["period"], evidence["actor"])
    reviewed = next(
        row for row in report["journals"] if row["journal_entry_id"] == str(application)
    )
    assert reviewed["source_status"] == reviewed["review_status"] == "current"
    assert all(
        row["journal_entry_id"] != str(application)
        for row in report["noncash_components"]
    )
