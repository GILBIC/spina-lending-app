from __future__ import annotations

import inspect

from gilbic_backend.regular_journal_draft_repository import (
    PostgresRegularJournalDraftRepository,
)


def test_prepare_replays_exact_evidence_before_and_after_source_lock() -> None:
    source = inspect.getsource(PostgresRegularJournalDraftRepository.prepare)

    assert source.count("self._load_exact_bundles") == 2
    assert "regular_journal_draft_review_set_fingerprint" in source
    assert "final_bundles != initial_bundles" in source
    assert "Posting-ready evidence changed during preparation" in source


def test_prepare_serializes_same_loan_and_freezes_every_mutable_replay_source() -> None:
    source = inspect.getsource(PostgresRegularJournalDraftRepository.prepare)

    advisory = 'f"regular-journal-draft-loan:{loan_id}"'
    protected_sources = (
        "lending.loan_collection_state",
        "lending.loans",
        "lending.loan_types",
        "lending.collection_transactions",
        "accounting.opening_balance_workbooks",
        "accounting.opening_balance_journal_preparations",
        "accounting.opening_balance_journal_postings",
        "accounting.opening_balance_loan_snapshot_batches",
        "accounting.opening_balance_loan_measurement_snapshots",
        "accounting.fiscal_periods",
        "accounting.accounts",
        "accounting.journal_entries",
        "accounting.journal_lines",
    )
    final_replay = "final_bundles = self._load_exact_bundles"
    batch_create = "accounting.create_regular_journal_draft_batch"

    assert advisory in source
    assert "pg_advisory_xact_lock" in source
    assert "in share mode" in source.lower()
    assert source.index(advisory) < source.index(final_replay)
    for protected_source in protected_sources:
        assert protected_source in source
        assert source.index(protected_source) < source.index(final_replay)
    assert source.index(final_replay) < source.index(batch_create)


def test_one_database_transaction_creates_the_entire_review_set_all_or_none() -> None:
    source = inspect.getsource(PostgresRegularJournalDraftRepository.prepare)

    transaction = "with open_connection() as connection"
    loop = "for bundle in final_bundles"
    batch_create = "accounting.create_regular_journal_draft_batch"
    integrity_gate = "if not status.draft_integrity_ready"

    assert transaction in source
    assert loop in source
    assert batch_create in source
    assert integrity_gate in source
    assert source.index(transaction) < source.index(loop)
    assert source.index(loop) < source.index(batch_create)
    assert source.index(batch_create) < source.index(integrity_gate)


def test_retry_uses_immutable_preparation_evidence_after_drafts_exist() -> None:
    source = inspect.getsource(PostgresRegularJournalDraftRepository.prepare)

    existing = "existing = self._load_existing_review_set"
    initial_replay = "initial_bundles = self._load_exact_bundles"
    assert existing in source
    assert initial_replay in source
    assert source.index(existing) < source.index(initial_replay)
    assert "if not existing.draft_integrity_ready" in source
    assert "return existing" in source
