"""Legacy sources absent from prepared queues must still prevent formal close."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import test_loan_disbursement_journal_posting_postgres as disbursement
import test_period_close_postgres as close
import test_regular_collection_reversal_postgres as reversal
import test_regular_journal_posting_postgres as regular
import test_remittance_transfer_journal_lifecycle_postgres as remittance
import test_v1_tax_additional_amendment_postgres as tax_amendment
import test_v1_tax_evidence_postgres as tax_evidence
import test_v1_tax_liability_postgres as tax_liability
import test_v1_tax_recoverable_credit_postgres as tax_credit
import test_v1_tax_recoverable_refund_postgres as tax_refund
from psycopg.types.json import Jsonb
from test_source_close_guard_postgres import _connect, _wait_for_lock

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0143_add_legacy_source_completeness.sql"
)


@pytest.fixture
def legacy_close():
    with _connect() as conn:
        try:
            if os.getenv("SPINA_LEGACY_CLOSE_BASELINE") != "1":
                conn.execute(close._body(MIGRATION.read_text(encoding="utf-8")))
            suffix = uuid4().hex
            actor = close._management_actor(conn, suffix)
            start = conn.execute(
                "SELECT greatest(coalesce(max(end_date)+10,DATE '2048-01-01'),DATE '2048-01-01') FROM accounting.fiscal_periods"
            ).fetchone()[0]
            end = start + timedelta(days=9)
            period = conn.execute(
                "SELECT accounting.create_fiscal_period(%s,%s,%s,%s)",
                ("Legacy source " + suffix, start, end, actor),
            ).fetchone()[0]
            device = uuid4()
            conn.execute(
                "INSERT INTO core.devices(id,user_id,device_identifier_hash,platform,status) VALUES(%s,%s,%s,'web','active')",
                (device, actor, device.hex),
            )
            client, loan = disbursement._loan(
                conn,
                suffix=suffix,
                actor_id=actor,
                release_date=start - timedelta(days=30),
            )
            yield {
                "conn": conn,
                "actor": actor,
                "device": device,
                "period": period,
                "start": start,
                "end": end,
                "client": client,
                "loan": loan,
                "suffix": suffix,
            }
        finally:
            conn.rollback()


def _collection(f, *, day=None, amount="100.00"):
    return regular._create_collection(
        f["conn"],
        suffix=f["suffix"],
        loan_id=f["loan"],
        client_id=f["client"],
        actor_id=f["actor"],
        device_id=f["device"],
        sequence=1,
        collection_date=day or f["start"],
        amount=amount,
    )


def _release(f):
    _, loan = disbursement._loan(
        f["conn"],
        suffix=f["suffix"] + "-release",
        actor_id=f["actor"],
        release_date=f["start"],
    )
    return disbursement._record(
        f["conn"],
        loan_id=loan,
        actor_id=f["actor"],
        business_date=f["start"],
        reference="Synthetic " + f["suffix"],
    )


def _received_remittance(f):
    collector = remittance._create_user(f["conn"], f["suffix"])
    return remittance._create_received_remittance(
        f["conn"],
        suffix=f["suffix"],
        collector_id=collector,
        recipient_id=f["actor"],
        business_date=f["start"],
    )


@pytest.mark.parametrize("family", ["collection", "release", "remittance"])
def test_review_rejects_raw_legacy_source_without_draft(legacy_close, family):
    """Baseline 0141 admits these real sources because no journal draft exists."""
    f = legacy_close
    {
        "collection": _collection,
        "release": _release,
        "remittance": _received_remittance,
    }[family](f)
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) FROM accounting.journal_entries WHERE fiscal_period_id=%s",
            (f["period"],),
        )
        .fetchone()[0]
        == 0
    )
    with (
        pytest.raises(psycopg.Error, match="unreconciled legacy source"),
        f["conn"].transaction(),
    ):
        close._move_to_review(f["conn"], f["period"], f["actor"])
    assert (
        f["conn"]
        .execute(
            "SELECT status FROM accounting.fiscal_periods WHERE id=%s", (f["period"],)
        )
        .fetchone()[0]
        == "open"
    )


def _blockers(f):
    return (
        f["conn"]
        .execute(
            "SELECT source_type,source_id,reason,account_id FROM accounting.period_legacy_source_blockers(%s)",
            (f["period"],),
        )
        .fetchall()
    )


@pytest.mark.parametrize(
    "family,source_type",
    [
        ("collection", "collection"),
        ("release", "loan_disbursement"),
        ("remittance", "remittance_transfer"),
    ],
)
def test_inventory_starts_from_raw_sources_and_preserves_public_legacy_scope(
    legacy_close, family, source_type
):
    f = legacy_close
    source = {
        "collection": _collection,
        "release": _release,
        "remittance": _received_remittance,
    }[family](f)
    assert any(
        row[0] == source_type and row[1] == source and row[3] is None
        for row in _blockers(f)
    )


def test_zero_pass_and_unfunded_loan_row_do_not_manufacture_financial_source(
    legacy_close,
):
    f = legacy_close
    f["conn"].execute(
        """INSERT INTO lending.collection_transactions(idempotency_key,loan_id,client_id,collector_user_id,
        registered_device_id,route_entry_id,collection_date,entry_type,amount,recorded_at,device_sequence,
        previous_balance,official_balance,pass_count_after,receipt_number)
        VALUES(%s,%s,%s,%s,%s,%s,%s,'pass',0,now(),1,5000,5000,1,%s)""",
        (
            uuid4(),
            f["loan"],
            f["client"],
            f["actor"],
            f["device"],
            f["loan"],
            f["start"],
            f["suffix"],
        ),
    )
    assert _blockers(f) == []
    close._move_to_review(f["conn"], f["period"], f["actor"])


def test_collection_outside_period_is_not_a_current_cash_obligation(legacy_close):
    f = legacy_close
    _collection(f, day=f["start"] - timedelta(days=1))
    assert _blockers(f) == []


def test_exact_disbursement_posting_clears_release_source(legacy_close):
    f = legacy_close
    source = _release(f)
    status = disbursement._prepare(
        f["conn"], event_id=source, actor_id=f["actor"], draft_token="4" * 64
    )
    disbursement._post(
        f["conn"], actor_id=f["actor"], status=status, posting_token="5" * 64
    )
    assert not any(
        row[0] == "loan_disbursement" and row[1] == source for row in _blockers(f)
    )
    # Other period-end EIR/ECL/tax requirements may still be genuinely missing.
    # This test asserts only the exact source effect, not complete close readiness.


def _post_regular(f, transaction):
    journals = regular._create_protected_review_set(
        f["conn"],
        actor_id=f["actor"],
        client_id=f["client"],
        loan_id=f["loan"],
        transaction_id=transaction,
        eir_period_id=f["period"],
        eir_date=f["start"],
        collection_period_id=f["period"],
        collection_date=f["start"],
        accounts=regular._account_ids(f["conn"]),
        review_token="6" * 64,
        bundle_token="7" * 64,
    )
    f["conn"].execute(
        "SELECT accounting.post_regular_journal_review_set(%s,%s,%s)",
        (f["loan"], "6" * 64, f["actor"]),
    )
    return journals


def _void_collection(f, transaction, day):
    evidence = {"transaction_id": transaction, "actor_id": f["actor"]}
    when = reversal._void_time(day)
    reason = "Synthetic complete void evidence"
    reversal._insert_void_audit(
        f["conn"], fixture=evidence, void_id=uuid4(), reason=reason, voided_at=when
    )
    reversal._mark_voided(f["conn"], fixture=evidence, reason=reason, voided_at=when)


def test_exact_regular_posted_set_clears_its_source(legacy_close):
    f = legacy_close
    source = _collection(f)
    _post_regular(f, source)
    assert not any(row[0] == "collection" and row[1] == source for row in _blockers(f))
    assert f["conn"].execute(
        "SELECT accounting.legacy_regular_collection_posted_exact(%s)", (source,)
    ).fetchone() == (True,)


def test_void_before_any_accounting_is_nonfinancial_at_cutoff(legacy_close):
    f = legacy_close
    source = _collection(f)
    _void_collection(f, source, f["start"])
    assert _blockers(f) == []
    close._move_to_review(f["conn"], f["period"], f["actor"])


def test_future_void_cannot_hide_missing_original_accounting(legacy_close):
    f = legacy_close
    source = _collection(f)
    _void_collection(f, source, f["end"] + timedelta(days=1))
    assert any(row[0] == "collection" and row[1] == source for row in _blockers(f))


def test_protected_regular_void_requires_complete_swapped_lines(legacy_close):
    f = legacy_close
    source = _collection(f)
    _post_regular(f, source)
    _void_collection(f, source, f["start"])
    assert f["conn"].execute(
        "SELECT accounting.legacy_regular_collection_reversed_exact(%s,%s)",
        (source, f["end"]),
    ).fetchone() == (True,)
    assert not any(row[0] == "collection" and row[1] == source for row in _blockers(f))


def test_received_remittance_with_exact_posting_stays_clear_in_review(legacy_close):
    f = legacy_close
    source = _received_remittance(f)
    evidence = remittance._record_evidence(
        f["conn"], remittance_id=source, actor_id=f["actor"], business_date=f["start"]
    )
    key = f"remittance_transfer:{source}"
    prepared = (
        f["conn"]
        .execute(
            """SELECT accounting.create_remittance_transfer_journal_draft(
        %s,%s,%s,%s,%s,%s,'cash_office','cash_collector_custody',1500.00,
        'remittance_transfer_coordinates_v1','remittance_transfer_journal_draft_v1')""",
            (source, f["actor"], "8" * 64, evidence, key, f["start"]),
        )
        .fetchone()[0]
    )
    journal = (
        f["conn"]
        .execute(
            "SELECT journal_entry_id FROM accounting.remittance_transfer_journal_preparations WHERE id=%s",
            (prepared,),
        )
        .fetchone()[0]
    )
    f["conn"].execute(
        """SELECT accounting.post_remittance_transfer_journal(
        %s,%s,%s,%s,%s,%s,1500.00,'remittance_transfer_journal_posting_v1')""",
        (prepared, f["actor"], "9" * 64, journal, key, "8" * 64),
    )
    assert _blockers(f) == []
    close._move_to_review(f["conn"], f["period"], f["actor"])
    assert _blockers(f) == []


def test_review_then_same_transaction_source_fails_deferred_validation(legacy_close):
    f = legacy_close
    with (
        pytest.raises(psycopg.Error, match="unreconciled legacy source"),
        f["conn"].transaction(),
    ):
        close._move_to_review(f["conn"], f["period"], f["actor"])
        _collection(f)
        f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
    assert f["conn"].execute(
        "SELECT status FROM accounting.fiscal_periods WHERE id=%s", (f["period"],)
    ).fetchone() == ("open",)


def test_partial_collection_requires_unallocated_liability_mapping(legacy_close):
    f = legacy_close
    source = _collection(f)
    f["conn"].execute(
        """UPDATE lending.collection_transactions SET applied_amount=80,
        unallocated_amount=20,allocation_state='partially_allocated' WHERE id=%s""",
        (source,),
    )
    assert (
        "collection",
        source,
        "collection_unallocated_liability_mapping_required",
        None,
    ) in _blockers(f)


@pytest.mark.parametrize("source_type", ["eir_period_end", "ecl_period_end"])
def test_posted_receivable_requires_dated_assessment(legacy_close, source_type):
    f = legacy_close
    source = _release(f)
    status = disbursement._prepare(
        f["conn"], event_id=source, actor_id=f["actor"], draft_token="a" * 64
    )
    disbursement._post(
        f["conn"], actor_id=f["actor"], status=status, posting_token="b" * 64
    )
    loan = (
        f["conn"]
        .execute(
            "SELECT loan_id FROM lending.loan_disbursement_events WHERE id=%s",
            (source,),
        )
        .fetchone()[0]
    )
    assert any(row[0] == source_type and row[1] == loan for row in _blockers(f))


@pytest.mark.parametrize(
    "family,source_type", [("release", "tax_dst"), ("collection", "tax_percentage")]
)
def test_tax_population_includes_raw_source_without_any_posting(
    legacy_close, family, source_type
):
    f = legacy_close
    source = {"release": _release, "collection": _collection}[family](f)
    assert any(row[0] == source_type and row[1] == source for row in _blockers(f))


def test_valid_unpaid_liability_does_not_require_zero_payables(legacy_close):
    f = legacy_close
    close._manual_journal(
        f["conn"],
        actor_id=f["actor"],
        posting_date=f["start"],
        description="Synthetic retained payable",
        lines=[
            {"account_code": "1010", "debit": "100.00", "credit": "0.00"},
            {"account_code": "2000", "debit": "0.00", "credit": "100.00"},
        ],
    )
    assert _blockers(f) == []
    close._move_to_review(f["conn"], f["period"], f["actor"])


def test_unallocated_loan_control_balance_cannot_hide_from_assessment(legacy_close):
    f = legacy_close
    close._manual_journal(
        f["conn"],
        actor_id=f["actor"],
        posting_date=f["start"],
        description="Synthetic receivable without loan dimension",
        lines=[
            {"account_code": "1100", "debit": "100.00", "credit": "0.00"},
            {"account_code": "1010", "debit": "0.00", "credit": "100.00"},
        ],
    )
    assert any(row[2] == "unallocated_control_balance" for row in _blockers(f))


@pytest.mark.parametrize(
    "credit_code,debit_code", [("1100", "1110"), ("1110", "1120"), ("1120", "1100")]
)
def test_negative_loan_control_cannot_be_hidden_by_another_control_debit(
    legacy_close, credit_code, debit_code
):
    f = legacy_close
    # The manual API deliberately ignores dimensions; retain them on the mutable
    # draft before protected posting to exercise actual loan-level GL evidence.
    journal = (
        f["conn"]
        .execute(
            "SELECT accounting.create_manual_journal_draft(%s,%s,%s,%s::jsonb)",
            (
                f["start"],
                "Synthetic offsetting loan control balances",
                f["actor"],
                Jsonb(
                    [
                        {
                            "account_code": debit_code,
                            "debit": "100.00",
                            "credit": "0.00",
                        },
                        {
                            "account_code": credit_code,
                            "debit": "0.00",
                            "credit": "100.00",
                        },
                    ]
                ),
            ),
        )
        .fetchone()[0]
    )
    f["conn"].execute(
        "UPDATE accounting.journal_lines SET loan_id=%s,client_id=%s WHERE journal_entry_id=%s",
        (f["loan"], f["client"], journal),
    )
    f["conn"].execute(
        "SELECT accounting.post_manual_journal_entry(%s,%s)", (journal, f["actor"])
    )
    assert (
        "loan_control_balance",
        f["loan"],
        f"negative_{credit_code}_balance_requires_borrower_credit_review",
        None,
    ) in _blockers(f)
    with (
        pytest.raises(psycopg.Error, match="unreconciled legacy source"),
        f["conn"].transaction(),
    ):
        close._move_to_review(f["conn"], f["period"], f["actor"])


def _percentage_evidence(f, *, due="0.60", taxable="20.00", principal="80.00"):
    source = _collection(f)
    _post_regular(f, source)
    rule = tax_evidence._record_rule(
        f["conn"],
        actor_id=f["actor"],
        tax_type="percentage_tax_lending",
        key="legacy-completeness-" + f["suffix"],
        effective_from=f["start"],
        rate="0.03",
        maturity_max_days=None,
        digest_char="c",
    )
    evidence = (
        f["conn"]
        .execute(
            """SELECT accounting.record_v1_percentage_tax_evidence(
        %s,%s,%s,%s,100.00,%s,%s,%s,'synthetic allocation',%s,
        'Synthetic independent tax allocation retained for disposable validation',NULL)""",
            (f["actor"], uuid4(), source, rule, taxable, principal, due, "d" * 64),
        )
        .fetchone()[0]
    )
    return source, evidence


def test_exact_unpaid_percentage_tax_liability_clears_tax_source(legacy_close):
    f = legacy_close
    source, evidence = _percentage_evidence(f)
    f["conn"].execute(
        "SELECT accounting.prepare_v1_tax_liability_journal(%s,%s,%s)",
        ("percentage_tax_lending", evidence, f["actor"]),
    )
    tax_liability._post(
        f["conn"],
        tax_type="percentage_tax_lending",
        evidence_id=evidence,
        actor_id=f["actor"],
        evidence_digest="d" * 64,
        tax_due="0.60",
        expense_code="5300",
        posting_date=f["start"],
        period_id=f["period"],
    )
    assert not any(
        row[0] == "tax_percentage" and row[1] == source for row in _blockers(f)
    )


def test_zero_tax_evidence_requires_no_fake_liability_journal(legacy_close):
    f = legacy_close
    source, _ = _percentage_evidence(f, due="0", taxable="0", principal="100")
    assert not any(
        row[0] == "tax_percentage" and row[1] == source for row in _blockers(f)
    )


def _tax_payment(f):
    _, evidence = _percentage_evidence(f)
    f["conn"].execute(
        "SELECT accounting.prepare_v1_tax_liability_journal(%s,%s,%s)",
        ("percentage_tax_lending", evidence, f["actor"]),
    )
    posting = tax_liability._post(
        f["conn"],
        tax_type="percentage_tax_lending",
        evidence_id=evidence,
        actor_id=f["actor"],
        evidence_digest="d" * 64,
        tax_due="0.60",
        expense_code="5300",
        posting_date=f["start"],
        period_id=f["period"],
    )
    tax_return = (
        f["conn"]
        .execute(
            """SELECT accounting.record_v1_tax_return_evidence(
        %s,%s,'percentage_tax_lending',%s,%s,%s,0.60,
        'Synthetic return','Synthetic retained return',%s,
        'Synthetic exact return composition for disposable source close validation',%s)""",
            (
                f["actor"],
                uuid4(),
                f["start"],
                f["start"],
                f["start"],
                "e" * 64,
                [posting],
            ),
        )
        .fetchone()[0]
    )
    return (
        f["conn"]
        .execute(
            """SELECT accounting.record_v1_tax_payment_evidence(
        %s,%s,%s,%s,0.60,'cash_bank_gcash','Synthetic tax payment','Synthetic bank proof',%s,
        'Synthetic retained payment proof for disposable source close validation')""",
            (f["actor"], uuid4(), tax_return, f["start"], "f" * 64),
        )
        .fetchone()[0]
    )


def test_raw_tax_payment_without_preparation_is_incomplete(legacy_close):
    f = legacy_close
    payment = _tax_payment(f)
    assert any(row[0] == "tax_payment" and row[1] == payment for row in _blockers(f))


def test_exact_tax_payment_does_not_clear_unresolved_loan_control(legacy_close):
    f = legacy_close
    payment = _tax_payment(f)
    f["conn"].execute(
        "SELECT accounting.prepare_v1_tax_settlement_journal(%s,%s)",
        (payment, f["actor"]),
    )
    f["conn"].execute(
        """SELECT accounting.post_v1_tax_settlement_journal(
        %s,%s,%s,%s,%s,0.60,'2100','1030',%s,%s,'v1_tax_settlement_posting_v1')""",
        (payment, f["actor"], "a" * 64, "e" * 64, "f" * 64, f["start"], f["period"]),
    )
    assert not any(
        row[0] == "tax_payment" and row[1] == payment for row in _blockers(f)
    )
    # This synthetic source-level fixture has no receivable opening. Its exact
    # tax proof must not certify economic completeness of the whole book.
    assert any(row[0] == "loan_control_balance" for row in _blockers(f))
    with (
        pytest.raises(psycopg.Error, match="unreconciled legacy source"),
        f["conn"].transaction(),
    ):
        close._move_to_review(f["conn"], f["period"], f["actor"])
    assert f["conn"].execute(
        "SELECT posted_exact FROM accounting.legacy_tax_movement_proof WHERE source_type='tax_payment' AND source_id=%s",
        (payment,),
    ).fetchone() == (True,)
    assert f["conn"].execute(
        "SELECT status FROM accounting.fiscal_periods WHERE id=%s", (f["period"],)
    ).fetchone() == ("open",)


@pytest.mark.parametrize("realization", ["refund", "credit"])
def test_tax_decrease_and_realization_require_exact_separate_postings(
    legacy_close, realization
):
    f = legacy_close
    conn = f["conn"]
    actor, _, adjustment_posting, adjustment_date, period = (
        tax_refund._posted_recoverable(conn, f["suffix"])
    )
    tax_f = dict(f, period=period)
    # The posted decrease covers the replacement, so another full liability is wrong.
    assert not any(
        row[0] in ("tax_dst", "tax_adjustment", "tax_payment")
        for row in _blockers(tax_f)
    )
    when = adjustment_date + timedelta(days=1)
    if realization == "refund":
        evidence = tax_refund._record_refund(
            conn,
            actor_id=actor,
            adjustment_posting_id=adjustment_posting,
            refund_date=when,
            idempotency_key=uuid4(),
            digest_char="3",
        )
        source_type = "tax_refund"
        assert any(
            row[0] == source_type and row[1] == evidence for row in _blockers(tax_f)
        )
        conn.execute(
            "SELECT accounting.prepare_v1_tax_recoverable_refund_journal(%s,%s)",
            (evidence, actor),
        )
        tax_refund._post_refund(
            conn,
            refund_evidence_id=evidence,
            actor_id=actor,
            digest="3" * 64,
            refund_date=when,
            period_id=period,
        )
    else:
        tax_return, _ = tax_credit._target_return_247(
            conn, actor_id=actor, period_id=period, suffix=f["suffix"]
        )
        evidence = tax_credit._record_credit(
            conn,
            actor_id=actor,
            adjustment_posting_id=adjustment_posting,
            target_return_id=tax_return,
            application_date=when,
            idempotency_key=uuid4(),
            digest_char="6",
        )
        source_type = "tax_credit_application"
        assert any(
            row[0] == source_type and row[1] == evidence for row in _blockers(tax_f)
        )
        conn.execute(
            "SELECT accounting.prepare_v1_tax_recoverable_credit_journal(%s,%s)",
            (evidence, actor),
        )
        tax_credit._post_credit(
            conn,
            credit_evidence_id=evidence,
            actor_id=actor,
            digest="6" * 64,
            application_date=when,
            period_id=period,
        )
    assert not any(
        row[0] == source_type and row[1] == evidence for row in _blockers(tax_f)
    )


def test_additional_tax_delta_covers_replacement_but_actual_payment_is_separate(
    legacy_close,
):
    f = legacy_close
    conn = f["conn"]
    (
        actor,
        loan,
        _,
        event,
        release_date,
        period,
        old_rule,
        old_evidence,
        posting,
        tax_return,
    ) = tax_amendment._setup_filed_case(conn, f["suffix"])
    replacement = tax_amendment._higher_dst_replacement(
        conn,
        actor_id=actor,
        loan_id=loan,
        event_id=event,
        release_date=release_date,
        old_rule_id=old_rule,
        old_evidence_id=old_evidence,
        suffix=f["suffix"],
    )
    when = release_date + timedelta(days=2)
    amendment = tax_amendment._record_amendment(
        conn,
        actor_id=actor,
        return_id=tax_return,
        liability_posting_id=posting,
        replacement_evidence_id=replacement,
        amendment_date=when,
        recognition_date=when,
        digest_char="7",
    )
    tax_f = dict(f, period=period)
    assert any(
        row[0] == "tax_additional_liability" and row[1] == amendment
        for row in _blockers(tax_f)
    )
    conn.execute(
        "SELECT accounting.prepare_v1_tax_additional_liability_journal(%s,%s)",
        (amendment, actor),
    )
    liability = tax_amendment._post_liability(
        conn,
        amendment_id=amendment,
        actor_id=actor,
        digest="7" * 64,
        posting_date=when,
        period_id=period,
    )
    assert not any(
        row[0] in ("tax_dst", "tax_additional_liability") for row in _blockers(tax_f)
    )
    # An unpaid, fully recognized revised liability is valid until actual payment exists.
    payment = tax_amendment._record_additional_payment(
        conn,
        actor_id=actor,
        amendment_id=amendment,
        payment_date=when,
        amount="9.86",
        digest_char="8",
    )
    assert any(
        row[0] == "tax_additional_payment" and row[1] == payment
        for row in _blockers(tax_f)
    )
    conn.execute(
        "SELECT accounting.prepare_v1_tax_additional_settlement_journal(%s,%s)",
        (payment, actor),
    )
    digest = conn.execute(
        "SELECT confirmation_digest FROM accounting.v1_tax_additional_liability_postings WHERE id=%s",
        (liability,),
    ).fetchone()[0]
    tax_amendment._post_settlement(
        conn,
        payment_id=payment,
        actor_id=actor,
        amendment_digest="7" * 64,
        liability_digest=digest,
        payment_digest="8" * 64,
        amount="9.86",
        posting_date=when,
        period_id=period,
    )
    assert not any(
        row[0] == "tax_additional_payment" and row[1] == payment
        for row in _blockers(tax_f)
    )


def test_legacy_source_writer_commits_first_and_waiting_review_sees_it(legacy_close):
    f = legacy_close
    f["conn"].commit()
    with (
        _connect() as writer,
        _connect() as reviewer,
        ThreadPoolExecutor(max_workers=1) as pool,
    ):
        writer.execute("SET statement_timeout='8s'")
        reviewer.execute("SET statement_timeout='8s'")
        source = _collection(dict(f, conn=writer))

        def review():
            try:
                close._move_to_review(reviewer, f["period"], f["actor"])
                reviewer.commit()
                return "unexpected success"
            except psycopg.Error as error:
                reviewer.rollback()
                return str(error)

        pending = pool.submit(review)
        try:
            _wait_for_lock(f["conn"], reviewer.info.backend_pid)
        finally:
            writer.commit()
        assert "unreconciled legacy source" in pending.result(timeout=10)
        assert any(row[0] == "collection" and row[1] == source for row in _blockers(f))
        assert f["conn"].execute(
            "SELECT status FROM accounting.fiscal_periods WHERE id=%s", (f["period"],)
        ).fetchone() == ("open",)


def test_review_first_retains_late_legacy_money_after_wait(legacy_close):
    f = legacy_close
    f["conn"].commit()
    close._move_to_review(f["conn"], f["period"], f["actor"])
    with _connect() as writer, ThreadPoolExecutor(max_workers=1) as pool:
        writer.execute("SET statement_timeout='8s'")

        def write_collection():
            source = _collection(dict(f, conn=writer))
            writer.commit()
            return source

        pending = pool.submit(write_collection)
        try:
            _wait_for_lock(f["conn"], writer.info.backend_pid)
        finally:
            f["conn"].commit()
        source = pending.result(timeout=10)
        assert any(row[0] == "collection" and row[1] == source for row in _blockers(f))
        with (
            pytest.raises(psycopg.Error, match="unreconciled legacy source"),
            f["conn"].transaction(),
        ):
            f["conn"].execute(
                "SELECT accounting.prepare_period_close(%s,%s)",
                (f["period"], f["actor"]),
            )
