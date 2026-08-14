from __future__ import annotations

import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

SQL_0091 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0091_add_protected_period_close.sql"
).read_text(encoding="utf-8")
POLICY = "period_close_retained_earnings_v1"


def _body(source: str) -> str:
    text = source.strip()
    assert text.startswith("BEGIN;") and text.endswith("COMMIT;")
    return text[len("BEGIN;") :].lstrip()[: -len("COMMIT;")].rstrip()


def _install(connection: psycopg.Connection) -> None:
    connection.execute(_body(SQL_0091))


def _management_actor(connection: psycopg.Connection, suffix: str):
    actor_id = connection.execute(
        """
        INSERT INTO core.users(username, full_name, status)
        VALUES(%s, %s, 'active')
        RETURNING id
        """,
        (f"period-close-{suffix}", f"Period Close {suffix}"),
    ).fetchone()[0]
    connection.execute(
        """
        INSERT INTO core.user_roles(user_id, role_id)
        SELECT %s, id FROM core.roles WHERE code='management'
        """,
        (actor_id,),
    )
    return actor_id


def _period(
    connection: psycopg.Connection,
    *,
    actor_id,
    suffix: str,
    start_offset: int = 0,
):
    today = connection.execute("SELECT current_date").fetchone()[0]
    start_date = today + timedelta(days=start_offset)
    end_date = start_date + timedelta(days=9)
    period_id = connection.execute(
        "SELECT accounting.create_fiscal_period(%s,%s,%s,%s)",
        (f"Close {suffix}", start_date, end_date, actor_id),
    ).fetchone()[0]
    return period_id, start_date, end_date


def _manual_journal(
    connection: psycopg.Connection,
    *,
    actor_id,
    posting_date,
    description: str,
    lines: list[dict[str, object]],
):
    journal_id = connection.execute(
        "SELECT accounting.create_manual_journal_draft(%s,%s,%s,%s::jsonb)",
        (posting_date, description, actor_id, Jsonb(lines)),
    ).fetchone()[0]
    entry_number = connection.execute(
        "SELECT accounting.post_manual_journal_entry(%s,%s)",
        (journal_id, actor_id),
    ).fetchone()[0]
    return journal_id, entry_number


def _move_to_review(connection: psycopg.Connection, period_id, actor_id) -> None:
    assert connection.execute(
        "SELECT accounting.set_fiscal_period_status(%s,'review',%s)",
        (period_id, actor_id),
    ).fetchone()[0] == "review"


def _post_close(
    connection: psycopg.Connection,
    *,
    period_id,
    actor_id,
    token: str,
    close_digest: str,
    net_income: str,
    end_date,
):
    return connection.execute(
        """
        SELECT accounting.post_period_close(
            %s,%s,%s,%s,%s,'3100',%s,%s
        )
        """,
        (
            period_id,
            actor_id,
            token,
            close_digest,
            Decimal(net_income),
            end_date,
            POLICY,
        ),
    ).fetchone()[0]


