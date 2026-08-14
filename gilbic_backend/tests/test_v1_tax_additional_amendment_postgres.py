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
ADJUSTMENT_HELPER_PATH = TEST_DIR / "test_v1_tax_adjustment_postgres.py"
_spec = importlib.util.spec_from_file_location(
    "v1_tax_additional_amendment_adjustment_helpers", ADJUSTMENT_HELPER_PATH
)
assert _spec is not None and _spec.loader is not None
adjustment_helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(adjustment_helpers)
settlement_helpers = adjustment_helpers.settlement_helpers
tax_helpers = adjustment_helpers.tax_helpers

SQL_0087 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0087_add_protected_v1_tax_additional_amendment.sql"
).read_text(encoding="utf-8")
SQL_0088 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0088_add_protected_v1_tax_additional_settlement.sql"
).read_text(encoding="utf-8")

LIABILITY_POLICY = "v1_tax_additional_liability_posting_v1"
SETTLEMENT_POLICY = "v1_tax_additional_settlement_posting_v1"
LIABILITY_TOKEN = "6" * 64
SETTLEMENT_TOKEN = "8" * 64


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    return body[len("BEGIN;") : -len("COMMIT;")].strip()


def _install(connection: psycopg.Connection) -> None:
    adjustment_helpers._install(connection)
    connection.execute(_transaction_body(SQL_0087))
    connection.execute(_transaction_body(SQL_0088))


def _higher_dst_replacement(connection, *, actor_id, loan_id, event_id, release_date, old_rule_id, old_evidence_id, suffix):
    rule_id = tax_helpers._record_rule(
        connection,
        actor_id=actor_id,
        tax_type="documentary_stamp_tax",
        key=f"dst-settle-{suffix}",
        effective_from=release_date,
        rate="0.0100000000",
        maturity_max_days=None,
        digest_char="e",
        supersedes=old_rule_id,
    )
    evidence_id = tax_helpers._record_dst(
        connection,
        actor_id=actor_id,
        loan_id=loan_id,
        event_id=event_id,
        rule_id=rule_id,
        tax_due="9.86",
        token="f",
        supersedes=old_evidence_id,
    )
    return evidence_id


def _record_amendment(connection, *, actor_id, return_id, liability_posting_id, replacement_evidence_id, amendment_date, recognition_date, digest_char, basis="amended_return"):
    return connection.execute(
        """
        SELECT accounting.record_v1_tax_additional_amendment_evidence(
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        """,
        (
            actor_id,
            uuid4(),
            return_id,
            liability_posting_id,
            replacement_evidence_id,
            basis,
            amendment_date,
            recognition_date,
            f"BIR-AMENDMENT-{digest_char}",
            f"RETAINED-AMENDMENT-{digest_char}",
            digest_char * 64,
            "Management retained exact synthetic amended-return or additional-assessment evidence for disposable V1 additional-tax validation.",
        ),
    ).fetchone()[0]


def _post_liability(connection, *, amendment_id, actor_id, digest, posting_date, period_id):
    return connection.execute(
        """
        SELECT accounting.post_v1_tax_additional_liability_journal(
            %s,%s,%s,%s,7.40,9.86,7.40,9.86,2.46,'5310','2100',%s,%s,%s
        )
        """,
        (
            amendment_id,
            actor_id,
            LIABILITY_TOKEN,
            digest,
            posting_date,
            period_id,
            LIABILITY_POLICY,
        ),
    ).fetchone()[0]


def _record_additional_payment(connection, *, actor_id, amendment_id, payment_date, amount, digest_char):
    return connection.execute(
        """
        SELECT accounting.record_v1_tax_additional_payment_evidence(
            %s,%s,%s,%s,%s,'cash_bank_gcash',%s,%s,%s,%s
        )
        """,
        (
            actor_id,
            uuid4(),
            amendment_id,
            payment_date,
            Decimal(amount),
            f"BIR-ADDITIONAL-PAYMENT-{digest_char}",
            f"RETAINED-ADDITIONAL-PAYMENT-{digest_char}",
            digest_char * 64,
            "Management retained exact synthetic BIR payment and bank evidence for protected additional-tax settlement validation.",
        ),
    ).fetchone()[0]


