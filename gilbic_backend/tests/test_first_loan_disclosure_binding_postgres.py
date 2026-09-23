"""Task 4 approval binding on the existing guarded disposable database.

These tests consume real Task 3 reviews. No ready flag, approval packet,
source guard, private-file check or financial operation is mocked.
"""

from __future__ import annotations

import inspect
import json
from copy import deepcopy
from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest
import test_first_loan_disclosure_repository_postgres as review_proof
from gilbic_backend.first_loan_repository import (
    FirstLoanAccessDenied,
    FirstLoanConflict,
    PostgresFirstLoanRepository,
)
from gilbic_backend.first_loan_terms import snapshot_digest
from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore

runtime_url = review_proof.runtime_url
connection = review_proof.connection
private_fixture_configuration = review_proof.private_fixture_configuration
pytestmark = review_proof.pytestmark
SOURCE_ARGUMENTS = {
    "disclosure_calculation_id",
    "expected_disclosure_digest",
}


def _require_binding(repository):
    parameters = inspect.signature(repository.approve).parameters
    if not SOURCE_ARGUMENTS.issubset(parameters):
        pytest.fail(
            "R1 Task 4: saved disclosure approval binding is not implemented",
            pytrace=False,
        )


def _setup(connection, monkeypatch, *, complete=True):
    reviews, case = review_proof._setup(connection, monkeypatch)
    payload = review_proof._payload(connection, reviews, case)
    if complete:
        # Precomputed synthetic values exercise binding, not legal EIR proof.
        payload["disclosure_values"] = {
            "amount_financed": "1000.00",
            "amount_financed_reference": "SYNTHETIC support section 3",
            "finance_charge_total": "200.00",
            "finance_charge_reference": "SYNTHETIC support section 4",
            "non_finance_charge_total": "0.00",
            "non_finance_charge_reference": "SYNTHETIC support section 5",
            "effective_interest_rate": "20.0000",
            "effective_interest_rate_reference": "SYNTHETIC support section 6",
            "rate_period": "synthetic contract period",
            "calculation_method": "SYNTHETIC precomputed example only",
        }
    record = review_proof._record(reviews, case, payload)
    assert record["approval_ready"] is complete
    repository = PostgresFirstLoanRepository()
    _require_binding(repository)
    return repository, reviews, case, payload, record


def _arguments(case, record):
    return {
        **review_proof._actor(case),
        "application_version_id": case["app"].id,
        "terms": deepcopy(case["terms"]),
        "template_version": case["template"],
        "request_id": uuid4(),
        "disclosure_calculation_id": UUID(record["id"]),
        "expected_disclosure_digest": record["review_digest"],
    }


def _state(connection):
    audit = connection.execute("select * from core.audit_logs order by id").fetchall()
    return (
        review_proof._business_rows(connection),
        review_proof._state(connection),
        audit,
    )


def _supersede_rule(connection, case, kind):
    current = connection.execute(
        "select * from accounting.v1_tax_rule_evidence where id = %s",
        (case[f"{kind}_rule"],),
    ).fetchone()
    assert current is not None
    connection.execute(
        "select accounting.record_v1_tax_rule_evidence("
        "%s, %s, %s, %s, %s, null, 'exempt', 0, null, "
        "'SYNTHETIC ONLY', 'SYNTHETIC ONLY', 'SYNTHETIC ONLY', %s, "
        "'Synthetic binding regression; not a live tax decision.', %s)",
        (
            case["actor"],
            uuid4(),
            current["tax_type"],
            current["rule_key"],
            current["effective_from"],
            "c" * 64,
            current["id"],
        ),
    )


def test_approval_copies_one_safe_review_without_financial_execution(
    connection, monkeypatch
):
    repository, _, case, _, record = _setup(connection, monkeypatch)
    before = _state(connection)
    result = repository.approve(**_arguments(case, record))
    packet = result["packet"]
    assert packet["schema_version"] == 2
    assert snapshot_digest(packet) == result["packet_hash"]
    binding = packet["tax_disclosure"]
    assert binding["calculation_id"] == record["id"]
    assert binding["review_digest"] == record["review_digest"]
    assert binding["financial_snapshot"] == record["financial_snapshot"]
    serialized = json.dumps(binding)
    for name in (
        "support_base64",
        "support_storage_key",
        "support_section_reference",
        "review_rationale",
        "borrower_charge_basis",
    ):
        assert name not in serialized
    row = connection.execute(
        "select * from lending.loans where id = %s", (result["loan_id"],)
    ).fetchone()
    assert row["status"] == "approved"
    assert row["date_released"] is None and row["due_date"] is None
    assert result["release"] is None
    after = _state(connection)
    allowed = {("lending", "loans"), ("lending", "first_loan_approvals")}
    assert {k: v for k, v in before[0].items() if k not in allowed} == {
        k: v for k, v in after[0].items() if k not in allowed
    }
    assert after[1][0] == before[1][0]
    assert after[1][2] == before[1][2]


@pytest.mark.parametrize("missing", ["both", "id", "digest"])
def test_new_approval_cannot_omit_the_saved_source_pair(
    connection, monkeypatch, missing
):
    repository, _, case, _, record = _setup(connection, monkeypatch)
    arguments = _arguments(case, record)
    if missing in {"both", "id"}:
        arguments.pop("disclosure_calculation_id")
    if missing in {"both", "digest"}:
        arguments.pop("expected_disclosure_digest")
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        repository.approve(**arguments)
    assert _state(connection) == before


