from __future__ import annotations

import importlib.util
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

TEST_DIR = Path(__file__).resolve().parent
ANCHOR_HELPER_PATH = TEST_DIR / "test_7x7_eir_initial_carrying_anchor_postgres.py"
_spec = importlib.util.spec_from_file_location("x7_anchor_helpers", ANCHOR_HELPER_PATH)
assert _spec is not None and _spec.loader is not None
anchor_helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(anchor_helpers)

SQL_0064 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0064_add_7x7_source_event_accounting_preview.sql"
).read_text(encoding="utf-8")


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def _device(connection, actor_id, suffix: str):
    return connection.execute(
        """
        insert into core.devices (
            user_id, device_identifier_hash, platform, app_version, status
        ) values (%s, %s, 'android', 'x7-preview-test', 'active')
        returning id
        """,
        (actor_id, f"x7-preview-device-{suffix}"),
    ).fetchone()[0]


def _client_id(connection, loan_id):
    return connection.execute(
        "select client_id from lending.loans where id = %s",
        (loan_id,),
    ).fetchone()[0]


def _collection(
    connection,
    *,
    actor_id,
    device_id,
    loan_id,
    suffix: str,
    collection_date: date,
    amount: str,
    entry_type: str = "payment",
    device_sequence: int,
    is_voided: bool = False,
):
    transaction_id = uuid4()
    recorded = datetime.combine(collection_date, time(12, 0), tzinfo=timezone.utc)
    client_id = _client_id(connection, loan_id)
    advance_from = collection_date if entry_type == "advance" else None
    advance_until = collection_date + timedelta(days=1) if entry_type == "advance" else None
    connection.execute(
        """
        insert into lending.collection_transactions (
            id, idempotency_key, loan_id, client_id, collector_user_id,
            registered_device_id, route_entry_id, collection_date, entry_type,
            amount, advance_from, advance_until, recorded_at, accepted_at,
            device_sequence, note, previous_balance, official_balance,
            pass_count_after, receipt_number, is_voided, voided_at,
            voided_by_user_id, void_reason
        ) values (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, 3000.00, 3000.00,
            0, %s, %s, %s,
            %s, %s
        )
        """,
        (
            transaction_id,
            uuid4(),
            loan_id,
            client_id,
            actor_id,
            device_id,
            loan_id,
            collection_date,
            entry_type,
            amount,
            advance_from,
            advance_until,
            recorded,
            recorded + timedelta(seconds=1),
            device_sequence,
            f"7x7 preview fixture {suffix}",
            f"X7PREVIEW-{suffix}-{device_sequence}",
            is_voided,
            recorded + timedelta(minutes=1) if is_voided else None,
            actor_id if is_voided else None,
            "fixture voided before accounting preview" if is_voided else None,
        ),
    )
    return transaction_id


def _pass(
    connection,
    *,
    actor_id,
    device_id,
    loan_id,
    suffix: str,
    collection_date: date,
    device_sequence: int,
):
    return _collection(
        connection,
        actor_id=actor_id,
        device_id=device_id,
        loan_id=loan_id,
        suffix=suffix,
        collection_date=collection_date,
        amount="0.00",
        entry_type="pass",
        device_sequence=device_sequence,
    )


def _open_period(connection, suffix: str, start_date: date, end_date: date):
    return connection.execute(
        """
        insert into accounting.fiscal_periods (label, start_date, end_date, status)
        values (%s, %s, %s, 'open') returning id
        """,
        (f"7x7 source preview {suffix}", start_date, end_date),
    ).fetchone()[0]


def _anchored_case(connection, suffix: str, release_date: date):
    management_actor, _, loan_id, _, anchor_token = anchor_helpers._setup_case(
        connection,
        suffix,
        release_date,
    )
    anchor_id = anchor_helpers._record_anchor(
        connection,
        loan_id=loan_id,
        token=anchor_token,
        actor_id=management_actor,
    )
    device_id = _device(connection, management_actor, suffix)
    return management_actor, loan_id, anchor_id, device_id


