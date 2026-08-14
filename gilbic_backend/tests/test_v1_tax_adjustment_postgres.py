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
SETTLEMENT_HELPER_PATH = TEST_DIR / "test_v1_tax_settlement_postgres.py"
_spec = importlib.util.spec_from_file_location(
    "v1_tax_adjustment_settlement_helpers", SETTLEMENT_HELPER_PATH
)
assert _spec is not None and _spec.loader is not None
settlement_helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(settlement_helpers)

tax_helpers = settlement_helpers.tax_helpers
SQL_0086 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0086_add_protected_v1_tax_adjustment_reversal.sql"
).read_text(encoding="utf-8")

ADJUSTMENT_POLICY = "v1_tax_adjustment_posting_v1"
ADJUSTMENT_TOKEN = "7" * 64


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _install(connection: psycopg.Connection) -> None:
    settlement_helpers._install(connection)
    connection.execute(_transaction_body(SQL_0086))


def _lower_dst_replacement(
    connection: psycopg.Connection,
    *,
    actor_id,
    loan_id,
    event_id,
    release_date,
    old_rule_id,
    old_evidence_id,
    suffix: str,
):
    replacement_rule_id = tax_helpers._record_rule(
        connection,
        actor_id=actor_id,
        tax_type="documentary_stamp_tax",
        key=f"dst-settle-{suffix}",
        effective_from=release_date,
        rate="0.0050000000",
        maturity_max_days=None,
        digest_char="e",
        supersedes=old_rule_id,
    )
    replacement_evidence_id = tax_helpers._record_dst(
        connection,
        actor_id=actor_id,
        loan_id=loan_id,
        event_id=event_id,
        rule_id=replacement_rule_id,
        tax_due="4.93",
        token="f",
        supersedes=old_evidence_id,
    )
    return replacement_rule_id, replacement_evidence_id


def _record_adjustment(
    connection: psycopg.Connection,
    *,
    actor_id,
    liability_posting_id,
    replacement_evidence_id,
    kind: str,
    adjustment_date,
    idempotency_key,
    digest_char: str,
):
    return connection.execute(
        """
        SELECT accounting.record_v1_tax_adjustment_evidence(
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        """,
        (
            actor_id,
            idempotency_key,
            liability_posting_id,
            replacement_evidence_id,
            kind,
            adjustment_date,
            f"TAX-ADJUSTMENT-{digest_char}",
            f"RETAINED-TAX-ADJUSTMENT-{digest_char}",
            digest_char * 64,
            "Management retained exact synthetic correction evidence for protected disposable V1 tax adjustment validation.",
        ),
    ).fetchone()[0]


def _post_adjustment(
    connection: psycopg.Connection,
    *,
    adjustment_evidence_id,
    actor_id,
    digest: str,
    original_due: str,
    replacement_due: str,
    adjustment_amount: str,
    debit_code: str,
    credit_code: str,
    posting_date,
    period_id,
    token: str = ADJUSTMENT_TOKEN,
):
    return connection.execute(
        """
        SELECT accounting.post_v1_tax_adjustment_journal(
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        """,
        (
            adjustment_evidence_id,
            actor_id,
            token,
            digest,
            Decimal(original_due),
            Decimal(replacement_due),
            Decimal(adjustment_amount),
            debit_code,
            credit_code,
            posting_date,
            period_id,
            ADJUSTMENT_POLICY,
        ),
    ).fetchone()[0]


