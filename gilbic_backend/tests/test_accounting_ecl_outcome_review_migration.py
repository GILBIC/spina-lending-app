from pathlib import Path


SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0033_add_accounting_ecl_outcome_review.sql"
).read_text(encoding="utf-8")


def test_stage5e3_adds_protected_review_workflow() -> None:
    assert "accounting.ecl.review" in SQL
    assert "CREATE TABLE IF NOT EXISTS accounting.ecl_outcome_label_reviews" in SQL
    assert "CREATE OR REPLACE FUNCTION accounting.review_ecl_historical_outcome" in SQL
    assert "CREATE OR REPLACE VIEW accounting.ecl_outcome_label_review_queue" in SQL
    assert "CREATE OR REPLACE VIEW accounting.ecl_outcome_label_review_summary" in SQL


def test_stage5e3_requires_evidence_and_structurally_usable_source() -> None:
    assert "Evidence reference is required." in SQL
    assert "Review note is required." in SQL
    assert "Source review must be completed before an ECL outcome label can be recorded." in SQL
    assert "ready_for_outcome_labeling" in SQL


def test_stage5e3_keeps_review_history_immutable_and_blocks_direct_label_writes() -> None:
    assert "Historical ECL outcome review records are immutable." in SQL
    assert "Historical ECL outcome labels must use the protected review function." in SQL
    assert "BEFORE UPDATE OF explicit_default_label" in SQL
    assert "supersedes_review_id" in SQL


def test_stage5e3_does_not_auto_label_operational_events() -> None:
    lowered = SQL.lower()
    assert "set explicit_default_label = p_default_label" in lowered
    assert "set explicit_default_label = true" not in lowered
    assert "set explicit_default_label = false" not in lowered
    assert "where outcome_evidence = 'renewed'" not in lowered
    assert "where outcome_evidence = 'deleted'" not in lowered
    assert "where outcome_evidence = 'archived'" not in lowered


def test_stage5e3_requires_all_usable_episodes_to_be_reviewed_before_advancing() -> None:
    assert "outcome_labeling_in_progress" in SQL
    assert "AND episode.explicit_default_label IS NULL" in SQL
    assert "default_outcome_data_required" in SQL
    assert "loss_recovery_labeling_required" in SQL


def test_stage5e3_still_does_not_calculate_or_post_ecl() -> None:
    assert "NULL::numeric(18,2) AS ecl_amount" in SQL
    assert "false AS ecl_included" in SQL
    assert "false AS ready_to_post" in SQL
    assert "INSERT INTO accounting.journal_entries" not in SQL
    assert "post_manual_journal_entry" not in SQL
    assert "UPDATE lending." not in SQL
    assert "DELETE FROM lending." not in SQL
    assert "SET explicit_loss_amount" not in SQL
    assert "SET explicit_recovery_amount" not in SQL
