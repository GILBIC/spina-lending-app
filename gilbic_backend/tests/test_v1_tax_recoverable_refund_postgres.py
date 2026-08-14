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
ADDITIONAL_HELPER_PATH = TEST_DIR / "test_v1_tax_additional_amendment_postgres.py"
_spec = importlib.util.spec_from_file_location(
    "v1_tax_recoverable_refund_additional_helpers", ADDITIONAL_HELPER_PATH
)
assert _spec is not None and _spec.loader is not None
additional_helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(additional_helpers)
adjustment_helpers = additional_helpers.adjustment_helpers
settlement_helpers = additional_helpers.settlement_helpers

SQL_0089 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0089_add_protected_v1_tax_recoverable_refund.sql"
).read_text(encoding="utf-8")

REFUND_POLICY = "v1_tax_recoverable_refund_posting_v1"
REFUND_TOKEN = "9" * 64


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    return body[len("BEGIN;") : -len("COMMIT;")].strip()


def _install(connection: psycopg.Connection) -> None:
    additional_helpers._install(connection)
    connection.execute(_transaction_body(SQL_0089))


def _posted_recoverable(connection: psycopg.Connection, suffix: str):
    (
        actor_id,
        loan_id,
        _,
        event_id,
        release_date,
        period_id,
        old_rule_id,
        old_evidence_id,
        liability_posting_id,
    ) = settlement_helpers._posted_dst_liability(connection, suffix)

    return_id = settlement_helpers._record_return(
        connection,
        actor_id=actor_id,
        posting_id=liability_posting_id,
        release_date=release_date,
        idempotency_key=uuid4(),
    )
    payment_id = settlement_helpers._record_payment(
        connection,
        actor_id=actor_id,
        return_id=return_id,
        release_date=release_date,
        idempotency_key=uuid4(),
    )
    connection.execute(
        "SELECT accounting.prepare_v1_tax_settlement_journal(%s,%s)",
        (payment_id, actor_id),
    ).fetchone()[0]
    settlement_helpers._post_settlement(
        connection,
        payment_id=payment_id,
        actor_id=actor_id,
        release_date=release_date,
        period_id=period_id,
    )

    _, replacement_evidence_id = adjustment_helpers._lower_dst_replacement(
        connection,
        actor_id=actor_id,
        loan_id=loan_id,
        event_id=event_id,
        release_date=release_date,
        old_rule_id=old_rule_id,
        old_evidence_id=old_evidence_id,
        suffix=suffix,
    )
    adjustment_date = release_date + timedelta(days=3)
    adjustment_id = adjustment_helpers._record_adjustment(
        connection,
        actor_id=actor_id,
        liability_posting_id=liability_posting_id,
        replacement_evidence_id=replacement_evidence_id,
        kind="recognize_settled_tax_recoverable",
        adjustment_date=adjustment_date,
        idempotency_key=uuid4(),
        digest_char="2",
    )
    connection.execute(
        "SELECT accounting.prepare_v1_tax_adjustment_journal(%s,%s)",
        (adjustment_id, actor_id),
    ).fetchone()[0]
    adjustment_posting_id = adjustment_helpers._post_adjustment(
        connection,
        adjustment_evidence_id=adjustment_id,
        actor_id=actor_id,
        digest="2" * 64,
        original_due="7.40",
        replacement_due="4.93",
        adjustment_amount="2.47",
        debit_code="1130",
        credit_code="5310",
        posting_date=adjustment_date,
        period_id=period_id,
    )
    return actor_id, adjustment_id, adjustment_posting_id, adjustment_date, period_id


def _record_refund(
    connection: psycopg.Connection,
    *,
    actor_id,
    adjustment_posting_id,
    refund_date,
    idempotency_key,
    digest_char: str,
    cash_code: str = "1010",
):
    return connection.execute(
        """
        SELECT accounting.record_v1_tax_recoverable_refund_evidence(
            %s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        """,
        (
            actor_id,
            idempotency_key,
            adjustment_posting_id,
            refund_date,
            cash_code,
            f"BIR-REFUND-{digest_char}",
            f"RETAINED-REFUND-AUTHORITY-{digest_char}",
            digest_char * 64,
            "Management retained exact synthetic refund receipt and authority evidence for protected disposable Tax Recoverable validation.",
        ),
    ).fetchone()[0]


def _post_refund(
    connection: psycopg.Connection,
    *,
    refund_evidence_id,
    actor_id,
    digest: str,
    refund_date,
    period_id,
    cash_code: str = "1010",
    token: str = REFUND_TOKEN,
):
    return connection.execute(
        """
        SELECT accounting.post_v1_tax_recoverable_refund_journal(
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        """,
        (
            refund_evidence_id,
            actor_id,
            token,
            digest,
            Decimal("2.47"),
            cash_code,
            "1130",
            refund_date,
            period_id,
            REFUND_POLICY,
        ),
    ).fetchone()[0]


