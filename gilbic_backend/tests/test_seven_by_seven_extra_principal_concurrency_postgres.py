from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Barrier, Event
from uuid import UUID, uuid4

import gilbic_backend.collection_void_repository as void_repository_module
import gilbic_backend.refund_due_repository as refund_repository_module
import psycopg
import pytest
from gilbic_backend.collection_void_repository import (
    CollectionVoidConflict,
    CollectionVoidRecord,
    PostgresCollectionVoidRepository,
)
from gilbic_backend.refund_due_repository import (
    PostgresRefundDueRepository,
    RefundDueReleaseNotApproved,
)
from gilbic_backend.seven_by_seven_extra_principal_replay import (
    verify_persisted_extra_principal_replay,
)
from psycopg.rows import dict_row
from spina_mobile_collections.contracts import CollectionStatus, PaymentAllocationIntent
from test_seven_by_seven_extra_principal_reversal_requests_postgres import (
    _seed_extra_principal_case,
    _test_connection,
)
from test_seven_by_seven_mobile_collection_postgres import (
    _command,
    _register_verified_schedule,
    _setup_case,
    _submit,
)

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)


def _capture(call):
    try:
        return call()
    except Exception as error:
        return error


def test_concurrent_identical_requests_create_one_receipt_and_adjustment() -> None:
    assert DATABASE_URL is not None
    case = _setup_case()
    _register_verified_schedule(case)
    scheduled = _submit(case, _command(case, amount="50.00"))
    assert scheduled.status is CollectionStatus.ACCEPTED
    command = _command(
        case,
        key=uuid4(),
        amount="100.00",
        device_sequence=2,
        route_version=1,
        payment_allocation_intent=(
            PaymentAllocationIntent.EXTRA_AS_PRINCIPAL_REDUCTION
        ),
    )
    start = Barrier(2)

    def submit():
        start.wait()
        return _submit(case, command)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            future.result()
            for future in (executor.submit(submit), executor.submit(submit))
        )

    assert sorted(result.status.value for result in results) == [
        CollectionStatus.ACCEPTED.value,
        CollectionStatus.DUPLICATE.value,
    ]
    accepted = next(
        result for result in results if result.status is CollectionStatus.ACCEPTED
    )
    duplicate = next(
        result for result in results if result.status is CollectionStatus.DUPLICATE
    )
    assert accepted.posted is not None and duplicate.posted is not None
    assert (
        duplicate.posted.server_transaction_id == accepted.posted.server_transaction_id
    )
    assert duplicate.posted.result_metadata == accepted.posted.result_metadata
    assert duplicate.posted.official_balance == accepted.posted.official_balance
    assert duplicate.posted.route_revision == accepted.posted.route_revision

    with psycopg.connect(DATABASE_URL) as connection:
        counts = connection.execute(
            """
            select
                (select count(*) from lending.collection_transactions
                  where idempotency_key = %s),
                (select count(*)
                   from lending.seven_by_seven_extra_principal_adjustments adjustment
                   join lending.collection_transactions transaction
                     on transaction.id = adjustment.transaction_id
                  where transaction.idempotency_key = %s)
            """,
            (command.idempotency_key, command.idempotency_key),
        ).fetchone()
    assert counts == (1, 1)


