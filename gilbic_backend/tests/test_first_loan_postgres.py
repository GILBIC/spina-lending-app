"""First-loan operations use only the guarded disposable onboarding database."""

from contextlib import contextmanager
from datetime import timedelta
from importlib import import_module
from uuid import uuid4
from uuid import UUID
import hashlib
import json

import pytest
from psycopg.types.json import Jsonb

from test_client_cif_review_confirmation_postgres import (
    DATABASE_URL,
    connection as connection,
    runtime_url as runtime_url,
)
from test_loan_application_repository_postgres import _seed, _repository, _create
from test_loan_application_review_confirmation_postgres import (
    _complete_information,
    _insert_direct,
)
from test_first_loan_terms import values

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)

PDF = b"%PDF-1.4\nSYNTHETIC EVIDENCE ONLY\n%%EOF"


@pytest.fixture(autouse=True)
def private_fixture_configuration(monkeypatch, tmp_path):
    from gilbic_backend.privacy_record_repository import REQUIRED_FACTS

    monkeypatch.setenv("GILBIC_OFFICE_REVIEW_EVIDENCE_ROOT", str(tmp_path / "evidence"))
    pdf = tmp_path / "synthetic.pdf"
    pdf.write_bytes(PDF)
    manifest = tmp_path / "privacy.json"
    manifest.write_text(
        json.dumps(
            {
                "approved_for_issuance": True,
                "facts": {key: "Synthetic " + key for key in REQUIRED_FACTS},
                "notice": {
                    "version": "SYNTHETIC-NOTICE",
                    "sha256": hashlib.sha256(PDF).hexdigest(),
                    "path": str(pdf),
                },
                "consent": {
                    "version": "SYNTHETIC-CONSENT",
                    "sha256": hashlib.sha256(PDF).hexdigest(),
                    "path": str(pdf),
                },
            }
        )
    )
    monkeypatch.setenv("GILBIC_PRIVACY_PACKAGE_MANIFEST", str(manifest))


