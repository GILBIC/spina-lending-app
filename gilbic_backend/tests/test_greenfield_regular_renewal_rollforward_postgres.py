from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from gilbic_backend.eir_cash_allocation import EirCashSourceEvent
from gilbic_backend.greenfield_regular_eir_rollforward import (
    build_greenfield_regular_renewal_rollforward,
)


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
SQL_0052 = (
    SQL_ROOT / "0052_add_greenfield_regular_renewal_rollforward_targets.sql"
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
        (f"d26-{suffix}", f"Stage 5D.26 {suffix}"),
    ).fetchone()[0]


def _client(connection, suffix: str):
    return connection.execute(
        """
        insert into lending.clients (client_code, full_name, status)
        values (%s, %s, 'active') returning id
        """,
        (f"D26-C-{suffix}", f"D26 Client {suffix}"),
    ).fetchone()[0]


def _loan_type(connection, suffix: str):
    return connection.execute(
        """
        insert into lending.loan_types (
            code, name, term_days, calculation_mode, daily_interest_per_1000
        ) values (%s, %s, 120, 'fixed_daily', 0) returning id
        """,
        (f"D26-T-{suffix}", f"D26 Regular {suffix}"),
    ).fetchone()[0]


def _loan(
    connection,
    *,
    suffix: str,
    actor_id,
    client_id,
    loan_type_id,
    release_date,
    principal: str = "5000.00",
):
    return connection.execute(
        """
        insert into lending.loans (
            loan_number, client_id, loan_type_id, principal, daily_amount,
            interest_rate, date_released, due_date, status, created_by_user_id
        ) values (%s, %s, %s, %s, 50.00, 20.0000, %s, %s, 'active', %s)
        returning id
        """,
        (
            f"D26-L-{suffix}",
            client_id,
            loan_type_id,
            principal,
            release_date,
            release_date + timedelta(days=120),
            actor_id,
        ),
    ).fetchone()[0]


def _record_disbursement(
    connection,
    *,
    loan_id,
    actor_id,
    event_kind: str,
    business_date,
    cash: str,
    settlement: str,
    reference: str,
):
    disbursed_at = datetime(
        business_date.year,
        business_date.month,
        business_date.day,
        10,
        0,
        tzinfo=MANILA,
    )
    event_id = connection.execute(
        """
        select accounting.record_loan_disbursement_evidence(
            %s, %s, %s, %s, %s, %s, %s, 0.00,
            'cash_office', %s, %s
        )
        """,
        (
            loan_id,
            actor_id,
            event_kind,
            business_date,
            disbursed_at,
            cash,
            settlement,
            reference,
            "Stage 5D.26 authoritative release evidence",
        ),
    ).fetchone()[0]
    return event_id, disbursed_at


