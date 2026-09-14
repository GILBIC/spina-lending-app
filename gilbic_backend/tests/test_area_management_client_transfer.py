from __future__ import annotations

import inspect
import os
from contextlib import contextmanager
from datetime import date
from uuid import UUID, uuid4

import psycopg
import pytest

import gilbic_backend.area_management_repository as repository_module
import gilbic_backend.collection_posting as collection_posting_module
import gilbic_backend.collector_route_repository as collector_route_module
import gilbic_backend.collector_schedule_repository as collector_schedule_module
import gilbic_backend.other_area_repository as other_area_module
from gilbic_backend.area_management_repository import PostgresAreaManagementRepository

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")


@contextmanager
def _same_connection(connection):
    yield connection


def _insert_user(connection, *, suffix: str, label: str, role: str) -> UUID:
    user_id = connection.execute(
        """
        insert into core.users (username, full_name, status)
        values (%s, %s, 'active')
        returning id
        """,
        (
            f"area-transfer-{label}-{suffix}-{uuid4().hex[:6]}",
            f"Area Transfer {label} {suffix}",
        ),
    ).fetchone()[0]
    connection.execute(
        """
        insert into core.user_roles (user_id, role_id)
        select %s, id from core.roles where code = %s
        """,
        (user_id, role),
    )
    return user_id


def _insert_device(connection, *, user_id: UUID, suffix: str) -> UUID:
    return connection.execute(
        """
        insert into core.devices (
            user_id,
            device_identifier_hash,
            platform,
            status
        ) values (%s, %s, 'desktop', 'active')
        returning id
        """,
        (user_id, f"area-transfer-device-{suffix}-{uuid4().hex[:8]}"),
    ).fetchone()[0]


def _insert_client(
    connection,
    *,
    suffix: str,
    label: str,
    area_uid: UUID,
    area_path: str,
) -> UUID:
    return connection.execute(
        """
        insert into lending.clients (
            client_code,
            full_name,
            area,
            area_uid,
            status
        ) values (%s, %s, %s, %s, 'active')
        returning id
        """,
        (
            f"AREA-XFER-{label}-{suffix}",
            f"Area Transfer Client {label} {suffix}",
            area_path,
            area_uid,
        ),
    ).fetchone()[0]


def _insert_active_verified_schedule(
    connection,
    *,
    suffix: str,
    label: str,
    client_id: UUID,
    actor_user_id: UUID,
    due_dates: tuple[date, ...],
) -> UUID:
    loan_type_id = connection.execute(
        """
        insert into lending.loan_types (
            code,
            name,
            term_days,
            calculation_mode,
            daily_interest_per_1000
        ) values (%s, %s, 120, 'custom', 0)
        returning id
        """,
        (
            f"AX-{label}-{suffix}-{uuid4().hex[:4]}",
            f"Area Transfer {label} {suffix}",
        ),
    ).fetchone()[0]
    loan_id = connection.execute(
        """
        insert into lending.loans (
            loan_number,
            client_id,
            loan_type_id,
            principal,
            daily_amount,
            date_released,
            due_date,
            status
        ) values (%s, %s, %s, 300.00, 100.00, %s, %s, 'active')
        returning id
        """,
        (
            f"AX-L-{label}-{suffix}-{uuid4().hex[:4]}",
            client_id,
            loan_type_id,
            due_dates[0],
            due_dates[-1],
        ),
    ).fetchone()[0]
    schedule_id = connection.execute(
        """
        insert into lending.loan_contract_schedules (
            loan_id,
            schedule_version,
            status,
            payment_frequency,
            contract_reference,
            contract_signed_date,
            effective_from,
            grace_days,
            created_by_user_id
        ) values (%s, 1, 'active', 'custom', %s, %s, %s, 0, %s)
        returning id
        """,
        (
            loan_id,
            f"AX-CONTRACT-{label}-{suffix}",
            due_dates[0],
            due_dates[0],
            actor_user_id,
        ),
    ).fetchone()[0]
    for installment_number, due_date in enumerate(due_dates, start=1):
        connection.execute(
            """
            insert into lending.loan_contract_installments (
                schedule_id,
                installment_number,
                due_date,
                contractual_amount
            ) values (%s, %s, %s, 100.00)
            """,
            (schedule_id, installment_number, due_date),
        )
    connection.execute(
        """
        insert into lending.loan_contract_schedule_registrations (
            schedule_id,
            evidence_basis,
            evidence_reference,
            verification_note,
            verified_by_user_id
        ) values (%s, 'signed_contract', %s, %s, %s)
        """,
        (
            schedule_id,
            f"AX-EVIDENCE-{label}-{suffix}",
            "Verified test schedule for Area transfer timing.",
            actor_user_id,
        ),
    )
    return loan_id


