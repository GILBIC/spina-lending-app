"""Released schema-one originals, never legacy permission for a new release.

Seed explicit historical records in the existing rollback-only disposable DB.
Do not rewrite a schema-two packet, disable triggers, or bypass a runtime guard.
Synthetic bytes and reviewed fixture terms are not legal/tax acceptance.
"""

from uuid import uuid4

import pytest
import test_first_loan_disclosure_binding_postgres as binding_proof
import test_first_loan_disclosure_repository_postgres as review_proof
from first_loan_approval_fixtures import seed_historical_schema_one_approval
from gilbic_backend.office_review_evidence_storage import (
    EvidenceFileError,
    PrivateEvidenceStore,
)
from psycopg.rows import tuple_row
from psycopg.types.json import Jsonb
from test_first_loan_postgres import PDF, setup

from gilbic_backend import first_loan_repository as owner

runtime_url = review_proof.runtime_url
connection = review_proof.connection
private_fixture_configuration = review_proof.private_fixture_configuration
pytestmark = review_proof.pytestmark


def _historical_release(connection, monkeypatch):
    """Seed a complete retained schema-one release, not execute a new one."""
    _, repository, case = setup(connection, monkeypatch)
    row = seed_historical_schema_one_approval(connection, case)
    terms = owner.FirstLoanTerms.model_validate(row["packet"]["terms"])
    rows = owner.generate_first_loan_schedule(terms)
    document_id, authorization_id, release_id, request_id = (uuid4() for _ in range(4))
    digest = PrivateEvidenceStore().put(document_id, PDF, "application/pdf")
    document = {
        "id": str(document_id),
        "content_sha256": digest,
        "byte_count": len(PDF),
        "pricing_snapshot": {},
    }
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into lending.first_loan_packet_documents("
            "id,loan_id,packet_hash,content_sha256,byte_count,storage_key,"
            "pricing_snapshot,generated_by_user_id) "
            "values(%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                document_id,
                row["loan_id"],
                row["packet_hash"],
                digest,
                len(PDF),
                document_id,
                Jsonb({}),
                case["actor"],
            ),
        )
        cursor.execute(
            "insert into lending.first_loan_authorizations("
            "id,request_id,loan_id,packet_hash,authorized_by_user_id) "
            "values(%s,%s,%s,%s,%s)",
            (
                authorization_id,
                uuid4(),
                row["loan_id"],
                row["packet_hash"],
                case["actor"],
            ),
        )
        evidence = {}
        for purpose, snapshot in (
            ("borrower_contract_signed", owner._sign_snapshot(row, document)),
            (
                "borrower_cash_received",
                owner._cash_snapshot(row, authorization_id, document),
            ),
        ):
            saved = owner.capture_evidence(
                cursor,
                actor_user_id=case["actor"],
                client_id=case["client"],
                cif_version_id=case["cif"],
                application_id=case["app"].application_id,
                application_version_id=case["app"].id,
                purpose=purpose,
                subject_id=row["id"],
                review_snapshot=snapshot,
                content=PDF,
                media_type="application/pdf",
                request_id=uuid4(),
            )
            evidence[purpose] = saved.evidence_reference
        moment = cursor.execute("select clock_timestamp() as t").fetchone()["t"]
        cursor.execute(
            "update lending.loans set status='active',date_released=%s,"
            "due_date=%s where id=%s",
            (terms.schedule_basis_date, rows[-1].due_date, row["loan_id"]),
        )
        contract = evidence["borrower_contract_signed"]
        cash = evidence["borrower_cash_received"]
        with connection.cursor(row_factory=tuple_row) as schedule_cursor:
            schedule_id = owner.register_verified_contract_schedule(
                schedule_cursor,
                loan_id=row["loan_id"],
                payment_frequency=terms.payment_frequency,
                contract_reference=str(row["id"]),
                contract_signed_date=terms.schedule_basis_date,
                effective_from=terms.schedule_basis_date,
                grace_days=terms.grace_days,
                installments=rows,
                evidence_basis="signed_contract",
                evidence_reference=contract,
                verification_note="Synthetic retained schema-one history only",
                verified_by_user_id=case["actor"],
                agreed_daily_payment=None,
                schedule_settings={"first_loan_packet_hash": row["packet_hash"]},
                confirmed=True,
            )
        receipt_reference = f"SYN-HIST-FLR-{release_id.hex}"
        event = cursor.execute(
            "select accounting.record_loan_disbursement_evidence("
            "%s,%s,'new_loan_release',%s,%s,%s,0,%s,'cash_office',%s,%s) as id",
            (
                row["loan_id"],
                case["actor"],
                terms.schedule_basis_date,
                moment,
                terms.net_cash,
                terms.total_deductions,
                receipt_reference,
                "Synthetic retained schema-one history only",
            ),
        ).fetchone()
        loan = cursor.execute(
            "select loan_number from lending.loans where id=%s", (row["loan_id"],)
        ).fetchone()
        receipt = {
            "receipt_reference": receipt_reference,
            "loan_id": str(row["loan_id"]),
            "loan_number": loan["loan_number"],
            "client_id": str(case["client"]),
            "borrower_name": row["packet"]["borrower"]["full_name"],
            "packet_id": str(row["id"]),
            "packet_hash": row["packet_hash"],
            "gross_principal": str(terms.principal),
            "deductions": str(terms.total_deductions),
            "actual_cash_received": str(terms.net_cash),
            "released_at": moment.isoformat(),
            "management_authorizer_id": str(case["actor"]),
            "releasing_staff_id": str(case["actor"]),
            "contract_evidence_reference": contract,
            "cash_evidence_reference": cash,
        }
        cursor.execute(
            "insert into lending.first_loan_releases("
            "id,request_id,loan_id,authorization_id,packet_hash,"
            "contract_evidence_reference,cash_evidence_reference,cash_amount,"
            "receipt_reference,schedule_id,disbursement_event_id,"
            "released_by_user_id,released_device_id,released_at,receipt) "
            "values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                release_id,
                request_id,
                row["loan_id"],
                authorization_id,
                row["packet_hash"],
                contract,
                cash,
                terms.net_cash,
                receipt_reference,
                schedule_id,
                event["id"],
                case["actor"],
                case["device"],
                moment,
                Jsonb(receipt),
            ),
        )
        cursor.execute(
            "insert into lending.loan_collection_state(loan_id,remaining_balance) "
            "values(%s,%s)",
            (row["loan_id"], sum(item.contractual_amount for item in rows)),
        )
        cursor.execute(
            "insert into lending.first_loan_credential_intents("
            "client_id,loan_id,release_id,email,requested_by_user_id) "
            "values(%s,%s,%s,%s,%s)",
            (
                case["client"],
                row["loan_id"],
                release_id,
                terms.account_email,
                case["actor"],
            ),
        )
        # Prove the historical fixture is complete without committing test data
        # or disabling the deferred release-integrity constraint.
        cursor.execute("set constraints all immediate")
    arguments = {
        **review_proof._actor(case),
        "loan_id": row["loan_id"],
        "packet_hash": row["packet_hash"],
        "authorization_id": authorization_id,
        "contract_evidence_reference": contract,
        "cash_evidence_reference": cash,
        "cash_amount": str(terms.net_cash),
        "borrower_confirmed": True,
        "request_id": request_id,
    }
    calculations = connection.execute(
        "select count(*) as n from lending.first_loan_disclosure_calculations "
        "where application_version_id=%s",
        (case["app"].id,),
    ).fetchone()
    assert calculations["n"] == 0
    return repository, case, row, document_id, arguments


