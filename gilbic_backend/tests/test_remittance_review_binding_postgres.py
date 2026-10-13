"""A remittance must contain exactly the financial facts its sender reviewed."""

import inspect
import os
import re
from datetime import date
from uuid import uuid4

import psycopg
import pytest
from gilbic_backend.remittance_review_repository import (
    PostgresReviewedRemittanceRepository,
)
from psycopg.conninfo import conninfo_to_dict
from test_remittance_review_rejection_postgres import _seed_collection

from gilbic_backend import remittance_repository as module


@pytest.fixture
def reviewed_batch(monkeypatch):
    url = os.getenv("GILBIC_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Explicit disposable loopback PostgreSQL required")
    params = conninfo_to_dict(url)
    assert params.get("host") in {"127.0.0.1", "localhost", "::1"}
    assert re.fullmatch(r"spina_treasury_validation_[a-f0-9]{24}", params["dbname"])
    assert os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") == "1"
    monkeypatch.setattr(module, "open_connection", lambda: psycopg.connect(url))
    when = date(2098, 10, 6)
    collector, recipient, transaction = _seed_collection(
        suffix=uuid4().hex, collection_date=when
    )
    repository = PostgresReviewedRemittanceRepository()
    preview = repository.preview(collector_user_id=collector, collection_date=when)
    return {
        "url": url,
        "collector": collector,
        "recipient": recipient,
        "transaction": transaction,
        "day": when,
        "repository": repository,
        "preview": preview,
    }


def _submit(f, *, reviewed=True):
    args = {
        "collector_user_id": f["collector"],
        "recipient_user_id": f["recipient"],
        "collection_date": f["day"],
        "note": "Exact synthetic reviewed batch",
    }
    # Exercise the real old boundary for the baseline RED, rather than failing
    # on an unknown keyword before the unsafe financial write is reached.
    if "expected_review_digest" in inspect.signature(f["repository"].submit).parameters:
        args["expected_review_digest"] = (
            getattr(f["preview"], "review_digest", None) if reviewed else None
        )
    return f["repository"].submit(**args)


def _add_receipt(conn, transaction, amount):
    return conn.execute(
        "INSERT INTO lending.collection_transactions(idempotency_key,loan_id,client_id,"
        "collector_user_id,registered_device_id,route_entry_id,collection_date,entry_type,amount,"
        "recorded_at,device_sequence,note,previous_balance,official_balance,pass_count_after,receipt_number,details) "
        "SELECT %s,loan_id,client_id,collector_user_id,registered_device_id,route_entry_id,collection_date,"
        "'payment',%s,now(),device_sequence+1,'Synthetic later device receipt',1000,900,0,%s,details "
        "FROM lending.collection_transactions WHERE id=%s RETURNING id",
        (uuid4(), amount, "REVIEW-" + uuid4().hex, transaction),
    ).fetchone()[0]


@pytest.mark.parametrize(
    "change", ["new_receipt", "same_total_membership", "version_only"]
)
def test_changed_review_rejects_before_locking_any_receipt(reviewed_batch, change):
    f = reviewed_batch
    with psycopg.connect(f["url"]) as conn:
        if change == "version_only":
            conn.execute(
                "UPDATE lending.collection_transactions SET edit_version=edit_version+1 WHERE id=%s",
                (f["transaction"],),
            )
        else:
            _add_receipt(
                conn, f["transaction"], 50 if change == "same_total_membership" else 100
            )
            if change == "same_total_membership":
                conn.execute(
                    "UPDATE lending.collection_transactions SET amount=50,applied_amount=50 WHERE id=%s",
                    (f["transaction"],),
                )
    with pytest.raises(module.RemittanceError, match="review|Refresh|refresh"):
        _submit(f)
    with psycopg.connect(f["url"]) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM lending.collection_remittances WHERE collector_user_id=%s",
                (f["collector"],),
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute(
                "SELECT bool_or(is_locked OR remittance_id IS NOT NULL) FROM lending.collection_transactions WHERE collector_user_id=%s",
                (f["collector"],),
            ).fetchone()[0]
            is False
        )


def test_missing_review_identity_fails_closed(reviewed_batch):
    with pytest.raises(module.RemittanceError, match="review|Refresh|refresh|update"):
        _submit(reviewed_batch, reviewed=False)


def test_unchanged_review_submits_exact_receipts(reviewed_batch):
    f = reviewed_batch
    saved = _submit(f)
    assert saved.total_amount == f["preview"].total_amount
    assert saved.items == f["preview"].items


def test_digest_binds_cash_allocation_even_when_total_and_version_match(reviewed_batch):
    f = reviewed_batch
    with psycopg.connect(f["url"]) as conn:
        conn.execute(
            "UPDATE lending.collection_transactions SET applied_amount=90,unallocated_amount=10,allocation_state='partially_allocated' WHERE id=%s",
            (f["transaction"],),
        )
    with pytest.raises(module.RemittanceReviewChanged):
        _submit(f)