def setup(connection, monkeypatch):
    try:
        module = import_module("gilbic_backend.first_loan_repository")
    except ModuleNotFoundError:
        pytest.fail(
            "First-loan transactional repository is not implemented", pytrace=False
        )
    case = _seed(connection, "management")
    device = uuid4()
    connection.execute(
        "insert into core.devices(id,user_id,device_identifier_hash,platform) values(%s,%s,%s,'web')",
        (device, case["actor"], uuid4().hex),
    )
    case["device"] = device
    connection.execute(
        "update lending.clients set status='active' where id=%s", (case["client"],)
    )
    connection.execute(
        "update lending.client_cif_versions set status='active',baseline_liveness_status='passed',baseline_face_scan_evidence_reference='SYNTHETIC-FACE',activated_at=now(),expires_at=now()+interval '5 years',review_due_at=now()+interval '5 years'-interval '90 days' where id=%s",
        (case["cif"],),
    )
    from gilbic_backend.office_review_evidence_repository import (
        capture_evidence,
        cif_review_snapshot,
        application_review_snapshot,
    )
    from gilbic_backend.privacy_record_repository import build_privacy_context

    cif_information = dict(
        connection.execute(
            "select full_name,phone_number,email,present_address from lending.client_cif_versions where id=%s",
            (case["cif"],),
        ).fetchone()
    )
    with connection.cursor() as cursor:
        cif_evidence = capture_evidence(
            cursor,
            actor_user_id=case["actor"],
            client_id=case["client"],
            cif_version_id=case["cif"],
            purpose="cif_review",
            subject_id=case["cif"],
            review_snapshot=cif_review_snapshot(
                client_id=case["client"],
                cif_version_id=case["cif"],
                information=cif_information,
            ),
            content=PDF,
            media_type="application/pdf",
            request_id=uuid4(),
        )
        privacy = build_privacy_context(
            cursor, client_id=case["client"], cif_version_id=case["cif"]
        )
        privacy_evidence = capture_evidence(
            cursor,
            actor_user_id=case["actor"],
            client_id=case["client"],
            cif_version_id=case["cif"],
            purpose="privacy_acknowledgment",
            subject_id=case["cif"],
            review_snapshot=privacy["review_snapshot"],
            content=PDF,
            media_type="application/pdf",
            request_id=uuid4(),
        )
    connection.execute(
        "insert into lending.client_cif_review_confirmations(client_id,cif_version_id,review_cycle_number,review_snapshot,applicant_confirmation_evidence_reference,witnessed_by_user_id) values(%s,%s,1,%s,%s,%s)",
        (
            case["client"],
            case["cif"],
            Jsonb(cif_information),
            cif_evidence.evidence_reference,
            case["actor"],
        ),
    )
    app = _create(
        _repository(connection, monkeypatch),
        case,
        f"SYN-{uuid4().hex}",
        information=_complete_information(),
    )
    with connection.cursor() as cursor:
        evidence = capture_evidence(
            cursor,
            actor_user_id=case["actor"],
            client_id=case["client"],
            cif_version_id=case["cif"],
            application_id=app.application_id,
            application_version_id=app.id,
            purpose="application_review",
            subject_id=app.id,
            review_snapshot=application_review_snapshot(
                client_id=case["client"],
                cif_version_id=case["cif"],
                application_id=app.application_id,
                application_version_id=app.id,
                information=app.information.model_dump(mode="json"),
                cif_information=cif_information,
            ),
            content=PDF,
            media_type="application/pdf",
            request_id=uuid4(),
        )
    _insert_direct(
        connection,
        app,
        case["actor"],
        applicant_confirmation_evidence_reference=evidence.evidence_reference,
    )
    connection.execute(
        "insert into lending.client_privacy_acknowledgments(client_id,cif_version_id,notice_version,notice_sha256,consent_version,consent_sha256,optional_service_communications,evidence_id,review_snapshot,acknowledged_by_user_id) values(%s,%s,%s,%s,%s,%s,false,%s,%s,%s)",
        (
            case["client"],
            case["cif"],
            "SYNTHETIC-NOTICE",
            hashlib.sha256(PDF).hexdigest(),
            "SYNTHETIC-CONSENT",
            hashlib.sha256(PDF).hexdigest(),
            privacy_evidence.id,
            Jsonb(privacy["review_snapshot"]),
            case["actor"],
        ),
    )
    product = connection.execute(
        "select id from lending.loan_types where calculation_mode in ('fixed_daily','fixed_total') and is_active limit 1"
    ).fetchone()
    if not product:
        product = connection.execute(
            "insert into lending.loan_types(code,name,term_days,calculation_mode) values(%s,'Synthetic Regular',12,'fixed_daily') returning id",
            (f"SYN-{uuid4().hex}",),
        ).fetchone()
    today = connection.execute(
        "select (clock_timestamp() at time zone 'Asia/Manila')::date as d"
    ).fetchone()["d"]
    data = values()
    data.update(
        loan_type_id=str(product["id"]),
        schedule_basis_date=today.isoformat(),
        first_due_date=(today + timedelta(days=1)).isoformat(),
    )
    template = f"SYNTHETIC-{uuid4().hex}"
    connection.execute(
        "insert into lending.first_loan_document_templates(version,content_sha256,approved_for_execution) values(%s,%s,true)",
        (template, "a" * 64),
    )

    @contextmanager
    def acquire():
        with connection.transaction():
            yield connection

    monkeypatch.setattr(module, "open_connection", acquire)
    case.update(app=app, terms=data, template=template)
    return module, module.PostgresFirstLoanRepository(), case


def approve(repository, case, **changes):
    return repository.approve(
        **dict(
            actor_user_id=case["actor"],
            registered_device_id=case["device"],
            application_version_id=case["app"].id,
            terms=case["terms"],
            template_version=case["template"],
            request_id=uuid4(),
            **changes,
        )
    )


def counts(connection):
    return {
        table: connection.execute(
            f"select count(*) as n from lending.{table}"
        ).fetchone()["n"]
        for table in (
            "loans",
            "loan_contract_schedules",
            "loan_disbursement_events",
            "first_loan_releases",
            "first_loan_credential_intents",
        )
    }


