"""Actual repository transactions retain historical measurements and exact cents."""

from uuid import uuid4

import psycopg
import pytest
from gilbic_backend.elapsed_period_assessment_repository import (
    PostgresElapsedPeriodAssessmentRepository,
)
from gilbic_backend.retained_cutoff_assessment_repository import (
    CutoffAssessmentConflict,
    CutoffAssessmentDenied,
)
from test_elapsed_period_assessment_postgres import _risk, _scenarios, _seed
from test_financial_statement_snapshot_postgres import (
    isolated_statement_database as _isolated_statement_database,
)

from gilbic_backend import retained_cutoff_assessment_repository as shared

isolated_statement_database = _isolated_statement_database


def _case(url, monkeypatch):
    with psycopg.connect(url) as conn:
        f = _seed(conn)
    monkeypatch.setattr(shared, "open_connection", lambda: psycopg.connect(url))
    return f, PostgresElapsedPeriodAssessmentRepository()


def _values(f, candidate):
    scenarios = _scenarios(f)
    for scenario in scenarios:
        scenario["probability"] = str(scenario["probability"])
        for receipt in scenario["expected_cash_flows"]:
            receipt["amount"] = format(receipt["amount"], ".2f")
    return {
        "period_id": f["period"],
        "loan_id": f["loan"],
        "actor_user_id": f["actor"],
        "expected_book_id": f["book"],
        "source_digest": candidate["source_digest"],
        "risk_review": _risk(f),
        "scenarios": scenarios,
        "review_rationale": "Reviewed original timing, actual cutoff sources and retained historical scenarios.",
    }


def test_repository_retains_historical_calculation_and_posts_exact_review(
    isolated_statement_database, monkeypatch
):
    f, repository = _case(isolated_statement_database, monkeypatch)
    scope = {
        "period_id": f["period"],
        "loan_id": f["loan"],
        "actor_user_id": f["actor"],
    }
    candidate = repository.load_candidate(**scope)
    assert candidate["ready"] and candidate["eir"]["cumulative_interest"] == "110.02"
    assert (
        "snapshot" not in candidate
        and candidate["comprehensive_source_coverage"] is False
    )
    prepared = repository.prepare(**_values(f, candidate))
    assert prepared["as_of_date"] == f["cutoff"].isoformat()
    assert prepared["calculated_at"].startswith(f["today"].isoformat())
    assert prepared["incremental_interest"] == "110.02"
    assert (
        prepared["review_inputs"]["risk_review"] == _values(f, candidate)["risk_review"]
    )
    assert prepared["review_inputs"]["scenarios"] == _values(f, candidate)["scenarios"]
    assert "source_snapshot" not in prepared and "measurement_snapshot" not in prepared
    values = {
        "preparation_id": prepared["preparation_id"],
        "expected_book_id": f["book"],
        "confirmation_digest": prepared["confirmation_digest"],
        "actor_user_id": f["actor"],
    }
    posted = repository.confirm(**values)
    assert repository.confirm(**values) == posted
    assert repository.load_candidate(**scope)["current_confirmation"] is True
    assert (
        repository.load_candidate(**scope)["preparation"]["review_inputs"]
        == prepared["review_inputs"]
    )


def test_repository_rechecks_book_and_live_actor_without_creating_audits(
    isolated_statement_database, monkeypatch
):
    f, repository = _case(isolated_statement_database, monkeypatch)
    scope = {
        "period_id": f["period"],
        "loan_id": f["loan"],
        "actor_user_id": f["actor"],
    }
    values = _values(f, repository.load_candidate(**scope))
    with pytest.raises(CutoffAssessmentConflict, match="book"):
        repository.prepare(**(values | {"expected_book_id": uuid4()}))
    with psycopg.connect(isolated_statement_database) as conn:
        conn.execute(
            "UPDATE core.users SET status='inactive' WHERE id=%s", (f["actor"],)
        )
    with pytest.raises(CutoffAssessmentDenied):
        repository.load_candidate(**scope)
    with pytest.raises(CutoffAssessmentDenied):
        repository.prepare(**values)
    with psycopg.connect(isolated_statement_database) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM accounting.loan_elapsed_assessment_preparations"
            ).fetchone()[0]
            == 0
        )