def test_cross_review_binds_exact_current_source_and_capacity(
    reviewed_batch, monkeypatch
):
    from gilbic_backend import cross_remittance_repository as cross

    f = reviewed_batch
    monkeypatch.setattr(cross, "open_connection", lambda: psycopg.connect(f["url"]))
    with psycopg.connect(f["url"]) as conn:
        conn.execute(
            "INSERT INTO core.user_roles(user_id,role_id) SELECT %s,id FROM core.roles WHERE code='management' ON CONFLICT DO NOTHING",
            (f["recipient"],),
        )
        conn.execute(
            "UPDATE lending.collection_transactions SET collection_origin='cross_collector',assigned_collector_user_id=%s WHERE id=%s",
            (f["recipient"], f["transaction"]),
        )
    repo = cross.PostgresCrossRemittanceRepository()
    args = {
        "collector_user_id": f["collector"],
        "recipient_user_id": f["recipient"],
        "recipient_capacity": "management",
        "collection_date": f["day"],
    }
    preview = repo.preview(**args)
    assert len(preview.items) == 1
    with psycopg.connect(f["url"]) as conn:
        conn.execute(
            "UPDATE lending.collection_transactions SET edit_version=edit_version+1 WHERE id=%s",
            (f["transaction"],),
        )
    with pytest.raises(module.RemittanceReviewChanged):
        repo.submit(
            **args,
            note="Reviewed cross batch",
            expected_review_digest=preview.review_digest,
        )
    current = repo.preview(**args)
    record = repo.submit(
        **args,
        note="Reviewed cross batch",
        expected_review_digest=current.review_digest,
    )
    assert record.total_amount == current.total_amount


def test_inflight_correction_yields_without_blocking_actual_money(reviewed_batch):
    from concurrent.futures import ThreadPoolExecutor

    f = reviewed_batch
    with psycopg.connect(f["url"]) as editor, ThreadPoolExecutor(max_workers=1) as pool:
        editor.execute(
            "UPDATE lending.collection_transactions SET edit_version=edit_version+1 WHERE id=%s",
            (f["transaction"],),
        )
        pending = pool.submit(_submit, f)
        try:
            with pytest.raises(module.RemittanceReviewChanged, match="Refresh|refresh"):
                pending.result(timeout=1)
        finally:
            editor.commit()
    with pytest.raises(module.RemittanceReviewChanged):
        _submit(f)
    with psycopg.connect(f["url"]) as conn:
        assert conn.execute(
            "SELECT is_locked,remittance_id FROM lending.collection_transactions WHERE id=%s",
            (f["transaction"],),
        ).fetchone() == (False, None)