def test_approval_keeps_real_dates_null_and_has_no_schedule_cash_or_credentials(
    connection, monkeypatch
):
    module, repository, case = setup(connection, monkeypatch)
    before = counts(connection)
    request_id = uuid4()
    record = repository.approve(
        actor_user_id=case["actor"],
        registered_device_id=case["device"],
        application_version_id=case["app"].id,
        terms=case["terms"],
        template_version=case["template"],
        request_id=request_id,
    )
    loan = connection.execute(
        "select * from lending.loans where id=%s", (record["loan_id"],)
    ).fetchone()
    assert loan["status"] == "approved"
    assert loan["date_released"] is None and loan["due_date"] is None
    after = counts(connection)
    assert after == {**before, "loans": before["loans"] + 1}
    assert record["packet"]["application"]["id"] == str(case["app"].id)
    assert record["packet_hash"] == module.snapshot_digest(record["packet"])
    retry = repository.approve(
        actor_user_id=case["actor"],
        registered_device_id=case["device"],
        application_version_id=case["app"].id,
        terms=case["terms"],
        template_version=case["template"],
        request_id=request_id,
    )
    assert retry["loan_id"] == record["loan_id"]
    assert counts(connection) == after


@pytest.mark.parametrize(
    "change",
    [
        "employee",
        "collector",
        "device_revoked",
        "permission_removed",
        "inactive_cif",
        "expired_cif",
        "reverification",
        "unconfirmed",
        "superseded_application",
    ],
)
def test_approval_rechecks_exact_persisted_authority_and_current_confirmed_sources(
    connection, monkeypatch, change
):
    module, repository, case = setup(connection, monkeypatch)
    if change in ("employee", "collector"):
        connection.execute(
            "delete from core.user_roles where user_id=%s", (case["actor"],)
        )
        connection.execute(
            "insert into core.user_roles select %s,id from core.roles where code=%s",
            (case["actor"], change),
        )
    elif change == "device_revoked":
        connection.execute(
            "update core.devices set status='revoked' where id=%s", (case["device"],)
        )
    elif change == "permission_removed":
        connection.execute(
            "delete from core.role_permissions where permission_code='lending.first_loan.approve'"
        )
    elif change == "inactive_cif":
        connection.execute(
            "update lending.client_cif_versions set status='superseded',is_current=false where id=%s",
            (case["cif"],),
        )
    elif change == "expired_cif":
        connection.execute(
            "update lending.client_cif_versions set activated_at=now()-interval '6 years',expires_at=now()-interval '1 year',review_due_at=now()-interval '1 year 90 days' where id=%s",
            (case["cif"],),
        )
    elif change == "reverification":
        connection.execute(
            "update lending.client_cif_versions set reverification_required_at=now(),reverification_reason='Synthetic review' where id=%s",
            (case["cif"],),
        )
    elif change == "unconfirmed":
        # A fresh unconfirmed version is selected; immutable confirmation is never deleted.
        apprepo = _repository(connection, monkeypatch)
        case["app"] = apprepo.append_draft(
            actor_user_id=case["actor"],
            client_id=case["client"],
            application_id=case["app"].application_id,
            cif_version_id=case["cif"],
            expected_version_number=1,
            information=_complete_information("4000.00"),
        )
    else:
        _repository(connection, monkeypatch).append_draft(
            actor_user_id=case["actor"],
            client_id=case["client"],
            application_id=case["app"].application_id,
            cif_version_id=case["cif"],
            expected_version_number=1,
            information=_complete_information("4000.00"),
        )
    before = counts(connection)
    with pytest.raises(module.FirstLoanError):
        approve(repository, case)
    assert counts(connection) == before


def test_unapproved_template_never_authorizes_signing_or_release(
    connection, monkeypatch
):
    module, repository, case = setup(connection, monkeypatch)
    connection.execute(
        "update lending.first_loan_document_templates set approved_for_execution=false where version=%s",
        (case["template"],),
    )
    record = approve(repository, case)
    with pytest.raises(module.FirstLoanConflict):
        repository.authorize_release(
            actor_user_id=case["actor"],
            registered_device_id=case["device"],
            loan_id=record["loan_id"],
            packet_hash=record["packet_hash"],
            request_id=uuid4(),
        )
    assert (
        connection.execute(
            "select count(*) as n from lending.first_loan_authorizations"
        ).fetchone()["n"]
        == 0
    )


def test_approved_terms_and_snapshots_are_immutable(connection, monkeypatch):
    _, repository, case = setup(connection, monkeypatch)
    record = approve(repository, case)
    import psycopg

    with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
        connection.execute(
            "update lending.first_loan_approvals set packet='{}' where loan_id=%s",
            (record["loan_id"],),
        )
    with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
        connection.execute(
            "update lending.loans set principal=principal+1 where id=%s",
            (record["loan_id"],),
        )


