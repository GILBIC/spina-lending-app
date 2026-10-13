"""Exercise genuine dated native sources restored from the October5 capture.

The runner restores a task-owned synthetic dump and sets the manifest path.
No loan, contract, payout, source event or retained audit timestamp is rewritten.
Each test rolls back its added review/accounting facts.
"""

import json
import os
from contextlib import nullcontext
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, localcontext
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from gilbic_backend.account_repository import AccountContext
from gilbic_backend.contract_collection_activation_repository import (
    PostgresContractCollectionActivationRepository,
)
from gilbic_backend.contract_collection_posting import CONTRACT_ALLOCATION_SETTING
from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore
from gilbic_backend.treasury_claims import claim_action, put_evidence
from gilbic_backend.treasury_models import (
    AllocationPreview,
    ReceiptApply,
    ReceiptVerify,
)
from gilbic_backend.treasury_repository import TreasuryService
from psycopg.rows import dict_row, tuple_row
from psycopg.types.json import Jsonb
from test_native_payout_regular_origin_postgres import _independent_rate
from test_source_close_guard_postgres import _connect
from test_treasury_receipt_accounting_postgres import install, mapping, post, prepare
from treasury_test_support import PDF, grant_live

from gilbic_backend import contract_collection_activation_repository as activation
from gilbic_backend import treasury_collection_posting as allocation

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql/0163_add_native_regular_assessment_integration.sql"
)


@pytest.fixture
def dated_native():
    if not os.getenv("GILBIC_TEST_DATABASE_URL"):
        pytest.skip("Requires the dedicated restored native history database")
    path = os.getenv("SPINA_NATIVE_HISTORY_MANIFEST")
    assert path, "Restore the synthetic native capture and provide its manifest"
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    with _connect() as conn:
        conn.row_factory = dict_row
        try:
            if MIGRATION.exists() and os.getenv("SPINA_NATIVE_BASELINE") != "1":
                install(conn, MIGRATION)
            f = {
                "conn": conn,
                **{
                    key: UUID(manifest[key])
                    for key in (
                        "loan_id",
                        "client_id",
                        "payout_id",
                        "period_id",
                        "actor_id",
                        "device_id",
                        "wallet_id",
                        "debit_journal_id",
                        "completion_journal_id",
                    )
                },
                "release_day": date.fromisoformat(manifest["release_date"]),
                "cutoff": date.fromisoformat(manifest["earliest_elapsed_cutoff"]),
            }
            f["today"] = conn.execute(
                "SELECT (clock_timestamp() AT TIME ZONE 'Asia/Manila')::date AS day"
            ).fetchone()["day"]
            assert f["release_day"] < f["cutoff"] <= f["today"]
            assert conn.execute(
                "SELECT status FROM treasury.loan_payouts WHERE id=%s",
                (f["payout_id"],),
            ).fetchone() == {"status": "completed"}
            conn.execute(
                "UPDATE accounting.fiscal_periods SET end_date=%s WHERE id=%s",
                (f["cutoff"], f["period_id"]),
            )
            f["installments"] = conn.execute(
                "SELECT i.due_date,i.contractual_amount FROM lending.first_loan_releases r "
                "JOIN lending.loan_contract_installments i ON i.schedule_id=r.schedule_id "
                "WHERE r.funding_payout_id=%s ORDER BY i.installment_number",
                (f["payout_id"],),
            ).fetchall()
            f["rate"] = _independent_rate(
                {"date_released": f["release_day"]}, f["installments"]
            )
            yield f
        finally:
            conn.rollback()


def candidate(f):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS value",
            (f["period_id"], f["loan_id"]),
        )
        .fetchone()["value"]
    )