@pytest.mark.parametrize("cross_remittance", [False, True], ids=["normal", "cross"])
def test_row_locked_correction_can_finish_while_remittance_fails_fast(
    reviewed_batch, monkeypatch, cross_remittance
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from gilbic_backend import cross_remittance_repository as cross

    f = reviewed_batch
    args = {"collector_user_id": f["collector"], "collection_date": f["day"]}
    repository = f["repository"]
    if cross_remittance:
        monkeypatch.setattr(cross, "open_connection", lambda: psycopg.connect(f["url"]))
        with psycopg.connect(f["url"]) as setup:
            setup.execute(
                "UPDATE lending.collection_transactions SET collection_origin='cross_collector',assigned_collector_user_id=%s WHERE id=%s",
                (f["recipient"], f["transaction"]),
            )
        repository = cross.PostgresCrossRemittanceRepository()
        args.update(recipient_user_id=f["recipient"], recipient_capacity="management")
    preview = repository.preview(**args)
    assert [item.transaction_id for item in preview.items] == [f["transaction"]]
    submit_args = {**args, "recipient_user_id": f["recipient"], "note": "Reviewed cash"}

    admission_started = Event()
    original_admission = module.PostgresRemittanceRepository._lock_review_sources

    def observe_admission(cursor):
        admission_started.set()
        original_admission(cursor)

    monkeypatch.setattr(
        module.PostgresRemittanceRepository,
        "_lock_review_sources",
        staticmethod(observe_admission),
    )
    with psycopg.connect(f["url"]) as editor, ThreadPoolExecutor(max_workers=1) as pool:
        editor.execute("SET LOCAL statement_timeout = '2s'")
        # The real correction locks the receipt before its first DELETE/UPDATE.
        # At this point it holds ROW SHARE, not an UPDATE's ROW EXCLUSIVE.
        assert editor.execute(
            "SELECT id FROM lending.collection_transactions WHERE id=%s FOR UPDATE",
            (f["transaction"],),
        ).fetchone() == (f["transaction"],)
        pending = pool.submit(
            repository.submit,
            **submit_args,
            expected_review_digest=preview.review_digest,
        )
        try:
            assert admission_started.wait(5)
            with pytest.raises(module.RemittanceReviewChanged, match="Refresh|refresh"):
                pending.result(timeout=2)
            # These are the correction's next write targets. They must remain
            # writable in the same transaction while remittance asks for retry.
            editor.execute(
                "DELETE FROM lending.collection_covered_dates WHERE transaction_id=%s",
                (f["transaction"],),
            )
            editor.execute(
                "UPDATE lending.collection_transactions SET edit_version=edit_version+1 WHERE id=%s",
                (f["transaction"],),
            )
            editor.commit()
        finally:
            editor.rollback()
    with pytest.raises(module.RemittanceReviewChanged):
        repository.submit(**submit_args, expected_review_digest=preview.review_digest)
    current = repository.preview(**args)
    saved = repository.submit(
        **submit_args, expected_review_digest=current.review_digest
    )
    assert saved.items == current.items


def test_new_receipt_waits_until_exact_reviewed_batch_is_saved(
    reviewed_batch, monkeypatch
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    f = reviewed_batch
    checked, release = Event(), Event()
    original = module.assert_review_digest

    def pause(summary, expected):
        original(summary, expected)
        checked.set()
        assert release.wait(5)

    monkeypatch.setattr(module, "assert_review_digest", pause)

    def insert():
        with psycopg.connect(f["url"]) as conn:
            return _add_receipt(conn, f["transaction"], 100)

    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(_submit, f)
        assert checked.wait(5)
        newer = pool.submit(insert)
        try:
            from concurrent.futures import TimeoutError

            with pytest.raises(TimeoutError):
                newer.result(timeout=0.15)
        finally:
            release.set()
        saved = pending.result(timeout=5)
        new_id = newer.result(timeout=5)
    assert [item.transaction_id for item in saved.items] == [f["transaction"]]
    with psycopg.connect(f["url"]) as conn:
        assert conn.execute(
            "SELECT is_locked,remittance_id FROM lending.collection_transactions WHERE id=%s",
            (new_id,),
        ).fetchone() == (False, None)


def test_real_refund_release_after_review_rejects_without_allocating_cash(
    reviewed_batch, monkeypatch
):
    from datetime import datetime, timezone
    from decimal import Decimal

    from test_seven_by_seven_extra_principal_persistence_postgres import (
        _record_adjustment,
        _setup_case,
    )

    from gilbic_backend import refund_due_repository as refunds

    f = reviewed_batch
    loan, client, collector, device, installment = _setup_case()
    monkeypatch.setattr(refunds, "open_connection", lambda: psycopg.connect(f["url"]))
    with psycopg.connect(f["url"]) as conn:
        area = "review-refund-" + uuid4().hex
        conn.execute("UPDATE lending.clients SET area=%s WHERE id=%s", (area, client))
        conn.execute(
            "INSERT INTO lending.collector_area_assignments(collector_user_id,area,sort_order,is_active) VALUES(%s,%s,0,true)",
            (collector, area),
        )
        adjustment = _record_adjustment(
            conn,
            loan_id=loan,
            client_id=client,
            collector_id=collector,
            device_id=device,
            installment_id=installment,
            sequence=2,
            expected_version=0,
            prior_future_principal="3000.00",
            reduction="20.00",
            prior_principal="29.00",
            prior_amount="50.00",
            new_principal="9.00",
            new_amount="30.00",
            advance_before="35.00",
            advance_retained="30.00",
            refund_due="5.00",
        )
        day = conn.execute(
            "SELECT min(collection_date) FROM lending.collection_transactions WHERE collector_user_id=%s",
            (collector,),
        ).fetchone()[0]
    repo = refunds.PostgresRefundDueRepository()
    approval = repo.approve(
        idempotency_key=uuid4(),
        actor_user_id=collector,
        adjustment_id=adjustment,
        approved_amount=Decimal("5.00"),
        reason="Borrower return",
        authority_reference="review-test",
    )
    f = {**f, "collector": collector, "day": day}
    f["preview"] = f["repository"].preview(
        collector_user_id=collector, collection_date=day
    )
    assert f["preview"].total_amount > 5 and f["preview"].refund_due_release_count == 0
    release = repo.release(
        idempotency_key=uuid4(),
        actor_user_id=collector,
        approval_id=approval.approval_id,
        released_amount=Decimal("5.00"),
        released_at=datetime(2099, 1, 1, 9, tzinfo=timezone.utc),
        evidence_reference="Signed refund review test",
        evidence_digest="d" * 64,
    )
    with pytest.raises(module.RemittanceReviewChanged):
        _submit(f)
    with psycopg.connect(f["url"]) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM lending.collection_remittance_refund_due_release_items WHERE release_id=%s",
                (release.release_id,),
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute(
                "SELECT bool_or(is_locked) FROM lending.collection_transactions WHERE collector_user_id=%s",
                (collector,),
            ).fetchone()[0]
            is False
        )
    f["preview"] = f["repository"].preview(
        collector_user_id=collector, collection_date=day
    )
    assert f["preview"].refund_due_release_total == Decimal("5.00")
    saved = _submit(f)
    assert saved.refund_due_release_total == Decimal("5.00")
    assert saved.total_amount == f["preview"].total_amount
