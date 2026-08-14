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
REFUND_HELPER_PATH = TEST_DIR / "test_v1_tax_recoverable_refund_postgres.py"
_spec = importlib.util.spec_from_file_location(
    "v1_tax_recoverable_credit_refund_helpers", REFUND_HELPER_PATH
)
assert _spec is not None and _spec.loader is not None
refund_helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(refund_helpers)
settlement_helpers = refund_helpers.settlement_helpers
liability_helpers = settlement_helpers.liability_helpers
tax_helpers = settlement_helpers.tax_helpers

SQL_0090 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0090_add_protected_v1_tax_recoverable_credit_application.sql"
).read_text(encoding="utf-8")

CREDIT_POLICY = "v1_tax_recoverable_credit_posting_v1"
CREDIT_TOKEN = "a" * 64


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    return body[len("BEGIN;") : -len("COMMIT;")].strip()


def _install(connection: psycopg.Connection) -> None:
    refund_helpers._install(connection)
    connection.execute(_transaction_body(SQL_0090))


def _target_return_247(
    connection: psycopg.Connection,
    *,
    actor_id,
    period_id,
    suffix: str,
):
    loan_id, _, event_id, release_date = tax_helpers._simple_loan(
        connection, actor_id, f"{suffix}target"
    )
    rule_id = tax_helpers._record_rule(
        connection,
        actor_id=actor_id,
        tax_type="documentary_stamp_tax",
        key=f"dst-credit-target-{suffix}",
        effective_from=release_date,
        rate="0.0025000000",
        maturity_max_days=None,
        digest_char="3",
    )
    evidence_id = tax_helpers._record_dst(
        connection,
        actor_id=actor_id,
        loan_id=loan_id,
        event_id=event_id,
        rule_id=rule_id,
        tax_due="2.47",
        token="4",
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
        evidence_digest="4" * 64,
        tax_due="2.47",
        expense_code="5310",
        posting_date=release_date,
        period_id=period_id,
    )
    return_id = connection.execute(
        """
        SELECT accounting.record_v1_tax_return_evidence(
            %s,%s,'documentary_stamp_tax',%s,%s,%s,2.47,
            %s,%s,%s,%s,%s
        )
        """,
        (
            actor_id,
            uuid4(),
            release_date,
            release_date,
            release_date + timedelta(days=1),
            f"BIR-2000-CREDIT-{suffix}",
            f"RETURN-CREDIT-EVIDENCE-{suffix}",
            "5" * 64,
            "Management retained exact synthetic same-tax-type return evidence for full Tax Recoverable credit application validation.",
            [posting_id],
        ),
    ).fetchone()[0]
    return return_id, release_date


def _target_return_740(
    connection: psycopg.Connection,
    *,
    actor_id,
    period_id,
    suffix: str,
):
    """Build a mismatched DST return inside the already-open disposable period."""
    loan_id, _, event_id, release_date = tax_helpers._simple_loan(
        connection, actor_id, f"{suffix}mismatch"
    )
    rule_id = tax_helpers._record_rule(
        connection,
        actor_id=actor_id,
        tax_type="documentary_stamp_tax",
        key=f"dst-credit-mismatch-{suffix}",
        effective_from=release_date,
        rate="0.0075000000",
        maturity_max_days=None,
        digest_char="c",
    )
    evidence_id = tax_helpers._record_dst(
        connection,
        actor_id=actor_id,
        loan_id=loan_id,
        event_id=event_id,
        rule_id=rule_id,
        tax_due="7.40",
        token="d",
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
        evidence_digest="d" * 64,
        tax_due="7.40",
        expense_code="5310",
        posting_date=release_date,
        period_id=period_id,
    )
    return_id = settlement_helpers._record_return(
        connection,
        actor_id=actor_id,
        posting_id=posting_id,
        release_date=release_date,
        idempotency_key=uuid4(),
        digest_char="e",
    )
    return return_id, release_date


def _record_credit(
    connection: psycopg.Connection,
    *,
    actor_id,
    adjustment_posting_id,
    target_return_id,
    application_date,
    idempotency_key,
    digest_char: str,
):
    return connection.execute(
        """
        SELECT accounting.record_v1_tax_recoverable_credit_evidence(
            %s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        """,
        (
            actor_id,
            idempotency_key,
            adjustment_posting_id,
            target_return_id,
            application_date,
            f"BIR-TAX-CREDIT-APPLICATION-{digest_char}",
            f"RETAINED-TAX-CREDIT-AUTHORITY-{digest_char}",
            digest_char * 64,
            "Management retained exact synthetic legally usable tax-credit authority and application evidence for protected disposable validation.",
        ),
    ).fetchone()[0]


