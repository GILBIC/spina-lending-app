from pathlib import Path


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0103_add_past_due_followup_foundation.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_past_due_reason_and_promise_history_are_persistent() -> None:
    sql = _sql()

    assert "create table if not exists lending.past_due_obligations" in sql
    assert "create table if not exists lending.past_due_reason_revisions" in sql
    assert "create table if not exists lending.payment_promises" in sql
    assert "create table if not exists lending.payment_promise_obligations" in sql
    assert "create table if not exists lending.payment_promise_revisions" in sql
    assert "on delete restrict" in sql
    assert "past due / promise revision history is immutable" in sql


def test_reason_vocabulary_and_partial_vs_unable_are_explicit() -> None:
    sql = _sql()

    for reason in (
        "no_cash",
        "client_absent",
        "business_slow",
        "sick_hospital",
        "emergency",
        "promised_to_pay_later",
        "other",
    ):
        assert reason in sql

    assert "unable_to_pay" in sql
    assert "partial_payment" in sql
    assert "current_reason_code <> 'other'" in sql
    assert "btrim(current_reason_note) <> ''" in sql


def test_only_one_pending_promise_and_no_second_debt_semantics() -> None:
    sql = _sql()

    assert "lending_payment_promises_one_pending_client_uidx" in sql
    assert "where status = 'pending'" in sql
    assert "pending", "kept", "partially_kept", "not_kept"
    assert "never creates a second debt" in sql
    assert "payment promise may cover only past due obligations for the same client and loan" in sql
    assert "promise obligation targets cannot exceed the current promised amount" in sql