def test_unsettled_stale_liability_is_fully_reversed_idempotently() -> None:
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
                period_id,
                old_rule_id,
                old_evidence_id,
                liability_posting_id,
            ) = settlement_helpers._posted_dst_liability(connection, suffix)
            _, replacement_evidence_id = _lower_dst_replacement(
                connection,
                actor_id=actor_id,
                loan_id=loan_id,
                event_id=event_id,
                release_date=release_date,
                old_rule_id=old_rule_id,
                old_evidence_id=old_evidence_id,
                suffix=suffix,
            )

            assert connection.execute(
                """
                SELECT accounting_status
                FROM accounting.v1_tax_liability_queue
                WHERE posting_id=%s
                """,
                (liability_posting_id,),
            ).fetchone()[0] == "posted_adjustment_review_required"

            evidence_key = uuid4()
            adjustment_id = _record_adjustment(
                connection,
                actor_id=actor_id,
                liability_posting_id=liability_posting_id,
                replacement_evidence_id=replacement_evidence_id,
                kind="reverse_unsettled_liability",
                adjustment_date=release_date,
                idempotency_key=evidence_key,
                digest_char="1",
            )
            assert _record_adjustment(
                connection,
                actor_id=actor_id,
                liability_posting_id=liability_posting_id,
                replacement_evidence_id=replacement_evidence_id,
                kind="reverse_unsettled_liability",
                adjustment_date=release_date,
                idempotency_key=evidence_key,
                digest_char="1",
            ) == adjustment_id

            journal_id = connection.execute(
                "SELECT accounting.prepare_v1_tax_adjustment_journal(%s,%s)",
                (adjustment_id, actor_id),
            ).fetchone()[0]
            assert connection.execute(
                "SELECT accounting.prepare_v1_tax_adjustment_journal(%s,%s)",
                (adjustment_id, actor_id),
            ).fetchone()[0] == journal_id

            original_journal_id = connection.execute(
                """
                SELECT journal_entry_id FROM accounting.v1_tax_liability_postings
                WHERE id=%s
                """,
                (liability_posting_id,),
            ).fetchone()[0]
            assert connection.execute(
                "SELECT reversal_of_entry_id FROM accounting.journal_entries WHERE id=%s",
                (journal_id,),
            ).fetchone()[0] == original_journal_id

            assert connection.execute(
                """
                SELECT line.line_number, account.code, line.debit, line.credit
                FROM accounting.journal_lines line
                JOIN accounting.accounts account ON account.id=line.account_id
                WHERE line.journal_entry_id=%s ORDER BY line.line_number
                """,
                (journal_id,),
            ).fetchall() == [
                (1, "2100", Decimal("7.40"), Decimal("0.00")),
                (2, "5310", Decimal("0.00"), Decimal("7.40")),
            ]

            with pytest.raises(psycopg.Error, match="protected Management adjustment posting function"):
                with connection.transaction():
                    connection.execute(
                        "SELECT accounting.post_journal_entry(%s,%s)",
                        (journal_id, actor_id),
                    )

            adjustment_posting_id = _post_adjustment(
                connection,
                adjustment_evidence_id=adjustment_id,
                actor_id=actor_id,
                digest="1" * 64,
                original_due="7.40",
                replacement_due="4.93",
                adjustment_amount="7.40",
                debit_code="2100",
                credit_code="5310",
                posting_date=release_date,
                period_id=period_id,
            )
            assert _post_adjustment(
                connection,
                adjustment_evidence_id=adjustment_id,
                actor_id=actor_id,
                digest="1" * 64,
                original_due="7.40",
                replacement_due="4.93",
                adjustment_amount="7.40",
                debit_code="2100",
                credit_code="5310",
                posting_date=release_date,
                period_id=period_id,
            ) == adjustment_posting_id

            assert connection.execute(
                """
                SELECT accounting_status
                FROM accounting.v1_tax_liability_effective_queue
                WHERE posting_id=%s
                """,
                (liability_posting_id,),
            ).fetchone()[0] == "posted_adjusted_reversed"
            assert connection.execute(
                """
                SELECT adjustment_status, tax_adjustment_reversal_enabled,
                       automatic_source_posting
                FROM accounting.v1_tax_adjustment_queue
                WHERE adjustment_evidence_id=%s
                """,
                (adjustment_id,),
            ).fetchone() == ("posted_unsettled_liability_reversal", True, False)
        finally:
            connection.rollback()


