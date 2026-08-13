from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0069_add_ecl_methodology_source_policy.sql"
)


def _database_url() -> str:
    value = os.getenv("GILBIC_TEST_DATABASE_URL", "").strip()
    if not value:
        pytest.skip("GILBIC_TEST_DATABASE_URL is not configured")
    return value


def _history_counts(connection: psycopg.Connection) -> tuple[int, int, int, int]:
    return tuple(
        int(value)
        for value in connection.execute(
            """
            SELECT
                (SELECT count(*) FROM accounting.ecl_historical_loan_episodes),
                (SELECT count(*) FROM accounting.ecl_outcome_label_reviews),
                (SELECT count(*) FROM accounting.journal_entries),
                (SELECT count(*) FROM accounting.journal_lines)
            """
        ).fetchone()
    )


def test_ecl_methodology_source_policy_is_fail_closed_and_history_neutral() -> None:
    assert MIGRATION.is_file()
    with psycopg.connect(_database_url(), autocommit=True) as connection:
        before = _history_counts(connection)
        connection.execute(MIGRATION.read_text(encoding="utf-8"))
        after = _history_counts(connection)
        assert after == before

        policy = connection.execute(
            """
            SELECT
                policy_version,
                methodology_approved,
                measurement_method,
                discount_rate_basis,
                probability_weighted_outcomes_required,
                time_value_of_money_required,
                forward_looking_information_required,
                pd_lgd_parameter_model_required,
                numeric_pd_enabled,
                numeric_lgd_enabled,
                numeric_cure_rate_enabled,
                numeric_recovery_rate_enabled,
                scenario_weights_enabled,
                automatic_staging_enabled,
                ecl_calculation_enabled,
                account_1190_posting_enabled,
                automatic_source_posting
            FROM accounting.ecl_methodology_policy_v1
            """
        ).fetchone()
        assert policy == (
            "ecl_methodology_v1",
            True,
            "probability_weighted_discounted_expected_cash_shortfall",
            "original_effective_interest_rate",
            True,
            True,
            True,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            False,
        )

        source_rows = connection.execute(
            """
            SELECT source_order, source_class, approved_for_v1_methodology
            FROM accounting.ecl_approved_source_classes_v1
            ORDER BY source_order
            """
        ).fetchall()
        assert len(source_rows) == 8
        assert all(bool(row[2]) for row in source_rows)
        assert [row[1] for row in source_rows] == [
            "verified_contractual_cash_flows",
            "original_eir_and_carrying_evidence",
            "protected_collection_history",
            "contractual_dpd_and_qualitative_credit_risk_evidence",
            "historical_loan_episode_dataset",
            "management_reviewed_default_outcomes",
            "protected_loss_recovery_writeoff_evidence",
            "authoritative_forward_looking_economic_evidence",
        ]

        readiness = connection.execute(
            """
            SELECT
                methodology_source_status,
                methodology_policy_approved,
                protected_loss_recovery_evidence_ready,
                forward_looking_evidence_ready,
                staging_automation_enabled,
                quantitative_ecl_ready,
                ecl_calculation_enabled,
                account_1190_posting_enabled,
                automatic_source_posting
            FROM accounting.ecl_methodology_source_readiness
            """
        ).fetchone()
        assert readiness is not None
        assert readiness[0] in {
            "historical_dataset_required",
            "historical_source_review_required",
            "historical_outcome_review_required",
            "default_outcome_evidence_required",
            "protected_loss_recovery_evidence_required",
        }
        assert readiness[1] is True
        assert readiness[2:] == (False, False, False, False, False, False, False)
