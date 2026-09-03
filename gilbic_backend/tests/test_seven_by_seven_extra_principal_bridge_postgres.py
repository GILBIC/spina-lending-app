from __future__ import annotations

import os
from uuid import uuid4

import psycopg
import pytest

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

EVIDENCE_TABLES = (
    "seven_by_seven_extra_principal_reversal_requests",
    "seven_by_seven_extra_principal_reversals",
    "seven_by_seven_extra_principal_reversal_items",
    "loan_unused_advance_refund_due_approvals",
    "loan_unused_advance_refund_due_approval_items",
    "loan_unused_advance_refund_due_releases",
    "loan_unused_advance_refund_due_release_items",
    "collection_remittance_refund_due_release_items",
)


def test_0108_installs_real_bridge_relations_views_and_guards() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        relations = {
            row[0]: row[1]
            for row in connection.execute(
                """
                select candidate.name, to_regclass('lending.' || candidate.name)::text
                from unnest(%s::text[]) candidate(name)
                """,
                (list(EVIDENCE_TABLES),),
            ).fetchall()
        }
        assert relations == {name: f"lending.{name}" for name in EVIDENCE_TABLES}

        views = {
            row[0]
            for row in connection.execute(
                """
                select table_name
                from information_schema.views
                where table_schema in ('lending', 'accounting')
                  and table_name = any(%s::text[])
                """,
                (
                    [
                        "loan_unused_advance_refund_due_status",
                        "seven_by_seven_extra_principal_reversal_status",
                        "loan_installment_active_advance",
                        "seven_by_seven_extra_principal_accounting_readiness",
                    ],
                ),
            ).fetchall()
        }
        assert views == {
            "loan_unused_advance_refund_due_status",
            "seven_by_seven_extra_principal_reversal_status",
            "loan_installment_active_advance",
            "seven_by_seven_extra_principal_accounting_readiness",
        }

        guarded_tables = {
            row[0]
            for row in connection.execute(
                """
                select event_object_table as table_name
                from information_schema.triggers
                where trigger_schema = 'lending'
                  and action_statement like '%guard_7x7_bridge_append_only%'
                group by event_object_table
                """
            ).fetchall()
        }
        assert guarded_tables == set(EVIDENCE_TABLES)

        last_adjustment_nullable = connection.execute(
            """
            select is_nullable
            from information_schema.columns
            where table_schema = 'lending'
              and table_name = 'loan_installment_operational_amounts'
              and column_name = 'last_extra_principal_adjustment_id'
            """
        ).fetchone()[0]
        assert last_adjustment_nullable == "YES"


@pytest.mark.parametrize(
    ("statement", "parameters"),
    (
        (
            """
            insert into lending.seven_by_seven_extra_principal_reversal_requests (
                idempotency_key, canonical_request_hash, transaction_id,
                adjustment_id, requested_by_user_id, reason, outcome,
                released_refund_amount, result_payload
            ) values (%s, %s, %s, %s, %s, 'unauthorized',
                      'blocked_refund_released', 1.00, '{}'::jsonb)
            """,
            5,
        ),
        (
            """
            insert into lending.loan_unused_advance_refund_due_approvals (
                idempotency_key, canonical_request_hash, adjustment_id,
                loan_id, client_id, approved_amount, approved_by_user_id,
                reason, authority_reference, result_payload
            ) values (%s, %s, %s, %s, %s, 1.00, %s,
                      'unauthorized', 'unauthorized', '{}'::jsonb)
            """,
            6,
        ),
        (
            """
            insert into lending.loan_unused_advance_refund_due_releases (
                idempotency_key, canonical_request_hash, approval_id,
                loan_id, client_id, assigned_collector_user_id,
                released_amount, released_by_user_id, released_at,
                evidence_reference, evidence_digest, result_payload
            ) values (%s, %s, %s, %s, %s, %s, 1.00, %s, now(),
                      'unauthorized', %s, '{}'::jsonb)
            """,
            8,
        ),
    ),
)
def test_direct_bridge_evidence_inserts_fail_closed(
    statement: str,
    parameters: int,
) -> None:
    assert DATABASE_URL is not None
    values = [uuid4(), "0" * 64]
    values.extend(uuid4() for _ in range(parameters - 2))
    if parameters == 8:
        values[-1] = "0" * 64

    with (
        psycopg.connect(DATABASE_URL) as connection,
        pytest.raises(
            psycopg.errors.InsufficientPrivilege,
            match="controlled transaction-local writer",
        ),
    ):
        connection.execute(statement, tuple(values))
