"""Internal binding guards on real disposable sources, not approval activation.

The owning approve/sign/release integration remains independently required by
its original 21 tests. Synthetic packet rows here exercise only the guard seam.
"""

from copy import deepcopy
from uuid import UUID, uuid4

import pytest
import test_first_loan_disclosure_repository_postgres as review_proof
from gilbic_backend.first_loan_repository import FirstLoanConflict
from gilbic_backend.first_loan_terms import (
    FirstLoanTerms,
    generate_first_loan_schedule,
    schedule_payload,
    snapshot_digest,
)
from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore

from gilbic_backend import first_loan_disclosure_binding as binding
from gilbic_backend import first_loan_disclosure_repository as reviews_module

runtime_url = review_proof.runtime_url
connection = review_proof.connection
private_fixture_configuration = review_proof.private_fixture_configuration
pytestmark = review_proof.pytestmark


def _setup(connection, monkeypatch, *, complete=True):
    reviews, case = review_proof._setup(connection, monkeypatch)
    payload = review_proof._payload(connection, reviews, case)
    if complete:
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
    return reviews, case, payload, record


def _arguments(case, record):
    terms = FirstLoanTerms.model_validate(case["terms"])
    return {
        "calculation_id": UUID(record["id"]),
        "expected_digest": record["review_digest"],
        "application_version_id": case["app"].id,
        "terms": terms,
        "rows": tuple(generate_first_loan_schedule(terms)),
    }


def _require(case, **arguments):
    with reviews_module._transaction(**review_proof._actor(case)) as cursor:
        return binding.require_for_approval(cursor, **arguments)


def _state(connection):
    return (
        review_proof._business_rows(connection),
        review_proof._state(connection),
        connection.execute("select * from core.audit_logs order by id").fetchall(),
    )


def _packet_row(case, record):
    terms = FirstLoanTerms.model_validate(case["terms"])
    row = {
        "id": uuid4(),
        "loan_id": uuid4(),
        "client_id": case["client"],
        "cif_version_id": case["cif"],
        "application_version_id": case["app"].id,
    }
    packet = {
        "schema_version": 2,
        "packet_id": str(row["id"]),
        "loan_id": str(row["loan_id"]),
        "client_id": str(row["client_id"]),
        "cif_version_id": str(row["cif_version_id"]),
        "application": {"id": str(case["app"].id)},
        "terms": terms.model_dump(mode="json"),
        "schedule": schedule_payload(generate_first_loan_schedule(terms)),
        "tax_disclosure": {
            "calculation_id": record["id"],
            "review_digest": record["review_digest"],
            "financial_snapshot": deepcopy(record["financial_snapshot"]),
        },
    }
    return {**row, "packet": packet, "packet_hash": snapshot_digest(packet)}


def test_bound_review_is_safe_exact_and_has_no_persistent_side_effects(
    connection, monkeypatch
):
    _, case, _, record = _setup(connection, monkeypatch)
    before = _state(connection)
    result = _require(case, **_arguments(case, record))
    assert result == {
        "calculation_id": record["id"],
        "review_digest": record["review_digest"],
        "financial_snapshot": record["financial_snapshot"],
    }
    result["financial_snapshot"]["components"]["principal"] = "0.01"
    assert (
        _require(case, **_arguments(case, record))["financial_snapshot"]
        == record["financial_snapshot"]
    )
    assert _state(connection) == before


@pytest.mark.parametrize("change", ["digest", "application", "terms", "rows"])
def test_binding_rejects_different_sources_and_schedule_without_writes(
    connection, monkeypatch, change
):
    _, case, _, record = _setup(connection, monkeypatch)
    arguments = _arguments(case, record)
    if change == "digest":
        arguments["expected_digest"] = "b" * 64
    elif change == "application":
        arguments["application_version_id"] = uuid4()
    elif change == "terms":
        terms = arguments["terms"].model_dump(mode="json")
        terms["account_email"] = "other@example.invalid"
        arguments["terms"] = FirstLoanTerms.model_validate(terms)
    else:
        arguments["rows"] = arguments["rows"][:-1]
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        _require(case, **arguments)
    assert _state(connection) == before


@pytest.mark.parametrize("change", ["inactive_client", "superseded", "missing_file"])
def test_current_source_is_required_even_for_an_intact_saved_review(
    connection, monkeypatch, change
):
    reviews, case, payload, record = _setup(connection, monkeypatch)
    if change == "inactive_client":
        connection.execute(
            "update lending.clients set status = 'inactive' where id = %s",
            (case["client"],),
        )
    elif change == "superseded":
        successor = {
            **payload,
            "request_id": str(uuid4()),
            "supersedes_calculation_id": record["id"],
        }
        review_proof._record(reviews, case, successor)
    else:
        row = review_proof._row(connection, record["id"])
        path = PrivateEvidenceStore().root / f"{row['support_storage_key'].hex}.bin"
        path.unlink()
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        _require(case, **_arguments(case, record))
    assert _state(connection) == before


def test_missing_reviewed_disclosure_values_cannot_be_consumed(connection, monkeypatch):
    _, case, _, record = _setup(connection, monkeypatch, complete=False)
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        _require(case, **_arguments(case, record))
    assert _state(connection) == before


def test_packet_guard_uses_the_exact_saved_financial_snapshot(connection, monkeypatch):
    _, case, _, record = _setup(connection, monkeypatch)
    row = _packet_row(case, record)
    original = deepcopy(row)
    before = _state(connection)
    with reviews_module._transaction(**review_proof._actor(case)) as cursor:
        result = binding.require_packet_source(cursor, row=row)
    assert result == row["packet"]["tax_disclosure"]
    assert row == original
    assert _state(connection) == before


@pytest.mark.parametrize(
    "change", ["financial", "client", "schedule", "hash", "legacy", "schema_float"]
)
def test_changed_or_legacy_packet_is_not_authority_for_a_new_action(
    connection, monkeypatch, change
):
    _, case, _, record = _setup(connection, monkeypatch)
    row = _packet_row(case, record)
    if change == "financial":
        row["packet"]["tax_disclosure"]["financial_snapshot"]["components"][
            "principal"
        ] = "0.01"
    elif change == "client":
        row["packet"]["client_id"] = str(uuid4())
    elif change == "schedule":
        row["packet"]["schedule"][0]["contractual_amount"] = "0.01"
    elif change == "legacy":
        row["packet"]["schema_version"] = 1
        row["packet"].pop("tax_disclosure")
    elif change == "schema_float":
        row["packet"]["schema_version"] = 2.0
    row["packet_hash"] = (
        "b" * 64 if change == "hash" else snapshot_digest(row["packet"])
    )
    original = deepcopy(row)
    before = _state(connection)
    with (
        pytest.raises(FirstLoanConflict),
        reviews_module._transaction(**review_proof._actor(case)) as cursor,
    ):
        binding.require_packet_source(cursor, row=row)
    assert row == original
    assert _state(connection) == before
