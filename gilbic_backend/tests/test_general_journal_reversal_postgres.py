from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="Disposable PostgreSQL URL is not configured"
)
MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0131_allow_reviewed_journal_reversal_post.sql"
)


@pytest.fixture
def journal_db():
    assert DATABASE_URL is not None
    assert os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") == "1"
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            sql = MIGRATION.read_text(encoding="utf-8").strip()
            connection.execute(sql[len("BEGIN;") : -len("COMMIT;")])
            actor = connection.execute(
                "INSERT INTO core.users(username,full_name,status) VALUES(%s,'Synthetic Journal Manager','active') RETURNING id",
                (f"journal-reversal-{uuid4().hex}",),
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO core.user_roles(user_id,role_id) SELECT %s,id FROM core.roles WHERE code='management'",
                (actor,),
            )
            period = connection.execute(
                "SELECT accounting.create_fiscal_period(%s,%s,%s,%s)",
                (
                    f"Synthetic reversal {uuid4().hex}",
                    date(2050, 1, 1),
                    date(2050, 1, 31),
                    actor,
                ),
            ).fetchone()[0]
            yield connection, actor, period
        finally:
            connection.rollback()


def _draft(connection, actor):
    return connection.execute(
        "SELECT accounting.create_manual_journal_draft(%s,%s,%s,%s::jsonb)",
        (
            date(2050, 1, 2),
            "Synthetic exact original",
            actor,
            Jsonb(
                [
                    {"account_code": "1010", "debit": "1234.56", "credit": "0.00"},
                    {"account_code": "3000", "debit": "0.00", "credit": "1234.56"},
                ]
            ),
        ),
    ).fetchone()[0]


def _post(connection, actor, entry):
    return connection.execute(
        "SELECT accounting.post_manual_journal_entry(%s,%s)", (entry, actor)
    ).fetchone()[0]


def _reverse(connection, actor, entry):
    return connection.execute(
        "SELECT accounting.create_manual_reversal_draft(%s,%s,%s,%s)",
        (entry, actor, date(2050, 1, 3), "Reviewed reversal"),
    ).fetchone()[0]


def test_reviewed_reversal_posts_balanced_lines_without_changing_original(journal_db):
    connection, actor, _ = journal_db
    original = _draft(connection, actor)
    _post(connection, actor, original)
    before = connection.execute(
        "SELECT to_jsonb(j) FROM accounting.journal_entries j WHERE id=%s", (original,)
    ).fetchone()[0]
    with (
        pytest.raises(psycopg.Error, match="immutable|posted"),
        connection.transaction(),
    ):
        connection.execute(
            "UPDATE accounting.journal_entries SET description='Changed original' WHERE id=%s",
            (original,),
        )
    reversal = _reverse(connection, actor, original)
    assert _post(connection, actor, reversal)
    row = connection.execute(
        "SELECT status,source_type,reversal_of_entry_id FROM accounting.journal_entries WHERE id=%s",
        (reversal,),
    ).fetchone()
    assert row == ("posted", "reversal", original)
    assert (
        connection.execute(
            "SELECT to_jsonb(j) FROM accounting.journal_entries j WHERE id=%s",
            (original,),
        ).fetchone()[0]
        == before
    )
    assert connection.execute(
        "SELECT sum(debit),sum(credit) FROM accounting.journal_lines WHERE journal_entry_id IN (%s,%s)",
        (original, reversal),
    ).fetchone() == (Decimal("2469.12"), Decimal("2469.12"))
    assert (
        connection.execute(
            "SELECT count(*) FROM accounting.journal_events WHERE journal_entry_id=%s AND event_type='posted'",
            (reversal,),
        ).fetchone()[0]
        == 1
    )
    with pytest.raises(psycopg.Error, match="draft"), connection.transaction():
        _post(connection, actor, reversal)
    with (
        pytest.raises(psycopg.Error, match="already has a reversal"),
        connection.transaction(),
    ):
        _reverse(connection, actor, original)
    with (
        pytest.raises(psycopg.Error, match="cannot be reversed again"),
        connection.transaction(),
    ):
        _reverse(connection, actor, reversal)


@pytest.mark.parametrize(
    "source_type",
    [None, "loan_interest", "opening_balance", "period_close", "reversal"],
)
def test_generated_or_unlinked_drafts_cannot_use_manual_posting(
    journal_db, source_type
):
    connection, actor, _ = journal_db
    draft = _draft(connection, actor)
    connection.execute(
        "UPDATE accounting.journal_entries SET source_type=%s WHERE id=%s",
        (source_type, draft),
    )
    with (
        pytest.raises(psycopg.Error, match="manual|reversal|protected"),
        connection.transaction(),
    ):
        _post(connection, actor, draft)
    assert (
        connection.execute(
            "SELECT status FROM accounting.journal_entries WHERE id=%s", (draft,)
        ).fetchone()[0]
        == "draft"
    )


def test_changed_reversal_lines_cannot_be_posted(journal_db):
    connection, actor, _ = journal_db
    original = _draft(connection, actor)
    _post(connection, actor, original)
    reversal = _reverse(connection, actor, original)
    connection.execute(
        "UPDATE accounting.journal_lines SET debit=debit*2,credit=credit*2 WHERE journal_entry_id=%s",
        (reversal,),
    )
    with (
        pytest.raises(psycopg.Error, match="exact reversed lines"),
        connection.transaction(),
    ):
        _post(connection, actor, reversal)
    assert (
        connection.execute(
            "SELECT status FROM accounting.journal_entries WHERE id=%s", (reversal,)
        ).fetchone()[0]
        == "draft"
    )


@pytest.mark.parametrize("field", ["source_event_key", "source_reference"])
def test_changed_reversal_linkage_cannot_be_posted(journal_db, field):
    connection, actor, _ = journal_db
    original = _draft(connection, actor)
    _post(connection, actor, original)
    reversal = _reverse(connection, actor, original)
    connection.execute(
        psycopg.sql.SQL(
            "UPDATE accounting.journal_entries SET {}=%s WHERE id=%s"
        ).format(psycopg.sql.Identifier(field)),
        ("incorrect reviewed linkage", reversal),
    )
    with (
        pytest.raises(psycopg.Error, match="linked reversal"),
        connection.transaction(),
    ):
        _post(connection, actor, reversal)
    assert (
        connection.execute(
            "SELECT status FROM accounting.journal_entries WHERE id=%s", (reversal,)
        ).fetchone()[0]
        == "draft"
    )
