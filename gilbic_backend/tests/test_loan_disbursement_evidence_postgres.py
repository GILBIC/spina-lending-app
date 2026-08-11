from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
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
SQL_0045 = (SQL_ROOT / "0045_add_authoritative_loan_disbursement_evidence.sql").read_text(
    encoding="utf-8"
)
MANILA = timezone(timedelta(hours=8))


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _create_actor(connection, suffix: str):
    return connection.execute(
        """
        insert into core.users (username, full_name, status)
        values (%s, %s, 'active')
        returning id
        """,
        (f"disbursement-{suffix}", f"Disbursement Evidence {suffix}"),
    ).fetchone()[0]


def _create_loan(connection, *, suffix: str, actor_id, release_date, principal="5000.00"):
    client_id = connection.execute(
        """
        insert into lending.clients (client_code, full_name, status)
        values (%s, %s, 'active')
        returning id
        """,
        (f"DISB-C-{suffix}", f"Disbursement Client {suffix}"),
    ).fetchone()[0]
    loan_type_id = connection.execute(
        """
        insert into lending.loan_types (
            code, name, term_days, calculation_mode, daily_interest_per_1000
        )
        values (%s, %s, 120, 'fixed_daily', 0)
        returning id
        """,
        (f"DISB-{suffix}", f"Disbursement Regular {suffix}"),
    ).fetchone()[0]
    loan_id = connection.execute(
        """
        insert into lending.loans (
            loan_number, client_id, loan_type_id, principal, daily_amount,
            date_released, due_date, status, created_by_user_id
        )
        values (%s, %s, %s, %s, 50.00, %s, %s, 'active', %s)
        returning id
        """,
        (
            f"DISB-L-{suffix}",
            client_id,
            loan_type_id,
            principal,
            release_date,
            release_date + timedelta(days=120),
            actor_id,
        ),
    ).fetchone()[0]
    return client_id, loan_id