def _post_settlement(connection, *, payment_id, actor_id, amendment_digest, liability_digest, payment_digest, amount, posting_date, period_id):
    return connection.execute(
        """
        SELECT accounting.post_v1_tax_additional_settlement_journal(
            %s,%s,%s,%s,%s,%s,%s,'2100','1030',%s,%s,%s
        )
        """,
        (
            payment_id,
            actor_id,
            SETTLEMENT_TOKEN,
            amendment_digest,
            liability_digest,
            payment_digest,
            Decimal(amount),
            posting_date,
            period_id,
            SETTLEMENT_POLICY,
        ),
    ).fetchone()[0]


def _setup_filed_case(connection, suffix):
    case = settlement_helpers._posted_dst_liability(connection, suffix)
    actor_id, loan_id, client_id, event_id, release_date, period_id, old_rule_id, old_evidence_id, posting_id = case
    return_id = settlement_helpers._record_return(
        connection,
        actor_id=actor_id,
        posting_id=posting_id,
        release_date=release_date,
        idempotency_key=uuid4(),
    )
    return (*case, return_id)


def test_settled_upward_amendment_posts_delta_then_exact_additional_payment() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            suffix = uuid4().hex[:10]
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
                return_id,
            ) = _setup_filed_case(connection, suffix)

            original_payment_id = settlement_helpers._record_payment(
                connection,
                actor_id=actor_id,
                return_id=return_id,
                release_date=release_date,
                idempotency_key=uuid4(),
            )
            original_settlement_journal = connection.execute(
                "SELECT accounting.prepare_v1_tax_settlement_journal(%s,%s)",
                (original_payment_id, actor_id),
            ).fetchone()[0]
            settlement_helpers._post_settlement(
                connection,
                payment_id=original_payment_id,
                actor_id=actor_id,
                release_date=release_date,
                period_id=period_id,
            )
            original_state = connection.execute(
                "SELECT status, entry_number FROM accounting.journal_entries WHERE id=%s",
                (original_settlement_journal,),
            ).fetchone()

            replacement_id = _higher_dst_replacement(
                connection,
                actor_id=actor_id,
                loan_id=loan_id,
                event_id=event_id,
                release_date=release_date,
                old_rule_id=old_rule_id,
                old_evidence_id=old_evidence_id,
                suffix=suffix,
            )
            recognition_date = release_date + timedelta(days=3)
            amendment_id = _record_amendment(
                connection,
                actor_id=actor_id,
                return_id=return_id,
                liability_posting_id=liability_posting_id,
                replacement_evidence_id=replacement_id,
                amendment_date=release_date + timedelta(days=4),
                recognition_date=recognition_date,
                digest_char="1",
            )
            assert connection.execute(
                """
                SELECT revised_declared_tax_due, additional_tax_due,
                       payment_basis, payment_required_amount, amendment_status
                FROM accounting.v1_tax_additional_amendment_queue
                WHERE amendment_evidence_id=%s
                """,
                (amendment_id,),
            ).fetchone() == (
                Decimal("9.86"),
                Decimal("2.46"),
                "additional_due_after_settlement",
                Decimal("2.46"),
                "amendment_evidence_ready",
            )

            liability_journal = connection.execute(
                "SELECT accounting.prepare_v1_tax_additional_liability_journal(%s,%s)",
                (amendment_id, actor_id),
            ).fetchone()[0]
            assert connection.execute(
                """
                SELECT account.code, line.debit, line.credit
                FROM accounting.journal_lines line
                JOIN accounting.accounts account ON account.id=line.account_id
                WHERE line.journal_entry_id=%s ORDER BY line.line_number
                """,
                (liability_journal,),
            ).fetchall() == [
                ("5310", Decimal("2.46"), Decimal("0.00")),
                ("2100", Decimal("0.00"), Decimal("2.46")),
            ]

            with pytest.raises(psycopg.Error, match="protected Management amendment posting function"):
                with connection.transaction():
                    connection.execute(
                        "SELECT accounting.post_journal_entry(%s,%s)",
                        (liability_journal, actor_id),
                    )

            liability_posting = _post_liability(
                connection,
                amendment_id=amendment_id,
                actor_id=actor_id,
                digest="1" * 64,
                posting_date=recognition_date,
                period_id=period_id,
            )
            liability_digest = connection.execute(
                "SELECT confirmation_digest FROM accounting.v1_tax_additional_liability_postings WHERE id=%s",
                (liability_posting,),
            ).fetchone()[0]

            with pytest.raises(psycopg.Error, match="duplicate full liability"):
                with connection.transaction():
                    connection.execute(
                        "SELECT accounting.prepare_v1_tax_liability_journal(%s,%s,%s)",
                        ("documentary_stamp_tax", replacement_id, actor_id),
                    )

            payment_date = release_date + timedelta(days=5)
            payment_id = _record_additional_payment(
                connection,
                actor_id=actor_id,
                amendment_id=amendment_id,
                payment_date=payment_date,
                amount="2.46",
                digest_char="2",
            )
            settlement_journal = connection.execute(
                "SELECT accounting.prepare_v1_tax_additional_settlement_journal(%s,%s)",
                (payment_id, actor_id),
            ).fetchone()[0]
            assert connection.execute(
                """
                SELECT account.code, line.debit, line.credit
                FROM accounting.journal_lines line
                JOIN accounting.accounts account ON account.id=line.account_id
                WHERE line.journal_entry_id=%s ORDER BY line.line_number
                """,
                (settlement_journal,),
            ).fetchall() == [
                ("2100", Decimal("2.46"), Decimal("0.00")),
                ("1030", Decimal("0.00"), Decimal("2.46")),
            ]
            settlement_posting = _post_settlement(
                connection,
                payment_id=payment_id,
                actor_id=actor_id,
                amendment_digest="1" * 64,
                liability_digest=liability_digest,
                payment_digest="2" * 64,
                amount="2.46",
                posting_date=payment_date,
                period_id=period_id,
            )
            assert settlement_posting is not None
            assert connection.execute(
                "SELECT status, entry_number FROM accounting.journal_entries WHERE id=%s",
                (original_settlement_journal,),
            ).fetchone() == original_state
            assert connection.execute(
                """
                SELECT amendment_status, tax_refund_credit_realization_enabled,
                       automatic_source_posting
                FROM accounting.v1_tax_additional_amendment_queue
                WHERE amendment_evidence_id=%s
                """,
                (amendment_id,),
            ).fetchone() == ("additional_tax_settled", False, False)
        finally:
            connection.rollback()


