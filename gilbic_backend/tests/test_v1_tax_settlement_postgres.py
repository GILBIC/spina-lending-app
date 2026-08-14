from __future__ import annotations

import importlib.util
import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

TEST_DIR = Path(__file__).resolve().parent
LIABILITY_HELPER_PATH = TEST_DIR / "test_v1_tax_liability_postgres.py"
_spec = importlib.util.spec_from_file_location(
    "v1_tax_settlement_liability_helpers", LIABILITY_HELPER_PATH
)
assert _spec is not None and _spec.loader is not None
liability_helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(liability_helpers)

tax_helpers = liability_helpers.tax_helpers
SQL_0085 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0085_add_protected_v1_tax_settlement.sql"
).read_text(encoding="utf-8")

SETTLEMENT_POLICY = "v1_tax_settlement_posting_v1"
SETTLEMENT_TOKEN = "9" * 64


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _install(connection: psycopg.Connection) -> None:
    liability_helpers._install(connection)
    connection.execute(_transaction_body(SQL_0085))


def _posted_dst_liability(connection: psycopg.Connection, suffix: str):
    actor_id = tax_helpers._management_actor(connection, suffix)
    loan_id, client_id, event_id, release_date = tax_helpers._simple_loan(
        connection, actor_id, suffix
    )
    period_id = liability_helpers._open_period(
        connection,
        suffix,
        release_date,
        release_date.replace(month=12, day=31),
    )
    rule_id = tax_helpers._record_rule(
        connection,
        actor_id=actor_id,
        tax_type="documentary_stamp_tax",
        key=f"dst-settle-{suffix}",
        effective_from=release_date,
        rate="0.0075000000",
        maturity_max_days=None,
        digest_char="a",
    )
    evidence_id = tax_helpers._record_dst(
        connection,
        actor_id=actor_id,
        loan_id=loan_id,
        event_id=event_id,
        rule_id=rule_id,
        tax_due="7.40",
        token="b",
    )
    connection.execute(
        "SELECT accounting.prepare_v1_tax_liability_journal(%s,%s,%s)",
        ("documentary_stamp_tax", evidence_id, actor_id),
    ).fetchone()[0]
    posting_id = liability_helpers._post(
        connection,
        tax_type="documentary_stamp_tax",
        evidence_id=evidence_id,
        actor_id=actor_id,
        evidence_digest="b" * 64,
        tax_due="7.40",
        expense_code="5310",
        posting_date=release_date,
        period_id=period_id,
    )
    return (
        actor_id,
        loan_id,
        client_id,
        event_id,
        release_date,
        period_id,
        rule_id,
        evidence_id,
        posting_id,
    )


def _record_return(
    connection: psycopg.Connection,
    *,
    actor_id,
    posting_id,
    release_date,
    idempotency_key,
    digest_char: str = "c",
):
    return connection.execute(
        """
        SELECT accounting.record_v1_tax_return_evidence(
            %s,%s,'documentary_stamp_tax',%s,%s,%s,7.40,
            %s,%s,%s,%s,%s
        )
        """,
        (
            actor_id,
            idempotency_key,
            release_date,
            release_date,
            release_date + timedelta(days=1),
            f"BIR-2000-{digest_char}",
            f"RETURN-EVIDENCE-{digest_char}",
            digest_char * 64,
            "Management retained the exact filed DST return for disposable settlement validation.",
            [posting_id],
        ),
    ).fetchone()[0]


def _record_payment(
    connection: psycopg.Connection,
    *,
    actor_id,
    return_id,
    release_date,
    idempotency_key,
    digest_char: str = "d",
):
    return connection.execute(
        """
        SELECT accounting.record_v1_tax_payment_evidence(
            %s,%s,%s,%s,7.40,'cash_bank_gcash',%s,%s,%s,%s
        )
        """,
        (
            actor_id,
            idempotency_key,
            return_id,
            release_date + timedelta(days=2),
            f"BIR-PAYMENT-{digest_char}",
            f"PAYMENT-EVIDENCE-{digest_char}",
            digest_char * 64,
            "Management retained exact BIR payment proof and bank/GCash funding evidence for disposable validation.",
        ),
    ).fetchone()[0]


def _post_settlement(
    connection: psycopg.Connection,
    *,
    payment_id,
    actor_id,
    release_date,
    period_id,
    return_digest: str = "c" * 64,
    payment_digest: str = "d" * 64,
    token: str = SETTLEMENT_TOKEN,
):
    return connection.execute(
        """
        SELECT accounting.post_v1_tax_settlement_journal(
            %s,%s,%s,%s,%s,7.40,'2100','1030',%s,%s,%s
        )
        """,
        (
            payment_id,
            actor_id,
            token,
            return_digest,
            payment_digest,
            release_date + timedelta(days=2),
            period_id,
            SETTLEMENT_POLICY,
        ),
    ).fetchone()[0]


