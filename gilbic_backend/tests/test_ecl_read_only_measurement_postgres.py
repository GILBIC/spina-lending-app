from __future__ import annotations

import json
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
MIGRATIONS = tuple(
    (SQL_ROOT / name).read_text(encoding="utf-8")
    for name in (
        "0070_add_ecl_credit_risk_labels.sql",
        "0071_harden_ecl_cash_recovery_chronology.sql",
        "0072_add_ecl_quantitative_input_readiness.sql",
        "0073_add_ecl_forward_looking_evidence_governance.sql",
        "0074_integrate_ecl_forward_looking_readiness.sql",
        "0075_add_read_only_quantitative_ecl_measurement.sql",
        "0076_harden_read_only_quantitative_ecl_measurement.sql",
    )
)
MANILA = timezone(timedelta(hours=8))


def _transaction_body(source: str) -> str:
    body = source.strip()
    assert body.startswith("BEGIN;")
    assert body.endswith("COMMIT;")
    return body[len("BEGIN;") :].lstrip()[: -len("COMMIT;")].rstrip()


def _actor(connection, suffix: str):
    actor_id = connection.execute(
        """
        INSERT INTO core.users (username, full_name, status)
        VALUES (%s, %s, 'active') RETURNING id
        """,
        (f"ecl-a3-{suffix}", f"ECL A3 Management {suffix}"),
    ).fetchone()[0]
    connection.execute(
        """
        INSERT INTO core.user_roles (user_id, role_id)
        SELECT %s, id FROM core.roles WHERE code = 'management'
        ON CONFLICT DO NOTHING
        """,
        (actor_id,),
    )
    return actor_id


