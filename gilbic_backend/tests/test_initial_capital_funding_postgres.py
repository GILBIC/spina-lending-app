from __future__ import annotations

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

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
MIGRATIONS = (
    "0001_core_lending_foundation.sql",
    "0003_add_management_administration.sql",
    "0021_add_accounting_foundation.sql",
    "0024_add_manual_general_journal_and_trial_balance.sql",
    "0081_add_protected_initial_capital_funding.sql",
)
POLICY = "initial_capital_funding_v1"


def _body(source: str) -> str:
    source = source.strip()
    lowered = source.lower()
    assert lowered.startswith("begin;") and lowered.endswith("commit;")
    return source[len("BEGIN;") :].lstrip()[: -len("COMMIT;")].rstrip()


def _install(connection: psycopg.Connection) -> None:
    for name in MIGRATIONS:
        source = (SQL_ROOT / name).read_text(encoding="utf-8")
        connection.execute(_body(source))


def _management_actor(connection: psycopg.Connection, suffix: str):
    actor_id = connection.execute(
        """
        INSERT INTO core.users(username, full_name, status)
        VALUES(%s, %s, 'active')
        RETURNING id
        """,
        (f"capital-{suffix}", f"Capital Test {suffix}"),
    ).fetchone()[0]
    connection.execute(
        """
        INSERT INTO core.user_roles(user_id, role_id)
        SELECT %s, id FROM core.roles WHERE code='management'
        """,
        (actor_id,),
    )
    return actor_id


def _period(connection: psycopg.Connection, suffix: str):
    today = connection.execute("SELECT current_date").fetchone()[0]
    period_id = connection.execute(
        """
        INSERT INTO accounting.fiscal_periods(label, start_date, end_date, status)
        VALUES(%s, %s, %s, 'open')
        RETURNING id
        """,
        (f"Initial capital {suffix}", today, today + timedelta(days=30)),
    ).fetchone()[0]
    return period_id, today


def _record(
    connection: psycopg.Connection,
    *,
    actor_id,
    key,
    funding_date,
    amount: str,
    cash_code: str,
    suffix: str,
    digest_char: str = "a",
):
    return connection.execute(
        """
        SELECT accounting.record_initial_capital_funding_evidence(
            %s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        """,
        (
            actor_id,
            key,
            funding_date,
            Decimal(amount),
            cash_code,
            "bank_statement",
            f"CAP-{suffix}",
            digest_char * 64,
            "Retained bank evidence proves the exact initial capital funding receipt.",
        ),
    ).fetchone()[0]


def _post(
    connection: psycopg.Connection,
    *,
    evidence_id,
    actor_id,
    token: str,
    digest: str,
    amount: str,
    cash_code: str,
    posting_date,
    period_id,
):
    return connection.execute(
        """
        SELECT accounting.post_initial_capital_funding_journal(
            %s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        """,
        (
            evidence_id,
            actor_id,
            token,
            digest,
            Decimal(amount),
            cash_code,
            posting_date,
            period_id,
            POLICY,
        ),
    ).fetchone()[0]


