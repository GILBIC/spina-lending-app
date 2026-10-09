"""Committed tax races run only in an explicitly owned disposable database.

The caller installs the real migration sequence. These tests never reinstall
historical tax functions, which could hide a current-schema regression.
"""

from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Event
from time import monotonic
from uuid import uuid4

import psycopg
import pytest
import test_v1_tax_recoverable_credit_postgres as credit_helpers

DATABASE_URL = os.getenv("SPINA_TAX_RACE_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="Owned disposable tax-race database is not configured"
)


@pytest.fixture(scope="module")
def database_url():
    assert DATABASE_URL is not None
    params = psycopg.conninfo.conninfo_to_dict(DATABASE_URL)
    if (
        os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") != "1"
        or params.get("host") != "127.0.0.1"
        or params.get("hostaddr") != "127.0.0.1"
        or not params.get("port")
        or not re.fullmatch(
            r"spina_tax_race_(?:[0-9a-f]{12}|[0-9a-f]{32})", params.get("dbname", "")
        )
        or any(
            params.get(key) for key in ("service", "servicefile", "passfile", "options")
        )
    ):
        raise RuntimeError(
            "Tax races require an explicitly owned loopback disposable database"
        )
    return DATABASE_URL


def _connect(database_url, *, autocommit=False):
    return psycopg.connect(
        database_url,
        autocommit=autocommit,
        options="-c jit=off -c statement_timeout=15000 -c lock_timeout=10000",
    )


@pytest.fixture(autouse=True)
def shared_tax_period(monkeypatch):
    # These historical seed helpers normally roll their period back. Committed
    # independent-session fixtures share the same open synthetic 2098 period.
    create_period = credit_helpers.liability_helpers._open_period

    def shared_period(connection, suffix, start, end):
        existing = connection.execute(
            "SELECT id FROM accounting.fiscal_periods "
            "WHERE start_date=%s AND end_date=%s AND status='open'",
            (start, end),
        ).fetchone()
        return (
            existing[0] if existing else create_period(connection, suffix, start, end)
        )

    monkeypatch.setattr(credit_helpers.liability_helpers, "_open_period", shared_period)


@pytest.fixture
def recoverable(database_url):
    suffix = "race" + uuid4().hex[:8]
    with _connect(database_url) as connection:
        actor, _, adjustment, adjustment_date, period = (
            credit_helpers.refund_helpers._posted_recoverable(connection, suffix)
        )
        target, target_date = credit_helpers._target_return_247(
            connection, actor_id=actor, period_id=period, suffix=suffix
        )
        return {
            "actor": actor,
            "adjustment": adjustment,
            "period": period,
            "target": target,
            "date": max(adjustment_date, target_date) + timedelta(days=2),
            "credit_key": uuid4(),
            "refund_key": uuid4(),
        }


def _record(connection, case, kind):
    common = {
        "actor_id": case["actor"],
        "adjustment_posting_id": case["adjustment"],
        "idempotency_key": case[kind + "_key"],
        "digest_char": "6" if kind == "credit" else "7",
    }
    if kind == "credit":
        return credit_helpers._record_credit(
            connection,
            **common,
            target_return_id=case["target"],
            application_date=case["date"],
        )
    return credit_helpers.refund_helpers._record_refund(
        connection, **common, refund_date=case["date"]
    )


def _attempt(connection, case, kind):
    try:
        result = _record(connection, case, kind)
        connection.commit()
        return "accepted", result
    except psycopg.Error as error:
        connection.rollback()
        return "rejected", error


