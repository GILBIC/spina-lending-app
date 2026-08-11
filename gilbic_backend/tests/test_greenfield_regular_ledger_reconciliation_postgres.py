from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from gilbic_backend.config import get_settings
from gilbic_backend.eir_cash_allocation import EirCashSourceEvent
from gilbic_backend.greenfield_regular_eir_rollforward import (
    build_greenfield_regular_renewal_rollforward,
)
from gilbic_backend.greenfield_regular_ledger_reconciliation import (
    build_expected_greenfield_regular_journals,
)
from gilbic_backend.greenfield_regular_ledger_reconciliation_repository import (
    PostgresGreenfieldRegularLedgerReconciliationRepository,
)
from gilbic_backend.regular_eir_accrual_journal_preview import (
    AccountingFiscalPeriodReference,
)


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
SQL_0053 = (
    SQL_ROOT / "0053_add_greenfield_regular_ledger_reconciliation_targets.sql"
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
        (f"d27-{suffix}", f"Stage 5D.27 {suffix}"),
    ).fetchone()[0]


def _device(connection, *, actor_id, suffix: str):
    return connection.execute(
        """
        insert into core.devices (
            user_id, device_identifier_hash, platform, status
        ) values (%s, %s, 'desktop', 'active') returning id
        """,
        (actor_id, f"d27-device-{suffix}"),
    ).fetchone()[0]


def _client(connection, suffix: str):
    return connection.execute(
        """
        insert into lending.clients (client_code, full_name, status)
        values (%s, %s, 'active') returning id
        """,
        (f"D27-C-{suffix}", f"D27 Client {suffix}"),
    ).fetchone()[0]


def _loan_type(connection, suffix: str):
    return connection.execute(
        """
        insert into lending.loan_types (
            code, name, term_days, calculation_mode, daily_interest_per_1000
        ) values (%s, %s, 120, 'fixed_daily', 0) returning id
        """,
        (f"D27-T-{suffix}", f"D27 Regular {suffix}"),
    ).fetchone()[0]


def _loan(
    connection,
    *,
    suffix: str,
    actor_id,
    client_id,
    loan_type_id,
    release_date,
):
    return connection.execute(
        """
        insert into lending.loans (
            loan_number, client_id, loan_type_id, principal, daily_amount,
            interest_rate, date_released, due_date, status, created_by_user_id
        ) values (%s, %s, %s, 5000.00, 50.00, 20.0000, %s, %s, 'active', %s)
        returning id
        """,
        (
            f"D27-L-{suffix}", client_id, loan_type_id, release_date,
            release_date + timedelta(days=120), actor_id,
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
            loan_id, actor_id, event_kind, business_date, disbursed_at,
            cash, settlement, reference, "Stage 5D.27 authoritative release evidence",
        ),
    ).fetchone()[0]
    return event_id, disbursed_at


