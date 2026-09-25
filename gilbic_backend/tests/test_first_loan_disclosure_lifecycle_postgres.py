"""Task 4 lifecycle consumers on the existing guarded disposable database.

Use real source reviews and the owning first-loan methods. No readiness flag,
source guard, immutable packet or financial operation is replaced. Synthetic
support and PDF bytes here are not legal-template or tax-policy acceptance.
"""

from copy import deepcopy
from uuid import UUID, uuid4

import pytest
import test_first_loan_disclosure_binding_postgres as binding_proof
import test_first_loan_disclosure_repository_postgres as review_proof
from first_loan_approval_fixtures import seed_historical_schema_one_approval
from gilbic_backend.first_loan_repository import (
    FirstLoanAccessDenied,
    FirstLoanConflict,
)
from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore
from test_first_loan_postgres import PDF, setup

runtime_url = review_proof.runtime_url
connection = review_proof.connection
private_fixture_configuration = review_proof.private_fixture_configuration
pytestmark = review_proof.pytestmark
STAGES = ("generate", "sign", "authorize", "cash", "release")


def _prepare(connection, monkeypatch, stage):
    """Stop immediately before one NEW action with its real prerequisites."""
    repository, reviews, case, payload, calculation = binding_proof._setup(
        connection, monkeypatch
    )
    approval = repository.approve(**binding_proof._arguments(case, calculation))
    common = {
        **review_proof._actor(case),
        "loan_id": UUID(approval["loan_id"]),
        "packet_hash": approval["packet_hash"],
    }
    context = {
        "repository": repository,
        "reviews": reviews,
        "case": case,
        "payload": payload,
        "calculation": calculation,
        "approval": approval,
        "common": common,
    }
    arguments = {**common, "content": PDF, "expected_pricing_snapshot": {}}
    if stage == "generate":
        return context, repository.register_packet_document, arguments
    repository.register_packet_document(**arguments)

    arguments = {
        **common,
        "purpose": "borrower_contract_signed",
        "witnessed_wet_signature": True,
        "content": PDF,
        "media_type": "application/pdf",
        "request_id": uuid4(),
    }
    if stage == "sign":
        return context, repository.capture, arguments
    contract = repository.capture(**arguments)

    arguments = {**common, "request_id": uuid4()}
    if stage == "authorize":
        return context, repository.authorize_release, arguments
    authorization = repository.authorize_release(**arguments)
    authorization_id = UUID(authorization["authorization_id"])
    arguments = {
        **common,
        "purpose": "borrower_cash_received",
        "content": PDF,
        "media_type": "application/pdf",
        "request_id": uuid4(),
        "authorization_id": authorization_id,
    }
    if stage == "cash":
        return context, repository.capture, arguments
    cash = repository.capture(**arguments)
    assert stage == "release"
    return context, repository.release, {
        **common,
        "authorization_id": authorization_id,
        "contract_evidence_reference": contract["evidence_reference"],
        "cash_evidence_reference": cash["evidence_reference"],
        "cash_amount": approval["packet"]["net_cash"],
        "borrower_confirmed": True,
        "request_id": uuid4(),
    }


def _invalidate(connection, context, change):
    case = context["case"]
    if change == "client":
        connection.execute(
            "update lending.clients set status = 'inactive' where id = %s",
            (case["client"],),
        )
    elif change in {"missing", "corrupt"}:
        row = review_proof._row(connection, context["calculation"]["id"])
        path = PrivateEvidenceStore().root / f"{row['support_storage_key'].hex}.bin"
        if change == "missing":
            path.unlink()
        else:
            path.write_bytes(path.read_bytes().replace(b"SUPPORT", b"CORRUPT"))
    elif change in {"dst", "grt"}:
        binding_proof._supersede_rule(connection, case, change)
    else:
        assert change == "review"
        payload = deepcopy(context["payload"])
        payload["request_id"] = str(uuid4())
        payload["supersedes_calculation_id"] = context["calculation"]["id"]
        successor = review_proof._record(context["reviews"], case, payload)
        assert (
            successor["version_number"]
            == context["calculation"]["version_number"] + 1
        )
        assert successor["id"] != context["calculation"]["id"]


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("change", ("missing", "corrupt", "dst", "grt", "review"))
def test_new_lifecycle_action_rejects_unusable_disclosure_without_side_effects(
    connection, monkeypatch, stage, change
):
    context, action, arguments = _prepare(connection, monkeypatch, stage)
    _invalidate(connection, context, change)
    before = binding_proof._state(connection)
    with pytest.raises(FirstLoanConflict):
        action(**arguments)
    # Includes full financial/business rows, retained reviews, audits and bytes.
    assert binding_proof._state(connection) == before


@pytest.mark.parametrize("stage", STAGES)
@pytest.mark.parametrize("change", ("client", "missing", "review"))
def test_committed_lifecycle_retry_preserves_original_after_source_invalidation(
    connection, monkeypatch, stage, change
):
    context, action, arguments = _prepare(connection, monkeypatch, stage)
    original = action(**arguments)
    _invalidate(connection, context, change)
    before = binding_proof._state(connection)
    replay = action(**arguments)
    assert replay == original
    assert binding_proof._state(connection) == before


