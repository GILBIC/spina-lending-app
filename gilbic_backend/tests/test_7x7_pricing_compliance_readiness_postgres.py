from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

SQL_0117 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0117_add_7x7_pricing_compliance_readiness.sql"
).read_text(encoding="utf-8")


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    body = body[len("BEGIN;") :].lstrip()
    return body[: -len("COMMIT;")].rstrip()


def test_exact_term_pricing_compliance_review_is_append_only_and_fail_closed() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]
    ready_fingerprint = "a" * 64
    changed_fingerprint = "b" * 64

    with psycopg.connect(DATABASE_URL) as connection:
        try:
            connection.execute(_transaction_body(SQL_0117))
            actor_id = connection.execute(
                """
                insert into core.users (username, full_name, status)
                values (%s, %s, 'active') returning id
                """,
                (f"x7-ready-{suffix}", f"7x7 Readiness Reviewer {suffix}"),
            ).fetchone()[0]
            client_id = connection.execute(
                """
                insert into lending.clients (client_code, full_name, status)
                values (%s, %s, 'active') returning id
                """,
                (f"X7-RDY-C-{suffix}", f"7x7 Readiness Client {suffix}"),
            ).fetchone()[0]
            loan_type_id = connection.execute(
                """
                insert into lending.loan_types (
                    code, name, term_days, calculation_mode,
                    daily_interest_per_1000, settings
                ) values (%s, %s, 60, 'seven_by_seven', 7.00, '{}'::jsonb)
                returning id
                """,
                (f"X7-RDY-{suffix}", f"7x7 Readiness {suffix}"),
            ).fetchone()[0]
            loan_id = connection.execute(
                """
                insert into lending.loans (
                    loan_number, client_id, loan_type_id, principal, daily_amount,
                    date_released, due_date, status, created_by_user_id
                ) values (%s, %s, %s, 3000.00, 50.00, %s, %s, 'active', %s)
                returning id
                """,
                (
                    f"X7-RDY-L-{suffix}",
                    client_id,
                    loan_type_id,
                    date(2093, 1, 1),
                    date(2093, 4, 15),
                    actor_id,
                ),
            ).fetchone()[0]

            first_review_id = connection.execute(
                """
                insert into lending.seven_by_seven_pricing_compliance_reviews (
                    loan_id, terms_fingerprint,
                    applicability_review_ready, pricing_cap_review_ready,
                    disclosure_ready, total_cost_cap_review_ready,
                    evidence_reference, review_note, reviewed_by_user_id
                ) values (%s, %s, true, true, true, true, %s, %s, %s)
                returning id
                """,
                (
                    loan_id,
                    ready_fingerprint,
                    f"X7-RDY-EVIDENCE-{suffix}",
                    "Exact proposed terms reviewed and all readiness evidence is complete.",
                    actor_id,
                ),
            ).fetchone()[0]

            connection.execute("savepoint immutable_review")
            with pytest.raises(psycopg.Error):
                connection.execute(
                    """
                    update lending.seven_by_seven_pricing_compliance_reviews
                    set disclosure_ready = false
                    where id = %s
                    """,
                    (first_review_id,),
                )
            connection.execute("rollback to savepoint immutable_review")

            connection.execute(
                """
                insert into lending.seven_by_seven_pricing_compliance_reviews (
                    loan_id, terms_fingerprint,
                    applicability_review_ready, pricing_cap_review_ready,
                    disclosure_ready, total_cost_cap_review_ready,
                    evidence_reference, review_note, reviewed_by_user_id
                ) values (%s, %s, true, true, false, true, %s, %s, %s)
                """,
                (
                    loan_id,
                    ready_fingerprint,
                    f"X7-RDY-REVIEW-{suffix}",
                    "A newer exact-term review marks disclosure readiness unresolved.",
                    actor_id,
                ),
            )
            connection.execute(
                """
                insert into lending.seven_by_seven_pricing_compliance_reviews (
                    loan_id, terms_fingerprint,
                    applicability_review_ready, pricing_cap_review_ready,
                    disclosure_ready, total_cost_cap_review_ready,
                    evidence_reference, review_note, reviewed_by_user_id
                ) values (%s, %s, true, true, true, true, %s, %s, %s)
                """,
                (
                    loan_id,
                    changed_fingerprint,
                    f"X7-RDY-CHANGED-{suffix}",
                    "Different proposed terms require and receive their own exact-term review.",
                    actor_id,
                ),
            )

            latest_same_terms = connection.execute(
                """
                select applicability_review_ready, pricing_cap_review_ready,
                       disclosure_ready, total_cost_cap_review_ready
                from lending.seven_by_seven_pricing_compliance_reviews
                where loan_id = %s and terms_fingerprint = %s
                order by reviewed_at desc, id desc
                limit 1
                """,
                (loan_id, ready_fingerprint),
            ).fetchone()
            assert latest_same_terms == (True, True, False, True)

            different_terms_count = connection.execute(
                """
                select count(*)
                from lending.seven_by_seven_pricing_compliance_reviews
                where loan_id = %s and terms_fingerprint = %s
                """,
                (loan_id, changed_fingerprint),
            ).fetchone()[0]
            assert different_terms_count == 1
        finally:
            connection.rollback()