def test_only_implicit_historical_paper_scan_matches_the_current_capture_default(
    dated_native,
):
    conn = dated_native["conn"]
    original = {
        "office_evidence": {"id": "retained-evidence", "sha256": "retained-hash"}
    }
    current = {
        "office_evidence": original["office_evidence"]
        | {"capture_method": "paper_scan"}
    }

    def matches(left, right):
        return conn.execute(
            "SELECT accounting.loan_payout_origin_matches(%s,%s) AS matches",
            (Jsonb(left), Jsonb(right)),
        ).fetchone()["matches"]

    assert matches(current, original)
    assert matches(current, current)
    assert not matches(original, current)
    assert not matches(
        {
            "office_evidence": current["office_evidence"]
            | {"capture_method": "screen_signature"}
        },
        original,
    )
    assert not matches(
        {"office_evidence": current["office_evidence"] | {"sha256": "changed-hash"}},
        original,
    )
    assert conn.execute(
        "SELECT bool_and(exact_posted AND NOT correction_pending) AS exact "
        "FROM accounting.loan_payout_accounting_posting_status WHERE payout_id=%s",
        (dated_native["payout_id"],),
    ).fetchone()["exact"]


def money(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def post_prefix(f):
    conn = f["conn"]
    source = candidate(f)
    assert source["ready"], source["blockers"]
    evidence = conn.execute(
        "SELECT accounting.record_ecl_forward_looking_evidence("
        "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL) AS id",
        (
            "native-history-" + uuid4().hex,
            "Synthetic retained native economic publication",
            "Native historical forecast evidence",
            f["cutoff"] - timedelta(days=30),
            f["cutoff"] - timedelta(days=1),
            f["cutoff"],
            f["cutoff"] + timedelta(days=180),
            datetime.combine(
                f["cutoff"], time(10), tzinfo=timezone(timedelta(hours=8))
            ),
            f["cutoff"],
            "Synthetic published inputs available at the actual historical cutoff.",
            f["actor_id"],
        ),
    ).fetchone()["id"]
    risk = {
        "as_of_date": f["cutoff"].isoformat(),
        "stage_label": "stage_1_12_month",
        "default_label": False,
        "write_off_label": "none",
        "recovery_label": "none",
        "primary_evidence_basis": "contractual_dpd",
        "evidence_reference": "Captured native signed contract",
        "review_note": "Original contractual conditions and dated forecasts reviewed.",
    }
    scenarios = [
        {
            "scenario_key": name,
            "probability": probability,
            "evidence_reference": "Synthetic " + name + " retained forecast",
            "management_rationale": "Explicit historical scenario from the dated native contract.",
            "forward_evidence_ids": [str(evidence)],
            "expected_cash_flows": [
                {
                    "cash_date": item["due_date"].isoformat(),
                    "amount": str(item["contractual_amount"]),
                }
                for item in f["installments"]
            ],
        }
        for name, probability in (("base", "0.7"), ("downside", "0.3"))
    ]
    preparation = conn.execute(
        "SELECT accounting.prepare_elapsed_loan_period_assessment(%s,%s,%s,%s,%s,%s,%s) AS id",
        (
            f["period_id"],
            f["loan_id"],
            f["actor_id"],
            source["source_digest"],
            Jsonb(risk),
            Jsonb(scenarios),
            "Review retained native completion and original signed contract without altering origin dates.",
        ),
    ).fetchone()["id"]
    digest = conn.execute(
        "SELECT confirmation_digest FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
        (preparation,),
    ).fetchone()["confirmation_digest"]
    audit = conn.execute(
        "SELECT accounting.post_elapsed_loan_period_assessment(%s,%s,%s) AS id",
        (preparation, f["actor_id"], digest),
    ).fetchone()["id"]
    return preparation, digest, audit


def test_captured_native_completion_produces_elapsed_interest_without_second_cash(
    dated_native,
):
    f = dated_native
    source = candidate(f)
    assert source["ready"], source["blockers"]
    with localcontext() as context:
        context.prec = 50
        expected = money(
            Decimal(1000)
            * ((1 + f["rate"]) ** (f["cutoff"] - f["release_day"]).days - 1)
        )
    assert Decimal(str(source["eir"]["cumulative_interest"])) == expected
    assert source["snapshot"]["anchor"]["journal_entry_id"] == str(
        f["completion_journal_id"]
    )
    assert source["snapshot"]["native_origin"]["snapshot"]["debit_proof"][
        "journal_entry_id"
    ] == str(f["debit_journal_id"])

    preparation, digest, audit = post_prefix(f)

    assert (
        f["conn"]
        .execute(
            "SELECT accounting.post_elapsed_loan_period_assessment(%s,%s,%s) AS id",
            (preparation, f["actor_id"], digest),
        )
        .fetchone()["id"]
        == audit
    )
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
    balances = (
        f["conn"]
        .execute(
            "SELECT a.code,sum(l.debit-l.credit) AS balance FROM accounting.journal_entries j "
            "JOIN accounting.journal_lines l ON l.journal_entry_id=j.id "
            "JOIN accounting.accounts a ON a.id=l.account_id WHERE j.status='posted' "
            "AND a.code IN('1030','1050','1100','1120','5240') GROUP BY a.code"
        )
        .fetchall()
    )
    fee = (
        f["conn"]
        .execute(
            "SELECT fee FROM accounting.loan_payout_accounting_postings WHERE payout_id=%s AND stage='debit'",
            (f["payout_id"],),
        )
        .fetchone()["fee"]
    )
    assert fee == Decimal("2.00")  # The capture retained an actual separate fee.
    assert {row["code"]: row["balance"] for row in balances} == {
        "1030": -Decimal(1000) - fee,
        "1050": Decimal(0),
        "1100": Decimal(1000),
        "1120": expected,
        "5240": fee,
    }
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM accounting.loan_disbursement_journal_postings WHERE loan_id=%s",
            (f["loan_id"],),
        )
        .fetchone()["n"]
        == 0
    )


