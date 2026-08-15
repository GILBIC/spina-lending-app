from __future__ import annotations

import importlib.util
import os
import sys
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

ROOT = Path(__file__).resolve().parents[2]
TEST_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "gilbic_backend" / "src"))
sys.path.insert(0, str(TEST_DIR))

from gilbic_backend.seven_by_seven_operational_allocator import (  # noqa: E402
    SEVEN_BY_SEVEN_OPERATIONAL_POLICY,
    SevenBySevenAllocationError,
    SevenBySevenCashEvent,
    allocate_seven_by_seven_payments,
    fixed_daily_interest_for_original_principal,
)
from spina_app.calculation_rules import allocate_x7_payments  # noqa: E402
import test_seven_by_seven_desktop_server_parity_matrix as b2_matrix  # noqa: E402


PREVIEW_HELPER_PATH = TEST_DIR / "test_7x7_source_event_accounting_preview_postgres.py"
_preview_spec = importlib.util.spec_from_file_location(
    "x7_b3_preview_helpers", PREVIEW_HELPER_PATH
)
assert _preview_spec is not None and _preview_spec.loader is not None
preview_helpers = importlib.util.module_from_spec(_preview_spec)
_preview_spec.loader.exec_module(preview_helpers)

SQL_0064 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0064_add_7x7_source_event_accounting_preview.sql"
).read_text(encoding="utf-8")

MONEY = Decimal("0.01")
ZERO = Decimal("0.00")


