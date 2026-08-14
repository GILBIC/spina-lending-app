from __future__ import annotations

import importlib.util
import os
from datetime import date, datetime, timedelta, timezone
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
POSTING_HELPER_PATH = TEST_DIR / "test_7x7_protected_journal_posting_postgres.py"
_spec = importlib.util.spec_from_file_location("v1_tax_x7_posting_helpers", POSTING_HELPER_PATH)
assert _spec is not None and _spec.loader is not None
x7_posting = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(x7_posting)

SQL_0082 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0082_add_v1_tax_evidence_readiness.sql"
).read_text(encoding="utf-8")


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _management_actor(connection: psycopg.Connection, suffix: str):
    actor_id = connection.execute(
        """
        INSERT INTO core.users(username, full_name, status)
        VALUES(%s, %s, 'active')
        RETURNING id
        """,
        (f"tax-{suffix}", f"Tax Evidence {suffix}"),
    ).fetchone()[0]
    connection.execute(
        """
        INSERT INTO core.user_roles(user_id, role_id)
        SELECT %s, id FROM core.roles WHERE code='management'
        """,
        (actor_id,),
    )
    return actor_id


def _simple_loan(connection: psycopg.Connection, actor_id, suffix: str):
    loan_type_id = connection.execute(
        """
        INSERT INTO lending.loan_types(
            code, name, term_days, calculation_mode, daily_interest_per_1000
        ) VALUES(%s, %s, 120, 'fixed_daily', 0)
        RETURNING id
        """,
        (f"TAX-REG-{suffix}", f"Tax Regular {suffix}"),
    ).fetchone()[0]
    client_id = connection.execute(
        """
        INSERT INTO lending.clients(client_code, full_name, status)
        VALUES(%s, %s, 'active')
        RETURNING id
        """,
        (f"TAX-C-{suffix}", f"Tax Client {suffix}"),
    ).fetchone()[0]
    release_date = date(2098, 1, 1)
    loan_id = connection.execute(
        """
        INSERT INTO lending.loans(
            loan_number, client_id, loan_type_id, principal, daily_amount,
            interest_rate, date_released, due_date, status, created_by_user_id
        ) VALUES(%s, %s, %s, 3000.00, 30.00, 20.0000, %s, %s, 'active', %s)
        RETURNING id
        """,
        (
            f"TAX-L-{suffix}",
            client_id,
            loan_type_id,
            release_date,
            release_date + timedelta(days=120),
            actor_id,
        ),
    ).fetchone()[0]
    disbursed_at = datetime(2098, 1, 1, 4, 0, tzinfo=timezone.utc)
    event_id = connection.execute(
        """
        SELECT accounting.record_loan_disbursement_evidence(
            %s, %s, 'new_loan_release', %s, %s,
            3000.00, 0.00, 0.00, 'cash_office', %s, %s
        )
        """,
        (
            loan_id,
            actor_id,
            release_date,
            disbursed_at,
            f"TAX-DISB-{suffix}",
            "Retained synthetic release evidence for disposable A6.2 DST proof.",
        ),
    ).fetchone()[0]
    return loan_id, client_id, event_id, release_date


def _record_rule(
    connection: psycopg.Connection,
    *,
    actor_id,
    tax_type: str,
    key: str,
    effective_from: date,
    rate: str,
    maturity_max_days: int | None,
    digest_char: str,
    supersedes=None,
):
    return connection.execute(
        """
        SELECT accounting.record_v1_tax_rule_evidence(
            %s,%s,%s,%s,%s,NULL,'taxable',%s,%s,
            %s,%s,%s,%s,%s,%s
        )
        """,
        (
            actor_id,
            uuid4(),
            tax_type,
            key,
            effective_from,
            Decimal(rate),
            maturity_max_days,
            "Philippine tax authority / statute",
            f"LEGAL-{key}-{digest_char}",
            f"RETAINED-{key}-{digest_char}",
            digest_char * 64,
            "Management approved this exact synthetic rule evidence for disposable A6.2 validation only.",
            supersedes,
        ),
    ).fetchone()[0]