def test_unknown_post_origin_transit_pair_does_not_net_away(dated_native):
    f = dated_native
    assert candidate(f)["ready"]
    for debit, credit in ((1, 0), (0, 1)):
        journal = (
            f["conn"]
            .execute(
                "INSERT INTO accounting.journal_entries(fiscal_period_id,posting_date,description,source_type,created_by_user_id) "
                "VALUES(%s,%s,'Synthetic unexplained post-origin transit','manual',%s) RETURNING id",
                (f["period_id"], f["cutoff"], f["actor_id"]),
            )
            .fetchone()["id"]
        )
        f["conn"].execute(
            "INSERT INTO accounting.journal_lines(journal_entry_id,line_number,account_id,debit,credit,loan_id,client_id) "
            "SELECT %s,x.n,a.id,x.dr,x.cr,%s,%s FROM "
            "(VALUES(1,'1050',%s::numeric,%s::numeric),(2,'1030',%s::numeric,%s::numeric)) x(n,code,dr,cr) "
            "JOIN accounting.accounts a ON a.code=x.code",
            (journal, f["loan_id"], f["client_id"], debit, credit, credit, debit),
        )
        f["conn"].execute(
            "SELECT accounting.post_journal_entry(%s,%s)", (journal, f["actor_id"])
        )
    source = candidate(f)
    assert not source["ready"]
    assert "unrecognized_loan_control_journal" in source["blockers"]