def _post_pure_new_release(connection, *, event_id, actor_id):
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

    preparation_id = connection.execute(
        """
        select accounting.create_new_loan_disbursement_journal_draft(
            %s, %s, %s, %s, %s, %s, %s, %s, %s,
            'new_loan_disbursement_coordinates_v1',
            'new_loan_disbursement_journal_draft_v1'
        )
        """,
        (
            event_id, actor_id, "a" * 64, coordinate[0], coordinate[1],
            coordinate[2], coordinate[3], coordinate[4], coordinate[5],
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
    return connection.execute(
        """
        select accounting.post_new_loan_disbursement_journal(
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            'new_loan_disbursement_journal_posting_v1'
        )
        """,
        (
            status[0], actor_id, "f" * 64, status[1], status[2], status[3],
            status[4], status[5], status[6], status[7], status[8], status[9], status[10],
        ),
    ).fetchone()[0]


def _register_contract(connection, *, loan_id, actor_id, release_date, suffix: str):
    schedule_id = connection.execute(
        """
        insert into lending.loan_contract_schedules (
            loan_id, schedule_version, status, payment_frequency,
            contract_reference, contract_signed_date, effective_from,
            grace_days, settings, created_by_user_id
        ) values (%s, 1, 'active', 'daily', %s, %s, %s, 0, '{}'::jsonb, %s)
        returning id
        """,
        (loan_id, f"D27-CONTRACT-{suffix}", release_date, release_date, actor_id),
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
            schedule_id, f"D27-SIGNED-{suffix}",
            "Verified original signed contract for Stage 5D.27", actor_id,
        ),
    )


def _collection(
    connection,
    *,
    suffix: str,
    loan_id,
    client_id,
    actor_id,
    device_id,
    collection_date,
):
    return connection.execute(
        """
        insert into lending.collection_transactions (
            idempotency_key, loan_id, client_id, collector_user_id,
            registered_device_id, route_entry_id, collection_date,
            entry_type, amount, recorded_at, device_sequence, note,
            previous_balance, official_balance, pass_count_after,
            advance_until_after, receipt_number, details
        ) values (
            %s, %s, %s, %s, %s, %s, %s, 'payment', 100.00,
            now(), 1, '', 5000.00, 4900.00, 0, null, %s, '{}'::jsonb
        ) returning id
        """,
        (
            uuid4(), loan_id, client_id, actor_id, device_id, loan_id,
            collection_date, f"D27-R-{suffix}",
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
):
    return connection.execute(
        """
        select accounting.record_loan_renewal_execution_evidence(
            %s, %s, %s, %s, %s, %s, 3000.00, %s, %s, null
        )
        """,
        (
            old_loan_id, new_loan_id, renewal_release_event_id, actor_id,
            business_date, executed_at, "D27-EXECUTION",
            "Stage 5D.27 authoritative renewal execution",
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
            transaction_id=row[0], collection_date=row[1], accepted_at=row[2],
            entry_type=row[3], amount=Decimal(row[4]), is_voided=bool(row[5]),
        )
        for row in rows
    )


def _periods(connection, *, anchor_date, target_date):
    rows = connection.execute(
        """
        select id, label, start_date, end_date, status
        from accounting.fiscal_periods
        where end_date > %s and start_date <= %s
        order by start_date, end_date, id
        """,
        (anchor_date, target_date),
    ).fetchall()
    return tuple(
        AccountingFiscalPeriodReference(
            period_id=row[0], label=row[1], start_date=row[2],
            end_date=row[3], status=row[4],
        )
        for row in rows
    )


def _account_ids(connection):
    keys = (
        "accrued_interest_receivable",
        "interest_income_regular",
        "cash_collector_custody",
        "loans_receivable_regular",
    )
    rows = connection.execute(
        "select system_key, id from accounting.accounts where system_key = any(%s)",
        (list(keys),),
    ).fetchall()
    result = {row[0]: row[1] for row in rows}
    assert set(result) == set(keys)
    return result


def _prepare_and_post_expected_regular_journals(
    connection,
    *,
    loan_id,
    client_id,
    actor_id,
    transaction_id,
    expected,
):
    accounts = _account_ids(connection)
    created: list[tuple[object, object]] = []
    for journal in expected:
        journal_id = connection.execute(
            """
            insert into accounting.journal_entries (
                fiscal_period_id, posting_date, description, status,
                source_type, source_reference, source_event_key,
                created_by_user_id, updated_at
            ) values (%s, %s, %s, 'draft', %s, %s, %s, %s, now())
            returning id
            """,
            (
                journal.fiscal_period_id, journal.posting_date,
                "Stage 5D.27 exact protected Regular draft", journal.source_type,
                journal.source_reference, journal.source_event_key, actor_id,
            ),
        ).fetchone()[0]
        for line in journal.lines:
            connection.execute(
                """
                insert into accounting.journal_lines (
                    journal_entry_id, line_number, account_id, description,
                    debit, credit, client_id, loan_id
                ) values (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    journal_id, line.line_number, accounts[line.account_system_key],
                    "Stage 5D.27 exact protected line", line.debit, line.credit,
                    client_id, loan_id,
                ),
            )
        created.append((journal, journal_id))

    review_token = "7" * 64
    connection.execute(
        "select set_config('accounting.regular_journal_prepare_allowed', 'on', true)"
    )
    preparation_id = connection.execute(
        """
        insert into accounting.regular_journal_draft_preparations (
            loan_id, transaction_id, review_set_fingerprint,
            bundle_fingerprint, evidence_policy_version, draft_policy_version,
            expected_set_transaction_count, expected_entry_count,
            prepared_by_user_id
        ) values (
            %s, %s, %s, %s,
            'regular_cross_period_posting_ready_evidence_v1',
            'regular_journal_draft_v1', 1, %s, %s
        ) returning id
        """,
        (loan_id, transaction_id, review_token, "8" * 64, len(created), actor_id),
    ).fetchone()[0]
    for journal, journal_id in created:
        connection.execute(
            """
            insert into accounting.regular_journal_draft_preparation_entries (
                preparation_id, sequence_order, entry_type, journal_entry_id,
                bundle_entry_key, source_event_key
            ) values (%s, %s, %s, %s, %s, %s)
            """,
            (
                preparation_id, journal.sequence_order, journal.entry_type,
                journal_id, f"stage5d27:{journal.source_event_key}",
                journal.source_event_key,
            ),
        )
    posting_set_id = connection.execute(
        "select accounting.post_regular_journal_review_set(%s, %s, %s)",
        (loan_id, review_token, actor_id),
    ).fetchone()[0]
    assert posting_set_id is not None


def test_greenfield_regular_ledger_reconciliation_proves_source_journals_then_blocks_unposted_tail() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        assert connection.execute(
            "select to_regclass('accounting.greenfield_regular_renewal_rollforward_targets')"
        ).fetchone()[0] is not None
        assert connection.execute(
            "select to_regclass('accounting.greenfield_regular_renewal_ledger_reconciliation_targets')"
        ).fetchone()[0] is None

        before_install = (
            connection.execute("select count(*) from lending.loans").fetchone()[0],
            connection.execute("select count(*) from lending.collection_transactions").fetchone()[0],
            connection.execute("select count(*) from accounting.journal_entries").fetchone()[0],
            connection.execute("select count(*) from accounting.journal_lines").fetchone()[0],
        )
        connection.execute(_transaction_body(SQL_0053))
        after_install = (
            connection.execute("select count(*) from lending.loans").fetchone()[0],
            connection.execute("select count(*) from lending.collection_transactions").fetchone()[0],
            connection.execute("select count(*) from accounting.journal_entries").fetchone()[0],
            connection.execute("select count(*) from accounting.journal_lines").fetchone()[0],
        )
        assert after_install == before_install

        actor_id = _actor(connection, suffix)
        device_id = _device(connection, actor_id=actor_id, suffix=suffix)
        client_id = _client(connection, suffix)
        loan_type_id = _loan_type(connection, suffix)
        max_end = connection.execute(
            "select coalesce(max(end_date), date '2090-01-01') from accounting.fiscal_periods"
        ).fetchone()[0]
        release_date = max_end + timedelta(days=7)
        target_date = release_date + timedelta(days=30)
        connection.execute(
            """
            insert into accounting.fiscal_periods (label, start_date, end_date, status)
            values (%s, %s, %s, 'open')
            """,
            (f"D27 {suffix}", release_date, release_date + timedelta(days=120)),
        )

        old_loan_id = _loan(
            connection, suffix=f"{suffix}old", actor_id=actor_id,
            client_id=client_id, loan_type_id=loan_type_id, release_date=release_date,
        )
        old_release_event, _ = _record_disbursement(
            connection, loan_id=old_loan_id, actor_id=actor_id,
            event_kind="new_loan_release", business_date=release_date,
            cash="5000.00", settlement="0.00", reference="D27-OLD-RELEASE",
        )
        _post_pure_new_release(connection, event_id=old_release_event, actor_id=actor_id)
        _register_contract(
            connection, loan_id=old_loan_id, actor_id=actor_id,
            release_date=release_date, suffix=suffix,
        )
        transaction_id = _collection(
            connection, suffix=suffix, loan_id=old_loan_id, client_id=client_id,
            actor_id=actor_id, device_id=device_id,
            collection_date=release_date + timedelta(days=10),
        )

        new_loan_id = _loan(
            connection, suffix=f"{suffix}new", actor_id=actor_id,
            client_id=client_id, loan_type_id=loan_type_id, release_date=target_date,
        )
        renewal_release_event, executed_at = _record_disbursement(
            connection, loan_id=new_loan_id, actor_id=actor_id,
            event_kind="renewal_release", business_date=target_date,
            cash="2000.00", settlement="3000.00", reference="D27-RENEWAL-RELEASE",
        )
        execution_id = _renewal_execution(
            connection, old_loan_id=old_loan_id, new_loan_id=new_loan_id,
            renewal_release_event_id=renewal_release_event, actor_id=actor_id,
            business_date=target_date, executed_at=executed_at,
        )

        coarse_before = connection.execute(
            """
            select reconciliation_readiness_status, active_source_count,
                   protected_complete_active_source_count,
                   accounting_carrying_amount_ready, journal_lines_enabled,
                   automatic_source_posting
            from accounting.greenfield_regular_renewal_ledger_reconciliation_targets
            where renewal_execution_event_id = %s
            """,
            (execution_id,),
        ).fetchone()
        assert coarse_before is not None
        assert coarse_before[0] == "protected_regular_source_posting_gap"
        assert coarse_before[1:3] == (1, 0)
        assert coarse_before[3:] == (False, False, False)

        target = connection.execute(
            """
            select anchor_date, target_date, contractual_due_date, daily_eir,
                   initial_gross_carrying_amount,
                   initial_accrued_interest_component, initial_loan_component
            from accounting.greenfield_regular_renewal_rollforward_targets
            where renewal_execution_event_id = %s
            """,
            (execution_id,),
        ).fetchone()
        assert target is not None
        source_events = _source_events(
            connection, loan_id=old_loan_id, anchor_date=target[0], target_date=target[1]
        )
        rollforward = build_greenfield_regular_renewal_rollforward(
            loan_id=old_loan_id, anchor_date=target[0], target_date=target[1],
            contractual_due_date=target[2], daily_eir=Decimal(target[3]),
            initial_gross_carrying_amount=Decimal(target[4]),
            initial_accrued_interest_component=Decimal(target[5]),
            initial_loan_component=Decimal(target[6]), source_events=source_events,
        )
        assert rollforward.measurement_preview_ready is True
        assert rollforward.tail_effective_interest_accrued > Decimal("0.00")
        expected = build_expected_greenfield_regular_journals(
            rollforward,
            fiscal_periods=_periods(
                connection, anchor_date=target[0], target_date=target[1]
            ),
        )
        assert expected is not None
        assert expected[-1].entry_type == "collection"
        assert expected[-1].transaction_id == transaction_id

        _prepare_and_post_expected_regular_journals(
            connection, loan_id=old_loan_id, client_id=client_id,
            actor_id=actor_id, transaction_id=transaction_id, expected=expected,
        )

        coarse_after = connection.execute(
            """
            select reconciliation_readiness_status, active_source_count,
                   protected_complete_active_source_count,
                   exact_reconciliation_preview_enabled,
                   accounting_carrying_amount_ready, journal_lines_enabled,
                   automatic_source_posting
            from accounting.greenfield_regular_renewal_ledger_reconciliation_targets
            where renewal_execution_event_id = %s
            """,
            (execution_id,),
        ).fetchone()
        assert coarse_after is not None
        assert coarse_after[0] == "greenfield_regular_ledger_reconciliation_candidate"
        assert coarse_after[1:4] == (1, 1, True)
        assert coarse_after[4:] == (False, False, False)

        connection.commit()

    os.environ["GILBIC_DATABASE_URL"] = DATABASE_URL
    get_settings.cache_clear()
    repository = PostgresGreenfieldRegularLedgerReconciliationRepository()
    records = repository.list_previews(renewal_execution_event_id=execution_id)
    assert len(records) == 1
    record = records[0]
    assert record.exact_reconciliation_preview_enabled is True
    assert record.reconciliation is not None
    result = record.reconciliation
    assert result.protected_regular_journals_reconciled is True
    assert result.expected_journal_count == len(expected)
    assert result.exact_posted_journal_count == len(expected)
    assert result.blocker_code == "renewal_boundary_eir_accrual_not_posted"
    assert result.tail_effective_interest_accrued > Decimal("0.00")
    assert result.accounting_carrying_amount_ready is False
    assert result.journal_lines_enabled is False
    assert result.automatic_source_posting is False