def _insert_official_collection(
    connection,
    *,
    suffix: str,
    loan_id: UUID,
    client_id: UUID,
    collector_user_id: UUID,
    device_id: UUID,
    device_sequence: int,
    collection_date: date,
) -> UUID:
    return connection.execute(
        """
        insert into lending.collection_transactions (
            idempotency_key,
            loan_id,
            client_id,
            collector_user_id,
            registered_device_id,
            route_entry_id,
            collection_date,
            entry_type,
            amount,
            recorded_at,
            device_sequence,
            note,
            previous_balance,
            official_balance,
            pass_count_after,
            advance_until_after,
            receipt_number,
            details
        ) values (
            %s, %s, %s, %s, %s, %s, %s,
            'payment', 100.00, now(), %s, '',
            300.00, 200.00, 0, null, %s, '{}'::jsonb
        )
        returning id
        """,
        (
            uuid4(),
            loan_id,
            client_id,
            collector_user_id,
            device_id,
            loan_id,
            collection_date,
            device_sequence,
            f"AX-R-{suffix}-{uuid4().hex[:8]}",
        ),
    ).fetchone()[0]


def test_client_transfer_interfaces_are_present() -> None:
    repository = PostgresAreaManagementRepository()

    assert callable(getattr(repository, "preview_client_transfer"))
    assert callable(getattr(repository, "schedule_client_transfer"))
    assert callable(getattr(repository_module, "apply_due_client_area_transfers"))


def test_client_transfer_source_uses_persisted_schedule_and_preserves_history() -> None:
    source = inspect.getsource(repository_module).lower()

    assert "def preview_client_transfer" in source
    assert "def schedule_client_transfer" in source
    assert "def apply_due_client_area_transfers" in source
    assert "loan_contract_installments_operational" in source
    assert "effective_due_date" in source
    assert "loan_contract_schedule_registrations" in source
    assert "client_transfer_next_collection_day_unavailable" in source
    assert "client_area_pending_transfers" in source
    assert "client_area_transfer_history" in source
    assert "collection_transactions" in source
    assert "is_voided = false" in source
    assert "timedelta(days=1)" not in source

    for forbidden in (
        "update lending.collection_transactions",
        "delete from lending.collection_transactions",
        "truncate lending.collection_transactions",
        "update lending.collection_remittances",
        "delete from lending.collection_remittances",
        "truncate lending.collection_remittances",
        "update accounting.",
        "delete from accounting.",
        "truncate accounting.",
    ):
        assert forbidden not in source


def test_due_transfer_activation_is_wired_to_authoritative_ownership_boundaries() -> None:
    for module in (
        collector_route_module,
        collector_schedule_module,
        other_area_module,
        collection_posting_module,
    ):
        assert "apply_due_client_area_transfers" in inspect.getsource(module)


@pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)
def test_client_transfer_is_immediate_before_collection_and_deferred_to_next_real_installment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert DATABASE_URL is not None
    connection = psycopg.connect(DATABASE_URL)
    try:
        if connection.execute(
            "select to_regclass('lending.client_area_pending_transfers')"
        ).fetchone()[0] is None:
            pytest.skip("Area Management migration 0113 is not installed")
        if connection.execute(
            "select to_regclass('lending.loan_contract_schedule_registrations')"
        ).fetchone()[0] is None:
            pytest.skip("Verified contract schedule registration is not installed")

        monkeypatch.setattr(
            repository_module,
            "open_connection",
            lambda: _same_connection(connection),
        )
        repository = PostgresAreaManagementRepository()
        suffix = uuid4().hex[:8]
        business_date = date(2026, 9, 7)

        actor_id = _insert_user(
            connection,
            suffix=suffix,
            label="actor",
            role="management",
        )
        old_collector = _insert_user(
            connection,
            suffix=suffix,
            label="old",
            role="collector",
        )
        new_collector = _insert_user(
            connection,
            suffix=suffix,
            label="new",
            role="collector",
        )
        replacement_collector = _insert_user(
            connection,
            suffix=suffix,
            label="replacement",
            role="collector",
        )
        device_id = _insert_device(
            connection,
            user_id=old_collector,
            suffix=suffix,
        )

        root_name = f"Transfer Cardona {suffix}"
        repository.create_area(
            actor_user_id=actor_id,
            parent_area_uid=None,
            name=root_name,
        )
        root_uid = connection.execute(
            "select area_uid from lending.area_nodes where full_path = %s",
            (root_name,),
        ).fetchone()[0]
        for child_name in ("Old Route", "New Route", "Replacement Route"):
            repository.create_area(
                actor_user_id=actor_id,
                parent_area_uid=root_uid,
                name=child_name,
            )

        old_path = f"{root_name} › Old Route"
        new_path = f"{root_name} › New Route"
        replacement_path = f"{root_name} › Replacement Route"
        old_uid = connection.execute(
            "select area_uid from lending.area_nodes where full_path = %s",
            (old_path,),
        ).fetchone()[0]
        new_uid = connection.execute(
            "select area_uid from lending.area_nodes where full_path = %s",
            (new_path,),
        ).fetchone()[0]
        replacement_uid = connection.execute(
            "select area_uid from lending.area_nodes where full_path = %s",
            (replacement_path,),
        ).fetchone()[0]
        repository.assign_collector(
            actor_user_id=actor_id,
            area_uid=old_uid,
            collector_user_id=old_collector,
        )
        repository.assign_collector(
            actor_user_id=actor_id,
            area_uid=new_uid,
            collector_user_id=new_collector,
        )
        repository.assign_collector(
            actor_user_id=actor_id,
            area_uid=replacement_uid,
            collector_user_id=replacement_collector,
        )

        immediate_client = _insert_client(
            connection,
            suffix=suffix,
            label="immediate",
            area_uid=old_uid,
            area_path=old_path,
        )
        preview = repository.preview_client_transfer(
            client_id=immediate_client,
            target_area_uid=new_uid,
            as_of_date=business_date,
        )
        assert preview.timing == "immediate"
        assert preview.effective_date == business_date
        assert preview.old_area_uid == old_uid
        assert preview.new_area_uid == new_uid
        assert preview.old_effective_collector_user_id == old_collector
        assert preview.new_effective_collector_user_id == new_collector

        repository.schedule_client_transfer(
            actor_user_id=actor_id,
            client_id=immediate_client,
            target_area_uid=new_uid,
            as_of_date=business_date,
        )
        assert connection.execute(
            "select area_uid, area from lending.clients where id = %s",
            (immediate_client,),
        ).fetchone() == (new_uid, new_path)
        assert connection.execute(
            """
            select timing, effective_date, new_area_uid
            from lending.client_area_transfer_history
            where client_id = %s
            """,
            (immediate_client,),
        ).fetchone() == ("immediate", business_date, new_uid)

        deferred_client = _insert_client(
            connection,
            suffix=suffix,
            label="deferred",
            area_uid=old_uid,
            area_path=old_path,
        )
        deferred_loan = _insert_active_verified_schedule(
            connection,
            suffix=suffix,
            label="deferred",
            client_id=deferred_client,
            actor_user_id=actor_id,
            due_dates=(
                business_date,
                date(2026, 9, 9),
                date(2026, 9, 10),
            ),
        )
        transaction_id = _insert_official_collection(
            connection,
            suffix=suffix,
            loan_id=deferred_loan,
            client_id=deferred_client,
            collector_user_id=old_collector,
            device_id=device_id,
            device_sequence=1,
            collection_date=business_date,
        )
        historical_before = connection.execute(
            """
            select
                assignment_area,
                assigned_collector_user_id,
                collector_user_id,
                receipt_number,
                amount
            from lending.collection_transactions
            where id = %s
            """,
            (transaction_id,),
        ).fetchone()

        preview = repository.preview_client_transfer(
            client_id=deferred_client,
            target_area_uid=new_uid,
            as_of_date=business_date,
        )
        assert preview.timing == "next_collection_day"
        assert preview.effective_date == date(2026, 9, 9)
        assert preview.effective_date != date(2026, 9, 8)

        repository.schedule_client_transfer(
            actor_user_id=actor_id,
            client_id=deferred_client,
            target_area_uid=new_uid,
            as_of_date=business_date,
        )
        assert connection.execute(
            "select area_uid, area from lending.clients where id = %s",
            (deferred_client,),
        ).fetchone() == (old_uid, old_path)

        first_pending_id = connection.execute(
            """
            select id
            from lending.client_area_pending_transfers
            where client_id = %s
              and applied_at is null
              and cancelled_at is null
            """,
            (deferred_client,),
        ).fetchone()[0]
        repository.schedule_client_transfer(
            actor_user_id=actor_id,
            client_id=deferred_client,
            target_area_uid=replacement_uid,
            as_of_date=business_date,
        )
        assert connection.execute(
            """
            select cancelled_at is not null
            from lending.client_area_pending_transfers
            where id = %s
            """,
            (first_pending_id,),
        ).fetchone()[0] is True
        pending = connection.execute(
            """
            select target_area_uid, effective_date
            from lending.client_area_pending_transfers
            where client_id = %s
              and applied_at is null
              and cancelled_at is null
            """,
            (deferred_client,),
        ).fetchone()
        assert pending == (replacement_uid, date(2026, 9, 9))

        repository_module.apply_due_client_area_transfers(
            connection,
            as_of_date=date(2026, 9, 8),
            client_id=deferred_client,
        )
        assert connection.execute(
            "select area_uid from lending.clients where id = %s",
            (deferred_client,),
        ).fetchone()[0] == old_uid

        repository_module.apply_due_client_area_transfers(
            connection,
            as_of_date=date(2026, 9, 9),
            client_id=deferred_client,
        )
        assert connection.execute(
            "select area_uid, area from lending.clients where id = %s",
            (deferred_client,),
        ).fetchone() == (replacement_uid, replacement_path)
        history_count = connection.execute(
            """
            select count(*)
            from lending.client_area_transfer_history
            where client_id = %s
              and timing = 'next_collection_day'
            """,
            (deferred_client,),
        ).fetchone()[0]
        assert history_count == 1

        repository_module.apply_due_client_area_transfers(
            connection,
            as_of_date=date(2026, 9, 9),
            client_id=deferred_client,
        )
        assert connection.execute(
            """
            select count(*)
            from lending.client_area_transfer_history
            where client_id = %s
              and timing = 'next_collection_day'
            """,
            (deferred_client,),
        ).fetchone()[0] == history_count

        historical_after = connection.execute(
            """
            select
                assignment_area,
                assigned_collector_user_id,
                collector_user_id,
                receipt_number,
                amount
            from lending.collection_transactions
            where id = %s
            """,
            (transaction_id,),
        ).fetchone()
        assert historical_after == historical_before

        no_future_client = _insert_client(
            connection,
            suffix=suffix,
            label="no-future",
            area_uid=old_uid,
            area_path=old_path,
        )
        no_future_loan = _insert_active_verified_schedule(
            connection,
            suffix=suffix,
            label="no-future",
            client_id=no_future_client,
            actor_user_id=actor_id,
            due_dates=(business_date,),
        )
        _insert_official_collection(
            connection,
            suffix=suffix,
            loan_id=no_future_loan,
            client_id=no_future_client,
            collector_user_id=old_collector,
            device_id=device_id,
            device_sequence=2,
            collection_date=business_date,
        )
        with pytest.raises(ValueError, match="client_transfer_next_collection_day_unavailable"):
            repository.preview_client_transfer(
                client_id=no_future_client,
                target_area_uid=new_uid,
                as_of_date=business_date,
            )
    finally:
        connection.rollback()
        connection.close()
