"""Review responses expose approved money coordinates, not retained private files."""

import json
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from gilbic_backend.treasury_transfer_accounting_repository import (
    PostgresTreasuryTransferAccountingRepository,
)


@pytest.mark.parametrize("operation", ["review", "read_preparation", "post"])
def test_transfer_public_payload_keeps_raw_evidence_private(monkeypatch, operation):
    identity, source_account, destination_account = (uuid4() for _ in range(3))
    secret = "RAW_PRIVATE_EVIDENCE_MUST_STAY_IN_DATABASE"
    source = {
        "book_id": identity,
        "transfer_id": identity,
        "leg": "source",
        "event_id": identity,
        "source_account_id": source_account,
        "destination_account_id": destination_account,
        "treasury_account_id": source_account,
        "posting_date": "2000-01-02",
        "amount": "100.00",
        "fee": "2.00",
        "source_digest": "a" * 64,
        "origin": {"private": secret},
        "evidence": {"sha256": "b" * 64, "private": secret},
        "source_mapping": {"private": secret},
        "destination_mapping": {"private": secret},
        "lines": [
            {
                "line_number": 1,
                "account_code": "1040",
                "debit": "100.00",
                "credit": "0.00",
                "account_snapshot": {
                    "name": "Transfer Funds in Transit",
                    "private": secret,
                },
            }
        ],
    }
    prep = {
        "id": identity,
        "actor_user_id": identity,
        "request_id": identity,
        "confirmation_token": "c" * 64,
        "source_digest": "a" * 64,
        "book_id": identity,
        "transfer_id": identity,
        "leg": "source",
        "event_id": identity,
        "source_account_id": source_account,
        "destination_account_id": destination_account,
        "snapshot": source,
    }

    class Connection:
        def execute(self, statement, values=None):
            if "treasury_transfer_coordinates" in statement:
                row = {"source": source}
            elif "FROM accounting.treasury_transfer_preparations" in statement:
                row = prep
            elif "FROM accounting.treasury_transfer_posting_status" in statement:
                row = {
                    "exact_posted": True,
                    "correction_pending": False,
                    "journal_entry_id": identity,
                    "private": secret,
                }
            else:
                row = {"id": identity}
            return SimpleNamespace(fetchone=lambda: row)

    @contextmanager
    def transaction():
        yield Connection()

    repo = PostgresTreasuryTransferAccountingRepository()
    authorized = []
    monkeypatch.setattr(repo, "_transaction", transaction)
    monkeypatch.setattr(
        repo, "_authorize", lambda conn, actor, account: authorized.append(account)
    )
    monkeypatch.setattr(repo, "_authorize_transfer", lambda *args: None)
    monkeypatch.setattr(repo, "_verify_file", lambda raw: raw["evidence"]["sha256"])
    actor = SimpleNamespace(user_id=identity)
    if operation == "review":
        result = repo.review(
            actor,
            transfer_id=identity,
            leg="source",
            source_mapping_id=identity,
            destination_mapping_id=identity,
        )
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
    assert secret not in json.dumps(result, default=str)
    assert public["amount"] == "100.00" and public["fee"] == "2.00"
    assert public["lines"][0]["account_snapshot"] == {
        "name": "Transfer Funds in Transit"
    }
    if operation != "review":
        assert authorized == sorted((source_account, destination_account), key=str)
        assert result["preparation"]["confirmation_token"] == "c" * 64