def test_exact_posted_recoverable_is_refunded_in_full_idempotently() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            actor_id, adjustment_id, adjustment_posting_id, adjustment_date, period_id = (
                _posted_recoverable(connection, suffix)
            )
            refund_date = adjustment_date + timedelta(days=2)
            evidence_key = uuid4()
            refund_id = _record_refund(
                connection,
                actor_id=actor_id,
                adjustment_posting_id=adjustment_posting_id,
                refund_date=refund_date,
                idempotency_key=evidence_key,
                digest_char="a",
            )
            assert _record_refund(
                connection,
                actor_id=actor_id,
                adjustment_posting_id=adjustment_posting_id,
                refund_date=refund_date,
                idempotency_key=evidence_key,
                digest_char="a",
            ) == refund_id

            assert connection.execute(
                """
                SELECT adjustment_evidence_id, refund_amount, cash_account_code,
                       refund_status, tax_recoverable_refund_realization_enabled,
                       tax_recoverable_credit_application_enabled, automatic_source_posting
                FROM accounting.v1_tax_recoverable_refund_queue
                WHERE refund_evidence_id=%s
                """,
                (refund_id,),
            ).fetchone() == (
                adjustment_id,
                Decimal("2.47"),
                "1010",
                "refund_evidence_ready",
                True,
                False,
                False,
            )

            journal_id = connection.execute(
                "SELECT accounting.prepare_v1_tax_recoverable_refund_journal(%s,%s)",
                (refund_id, actor_id),
            ).fetchone()[0]
            assert connection.execute(
                "SELECT accounting.prepare_v1_tax_recoverable_refund_journal(%s,%s)",
                (refund_id, actor_id),
            ).fetchone()[0] == journal_id

            assert connection.execute(
                """
                SELECT line.line_number, account.code, line.debit, line.credit
                FROM accounting.journal_lines line
                JOIN accounting.accounts account ON account.id=line.account_id
                WHERE line.journal_entry_id=%s ORDER BY line.line_number
                """,
                (journal_id,),
            ).fetchall() == [
                (1, "1010", Decimal("2.47"), Decimal("0.00")),
                (2, "1130", Decimal("0.00"), Decimal("2.47")),
            ]

            with pytest.raises(psycopg.Error, match="protected Management refund posting function"):
                with connection.transaction():
                    connection.execute(
                        "SELECT accounting.post_journal_entry(%s,%s)",
                        (journal_id, actor_id),
                    )

            refund_posting_id = _post_refund(
                connection,
                refund_evidence_id=refund_id,
                actor_id=actor_id,
                digest="a" * 64,
                refund_date=refund_date,
                period_id=period_id,
            )
            assert _post_refund(
                connection,
                refund_evidence_id=refund_id,
                actor_id=actor_id,
                digest="a" * 64,
                refund_date=refund_date,
                period_id=period_id,
            ) == refund_posting_id

            assert connection.execute(
                """
                SELECT refund_status, tax_recoverable_refund_realization_enabled,
                       tax_recoverable_credit_application_enabled, automatic_source_posting
                FROM accounting.v1_tax_recoverable_refund_queue
                WHERE refund_evidence_id=%s
                """,
                (refund_id,),
            ).fetchone() == ("refund_realized", True, False, False)

            assert connection.execute(
                "SELECT * FROM accounting.v1_tax_recoverable_controls"
            ).fetchone() == (True, False, False, False)

            with pytest.raises(psycopg.Error, match="already has immutable refund realization evidence"):
                with connection.transaction():
                    _record_refund(
                        connection,
                        actor_id=actor_id,
                        adjustment_posting_id=adjustment_posting_id,
                        refund_date=refund_date,
                        idempotency_key=uuid4(),
                        digest_char="b",
                    )
        finally:
            connection.rollback()


def test_refund_evidence_rejects_unapproved_cash_and_predating_refund() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            actor_id, _, adjustment_posting_id, adjustment_date, _ = _posted_recoverable(
                connection, suffix
            )

            with pytest.raises(psycopg.Error, match="approved cash/bank account"):
                with connection.transaction():
                    _record_refund(
                        connection,
                        actor_id=actor_id,
                        adjustment_posting_id=adjustment_posting_id,
                        refund_date=adjustment_date,
                        idempotency_key=uuid4(),
                        digest_char="c",
                        cash_code="1020",
                    )

            with pytest.raises(psycopg.Error, match="cannot predate recognition"):
                with connection.transaction():
                    _record_refund(
                        connection,
                        actor_id=actor_id,
                        adjustment_posting_id=adjustment_posting_id,
                        refund_date=adjustment_date - timedelta(days=1),
                        idempotency_key=uuid4(),
                        digest_char="d",
                    )
        finally:
            connection.rollback()


def test_refund_post_forced_audit_failure_rolls_back_atomically() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            actor_id, _, adjustment_posting_id, adjustment_date, period_id = _posted_recoverable(
                connection, suffix
            )
            refund_date = adjustment_date + timedelta(days=2)
            refund_id = _record_refund(
                connection,
                actor_id=actor_id,
                adjustment_posting_id=adjustment_posting_id,
                refund_date=refund_date,
                idempotency_key=uuid4(),
                digest_char="e",
            )
            journal_id = connection.execute(
                "SELECT accounting.prepare_v1_tax_recoverable_refund_journal(%s,%s)",
                (refund_id, actor_id),
            ).fetchone()[0]

            with pytest.raises(psycopg.Error, match="Forced V1 Tax Recoverable refund audit failure"):
                with connection.transaction():
                    connection.execute(
                        "SELECT set_config('accounting.v1_tax_recoverable_refund_force_audit_failure','on',true)"
                    )
                    _post_refund(
                        connection,
                        refund_evidence_id=refund_id,
                        actor_id=actor_id,
                        digest="e" * 64,
                        refund_date=refund_date,
                        period_id=period_id,
                    )

            assert connection.execute(
                "SELECT status, entry_number FROM accounting.journal_entries WHERE id=%s",
                (journal_id,),
            ).fetchone() == ("draft", None)
            assert connection.execute(
                """
                SELECT count(*) FROM accounting.v1_tax_recoverable_refund_postings
                WHERE journal_entry_id=%s
                """,
                (journal_id,),
            ).fetchone()[0] == 0
        finally:
            connection.rollback()