def test_unpaid_filed_amendment_requires_full_revised_payment_and_reserves_base_payment() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            suffix = uuid4().hex[:10]
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
                return_id,
            ) = _setup_filed_case(connection, suffix)
            replacement_id = _higher_dst_replacement(
                connection,
                actor_id=actor_id,
                loan_id=loan_id,
                event_id=event_id,
                release_date=release_date,
                old_rule_id=old_rule_id,
                old_evidence_id=old_evidence_id,
                suffix=suffix,
            )
            recognition_date = release_date + timedelta(days=2)
            amendment_id = _record_amendment(
                connection,
                actor_id=actor_id,
                return_id=return_id,
                liability_posting_id=liability_posting_id,
                replacement_evidence_id=replacement_id,
                amendment_date=release_date + timedelta(days=3),
                recognition_date=recognition_date,
                digest_char="3",
                basis="additional_assessment",
            )
            assert connection.execute(
                """
                SELECT payment_basis, payment_required_amount
                FROM accounting.v1_tax_additional_amendment_queue
                WHERE amendment_evidence_id=%s
                """,
                (amendment_id,),
            ).fetchone() == ("full_revised_return_unpaid", Decimal("9.86"))

            with pytest.raises(psycopg.Error, match="reserved by immutable additional-tax amendment evidence"):
                with connection.transaction():
                    settlement_helpers._record_payment(
                        connection,
                        actor_id=actor_id,
                        return_id=return_id,
                        release_date=release_date,
                        idempotency_key=uuid4(),
                        digest_char="e",
                    )

            connection.execute(
                "SELECT accounting.prepare_v1_tax_additional_liability_journal(%s,%s)",
                (amendment_id, actor_id),
            )
            liability_posting = _post_liability(
                connection,
                amendment_id=amendment_id,
                actor_id=actor_id,
                digest="3" * 64,
                posting_date=recognition_date,
                period_id=period_id,
            )
            liability_digest = connection.execute(
                "SELECT confirmation_digest FROM accounting.v1_tax_additional_liability_postings WHERE id=%s",
                (liability_posting,),
            ).fetchone()[0]
            payment_date = release_date + timedelta(days=4)
            with pytest.raises(psycopg.Error, match="exactly equal the retained amendment payment requirement"):
                with connection.transaction():
                    _record_additional_payment(
                        connection,
                        actor_id=actor_id,
                        amendment_id=amendment_id,
                        payment_date=payment_date,
                        amount="2.46",
                        digest_char="4",
                    )

            payment_id = _record_additional_payment(
                connection,
                actor_id=actor_id,
                amendment_id=amendment_id,
                payment_date=payment_date,
                amount="9.86",
                digest_char="5",
            )
            connection.execute(
                "SELECT accounting.prepare_v1_tax_additional_settlement_journal(%s,%s)",
                (payment_id, actor_id),
            )
            _post_settlement(
                connection,
                payment_id=payment_id,
                actor_id=actor_id,
                amendment_digest="3" * 64,
                liability_digest=liability_digest,
                payment_digest="5" * 64,
                amount="9.86",
                posting_date=payment_date,
                period_id=period_id,
            )
            assert connection.execute(
                """
                SELECT amendment_status, payment_amount
                FROM accounting.v1_tax_additional_amendment_queue
                WHERE amendment_evidence_id=%s
                """,
                (amendment_id,),
            ).fetchone() == ("additional_tax_settled", Decimal("9.86"))
        finally:
            connection.rollback()