def ready(repository, case):
    record = approve(repository, case)
    args = {
        "actor_user_id": case["actor"],
        "registered_device_id": case["device"],
        "loan_id": UUID(record["loan_id"]),
        "packet_hash": record["packet_hash"],
    }
    repository.register_packet_document(
        **args, content=PDF, expected_pricing_snapshot={}
    )
    authorization = repository.authorize_release(**args, request_id=uuid4())
    authorization_id = UUID(authorization["authorization_id"])
    contract = repository.capture(
        **args,
        purpose="borrower_contract_signed",
        witnessed_wet_signature=True,
        content=PDF,
        media_type="application/pdf",
        request_id=uuid4(),
    )
    cash = repository.capture(
        **args,
        purpose="borrower_cash_received",
        content=PDF,
        media_type="application/pdf",
        request_id=uuid4(),
        authorization_id=authorization_id,
    )
    return record, {
        **args,
        "authorization_id": authorization_id,
        "contract_evidence_reference": contract["evidence_reference"],
        "cash_evidence_reference": cash["evidence_reference"],
        "cash_amount": "1000.00",
        "borrower_confirmed": True,
        "request_id": uuid4(),
    }


def test_complete_release_is_one_atomic_financial_transition_with_one_credential_intent(
    connection, monkeypatch
):
    _, repository, case = setup(connection, monkeypatch)
    record, args = ready(repository, case)
    before = counts(connection)
    auth_before = connection.execute("select count(*) as n from auth.users").fetchone()[
        "n"
    ]
    result = repository.release(**args)
    assert result["status"] == "released"
    after = counts(connection)
    assert after == {
        **before,
        **{
            key: before[key] + 1
            for key in (
                "loan_contract_schedules",
                "loan_disbursement_events",
                "first_loan_releases",
                "first_loan_credential_intents",
            )
        },
    }
    loan = connection.execute(
        "select * from lending.loans where id=%s", (record["loan_id"],)
    ).fetchone()
    assert (
        loan["status"] == "active"
        and loan["date_released"].isoformat() == case["terms"]["schedule_basis_date"]
    )
    assert result["release"]["receipt"]["actual_cash_received"] == "1000.00"
    assert result["credential_intent"]["status"] == "pending"
    assert (
        connection.execute("select count(*) as n from auth.users").fetchone()["n"]
        == auth_before
    )
    assert repository.release(**args)["release"] == result["release"]
    assert counts(connection) == after


@pytest.mark.parametrize(
    "field,value",
    [
        ("cash_amount", "999.99"),
        ("borrower_confirmed", False),
        ("packet_hash", "0" * 64),
        ("authorization_id", None),
        ("contract_evidence_reference", "free-typed"),
        ("cash_evidence_reference", "free-typed"),
    ],
)
def test_invalid_handoff_leaves_approval_without_partial_cash_schedule_or_intent(
    connection, monkeypatch, field, value
):
    module, repository, case = setup(connection, monkeypatch)
    record, args = ready(repository, case)
    before = counts(connection)
    args[field] = value
    from gilbic_backend.office_review_evidence_repository import (
        OfficeReviewEvidenceConflict,
    )

    with pytest.raises((module.FirstLoanConflict, OfficeReviewEvidenceConflict)):
        repository.release(**args)
    assert counts(connection) == before
    assert connection.execute(
        "select status,date_released from lending.loans where id=%s",
        (record["loan_id"],),
    ).fetchone() == {"status": "approved", "date_released": None}


def test_revoked_authorization_and_future_release_basis_block_handoff(
    connection, monkeypatch
):
    module, repository, case = setup(connection, monkeypatch)
    record, args = ready(repository, case)
    repository.revoke_release(
        actor_user_id=case["actor"],
        registered_device_id=case["device"],
        loan_id=args["loan_id"],
        authorization_id=args["authorization_id"],
        reason="Synthetic cancelled handoff",
        request_id=uuid4(),
    )
    before = counts(connection)
    with pytest.raises(module.FirstLoanConflict):
        repository.release(**args)
    assert counts(connection) == before


