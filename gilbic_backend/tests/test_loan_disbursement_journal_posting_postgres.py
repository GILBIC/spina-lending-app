from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
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
SQL_0048 = (
    SQL_ROOT / "0048_add_protected_new_loan_disbursement_journal_posting.sql"
).read_text(encoding="utf-8")
MANILA = timezone(timedelta(hours=8))


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _actor(connection, suffix: str):
    return connection.execute(
        """
        insert into core.users (username, full_name, status)
        values (%s, %s, 'active') returning id
        """,
        (f"d22-{suffix}", f"Stage 5D.22 {suffix}"),
    ).fetchone()[0]


def _loan(connection, *, suffix: str, actor_id, release_date, principal="5000.00"):
    client_id = connection.execute(
        """
        insert into lending.clients (client_code, full_name, status)
        values (%s, %s, 'active') returning id
        """,
        (f"D22-C-{suffix}", f"D22 Client {suffix}"),
    ).fetchone()[0]
    loan_type_id = connection.execute(
        """
        insert into lending.loan_types (
            code, name, term_days, calculation_mode, daily_interest_per_1000
        ) values (%s, %s, 120, 'fixed_daily', 0) returning id
        """,
        (f"D22-T-{suffix}", f"D22 Regular {suffix}"),
    ).fetchone()[0]
    loan_id = connection.execute(
        """
        insert into lending.loans (
            loan_number, client_id, loan_type_id, principal, daily_amount,
            interest_rate, date_released, due_date, status, created_by_user_id
        ) values (%s, %s, %s, %s, 50.00, 20.0000, %s, %s, 'active', %s)
        returning id
        """,
        (
            f"D22-L-{suffix}", client_id, loan_type_id, principal,
            release_date, release_date + timedelta(days=120), actor_id,
        ),
    ).fetchone()[0]
    return client_id, loan_id


def _record(connection, *, loan_id, actor_id, business_date, reference):
    disbursed_at = datetime(
        business_date.year,
        business_date.month,
        business_date.day,
        10,
        0,
        tzinfo=MANILA,
    )
    return connection.execute(
        """
        select accounting.record_loan_disbursement_evidence(
            %s, %s, 'new_loan_release', %s, %s, 5000.00,
            0.00, 0.00, 'cash_office', %s, %s
        )
        """,
        (
            loan_id,
            actor_id,
            business_date,
            disbursed_at,
            reference,
            "Stage 5D.22 disposable posting evidence",
        ),
    ).fetchone()[0]


def _coordinate(connection, event_id):
    return connection.execute(
        """
        select
            source_event_key, posting_date, fiscal_period_id,
            debit_account_id, credit_account_id, debit_amount
        from accounting.loan_disbursement_journal_coordinates
        where disbursement_event_id = %s
          and coordinate_status = 'coordinate_ready'
        """,
        (event_id,),
    ).fetchone()


def _prepare(connection, *, event_id, actor_id, draft_token):
    coordinate = _coordinate(connection, event_id)
    assert coordinate is not None
    preparation_id = connection.execute(
        """
        select accounting.create_new_loan_disbursement_journal_draft(
            %s, %s, %s, %s, %s, %s, %s, %s, %s,
            'new_loan_disbursement_coordinates_v1',
            'new_loan_disbursement_journal_draft_v1'
        )
        """,
        (
            event_id,
            actor_id,
            draft_token,
            coordinate[0],
            coordinate[1],
            coordinate[2],
            coordinate[3],
            coordinate[4],
            coordinate[5],
        ),
    ).fetchone()[0]
    status = connection.execute(
        """
        select preparation_id, journal_entry_id, source_event_key,
               draft_review_token, posting_date, fiscal_period_id,
               debit_account_id, credit_account_id, amount,
               total_debit, total_credit, posting_ready
        from accounting.loan_disbursement_journal_posting_status
        where preparation_id = %s
        """,
        (preparation_id,),
    ).fetchone()
    return status