def _overlap(database_url, case, first_kind, second_kind, *, commit_first=True):
    """The first real write stays open until a real contender lock is observed."""
    with (
        _connect(database_url) as first,
        _connect(database_url) as second,
        _connect(database_url, autocommit=True) as observer,
        ThreadPoolExecutor(max_workers=1) as executor,
    ):
        first_id = _record(first, case, first_kind)
        future = executor.submit(_attempt, second, case, second_kind)
        blocked = False
        try:
            deadline = monotonic() + 5
            while monotonic() < deadline:
                blockers = observer.execute(
                    "SELECT pg_blocking_pids(%s)", (second.info.backend_pid,)
                ).fetchone()[0]
                if first.info.backend_pid in blockers:
                    blocked = True
                    break
                if future.done():
                    break
                Event().wait(0.01)
            if commit_first:
                first.commit()
            else:
                first.rollback()
            outcome = future.result(timeout=15)
        finally:
            # Release a held first transaction even if observation fails.
            first.rollback()
        return first_id, outcome, blocked


def _counts(connection, adjustment):
    return connection.execute(
        """
        SELECT
          (SELECT count(*) FROM accounting.v1_tax_recoverable_credit_evidence
           WHERE adjustment_posting_id = %s),
          (SELECT count(*) FROM accounting.v1_tax_recoverable_refund_evidence
           WHERE adjustment_posting_id = %s)
        """,
        (adjustment, adjustment),
    ).fetchone()


@pytest.mark.parametrize(
    ("module", "proof"),
    [
        (
            credit_helpers,
            "test_exact_recoverable_is_applied_to_exact_unpaid_return_and_blocks_cash_or_refund_duplicate",
        ),
        (
            credit_helpers,
            "test_credit_rejects_amount_mismatch_and_existing_cash_payment",
        ),
        (credit_helpers, "test_credit_post_forced_audit_failure_rolls_back_atomically"),
        (
            credit_helpers.refund_helpers,
            "test_refund_evidence_rejects_unapproved_cash_and_predating_refund",
        ),
        (
            credit_helpers.refund_helpers,
            "test_refund_post_forced_audit_failure_rolls_back_atomically",
        ),
    ],
    ids=[
        "credit-lifecycle",
        "credit-policy",
        "credit-audit-rollback",
        "refund-policy",
        "refund-audit-rollback",
    ],
)
def test_existing_protected_lifecycle_on_current_schema(
    database_url, monkeypatch, module, proof
):
    # Reuse the real policy assertions, but do not reinstall their historical
    # 0082-0090 fixtures over the already migrated current schema. In particular,
    # 0084 adds a non-idempotent constraint. All evidence/journal/audit writes
    # below execute the installed protected owners and roll back after the proof.
    monkeypatch.setattr(module, "DATABASE_URL", database_url)
    monkeypatch.setattr(module, "_install", lambda _connection: None)
    getattr(module, proof)()


def test_full_refund_still_posts_and_replays_on_current_schema(
    database_url, recoverable
):
    with _connect(database_url) as connection:
        try:
            evidence_id = _record(connection, recoverable, "refund")
            assert _record(connection, recoverable, "refund") == evidence_id
            journal_id = connection.execute(
                "SELECT accounting.prepare_v1_tax_recoverable_refund_journal(%s,%s)",
                (evidence_id, recoverable["actor"]),
            ).fetchone()[0]
            assert connection.execute(
                "SELECT line.line_number, account.code, line.debit, line.credit "
                "FROM accounting.journal_lines line "
                "JOIN accounting.accounts account ON account.id=line.account_id "
                "WHERE line.journal_entry_id=%s ORDER BY line.line_number",
                (journal_id,),
            ).fetchall() == [
                (1, "1010", Decimal("2.47"), Decimal("0.00")),
                (2, "1130", Decimal("0.00"), Decimal("2.47")),
            ]
            with (
                pytest.raises(
                    psycopg.Error, match="protected Management refund posting function"
                ),
                connection.transaction(),
            ):
                connection.execute(
                    "SELECT accounting.post_journal_entry(%s,%s)",
                    (journal_id, recoverable["actor"]),
                )
            arguments = {
                "refund_evidence_id": evidence_id,
                "actor_id": recoverable["actor"],
                "digest": "7" * 64,
                "refund_date": recoverable["date"],
                "period_id": recoverable["period"],
            }
            posting_id = credit_helpers.refund_helpers._post_refund(
                connection, **arguments
            )
            assert (
                credit_helpers.refund_helpers._post_refund(connection, **arguments)
                == posting_id
            )
            assert connection.execute(
                "SELECT refund_status FROM accounting.v1_tax_recoverable_refund_queue "
                "WHERE refund_evidence_id=%s",
                (evidence_id,),
            ).fetchone() == ("refund_realized",)
            assert (
                connection.execute(
                    "SELECT count(*) FROM accounting.v1_tax_recoverable_refund_postings "
                    "WHERE refund_evidence_id=%s",
                    (evidence_id,),
                ).fetchone()[0]
                == 1
            )
        finally:
            connection.rollback()