def test_failure_after_schedule_creation_rolls_back_entire_release(
    connection, monkeypatch
):
    module, repository, case = setup(connection, monkeypatch)
    record, args = ready(repository, case)
    before = counts(connection)
    connection.execute(
        "update accounting.accounts set is_active=false where system_key='cash_office'"
    )
    import psycopg

    with pytest.raises(psycopg.Error):
        repository.release(**args)
    assert counts(connection) == before
    assert connection.execute(
        "select status,date_released from lending.loans where id=%s",
        (record["loan_id"],),
    ).fetchone() == {"status": "approved", "date_released": None}


def test_missing_or_tampered_packet_pdf_blocks_signing(connection, monkeypatch):
    module, repository, case = setup(connection, monkeypatch)
    record = approve(repository, case)
    args = {
        "actor_user_id": case["actor"],
        "registered_device_id": case["device"],
        "loan_id": UUID(record["loan_id"]),
        "packet_hash": record["packet_hash"],
    }
    with pytest.raises(module.FirstLoanConflict):
        repository.capture(
            **args,
            purpose="borrower_contract_signed",
            witnessed_wet_signature=True,
            content=PDF,
            media_type="application/pdf",
            request_id=uuid4(),
        )

    document = repository.register_packet_document(
        **args, content=PDF, expected_pricing_snapshot={}
    )
    from gilbic_backend.office_review_evidence_storage import (
        PrivateEvidenceStore,
        EvidenceFileError,
    )

    (PrivateEvidenceStore().root / f"{UUID(document['id']).hex}.bin").write_bytes(
        b"CORRUPTED"
    )
    with pytest.raises(EvidenceFileError):
        repository.capture(
            **args,
            purpose="borrower_contract_signed",
            witnessed_wet_signature=True,
            content=PDF,
            media_type="application/pdf",
            request_id=uuid4(),
        )


def test_resumed_review_reads_exact_recorded_evidence_and_new_authorization_invalidates_cash(
    connection, monkeypatch
):
    module, repository, case = setup(connection, monkeypatch)
    record, args = ready(repository, case)
    read = repository.get(
        actor_user_id=case["actor"],
        registered_device_id=case["device"],
        loan_id=args["loan_id"],
    )
    assert (
        read["evidence"]["borrower_contract_signed"]["evidence_reference"]
        == args["contract_evidence_reference"]
    )
    assert (
        read["evidence"]["borrower_cash_received"]["evidence_reference"]
        == args["cash_evidence_reference"]
    )
    new = repository.authorize_release(
        actor_user_id=case["actor"],
        registered_device_id=case["device"],
        loan_id=args["loan_id"],
        packet_hash=args["packet_hash"],
        request_id=uuid4(),
    )
    read = repository.get(
        actor_user_id=case["actor"],
        registered_device_id=case["device"],
        loan_id=args["loan_id"],
    )
    assert read["authorization"]["id"] == new["authorization_id"]
    assert "borrower_cash_received" not in read["evidence"]
    with pytest.raises(module.FirstLoanConflict):
        repository.release(**args)


def test_unreleased_first_loan_cannot_use_generic_schedule_or_fake_activation(
    connection, monkeypatch
):
    import psycopg

    _, repository, case = setup(connection, monkeypatch)
    record = approve(repository, case)
    with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
        connection.execute(
            "insert into lending.loan_contract_schedules(loan_id,schedule_version,payment_frequency,contract_reference,effective_from) values(%s,1,'daily','SYNTHETIC',current_date)",
            (record["loan_id"],),
        )
    with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
        connection.execute(
            "update lending.loans set status='active',date_released=current_date,due_date=current_date+12 where id=%s",
            (record["loan_id"],),
        )
        connection.execute(
            "set constraints lending.first_loan_release_transition immediate"
        )


def test_client_first_payment_projection_uses_exact_verified_stored_schedule(
    connection, monkeypatch
):
    _, repository, case = setup(connection, monkeypatch)
    record, args = ready(repository, case)
    connection.execute(
        "update lending.clients set user_id=%s where id=%s",
        (case["actor"], case["client"]),
    )
    from gilbic_backend import client_loan_repository as reader

    @contextmanager
    def acquire():
        with connection.transaction():
            yield connection

    monkeypatch.setattr(reader, "open_connection", acquire)
    assert (
        reader.PostgresClientLoanRepository()
        .list_for_user(user_id=case["actor"])
        .loans[0]
        .first_payment_date
        is None
    )
    repository.release(**args)
    loan = (
        reader.PostgresClientLoanRepository()
        .list_for_user(user_id=case["actor"])
        .loans[0]
    )
    assert (
        loan.first_payment_date.isoformat()
        == record["packet"]["schedule"][0]["due_date"]
    )