def test_concurrent_post_and_reversal_serialize_without_partial_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert DATABASE_URL is not None
    case = _setup_case()
    _register_verified_schedule(case)
    scheduled = _submit(case, _command(case, amount="50.00"))
    assert scheduled.status is CollectionStatus.ACCEPTED
    first_extra = _submit(
        case,
        _command(
            case,
            amount="100.00",
            device_sequence=2,
            route_version=1,
            payment_allocation_intent=(
                PaymentAllocationIntent.EXTRA_AS_PRINCIPAL_REDUCTION
            ),
        ),
    )
    assert first_extra.status is CollectionStatus.ACCEPTED
    assert first_extra.posted is not None
    first_transaction_id = UUID(first_extra.posted.server_transaction_id)
    monkeypatch.setattr(void_repository_module, "open_connection", _test_connection)
    second_command = _command(
        case,
        amount="75.00",
        device_sequence=3,
        route_version=2,
        payment_allocation_intent=(
            PaymentAllocationIntent.EXTRA_AS_PRINCIPAL_REDUCTION
        ),
    )
    start = Barrier(2)

    def post_second():
        start.wait()
        return _submit(case, second_command)

    def reverse_first():
        start.wait()
        return _capture(
            lambda: PostgresCollectionVoidRepository().void_unremitted(
                actor_user_id=case.collector_id,
                transaction_id=first_transaction_id,
                reason="Concurrent correction",
                idempotency_key=uuid4(),
            )
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        post_future = executor.submit(post_second)
        reversal_future = executor.submit(reverse_first)
        post_result = post_future.result()
        reversal_result = reversal_future.result()

    accepted_post = post_result.status is CollectionStatus.ACCEPTED
    completed_reversal = isinstance(reversal_result, CollectionVoidRecord)
    assert accepted_post is not completed_reversal
    if accepted_post:
        assert isinstance(reversal_result, CollectionVoidConflict)
    else:
        assert post_result.status is CollectionStatus.CONFLICT

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        state = connection.execute(
            """
            select
                    (select count(*) from lending.collection_transactions
                      where loan_id = %s) as receipt_count,
                    (select count(*)
                       from lending.seven_by_seven_extra_principal_adjustments
                      where loan_id = %s) as adjustment_count,
                    (select count(*)
                       from lending.seven_by_seven_extra_principal_reversals
                      where loan_id = %s) as reversal_count,
                    (select is_voided
                       from lending.collection_transactions
                      where id = %s)
                        as first_is_voided,
                collection_state.state_version,
                operational_state.operational_version,
                operational_state.schedule_id
            from lending.loan_collection_state collection_state
            join lending.loan_contract_schedules schedule
              on schedule.loan_id = collection_state.loan_id
             and schedule.status = 'active'
            join lending.loan_schedule_operational_state operational_state
              on operational_state.schedule_id = schedule.id
            where collection_state.loan_id = %s
            """,
            (
                case.loan_id,
                case.loan_id,
                case.loan_id,
                first_transaction_id,
                case.loan_id,
            ),
        ).fetchone()
        assert state is not None
        with connection.cursor() as cursor:
            replay = verify_persisted_extra_principal_replay(
                cursor,
                schedule_id=state["schedule_id"],
            )

    assert state["state_version"] == 3
    assert state["operational_version"] == 2
    if accepted_post:
        assert (
            state["receipt_count"],
            state["adjustment_count"],
            state["reversal_count"],
            state["first_is_voided"],
        ) == (3, 2, 0, False)
        assert len(replay.active_adjustment_ids) == 2
    else:
        assert (
            state["receipt_count"],
            state["adjustment_count"],
            state["reversal_count"],
            state["first_is_voided"],
        ) == (2, 1, 1, True)
        assert replay.active_adjustment_ids == ()


def test_concurrent_release_after_reversal_lock_is_rejected_from_fresh_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert DATABASE_URL is not None
    adjustment_id, transaction_id, actor_id = _seed_extra_principal_case()
    monkeypatch.setattr(void_repository_module, "open_connection", _test_connection)
    monkeypatch.setattr(refund_repository_module, "open_connection", _test_connection)
    refunds = PostgresRefundDueRepository()
    approval = refunds.approve(
        idempotency_key=uuid4(),
        actor_user_id=actor_id,
        adjustment_id=adjustment_id,
        approved_amount=Decimal("5.00"),
        reason="Approve before concurrent release test",
        authority_reference="MGT-CONCURRENCY-REFUND-0001",
    )
    release_reached_common_lock = Event()
    allow_release = Event()
    original_advisory_lock = refund_repository_module._advisory_lock
    common_key = f"refund-due-adjustment:{adjustment_id}"

    def pause_before_common_lock(cursor, key: str) -> None:
        if key == common_key:
            release_reached_common_lock.set()
            assert allow_release.wait(timeout=10)
        original_advisory_lock(cursor, key)

    monkeypatch.setattr(
        refund_repository_module, "_advisory_lock", pause_before_common_lock
    )

    def release():
        return _capture(
            lambda: refunds.release(
                idempotency_key=uuid4(),
                actor_user_id=actor_id,
                approval_id=approval.approval_id,
                released_amount=Decimal("5.00"),
                released_at=datetime.now(UTC) + timedelta(minutes=1),
                evidence_reference="SIGNED-CONCURRENT-REFUND-0001",
                evidence_digest="d" * 64,
            )
        )

    with ThreadPoolExecutor(max_workers=1) as executor:
        release_future = executor.submit(release)
        assert release_reached_common_lock.wait(timeout=10)
        reversal = PostgresCollectionVoidRepository().void_unremitted(
            actor_user_id=actor_id,
            transaction_id=transaction_id,
            reason="Concurrent reversal wins common lock",
            idempotency_key=uuid4(),
        )
        allow_release.set()
        release_result = release_future.result(timeout=10)

    assert isinstance(reversal, CollectionVoidRecord)
    assert isinstance(release_result, RefundDueReleaseNotApproved)
    with psycopg.connect(DATABASE_URL) as connection:
        counts = connection.execute(
            """
            select
                (select count(*)
                   from lending.loan_unused_advance_refund_due_releases
                  where approval_id = %s),
                (select count(*)
                   from lending.seven_by_seven_extra_principal_reversals
                  where adjustment_id = %s)
            """,
            (approval.approval_id, adjustment_id),
        ).fetchone()
    assert counts == (0, 1)


def test_stale_operational_version_rolls_back_entire_void() -> None:
    assert DATABASE_URL is not None
    adjustment_id, transaction_id, actor_id = _seed_extra_principal_case()
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            """
            update lending.loan_schedule_operational_state state
            set operational_version = 2
            from lending.seven_by_seven_extra_principal_adjustments adjustment
            where adjustment.id = %s
              and state.schedule_id = adjustment.schedule_id
            """,
            (adjustment_id,),
        )

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(void_repository_module, "open_connection", _test_connection)
        with pytest.raises(
            psycopg.Error, match="operational schedule version is stale"
        ):
            PostgresCollectionVoidRepository().void_unremitted(
                actor_user_id=actor_id,
                transaction_id=transaction_id,
                reason="Stale operational version test",
                idempotency_key=uuid4(),
            )

    with psycopg.connect(DATABASE_URL) as connection:
        state = connection.execute(
            """
            select
                transaction.is_voided,
                (select count(*) from lending.collection_transaction_voids
                  where transaction_id = transaction.id),
                (select count(*)
                   from lending.seven_by_seven_extra_principal_reversal_requests
                  where transaction_id = transaction.id),
                (select count(*)
                   from lending.seven_by_seven_extra_principal_reversals
                  where adjustment_id = %s)
            from lending.collection_transactions transaction where transaction.id = %s
            """,
            (adjustment_id, transaction_id),
        ).fetchone()
    assert state == (False, 0, 0, 0)


