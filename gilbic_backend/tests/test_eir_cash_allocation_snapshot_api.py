from __future__ import annotations

from datetime import date
from uuid import UUID

from gilbic_backend.eir_cash_allocation_api import _pack_payload
from gilbic_backend.eir_cash_allocation_repository import EirCashAllocationPack


LOAN_ID = UUID("11111111-1111-4111-8111-111111111111")


def test_api_exposes_protected_snapshot_reconciliation_state() -> None:
    payload = _pack_payload(
        EirCashAllocationPack(
            loan_id=LOAN_ID,
            loan_number="L-001",
            client_name="Synthetic Borrower",
            cutover_date=date(2026, 8, 8),
            opening_balance_prepared=True,
            opening_balance_posted=True,
            opening_balance_entry_number="JE-202608-00000001",
            source_event_count=0,
            source_history_complete=True,
            blocker_code=None,
            blocker_message=None,
            allocation=None,
            protected_snapshot_available=True,
            protected_snapshot_reconciled=True,
            protected_snapshot_blocker=None,
        )
    )

    assert payload["opening_balance_prepared"] is True
    assert payload["opening_balance_posted"] is True
    assert payload["protected_snapshot_available"] is True
    assert payload["protected_snapshot_reconciled"] is True
    assert payload["protected_snapshot_blocker"] is None
    assert payload["automatic_source_posting_enabled"] is False