def _post_pure_new_release(connection, *, event_id, actor_id, token: str):
    coordinate = connection.execute(
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
    assert coordinate is not None

    draft_token = token * 64
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
    assert status is not None and status[-1] is True

    posting_token = ("f" if token == "a" else "e") * 64
    return connection.execute(
        """
        select accounting.post_new_loan_disbursement_journal(
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            'new_loan_disbursement_journal_posting_v1'
        )
        """,
        (
            status[0],
            actor_id,
            posting_token,
            status[1],
            status[2],
            status[3],
            status[4],
            status[5],
            status[6],
            status[7],
            status[8],
            status[9],
            status[10],
        ),
    ).fetchone()[0]


def _register_original_contract(
    connection,
    *,
    loan_id,
    actor_id,
    release_date,
    suffix: str,
):
    schedule_id = connection.execute(
        """
        insert into lending.loan_contract_schedules (
            loan_id, schedule_version, status, payment_frequency,
            contract_reference, contract_signed_date, effective_from,
            grace_days, settings, created_by_user_id
        ) values (%s, 1, 'active', 'daily', %s, %s, %s, 0, '{}'::jsonb, %s)
        returning id
        """,
        (
            loan_id,
            f"D26-CONTRACT-{suffix}",
            release_date,
            release_date,
            actor_id,
        ),
    ).fetchone()[0]
    connection.execute(
        """
        insert into lending.loan_contract_installments (
            schedule_id, installment_number, due_date, contractual_amount
        )
        select %s, day_number, %s::date + day_number, 50.00
        from generate_series(1, 120) day_number
        """,
        (schedule_id, release_date),
    )
    connection.execute(
        """
        insert into lending.loan_contract_schedule_registrations (
            schedule_id, evidence_basis, evidence_reference,
            verification_note, verified_by_user_id
        ) values (%s, 'signed_contract', %s, %s, %s)
        """,
        (
            schedule_id,
            f"D26-SIGNED-{suffix}",
            "Verified original signed contract for Stage 5D.26",
            actor_id,
        ),
    )
    return schedule_id


def _collection(
    connection,
    *,
    suffix: str,
    loan_id,
    client_id,
    actor_id,
    collection_date,
    sequence: int,
    amount: str,
):
    device_id = connection.execute(
        """
        select id from core.devices
        where user_id = %s and status = 'active'
        order by created_at
        limit 1
        """,
        (actor_id,),
    ).fetchone()
    if device_id is None:
        device_id = connection.execute(
            """
            insert into core.devices (
                user_id, device_identifier_hash, platform, status
            ) values (%s, %s, 'desktop', 'active') returning id
            """,
            (actor_id, f"d26-device-{suffix}"),
        ).fetchone()
    device_id = device_id[0]
    return connection.execute(
        """
        insert into lending.collection_transactions (
            idempotency_key, loan_id, client_id, collector_user_id,
            registered_device_id, route_entry_id, collection_date,
            entry_type, amount, recorded_at, device_sequence, note,
            previous_balance, official_balance, pass_count_after,
            advance_until_after, receipt_number, details
        ) values (
            %s, %s, %s, %s, %s, %s, %s, 'payment', %s,
            now(), %s, '', 5000.00, 4900.00, 0, null, %s, '{}'::jsonb
        ) returning id
        """,
        (
            uuid4(),
            loan_id,
            client_id,
            actor_id,
            device_id,
            loan_id,
            collection_date,
            amount,
            sequence,
            f"D26-R-{suffix}-{sequence}",
        ),
    ).fetchone()[0]


def _renewal_execution(
    connection,
    *,
    old_loan_id,
    new_loan_id,
    renewal_release_event_id,
    actor_id,
    business_date,
    executed_at,
    settlement: str,
    reference: str,
):
    return connection.execute(
        """
        select accounting.record_loan_renewal_execution_evidence(
            %s, %s, %s, %s, %s, %s, %s, %s, %s, null
        )
        """,
        (
            old_loan_id,
            new_loan_id,
            renewal_release_event_id,
            actor_id,
            business_date,
            executed_at,
            settlement,
            reference,
            "Stage 5D.26 authoritative renewal execution",
        ),
    ).fetchone()[0]


def _source_events(connection, *, loan_id, anchor_date, target_date):
    rows = connection.execute(
        """
        select id, collection_date, accepted_at, entry_type, amount, is_voided
        from lending.collection_transactions
        where loan_id = %s
          and collection_date > %s
          and collection_date < %s
          and is_voided = false
          and entry_type in ('payment', 'advance')
          and amount > 0
        order by collection_date, accepted_at, id
        """,
        (loan_id, anchor_date, target_date),
    ).fetchall()
    return tuple(
        EirCashSourceEvent(
            transaction_id=row[0],
            collection_date=row[1],
            accepted_at=row[2],
            entry_type=row[3],
            amount=Decimal(row[4]),
            is_voided=bool(row[5]),
        )
        for row in rows
    )


def test_greenfield_regular_renewal_rollforward_is_read_only_and_fail_closed() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            assert connection.execute(
                "select to_regclass('accounting.greenfield_regular_eir_anchor_readiness')"
            ).fetchone()[0] is not None
            assert connection.execute(
                "select to_regclass('accounting.greenfield_regular_renewal_rollforward_targets')"
            ).fetchone()[0] is None

            before_install = (
                connection.execute("select count(*) from lending.loans").fetchone()[0],
                connection.execute("select count(*) from lending.collection_transactions").fetchone()[0],
                connection.execute("select count(*) from lending.loan_renewal_execution_events").fetchone()[0],
                connection.execute("select count(*) from accounting.journal_entries").fetchone()[0],
                connection.execute("select count(*) from accounting.journal_lines").fetchone()[0],
                connection.execute("select count(*) from accounting.opening_balance_workbooks").fetchone()[0],
            )
            connection.execute(_transaction_body(SQL_0052))
            after_install = (
                connection.execute("select count(*) from lending.loans").fetchone()[0],
                connection.execute("select count(*) from lending.collection_transactions").fetchone()[0],
                connection.execute("select count(*) from lending.loan_renewal_execution_events").fetchone()[0],
                connection.execute("select count(*) from accounting.journal_entries").fetchone()[0],
                connection.execute("select count(*) from accounting.journal_lines").fetchone()[0],
                connection.execute("select count(*) from accounting.opening_balance_workbooks").fetchone()[0],
            )
            assert after_install == before_install

            actor_id = _actor(connection, suffix)
            client_id = _client(connection, suffix)
            loan_type_id = _loan_type(connection, suffix)
            max_end = connection.execute(
                "select coalesce(max(end_date), date '2090-01-01') from accounting.fiscal_periods"
            ).fetchone()[0]
            release_date = max_end + timedelta(days=7)
            target_date = release_date + timedelta(days=30)
            connection.execute(
                """
                insert into accounting.fiscal_periods (
                    label, start_date, end_date, status
                ) values (%s, %s, %s, 'open')
                """,
                (
                    f"D26 {suffix}",
                    release_date,
                    release_date + timedelta(days=120),
                ),
            )

            old_loan_id = _loan(
                connection,
                suffix=f"{suffix}old",
                actor_id=actor_id,
                client_id=client_id,
                loan_type_id=loan_type_id,
                release_date=release_date,
            )
            old_release_event, _ = _record_disbursement(
                connection,
                loan_id=old_loan_id,
                actor_id=actor_id,
                event_kind="new_loan_release",
                business_date=release_date,
                cash="5000.00",
                settlement="0.00",
                reference="D26-OLD-RELEASE",
            )
            _post_pure_new_release(
                connection,
                event_id=old_release_event,
                actor_id=actor_id,
                token="a",
            )
            _register_original_contract(
                connection,
                loan_id=old_loan_id,
                actor_id=actor_id,
                release_date=release_date,
                suffix=suffix,
            )
            _collection(
                connection,
                suffix=suffix,
                loan_id=old_loan_id,
                client_id=client_id,
                actor_id=actor_id,
                collection_date=release_date + timedelta(days=10),
                sequence=1,
                amount="100.00",
            )
            _collection(
                connection,
                suffix=suffix,
                loan_id=old_loan_id,
                client_id=client_id,
                actor_id=actor_id,
                collection_date=release_date + timedelta(days=20),
                sequence=2,
                amount="100.00",
            )

            new_loan_id = _loan(
                connection,
                suffix=f"{suffix}new",
                actor_id=actor_id,
                client_id=client_id,
                loan_type_id=loan_type_id,
                release_date=target_date,
            )
            renewal_release_event, executed_at = _record_disbursement(
                connection,
                loan_id=new_loan_id,
                actor_id=actor_id,
                event_kind="renewal_release",
                business_date=target_date,
                cash="2000.00",
                settlement="3000.00",
                reference="D26-RENEWAL-RELEASE",
            )
            execution_id = _renewal_execution(
                connection,
                old_loan_id=old_loan_id,
                new_loan_id=new_loan_id,
                renewal_release_event_id=renewal_release_event,
                actor_id=actor_id,
                business_date=target_date,
                executed_at=executed_at,
                settlement="3000.00",
                reference="D26-EXECUTION",
            )

            target = connection.execute(
                """
                select
                    readiness_status, measurement_preview_enabled,
                    accounting_carrying_amount_ready, journal_lines_enabled,
                    automatic_source_posting, source_event_count_before_target,
                    same_day_target_collection_count, anchor_date,
                    contractual_due_date, daily_eir,
                    initial_gross_carrying_amount,
                    initial_accrued_interest_component,
                    initial_loan_component
                from accounting.greenfield_regular_renewal_rollforward_targets
                where renewal_execution_event_id = %s
                """,
                (execution_id,),
            ).fetchone()
            assert target is not None
            assert target[:7] == (
                "greenfield_regular_renewal_rollforward_target_ready",
                True,
                False,
                False,
                False,
                2,
                0,
            )

            events = _source_events(
                connection,
                loan_id=old_loan_id,
                anchor_date=target[7],
                target_date=target_date,
            )
            preview = build_greenfield_regular_renewal_rollforward(
                loan_id=old_loan_id,
                anchor_date=target[7],
                target_date=target_date,
                contractual_due_date=target[8],
                daily_eir=Decimal(target[9]),
                initial_gross_carrying_amount=Decimal(target[10]),
                initial_accrued_interest_component=Decimal(target[11]),
                initial_loan_component=Decimal(target[12]),
                source_events=events,
            )
            assert preview.disposition == "greenfield_regular_renewal_rollforward_preview_ready"
            assert preview.blocker_code is None
            assert preview.source_event_count == 2
            assert preview.allocation_count == 2
            assert preview.measurement_preview_ready is True
            assert preview.accounting_carrying_amount_ready is False
            assert preview.journal_lines_enabled is False
            assert preview.automatic_source_posting is False
            assert preview.gross_carrying_amount_at_target is not None
            assert preview.accrued_interest_component_at_target is not None
            assert preview.loan_component_at_target is not None
            assert (
                preview.accrued_interest_component_at_target
                + preview.loan_component_at_target
                == preview.gross_carrying_amount_at_target
            )
            assert preview.total_effective_interest_accrued > 0
            assert len(preview.tail_daily_accruals) == 10
            assert preview.allocations[0].collection_date == release_date + timedelta(days=10)
            assert preview.allocations[1].collection_date == release_date + timedelta(days=20)

            # Stage 5D.26 deliberately does not label the measurement preview as
            # authoritative accounting carrying amount or turn settlement into a
            # derecognition/modification result.
            assert connection.execute(
                """
                select old_loan_settlement_amount, accounting_carrying_amount_ready
                from accounting.greenfield_regular_renewal_rollforward_targets
                where renewal_execution_event_id = %s
                """,
                (execution_id,),
            ).fetchone() == (Decimal("3000.00"), False)

            # Any PAYMENT/ADV on the renewal business date blocks the target. The
            # stage refuses to guess whether it occurred before or after execution.
            _collection(
                connection,
                suffix=suffix,
                loan_id=old_loan_id,
                client_id=client_id,
                actor_id=actor_id,
                collection_date=target_date,
                sequence=3,
                amount="50.00",
            )
            assert connection.execute(
                """
                select readiness_status, measurement_preview_enabled,
                       same_day_target_collection_count,
                       accounting_carrying_amount_ready,
                       journal_lines_enabled, automatic_source_posting
                from accounting.greenfield_regular_renewal_rollforward_targets
                where renewal_execution_event_id = %s
                """,
                (execution_id,),
            ).fetchone() == (
                "same_day_renewal_collection_ordering_review",
                False,
                1,
                False,
                False,
                False,
            )

            blocked_preview = build_greenfield_regular_renewal_rollforward(
                loan_id=old_loan_id,
                anchor_date=target[7],
                target_date=target_date,
                contractual_due_date=target[8],
                daily_eir=Decimal(target[9]),
                initial_gross_carrying_amount=Decimal(target[10]),
                initial_accrued_interest_component=Decimal(target[11]),
                initial_loan_component=Decimal(target[12]),
                source_events=events + (
                    EirCashSourceEvent(
                        transaction_id=uuid4(),
                        collection_date=target_date,
                        accepted_at=executed_at,
                        entry_type="payment",
                        amount=Decimal("50.00"),
                        is_voided=False,
                    ),
                ),
            )
            assert blocked_preview.blocker_code == "same_day_renewal_collection_ordering_review"
            assert blocked_preview.measurement_preview_ready is False
            assert blocked_preview.accounting_carrying_amount_ready is False

            # Installation and previewing do not infer any opening-balance history.
            assert connection.execute(
                "select count(*) from accounting.opening_balance_workbooks"
            ).fetchone()[0] == 0
        finally:
            connection.rollback()