def _money(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    return body[len("BEGIN;") : -len("COMMIT;")].strip()


def _create_operational_loan(
    connection: psycopg.Connection,
    *,
    suffix: str,
    principal: Decimal,
    payment_start: date,
    actor_id=None,
    client_id=None,
    loan_type_id=None,
):
    if actor_id is None:
        actor_id = preview_helpers.anchor_helpers._actor(
            connection, suffix + "-mgmt", management=True
        )
    if loan_type_id is None:
        loan_type_id = preview_helpers.anchor_helpers._loan_type(connection, suffix)
    if client_id is None:
        client_id = connection.execute(
            """
            insert into lending.clients (client_code, full_name, status)
            values (%s, %s, 'active') returning id
            """,
            (f"X7B3-C-{suffix}", f"7x7 B3 Client {suffix}"),
        ).fetchone()[0]

    release_date = payment_start - timedelta(days=1)
    daily_interest = fixed_daily_interest_for_original_principal(
        original_principal=principal,
        daily_interest_per_1000=Decimal("7.00"),
    )
    loan_id = connection.execute(
        """
        insert into lending.loans (
            loan_number, client_id, loan_type_id, principal, daily_amount,
            date_released, due_date, status, created_by_user_id
        ) values (%s, %s, %s, %s, %s, %s, %s, 'active', %s)
        returning id
        """,
        (
            f"X7B3-L-{suffix}",
            client_id,
            loan_type_id,
            principal,
            daily_interest,
            release_date,
            release_date + timedelta(days=120),
            actor_id,
        ),
    ).fetchone()[0]
    device_id = preview_helpers._device(connection, actor_id, suffix)
    return actor_id, client_id, loan_type_id, loan_id, device_id


def _case_source_rows(case) -> list[dict[str, Any]]:
    rows = [dict(payment) for payment in case.payments]
    if case.name == "pass_equivalent_days_are_calendar_gap_not_cash":
        first = case.payment_start
        rows.extend(
            {
                "event_id": f"pass-{day}",
                "date": first + timedelta(days=day),
                "payment": "0.00",
                "entry_type": "pass",
            }
            for day in (1, 2, 3)
        )
    return sorted(rows, key=lambda item: (item["date"], item.get("entry_type") == "pass"))


def _insert_source_rows(
    connection: psycopg.Connection,
    *,
    case,
    suffix: str,
    actor_id,
    device_id,
    loan_id,
    sequence_start: int = 1,
) -> dict[str, str]:
    source_ids: dict[str, str] = {}
    for sequence, source in enumerate(_case_source_rows(case), start=sequence_start):
        entry_type = str(source.get("entry_type") or "payment")
        amount = str(source.get("payment", source.get("amount", "0.00")))
        event_id = str(source.get("event_id") or f"source-{sequence}")
        if entry_type == "pass":
            transaction_id = preview_helpers._pass(
                connection,
                actor_id=actor_id,
                device_id=device_id,
                loan_id=loan_id,
                suffix=f"{suffix}-{event_id}",
                collection_date=source["date"],
                device_sequence=sequence,
            )
        else:
            transaction_id = preview_helpers._collection(
                connection,
                actor_id=actor_id,
                device_id=device_id,
                loan_id=loan_id,
                suffix=f"{suffix}-{event_id}",
                collection_date=source["date"],
                amount=amount,
                entry_type=entry_type,
                device_sequence=sequence,
            )

        connection.execute(
            """
            update lending.collection_transactions
            set previous_balance=%s, official_balance=%s
            where id=%s
            """,
            (case.principal, case.principal, transaction_id),
        )

        covered_dates = tuple(source.get("covered_dates") or ())
        if covered_dates:
            connection.execute(
                """
                update lending.collection_transactions
                set advance_from=%s, advance_until=%s
                where id=%s
                """,
                (min(covered_dates), max(covered_dates), transaction_id),
            )
            for covered_date in covered_dates:
                connection.execute(
                    """
                    insert into lending.collection_covered_dates (
                        transaction_id, loan_id, covered_date
                    ) values (%s,%s,%s)
                    """,
                    (transaction_id, loan_id, covered_date),
                )
        source_ids[event_id] = str(transaction_id)
    return source_ids


def _protected_inventory(connection: psycopg.Connection, loan_id):
    return connection.execute(
        """
        select inventory.transaction_id,
               inventory.collection_date,
               inventory.entry_type,
               inventory.amount,
               inventory.is_voided,
               inventory.is_active_positive_cash_event,
               inventory.active_positive_cash_events_on_date,
               coalesce(
                   array(
                       select covered.covered_date
                       from lending.collection_covered_dates covered
                       where covered.transaction_id=inventory.transaction_id
                       order by covered.covered_date
                   ),
                   array[]::date[]
               ) as covered_dates
        from accounting.seven_by_seven_collection_source_inventory inventory
        where inventory.loan_id=%s
        order by inventory.collection_date, inventory.recorded_at, inventory.transaction_id
        """,
        (loan_id,),
    ).fetchall()


def _assert_protected_source_parity(
    connection: psycopg.Connection,
    *,
    case,
    suffix: str,
    actor_id=None,
    client_id=None,
    loan_type_id=None,
):
    actor_id, client_id, loan_type_id, loan_id, device_id = _create_operational_loan(
        connection,
        suffix=suffix,
        principal=case.principal,
        payment_start=case.payment_start,
        actor_id=actor_id,
        client_id=client_id,
        loan_type_id=loan_type_id,
    )
    _insert_source_rows(
        connection,
        case=case,
        suffix=suffix,
        actor_id=actor_id,
        device_id=device_id,
        loan_id=loan_id,
    )

    coordinates = connection.execute(
        """
        select loan.principal,
               loan.date_released + 1,
               loan_type.daily_interest_per_1000,
               coalesce((loan_type.settings->>'mobile_collections_enabled')::boolean, false)
        from lending.loans loan
        join lending.loan_types loan_type on loan_type.id=loan.loan_type_id
        where loan.id=%s
        """,
        (loan_id,),
    ).fetchone()
    assert coordinates == (
        case.principal,
        case.payment_start,
        Decimal("7.00"),
        False,
    )

    inventory = _protected_inventory(connection, loan_id)
    active = [row for row in inventory if row[5]]
    assert active, case.name
    assert all(row[6] == 1 for row in active), case.name

    if case.name == "pass_equivalent_days_are_calendar_gap_not_cash":
        pass_rows = [row for row in inventory if row[2] == "pass"]
        assert len(pass_rows) == 3
        assert all(row[3] == ZERO and row[5] is False for row in pass_rows)

    expected_covered = {
        str(source.get("event_id")): tuple(source.get("covered_dates") or ())
        for source in case.payments
        if source.get("covered_dates")
    }
    if expected_covered:
        observed_covered = {
            row[1]: tuple(row[7])
            for row in active
            if row[2] == "advance"
        }
        assert tuple(expected_covered.values())[0] in observed_covered.values()

    desktop_payments = tuple(
        {
            "event_id": str(row[0]),
            "date": row[1],
            "payment": row[3],
            "entry_type": row[2],
            "covered_dates": tuple(row[7]),
        }
        for row in active
    )
    server_events = tuple(
        SevenBySevenCashEvent(
            event_id=str(row[0]),
            collection_date=row[1],
            amount=row[3],
        )
        for row in active
    )
    as_of_date = max(row[1] for row in active)

    desktop = allocate_x7_payments(
        principal=coordinates[0],
        payment_start=coordinates[1],
        payments=desktop_payments,
        as_of_date=as_of_date,
    )
    server = allocate_seven_by_seven_payments(
        original_principal=coordinates[0],
        daily_interest_per_1000=coordinates[2],
        payment_start=coordinates[1],
        events=server_events,
    )

    desktop_unallocated = _money(
        _money(desktop["total_collected"])
        - _money(desktop["interest_paid"])
        - _money(desktop["principal_paid"])
    )

    assert server.policy == SEVEN_BY_SEVEN_OPERATIONAL_POLICY
    assert server.fixed_daily_interest == _money(desktop["daily_interest"]), case.name
    assert server.total_interest_paid == _money(desktop["interest_paid"]), case.name
    assert server.total_principal_paid == _money(desktop["principal_paid"]), case.name
    assert server.closing_remaining_principal == _money(desktop["remaining_principal"]), case.name
    assert server.closing_interest_arrears == _money(desktop["interest_arrears"]), case.name
    assert server.total_unallocated_cash == desktop_unallocated, case.name
    assert server.complete is (
        _money(desktop["remaining_principal"]) == ZERO
        and _money(desktop["interest_arrears"]) == ZERO
    ), case.name
    assert [line.event_id for line in server.allocations] == [str(row[0]) for row in active]
    assert sum((line.interest_paid for line in server.allocations), ZERO) == server.total_interest_paid
    assert sum((line.principal_paid for line in server.allocations), ZERO) == server.total_principal_paid

    return actor_id, client_id, loan_type_id, loan_id


@pytest.mark.parametrize(
    "case",
    b2_matrix.PARITY_CASES,
    ids=lambda case: f"postgres-{case.name}",
)
def test_exact_desktop_server_matrix_from_protected_postgresql_source_rows(case) -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0064))
            _assert_protected_source_parity(connection, case=case, suffix=suffix)
        finally:
            connection.rollback()