def _record_dst(
    connection: psycopg.Connection,
    *,
    actor_id,
    loan_id,
    event_id,
    rule_id,
    tax_due: str,
    token: str,
    supersedes=None,
):
    return connection.execute(
        """
        SELECT accounting.record_v1_dst_evidence(
            %s,%s,%s,%s,%s,3000.00,120,%s,%s,%s,%s,%s,%s,%s
        )
        """,
        (
            actor_id,
            uuid4(),
            loan_id,
            event_id,
            rule_id,
            Decimal(tax_due),
            f"LOAN-INSTRUMENT-{token}",
            token * 64,
            f"DST-CALC-{token}",
            token * 64,
            "Management retained the exact synthetic debt instrument and DST calculation for disposable validation.",
            supersedes,
        ),
    ).fetchone()[0]


def _record_percentage(
    connection: psycopg.Connection,
    *,
    actor_id,
    transaction_id,
    rule_id,
    taxable: str,
    principal: str,
    tax_due: str,
    digest_char: str,
    idempotency_key=None,
    supersedes=None,
):
    return connection.execute(
        """
        SELECT accounting.record_v1_percentage_tax_evidence(
            %s,%s,%s,%s,50.00,%s,%s,%s,%s,%s,%s,%s
        )
        """,
        (
            actor_id,
            idempotency_key or uuid4(),
            transaction_id,
            rule_id,
            Decimal(taxable),
            Decimal(principal),
            Decimal(tax_due),
            f"TAX-ALLOCATION-{digest_char}",
            digest_char * 64,
            "Management retained an independent contractual/statutory tax allocation; no PFRS EIR amount is used as the tax base.",
            supersedes,
        ),
    ).fetchone()[0]


def test_v1_dst_evidence_is_exact_versioned_idempotent_and_readiness_only() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0082))
            actor_id = _management_actor(connection, suffix)
            loan_id, _, event_id, release_date = _simple_loan(connection, actor_id, suffix)

            rule_v1 = _record_rule(
                connection,
                actor_id=actor_id,
                tax_type="documentary_stamp_tax",
                key=f"dst-debt-{suffix}",
                effective_from=release_date,
                rate="0.0075000000",
                maturity_max_days=None,
                digest_char="a",
            )
            evidence_v1 = _record_dst(
                connection,
                actor_id=actor_id,
                loan_id=loan_id,
                event_id=event_id,
                rule_id=rule_v1,
                tax_due="7.40",
                token="b",
            )

            readiness = connection.execute(
                """
                SELECT tax_status, tax_due, tax_posting_enabled, automatic_source_posting
                FROM accounting.v1_tax_dst_readiness
                WHERE loan_id=%s
                """,
                (loan_id,),
            ).fetchone()
            assert readiness == ("evidence_ready", Decimal("7.40"), False, False)

            with pytest.raises(psycopg.Error, match="tax due does not reconcile"):
                with connection.transaction():
                    _record_dst(
                        connection,
                        actor_id=actor_id,
                        loan_id=loan_id,
                        event_id=event_id,
                        rule_id=rule_v1,
                        tax_due="7.41",
                        token="c",
                        supersedes=evidence_v1,
                    )

            with pytest.raises(psycopg.Error, match="immutable"):
                with connection.transaction():
                    connection.execute(
                        "UPDATE accounting.v1_dst_evidence SET tax_due=0 WHERE id=%s",
                        (evidence_v1,),
                    )

            rule_v2 = _record_rule(
                connection,
                actor_id=actor_id,
                tax_type="documentary_stamp_tax",
                key=f"dst-debt-{suffix}",
                effective_from=release_date,
                rate="0.0080000000",
                maturity_max_days=None,
                digest_char="d",
                supersedes=rule_v1,
            )
            blocked = connection.execute(
                "SELECT tax_status FROM accounting.v1_tax_dst_readiness WHERE loan_id=%s",
                (loan_id,),
            ).fetchone()[0]
            assert blocked == "blocked_rule_superseded"

            evidence_v2 = _record_dst(
                connection,
                actor_id=actor_id,
                loan_id=loan_id,
                event_id=event_id,
                rule_id=rule_v2,
                tax_due="7.89",
                token="e",
                supersedes=evidence_v1,
            )
            assert evidence_v2 != evidence_v1
            current = connection.execute(
                """
                SELECT evidence_version, tax_status, tax_due
                FROM accounting.v1_tax_dst_readiness
                WHERE loan_id=%s
                """,
                (loan_id,),
            ).fetchone()
            assert current == (2, "evidence_ready", Decimal("7.89"))
        finally:
            connection.rollback()