def _loan(connection, *, suffix: str, actor_id, release_date):
    client_id = connection.execute(
        """
        INSERT INTO lending.clients (client_code, full_name, status)
        VALUES (%s, %s, 'active') RETURNING id
        """,
        (f"ECLA3-C-{suffix}", f"ECL A3 Client {suffix}"),
    ).fetchone()[0]
    loan_type_id = connection.execute(
        """
        INSERT INTO lending.loan_types (
            code, name, term_days, calculation_mode, daily_interest_per_1000
        ) VALUES (%s, %s, 120, 'fixed_daily', 0) RETURNING id
        """,
        (f"ECLA3-T-{suffix}", f"ECL A3 Regular {suffix}"),
    ).fetchone()[0]
    loan_id = connection.execute(
        """
        INSERT INTO lending.loans (
            loan_number, client_id, loan_type_id, principal, daily_amount,
            interest_rate, date_released, due_date, status, created_by_user_id
        ) VALUES (
            %s, %s, %s, 5000.00, 50.00, 20.0000,
            %s, %s, 'active', %s
        ) RETURNING id
        """,
        (
            f"ECLA3-L-{suffix}",
            client_id,
            loan_type_id,
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
        SELECT accounting.record_loan_disbursement_evidence(
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
            "A3 protected greenfield release evidence",
        ),
    ).fetchone()[0]


def _prepare_and_post_release(connection, *, event_id, actor_id, token_char: str):
    coordinate = connection.execute(
        """
        SELECT source_event_key, posting_date, fiscal_period_id,
               debit_account_id, credit_account_id, debit_amount
        FROM accounting.loan_disbursement_journal_coordinates
        WHERE disbursement_event_id = %s
          AND coordinate_status = 'coordinate_ready'
        """,
        (event_id,),
    ).fetchone()
    assert coordinate is not None
    preparation_id = connection.execute(
        """
        SELECT accounting.create_new_loan_disbursement_journal_draft(
            %s, %s, %s, %s, %s, %s, %s, %s, %s,
            'new_loan_disbursement_coordinates_v1',
            'new_loan_disbursement_journal_draft_v1'
        )
        """,
        (
            event_id,
            actor_id,
            token_char * 64,
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
        SELECT preparation_id, journal_entry_id, source_event_key,
               draft_review_token, posting_date, fiscal_period_id,
               debit_account_id, credit_account_id, amount,
               total_debit, total_credit, posting_ready
        FROM accounting.loan_disbursement_journal_posting_status
        WHERE preparation_id = %s
        """,
        (preparation_id,),
    ).fetchone()
    assert status is not None and status[-1] is True
    return connection.execute(
        """
        SELECT accounting.post_new_loan_disbursement_journal(
            %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            'new_loan_disbursement_journal_posting_v1'
        )
        """,
        (
            status[0], actor_id, token_char.upper() * 64,
            status[1], status[2], status[3], status[4], status[5],
            status[6], status[7], status[8], status[9], status[10],
        ),
    ).fetchone()[0]


def _register_schedule(connection, *, loan_id, actor_id, release_date, suffix: str):
    schedule_id = connection.execute(
        """
        INSERT INTO lending.loan_contract_schedules (
            loan_id, schedule_version, status, payment_frequency,
            contract_reference, contract_signed_date, effective_from,
            grace_days, settings, created_by_user_id
        ) VALUES (%s, 1, 'active', 'daily', %s, %s, %s, 0, '{}'::jsonb, %s)
        RETURNING id
        """,
        (
            loan_id,
            f"ECLA3-CONTRACT-{suffix}",
            release_date,
            release_date,
            actor_id,
        ),
    ).fetchone()[0]
    connection.execute(
        """
        INSERT INTO lending.loan_contract_installments (
            schedule_id, installment_number, due_date, contractual_amount
        )
        SELECT %s, day_number, %s::date + day_number, 50.00
        FROM generate_series(1, 120) day_number
        """,
        (schedule_id, release_date),
    )
    connection.execute(
        """
        INSERT INTO lending.loan_contract_schedule_registrations (
            schedule_id, evidence_basis, evidence_reference,
            verification_note, verified_by_user_id
        ) VALUES (%s, 'signed_contract', %s, %s, %s)
        """,
        (
            schedule_id,
            f"ECLA3-SIGNED-{suffix}",
            "Verified exact signed contractual cash flows for A3 measurement proof.",
            actor_id,
        ),
    )
    return schedule_id


def _review_stage(connection, *, loan_id, actor_id, stage: str, basis: str, reference: str):
    return connection.execute(
        """
        SELECT accounting.review_ecl_credit_risk_labels(
            %s, %s, false, 'none', 'none', %s, %s, %s,
            false, false, NULL, NULL, NULL, NULL, NULL, %s
        )
        """,
        (
            loan_id,
            stage,
            basis,
            reference,
            "Management reviewed protected evidence for A3 staging and read-only measurement.",
            actor_id,
        ),
    ).fetchone()[0]


def _forward_evidence(connection, *, actor_id, key: str, reference: str):
    return connection.execute(
        """
        SELECT accounting.record_ecl_forward_looking_evidence(
            %s, %s, %s,
            current_date - 30, current_date,
            current_date, current_date + 180,
            clock_timestamp(), current_date,
            %s, %s, NULL
        )
        """,
        (
            key,
            "Authoritative A3 Test Economic Source",
            reference,
            "Management approves this exact retained forward-looking evidence version for the A3 scenario matrix.",
            actor_id,
        ),
    ).fetchone()[0]


def _scenario_payload(*, evidence_ids, release_date, downside_amount="40.00"):
    contractual = [
        {"cash_date": str(release_date + timedelta(days=day)), "amount": 50.00}
        for day in range(1, 121)
    ]
    downside = [
        {"cash_date": str(release_date + timedelta(days=day)), "amount": float(downside_amount)}
        for day in range(1, 121)
    ]
    return [
        {
            "scenario_key": "base",
            "probability": 0.7,
            "evidence_reference": "A3-SCENARIO-BASE",
            "management_rationale": "Protected evidence supports the base expected receipt scenario for this exact measurement date.",
            "forward_evidence_ids": [str(value) for value in evidence_ids],
            "expected_cash_flows": contractual,
        },
        {
            "scenario_key": "downside",
            "probability": 0.3,
            "evidence_reference": "A3-SCENARIO-DOWNSIDE",
            "management_rationale": "Protected evidence supports a lower expected receipt scenario without inventing PD or LGD inputs.",
            "forward_evidence_ids": [str(value) for value in evidence_ids],
            "expected_cash_flows": downside,
        },
    ]


def _measure(connection, *, loan_id, actor_id, scenarios):
    return connection.execute(
        """
        SELECT accounting.record_read_only_quantitative_ecl_measurement(
            %s, current_date, %s::jsonb, %s, %s
        )
        """,
        (
            loan_id,
            json.dumps(scenarios, separators=(",", ":")),
            "Management confirms the exact protected scenario evidence for this read-only A3 measurement.",
            actor_id,
        ),
    ).fetchone()[0]


def test_read_only_ecl_is_stage_aware_deterministic_evidence_backed_and_non_posting() -> None:
    assert DATABASE_URL is not None
    suffix = uuid4().hex[:10]

    with psycopg.connect(DATABASE_URL) as connection:
        if connection.execute(
            "SELECT to_regclass('accounting.ecl_methodology_policy_v1')"
        ).fetchone()[0] is None:
            pytest.skip("0069 ECL methodology/source policy is not installed")

        try:
            for migration in MIGRATIONS:
                connection.execute(_transaction_body(migration))

            assert connection.execute(
                "SELECT count(*) FROM accounting.ecl_quantitative_measurements"
            ).fetchone()[0] == 0

            actor_id = _actor(connection, suffix)
            release_date = connection.execute("SELECT current_date - 1").fetchone()[0]
            connection.execute(
                """
                INSERT INTO accounting.fiscal_periods (label, start_date, end_date, status)
                VALUES (%s, %s, %s, 'open')
                """,
                (f"ECL A3 {suffix}", release_date, release_date + timedelta(days=120)),
            )

            _, loan_id = _loan(
                connection,
                suffix=suffix,
                actor_id=actor_id,
                release_date=release_date,
            )
            event_id = _record_release(
                connection,
                loan_id=loan_id,
                actor_id=actor_id,
                business_date=release_date,
                reference=f"ECLA3-REL-{suffix}",
            )
            _prepare_and_post_release(
                connection,
                event_id=event_id,
                actor_id=actor_id,
                token_char="a",
            )
            _register_schedule(
                connection,
                loan_id=loan_id,
                actor_id=actor_id,
                release_date=release_date,
                suffix=suffix,
            )
            stage1_review = _review_stage(
                connection,
                loan_id=loan_id,
                actor_id=actor_id,
                stage="stage_1_12_month",
                basis="contractual_dpd",
                reference=f"ECLA3-STAGE1-{suffix}",
            )
            evidence_a = _forward_evidence(
                connection,
                actor_id=actor_id,
                key=f"macro-{suffix}",
                reference=f"ECLA3-MACRO-{suffix}",
            )
            evidence_b = _forward_evidence(
                connection,
                actor_id=actor_id,
                key=f"portfolio-{suffix}",
                reference=f"ECLA3-PORTFOLIO-{suffix}",
            )

            gate = connection.execute(
                """
                SELECT quantitative_input_ready, blocker_codes,
                       approved_forward_looking_evidence_ready,
                       account_1190_posting_enabled, automatic_source_posting
                FROM accounting.ecl_quantitative_input_readiness
                WHERE loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert gate == (True, [], True, False, False)

            measurement_history_before = connection.execute(
                """
                SELECT
                    (SELECT count(*) FROM accounting.journal_entries),
                    (SELECT count(*) FROM accounting.journal_lines),
                    (SELECT count(*) FROM core.audit_logs)
                """
            ).fetchone()

            scenarios = _scenario_payload(
                evidence_ids=[evidence_b, evidence_a],
                release_date=release_date,
            )
            first_id = _measure(
                connection,
                loan_id=loan_id,
                actor_id=actor_id,
                scenarios=scenarios,
            )
            first = connection.execute(
                """
                SELECT measurement_version, stage_label, loss_horizon,
                       label_review_id, scenario_count, probability_total,
                       ecl_amount, calculation_policy_version, discount_basis,
                       rounding_policy, calculation_digest, forward_evidence_ids
                FROM accounting.ecl_quantitative_measurements
                WHERE id = %s
                """,
                (first_id,),
            ).fetchone()
            assert first is not None
            assert first[0:6] == (
                1,
                "stage_1_12_month",
                "12_month",
                stage1_review,
                2,
                Decimal("1.000000000000"),
            )
            assert first[6] > 0
            assert first[7:10] == (
                "loan_level_probability_weighted_discounted_cash_shortfall_v1",
                "original_daily_eir_calendar_days_to_measurement_date",
                "numeric_high_precision_final_currency_cent",
            )
            assert len(first[10]) == 64
            assert first[11] == sorted([evidence_a, evidence_b])

            queue = connection.execute(
                """
                SELECT measurement_status, authoritative_ecl_amount,
                       measurement_forward_evidence_current,
                       read_only_ecl_calculation_enabled,
                       account_1190_posting_enabled, automatic_source_posting
                FROM accounting.ecl_quantitative_measurement_queue
                WHERE loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert queue[0] == "measured_read_only"
            assert queue[1] == first[6]
            assert queue[2:] == (True, True, False, False)

            # Same semantic inputs with scenario/evidence/cash-flow ordering
            # changed must return the same immutable measurement and digest.
            retry_scenarios = list(reversed(scenarios))
            for scenario in retry_scenarios:
                scenario["forward_evidence_ids"] = list(
                    reversed(scenario["forward_evidence_ids"])
                )
                scenario["expected_cash_flows"] = list(
                    reversed(scenario["expected_cash_flows"])
                )
            retry_id = _measure(
                connection,
                loan_id=loan_id,
                actor_id=actor_id,
                scenarios=retry_scenarios,
            )
            assert retry_id == first_id
            assert connection.execute(
                "SELECT count(*) FROM accounting.ecl_quantitative_measurements WHERE loan_id = %s",
                (loan_id,),
            ).fetchone()[0] == 1

            # A current qualitative deterioration produces a lifetime-ECL stage;
            # the prior Stage 1 result stays immutable and a new measurement is required.
            stage2_review = _review_stage(
                connection,
                loan_id=loan_id,
                actor_id=actor_id,
                stage="stage_2_lifetime",
                basis="verified_qualitative_credit_event",
                reference=f"ECLA3-STAGE2-{suffix}",
            )
            stale_queue = connection.execute(
                """
                SELECT measurement_status, authoritative_ecl_amount
                FROM accounting.ecl_quantitative_measurement_queue
                WHERE loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert stale_queue == ("new_measurement_required", None)

            lifetime_id = _measure(
                connection,
                loan_id=loan_id,
                actor_id=actor_id,
                scenarios=_scenario_payload(
                    evidence_ids=[evidence_a, evidence_b],
                    release_date=release_date,
                    downside_amount="35.00",
                ),
            )
            lifetime = connection.execute(
                """
                SELECT measurement_version, stage_label, loss_horizon,
                       label_review_id, ecl_amount
                FROM accounting.ecl_quantitative_measurements
                WHERE id = %s
                """,
                (lifetime_id,),
            ).fetchone()
            assert lifetime[0:4] == (2, "stage_2_lifetime", "lifetime", stage2_review)
            assert lifetime[4] > first[6]

            # Direct mutation cannot rewrite an approved calculation snapshot.
            with pytest.raises(psycopg.Error, match="immutable"):
                with connection.transaction():
                    connection.execute(
                        "UPDATE accounting.ecl_quantitative_measurements SET ecl_amount = 0 WHERE id = %s",
                        (first_id,),
                    )

            # If exact forward evidence is revoked, readiness becomes blocked,
            # the prior amount is no longer authoritative and no new measurement can run.
            connection.execute(
                "SELECT accounting.revoke_ecl_forward_looking_evidence(%s, %s, %s)",
                (evidence_a, "A3 test source withdrawn", actor_id),
            )
            blocked_queue = connection.execute(
                """
                SELECT quantitative_input_ready, measurement_status,
                       authoritative_ecl_amount, account_1190_posting_enabled,
                       automatic_source_posting
                FROM accounting.ecl_quantitative_measurement_queue
                WHERE loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            # Evidence B remains globally current so A1+A2 stays ready, but this
            # exact measurement used revoked evidence A and must be remeasured.
            assert blocked_queue == (True, "new_measurement_required", None, False, False)

            connection.execute(
                "SELECT accounting.revoke_ecl_forward_looking_evidence(%s, %s, %s)",
                (evidence_b, "A3 second test source withdrawn", actor_id),
            )
            fully_blocked = connection.execute(
                """
                SELECT quantitative_input_ready, measurement_status,
                       authoritative_ecl_amount
                FROM accounting.ecl_quantitative_measurement_queue
                WHERE loan_id = %s
                """,
                (loan_id,),
            ).fetchone()
            assert fully_blocked == (False, "input_blocked", None)
            with pytest.raises(psycopg.Error, match="input gate is blocked"):
                with connection.transaction():
                    _measure(
                        connection,
                        loan_id=loan_id,
                        actor_id=actor_id,
                        scenarios=scenarios,
                    )

            summary = connection.execute(
                """
                SELECT read_only_ecl_calculation_enabled,
                       account_1190_posting_enabled, automatic_source_posting
                FROM accounting.ecl_quantitative_measurement_summary
                """
            ).fetchone()
            assert summary == (True, False, False)

            after_history = connection.execute(
                """
                SELECT
                    (SELECT count(*) FROM accounting.journal_entries),
                    (SELECT count(*) FROM accounting.journal_lines),
                    (SELECT count(*) FROM core.audit_logs)
                """
            ).fetchone()
            # Compare against the baseline after the protected test loan release
            # was posted. A3 itself may add immutable audit rows but no journal.
            assert after_history[0:2] == measurement_history_before[0:2]
            assert after_history[2] > measurement_history_before[2]
        finally:
            connection.rollback()
