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
SQL_0050 = (SQL_ROOT / "0050_add_authoritative_renewal_execution_evidence.sql").read_text(
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
        (f"renewal-exec-{suffix}", f"Renewal Execution {suffix}"),
    ).fetchone()[0]


def _create_client(connection, suffix: str):
    return connection.execute(
        """
        insert into lending.clients (client_code, full_name, status)
        values (%s, %s, 'active')
        returning id
        """,
        (f"REN-C-{suffix}", f"Renewal Client {suffix}"),
    ).fetchone()[0]


def _create_loan_type(connection, *, suffix: str, calculation_mode: str = "fixed_daily"):
    return connection.execute(
        """
        insert into lending.loan_types (
            code, name, term_days, calculation_mode, daily_interest_per_1000
        )
        values (%s, %s, 120, %s, 0)
        returning id
        """,
        (f"REN-{suffix}", f"Renewal Type {suffix}", calculation_mode),
    ).fetchone()[0]


def _create_loan(
    connection,
    *,
    suffix: str,
    actor_id,
    client_id,
    loan_type_id,
    release_date,
    principal="5000.00",
    status="active",
):
    return connection.execute(
        """
        insert into lending.loans (
            loan_number, client_id, loan_type_id, principal, daily_amount,
            date_released, due_date, status, created_by_user_id
        )
        values (%s, %s, %s, %s, 50.00, %s, %s, %s, %s)
        returning id
        """,
        (
            f"REN-L-{suffix}",
            client_id,
            loan_type_id,
            principal,
            release_date,
            release_date + timedelta(days=120),
            status,
            actor_id,
        ),
    ).fetchone()[0]


def _record_release(
    connection,
    *,
    new_loan_id,
    actor_id,
    business_date,
    cash="2000.00",
    settlement="3000.00",
    deduction="0.00",
    event_kind="renewal_release",
    reference="RENEW-RELEASE-001",
):
    return connection.execute(
        """
        select accounting.record_loan_disbursement_evidence(
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            new_loan_id,
            actor_id,
            event_kind,
            business_date,
            datetime(
                business_date.year,
                business_date.month,
                business_date.day,
                10,
                0,
                tzinfo=MANILA,
            ),
            cash,
            settlement,
            deduction,
            "cash_office",
            reference,
            "Disposable Stage 5D.24 renewal release evidence",
        ),
    ).fetchone()[0]


def _create_approved_request(
    connection,
    *,
    client_id,
    old_loan_id,
    actor_id,
    requested_amount="5000.00",
):
    return connection.execute(
        """
        insert into lending.client_renewal_requests (
            client_id, loan_id, requested_by_user_id, requested_amount,
            client_message, status, reviewed_by_user_id, review_note,
            reviewed_at
        )
        values (
            %s, %s, %s, %s, 'Please renew', 'approved', %s,
            'Approved for office processing', now()
        )
        returning id
        """,
        (client_id, old_loan_id, actor_id, requested_amount, actor_id),
    ).fetchone()[0]


def _record_execution(
    connection,
    *,
    old_loan_id,
    new_loan_id,
    disbursement_event_id,
    actor_id,
    business_date,
    settlement="3000.00",
    reference="RENEW-EXEC-001",
    renewal_request_id=None,
    executed_at=None,
):
    exact_time = executed_at or datetime(
        business_date.year,
        business_date.month,
        business_date.day,
        10,
        5,
        tzinfo=MANILA,
    )
    return connection.execute(
        """
        select accounting.record_loan_renewal_execution_evidence(
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            old_loan_id,
            new_loan_id,
            disbursement_event_id,
            actor_id,
            business_date,
            exact_time,
            settlement,
            reference,
            "Disposable Stage 5D.24 execution evidence",
            renewal_request_id,
        ),
    ).fetchone()[0]


