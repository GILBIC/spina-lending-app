"""The close invariant includes every posted temporary-account balance."""

import os
import re
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest
import test_period_close_postgres as close
from psycopg import sql
from psycopg.conninfo import make_conninfo

from tools import run_stage5d17_disposable_postgres_validation as disposable

URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not URL, reason="Guarded disposable PostgreSQL is not configured"
)


@pytest.fixture
def connection():
    if os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") != "1":
        raise RuntimeError("Close proofs require explicitly disposable PostgreSQL")
    params = disposable._safe_local_connection_params(URL)
    if not re.fullmatch(
        r"spina_(?:onboarding_[0-9a-f]{12}|period_close_[0-9a-f]{32})", params["dbname"]
    ):
        raise RuntimeError(
            "Close proofs require a generated onboarding disposable database"
        )
    disposable._clear_endpoint_environment()
    with psycopg.connect(make_conninfo(**params)) as conn:
        try:
            close._install(conn)
            yield conn
        finally:
            conn.rollback()


@pytest.mark.parametrize("flag", ["is_active", "is_posting"])
@pytest.mark.parametrize("after_preparation", [False, True])
def test_close_blocks_nonposting_or_retired_balances_before_prepare_and_post(
    connection, flag, after_preparation
):
    conn = connection
    suffix = uuid4().hex[:10]
    actor = close._management_actor(conn, suffix)
    period, start, end = close._period(conn, actor_id=actor, suffix=suffix)
    close._manual_journal(
        conn,
        actor_id=actor,
        posting_date=start,
        description="Synthetic expense later retired",
        lines=[
            {"account_code": "5200", "debit": "40.00", "credit": "0"},
            {"account_code": "1010", "debit": "0", "credit": "40.00"},
        ],
    )
    close._move_to_review(conn, period, actor)
    preparation = None
    if after_preparation:
        preparation = conn.execute(
            "SELECT accounting.prepare_period_close(%s,%s)", (period, actor)
        ).fetchone()[0]
    before = conn.execute(
        "SELECT id,status FROM accounting.journal_entries WHERE fiscal_period_id=%s ORDER BY id",
        (period,),
    ).fetchall()
    conn.execute(
        sql.SQL("UPDATE accounting.accounts SET {}=false WHERE code='5200'").format(
            sql.Identifier(flag)
        )
    )
    with pytest.raises(psycopg.Error, match="inactive|nonposting"), conn.transaction():
        if after_preparation:
            digest = conn.execute(
                "SELECT close_digest FROM accounting.period_close_preparations WHERE id=%s",
                (preparation,),
            ).fetchone()[0]
            close._post_close(
                conn,
                period_id=period,
                actor_id=actor,
                token="a" * 64,
                close_digest=digest,
                net_income="-40.00",
                end_date=end,
            )
        else:
            conn.execute(
                "SELECT accounting.prepare_period_close(%s,%s)", (period, actor)
            )
    assert (
        conn.execute(
            "SELECT status FROM accounting.fiscal_periods WHERE id=%s", (period,)
        ).fetchone()[0]
        == "review"
    )
    assert (
        conn.execute(
            "SELECT id,status FROM accounting.journal_entries WHERE fiscal_period_id=%s ORDER BY id",
            (period,),
        ).fetchall()
        == before
    )
    assert (
        conn.execute(
            "SELECT count(*) FROM accounting.period_close_postings WHERE fiscal_period_id=%s",
            (period,),
        ).fetchone()[0]
        == 0
    )
    assert conn.execute(
        "SELECT count(*) FROM accounting.period_close_preparations WHERE fiscal_period_id=%s",
        (period,),
    ).fetchone()[0] == int(after_preparation)

    conn.execute(
        sql.SQL("UPDATE accounting.accounts SET {}=true WHERE code='5200'").format(
            sql.Identifier(flag)
        )
    )
    preparation = conn.execute(
        "SELECT accounting.prepare_period_close(%s,%s)", (period, actor)
    ).fetchone()[0]
    digest = conn.execute(
        "SELECT close_digest FROM accounting.period_close_preparations WHERE id=%s",
        (preparation,),
    ).fetchone()[0]
    close._post_close(
        conn,
        period_id=period,
        actor_id=actor,
        token="a" * 64,
        close_digest=digest,
        net_income="-40.00",
        end_date=end,
    )
    # Independent unfiltered ledger query: a shared filtered helper cannot hide a residual.
    assert (
        conn.execute(
            """
        SELECT account.id, sum(line.debit-line.credit)
        FROM accounting.accounts account
        JOIN accounting.journal_lines line ON line.account_id=account.id
        JOIN accounting.journal_entries journal ON journal.id=line.journal_entry_id
        WHERE journal.fiscal_period_id=%s AND journal.status='posted'
          AND account.account_type IN ('income','expense')
        GROUP BY account.id HAVING sum(line.debit-line.credit)<>0
    """,
            (period,),
        ).fetchall()
        == []
    )
    assert conn.execute(
        "SELECT retained_earnings_balance_after FROM accounting.period_close_postings WHERE fiscal_period_id=%s",
        (period,),
    ).fetchone()[0] == Decimal("-40.00")