def test_forced_reversal_evidence_failure_rolls_back_every_fragment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert DATABASE_URL is not None
    adjustment_id, transaction_id, actor_id = _seed_extra_principal_case()
    trigger_name = f"zz_test_fail_extra_reversal_{uuid4().hex[:12]}"
    function_name = f"test_fail_extra_reversal_{uuid4().hex[:12]}"
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            f"""
            create function lending.{function_name}()
            returns trigger language plpgsql as $$
            begin
                raise exception 'forced Extra Principal reversal evidence failure';
            end;
            $$
            """
        )
        connection.execute(
            f"""
            create trigger {trigger_name}
            before insert on lending.seven_by_seven_extra_principal_reversal_items
            for each row execute function lending.{function_name}()
            """
        )

    monkeypatch.setattr(void_repository_module, "open_connection", _test_connection)
    try:
        with pytest.raises(psycopg.Error, match="forced Extra Principal reversal"):
            PostgresCollectionVoidRepository().void_unremitted(
                actor_user_id=actor_id,
                transaction_id=transaction_id,
                reason="Force atomic rollback",
                idempotency_key=uuid4(),
            )

        with psycopg.connect(DATABASE_URL) as connection:
            state = connection.execute(
                """
                select
                    transaction.is_voided,
                    (select count(*) from lending.collection_transaction_voids
                      where transaction_id = transaction.id),
                    (select count(*)
                       from lending.seven_by_seven_extra_principal_reversal_requests
                      where transaction_id = transaction.id),
                    (select count(*)
                       from lending.seven_by_seven_extra_principal_reversals
                      where adjustment_id = %s),
                    (select operational_version
                       from lending.loan_schedule_operational_state state
                       join lending.seven_by_seven_extra_principal_adjustments
                         adjustment
                         on adjustment.schedule_id = state.schedule_id
                      where adjustment.id = %s),
                    (select sum(operational.operational_principal_component)
                       from lending.loan_installment_operational_amounts operational
                       join lending.loan_contract_installments installment
                         on installment.id = operational.installment_id
                       join lending.seven_by_seven_extra_principal_adjustments
                         adjustment
                         on adjustment.schedule_id = installment.schedule_id
                      where adjustment.id = %s)
                from lending.collection_transactions transaction
                where transaction.id = %s
                """,
                (adjustment_id, adjustment_id, adjustment_id, transaction_id),
            ).fetchone()
        assert state == (False, 0, 0, 0, 1, Decimal("2967.00"))
    finally:
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute(
                f"drop trigger if exists {trigger_name} on "
                "lending.seven_by_seven_extra_principal_reversal_items"
            )
            connection.execute(f"drop function if exists lending.{function_name}()")