@pytest.mark.parametrize("stage", STAGES)
def test_committed_lifecycle_retry_still_requires_current_device_authorization(
    connection, monkeypatch, stage
):
    context, action, arguments = _prepare(connection, monkeypatch, stage)
    action(**arguments)
    connection.execute(
        "update core.devices set status = 'revoked' where id = %s",
        (context["case"]["device"],),
    )
    before = binding_proof._state(connection)
    with pytest.raises(FirstLoanAccessDenied):
        action(**arguments)
    assert binding_proof._state(connection) == before


@pytest.mark.parametrize("stage", STAGES)
def test_committed_lifecycle_retry_cannot_change_its_packet_identity(
    connection, monkeypatch, stage
):
    _, action, arguments = _prepare(connection, monkeypatch, stage)
    action(**arguments)
    changed = {**arguments, "packet_hash": "0" * 64}
    before = binding_proof._state(connection)
    with pytest.raises(FirstLoanConflict):
        action(**changed)
    assert binding_proof._state(connection) == before


@pytest.mark.parametrize("stage", ("generate", "sign", "cash", "release"))
def test_committed_retry_cannot_replace_bytes_or_amount_after_support_loss(
    connection, monkeypatch, stage
):
    context, action, arguments = _prepare(connection, monkeypatch, stage)
    action(**arguments)
    _invalidate(connection, context, "missing")
    changed = dict(arguments)
    if stage == "release":
        changed["cash_amount"] = "999.99"
    else:
        changed["content"] = PDF.replace(b"SYNTHETIC", b"DIFFERENT")
    before = binding_proof._state(connection)
    # Capture owns its existing evidence-conflict type; it must still reject.
    from gilbic_backend.office_review_evidence_repository import (
        OfficeReviewEvidenceConflict,
    )

    with pytest.raises((FirstLoanConflict, OfficeReviewEvidenceConflict)):
        action(**changed)
    assert binding_proof._state(connection) == before


def test_released_packet_original_bytes_survive_loss_of_calculation_support(
    connection, monkeypatch
):
    context, release, arguments = _prepare(connection, monkeypatch, "release")
    original = release(**arguments)
    repository = context["repository"]
    read_arguments = {
        **review_proof._actor(context["case"]),
        "loan_id": arguments["loan_id"],
    }
    metadata, content = repository.packet_document(**read_arguments)
    assert content == PDF
    _invalidate(connection, context, "missing")
    before = binding_proof._state(connection)
    assert repository.packet_document(**read_arguments) == (metadata, content)
    assert repository.get(**read_arguments)["packet"] == original["packet"]
    assert release(**arguments)["release"] == original["release"]
    assert binding_proof._state(connection) == before


def test_new_generation_rejects_unreleased_historical_schema_one_without_backfill(
    connection, monkeypatch
):
    _, repository, case = setup(connection, monkeypatch)
    historical = seed_historical_schema_one_approval(connection, case)
    assert historical["packet"]["schema_version"] == 1
    assert "tax_disclosure" not in historical["packet"]
    before = binding_proof._state(connection)
    with pytest.raises(FirstLoanConflict):
        repository.register_packet_document(
            **review_proof._actor(case),
            loan_id=historical["loan_id"],
            packet_hash=historical["packet_hash"],
            content=PDF,
            expected_pricing_snapshot={},
        )
    assert binding_proof._state(connection) == before


def test_cancellation_remains_available_after_disclosure_support_loss(
    connection, monkeypatch
):
    context, _, _ = _prepare(connection, monkeypatch, "generate")
    _invalidate(connection, context, "missing")
    repository = context["repository"]
    arguments = {
        **context["common"],
        "reason": "Synthetic cancellation for revised disclosure",
        "request_id": uuid4(),
    }
    result = repository.cancel_approval(**arguments)
    assert result["status"] == "cancelled"
    assert result["packet"] == context["approval"]["packet"]
    before = binding_proof._state(connection)
    assert repository.cancel_approval(**arguments) == result
    assert binding_proof._state(connection) == before


def test_authorization_revocation_remains_available_after_disclosure_support_loss(
    connection, monkeypatch
):
    context, authorize, arguments = _prepare(connection, monkeypatch, "authorize")
    authorization = authorize(**arguments)
    _invalidate(connection, context, "missing")
    repository = context["repository"]
    revoke_arguments = {
        **review_proof._actor(context["case"]),
        "loan_id": context["common"]["loan_id"],
        "authorization_id": UUID(authorization["authorization_id"]),
        "reason": "Synthetic revocation for revised disclosure",
        "request_id": uuid4(),
    }
    result = repository.revoke_release(**revoke_arguments)
    assert result["revocation_id"]
    before = binding_proof._state(connection)
    assert repository.revoke_release(**revoke_arguments) == result
    assert binding_proof._state(connection) == before
