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

HELPER_PATH = Path(__file__).resolve().parent / "test_period_close_postgres.py"
_spec = importlib.util.spec_from_file_location("period_close_test_helpers", HELPER_PATH)
assert _spec is not None and _spec.loader is not None
helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(helpers)


def test_formal_period_loss_debits_retained_earnings_exactly() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            helpers._install(connection)
            actor_id = helpers._management_actor(connection, suffix)
            period_id, start_date, end_date = helpers._period(
                connection, actor_id=actor_id, suffix=suffix
            )
            helpers._manual_journal(
                connection,
                actor_id=actor_id,
                posting_date=start_date + timedelta(days=1),
                description="Synthetic loss-period income",
                lines=[
                    {"account_code": "1010", "debit": "30.00", "credit": "0"},
                    {"account_code": "4000", "debit": "0", "credit": "30.00"},
                ],
            )
            helpers._manual_journal(
                connection,
                actor_id=actor_id,
                posting_date=start_date + timedelta(days=2),
                description="Synthetic loss-period expense",
                lines=[
                    {"account_code": "5200", "debit": "50.00", "credit": "0"},
                    {"account_code": "1010", "debit": "0", "credit": "50.00"},
                ],
            )
            helpers._move_to_review(connection, period_id, actor_id)
            preparation_id = connection.execute(
                "SELECT accounting.prepare_period_close(%s,%s)",
                (period_id, actor_id),
            ).fetchone()[0]
            journal_id, net_income, digest = connection.execute(
                """
                SELECT journal_entry_id, net_income, close_digest
                FROM accounting.period_close_preparations
                WHERE id=%s
                """,
                (preparation_id,),
            ).fetchone()
            assert net_income == Decimal("-20.00")
            assert connection.execute(
                """
                SELECT line.line_number, account.code, line.debit, line.credit
                FROM accounting.journal_lines line
                JOIN accounting.accounts account ON account.id=line.account_id
                WHERE line.journal_entry_id=%s
                ORDER BY line.line_number
                """,
                (journal_id,),
            ).fetchall() == [
                (1, "4000", Decimal("30.00"), Decimal("0.00")),
                (2, "5200", Decimal("0.00"), Decimal("50.00")),
                (3, "3100", Decimal("20.00"), Decimal("0.00")),
            ]

            posting_id = helpers._post_close(
                connection,
                period_id=period_id,
                actor_id=actor_id,
                token="e" * 64,
                close_digest=digest,
                net_income="-20.00",
                end_date=end_date,
            )
            assert connection.execute(
                """
                SELECT confirmed_net_income,
                       retained_earnings_balance_before,
                       retained_earnings_balance_after
                FROM accounting.period_close_postings
                WHERE id=%s
                """,
                (posting_id,),
            ).fetchone() == (
                Decimal("-20.00"),
                Decimal("0.00"),
                Decimal("-20.00"),
            )
            assert connection.execute(
                "SELECT status FROM accounting.fiscal_periods WHERE id=%s",
                (period_id,),
            ).fetchone()[0] == "closed"
        finally:
            connection.rollback()