def test_postgresql_renewal_cycles_are_isolated_and_restart_original_principal_basis() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    old_cycle = b2_matrix.ParityCase(
        name="postgres_renewal_old_cycle",
        principal=Decimal("5000.00"),
        payment_start=date(2026, 8, 1),
        payments=(
            {"event_id": "old-1", "date": date(2026, 8, 8), "payment": "100.00"},
            {"event_id": "old-2", "date": date(2026, 8, 9), "payment": "35.00"},
        ),
    )
    renewed_cycle = b2_matrix.ParityCase(
        name="postgres_renewal_new_cycle",
        principal=Decimal("3000.00"),
        payment_start=date(2026, 8, 10),
        payments=(
            {"event_id": "new-1", "date": date(2026, 8, 10), "payment": "21.00"},
            {"event_id": "new-2", "date": date(2026, 8, 11), "payment": "121.00"},
        ),
    )

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0064))
            actor_id, client_id, loan_type_id, old_loan_id = _assert_protected_source_parity(
                connection,
                case=old_cycle,
                suffix=suffix + "-old",
            )
            _, _, _, renewed_loan_id = _assert_protected_source_parity(
                connection,
                case=renewed_cycle,
                suffix=suffix + "-new",
                actor_id=actor_id,
                client_id=client_id,
                loan_type_id=loan_type_id,
            )

            assert old_loan_id != renewed_loan_id
            old_ids = {
                row[0]
                for row in connection.execute(
                    """
                    select transaction_id
                    from accounting.seven_by_seven_collection_source_inventory
                    where loan_id=%s and is_active_positive_cash_event
                    """,
                    (old_loan_id,),
                ).fetchall()
            }
            renewed_ids = {
                row[0]
                for row in connection.execute(
                    """
                    select transaction_id
                    from accounting.seven_by_seven_collection_source_inventory
                    where loan_id=%s and is_active_positive_cash_event
                    """,
                    (renewed_loan_id,),
                ).fetchall()
            }
            assert old_ids
            assert renewed_ids
            assert old_ids.isdisjoint(renewed_ids)

            old_fixed = fixed_daily_interest_for_original_principal(
                original_principal=old_cycle.principal,
                daily_interest_per_1000="7.00",
            )
            renewed_fixed = fixed_daily_interest_for_original_principal(
                original_principal=renewed_cycle.principal,
                daily_interest_per_1000="7.00",
            )
            assert old_fixed == Decimal("35.00")
            assert renewed_fixed == Decimal("21.00")
        finally:
            connection.rollback()


def test_same_day_protected_source_ambiguity_is_not_silently_normalized_for_server() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    case = b2_matrix.ParityCase(
        name="postgres_same_day_ambiguity",
        principal=Decimal("3000.00"),
        payment_start=date(2026, 8, 1),
        payments=(
            {"event_id": "a", "date": date(2026, 8, 1), "payment": "40.00"},
            {"event_id": "b", "date": date(2026, 8, 1), "payment": "50.00"},
        ),
    )

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0064))
            actor_id, _, _, loan_id, device_id = _create_operational_loan(
                connection,
                suffix=suffix,
                principal=case.principal,
                payment_start=case.payment_start,
            )
            _insert_source_rows(
                connection,
                case=case,
                suffix=suffix,
                actor_id=actor_id,
                device_id=device_id,
                loan_id=loan_id,
            )
            active = [row for row in _protected_inventory(connection, loan_id) if row[5]]
            assert len(active) == 2
            assert {row[6] for row in active} == {2}

            with pytest.raises(SevenBySevenAllocationError, match="strictly chronological"):
                allocate_seven_by_seven_payments(
                    original_principal=case.principal,
                    daily_interest_per_1000="7.00",
                    payment_start=case.payment_start,
                    events=tuple(
                        SevenBySevenCashEvent(
                            event_id=str(row[0]),
                            collection_date=row[1],
                            amount=row[3],
                        )
                        for row in active
                    ),
                )

            assert connection.execute(
                """
                select coalesce((loan_type.settings->>'mobile_collections_enabled')::boolean, false)
                from lending.loans loan
                join lending.loan_types loan_type on loan_type.id=loan.loan_type_id
                where loan.id=%s
                """,
                (loan_id,),
            ).fetchone()[0] is False
        finally:
            connection.rollback()