def test_signature_requires_witness_declaration_at_repository_boundary(
    connection, monkeypatch
):
    module, repository, case = setup(connection, monkeypatch)
    record = approve(repository, case)
    with pytest.raises(module.FirstLoanConflict):
        repository.capture(
            actor_user_id=case["actor"],
            registered_device_id=case["device"],
            loan_id=UUID(record["loan_id"]),
            packet_hash=record["packet_hash"],
            purpose="borrower_contract_signed",
            content=PDF,
            media_type="application/pdf",
            request_id=uuid4(),
        )


def test_generic_disbursement_cannot_record_unreleased_or_void_completed_first_loan(
    connection, monkeypatch
):
    from datetime import datetime, timezone
    from decimal import Decimal
    from gilbic_backend import loan_disbursement_evidence_repository as generic

    _, repository, case = setup(connection, monkeypatch)
    record, args = ready(repository, case)

    @contextmanager
    def acquire():
        with connection.transaction():
            yield connection

    monkeypatch.setattr(generic, "open_connection", acquire)
    with pytest.raises(generic.LoanDisbursementEvidenceConflict):
        generic.PostgresLoanDisbursementEvidenceRepository().record(
            actor_user_id=case["actor"],
            loan_id=args["loan_id"],
            event_kind="new_loan_release",
            business_date=datetime.now(timezone.utc).date(),
            disbursed_at=datetime.now(timezone.utc),
            cash_disbursed_amount=Decimal("1000.00"),
            settlement_amount=Decimal("0"),
            other_deduction_amount=Decimal("0"),
            funding_account_system_key="cash_office",
            external_reference="SYNTHETIC",
            evidence_note="Synthetic",
        )
    repository.release(**args)
    event = connection.execute(
        "select disbursement_event_id from lending.first_loan_releases where loan_id=%s",
        (args["loan_id"],),
    ).fetchone()
    with pytest.raises(generic.LoanDisbursementEvidenceConflict):
        generic.PostgresLoanDisbursementEvidenceRepository().void(
            actor_user_id=case["actor"],
            event_id=event["disbursement_event_id"],
            reason="Synthetic incompatible partial reversal",
        )


def test_employee_can_release_exact_packet_witnessed_by_another_office_staff(
    connection, monkeypatch
):
    _, repository, case = setup(connection, monkeypatch)
    record, args = ready(repository, case)
    employee = _seed(connection, "employee")
    device = uuid4()
    connection.execute(
        "insert into core.devices(id,user_id,device_identifier_hash,platform) values(%s,%s,%s,'web')",
        (device, employee["actor"], uuid4().hex),
    )
    office = {
        "actor_user_id": employee["actor"],
        "registered_device_id": device,
        "loan_id": args["loan_id"],
    }
    read = repository.get(**office)
    assert (
        read["evidence"]["borrower_contract_signed"]["evidence_reference"]
        == args["contract_evidence_reference"]
    )
    assert "borrower_cash_received" not in read["evidence"]
    cash = repository.capture(
        **office,
        packet_hash=args["packet_hash"],
        authorization_id=args["authorization_id"],
        purpose="borrower_cash_received",
        content=PDF,
        media_type="application/pdf",
        request_id=uuid4(),
    )
    result = repository.release(
        **{**args, **office, "cash_evidence_reference": cash["evidence_reference"]}
    )
    assert result["status"] == "released"
    assert result["release"]["receipt"]["releasing_staff_id"] == str(employee["actor"])