def test_initial_capital_funding_protected_general_journal_lifecycle_and_retry() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            suffix = uuid4().hex[:10]
            actor_id = _management_actor(connection, suffix)
            period_id, today = _period(connection, suffix)
            key = uuid4()

            evidence_id = _record(
                connection,
                actor_id=actor_id,
                key=key,
                funding_date=today,
                amount="100000.00",
                cash_code="1030",
                suffix=suffix,
            )
            assert _record(
                connection,
                actor_id=actor_id,
                key=key,
                funding_date=today,
                amount="100000.00",
                cash_code="1030",
                suffix=suffix,
            ) == evidence_id

            with pytest.raises(psycopg.Error, match="immutable retry identity"):
                with connection.transaction():
                    _record(
                        connection,
                        actor_id=actor_id,
                        key=key,
                        funding_date=today,
                        amount="99999.00",
                        cash_code="1030",
                        suffix=suffix,
                    )

            with pytest.raises(psycopg.Error, match="immutable"):
                with connection.transaction():
                    connection.execute(
                        "UPDATE accounting.initial_capital_funding_evidence SET amount=1 WHERE id=%s",
                        (evidence_id,),
                    )

            journal_id = connection.execute(
                "SELECT accounting.prepare_initial_capital_funding_journal(%s,%s)",
                (evidence_id, actor_id),
            ).fetchone()[0]
            assert connection.execute(
                "SELECT accounting.prepare_initial_capital_funding_journal(%s,%s)",
                (evidence_id, actor_id),
            ).fetchone()[0] == journal_id

            journal = connection.execute(
                """
                SELECT source_type, source_reference, source_event_key, status,
                       posting_date, fiscal_period_id
                FROM accounting.journal_entries WHERE id=%s
                """,
                (journal_id,),
            ).fetchone()
            assert journal == (
                "initial_capital_funding",
                str(evidence_id),
                f"initial_capital_funding:{evidence_id}",
                "draft",
                today,
                period_id,
            )

            lines = connection.execute(
                """
                SELECT account.code, line.debit, line.credit
                FROM accounting.journal_lines line
                JOIN accounting.accounts account ON account.id=line.account_id
                WHERE line.journal_entry_id=%s
                ORDER BY line.line_number
                """,
                (journal_id,),
            ).fetchall()
            assert lines == [
                ("1030", Decimal("100000.00"), Decimal("0.00")),
                ("3000", Decimal("0.00"), Decimal("100000.00")),
            ]

            with pytest.raises(
                psycopg.Error,
                match="manual.*General Journal|protected Management posting function",
            ):
                with connection.transaction():
                    connection.execute(
                        "SELECT accounting.post_manual_journal_entry(%s,%s)",
                        (journal_id, actor_id),
                    )

            with pytest.raises(psycopg.Error, match="system generated and immutable"):
                with connection.transaction():
                    connection.execute(
                        "UPDATE accounting.journal_lines SET description='tampered' WHERE journal_entry_id=%s",
                        (journal_id,),
                    )

            posting_id = _post(
                connection,
                evidence_id=evidence_id,
                actor_id=actor_id,
                token="b" * 64,
                digest="a" * 64,
                amount="100000.00",
                cash_code="1030",
                posting_date=today,
                period_id=period_id,
            )
            assert posting_id == evidence_id
            assert _post(
                connection,
                evidence_id=evidence_id,
                actor_id=actor_id,
                token="b" * 64,
                digest="a" * 64,
                amount="100000.00",
                cash_code="1030",
                posting_date=today,
                period_id=period_id,
            ) == evidence_id

            with pytest.raises(psycopg.Error, match="immutable retry identity"):
                with connection.transaction():
                    _post(
                        connection,
                        evidence_id=evidence_id,
                        actor_id=actor_id,
                        token="c" * 64,
                        digest="a" * 64,
                        amount="100000.00",
                        cash_code="1030",
                        posting_date=today,
                        period_id=period_id,
                    )

            posted = connection.execute(
                "SELECT status, entry_number FROM accounting.journal_entries WHERE id=%s",
                (journal_id,),
            ).fetchone()
            assert posted[0] == "posted"
            assert posted[1].startswith("JE-")

            balances = dict(
                connection.execute(
                    """
                    SELECT account.code, sum(line.debit-line.credit)
                    FROM accounting.journal_lines line
                    JOIN accounting.accounts account ON account.id=line.account_id
                    JOIN accounting.journal_entries journal ON journal.id=line.journal_entry_id
                    WHERE journal.status='posted' AND account.code IN ('1030','3000')
                    GROUP BY account.code
                    """
                ).fetchall()
            )
            assert balances["1030"] == Decimal("100000.00")
            assert balances["3000"] == Decimal("-100000.00")

            queue = connection.execute(
                """
                SELECT accounting_status, protected_initial_capital_funding_enabled,
                       synthetic_opening_balance_required, automatic_source_posting
                FROM accounting.initial_capital_funding_queue
                WHERE evidence_id=%s
                """,
                (evidence_id,),
            ).fetchone()
            assert queue == ("posted", True, False, False)

            assert connection.execute(
                "SELECT count(*) FROM accounting.journal_entries WHERE source_type='opening_balance'"
            ).fetchone()[0] == 0
        finally:
            connection.rollback()


def test_initial_capital_funding_posting_is_atomic_on_forced_audit_failure() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            suffix = "R" + uuid4().hex[:9]
            actor_id = _management_actor(connection, suffix)
            period_id, today = _period(connection, suffix)
            evidence_id = _record(
                connection,
                actor_id=actor_id,
                key=uuid4(),
                funding_date=today,
                amount="25000.00",
                cash_code="1010",
                suffix=suffix,
                digest_char="d",
            )
            journal_id = connection.execute(
                "SELECT accounting.prepare_initial_capital_funding_journal(%s,%s)",
                (evidence_id, actor_id),
            ).fetchone()[0]
            before_events = connection.execute(
                "SELECT count(*) FROM accounting.journal_events WHERE journal_entry_id=%s",
                (journal_id,),
            ).fetchone()[0]

            with pytest.raises(psycopg.Error, match="Forced initial-capital audit failure"):
                with connection.transaction():
                    connection.execute(
                        "SELECT set_config('accounting.initial_capital_force_audit_failure','on',true)"
                    )
                    _post(
                        connection,
                        evidence_id=evidence_id,
                        actor_id=actor_id,
                        token="e" * 64,
                        digest="d" * 64,
                        amount="25000.00",
                        cash_code="1010",
                        posting_date=today,
                        period_id=period_id,
                    )

            assert connection.execute(
                "SELECT status FROM accounting.journal_entries WHERE id=%s",
                (journal_id,),
            ).fetchone()[0] == "draft"
            assert connection.execute(
                "SELECT count(*) FROM accounting.initial_capital_funding_postings WHERE evidence_id=%s",
                (evidence_id,),
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT count(*) FROM accounting.journal_events WHERE journal_entry_id=%s",
                (journal_id,),
            ).fetchone()[0] == before_events
        finally:
            connection.rollback()
