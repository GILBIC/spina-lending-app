import json
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from gilbic_backend.collector_liability_accounting_repository import (
    PostgresCollectorLiabilityAccountingRepository,
)


@pytest.mark.parametrize("operation", ["review", "read_preparation", "prepare", "post"])
def test_raw_collector_source_files_and_constituents_stay_private(
    monkeypatch, operation
):
    identity = uuid4()
    sentinel = "PRIVATE_OTHER_SOURCE_AND_FILE_METADATA"
    source = {
        "book_id": identity,
        "source_kind": "settlement",
        "source_id": identity,
        "treasury_account_id": identity,
        "posting_date": "2000-01-02",
        "amount": "110.00",
        "fee": "0.00",
        "source_digest": "a" * 64,
        "source_facts": {"other_wallet": sentinel},
        "evidence": [
            {
                "id": identity,
                "sha256": "d" * 64,
                "byte_count": 12,
                "storage_key": sentinel,
            }
        ],
        "prerequisites": [{"private": sentinel}],
        "mapping_ids": {str(identity): sentinel},
        "lines": [
            {
                "line_number": 1,
                "account_id": identity,
                "account_code": "1010",
                "debit": "110.00",
                "credit": "0.00",
                "account_snapshot": {"private": sentinel},
            }
        ],
    }
    prepared = {
        "id": identity,
        "source_kind": "settlement",
        "source_id": identity,
        "actor_user_id": identity,
        "request_id": identity,
        "source_digest": "a" * 64,
        "confirmation_token": "b" * 64,
        "snapshot": source,
        "private": sentinel,
    }

    class Connection:
        def execute(self, sql, values=None):
            if "collector_liability_coordinates" in sql:
                row = {"source": source}
            elif "FROM accounting.collector_liability_preparations" in sql:
                row = prepared
            elif "FROM accounting.collector_liability_posting_status" in sql:
                row = {
                    "exact_posted": True,
                    "correction_pending": False,
                    "journal_entry_id": identity,
                    "private": sentinel,
                }
            else:
                row = {"id": identity}
            return SimpleNamespace(
                fetchone=lambda: row,
                fetchall=lambda: [{"id": identity, "name": "Cash on Hand"}],
            )

    @contextmanager
    def transaction():
        yield Connection()

    repo = PostgresCollectorLiabilityAccountingRepository()
    authorizations = []
    monkeypatch.setattr(repo, "_transaction", transaction)
    monkeypatch.setattr(
        repo,
        "_authorize_source",
        lambda conn, actor, kind, source_id: authorizations.append((kind, source_id)),
    )
    monkeypatch.setattr(repo, "_verify_files", lambda raw: None)
    actor = SimpleNamespace(user_id=identity)
    if operation == "review":
        result = repo.review(actor, source_kind="settlement", source_id=identity)
        public = result
    elif operation == "read_preparation":
        result = repo.read_preparation(actor, preparation_id=identity)
        public = result["preparation"]["snapshot"]
    elif operation == "prepare":
        result = repo.prepare(
            actor,
            source_kind="settlement",
            source_id=identity,
            source_digest="a" * 64,
            request_id=identity,
        )
        public = result["preparation"]["snapshot"]
    else:
        result = repo.post(
            actor,
            preparation_id=identity,
            source_digest="a" * 64,
            confirmation_token="b" * 64,
        )
        public = result["preparation"]["snapshot"]
    assert sentinel not in json.dumps(result, default=str)
    assert public["amount"] == "110.00" and public["fee"] == "0.00"
    assert public["lines"][0]["account_snapshot"] == {"name": "Cash on Hand"}
    assert authorizations == [("settlement", identity)]
    if operation != "review":
        assert result["preparation"]["confirmation_token"] == "b" * 64


def test_every_retained_file_is_verified_against_bytes():
    seen = []
    store = SimpleNamespace(read=lambda *args: seen.append(args))
    repo = PostgresCollectorLiabilityAccountingRepository(evidence_store=store)
    first, second = uuid4(), uuid4()
    repo._verify_files(
        {
            "evidence": [
                {"id": str(first), "sha256": "a" * 64, "byte_count": 20},
                {"id": str(second), "sha256": "b" * 64, "byte_count": 40},
            ]
        }
    )
    assert seen == [(first, "a" * 64, 20), (second, "b" * 64, 40)]
