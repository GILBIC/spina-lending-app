from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import gilbic_backend.refund_due_repository as refund_repository_module
import psycopg
import pytest
from gilbic_backend.refund_due_repository import (
    PostgresRefundDueRepository,
    RefundDueApprovalIdempotencyMismatch,
    RefundDueReleaseIdempotencyMismatch,
)
from psycopg.rows import dict_row
from test_seven_by_seven_extra_principal_persistence_postgres import (
    _record_adjustment,
    _setup_case,
)

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)


def _require_0108_schema() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        relation = connection.execute(
            "select to_regclass('lending.loan_unused_advance_refund_due_approvals')"
        ).fetchone()[0]
        payload_column = connection.execute(
            """
            select count(*)
            from information_schema.columns
            where table_schema = 'lending'
              and table_name = 'loan_unused_advance_refund_due_approvals'
              and column_name = 'result_payload'
            """
        ).fetchone()[0]
    if relation is None or payload_column != 1:
        pytest.skip(
            "Migration 0108 is not installed; disposable bridge validation owns this test."
        )


@contextmanager
def _test_connection():
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        yield connection


def test_approval_and_physical_release_are_exact_idempotent_separate_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert DATABASE_URL is not None
    _require_0108_schema()
    loan_id, client_id, collector_id, device_id, installment_id = _setup_case()
    unique_area = f"Refund-Due-{uuid4().hex[:12]}"
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            "update lending.clients set area = %s where id = %s",
            (unique_area, client_id),
        )
        connection.execute(
            """
            insert into lending.collector_area_assignments (
                collector_user_id, area, sort_order, is_active
            ) values (%s, %s, 0, true)
            """,
            (collector_id, unique_area),
        )
        adjustment_id = _record_adjustment(
            connection,
            loan_id=loan_id,
            client_id=client_id,
            collector_id=collector_id,
            device_id=device_id,
            installment_id=installment_id,
            sequence=2,
            expected_version=0,
            prior_future_principal="3000.00",
            reduction="20.00",
            prior_principal="29.00",
            prior_amount="50.00",
            new_principal="9.00",
            new_amount="30.00",
            advance_before="35.00",
            advance_retained="30.00",
            refund_due="5.00",
        )
        principal_before = connection.execute(
            "select principal from lending.loans where id = %s",
            (loan_id,),
        ).fetchone()[0]

    monkeypatch.setattr(refund_repository_module, "open_connection", _test_connection)
    repository = PostgresRefundDueRepository()
    approval_key = uuid4()
    approval = repository.approve(
        idempotency_key=approval_key,
        actor_user_id=collector_id,
        adjustment_id=adjustment_id,
        approved_amount=Decimal("5.00"),
        reason="Borrower requested return of unused Advance",
        authority_reference="MGT-REFUND-0001",
    )
    duplicate_approval = repository.approve(
        idempotency_key=approval_key,
        actor_user_id=collector_id,
        adjustment_id=adjustment_id,
        approved_amount=Decimal("5.00"),
        reason="Borrower requested return of unused Advance",
        authority_reference="MGT-REFUND-0001",
    )
    assert duplicate_approval == approval
    with pytest.raises(RefundDueApprovalIdempotencyMismatch):
        repository.approve(
            idempotency_key=approval_key,
            actor_user_id=collector_id,
            adjustment_id=adjustment_id,
            approved_amount=Decimal("4.00"),
            reason="Borrower requested return of unused Advance",
            authority_reference="MGT-REFUND-0001",
        )

    with (
        psycopg.connect(DATABASE_URL) as connection,
        connection.cursor(row_factory=dict_row) as cursor,
    ):
        cash_after_approval = refund_repository_module._collector_cash_held(
            cursor,
            collector_user_id=collector_id,
        )

    release_key = uuid4()
    released_at = datetime(2099, 1, 1, 9, tzinfo=timezone.utc)
    release = repository.release(
        idempotency_key=release_key,
        actor_user_id=collector_id,
        approval_id=approval.approval_id,
        released_amount=Decimal("5.00"),
        released_at=released_at,
        evidence_reference="SIGNED-REFUND-0001",
        evidence_digest="a" * 64,
    )
    duplicate_release = repository.release(
        idempotency_key=release_key,
        actor_user_id=collector_id,
        approval_id=approval.approval_id,
        released_amount=Decimal("5.00"),
        released_at=released_at,
        evidence_reference="SIGNED-REFUND-0001",
        evidence_digest="a" * 64,
    )
    assert duplicate_release == release
    with pytest.raises(RefundDueReleaseIdempotencyMismatch):
        repository.release(
            idempotency_key=release_key,
            actor_user_id=collector_id,
            approval_id=approval.approval_id,
            released_amount=Decimal("5.00"),
            released_at=released_at,
            evidence_reference="CHANGED-EVIDENCE",
            evidence_digest="a" * 64,
        )

    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cash_after_release = refund_repository_module._collector_cash_held(
                cursor,
                collector_user_id=collector_id,
            )
        evidence = connection.execute(
            """
            select
                (select count(*)
                   from lending.loan_unused_advance_refund_due_approvals
                  where id = %s),
                (select count(*)
                   from lending.loan_unused_advance_refund_due_releases
                  where id = %s),
                (select sum(released_amount)
                   from lending.loan_unused_advance_refund_due_releases
                  where approval_id = %s),
                (select sum(outstanding_refund_due)
                   from lending.loan_unused_advance_refund_due_status
                  where adjustment_id = %s),
                (select principal from lending.loans where id = %s)
            """,
            (
                approval.approval_id,
                release.release_id,
                approval.approval_id,
                adjustment_id,
                loan_id,
            ),
        ).fetchone()

    assert cash_after_release == cash_after_approval - Decimal("5.00")
    assert evidence == (1, 1, Decimal("5.00"), Decimal("0.00"), principal_before)
