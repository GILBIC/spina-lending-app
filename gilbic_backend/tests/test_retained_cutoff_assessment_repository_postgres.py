"""Real repository SQL, private projection, book binding and live authority."""

from uuid import uuid4

import psycopg
import pytest
from test_financial_statement_snapshot_postgres import (
    isolated_statement_database as _isolated_statement_database,
)
from test_retained_cutoff_assessment_postgres import _seed

from gilbic_backend import retained_cutoff_assessment_repository as repository

isolated_statement_database = _isolated_statement_database


@pytest.fixture
def assessment_repository(monkeypatch, isolated_statement_database):
    url = isolated_statement_database
    with psycopg.connect(url) as setup:
        case = _seed(setup)
    monkeypatch.setattr(repository, "open_connection", lambda: psycopg.connect(url))
    return repository.PostgresRetainedCutoffAssessmentRepository(), case, url


def _candidate(repo, case):
    return repo.load_candidate(
        period_id=case["period"], loan_id=case["loan"], actor_user_id=case["actor"]
    )


def _prepare(repo, case, candidate, **overrides):
    return repo.prepare(
        **(
            {
                "period_id": case["period"],
                "loan_id": case["loan"],
                "actor_user_id": case["actor"],
                "expected_book_id": case["book"],
                "source_digest": candidate["source_digest"],
                "review_rationale": "Actual protected release-day boundary and quantitative measurement reviewed.",
            }
            | overrides
        )
    )


def test_repository_returns_scoped_summary_and_retains_exact_confirmation(
    assessment_repository,
):
    repo, case, _ = assessment_repository
    candidate = _candidate(repo, case)
    assert candidate["ready"] and not candidate["current_confirmation"]
    assert candidate["balances"]["1100"] == "5000.00"
    assert "snapshot" not in candidate and "ledger" not in candidate
    assert "forward_evidence" not in candidate and "scenario_snapshot" not in candidate
    prepared = _prepare(repo, case, candidate)
    confirmation = repo.confirm(
        preparation_id=prepared,
        expected_book_id=case["book"],
        source_digest=candidate["source_digest"],
        actor_user_id=case["actor"],
    )
    current = _candidate(repo, case)
    assert current["current_confirmation"]
    assert current["preparation_id"] == str(prepared)
    assert current["confirmation_id"] == str(confirmation)
    assert current["comprehensive_source_coverage"] is False


def test_repository_rejects_another_book_before_audit_insert(assessment_repository):
    repo, case, url = assessment_repository
    candidate = _candidate(repo, case)
    with pytest.raises(repository.CutoffAssessmentConflict, match="book"):
        _prepare(repo, case, candidate, expected_book_id=uuid4())
    with psycopg.connect(url) as check:
        assert (
            check.execute(
                "SELECT count(*) FROM accounting.loan_period_assessment_preparations"
            ).fetchone()[0]
            == 0
        )


def test_repository_rechecks_membership_before_read_or_confirmation(
    assessment_repository,
):
    repo, case, url = assessment_repository
    candidate = _candidate(repo, case)
    prepared = _prepare(repo, case, candidate)
    with psycopg.connect(url) as change:
        change.execute("DELETE FROM core.user_roles WHERE user_id=%s", (case["actor"],))
    with pytest.raises(repository.CutoffAssessmentDenied):
        _candidate(repo, case)
    with pytest.raises(repository.CutoffAssessmentDenied):
        repo.confirm(
            preparation_id=prepared,
            expected_book_id=case["book"],
            source_digest=candidate["source_digest"],
            actor_user_id=case["actor"],
        )
    with psycopg.connect(url) as check:
        assert (
            check.execute(
                "SELECT count(*) FROM accounting.loan_period_assessment_postings"
            ).fetchone()[0]
            == 0
        )


def test_blocked_candidate_returns_no_money_or_measurement_detail(
    assessment_repository,
):
    repo, case, url = assessment_repository
    with psycopg.connect(url) as change:
        change.execute(
            "UPDATE accounting.fiscal_periods SET end_date=end_date+1 WHERE id=%s",
            (case["period"],),
        )
    candidate = _candidate(repo, case)
    assert not candidate["ready"]
    assert "elapsed_eir_boundary_adapter_required" in candidate["blockers"]
    assert (
        candidate["source_digest"]
        is candidate["measurement"]
        is candidate["balances"]
        is candidate["boundary"]
        is None
    )
