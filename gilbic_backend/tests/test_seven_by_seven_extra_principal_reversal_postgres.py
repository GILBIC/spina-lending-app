from __future__ import annotations

import os
from decimal import Decimal
from uuid import uuid4

import gilbic_backend.collection_void_repository as void_repository_module
import psycopg
import pytest
from gilbic_backend.collection_void_repository import (
    CollectionVoidRecord,
    PostgresCollectionVoidRepository,
)
from gilbic_backend.seven_by_seven_extra_principal_replay import (
    verify_persisted_extra_principal_replay,
)
from psycopg.rows import dict_row
from test_seven_by_seven_extra_principal_reversal_requests_postgres import (
    _seed_extra_principal_case,
    _test_connection,
)

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)


def _void_seeded_extra_principal(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[object, object, object]:
    adjustment_id, transaction_id, actor_id = _seed_extra_principal_case()
    monkeypatch.setattr(void_repository_module, "open_connection", _test_connection)
    result = PostgresCollectionVoidRepository().void_unremitted(
        actor_user_id=actor_id,
        transaction_id=transaction_id,
        reason="Reverse mistaken Extra Principal receipt",
        idempotency_key=uuid4(),
    )
    assert isinstance(result, CollectionVoidRecord)
    return adjustment_id, transaction_id, actor_id


def test_successful_reversal_reconstructs_schedule_and_preserves_originals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert DATABASE_URL is not None
    adjustment_id, transaction_id, _ = _void_seeded_extra_principal(monkeypatch)

    with psycopg.connect(DATABASE_URL) as connection:
        adjustment = connection.execute(
            """
            select schedule_id, prior_future_principal,
                   resulting_future_principal, principal_reduction
            from lending.seven_by_seven_extra_principal_adjustments
            where id = %s
            """,
            (adjustment_id,),
        ).fetchone()
        assert adjustment is not None
        schedule_id = adjustment[0]
        assert adjustment[1:] == (
            Decimal("3000.00"),
            Decimal("2967.00"),
            Decimal("33.00"),
        )

        signed_and_operational = connection.execute(
            """
            select
                installment.contractual_amount,
                installment.principal_component,
                installment.interest_component,
                operational.operational_amount,
                operational.operational_principal_component,
                operational.operational_interest_component,
                operational.removed_from_operational_schedule,
                operational.last_extra_principal_adjustment_id
            from lending.loan_contract_installments installment
            join lending.loan_installment_operational_amounts operational
              on operational.installment_id = installment.id
            where installment.schedule_id = %s
            order by installment.installment_number
            """,
            (schedule_id,),
        ).fetchall()
        assert signed_and_operational
        assert all(row[:3] == row[3:6] for row in signed_and_operational)
        assert all(row[6:] == (False, None) for row in signed_and_operational)

        reversal = connection.execute(
            """
            select
                expected_operational_version,
                resulting_operational_version,
                original_operational_principal,
                reconstructed_operational_principal,
                restored_active_advance,
                cancelled_refund_due,
                source_history_digest,
                operational_state_digest
            from lending.seven_by_seven_extra_principal_reversals
            where adjustment_id = %s
            """,
            (adjustment_id,),
        ).fetchone()
        assert reversal is not None
        assert reversal[:6] == (
            1,
            2,
            Decimal("2967.00"),
            Decimal("3000.00"),
            Decimal("5.00"),
            Decimal("5.00"),
        )
        assert len(reversal[6]) == len(reversal[7]) == 64

        evidence_counts = connection.execute(
            """
            select
                (select count(*)
                   from lending.seven_by_seven_extra_principal_adjustment_items
                  where adjustment_id = %s),
                (select count(*)
                   from lending.seven_by_seven_extra_principal_reversal_items item
                   join lending.seven_by_seven_extra_principal_reversals reversal
                     on reversal.id = item.reversal_id
                  where reversal.adjustment_id = %s),
                (select count(*)
                   from lending.loan_contract_installments installment
                  where installment.schedule_id = %s),
                (select is_voided
                   from lending.collection_transactions
                  where id = %s)
            """,
            (adjustment_id, adjustment_id, schedule_id, transaction_id),
        ).fetchone()
        assert evidence_counts[0] == evidence_counts[1] == evidence_counts[2]
        assert evidence_counts[3] is True


def test_read_only_replay_matches_persisted_reversal_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert DATABASE_URL is not None
    adjustment_id, _, _ = _void_seeded_extra_principal(monkeypatch)

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        reversal = connection.execute(
            """
            select schedule_id, source_history_digest, operational_state_digest
            from lending.seven_by_seven_extra_principal_reversals
            where adjustment_id = %s
            """,
            (adjustment_id,),
        ).fetchone()
        assert reversal is not None
        with connection.cursor() as cursor:
            replayed = verify_persisted_extra_principal_replay(
                cursor,
                schedule_id=reversal["schedule_id"],
                expected_source_history_digest=reversal[
                    "source_history_digest"
                ],
                expected_operational_state_digest=reversal[
                    "operational_state_digest"
                ],
            )

        assert replayed.active_adjustment_ids == ()
        assert replayed.future_principal == Decimal("3000.00")
