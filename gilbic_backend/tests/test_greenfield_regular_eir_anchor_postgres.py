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
SQL_0051 = (
    SQL_ROOT / "0051_add_greenfield_regular_eir_anchor_readiness.sql"
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
        (f"d25-{suffix}", f"Stage 5D.25 {suffix}"),
    ).fetchone()[0]


def _loan(
    connection,
    *,
    suffix: str,
    actor_id,
    release_date,
    principal: str = "5000.00",
    daily_amount: str = "50.00",
):
    client_id = connection.execute(
        """
        insert into lending.clients (client_code, full_name, status)
        values (%s, %s, 'active') returning id
        """,
        (f"D25-C-{suffix}", f"D25 Client {suffix}"),
    ).fetchone()[0]
    loan_type_id = connection.execute(
        """
        insert into lending.loan_types (
            code, name, term_days, calculation_mode, daily_interest_per_1000
        ) values (%s, %s, 120, 'fixed_daily', 0) returning id
        """,
        (f"D25-T-{suffix}", f"D25 Regular {suffix}"),
    ).fetchone()[0]
    loan_id = connection.execute(
        """
        insert into lending.loans (
            loan_number, client_id, loan_type_id, principal, daily_amount,
            interest_rate, date_released, due_date, status, created_by_user_id
        ) values (%s, %s, %s, %s, %s, 20.0000, %s, %s, 'active', %s)
        returning id
        """,
        (
            f"D25-L-{suffix}",
            client_id,
            loan_type_id,
            principal,
            daily_amount,
            release_date,
            release_date + timedelta(days=120),
            actor_id,
        ),
    ).fetchone()[0]
    return client_id, loan_id


def _record_release(connection, *, loan_id, actor_id, business_date, reference):
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
            "Stage 5D.25 protected greenfield release evidence",
        ),
    ).fetchone()[0]