def test_formal_period_close_moves_profit_to_retained_earnings_and_locks_period() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            actor_id = _management_actor(connection, suffix)
            period_id, start_date, end_date = _period(
                connection, actor_id=actor_id, suffix=suffix
            )

            _manual_journal(
                connection,
                actor_id=actor_id,
                posting_date=start_date + timedelta(days=1),
                description="Synthetic period income",
                lines=[
                    {"account_code": "1010", "debit": "100.00", "credit": "0"},
                    {"account_code": "4000", "debit": "0", "credit": "100.00"},
                ],
            )
            _manual_journal(
                connection,
                actor_id=actor_id,
                posting_date=start_date + timedelta(days=2),
                description="Synthetic period rent",
                lines=[
                    {"account_code": "5200", "debit": "40.00", "credit": "0"},
                    {"account_code": "1010", "debit": "0", "credit": "40.00"},
                ],
            )

            _move_to_review(connection, period_id, actor_id)
            preparation_id = connection.execute(
                "SELECT accounting.prepare_period_close(%s,%s)",
                (period_id, actor_id),
            ).fetchone()[0]
            assert connection.execute(
                "SELECT accounting.prepare_period_close(%s,%s)",
                (period_id, actor_id),
            ).fetchone()[0] == preparation_id

            preparation = connection.execute(
                """
                SELECT journal_entry_id, temporary_account_count,
                       temporary_closing_debit_total,
                       temporary_closing_credit_total,
                       net_income, retained_earnings_balance_before, close_digest
                FROM accounting.period_close_preparations
                WHERE id=%s
                """,
                (preparation_id,),
            ).fetchone()
            close_journal_id = preparation[0]
            assert preparation[1:6] == (
                2,
                Decimal("100.00"),
                Decimal("40.00"),
                Decimal("60.00"),
                Decimal("0.00"),
            )
            close_digest = preparation[6]
            assert connection.execute(
                """
                SELECT line.line_number, account.code, line.debit, line.credit
                FROM accounting.journal_lines line
                JOIN accounting.accounts account ON account.id=line.account_id
                WHERE line.journal_entry_id=%s
                ORDER BY line.line_number
                """,
                (close_journal_id,),
            ).fetchall() == [
                (1, "4000", Decimal("100.00"), Decimal("0.00")),
                (2, "5200", Decimal("0.00"), Decimal("40.00")),
                (3, "3100", Decimal("0.00"), Decimal("60.00")),
            ]

            with pytest.raises(psycopg.Error, match="review are frozen"):
                with connection.transaction():
                    connection.execute(
                        """
                        INSERT INTO accounting.journal_entries(
                            fiscal_period_id, posting_date, description, source_type,
                            created_by_user_id
                        ) VALUES(%s,%s,'Bypass review freeze','manual',%s)
                        """,
                        (period_id, end_date, actor_id),
                    )

            with pytest.raises(psycopg.Error, match="protected formal period-close"):
                with connection.transaction():
                    connection.execute(
                        "SELECT accounting.set_fiscal_period_status(%s,'closed',%s)",
                        (period_id, actor_id),
                    )

            token = "a" * 64
            posting_id = _post_close(
                connection,
                period_id=period_id,
                actor_id=actor_id,
                token=token,
                close_digest=close_digest,
                net_income="60.00",
                end_date=end_date,
            )
            assert _post_close(
                connection,
                period_id=period_id,
                actor_id=actor_id,
                token=token,
                close_digest=close_digest,
                net_income="60.00",
                end_date=end_date,
            ) == posting_id

            assert connection.execute(
                "SELECT status, closed_by_user_id IS NOT NULL, closed_at IS NOT NULL FROM accounting.fiscal_periods WHERE id=%s",
                (period_id,),
            ).fetchone() == ("closed", True, True)
            assert connection.execute(
                """
                SELECT account.code, coalesce(sum(line.debit-line.credit),0)::numeric(18,2)
                FROM accounting.accounts account
                LEFT JOIN accounting.journal_lines line ON line.account_id=account.id
                LEFT JOIN accounting.journal_entries journal
                  ON journal.id=line.journal_entry_id
                 AND journal.status='posted'
                 AND journal.fiscal_period_id=%s
                WHERE account.code IN ('4000','5200')
                GROUP BY account.code ORDER BY account.code
                """,
                (period_id,),
            ).fetchall() == [
                ("4000", Decimal("0.00")),
                ("5200", Decimal("0.00")),
            ]
            assert connection.execute(
                """
                SELECT posting.retained_earnings_balance_before,
                       posting.retained_earnings_balance_after,
                       posting.confirmed_net_income,
                       queue.close_status,
                       queue.closed_period_posting_protection_enabled,
                       queue.period_reopen_enabled,
                       queue.automatic_source_posting
                FROM accounting.period_close_postings posting
                JOIN accounting.period_close_queue queue
                  ON queue.fiscal_period_id=posting.fiscal_period_id
                WHERE posting.id=%s
                """,
                (posting_id,),
            ).fetchone() == (
                Decimal("0.00"),
                Decimal("60.00"),
                Decimal("60.00"),
                "closed_protected",
                True,
                False,
                False,
            )

            with pytest.raises(psycopg.Error, match="Closed accounting periods"):
                with connection.transaction():
                    connection.execute(
                        """
                        INSERT INTO accounting.journal_entries(
                            fiscal_period_id, posting_date, description, source_type,
                            created_by_user_id
                        ) VALUES(%s,%s,'Closed bypass','manual',%s)
                        """,
                        (period_id, end_date, actor_id),
                    )
            with pytest.raises(psycopg.Error, match="cannot be reopened"):
                with connection.transaction():
                    connection.execute(
                        "SELECT accounting.set_fiscal_period_status(%s,'open',%s)",
                        (period_id, actor_id),
                    )
            with pytest.raises(psycopg.Error, match="cannot be reversed"):
                with connection.transaction():
                    connection.execute(
                        "SELECT accounting.create_reversal_draft(%s,%s,%s,%s)",
                        (close_journal_id, actor_id, end_date, "Forbidden close reversal"),
                    )

            with pytest.raises(psycopg.Error, match="different confirmation"):
                with connection.transaction():
                    _post_close(
                        connection,
                        period_id=period_id,
                        actor_id=actor_id,
                        token="b" * 64,
                        close_digest=close_digest,
                        net_income="60.00",
                        end_date=end_date,
                    )
        finally:
            connection.rollback()