@pytest.mark.parametrize("changed", ["id", "digest", "terms", "date"])
def test_changed_binding_or_terms_fail_without_partial_approval(
    connection, monkeypatch, changed
):
    repository, _, case, _, record = _setup(connection, monkeypatch)
    arguments = _arguments(case, record)
    if changed == "id":
        arguments["disclosure_calculation_id"] = uuid4()
    elif changed == "digest":
        arguments["expected_disclosure_digest"] = "0" * 64
    elif changed == "terms":
        arguments["terms"]["account_email"] = "different@example.invalid"
    else:
        for key in ("schedule_basis_date", "first_due_date"):
            original = date.fromisoformat(arguments["terms"][key])
            arguments["terms"][key] = (original + timedelta(days=1)).isoformat()
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        repository.approve(**arguments)
    assert _state(connection) == before


def test_another_valid_application_cannot_consume_the_saved_review(
    connection, monkeypatch
):
    repository, _, _, _, record = _setup(connection, monkeypatch)
    _, _, other, _, _ = _setup(connection, monkeypatch)
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        repository.approve(**_arguments(other, record))
    assert _state(connection) == before


@pytest.mark.parametrize("changed", ["client", "cif", "dst", "grt"])
def test_source_invalidation_after_review_blocks_new_approval(
    connection, monkeypatch, changed
):
    repository, _, case, _, record = _setup(connection, monkeypatch)
    if changed == "client":
        connection.execute(
            "update lending.clients set status = 'inactive' where id = %s",
            (case["client"],),
        )
    elif changed == "cif":
        connection.execute(
            "update lending.client_cif_versions "
            "set reverification_required_at = clock_timestamp(), "
            "reverification_reason = 'Synthetic binding regression' "
            "where id = %s",
            (case["cif"],),
        )
    else:
        _supersede_rule(connection, case, changed)
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        repository.approve(**_arguments(case, record))
    assert _state(connection) == before


@pytest.mark.parametrize("changed", ["missing", "corrupt"])
def test_unavailable_retained_support_blocks_new_approval(
    connection, monkeypatch, changed
):
    repository, _, case, _, record = _setup(connection, monkeypatch)
    row = review_proof._row(connection, record["id"])
    path = PrivateEvidenceStore().root / f"{row['support_storage_key'].hex}.bin"
    if changed == "missing":
        path.unlink()
    else:
        path.write_bytes(path.read_bytes().replace(b"SUPPORT", b"CORRUPT"))
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        repository.approve(**_arguments(case, record))
    assert _state(connection) == before


def test_review_with_missing_disclosure_values_is_not_approval_authority(
    connection, monkeypatch
):
    repository, _, case, _, record = _setup(connection, monkeypatch, complete=False)
    assert "missing_amount_financed" in record["blockers"]
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        repository.approve(**_arguments(case, record))
    assert _state(connection) == before


def test_superseded_review_cannot_approve_even_with_its_original_digest(
    connection, monkeypatch
):
    repository, reviews, case, payload, record = _setup(connection, monkeypatch)
    payload["request_id"] = str(uuid4())
    payload["supersedes_calculation_id"] = record["id"]
    successor = review_proof._record(reviews, case, payload)
    assert successor["version_number"] == record["version_number"] + 1
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        repository.approve(**_arguments(case, record))
    assert _state(connection) == before


def test_identical_approval_retry_survives_later_source_invalidation(
    connection, monkeypatch
):
    repository, _, case, _, record = _setup(connection, monkeypatch)
    arguments = _arguments(case, record)
    original = repository.approve(**arguments)
    connection.execute(
        "update lending.clients set status = 'inactive' where id = %s",
        (case["client"],),
    )
    before = _state(connection)
    replay = repository.approve(**arguments)
    for key in ("loan_id", "packet_id", "packet_hash", "packet"):
        assert replay[key] == original[key]
    assert _state(connection) == before


def test_approval_retry_cannot_substitute_a_different_calculation(
    connection, monkeypatch
):
    repository, _, case, _, record = _setup(connection, monkeypatch)
    arguments = _arguments(case, record)
    repository.approve(**arguments)
    arguments["disclosure_calculation_id"] = uuid4()
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        repository.approve(**arguments)
    assert _state(connection) == before


def test_current_permission_is_required_even_for_a_committed_approval_retry(
    connection, monkeypatch
):
    repository, _, case, _, record = _setup(connection, monkeypatch)
    arguments = _arguments(case, record)
    repository.approve(**arguments)
    review_proof._employee(connection, case)
    before = _state(connection)
    with pytest.raises(FirstLoanAccessDenied):
        repository.approve(**arguments)
    assert _state(connection) == before


def test_balanced_but_unsupported_grt_split_cannot_approve(connection, monkeypatch):
    repository, reviews, case, payload, first = _setup(connection, monkeypatch)
    payload["request_id"] = str(uuid4())
    payload["supersedes_calculation_id"] = first["id"]
    payload["components"].update(
        contractual_interest="195.00", grt_in_repayments="5.00"
    )
    payload["charge_items"] = [
        {
            "item_id": "grt",
            "kind": "grt_recovery",
            "timing": "repayments",
            "amount": "5.00",
            "support_section_reference": "SYNTHETIC blocked component",
        }
    ]
    payload["borrower_charge_basis"]["grt_zero_reason"] = None
    blocked = review_proof._record(reviews, case, payload)
    assert blocked["approval_ready"] is False
    assert "component_integration_required" in blocked["blockers"]
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        repository.approve(**_arguments(case, blocked))
    assert _state(connection) == before
