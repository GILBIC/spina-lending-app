from __future__ import annotations

import inspect
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from gilbic_backend.general_journal_api import _visible_general_journal_entry
from gilbic_backend.general_journal_repository import (
    JournalEntry,
    PostgresGeneralJournalRepository,
)


ENTRY_ID = UUID("11111111-1111-4111-8111-111111111111")
PERIOD_ID = UUID("22222222-2222-4222-8222-222222222222")


def entry(*, source_type: str, status: str) -> JournalEntry:
    now = datetime(2026, 8, 9, tzinfo=timezone.utc)
    return JournalEntry(
        entry_id=ENTRY_ID,
        entry_number="JE-1" if status == "posted" else None,
        period_id=PERIOD_ID,
        period_label="August 2026",
        posting_date=date(2026, 8, 8),
        description="Accounting test",
        status=status,
        source_type=source_type,
        source_reference=None,
        reversal_of_entry_id=None,
        created_by_name="Management",
        posted_by_name="Management" if status == "posted" else None,
        created_at=now,
        posted_at=now if status == "posted" else None,
        total_debit=Decimal("100.00"),
        total_credit=Decimal("100.00"),
        lines=(),
    )


def test_protected_opening_balance_draft_is_hidden_from_general_journal_actions() -> None:
    assert _visible_general_journal_entry(
        entry(source_type="opening_balance", status="draft")
    ) is False
    assert _visible_general_journal_entry(
        entry(source_type="opening_balance", status="posted")
    ) is True
    assert _visible_general_journal_entry(entry(source_type="manual", status="draft")) is True


def test_trial_balance_no_longer_excludes_retired_accounts() -> None:
    source = inspect.getsource(PostgresGeneralJournalRepository.trial_balance)
    assert "account.is_active = true" not in source
    assert "journal.status = 'posted'" in source