def _post_credit(
    connection: psycopg.Connection,
    *,
    credit_evidence_id,
    actor_id,
    digest: str,
    application_date,
    period_id,
    token: str = CREDIT_TOKEN,
):
    return connection.execute(
        """
        SELECT accounting.post_v1_tax_recoverable_credit_journal(
            %s,%s,%s,%s,2.47,'2100','1130',%s,%s,%s
        )
        """,
        (
            credit_evidence_id,
            actor_id,
            token,
            digest,
            application_date,
            period_id,
            CREDIT_POLICY,
        ),
    ).fetchone()[0]


def test_exact_recoverable_is_applied_to_exact_unpaid_return_and_blocks_cash_or_refund_duplicate() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:8]
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            actor_id, _, adjustment_posting_id, adjustment_date, period_id = (
                refund_helpers._posted_recoverable(connection, suffix)
            )
            target_return_id, target_release_date = _target_return_247(
                connection,
                actor_id=actor_id,
                period_id=period_id,
                suffix=suffix,
            )
            application_date = max(
                adjustment_date + timedelta(days=2),
                target_release_date + timedelta(days=2),
            )
            evidence_key = uuid4()
            credit_id = _record_credit(
                connection,
                actor_id=actor_id,
                adjustment_posting_id=adjustment_posting_id,
                target_return_id=target_return_id,
                application_date=application_date,
                idempotency_key=evidence_key,
                digest_char="b",
            )
            assert _record_credit(
                connection,
                actor_id=actor_id,
                adjustment_posting_id=adjustment_posting_id,
                target_return_id=target_return_id,
                application_date=application_date,
                idempotency_key=evidence_key,
                digest_char="b",
            ) == credit_id

            assert connection.execute(
                """
                SELECT credit_amount, target_declared_tax_due, credit_status,
                       tax_recoverable_refund_realization_enabled,
                       tax_recoverable_credit_application_enabled,
                       partial_tax_recoverable_realization_enabled,
                       automatic_source_posting
                FROM accounting.v1_tax_recoverable_credit_queue
                WHERE credit_evidence_id=%s
                """,
                (credit_id,),
            ).fetchone() == (
                Decimal("2.47"),
                Decimal("2.47"),
                "credit_evidence_ready",
                True,
                True,
                False,
                False,
            )

            with pytest.raises(psycopg.Error, match="reserved for protected Tax Recoverable credit application"):
                with connection.transaction():
                    connection.execute(
                        """
                        SELECT accounting.record_v1_tax_payment_evidence(
                            %s,%s,%s,%s,2.47,'cash_bank_gcash',%s,%s,%s,%s
                        )
                        """,
                        (
                            actor_id,
                            uuid4(),
                            target_return_id,
                            application_date,
                            "BIR-CASH-DUPLICATE",
                            "PAYMENT-EVIDENCE-DUPLICATE",
                            "6" * 64,
                            "Management synthetic duplicate cash-payment evidence must be rejected after Tax Recoverable credit reservation.",
                        ),
                    )

            journal_id = connection.execute(
                "SELECT accounting.prepare_v1_tax_recoverable_credit_journal(%s,%s)",
                (credit_id, actor_id),
            ).fetchone()[0]
            assert connection.execute(
                "SELECT accounting.prepare_v1_tax_recoverable_credit_journal(%s,%s)",
                (credit_id, actor_id),
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
                (1, "2100", Decimal("2.47"), Decimal("0.00")),
                (2, "1130", Decimal("0.00"), Decimal("2.47")),
            ]

            with pytest.raises(psycopg.Error, match="protected Management credit posting function"):
                with connection.transaction():
                    connection.execute(
                        "SELECT accounting.post_journal_entry(%s,%s)",
                        (journal_id, actor_id),
                    )

            posting_id = _post_credit(
                connection,
                credit_evidence_id=credit_id,
                actor_id=actor_id,
                digest="b" * 64,
                application_date=application_date,
                period_id=period_id,
            )
            assert _post_credit(
                connection,
                credit_evidence_id=credit_id,
                actor_id=actor_id,
                digest="b" * 64,
                application_date=application_date,
                period_id=period_id,
            ) == posting_id

            assert connection.execute(
                """
                SELECT credit_status, tax_recoverable_credit_application_enabled,
                       partial_tax_recoverable_realization_enabled, automatic_source_posting
                FROM accounting.v1_tax_recoverable_credit_queue
                WHERE credit_evidence_id=%s
                """,
                (credit_id,),
            ).fetchone() == ("credit_applied", True, False, False)
            assert connection.execute(
                "SELECT * FROM accounting.v1_tax_recoverable_controls"
            ).fetchone() == (True, True, False, False)

            with pytest.raises(psycopg.Error, match="reserved for protected tax-credit application"):
                with connection.transaction():
                    refund_helpers._record_refund(
                        connection,
                        actor_id=actor_id,
                        adjustment_posting_id=adjustment_posting_id,
                        refund_date=application_date,
                        idempotency_key=uuid4(),
                        digest_char="c",
                    )
        finally:
            connection.rollback()


