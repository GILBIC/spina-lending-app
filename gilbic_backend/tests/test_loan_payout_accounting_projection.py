"""Review responses expose approved money coordinates, not retained private files."""

import json
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from gilbic_backend.loan_payout_accounting_repository import (
    PostgresLoanPayoutAccountingRepository,
)


@pytest.mark.parametrize("operation", ["review", "read_preparation", "post"])
def test_payout_public_payload_keeps_raw_evidence_private(monkeypatch, operation):
    identity, source_account = (uuid4() for _ in range(2))
    secret = "RAW_PRIVATE_EVIDENCE_MUST_STAY_IN_DATABASE"
    source = {
        "book_id": identity,
        "payout_id": identity,
        "stage": "debit",
        "event_id": identity,
        "treasury_account_id": source_account,
        "posting_date": "2000-01-02",
        "amount": "100.00",
        "fee": "2.00",
        "source_digest": "a" * 64,
        "origin": {"private": secret},
        "evidence": {"sha256": "b" * 64, "private": secret},
        "mapping": {"private": secret},
        "office_evidence": {"private": secret},
        "lines": [
            {
                "line_number": 1,
                "account_code": "1050",
                "debit": "100.00",
                "credit": "0.00",
                "account_snapshot": {
                    "name": "Loan Disbursement Funds in Transit",
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
        "payout_id": identity,
        "stage": "debit",
        "event_id": identity,
        "treasury_account_id": source_account,
        "snapshot": source,
    }

    class Connection:
        def execute(self, statement, values=None):
            if "loan_payout_coordinates" in statement:
                row = {"source": source}
            elif "FROM accounting.loan_payout_accounting_preparations" in statement:
                row = prep
            elif "FROM accounting.loan_payout_accounting_posting_status" in statement:
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

    repo = PostgresLoanPayoutAccountingRepository()
    authorized = []
    monkeypatch.setattr(repo, "_transaction", transaction)
    monkeypatch.setattr(
        repo, "_authorize", lambda conn, actor, account: authorized.append(account)
    )
    monkeypatch.setattr(repo, "_authorize_payout", lambda *args: None)
    monkeypatch.setattr(repo, "_verify_file", lambda raw: raw["evidence"]["sha256"])
    actor = SimpleNamespace(user_id=identity)
    if operation == "review":
        result = repo.review(
            actor,
            payout_id=identity,
            stage="debit",
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
        "name": "Loan Disbursement Funds in Transit"
    }
    if operation != "review":
        assert authorized == [source_account]
        assert result["preparation"]["confirmation_token"] == "c" * 64


@pytest.mark.parametrize("stage,count", [("debit", 1), ("completion", 3)])
def test_payout_review_verifies_each_actual_private_file(stage, count):
    keys = [uuid4() for _ in range(3)]
    calls = []

    class Store:
        def read(self, identity, digest, byte_count):
            calls.append((identity, digest, byte_count))

    source = {
        "stage": stage,
        "evidence": {"id": keys[0], "sha256": "a" * 64, "byte_count": 21},
        "borrower_evidence": {"id": keys[1], "sha256": "b" * 64, "byte_count": 22},
        "office_evidence": {
            "id": uuid4(),
            "request_id": keys[2],
            "content_sha256": "b" * 64,
            "byte_count": 22,
        },
    }
    repo = PostgresLoanPayoutAccountingRepository(
        evidence_store=Store(), office_evidence_store=Store()
    )
    repo._verify_file(source)
    assert (
        calls
        == [(keys[0], "a" * 64, 21), (keys[1], "b" * 64, 22), (keys[2], "b" * 64, 22)][
            :count
        ]
    )


def test_missing_borrower_file_fails_before_office_file_can_substitute():
    from gilbic_backend.office_review_evidence_storage import EvidenceFileError

    missing = uuid4()
    calls = []

    class Store:
        def read(self, identity, digest, byte_count):
            calls.append(identity)
            if identity == missing:
                raise EvidenceFileError("Missing actual borrower receipt")

    debit_file = uuid4()
    repo = PostgresLoanPayoutAccountingRepository(
        evidence_store=Store(), office_evidence_store=Store()
    )
    with pytest.raises(EvidenceFileError, match="borrower receipt"):
        repo._verify_file(
            {
                "stage": "completion",
                "evidence": {"id": debit_file, "sha256": "a" * 64, "byte_count": 21},
                "borrower_evidence": {
                    "id": missing,
                    "sha256": "b" * 64,
                    "byte_count": 22,
                },
                "office_evidence": {
                    "request_id": uuid4(),
                    "content_sha256": "b" * 64,
                    "byte_count": 22,
                },
            }
        )
    assert calls == [debit_file, missing]