def test_review_requires_no_drafts_and_forced_close_audit_failure_rolls_back() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            actor_id = _management_actor(connection, suffix)
            period_id, start_date, end_date = _period(
                connection, actor_id=actor_id, suffix=suffix
            )
            draft_id = connection.execute(
                """
                SELECT accounting.create_manual_journal_draft(%s,%s,%s,%s::jsonb)
                """,
                (
                    start_date,
                    "Unresolved draft",
                    actor_id,
                    Jsonb([
                        {"account_code": "1010", "debit": "25.00", "credit": "0"},
                        {"account_code": "4000", "debit": "0", "credit": "25.00"},
                    ]),
                ),
            ).fetchone()[0]
            with pytest.raises(psycopg.Error, match="cannot enter review while draft"):
                with connection.transaction():
                    connection.execute(
                        "SELECT accounting.set_fiscal_period_status(%s,'review',%s)",
                        (period_id, actor_id),
                    )
            connection.execute(
                "SELECT accounting.cancel_manual_journal_draft(%s,%s)",
                (draft_id, actor_id),
            )
            _manual_journal(
                connection,
                actor_id=actor_id,
                posting_date=start_date + timedelta(days=1),
                description="Income before rollback close",
                lines=[
                    {"account_code": "1010", "debit": "50.00", "credit": "0"},
                    {"account_code": "4000", "debit": "0", "credit": "50.00"},
                ],
            )
            _move_to_review(connection, period_id, actor_id)
            preparation_id = connection.execute(
                "SELECT accounting.prepare_period_close(%s,%s)",
                (period_id, actor_id),
            ).fetchone()[0]
            journal_id, digest = connection.execute(
                "SELECT journal_entry_id, close_digest FROM accounting.period_close_preparations WHERE id=%s",
                (preparation_id,),
            ).fetchone()

            with pytest.raises(psycopg.Error, match="Forced formal period-close audit failure"):
                with connection.transaction():
                    connection.execute(
                        "SELECT set_config('accounting.period_close_force_audit_failure','on',true)"
                    )
                    _post_close(
                        connection,
                        period_id=period_id,
                        actor_id=actor_id,
                        token="c" * 64,
                        close_digest=digest,
                        net_income="50.00",
                        end_date=end_date,
                    )

            assert connection.execute(
                "SELECT status FROM accounting.fiscal_periods WHERE id=%s",
                (period_id,),
            ).fetchone()[0] == "review"
            assert connection.execute(
                "SELECT status, entry_number FROM accounting.journal_entries WHERE id=%s",
                (journal_id,),
            ).fetchone() == ("draft", None)
            assert connection.execute(
                "SELECT count(*) FROM accounting.period_close_postings WHERE fiscal_period_id=%s",
                (period_id,),
            ).fetchone()[0] == 0
        finally:
            connection.rollback()


def test_zero_activity_period_can_close_without_fake_zero_value_journal() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install(connection)
            actor_id = _management_actor(connection, suffix)
            period_id, _, end_date = _period(
                connection, actor_id=actor_id, suffix=suffix
            )
            _move_to_review(connection, period_id, actor_id)
            preparation_id = connection.execute(
                "SELECT accounting.prepare_period_close(%s,%s)",
                (period_id, actor_id),
            ).fetchone()[0]
            journal_id, temp_count, net_income, retained_before, digest = connection.execute(
                """
                SELECT journal_entry_id, temporary_account_count, net_income,
                       retained_earnings_balance_before, close_digest
                FROM accounting.period_close_preparations WHERE id=%s
                """,
                (preparation_id,),
            ).fetchone()
            assert journal_id is None
            assert temp_count == 0
            assert net_income == Decimal("0.00")
            posting_id = _post_close(
                connection,
                period_id=period_id,
                actor_id=actor_id,
                token="d" * 64,
                close_digest=digest,
                net_income="0.00",
                end_date=end_date,
            )
            assert connection.execute(
                """
                SELECT journal_entry_id, entry_number,
                       retained_earnings_balance_before,
                       retained_earnings_balance_after
                FROM accounting.period_close_postings WHERE id=%s
                """,
                (posting_id,),
            ).fetchone() == (None, None, retained_before, retained_before)
            assert connection.execute(
                "SELECT status FROM accounting.fiscal_periods WHERE id=%s",
                (period_id,),
            ).fetchone()[0] == "closed"
        finally:
            connection.rollback()