def test_credit_rejects_amount_mismatch_and_existing_cash_payment() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:8]
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            actor_id, _, adjustment_posting_id, adjustment_date, period_id = (
                refund_helpers._posted_recoverable(connection, suffix)
            )

            mismatch_return_id, target_release = _target_return_740(
                connection,
                actor_id=actor_id,
                period_id=period_id,
                suffix=suffix,
            )
            with pytest.raises(psycopg.Error, match="full-only"):
                with connection.transaction():
                    _record_credit(
                        connection,
                        actor_id=actor_id,
                        adjustment_posting_id=adjustment_posting_id,
                        target_return_id=mismatch_return_id,
                        application_date=max(adjustment_date, target_release + timedelta(days=2)),
                        idempotency_key=uuid4(),
                        digest_char="e",
                    )

            exact_return_id, exact_release = _target_return_247(
                connection,
                actor_id=actor_id,
                period_id=period_id,
                suffix=f"{suffix}cash",
            )
            payment_date = max(adjustment_date + timedelta(days=2), exact_release + timedelta(days=2))
            connection.execute(
                """
                SELECT accounting.record_v1_tax_payment_evidence(
                    %s,%s,%s,%s,2.47,'cash_bank_gcash',%s,%s,%s,%s
                )
                """,
                (
                    actor_id,
                    uuid4(),
                    exact_return_id,
                    payment_date,
                    "BIR-CASH-EXISTS",
                    "PAYMENT-EVIDENCE-EXISTS",
                    "7" * 64,
                    "Management retained synthetic cash-payment evidence to prove Tax Recoverable credit application cannot duplicate settlement.",
                ),
            ).fetchone()[0]
            with pytest.raises(psycopg.Error, match="already has cash-payment or settlement evidence"):
                with connection.transaction():
                    _record_credit(
                        connection,
                        actor_id=actor_id,
                        adjustment_posting_id=adjustment_posting_id,
                        target_return_id=exact_return_id,
                        application_date=payment_date,
                        idempotency_key=uuid4(),
                        digest_char="f",
                    )
        finally:
            connection.rollback()


def test_credit_post_forced_audit_failure_rolls_back_atomically() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:8]
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            actor_id, _, adjustment_posting_id, adjustment_date, period_id = (
                refund_helpers._posted_recoverable(connection, suffix)
            )
            target_return_id, target_release = _target_return_247(
                connection,
                actor_id=actor_id,
                period_id=period_id,
                suffix=f"{suffix}rollback",
            )
            application_date = max(adjustment_date + timedelta(days=2), target_release + timedelta(days=2))
            credit_id = _record_credit(
                connection,
                actor_id=actor_id,
                adjustment_posting_id=adjustment_posting_id,
                target_return_id=target_return_id,
                application_date=application_date,
                idempotency_key=uuid4(),
                digest_char="8",
            )
            journal_id = connection.execute(
                "SELECT accounting.prepare_v1_tax_recoverable_credit_journal(%s,%s)",
                (credit_id, actor_id),
            ).fetchone()[0]

            with pytest.raises(psycopg.Error, match="Forced V1 Tax Recoverable credit audit failure"):
                with connection.transaction():
                    connection.execute(
                        "SELECT set_config('accounting.v1_tax_recoverable_credit_force_audit_failure','on',true)"
                    )
                    _post_credit(
                        connection,
                        credit_evidence_id=credit_id,
                        actor_id=actor_id,
                        digest="8" * 64,
                        application_date=application_date,
                        period_id=period_id,
                    )

            assert connection.execute(
                "SELECT status, entry_number FROM accounting.journal_entries WHERE id=%s",
                (journal_id,),
            ).fetchone() == ("draft", None)
            assert connection.execute(
                """
                SELECT count(*) FROM accounting.v1_tax_recoverable_credit_postings
                WHERE journal_entry_id=%s
                """,
                (journal_id,),
            ).fetchone()[0] == 0
        finally:
            connection.rollback()
