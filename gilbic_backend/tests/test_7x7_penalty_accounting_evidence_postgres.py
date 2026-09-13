from __future__ import annotations

import importlib.util
import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

TEST_DIR = Path(__file__).resolve().parent
SOURCE_PATH = TEST_DIR / "test_7x7_post_maturity_penalty_postgres.py"
_spec = importlib.util.spec_from_file_location("penalty_accounting_cases", SOURCE_PATH)
assert _spec is not None and _spec.loader is not None
cases = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cases)


def _ensure_priority6_schema() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        installed = connection.execute(
            "select to_regclass('accounting.seven_by_seven_penalty_evidence')"
        ).fetchone()[0]
        if installed is not None:
            return
        for path in cases._priority6_migrations():
            connection.execute(
                cases._transaction_body(path.read_text(encoding="utf-8"))
            )
            connection.commit()


@pytest.fixture(scope="module", autouse=True)
def _install_priority6_schema() -> None:
    if DATABASE_URL:
        _ensure_priority6_schema()


def _insert_assessment(
    connection,
    *,
    case: dict[str, object],
    through_date,
    amount: Decimal,
    source_transaction_id: UUID,
) -> None:
    connection.execute(
        """
        insert into lending.seven_by_seven_penalty_assessments (
            loan_id, schedule_id, pricing_compliance_review_id,
            terms_fingerprint, assessment_start_date, assessed_through_date,
            opening_penalty_base, calculation_evidence,
            contractual_monthly_rate, legal_rate_ceiling,
            effective_monthly_rate, penalty_proration_days,
            theoretical_penalty_exact, opening_cost_headroom,
            assessed_penalty_amount, source_transaction_id
        ) values (
            %s, %s, %s, %s, %s, %s,
            1000.00, '{}'::jsonb,
            0.030000, 0.030000, 0.030000, 30,
            %s, 5000.00, %s, %s
        )
        """,
        (
            case["loan_id"],
            case["schedule_id"],
            case["review_id"],
            case["fingerprint"],
            through_date,
            through_date,
            amount,
            amount,
            source_transaction_id,
        ),
    )


def _evidence_row(connection, *, loan_id: UUID):
    return connection.execute(
        """
        select
            assessed_penalty,
            penalty_paid,
            penalty_outstanding,
            assessed_through_date,
            ready_to_post
        from accounting.seven_by_seven_penalty_evidence
        where loan_id = %s
        """,
        (loan_id,),
    ).fetchone()


def test_accounting_evidence_rolls_up_assessments_and_ignores_voided_penalty_payment() -> None:
    """The read-only accounting view must reflect evidence, not mutate it.

    Multiple immutable assessments add together. A live penalty-payment allocation
    reduces outstanding penalty, while voiding that source receipt removes only its
    accounting effect; the immutable allocation evidence itself remains present for
    audit. The view stays explicitly not ready to post journals automatically.
    """

    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        case = cases._seed_case(connection, suffix=uuid4().hex[:10])
        first_day = cases.FIRST_PENALTY_DAY

        assessment_source_one = cases._payment(
            connection,
            case=case,
            collection_date=first_day,
            amount=Decimal("1.00"),
            sequence=701,
        )
        assessment_source_two = cases._payment(
            connection,
            case=case,
            collection_date=first_day + timedelta(days=1),
            amount=Decimal("2.00"),
            sequence=702,
        )
        _insert_assessment(
            connection,
            case=case,
            through_date=first_day,
            amount=Decimal("1.00"),
            source_transaction_id=assessment_source_one,
        )
        _insert_assessment(
            connection,
            case=case,
            through_date=first_day + timedelta(days=1),
            amount=Decimal("2.00"),
            source_transaction_id=assessment_source_two,
        )

        penalty_payment = cases._payment(
            connection,
            case=case,
            collection_date=first_day + timedelta(days=2),
            amount=Decimal("1.25"),
            sequence=703,
        )
        connection.execute(
            """
            insert into lending.seven_by_seven_penalty_payment_allocations (
                loan_id, transaction_id, amount_applied
            ) values (%s, %s, 1.25)
            """,
            (case["loan_id"], penalty_payment),
        )

        before_void = _evidence_row(connection, loan_id=case["loan_id"])
        assert before_void == (
            Decimal("3.00"),
            Decimal("1.25"),
            Decimal("1.75"),
            first_day + timedelta(days=1),
            False,
        )

        connection.execute(
            "update lending.collection_transactions set is_voided = true where id = %s",
            (penalty_payment,),
        )

        allocation_evidence = connection.execute(
            """
            select count(*), sum(amount_applied)
            from lending.seven_by_seven_penalty_payment_allocations
            where transaction_id = %s
            """,
            (penalty_payment,),
        ).fetchone()
        assert allocation_evidence == (1, Decimal("1.25"))

        after_void = _evidence_row(connection, loan_id=case["loan_id"])
        assert after_void == (
            Decimal("3.00"),
            Decimal("0.00"),
            Decimal("3.00"),
            first_day + timedelta(days=1),
            False,
        )
        connection.rollback()