def _read_arguments(case, row):
    return {**review_proof._actor(case), "loan_id": row["loan_id"]}


@pytest.mark.parametrize("change", ("client", "template", "cif"))
def test_released_schema_one_original_and_replay_survive_current_source_change(
    connection, monkeypatch, change
):
    repository, case, row, _, arguments = _historical_release(connection, monkeypatch)
    read = _read_arguments(case, row)
    original = repository.get(**read)
    document = repository.packet_document(**read)
    assert original["packet"] == row["packet"]
    assert original["packet"]["schema_version"] == 1
    assert "tax_disclosure" not in original["packet"]
    assert owner.snapshot_digest(original["packet"]) == row["packet_hash"]
    assert document[1] == PDF
    if change == "client":
        connection.execute(
            "update lending.clients set status='inactive' where id=%s",
            (case["client"],),
        )
    elif change == "template":
        connection.execute(
            "update lending.first_loan_document_templates set is_active=false where version=%s",
            (case["template"],),
        )
    else:
        connection.execute(
            "update lending.client_cif_versions "
            "set reverification_required_at=clock_timestamp(), "
            "reverification_reason=%s where id=%s",
            ("Synthetic historical readback proof", case["cif"]),
        )
    before = binding_proof._state(connection)
    assert repository.get(**read) == original
    assert repository.packet_document(**read) == document
    assert repository.release(**arguments) == original
    assert repository.release(**arguments) == original
    assert binding_proof._state(connection) == before