def actual_first_application(
    f, monkeypatch, tmp_path, *, amount_override=None, captured_reconciliation=True
):
    """Record a real receipt and first protected collection on the real current day."""
    conn = f["conn"]
    assert f["release_day"] <= f["today"]
    conn.execute(
        "UPDATE lending.loan_types SET settings=settings||%s "
        "WHERE id=(SELECT loan_type_id FROM lending.loans WHERE id=%s)",
        (
            Jsonb(
                {
                    "mobile_collections_enabled": True,
                    "mobile_balance_mode": "direct_remaining_balance",
                    CONTRACT_ALLOCATION_SETTING: True,
                }
            ),
            f["loan_id"],
        ),
    )
    conn.execute(
        "INSERT INTO lending.loan_schedule_operational_state(schedule_id,operational_version,updated_by_user_id) "
        "SELECT r.schedule_id,0,%s FROM lending.first_loan_releases r WHERE r.funding_payout_id=%s "
        "ON CONFLICT(schedule_id) DO NOTHING",
        (f["actor_id"], f["payout_id"]),
    )
    monkeypatch.setattr(activation, "open_connection", lambda: nullcontext(conn))
    conn.row_factory = tuple_row
    try:
        repository = PostgresContractCollectionActivationRepository()
        activated = repository.get_preview(loan_id=f["loan_id"])
        if not activated.active_for_current_schedule:
            activated = repository.activate(
                loan_id=f["loan_id"],
                acted_by_user_id=f["actor_id"],
                activation_note="Captured native signed schedule reconciled for actual current collection.",
            )
    finally:
        conn.row_factory = dict_row
    assert activated.active_for_current_schedule and activated.balance_reconciled
    reconciliation = conn.execute(
        "SELECT reconciliation_metadata FROM lending.loan_contract_collection_activation_events "
        "WHERE loan_id=%s AND event_action='activate' ORDER BY acted_at DESC LIMIT 1",
        (f["loan_id"],),
    ).fetchone()["reconciliation_metadata"]
    if captured_reconciliation:
        assert reconciliation["before"]["is_reconciled"] is False
        assert reconciliation["after_is_reconciled"] is True
        assert Decimal(str(reconciliation["unchanged_remaining_balance"])) == Decimal(
            "1200.00"
        )
    else:
        assert reconciliation == {}
    permissions = (
        "treasury.view",
        "treasury.account.manage",
        "treasury.receipt.verify",
        "treasury.payment.apply",
        "accounting.journal.manage",
    )
    grant_live(conn, f["actor_id"], *permissions)
    actor = AccountContext(
        f["actor_id"],
        f["actor_id"],
        "synthetic",
        None,
        "Synthetic captured native manager",
        "active",
        ("management",),
        permissions,
        True,
        f["device_id"],
    )
    context, wallet = uuid4(), uuid4()
    conn.execute(
        "INSERT INTO treasury.contexts(id,kind,created_by) VALUES(%s,'synthetic',%s)",
        (context, f["actor_id"]),
    )
    conn.execute(
        "INSERT INTO treasury.accounts(id,ledger_context_id,kind,alias,ownership,custodian_user_id) "
        "VALUES(%s,%s,'gcash','Synthetic current receiving wallet','synthetic',%s)",
        (wallet, context, f["actor_id"]),
    )
    conn.execute(
        "INSERT INTO treasury.account_access(account_id,user_id,permissions,private_history,granted_by) "
        "VALUES(%s,%s,%s,true,%s)",
        (wallet, f["actor_id"], list(permissions[:4]), f["actor_id"]),
    )
    service = TreasuryService(
        store=PrivateEvidenceStore(tmp_path / "native-receiving-private")
    )
    account = conn.execute(
        "SELECT * FROM treasury.accounts WHERE id=%s", (wallet,)
    ).fetchone()
    evidence = put_evidence(
        service, conn, actor, account, uuid4(), "recipient", PDF, "application/pdf"
    )
    # Clear actual outstanding due first. Advance remains subject to the
    # operational Past Due guard and is used only after due is fully settled.
    due = conn.execute(
        "SELECT due_unpaid_amount FROM accounting.loan_contract_dpd_assessment WHERE loan_id=%s",
        (f["loan_id"],),
    ).fetchone()["due_unpaid_amount"]
    amount = amount_override or due or Decimal("100.00")
    receipt_amount = amount + Decimal("50.00")
    receipt, _, _, _ = claim_action(
        service,
        conn,
        actor,
        account,
        ReceiptVerify(
            action="receipt_verify",
            request_id=uuid4(),
            account_id=wallet,
            expected_version=account["version"],
            client_id=f["client_id"],
            amount=str(receipt_amount),
            provider="gcash",
            reference=uuid4().hex,
            effective_at=datetime.now(timezone.utc),
            evidence_id=evidence["id"],
            recipient_attestation="Actual synthetic receiving wallet credit independently evidenced.",
        ),
    )
    posting_fixture = f | {"actor": actor, "wallet": wallet, "receipt": receipt}
    receipt_journal = post(
        posting_fixture, prepare(posting_fixture, mapping(posting_fixture))
    )
    receipt_row = conn.execute(
        "SELECT * FROM treasury.receipts WHERE id=%s", (receipt,)
    ).fetchone()
    version = conn.execute(
        "SELECT state_version FROM lending.loan_collection_state WHERE loan_id=%s",
        (f["loan_id"],),
    ).fetchone()["state_version"]
    inputs = {
        "mode": "single",
        "total_amount": f"{amount:.2f}",
        "loans": [{"loan_id": f["loan_id"], "expected_version": version}],
        "effective_date": f["today"],
        "expected_version": receipt_row["version"],
        "intent": "scheduled" if amount <= due else "extra_as_advance",
    }
    preview = allocation.preview_allocation(
        conn, actor, receipt_row, AllocationPreview(**inputs)
    )
    assert preview["can_apply"], preview
    account = conn.execute(
        "SELECT * FROM treasury.accounts WHERE id=%s", (wallet,)
    ).fetchone()
    _, _, result, _ = claim_action(
        service,
        conn,
        actor,
        account,
        ReceiptApply(
            **inputs,
            action="receipt_apply",
            request_id=uuid4(),
            account_id=wallet,
            receipt_id=receipt,
            digest=preview["digest"],
        ),
    )
    return {
        "application_id": UUID(result["application_id"]),
        "receipt_id": receipt,
        "receipt_journal_id": receipt_journal,
        "wallet_id": wallet,
        "amount": amount,
        "receipt_amount": receipt_amount,
        "actor": actor,
        "service": service,
    }


