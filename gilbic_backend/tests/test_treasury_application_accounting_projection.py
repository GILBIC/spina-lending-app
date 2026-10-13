"""Selected-wallet permission cannot disclose other-wallet ledger evidence."""

import json
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from gilbic_backend.treasury_application_accounting_repository import (
    PostgresTreasuryApplicationAccountingRepository,
)

PRIVATE = "PRIVATE_OTHER_WALLET_RECORD_MUST_NOT_LEAVE_REPOSITORY"


@pytest.mark.parametrize("operation", ["review", "read_preparation", "post"])
def test_public_application_payload_excludes_private_cross_wallet_coordinates(
    monkeypatch, operation
):
    identity = uuid4()
    source = {
        "book_id": identity,
        "application_id": identity,
        "transaction_id": identity,
        "receipt_id": identity,
        "event_id": identity,
        "treasury_account_id": identity,
        "loan_id": identity,
        "fiscal_period_id": identity,
        "posting_date": "2000-01-02",
        "source_digest": "a" * 64,
        "amount": "50.00",
        "lines": [
            {
                "line_number": 10,
                "account_code": "1120",
                "debit": "21.00",
                "credit": "0.00",
                "account_snapshot": {
                    "name": "Accrued Interest Receivable",
                    "unexpected_private_field": PRIVATE,
                },
            }
        ],
        "origin": {"private": PRIVATE},
        "measurement": {"private": PRIVATE},
        "evidence": {"sha256": "b" * 64, "private": PRIVATE},
        "ledger_evidence": [PRIVATE],
        "liability_ledger_evidence": [PRIVATE],
        "borrower_liability_balance": PRIVATE,
        "liability_remaining": PRIVATE,
    }
    prep = {
        "id": identity,
        "actor_user_id": identity,
        "request_id": identity,
        "confirmation_token": "c" * 64,
        "source_digest": "a" * 64,
        "book_id": identity,
        "application_id": identity,
        "transaction_id": identity,
        "receipt_id": identity,
        "treasury_account_id": identity,
        "loan_id": identity,
        "snapshot": source,
    }

    class Connection:
        def execute(self, statement, values=None):
            if "treasury_application_coordinates" in statement:
                row = {"source": source}
            elif "FROM accounting.treasury_application_preparations" in statement:
                row = prep
            elif "FROM accounting.treasury_application_posting_status" in statement:
                row = {
                    "exact_posted": True,
                    "correction_pending": False,
                    "journal_entry_id": identity,
                    "unexpected_private_field": PRIVATE,
                }
            else:
                row = {"id": identity}
            return SimpleNamespace(fetchone=lambda: row)

    @contextmanager
    def transaction():
        yield Connection()

    repo = PostgresTreasuryApplicationAccountingRepository()
    monkeypatch.setattr(repo, "_transaction", transaction)
    monkeypatch.setattr(repo, "_authorize", lambda *args: None)
    monkeypatch.setattr(repo, "_application_account", lambda *args: identity)
    monkeypatch.setattr(repo, "_verify_file", lambda raw: raw["evidence"]["sha256"])
    actor = SimpleNamespace(user_id=identity)
    if operation == "review":
        result = repo.review(actor, application_id=identity)
        public = result
    elif operation == "read_preparation":
        result = repo.read_preparation(actor, preparation_id=identity)
        public = result["preparation"]["snapshot"]
    else:
        result = repo.post(
            actor,
            preparation_id=identity,
            source_digest="a" * 64,
            confirmation_token="c" * 64,
        )
        public = result["preparation"]["snapshot"]
    assert PRIVATE not in json.dumps(result, default=str)
    assert public["amount"] == "50.00"
    assert public["lines"][0]["account_snapshot"] == {
        "name": "Accrued Interest Receivable"
    }
    if operation != "review":
        assert result["preparation"]["confirmation_token"] == "c" * 64