def test_source_identity_eir_preview_desktop_parity_and_coordinates_are_read_only() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    release_date = date(2096, 1, 1)

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0064))
            management_actor, loan_id, anchor_id, device_id = _anchored_case(
                connection,
                suffix,
                release_date,
            )
            period_id = _open_period(
                connection,
                suffix,
                release_date,
                release_date + timedelta(days=120),
            )

            first_id = _collection(
                connection,
                actor_id=management_actor,
                device_id=device_id,
                loan_id=loan_id,
                suffix=suffix,
                collection_date=release_date + timedelta(days=1),
                amount="50.00",
                device_sequence=1,
            )
            _pass(
                connection,
                actor_id=management_actor,
                device_id=device_id,
                loan_id=loan_id,
                suffix=suffix,
                collection_date=release_date + timedelta(days=2),
                device_sequence=2,
            )
            second_id = _collection(
                connection,
                actor_id=management_actor,
                device_id=device_id,
                loan_id=loan_id,
                suffix=suffix,
                collection_date=release_date + timedelta(days=3),
                amount="30.00",
                entry_type="advance",
                device_sequence=3,
            )
            voided_id = _collection(
                connection,
                actor_id=management_actor,
                device_id=device_id,
                loan_id=loan_id,
                suffix=suffix,
                collection_date=release_date + timedelta(days=4),
                amount="25.00",
                device_sequence=4,
                is_voided=True,
            )

            readiness = connection.execute(
                """
                select source_event_structure_ready,
                       source_event_readiness_status,
                       active_positive_cash_event_count,
                       duplicate_active_cash_date_count,
                       voided_original_cash_event_count,
                       authoritative_current_carrying_amount_ready,
                       journal_draft_enabled,
                       journal_lines_enabled,
                       automatic_source_posting
                from accounting.seven_by_seven_source_event_accounting_readiness
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert readiness == (
                True,
                "source_event_structure_ready_for_eir_preview",
                2,
                0,
                1,
                False,
                False,
                False,
                False,
            )

            preview_rows = connection.execute(
                """
                select transaction_id, source_event_key, source_event_sequence,
                       source_cash_amount, days_since_previous_event,
                       eir_interest_accrual, accounting_eir_interest_received,
                       accounting_7x7_principal_received,
                       closing_accrued_eir_interest,
                       closing_7x7_loan_component,
                       closing_gross_carrying_amount,
                       accounting_measurement_preview_ready,
                       journal_coordinate_preview_ready,
                       open_fiscal_period_id,
                       source_event_review_token,
                       operational_allocation_substituted_for_accounting,
                       authoritative_current_carrying_amount_ready,
                       journal_draft_enabled, journal_lines_enabled,
                       automatic_source_posting
                from accounting.seven_by_seven_source_event_accounting_preview
                where loan_id = %s
                order by source_event_sequence
                """,
                (loan_id,),
            ).fetchall()
            assert len(preview_rows) == 2
            first = preview_rows[0]
            assert first[0] == first_id
            assert first[1] == f"collection:{first_id}"
            assert first[2:5] == (1, 50, 1)
            assert first[5] > 0
            assert first[6] > 0
            assert first[6] < 50
            assert first[7] == 50 - first[6]
            assert first[8] >= 0
            assert first[10] == first[8] + first[9]
            assert first[11:14] == (True, True, period_id)
            assert first[14] is not None and len(first[14]) == 64
            assert first[15:] == (False, False, False, False, False)

            second = preview_rows[1]
            assert second[0] == second_id
            assert second[2] == 2
            assert second[4] == 2
            assert second[10] == second[8] + second[9]
            assert second[11:14] == (True, True, period_id)

            preview_ids = {row[0] for row in preview_rows}
            assert voided_id not in preview_ids

            parity = connection.execute(
                """
                select transaction_id,
                       fixed_operational_daily_interest,
                       operational_gap_days,
                       operational_interest_due,
                       operational_interest_paid,
                       operational_principal_paid,
                       accounting_eir_interest_received,
                       accounting_7x7_principal_received,
                       operational_allocation_matches_accounting_eir,
                       operational_allocation_substituted_for_accounting,
                       journal_lines_enabled,
                       automatic_source_posting
                from accounting.seven_by_seven_operational_allocation_parity_preview
                where loan_id = %s
                order by source_event_sequence
                """,
                (loan_id,),
            ).fetchall()
            assert len(parity) == 2
            assert parity[0][0] == first_id
            assert parity[0][1:6] == (21, 2, 42, 42, 8)
            assert parity[0][6] != parity[0][4]
            assert parity[0][7] != parity[0][5]
            assert parity[0][8:] == (False, False, False, False)

            coordinate_rows = connection.execute(
                """
                select transaction_id, account_code, account_system_key,
                       debit, credit, coordinate_preview_ready,
                       journal_lines_enabled, automatic_source_posting
                from accounting.seven_by_seven_source_event_journal_coordinate_preview
                where transaction_id = %s
                order by line_number
                """,
                (first_id,),
            ).fetchall()
            assert {row[1] for row in coordinate_rows} == {"1020", "1110", "1120", "4010"}
            assert all(row[5:] == (True, False, False) for row in coordinate_rows)
            assert sum(row[3] for row in coordinate_rows) == sum(row[4] for row in coordinate_rows)

            summary = connection.execute(
                """
                select preview_event_count,
                       measurement_ready_event_count,
                       coordinate_ready_event_count,
                       operational_accounting_allocation_difference_event_count,
                       blocked_preview_event_count,
                       preview_current_gross_carrying_amount,
                       authoritative_current_gross_carrying_amount,
                       authoritative_current_carrying_amount_ready,
                       journal_draft_enabled,
                       journal_lines_enabled,
                       automatic_source_posting,
                       accounting_preview_summary_status
                from accounting.seven_by_seven_source_event_accounting_summary
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert summary is not None
            assert summary[:5] == (2, 2, 2, 2, 0)
            assert summary[5] is not None and summary[5] > 0
            assert summary[6:11] == (None, False, False, False, False)
            assert summary[11] == "source_event_eir_preview_ready_for_protected_draft_design"

            assert connection.execute(
                "select count(*) from accounting.journal_entries where source_event_key like 'collection:%'"
            ).fetchone()[0] == 0
            assert connection.execute(
                "select count(*) from accounting.journal_lines where loan_id = %s",
                (loan_id,),
            ).fetchone()[0] == 0
            assert connection.execute(
                "select id from accounting.seven_by_seven_eir_initial_carrying_anchors where id = %s",
                (anchor_id,),
            ).fetchone()[0] == anchor_id
        finally:
            connection.rollback()


def test_same_day_duplicates_and_release_day_cash_fail_closed_without_invented_ordering() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0064))

            release_date = date(2097, 1, 1)
            actor_id, loan_id, _, device_id = _anchored_case(
                connection,
                suffix + "-dup",
                release_date,
            )
            _collection(
                connection,
                actor_id=actor_id,
                device_id=device_id,
                loan_id=loan_id,
                suffix=suffix + "-dup-a",
                collection_date=release_date + timedelta(days=1),
                amount="40.00",
                device_sequence=1,
            )
            _collection(
                connection,
                actor_id=actor_id,
                device_id=device_id,
                loan_id=loan_id,
                suffix=suffix + "-dup-b",
                collection_date=release_date + timedelta(days=1),
                amount="35.00",
                device_sequence=2,
            )

            duplicate_status = connection.execute(
                """
                select source_event_structure_ready,
                       duplicate_active_cash_date_count,
                       source_event_readiness_status
                from accounting.seven_by_seven_source_event_accounting_readiness
                where loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert duplicate_status == (
                False,
                1,
                "same_day_multiple_financial_source_events",
            )
            assert connection.execute(
                "select count(*) from accounting.seven_by_seven_source_event_accounting_preview where loan_id = %s",
                (loan_id,),
            ).fetchone()[0] == 0

            release2 = date(2098, 1, 1)
            actor2, loan2, _, device2 = _anchored_case(
                connection,
                suffix + "-release",
                release2,
            )
            _collection(
                connection,
                actor_id=actor2,
                device_id=device2,
                loan_id=loan2,
                suffix=suffix + "-release",
                collection_date=release2,
                amount="20.00",
                device_sequence=1,
            )
            release_status = connection.execute(
                """
                select source_event_structure_ready,
                       same_day_or_pre_anchor_cash_event_count,
                       source_event_readiness_status
                from accounting.seven_by_seven_source_event_accounting_readiness
                where loan_id = %s
                """,
                (loan2,),
            ).fetchone()
            assert release_status == (
                False,
                1,
                "same_day_or_pre_anchor_cash_ordering_review",
            )
            assert connection.execute(
                "select count(*) from accounting.seven_by_seven_source_event_accounting_preview where loan_id = %s",
                (loan2,),
            ).fetchone()[0] == 0
        finally:
            connection.rollback()