def test_captured_native_first_application_uses_original_eir_and_already_posted_cash(
    dated_native,
    monkeypatch,
    tmp_path,
):
    f = dated_native
    post_prefix(f)
    f["application_period_id"] = (
        f["conn"]
        .execute(
            "INSERT INTO accounting.fiscal_periods(label,start_date,end_date,status) VALUES(%s,%s,%s,'open') RETURNING id",
            (
                "Native first application " + uuid4().hex,
                f["cutoff"] + timedelta(days=1),
                f["today"],
            ),
        )
        .fetchone()["id"]
    )
    applied = actual_first_application(f, monkeypatch, tmp_path)
    source = (
        f["conn"]
        .execute(
            "SELECT accounting.treasury_application_coordinates(%s) AS source",
            (applied["application_id"],),
        )
        .fetchone()["source"]
    )
    with localcontext() as context:
        context.prec = 50
        cumulative = money(
            Decimal(1000)
            * ((1 + f["rate"]) ** (f["today"] - f["release_day"]).days - 1)
        )
        prior = money(
            Decimal(1000)
            * ((1 + f["rate"]) ** (f["cutoff"] - f["release_day"]).days - 1)
        )
    assert source["origin"]["native_origin"]["ready"]
    assert Decimal(source["measurement"]["cumulative_interest"]) == cumulative
    assert Decimal(source["measurement"]["incremental_interest"]) == cumulative - prior
    assert not {"1010", "1020", "1030", "1050"}.intersection(
        line["account_code"] for line in source["lines"]
    )
    prepared = (
        f["conn"]
        .execute(
            "SELECT accounting.prepare_treasury_application(%s,%s,%s,%s) AS id",
            (
                applied["application_id"],
                source["source_digest"],
                uuid4(),
                f["actor_id"],
            ),
        )
        .fetchone()["id"]
    )
    preparation = (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.treasury_application_preparations WHERE id=%s",
            (prepared,),
        )
        .fetchone()
    )
    params = (
        prepared,
        preparation["source_digest"],
        preparation["confirmation_token"],
        f["actor_id"],
    )
    query = "SELECT accounting.post_treasury_application(%s,%s,%s,%s) AS id"
    journal = f["conn"].execute(query, params).fetchone()["id"]
    assert f["conn"].execute(query, params).fetchone()["id"] == journal
    assert (
        f["conn"]
        .execute(
            "SELECT accounting.period_elapsed_loan_assessment_exact(%s,%s) AS exact",
            (f["period_id"], f["loan_id"]),
        )
        .fetchone()["exact"]
    )
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
    assert f["conn"].execute(
        "SELECT sum(l.credit-l.debit) AS balance FROM accounting.journal_entries j JOIN accounting.journal_lines l ON l.journal_entry_id=j.id "
        "JOIN accounting.accounts a ON a.id=l.account_id WHERE j.status='posted' AND a.code='2200' AND l.client_id=%s",
        (f["client_id"],),
    ).fetchone()["balance"] == Decimal(50)
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM treasury.events WHERE account_id=%s",
            (applied["wallet_id"],),
        )
        .fetchone()["n"]
        == 1
    )