def test_settled_tax_decrease_recognizes_recoverable_and_preserves_settlement() -> None:
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
            settlement_journal_id = connection.execute(
                "SELECT accounting.prepare_v1_tax_settlement_journal(%s,%s)",
                (payment_id, actor_id),
            ).fetchone()[0]
            settlement_posting_id = settlement_helpers._post_settlement(
                connection,
                payment_id=payment_id,
                actor_id=actor_id,
                release_date=release_date,
                period_id=period_id,
            )
            original_settlement_state = connection.execute(
                "SELECT status, entry_number FROM accounting.journal_entries WHERE id=%s",
                (settlement_journal_id,),
            ).fetchone()
            assert original_settlement_state[0] == "posted"

            _, replacement_evidence_id = _lower_dst_replacement(
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
            adjustment_id = _record_adjustment(
                connection,
                actor_id=actor_id,
                liability_posting_id=liability_posting_id,
                replacement_evidence_id=replacement_evidence_id,
                kind="recognize_settled_tax_recoverable",
                adjustment_date=adjustment_date,
                idempotency_key=uuid4(),
                digest_char="2",
            )
            adjustment_journal_id = connection.execute(
                "SELECT accounting.prepare_v1_tax_adjustment_journal(%s,%s)",
                (adjustment_id, actor_id),
            ).fetchone()[0]

            assert connection.execute(
                """
                SELECT line.line_number, account.code, line.debit, line.credit
                FROM accounting.journal_lines line
                JOIN accounting.accounts account ON account.id=line.account_id
                WHERE line.journal_entry_id=%s ORDER BY line.line_number
                """,
                (adjustment_journal_id,),
            ).fetchall() == [
                (1, "1130", Decimal("2.47"), Decimal("0.00")),
                (2, "5310", Decimal("0.00"), Decimal("2.47")),
            ]

            adjustment_posting_id = _post_adjustment(
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
            assert adjustment_posting_id is not None

            assert connection.execute(
                "SELECT status, entry_number FROM accounting.journal_entries WHERE id=%s",
                (settlement_journal_id,),
            ).fetchone() == original_settlement_state
            assert connection.execute(
                """
                SELECT settlement_posting_id, settlement_status,
                       tax_adjustment_reversal_enabled, automatic_source_posting
                FROM accounting.v1_tax_settlement_effective_queue
                WHERE tax_return_id=%s
                """,
                (return_id,),
            ).fetchone() == (
                settlement_posting_id,
                "settled_adjustment_recorded",
                True,
                False,
            )
            assert connection.execute(
                """
                SELECT accounting_status
                FROM accounting.v1_tax_liability_effective_queue
                WHERE evidence_id=%s
                """,
                (replacement_evidence_id,),
            ).fetchone()[0] == "covered_by_settled_adjustment"

            with pytest.raises(psycopg.Error, match="duplicate full liability"):
                with connection.transaction():
                    connection.execute(
                        "SELECT accounting.prepare_v1_tax_liability_journal(%s,%s,%s)",
                        ("documentary_stamp_tax", replacement_evidence_id, actor_id),
                    )
        finally:
            connection.rollback()


def test_adjustment_post_forced_audit_failure_rolls_back_atomically() -> None:
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
                period_id,
                old_rule_id,
                old_evidence_id,
                liability_posting_id,
            ) = settlement_helpers._posted_dst_liability(connection, suffix)
            _, replacement_evidence_id = _lower_dst_replacement(
                connection,
                actor_id=actor_id,
                loan_id=loan_id,
                event_id=event_id,
                release_date=release_date,
                old_rule_id=old_rule_id,
                old_evidence_id=old_evidence_id,
                suffix=suffix,
            )
            adjustment_id = _record_adjustment(
                connection,
                actor_id=actor_id,
                liability_posting_id=liability_posting_id,
                replacement_evidence_id=replacement_evidence_id,
                kind="reverse_unsettled_liability",
                adjustment_date=release_date,
                idempotency_key=uuid4(),
                digest_char="3",
            )
            journal_id = connection.execute(
                "SELECT accounting.prepare_v1_tax_adjustment_journal(%s,%s)",
                (adjustment_id, actor_id),
            ).fetchone()[0]

            with pytest.raises(psycopg.Error, match="Forced V1 tax adjustment audit failure"):
                with connection.transaction():
                    connection.execute(
                        "SELECT set_config('accounting.v1_tax_adjustment_force_audit_failure','on',true)"
                    )
                    _post_adjustment(
                        connection,
                        adjustment_evidence_id=adjustment_id,
                        actor_id=actor_id,
                        digest="3" * 64,
                        original_due="7.40",
                        replacement_due="4.93",
                        adjustment_amount="7.40",
                        debit_code="2100",
                        credit_code="5310",
                        posting_date=release_date,
                        period_id=period_id,
                    )

            assert connection.execute(
                "SELECT status, entry_number FROM accounting.journal_entries WHERE id=%s",
                (journal_id,),
            ).fetchone() == ("draft", None)
            assert connection.execute(
                """
                SELECT count(*) FROM accounting.v1_tax_adjustment_postings
                WHERE journal_entry_id=%s
                """,
                (journal_id,),
            ).fetchone()[0] == 0
        finally:
            connection.rollback()