def _post(connection, *, actor_id, status, posting_token):
    return connection.execute(
        """
        select accounting.post_new_loan_disbursement_journal(
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            'new_loan_disbursement_journal_posting_v1'
        )
        """,
        (
            status[0], actor_id, posting_token, status[1], status[2], status[3],
            status[4], status[5], status[6], status[7], status[8], status[9], status[10],
        ),
    ).fetchone()[0]


def test_new_regular_disbursement_posting_is_explicit_idempotent_audited_and_atomic() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    draft_token = "a" * 64
    posting_token = "b" * 64

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            assert connection.execute(
                "select to_regclass('accounting.loan_disbursement_journal_draft_preparations')"
            ).fetchone()[0] is not None
            assert connection.execute(
                "select to_regclass('accounting.loan_disbursement_journal_postings')"
            ).fetchone()[0] is None

            before = (
                connection.execute("select count(*) from accounting.journal_entries").fetchone()[0],
                connection.execute("select count(*) from accounting.journal_lines").fetchone()[0],
                connection.execute("select count(*) from core.audit_logs").fetchone()[0],
            )
            connection.execute(_transaction_body(SQL_0048))
            after_install = (
                connection.execute("select count(*) from accounting.journal_entries").fetchone()[0],
                connection.execute("select count(*) from accounting.journal_lines").fetchone()[0],
                connection.execute("select count(*) from core.audit_logs").fetchone()[0],
            )
            assert after_install == before
            assert connection.execute(
                "select count(*) from accounting.loan_disbursement_journal_postings"
            ).fetchone()[0] == 0

            actor_id = _actor(connection, suffix)
            max_end = connection.execute(
                "select coalesce(max(end_date), date '2090-01-01') from accounting.fiscal_periods"
            ).fetchone()[0]
            release_date = max_end + timedelta(days=7)
            connection.execute(
                """
                insert into accounting.fiscal_periods (
                    label, start_date, end_date, status
                ) values (%s, %s, %s, 'open')
                """,
                (f"D22 {suffix}", release_date, release_date),
            )

            _, loan_id = _loan(
                connection,
                suffix=f"{suffix}a",
                actor_id=actor_id,
                release_date=release_date,
            )
            event_id = _record(
                connection,
                loan_id=loan_id,
                actor_id=actor_id,
                business_date=release_date,
                reference="D22-REL-1",
            )
            status = _prepare(
                connection,
                event_id=event_id,
                actor_id=actor_id,
                draft_token=draft_token,
            )
            assert status[-1] is True
            journal_id = status[1]

            # Neither generic nor manual General Journal posting can bypass the
            # protected Stage 5D.22 workflow.
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "select accounting.post_journal_entry(%s, %s)",
                        (journal_id, actor_id),
                    )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "select accounting.post_manual_journal_entry(%s, %s)",
                        (journal_id, actor_id),
                    )
            assert connection.execute(
                "select status, entry_number from accounting.journal_entries where id = %s",
                (journal_id,),
            ).fetchone() == ("draft", None)

            # Exact confirmation mismatch fails before any status transition.
            bad_status = list(status)
            bad_status[8] = Decimal("4999.00")
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    _post(
                        connection,
                        actor_id=actor_id,
                        status=bad_status,
                        posting_token=posting_token,
                    )
            assert connection.execute(
                "select status from accounting.journal_entries where id = %s",
                (journal_id,),
            ).fetchone() == ("draft",)
            assert connection.execute(
                "select count(*) from accounting.loan_disbursement_journal_postings where preparation_id = %s",
                (status[0],),
            ).fetchone()[0] == 0

            posting_id = _post(
                connection,
                actor_id=actor_id,
                status=status,
                posting_token=posting_token,
            )
            posted = connection.execute(
                """
                select posting_id, journal_status, entry_number,
                       posting_review_token, posting_policy_version,
                       posting_ready, posted_audit_exact,
                       protected_posting_enabled, automatic_source_posting
                from accounting.loan_disbursement_journal_posting_status
                where preparation_id = %s
                """,
                (status[0],),
            ).fetchone()
            assert posted[0] == posting_id
            assert posted[1] == "posted"
            assert posted[2].startswith(f"JE-{release_date:%Y%m}-")
            assert posted[3] == posting_token
            assert posted[4] == "new_loan_disbursement_journal_posting_v1"
            assert posted[5:] == (False, True, True, False)

            audit = connection.execute(
                """
                select journal_entry_id, source_event_key, draft_review_token,
                       posting_review_token, amount, entry_number,
                       posted_by_user_id
                from accounting.loan_disbursement_journal_postings
                where id = %s
                """,
                (posting_id,),
            ).fetchone()
            assert audit == (
                journal_id,
                f"loan_disbursement:{event_id}",
                draft_token,
                posting_token,
                Decimal("5000.00"),
                posted[2],
                actor_id,
            )

            # Exact retry returns the same immutable posting and entry number.
            assert _post(
                connection,
                actor_id=actor_id,
                status=status,
                posting_token=posting_token,
            ) == posting_id
            assert connection.execute(
                "select count(*) from accounting.loan_disbursement_journal_postings where preparation_id = %s",
                (status[0],),
            ).fetchone()[0] == 1

            # Different retry identity and audit mutation are rejected.
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    _post(
                        connection,
                        actor_id=actor_id,
                        status=status,
                        posting_token="c" * 64,
                    )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "update accounting.loan_disbursement_journal_postings set posting_review_token = %s where id = %s",
                        ("d" * 64, posting_id),
                    )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "delete from accounting.loan_disbursement_journal_postings where id = %s",
                        (posting_id,),
                    )

            # Posted source evidence cannot be erased by the evidence-only path.
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "select accounting.void_loan_disbursement_evidence(%s, %s, %s)",
                        (event_id, actor_id, "Posted source requires protected reversal"),
                    )

            # Prove whole-statement atomic rollback: force the immutable posting
            # audit INSERT to fail after the journal transition is attempted.
            _, rollback_loan_id = _loan(
                connection,
                suffix=f"{suffix}b",
                actor_id=actor_id,
                release_date=release_date,
            )
            rollback_event_id = _record(
                connection,
                loan_id=rollback_loan_id,
                actor_id=actor_id,
                business_date=release_date,
                reference="D22-REL-ROLLBACK",
            )
            rollback_status = _prepare(
                connection,
                event_id=rollback_event_id,
                actor_id=actor_id,
                draft_token="e" * 64,
            )
            rollback_journal_id = rollback_status[1]

            connection.execute(
                """
                create or replace function accounting.test_fail_d22_posting_audit()
                returns trigger language plpgsql as $$
                begin
                    raise exception 'forced Stage 5D.22 posting audit failure';
                end;
                $$
                """
            )
            connection.execute(
                """
                create trigger zzz_test_fail_d22_posting_audit
                before insert on accounting.loan_disbursement_journal_postings
                for each row execute function accounting.test_fail_d22_posting_audit()
                """
            )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    _post(
                        connection,
                        actor_id=actor_id,
                        status=rollback_status,
                        posting_token="f" * 64,
                    )

            assert connection.execute(
                "select status, entry_number, posted_by_user_id, posted_at from accounting.journal_entries where id = %s",
                (rollback_journal_id,),
            ).fetchone() == ("draft", None, None, None)
            assert connection.execute(
                "select count(*) from accounting.loan_disbursement_journal_postings where preparation_id = %s",
                (rollback_status[0],),
            ).fetchone()[0] == 0
            connection.execute(
                "drop trigger zzz_test_fail_d22_posting_audit on accounting.loan_disbursement_journal_postings"
            )
            connection.execute(
                "drop function accounting.test_fail_d22_posting_audit()"
            )
        finally:
            connection.rollback()