@pytest.mark.parametrize(
    "field",
    (
        "request_id",
        "authorization_id",
        "packet_hash",
        "cash_amount",
        "contract_evidence_reference",
        "cash_evidence_reference",
    ),
)
def test_released_schema_one_replay_rejects_changed_request_without_side_effects(
    connection, monkeypatch, field
):
    repository, _, _, _, arguments = _historical_release(connection, monkeypatch)
    changed = dict(arguments)
    if field in {"request_id", "authorization_id"}:
        changed[field] = uuid4()
    elif field == "packet_hash":
        changed[field] = "0" * 64
    elif field == "cash_amount":
        changed[field] = "999.99"
    else:
        changed[field] = f"office-evidence:{uuid4()}"
    before = binding_proof._state(connection)
    with pytest.raises(owner.FirstLoanConflict):
        repository.release(**changed)
    assert binding_proof._state(connection) == before


@pytest.mark.parametrize("change", ("device", "actor"))
def test_released_schema_one_history_still_requires_current_access(
    connection, monkeypatch, change
):
    repository, case, row, _, arguments = _historical_release(connection, monkeypatch)
    if change == "device":
        connection.execute(
            "update core.devices set status='revoked' where id=%s",
            (case["device"],),
        )
    else:
        connection.execute(
            "update core.users set status='inactive' where id=%s", (case["actor"],)
        )
    before = binding_proof._state(connection)
    for action, payload in (
        (repository.get, _read_arguments(case, row)),
        (repository.packet_document, _read_arguments(case, row)),
        (repository.release, arguments),
    ):
        with pytest.raises(owner.FirstLoanAccessDenied):
            action(**payload)
    assert binding_proof._state(connection) == before


@pytest.mark.parametrize("damage", ("missing", "corrupt"))
def test_released_schema_one_missing_original_is_not_regenerated(
    connection, monkeypatch, damage
):
    repository, case, row, storage_key, arguments = _historical_release(
        connection, monkeypatch
    )
    original = repository.get(**_read_arguments(case, row))
    path = PrivateEvidenceStore().root / f"{storage_key.hex}.bin"
    if damage == "missing":
        path.unlink()
    else:
        path.write_bytes(PDF.replace(b"SYNTHETIC", b"CORRUPTED"))
    before = binding_proof._state(connection)
    with pytest.raises(EvidenceFileError):
        repository.packet_document(**_read_arguments(case, row))
    # Reading a committed cash receipt is not permission to regenerate a PDF.
    assert repository.release(**arguments) == original
    assert binding_proof._state(connection) == before