def seven_review(connection, module, record, case, *, ceiling="0.050000"):
    from decimal import Decimal
    from types import SimpleNamespace

    terms = module.FirstLoanTerms.model_validate(case["terms"])
    fingerprint = module.build_7x7_pricing_compliance_terms_fingerprint(
        context=SimpleNamespace(
            loan_id=UUID(record["loan_id"]),
            principal=terms.principal,
            daily_interest_per_1000=terms.daily_interest_per_1000,
        ),
        payment_frequency="daily",
        contract_reference=record["packet_id"],
        contract_signed_date=terms.schedule_basis_date,
        effective_from=terms.schedule_basis_date,
        grace_days=terms.grace_days,
        agreed_daily_payment=terms.installment_amount,
        installments=module.generate_first_loan_schedule(terms),
    )
    connection.execute(
        """insert into lending.seven_by_seven_pricing_compliance_reviews(loan_id,terms_fingerprint,applicability_review_ready,pricing_cap_review_ready,disclosure_ready,total_cost_cap_review_ready,evidence_reference,review_note,reviewed_by_user_id,penalty_policy_version,penalty_monthly_rate,penalty_proration_days,penalty_rate_ceiling,lifetime_nonprincipal_cost_ceiling,counted_nonprincipal_cost_at_contract_lock) values(%s,%s,true,true,true,true,'SYNTHETIC-REVIEW','Synthetic only',%s,'SYNTHETIC',0.030000,30,%s,1000,100)""",
        (record["loan_id"], fingerprint, case["actor"], Decimal(ceiling)),
    )


@pytest.mark.parametrize("change_after_signing", [False, True])
def test_exact_7x7_review_is_pinned_to_issued_signed_pdf_and_release(
    connection, monkeypatch, change_after_signing
):
    module, repository, case = setup(connection, monkeypatch)
    product = connection.execute(
        "insert into lending.loan_types(code,name,term_days,calculation_mode,daily_interest_per_1000) values(%s,'Synthetic 7x7',120,'seven_by_seven',7.00) returning id,daily_interest_per_1000",
        (f"SYN7-{uuid4().hex}",),
    ).fetchone()
    case["terms"].update(
        loan_type_id=str(product["id"]),
        product_code="seven_by_seven",
        contractual_interest=None,
        interest_rate_percent=None,
        daily_interest_per_1000=str(product["daily_interest_per_1000"]),
        installment_count=None,
        installment_amount="100.00",
    )
    record = approve(repository, case)
    args = {
        "actor_user_id": case["actor"],
        "registered_device_id": case["device"],
        "loan_id": UUID(record["loan_id"]),
        "packet_hash": record["packet_hash"],
    }
    with pytest.raises(module.FirstLoanConflict):
        repository.register_packet_document(
            **args, content=PDF, expected_pricing_snapshot={}
        )
    seven_review(connection, module, record, case)
    current = repository.get(**{k: v for k, v in args.items() if k != "packet_hash"})
    repository.register_packet_document(
        **args, content=PDF, expected_pricing_snapshot=current["pricing_snapshot"]
    )
    authorization = repository.authorize_release(**args, request_id=uuid4())
    contract = repository.capture(
        **args,
        purpose="borrower_contract_signed",
        witnessed_wet_signature=True,
        content=PDF,
        media_type="application/pdf",
        request_id=uuid4(),
    )
    cash = repository.capture(
        **args,
        purpose="borrower_cash_received",
        content=PDF,
        media_type="application/pdf",
        request_id=uuid4(),
        authorization_id=UUID(authorization["authorization_id"]),
    )
    release_args = {
        **args,
        "authorization_id": UUID(authorization["authorization_id"]),
        "contract_evidence_reference": contract["evidence_reference"],
        "cash_evidence_reference": cash["evidence_reference"],
        "cash_amount": "1000.00",
        "borrower_confirmed": True,
        "request_id": uuid4(),
    }
    if change_after_signing:
        seven_review(connection, module, record, case, ceiling="0.060000")
        before = counts(connection)
        with pytest.raises(module.FirstLoanConflict):
            repository.release(**release_args)
        assert counts(connection) == before
        assert (
            repository.packet_document(
                **{k: v for k, v in args.items() if k != "packet_hash"}
            )[1]
            == PDF
        )
    else:
        assert repository.release(**release_args)["status"] == "released"
        settings = connection.execute(
            "select settings from lending.loan_contract_schedules where loan_id=%s",
            (args["loan_id"],),
        ).fetchone()["settings"]
        assert (
            settings["seven_by_seven_penalty_policy"]
            == current["pricing_snapshot"]["seven_by_seven_penalty_policy"]
        )