def _record(
    connection,
    *,
    loan_id,
    actor_id,
    event_kind,
    business_date,
    cash,
    settlement="0.00",
    deduction="0.00",
    reference="RELEASE-001",
    account="cash_office",
    disbursed_at=None,
):
    exact_time = disbursed_at or datetime(
        business_date.year,
        business_date.month,
        business_date.day,
        10,
        30,
        tzinfo=MANILA,
    )
    return connection.execute(
        """
        select accounting.record_loan_disbursement_evidence(
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            loan_id,
            actor_id,
            event_kind,
            business_date,
            exact_time,
            cash,
            settlement,
            deduction,
            account,
            reference,
            "Disposable Stage 5D.19 evidence",
        ),
    ).fetchone()[0]


def test_authoritative_disbursement_evidence_is_explicit_immutable_and_policy_gated() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        required = (
            "core.users",
            "lending.clients",
            "lending.loan_types",
            "lending.loans",
            "accounting.accounts",
            "accounting.fiscal_periods",
            "accounting.journal_entries",
        )
        for relation in required:
            if connection.execute(
                "select to_regclass(%s)", (relation,)
            ).fetchone()[0] is None:
                pytest.skip(f"Accounting prerequisite is not installed: {relation}")

        try:
            assert connection.execute(
                "select to_regclass('lending.loan_disbursement_events')"
            ).fetchone()[0] is None
            before_journals = connection.execute(
                "select count(*) from accounting.journal_entries"
            ).fetchone()[0]

            connection.execute(_transaction_body(SQL_0045))

            # Installing the evidence layer must not infer/backfill funding from
            # lending.loans and must not create any journal history.
            assert connection.execute(
                "select count(*) from lending.loan_disbursement_events"
            ).fetchone()[0] == 0
            assert connection.execute(
                "select count(*) from accounting.journal_entries"
            ).fetchone()[0] == before_journals

            actor_id = _create_actor(connection, suffix)
            max_end = connection.execute(
                "select coalesce(max(end_date), date '2090-01-01') from accounting.fiscal_periods"
            ).fetchone()[0]
            release_date = max_end + timedelta(days=7)
            _, loan_id = _create_loan(
                connection,
                suffix=f"{suffix}a",
                actor_id=actor_id,
                release_date=release_date,
            )

            event_id = _record(
                connection,
                loan_id=loan_id,
                actor_id=actor_id,
                event_kind="new_loan_release",
                business_date=release_date,
                cash="5000.00",
            )

            readiness = connection.execute(
                """
                select readiness_status, source_event_key,
                       journal_lines_enabled, automatic_source_posting
                from accounting.loan_disbursement_source_readiness
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert readiness == (
                "source_evidence_ready",
                f"loan_disbursement:{event_id}",
                False,
                False,
            )

            # Exact retry is idempotent. A normal later loan-status change does
            # not rewrite or invalidate historical funding evidence.
            connection.execute(
                "update lending.loans set status = 'paid' where id = %s",
                (loan_id,),
            )
            repeated_id = _record(
                connection,
                loan_id=loan_id,
                actor_id=actor_id,
                event_kind="new_loan_release",
                business_date=release_date,
                cash="5000.00",
            )
            assert repeated_id == event_id
            assert connection.execute(
                """
                select readiness_status
                from accounting.loan_disbursement_source_readiness
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone() == ("source_evidence_ready",)

            # The protected function resets its insert GUC before returning, so
            # direct INSERT cannot piggy-back within the same SQL transaction.
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        """
                        insert into lending.loan_disbursement_events (
                            loan_id, client_id, event_kind, business_date,
                            disbursed_at, cash_disbursed_amount,
                            funding_account_system_key, external_reference,
                            principal_snapshot, date_released_snapshot,
                            loan_status_snapshot, recorded_by_user_id
                        )
                        select
                            loan.id, loan.client_id, 'new_loan_release', %s,
                            now(), 5000.00, 'cash_office', 'BYPASS',
                            loan.principal, loan.date_released, loan.status, %s
                        from lending.loans loan where loan.id = %s
                        """,
                        (release_date, actor_id, loan_id),
                    )

            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "update lending.loan_disbursement_events set evidence_note = 'tampered' where id = %s",
                        (event_id,),
                    )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "delete from lending.loan_disbursement_events where id = %s",
                        (event_id,),
                    )

            # A materially different retry cannot silently replace the active
            # source event.
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    _record(
                        connection,
                        loan_id=loan_id,
                        actor_id=actor_id,
                        event_kind="new_loan_release",
                        business_date=release_date,
                        cash="4900.00",
                        deduction="100.00",
                    )

            # Invalid funding accounts and Manila-date drift are rejected before
            # any source evidence is created.
            _, invalid_loan_id = _create_loan(
                connection,
                suffix=f"{suffix}x",
                actor_id=actor_id,
                release_date=release_date,
            )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    _record(
                        connection,
                        loan_id=invalid_loan_id,
                        actor_id=actor_id,
                        event_kind="new_loan_release",
                        business_date=release_date,
                        cash="5000.00",
                        account="loans_receivable_regular",
                    )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    _record(
                        connection,
                        loan_id=invalid_loan_id,
                        actor_id=actor_id,
                        event_kind="new_loan_release",
                        business_date=release_date,
                        cash="5000.00",
                        disbursed_at=datetime(
                            release_date.year,
                            release_date.month,
                            release_date.day,
                            23,
                            30,
                            tzinfo=timezone.utc,
                        ),
                    )

            # Renewal/restructure proceeds are captured but deliberately remain
            # policy-blocked because principal and actual cash proceeds can differ.
            _, renewal_loan_id = _create_loan(
                connection,
                suffix=f"{suffix}r",
                actor_id=actor_id,
                release_date=release_date,
            )
            _record(
                connection,
                loan_id=renewal_loan_id,
                actor_id=actor_id,
                event_kind="renewal_release",
                business_date=release_date,
                cash="2000.00",
                settlement="3000.00",
                reference="RENEWAL-001",
            )
            assert connection.execute(
                """
                select readiness_status, journal_lines_enabled
                from accounting.loan_disbursement_source_readiness
                where loan_id = %s
                """,
                (renewal_loan_id,),
            ).fetchone() == ("renewal_or_restructure_policy_review", False)

            # A loan row with date_released but no event stays explicitly missing.
            _, missing_loan_id = _create_loan(
                connection,
                suffix=f"{suffix}m",
                actor_id=actor_id,
                release_date=release_date,
            )
            assert connection.execute(
                """
                select readiness_status, disbursement_event_id
                from accounting.loan_disbursement_source_readiness
                where loan_id = %s
                """,
                (missing_loan_id,),
            ).fetchone() == ("missing_disbursement_evidence", None)

            # Unposted evidence can be explicitly voided, after which a corrected
            # event may be registered without mutating the old evidence row.
            connection.execute(
                "select accounting.void_loan_disbursement_evidence(%s, %s, %s)",
                (event_id, actor_id, "Wrong release reference"),
            )
            assert connection.execute(
                "select is_voided from lending.loan_disbursement_events where id = %s",
                (event_id,),
            ).fetchone() == (True,)
            corrected_id = _record(
                connection,
                loan_id=loan_id,
                actor_id=actor_id,
                event_kind="new_loan_release",
                business_date=release_date,
                cash="5000.00",
                reference="RELEASE-002",
            )
            assert corrected_id != event_id

            # Once any accounting journal history is linked to the source event,
            # this evidence-only stage refuses to void it. A later accounting
            # slice must provide the protected cancellation/reversal path.
            period_id = connection.execute(
                """
                insert into accounting.fiscal_periods (
                    label, start_date, end_date, status
                ) values (%s, %s, %s, 'open')
                returning id
                """,
                (f"Disbursement {suffix}", release_date, release_date),
            ).fetchone()[0]
            connection.execute(
                """
                insert into accounting.journal_entries (
                    fiscal_period_id, posting_date, description, status,
                    source_type, source_reference, source_event_key,
                    created_by_user_id, updated_at
                ) values (
                    %s, %s, 'Synthetic future disbursement journal', 'draft',
                    'loan_disbursement', %s, %s, %s, now()
                )
                """,
                (
                    period_id,
                    release_date,
                    str(corrected_id),
                    f"loan_disbursement:{corrected_id}",
                    actor_id,
                ),
            )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "select accounting.void_loan_disbursement_evidence(%s, %s, %s)",
                        (corrected_id, actor_id, "Cannot bypass journal history"),
                    )
            assert connection.execute(
                "select is_voided from lending.loan_disbursement_events where id = %s",
                (corrected_id,),
            ).fetchone() == (False,)
        finally:
            connection.rollback()