def _queue(connection: psycopg.Connection, return_id):
    return connection.execute(
        """
        SELECT settlement_status, settlement_blocker, liability_count,
               current_exact_count, liability_total, payment_evidence_id,
               journal_entry_id, journal_status, entry_number,
               settlement_posting_id, cash_account_code,
               tax_settlement_enabled, tax_adjustment_reversal_enabled,
               automatic_source_posting
        FROM accounting.v1_tax_settlement_queue
        WHERE tax_return_id=%s
        """,
        (return_id,),
    ).fetchone()


def test_return_payment_and_settlement_are_exact_idempotent_and_do_not_reexpense_tax() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            (
                actor_id,
                _,
                _,
                _,
                release_date,
                period_id,
                _,
                _,
                liability_posting_id,
            ) = _posted_dst_liability(connection, suffix)

            return_key = uuid4()
            return_id = _record_return(
                connection,
                actor_id=actor_id,
                posting_id=liability_posting_id,
                release_date=release_date,
                idempotency_key=return_key,
            )
            assert _record_return(
                connection,
                actor_id=actor_id,
                posting_id=liability_posting_id,
                release_date=release_date,
                idempotency_key=return_key,
            ) == return_id

            waiting = _queue(connection, return_id)
            assert waiting is not None
            assert waiting[0] == "return_recorded_awaiting_payment"
            assert waiting[2:5] == (1, 1, Decimal("7.40"))
            assert waiting[11:] == (True, False, False)

            with pytest.raises(psycopg.Error, match="does not exactly reconcile"):
                with connection.transaction():
                    connection.execute(
                        """
                        SELECT accounting.record_v1_tax_return_evidence(
                            %s,%s,'documentary_stamp_tax',%s,%s,%s,7.41,
                            'BAD-RETURN','BAD-EVIDENCE',%s,%s,%s
                        )
                        """,
                        (
                            actor_id,
                            uuid4(),
                            release_date,
                            release_date,
                            release_date + timedelta(days=1),
                            "f" * 64,
                            "Management intentionally submits a mismatched disposable return to prove fail-closed reconciliation.",
                            [liability_posting_id],
                        ),
                    )

            payment_key = uuid4()
            payment_id = _record_payment(
                connection,
                actor_id=actor_id,
                return_id=return_id,
                release_date=release_date,
                idempotency_key=payment_key,
            )
            assert _record_payment(
                connection,
                actor_id=actor_id,
                return_id=return_id,
                release_date=release_date,
                idempotency_key=payment_key,
            ) == payment_id

            ready = _queue(connection, return_id)
            assert ready is not None
            assert ready[0] == "payment_evidence_ready"
            assert ready[5] == payment_id
            assert ready[10] == "1030"

            journal_id = connection.execute(
                "SELECT accounting.prepare_v1_tax_settlement_journal(%s,%s)",
                (payment_id, actor_id),
            ).fetchone()[0]
            retry_journal_id = connection.execute(
                "SELECT accounting.prepare_v1_tax_settlement_journal(%s,%s)",
                (payment_id, actor_id),
            ).fetchone()[0]
            assert retry_journal_id == journal_id

            lines = connection.execute(
                """
                SELECT line.line_number, account.code, line.debit, line.credit
                FROM accounting.journal_lines line
                JOIN accounting.accounts account ON account.id=line.account_id
                WHERE line.journal_entry_id=%s ORDER BY line.line_number
                """,
                (journal_id,),
            ).fetchall()
            assert lines == [
                (1, "2100", Decimal("7.40"), Decimal("0.00")),
                (2, "1030", Decimal("0.00"), Decimal("7.40")),
            ]

            with pytest.raises(psycopg.Error, match="protected Management settlement posting function"):
                with connection.transaction():
                    connection.execute(
                        "SELECT accounting.post_journal_entry(%s,%s)",
                        (journal_id, actor_id),
                    )

            settlement_posting_id = _post_settlement(
                connection,
                payment_id=payment_id,
                actor_id=actor_id,
                release_date=release_date,
                period_id=period_id,
            )
            assert _post_settlement(
                connection,
                payment_id=payment_id,
                actor_id=actor_id,
                release_date=release_date,
                period_id=period_id,
            ) == settlement_posting_id

            settled = _queue(connection, return_id)
            assert settled is not None
            assert settled[0] == "settled"
            assert settled[7] == "posted"
            assert settled[8] is not None
            assert settled[9] == settlement_posting_id

            with pytest.raises(psycopg.Error, match="immutable retry identity"):
                with connection.transaction():
                    _post_settlement(
                        connection,
                        payment_id=payment_id,
                        actor_id=actor_id,
                        release_date=release_date,
                        period_id=period_id,
                        token="8" * 64,
                    )

            with pytest.raises(psycopg.Error, match="immutable"):
                with connection.transaction():
                    connection.execute(
                        "UPDATE accounting.v1_tax_payment_evidence SET payment_amount=0 WHERE id=%s",
                        (payment_id,),
                    )

            with pytest.raises(psycopg.Error, match="cannot be reversed through the manual General Journal"):
                with connection.transaction():
                    connection.execute(
                        "SELECT accounting.create_reversal_draft(%s,%s,%s,%s)",
                        (
                            journal_id,
                            actor_id,
                            release_date + timedelta(days=2),
                            "manual settlement reversal attempt",
                        ),
                    )
        finally:
            connection.rollback()