def test_renewal_execution_evidence_is_explicit_immutable_and_policy_gated() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        required = (
            "core.users",
            "lending.clients",
            "lending.loan_types",
            "lending.loans",
            "lending.client_renewal_requests",
            "lending.loan_disbursement_events",
            "accounting.journal_entries",
        )
        for relation in required:
            if connection.execute(
                "select to_regclass(%s)", (relation,)
            ).fetchone()[0] is None:
                pytest.skip(f"Accounting prerequisite is not installed: {relation}")

        try:
            assert connection.execute(
                "select to_regclass('lending.loan_renewal_execution_events')"
            ).fetchone()[0] is None
            before_journals = connection.execute(
                "select count(*) from accounting.journal_entries"
            ).fetchone()[0]

            connection.execute(_transaction_body(SQL_0050))

            # Installation is evidence-only: no inferred old->new relationship,
            # no backfill, and no journal history.
            assert connection.execute(
                "select count(*) from lending.loan_renewal_execution_events"
            ).fetchone()[0] == 0
            assert connection.execute(
                "select count(*) from accounting.journal_entries"
            ).fetchone()[0] == before_journals

            actor_id = _create_actor(connection, suffix)
            client_id = _create_client(connection, suffix)
            loan_type_id = _create_loan_type(connection, suffix=f"{suffix}a")
            max_end = connection.execute(
                "select coalesce(max(end_date), date '2090-01-01') from accounting.fiscal_periods"
            ).fetchone()[0]
            old_date = max_end + timedelta(days=7)
            renew_date = old_date + timedelta(days=30)
            old_loan_id = _create_loan(
                connection,
                suffix=f"{suffix}old",
                actor_id=actor_id,
                client_id=client_id,
                loan_type_id=loan_type_id,
                release_date=old_date,
            )
            new_loan_id = _create_loan(
                connection,
                suffix=f"{suffix}new",
                actor_id=actor_id,
                client_id=client_id,
                loan_type_id=loan_type_id,
                release_date=renew_date,
            )
            release_event_id = _record_release(
                connection,
                new_loan_id=new_loan_id,
                actor_id=actor_id,
                business_date=renew_date,
            )

            # The renewal_release proves release economics but does not itself
            # prove which old loan was actually settled.
            assert connection.execute(
                """
                select readiness_status, renewal_execution_event_id,
                       journal_lines_enabled, automatic_source_posting
                from accounting.loan_renewal_execution_source_readiness
                where disbursement_event_id = %s
                """,
                (release_event_id,),
            ).fetchone() == (
                "missing_renewal_execution_evidence",
                None,
                False,
                False,
            )

            request_id = _create_approved_request(
                connection,
                client_id=client_id,
                old_loan_id=old_loan_id,
                actor_id=actor_id,
            )
            execution_id = _record_execution(
                connection,
                old_loan_id=old_loan_id,
                new_loan_id=new_loan_id,
                disbursement_event_id=release_event_id,
                actor_id=actor_id,
                business_date=renew_date,
                renewal_request_id=request_id,
            )

            readiness = connection.execute(
                """
                select readiness_status, source_event_key,
                       old_loan_settlement_amount, settlement_amount,
                       journal_lines_enabled, automatic_source_posting
                from accounting.loan_renewal_execution_source_readiness
                where disbursement_event_id = %s
                """,
                (release_event_id,),
            ).fetchone()
            assert readiness == (
                "renewal_execution_evidence_ready",
                f"loan_renewal_execution:{execution_id}",
                3000,
                3000,
                False,
                False,
            )

            # Exact retries are idempotent and do not duplicate evidence.
            repeated_id = _record_execution(
                connection,
                old_loan_id=old_loan_id,
                new_loan_id=new_loan_id,
                disbursement_event_id=release_event_id,
                actor_id=actor_id,
                business_date=renew_date,
                renewal_request_id=request_id,
            )
            assert repeated_id == execution_id
            assert connection.execute(
                "select count(*) from lending.loan_renewal_execution_events where new_loan_id = %s",
                (new_loan_id,),
            ).fetchone() == (1,)

            # Direct insert/update/delete cannot bypass the protected evidence API.
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        """
                        insert into lending.loan_renewal_execution_events (
                            old_loan_id, new_loan_id, disbursement_event_id,
                            client_id, business_date, executed_at,
                            old_loan_settlement_amount, external_reference,
                            old_loan_principal_snapshot,
                            old_loan_date_released_snapshot,
                            old_loan_status_snapshot,
                            new_loan_principal_snapshot,
                            new_loan_date_released_snapshot,
                            new_loan_status_snapshot, recorded_by_user_id
                        )
                        select
                            %s, %s, %s, %s, %s, now(), 3000.00, 'BYPASS',
                            5000.00, %s, 'active', 5000.00, %s, 'active', %s
                        """,
                        (
                            old_loan_id,
                            new_loan_id,
                            release_event_id,
                            client_id,
                            renew_date,
                            old_date,
                            renew_date,
                            actor_id,
                        ),
                    )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "update lending.loan_renewal_execution_events set evidence_note = 'tampered' where id = %s",
                        (execution_id,),
                    )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "delete from lending.loan_renewal_execution_events where id = %s",
                        (execution_id,),
                    )

            # A materially different retry cannot silently replace the active link.
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    _record_execution(
                        connection,
                        old_loan_id=old_loan_id,
                        new_loan_id=new_loan_id,
                        disbursement_event_id=release_event_id,
                        actor_id=actor_id,
                        business_date=renew_date,
                        settlement="2999.00",
                        renewal_request_id=request_id,
                    )

            # A client request is optional, but when supplied it must be approved
            # for this same client and old loan; a request alone never proves execution.
            pending_client = _create_client(connection, f"{suffix}p")
            pending_type = _create_loan_type(connection, suffix=f"{suffix}p")
            pending_old = _create_loan(
                connection,
                suffix=f"{suffix}po",
                actor_id=actor_id,
                client_id=pending_client,
                loan_type_id=pending_type,
                release_date=old_date,
            )
            pending_new = _create_loan(
                connection,
                suffix=f"{suffix}pn",
                actor_id=actor_id,
                client_id=pending_client,
                loan_type_id=pending_type,
                release_date=renew_date,
            )
            pending_release = _record_release(
                connection,
                new_loan_id=pending_new,
                actor_id=actor_id,
                business_date=renew_date,
                reference="RENEW-RELEASE-PENDING",
            )
            pending_request = connection.execute(
                """
                insert into lending.client_renewal_requests (
                    client_id, loan_id, requested_by_user_id,
                    requested_amount, status
                ) values (%s, %s, %s, 5000.00, 'pending')
                returning id
                """,
                (pending_client, pending_old, actor_id),
            ).fetchone()[0]
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    _record_execution(
                        connection,
                        old_loan_id=pending_old,
                        new_loan_id=pending_new,
                        disbursement_event_id=pending_release,
                        actor_id=actor_id,
                        business_date=renew_date,
                        renewal_request_id=pending_request,
                    )
            assert connection.execute(
                """
                select readiness_status
                from accounting.loan_renewal_execution_source_readiness
                where disbursement_event_id = %s
                """,
                (pending_release,),
            ).fetchone() == ("missing_renewal_execution_evidence",)

            # Wrong source kind, cross-client old/new links, and Manila-date drift
            # are rejected before execution evidence exists.
            wrong_client = _create_client(connection, f"{suffix}x")
            wrong_old = _create_loan(
                connection,
                suffix=f"{suffix}xo",
                actor_id=actor_id,
                client_id=wrong_client,
                loan_type_id=loan_type_id,
                release_date=old_date,
            )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    _record_execution(
                        connection,
                        old_loan_id=wrong_old,
                        new_loan_id=pending_new,
                        disbursement_event_id=pending_release,
                        actor_id=actor_id,
                        business_date=renew_date,
                    )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    _record_execution(
                        connection,
                        old_loan_id=pending_old,
                        new_loan_id=pending_new,
                        disbursement_event_id=pending_release,
                        actor_id=actor_id,
                        business_date=renew_date,
                        executed_at=datetime(
                            renew_date.year,
                            renew_date.month,
                            renew_date.day,
                            23,
                            30,
                            tzinfo=timezone.utc,
                        ),
                    )

            kind_client = _create_client(connection, f"{suffix}k")
            kind_type = _create_loan_type(connection, suffix=f"{suffix}k")
            kind_old = _create_loan(
                connection,
                suffix=f"{suffix}ko",
                actor_id=actor_id,
                client_id=kind_client,
                loan_type_id=kind_type,
                release_date=old_date,
            )
            kind_new = _create_loan(
                connection,
                suffix=f"{suffix}kn",
                actor_id=actor_id,
                client_id=kind_client,
                loan_type_id=kind_type,
                release_date=renew_date,
            )
            wrong_kind_release = _record_release(
                connection,
                new_loan_id=kind_new,
                actor_id=actor_id,
                business_date=renew_date,
                cash="5000.00",
                settlement="0.00",
                event_kind="new_loan_release",
                reference="NOT-A-RENEWAL",
            )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    _record_execution(
                        connection,
                        old_loan_id=kind_old,
                        new_loan_id=kind_new,
                        disbursement_event_id=wrong_kind_release,
                        actor_id=actor_id,
                        business_date=renew_date,
                        settlement="0.00",
                    )

            # Deductions and 7x7 remain explicitly policy-blocked even when the
            # operational evidence linkage itself is authoritative.
            deduction_client = _create_client(connection, f"{suffix}d")
            deduction_type = _create_loan_type(connection, suffix=f"{suffix}d")
            deduction_old = _create_loan(
                connection,
                suffix=f"{suffix}do",
                actor_id=actor_id,
                client_id=deduction_client,
                loan_type_id=deduction_type,
                release_date=old_date,
            )
            deduction_new = _create_loan(
                connection,
                suffix=f"{suffix}dn",
                actor_id=actor_id,
                client_id=deduction_client,
                loan_type_id=deduction_type,
                release_date=renew_date,
            )
            deduction_release = _record_release(
                connection,
                new_loan_id=deduction_new,
                actor_id=actor_id,
                business_date=renew_date,
                cash="1900.00",
                settlement="3000.00",
                deduction="100.00",
                reference="RENEW-DEDUCTION",
            )
            _record_execution(
                connection,
                old_loan_id=deduction_old,
                new_loan_id=deduction_new,
                disbursement_event_id=deduction_release,
                actor_id=actor_id,
                business_date=renew_date,
                reference="RENEW-EXEC-DEDUCTION",
            )
            assert connection.execute(
                """
                select readiness_status, journal_lines_enabled
                from accounting.loan_renewal_execution_source_readiness
                where disbursement_event_id = %s
                """,
                (deduction_release,),
            ).fetchone() == ("deduction_policy_review", False)

            seven_client = _create_client(connection, f"{suffix}7")
            seven_type = _create_loan_type(
                connection,
                suffix=f"{suffix}7",
                calculation_mode="seven_by_seven",
            )
            seven_old = _create_loan(
                connection,
                suffix=f"{suffix}7o",
                actor_id=actor_id,
                client_id=seven_client,
                loan_type_id=seven_type,
                release_date=old_date,
            )
            seven_new = _create_loan(
                connection,
                suffix=f"{suffix}7n",
                actor_id=actor_id,
                client_id=seven_client,
                loan_type_id=seven_type,
                release_date=renew_date,
            )
            seven_release = _record_release(
                connection,
                new_loan_id=seven_new,
                actor_id=actor_id,
                business_date=renew_date,
                reference="RENEW-7X7",
            )
            _record_execution(
                connection,
                old_loan_id=seven_old,
                new_loan_id=seven_new,
                disbursement_event_id=seven_release,
                actor_id=actor_id,
                business_date=renew_date,
                reference="RENEW-EXEC-7X7",
            )
            assert connection.execute(
                """
                select readiness_status, automatic_source_posting
                from accounting.loan_renewal_execution_source_readiness
                where disbursement_event_id = %s
                """,
                (seven_release,),
            ).fetchone() == ("seven_by_seven_policy_review", False)

            # Unposted evidence can be voided, preserving the old row, then a
            # corrected bridge can be recorded. No financial history is deleted.
            connection.execute(
                "select accounting.void_loan_renewal_execution_evidence(%s, %s, %s)",
                (execution_id, actor_id, "Wrong execution reference"),
            )
            assert connection.execute(
                "select is_voided from lending.loan_renewal_execution_events where id = %s",
                (execution_id,),
            ).fetchone() == (True,)
            corrected_id = _record_execution(
                connection,
                old_loan_id=old_loan_id,
                new_loan_id=new_loan_id,
                disbursement_event_id=release_event_id,
                actor_id=actor_id,
                business_date=renew_date,
                reference="RENEW-EXEC-002",
                renewal_request_id=request_id,
            )
            assert corrected_id != execution_id

            # Once future journal history is linked to this execution source, the
            # evidence-only stage refuses to void it.
            period_id = connection.execute(
                """
                insert into accounting.fiscal_periods (
                    label, start_date, end_date, status
                ) values (%s, %s, %s, 'open')
                returning id
                """,
                (f"Renewal execution {suffix}", renew_date, renew_date),
            ).fetchone()[0]
            connection.execute(
                """
                insert into accounting.journal_entries (
                    fiscal_period_id, posting_date, description, status,
                    source_type, source_reference, source_event_key,
                    created_by_user_id, updated_at
                ) values (
                    %s, %s, 'Synthetic future renewal journal', 'draft',
                    'loan_renewal_execution', %s, %s, %s, now()
                )
                """,
                (
                    period_id,
                    renew_date,
                    str(corrected_id),
                    f"loan_renewal_execution:{corrected_id}",
                    actor_id,
                ),
            )
            with pytest.raises(psycopg.Error):
                with connection.transaction():
                    connection.execute(
                        "select accounting.void_loan_renewal_execution_evidence(%s, %s, %s)",
                        (corrected_id, actor_id, "Cannot bypass journal history"),
                    )
            assert connection.execute(
                "select is_voided from lending.loan_renewal_execution_events where id = %s",
                (corrected_id,),
            ).fetchone() == (False,)
        finally:
            connection.rollback()