def test_additional_liability_forced_audit_failure_rolls_back_atomically() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            suffix = uuid4().hex[:10]
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
                return_id,
            ) = _setup_filed_case(connection, suffix)
            replacement_id = _higher_dst_replacement(
                connection,
                actor_id=actor_id,
                loan_id=loan_id,
                event_id=event_id,
                release_date=release_date,
                old_rule_id=old_rule_id,
                old_evidence_id=old_evidence_id,
                suffix=suffix,
            )
            recognition_date = release_date + timedelta(days=2)
            amendment_id = _record_amendment(
                connection,
                actor_id=actor_id,
                return_id=return_id,
                liability_posting_id=liability_posting_id,
                replacement_evidence_id=replacement_id,
                amendment_date=release_date + timedelta(days=3),
                recognition_date=recognition_date,
                digest_char="7",
            )
            journal_id = connection.execute(
                "SELECT accounting.prepare_v1_tax_additional_liability_journal(%s,%s)",
                (amendment_id, actor_id),
            ).fetchone()[0]
            with pytest.raises(psycopg.Error, match="Forced V1 additional-tax liability audit failure"):
                with connection.transaction():
                    connection.execute(
                        "SELECT set_config('accounting.v1_tax_additional_liability_force_audit_failure','on',true)"
                    )
                    _post_liability(
                        connection,
                        amendment_id=amendment_id,
                        actor_id=actor_id,
                        digest="7" * 64,
                        posting_date=recognition_date,
                        period_id=period_id,
                    )
            assert connection.execute(
                "SELECT status, entry_number FROM accounting.journal_entries WHERE id=%s",
                (journal_id,),
            ).fetchone() == ("draft", None)
            assert connection.execute(
                "SELECT count(*) FROM accounting.v1_tax_additional_liability_postings WHERE journal_entry_id=%s",
                (journal_id,),
            ).fetchone()[0] == 0
        finally:
            connection.rollback()