def test_settlement_post_forced_audit_failure_rolls_back_atomically() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            (
                actor_id,
                _,
                _,
                _,
                release_date,
                period_id,
                _,
                _,
                liability_posting_id,
            ) = _posted_dst_liability(connection, suffix)
            return_id = _record_return(
                connection,
                actor_id=actor_id,
                posting_id=liability_posting_id,
                release_date=release_date,
                idempotency_key=uuid4(),
            )
            payment_id = _record_payment(
                connection,
                actor_id=actor_id,
                return_id=return_id,
                release_date=release_date,
                idempotency_key=uuid4(),
            )
            journal_id = connection.execute(
                "SELECT accounting.prepare_v1_tax_settlement_journal(%s,%s)",
                (payment_id, actor_id),
            ).fetchone()[0]

            with pytest.raises(psycopg.Error, match="Forced V1 tax settlement audit failure"):
                with connection.transaction():
                    connection.execute(
                        "SELECT set_config('accounting.v1_tax_settlement_force_audit_failure','on',true)"
                    )
                    _post_settlement(
                        connection,
                        payment_id=payment_id,
                        actor_id=actor_id,
                        release_date=release_date,
                        period_id=period_id,
                    )

            assert connection.execute(
                "SELECT status, entry_number FROM accounting.journal_entries WHERE id=%s",
                (journal_id,),
            ).fetchone() == ("draft", None)
            assert connection.execute(
                "SELECT count(*) FROM accounting.v1_tax_settlement_postings WHERE journal_entry_id=%s",
                (journal_id,),
            ).fetchone()[0] == 0
        finally:
            connection.rollback()


def test_return_becomes_blocked_when_underlying_posted_liability_evidence_is_superseded() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            (
                actor_id,
                loan_id,
                _,
                event_id,
                release_date,
                _,
                old_rule_id,
                old_evidence_id,
                liability_posting_id,
            ) = _posted_dst_liability(connection, suffix)
            return_id = _record_return(
                connection,
                actor_id=actor_id,
                posting_id=liability_posting_id,
                release_date=release_date,
                idempotency_key=uuid4(),
            )

            new_rule_id = tax_helpers._record_rule(
                connection,
                actor_id=actor_id,
                tax_type="documentary_stamp_tax",
                key=f"dst-settle-{suffix}",
                effective_from=release_date,
                rate="0.0080000000",
                maturity_max_days=None,
                digest_char="e",
                supersedes=old_rule_id,
            )
            tax_helpers._record_dst(
                connection,
                actor_id=actor_id,
                loan_id=loan_id,
                event_id=event_id,
                rule_id=new_rule_id,
                tax_due="7.89",
                token="f",
                supersedes=old_evidence_id,
            )

            blocked = _queue(connection, return_id)
            assert blocked is not None
            assert blocked[0] == "blocked_return_composition_changed"
            assert blocked[2:4] == (1, 0)

            payment_id = _record_payment(
                connection,
                actor_id=actor_id,
                return_id=return_id,
                release_date=release_date,
                idempotency_key=uuid4(),
            )
            with pytest.raises(psycopg.Error, match="missing, stale, reversed, superseded"):
                with connection.transaction():
                    connection.execute(
                        "SELECT accounting.prepare_v1_tax_settlement_journal(%s,%s)",
                        (payment_id, actor_id),
                    )
        finally:
            connection.rollback()