@pytest.mark.parametrize("first_kind", ["credit", "refund"])
def test_conflicting_realization_waits_then_rejects_after_other_commit(
    database_url, recoverable, first_kind
):
    second_kind = "refund" if first_kind == "credit" else "credit"
    first_id, outcome, blocked = _overlap(
        database_url, recoverable, first_kind, second_kind
    )
    with _connect(database_url) as verify:
        counts = _counts(verify, recoverable["adjustment"])
        assert blocked, (
            f"Competing realization did not wait; outcome={outcome}, persisted={counts}"
        )
        assert outcome[0] == "rejected", outcome
        assert isinstance(outcome[1], psycopg.errors.CheckViolation)
        expected_reason = (
            "refund evidence would duplicate realization"
            if second_kind == "refund"
            else "cannot also be applied as a tax credit"
        )
        assert expected_reason in str(outcome[1])
        assert counts == ((1, 0) if first_kind == "credit" else (0, 1))
        assert _record(verify, recoverable, first_kind) == first_id
        assert (
            verify.execute(
                "SELECT count(*) FROM core.audit_logs WHERE target_id=%s "
                "AND action LIKE 'accounting.tax.recoverable_%%.evidence_recorded'",
                (first_id,),
            ).fetchone()[0]
            == 1
        )


@pytest.mark.parametrize("first_kind", ["credit", "refund"])
def test_conflicting_realization_can_proceed_after_other_rollback(
    database_url, recoverable, first_kind
):
    second_kind = "refund" if first_kind == "credit" else "credit"
    _, outcome, blocked = _overlap(
        database_url, recoverable, first_kind, second_kind, commit_first=False
    )
    assert blocked, "The contender must reach a real lock before rollback releases it"
    assert outcome[0] == "accepted", outcome
    with _connect(database_url) as verify:
        assert _counts(verify, recoverable["adjustment"]) == (
            (1, 0) if second_kind == "credit" else (0, 1)
        )
        assert _record(verify, recoverable, second_kind) == outcome[1]


@pytest.mark.parametrize("kind", ["credit", "refund"])
def test_same_realization_retry_waits_and_returns_original_evidence(
    database_url, recoverable, kind
):
    first_id, outcome, blocked = _overlap(database_url, recoverable, kind, kind)
    assert blocked, "Idempotent replay must wait for the original evidence transaction"
    assert outcome == ("accepted", first_id)
    with _connect(database_url) as verify:
        assert _counts(verify, recoverable["adjustment"]) == (
            (1, 0) if kind == "credit" else (0, 1)
        )


@pytest.mark.parametrize("kind", ["credit", "refund"])
@pytest.mark.parametrize("isolation", ["REPEATABLE READ", "SERIALIZABLE"])
def test_realization_write_rejects_stale_snapshot_isolation(
    database_url, recoverable, kind, isolation
):
    with _connect(database_url) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL " + isolation)
        with pytest.raises(psycopg.errors.CheckViolation, match="READ COMMITTED"):
            _record(connection, recoverable, kind)
        connection.rollback()
    with _connect(database_url) as verify:
        assert _counts(verify, recoverable["adjustment"]) == (0, 0)