def test_v1_percentage_tax_requires_independent_cash_allocation_not_eir_and_exact_retry() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0082))
            actor_id, loan_id, _, transaction_id, before = x7_posting._prepared_case(
                connection, suffix
            )
            x7_posting._post(connection, actor_id, before)

            collection_date = connection.execute(
                "SELECT collection_date FROM lending.collection_transactions WHERE id=%s",
                (transaction_id,),
            ).fetchone()[0]
            rule_id = _record_rule(
                connection,
                actor_id=actor_id,
                tax_type="percentage_tax_lending",
                key=f"lending-grt-{suffix}",
                effective_from=collection_date,
                rate="0.0500000000",
                maturity_max_days=1825,
                digest_char="f",
            )

            retry_key = uuid4()
            evidence_id = _record_percentage(
                connection,
                actor_id=actor_id,
                transaction_id=transaction_id,
                rule_id=rule_id,
                taxable="21.00",
                principal="29.00",
                tax_due="1.05",
                digest_char="1",
                idempotency_key=retry_key,
            )
            retry_id = _record_percentage(
                connection,
                actor_id=actor_id,
                transaction_id=transaction_id,
                rule_id=rule_id,
                taxable="21.00",
                principal="29.00",
                tax_due="1.05",
                digest_char="1",
                idempotency_key=retry_key,
            )
            assert retry_id == evidence_id

            posted_eir_interest = connection.execute(
                """
                SELECT accounting_eir_interest_received
                FROM accounting.seven_by_seven_journal_postings
                WHERE transaction_id=%s
                """,
                (transaction_id,),
            ).fetchone()[0]
            retained_taxable = connection.execute(
                """
                SELECT taxable_lending_receipt_amount
                FROM accounting.v1_percentage_tax_evidence
                WHERE id=%s
                """,
                (evidence_id,),
            ).fetchone()[0]
            assert retained_taxable == Decimal("21.00")
            # This assertion proves the tax evidence is independently supplied rather
            # than copied from the protected PFRS/EIR allocation.
            assert retained_taxable != posted_eir_interest

            readiness = connection.execute(
                """
                SELECT tax_status, taxable_lending_receipt_amount,
                       principal_receipt_amount, tax_due,
                       tax_posting_enabled, automatic_source_posting
                FROM accounting.v1_tax_percentage_readiness
                WHERE transaction_id=%s
                """,
                (transaction_id,),
            ).fetchone()
            assert readiness == (
                "evidence_ready",
                Decimal("21.00"),
                Decimal("29.00"),
                Decimal("1.05"),
                False,
                False,
            )

            with pytest.raises(psycopg.Error, match="exactly reconcile"):
                with connection.transaction():
                    _record_percentage(
                        connection,
                        actor_id=actor_id,
                        transaction_id=transaction_id,
                        rule_id=rule_id,
                        taxable="21.00",
                        principal="28.00",
                        tax_due="1.05",
                        digest_char="2",
                        supersedes=evidence_id,
                    )

            with pytest.raises(psycopg.Error, match="tax due does not reconcile"):
                with connection.transaction():
                    _record_percentage(
                        connection,
                        actor_id=actor_id,
                        transaction_id=transaction_id,
                        rule_id=rule_id,
                        taxable="21.00",
                        principal="29.00",
                        tax_due="1.06",
                        digest_char="3",
                        supersedes=evidence_id,
                    )

            summary = connection.execute(
                """
                SELECT evidence_backed_tax_readiness_enabled,
                       tax_posting_enabled, automatic_source_posting
                FROM accounting.v1_tax_readiness_summary
                """
            ).fetchone()
            assert summary == (True, False, False)
        finally:
            connection.rollback()