def _coordinate(connection, event_id):
    row = connection.execute(
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
    assert row is not None
    return row


def _prepare_and_post(connection, *, event_id, actor_id, token_char: str):
    coordinate = _coordinate(connection, event_id)
    draft_token = token_char * 64
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
    posting_id = connection.execute(
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
            (token_char.upper() if token_char.isalpha() else token_char) * 64,
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
    return posting_id


def _register_schedule(
    connection,
    *,
    loan_id,
    actor_id,
    release_date,
    suffix: str,
    evidence_basis: str = "signed_contract",
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
            f"D25-CONTRACT-{suffix}",
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
        ) values (%s, %s, %s, %s, %s)
        """,
        (
            schedule_id,
            evidence_basis,
            f"D25-EVIDENCE-{suffix}",
            "Verified exact signed contractual cash-flow schedule for Stage 5D.25",
            actor_id,
        ),
    )
    return schedule_id


def _same_day_collection(
    connection,
    *,
    loan_id,
    client_id,
    actor_id,
    collection_date,
    suffix: str,
):
    device_id = connection.execute(
        """
        insert into core.devices (
            user_id, device_identifier_hash, platform, status
        ) values (%s, %s, 'desktop', 'active') returning id
        """,
        (actor_id, f"d25-device-{suffix}"),
    ).fetchone()[0]
    connection.execute(
        """
        insert into lending.collection_transactions (
            idempotency_key, loan_id, client_id, collector_user_id,
            registered_device_id, route_entry_id, collection_date,
            entry_type, amount, recorded_at, device_sequence, note,
            previous_balance, official_balance, pass_count_after,
            advance_until_after, receipt_number, details
        ) values (
            %s, %s, %s, %s, %s, %s, %s, 'payment', 50.00,
            now(), 1, '', 5000.00, 4950.00, 0, null, %s, '{}'::jsonb
        )
        """,
        (
            uuid4(),
            loan_id,
            client_id,
            actor_id,
            device_id,
            loan_id,
            collection_date,
            f"D25-R-{suffix}",
        ),
    )


def test_greenfield_regular_eir_anchor_uses_protected_release_and_verified_contract() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            assert connection.execute(
                "select to_regclass('accounting.loan_disbursement_journal_postings')"
            ).fetchone()[0] is not None
            assert connection.execute(
                "select to_regclass('lending.loan_contract_schedule_registrations')"
            ).fetchone()[0] is not None
            assert connection.execute(
                "select to_regclass('accounting.greenfield_regular_eir_anchor_readiness')"
            ).fetchone()[0] is None

            before = (
                connection.execute("select count(*) from lending.loans").fetchone()[0],
                connection.execute("select count(*) from lending.collection_transactions").fetchone()[0],
                connection.execute("select count(*) from lending.loan_disbursement_events").fetchone()[0],
                connection.execute("select count(*) from lending.loan_contract_schedules").fetchone()[0],
                connection.execute("select count(*) from lending.loan_contract_installments").fetchone()[0],
                connection.execute("select count(*) from lending.loan_contract_schedule_registrations").fetchone()[0],
                connection.execute("select count(*) from accounting.journal_entries").fetchone()[0],
                connection.execute("select count(*) from accounting.journal_lines").fetchone()[0],
            )
            connection.execute(_transaction_body(SQL_0051))
            after_install = (
                connection.execute("select count(*) from lending.loans").fetchone()[0],
                connection.execute("select count(*) from lending.collection_transactions").fetchone()[0],
                connection.execute("select count(*) from lending.loan_disbursement_events").fetchone()[0],
                connection.execute("select count(*) from lending.loan_contract_schedules").fetchone()[0],
                connection.execute("select count(*) from lending.loan_contract_installments").fetchone()[0],
                connection.execute("select count(*) from lending.loan_contract_schedule_registrations").fetchone()[0],
                connection.execute("select count(*) from accounting.journal_entries").fetchone()[0],
                connection.execute("select count(*) from accounting.journal_lines").fetchone()[0],
            )
            assert after_install == before

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
                (
                    f"D25 {suffix}",
                    release_date,
                    release_date + timedelta(days=120),
                ),
            )

            client_id, loan_id = _loan(
                connection,
                suffix=f"{suffix}a",
                actor_id=actor_id,
                release_date=release_date,
            )
            event_id = _record_release(
                connection,
                loan_id=loan_id,
                actor_id=actor_id,
                business_date=release_date,
                reference="D25-REL-READY",
            )
            posting_id = _prepare_and_post(
                connection,
                event_id=event_id,
                actor_id=actor_id,
                token_char="a",
            )
            schedule_id = _register_schedule(
                connection,
                loan_id=loan_id,
                actor_id=actor_id,
                release_date=release_date,
                suffix=f"{suffix}a",
            )

            ready = connection.execute(
                """
                select
                    posting_id, schedule_id, initial_gross_carrying_amount,
                    initial_loan_component, initial_accrued_interest_component,
                    installment_count, contractual_cash_total, daily_eir,
                    readiness_status, anchor_policy_version,
                    collection_journal_integration_enabled,
                    journal_lines_enabled, automatic_source_posting
                from accounting.greenfield_regular_eir_anchor_readiness
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert ready is not None
            assert ready[0] == posting_id
            assert ready[1] == schedule_id
            assert ready[2:5] == (
                Decimal("5000.00"),
                Decimal("5000.00"),
                Decimal("0.00"),
            )
            assert ready[5] == 120
            assert ready[6] == Decimal("6000.00")
            assert ready[7] is not None and ready[7] > 0
            assert ready[8] == "greenfield_regular_eir_anchor_ready"
            assert ready[9] == "greenfield_regular_eir_anchor_v1"
            assert ready[10:] == (False, False, False)

            legacy_formula_eir = connection.execute(
                "select accounting.solve_level_payment_daily_eir(5000.00, 50.00, 120)"
            ).fetchone()[0]
            assert ready[7] == legacy_formula_eir

            # A protected release without an immutable verified signed schedule
            # does not receive an EIR anchor.
            _, no_schedule_loan_id = _loan(
                connection,
                suffix=f"{suffix}b",
                actor_id=actor_id,
                release_date=release_date,
            )
            no_schedule_event = _record_release(
                connection,
                loan_id=no_schedule_loan_id,
                actor_id=actor_id,
                business_date=release_date,
                reference="D25-REL-NO-SCHEDULE",
            )
            _prepare_and_post(
                connection,
                event_id=no_schedule_event,
                actor_id=actor_id,
                token_char="b",
            )
            assert connection.execute(
                """
                select readiness_status
                from accounting.greenfield_regular_eir_anchor_readiness
                where loan_id = %s
                """,
                (no_schedule_loan_id,),
            ).fetchone() == ("verified_signed_contract_schedule_required",)

            # A renewal-contract registration cannot be reused as the original
            # new-loan signed-contract evidence for this pure new-loan anchor.
            _, wrong_basis_loan_id = _loan(
                connection,
                suffix=f"{suffix}c",
                actor_id=actor_id,
                release_date=release_date,
            )
            wrong_basis_event = _record_release(
                connection,
                loan_id=wrong_basis_loan_id,
                actor_id=actor_id,
                business_date=release_date,
                reference="D25-REL-WRONG-BASIS",
            )
            _prepare_and_post(
                connection,
                event_id=wrong_basis_event,
                actor_id=actor_id,
                token_char="c",
            )
            _register_schedule(
                connection,
                loan_id=wrong_basis_loan_id,
                actor_id=actor_id,
                release_date=release_date,
                suffix=f"{suffix}c",
                evidence_basis="signed_renewal_contract",
            )
            assert connection.execute(
                """
                select readiness_status
                from accounting.greenfield_regular_eir_anchor_readiness
                where loan_id = %s
                """,
                (wrong_basis_loan_id,),
            ).fetchone() == ("original_signed_contract_evidence_required",)

            # Same-day collection timing is deliberately fail-closed. Stage 5D.25
            # does not guess whether cash happened before or after release.
            _same_day_collection(
                connection,
                loan_id=loan_id,
                client_id=client_id,
                actor_id=actor_id,
                collection_date=release_date,
                suffix=suffix,
            )
            assert connection.execute(
                """
                select readiness_status, same_day_collection_count,
                       collection_journal_integration_enabled,
                       journal_lines_enabled, automatic_source_posting
                from accounting.greenfield_regular_eir_anchor_readiness
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone() == (
                "same_day_collection_ordering_review",
                1,
                False,
                False,
                False,
            )

            # The readiness layer itself never creates opening-balance state or
            # new accounting history.
            assert connection.execute(
                "select count(*) from accounting.opening_balance_workbooks"
            ).fetchone()[0] == 0
        finally:
            connection.rollback()
