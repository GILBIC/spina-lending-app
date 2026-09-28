"""Client document access uses only the disposable, real release/storage authority."""

from contextlib import contextmanager
import hashlib
from uuid import UUID, uuid4

import pytest
from psycopg import sql

from gilbic_backend import client_document_repository as module
from first_loan_approval_fixtures import reviewed_setup
from test_client_cif_review_confirmation_postgres import (
    DATABASE_URL,
    connection as connection,
    runtime_url as runtime_url,
)
from test_first_loan_postgres import (
    PDF,
    private_fixture_configuration as private_fixture_configuration,
    ready,
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)


def released_case(connection, monkeypatch, *, release=True):
    _, office, case = reviewed_setup(connection, monkeypatch)
    approval, args = ready(office, case)
    borrower = uuid4()
    connection.execute(
        "insert into core.users(id,username,full_name) values(%s,%s,'Synthetic Client')",
        (borrower, f"client-doc-{borrower.hex}"),
    )
    connection.execute(
        "update lending.clients set user_id=%s where id=%s", (borrower, case["client"])
    )
    if release:
        office.release(**args)

    @contextmanager
    def acquire():
        with connection.transaction():
            yield connection

    monkeypatch.setattr(module, "open_connection", acquire)
    return (
        module.PostgresClientDocumentRepository(),
        office,
        case,
        UUID(approval["loan_id"]),
        borrower,
        args,
    )


def state(connection):
    tables = (
        "clients",
        "loans",
        "client_cif_versions",
        "loan_application_versions",
        "first_loan_approvals",
        "first_loan_packet_documents",
        "first_loan_releases",
        "office_review_evidence",
        "loan_contract_schedules",
        "loan_disbursement_events",
        "first_loan_credential_intents",
    )
    return {
        table: connection.execute(
            sql.SQL("select * from lending.{} order by id").format(
                sql.Identifier(table)
            )
        ).fetchall()
        for table in tables
    }


def test_released_client_reads_only_exact_packet_and_two_release_linked_scans_without_writes(
    connection, monkeypatch
):
    repository, _, _, loan_id, user_id, _ = released_case(connection, monkeypatch)
    before = state(connection)
    documents = repository.list_for_user(user_id=user_id, loan_id=loan_id)
    assert [record.kind for record in documents] == [
        "finalized_loan_packet",
        "signed_loan_contract",
        "cash_release_acknowledgment",
    ]
    assert len({record.document_id for record in documents}) == 3
    for record in documents:
        assert record.media_type == "application/pdf"
        assert record.content_sha256 == hashlib.sha256(PDF).hexdigest()
        assert record.byte_count == len(PDF)
        result = repository.download_for_user(
            user_id=user_id, loan_id=loan_id, document_id=record.document_id
        )
        assert result.record == record and result.content == PDF
    assert state(connection) == before


@pytest.mark.parametrize(
    "change",
    [
        "cif_expired",
        "cif_superseded",
        "reverification",
        "loan_paid",
        "template_inactive",
    ],
)
def test_historical_release_remains_readable_after_current_lifecycle_changes(
    connection, monkeypatch, change
):
    repository, _, case, loan_id, user_id, _ = released_case(connection, monkeypatch)
    if change == "cif_expired":
        connection.execute(
            "update lending.client_cif_versions set activated_at=now()-interval '6 years',expires_at=now()-interval '1 year',review_due_at=now()-interval '1 year 90 days' where id=%s",
            (case["cif"],),
        )
    elif change == "cif_superseded":
        connection.execute(
            "update lending.client_cif_versions set status='superseded',is_current=false where id=%s",
            (case["cif"],),
        )
    elif change == "reverification":
        connection.execute(
            "update lending.client_cif_versions set reverification_required_at=now(),reverification_reason='Synthetic update' where id=%s",
            (case["cif"],),
        )
    elif change == "loan_paid":
        connection.execute(
            "update lending.loans set status='paid' where id=%s", (loan_id,)
        )
    else:
        connection.execute(
            "update lending.first_loan_document_templates set is_active=false,approved_for_execution=false where version=%s",
            (case["template"],),
        )
    before = state(connection)
    for record in repository.list_for_user(user_id=user_id, loan_id=loan_id):
        assert (
            repository.download_for_user(
                user_id=user_id, loan_id=loan_id, document_id=record.document_id
            ).content
            == PDF
        )
    assert state(connection) == before


@pytest.mark.parametrize("wrong", ["user", "loan", "document", "unrelated_evidence"])
def test_unknown_cross_client_or_unrelated_evidence_is_denied_before_private_file_access(
    connection, monkeypatch, wrong
):
    repository, _, case, loan_id, user_id, _ = released_case(connection, monkeypatch)
    document_id = repository.list_for_user(user_id=user_id, loan_id=loan_id)[
        0
    ].document_id
    if wrong == "user":
        user_id = uuid4()
    elif wrong == "loan":
        loan_id = uuid4()
    elif wrong == "document":
        document_id = uuid4()
    else:
        document_id = connection.execute(
            "select id from lending.office_review_evidence where client_id=%s and purpose='cif_review'",
            (case["client"],),
        ).fetchone()["id"]

    def never_open():
        pytest.fail(
            "Unowned/unreleased/private office evidence must never touch storage"
        )

    monkeypatch.setattr(module, "PrivateEvidenceStore", never_open)
    with pytest.raises(module.ClientDocumentNotFound):
        repository.download_for_user(
            user_id=user_id, loan_id=loan_id, document_id=document_id
        )


@pytest.mark.parametrize("cancelled", [False, True])
def test_unreleased_packet_and_scans_are_not_client_documents(
    connection, monkeypatch, cancelled
):
    repository, _, _, loan_id, user_id, _ = released_case(
        connection, monkeypatch, release=False
    )
    if cancelled:
        connection.execute(
            "update lending.loans set status='cancelled' where id=%s", (loan_id,)
        )
    with pytest.raises(module.ClientDocumentNotFound):
        repository.list_for_user(user_id=user_id, loan_id=loan_id)


@pytest.mark.parametrize("failure", ["changed", "missing", "unconfigured"])
def test_saved_file_integrity_failure_never_regenerates_or_rewrites_packet(
    connection, monkeypatch, failure
):
    repository, _, _, loan_id, user_id, _ = released_case(connection, monkeypatch)
    record = repository.list_for_user(user_id=user_id, loan_id=loan_id)[0]
    store = module.PrivateEvidenceStore()
    path = store.root / f"{record.document_id.hex}.bin"
    if failure == "changed":
        path.write_bytes(b"%PDF-1.4\nALTERED\n%%EOF")
    elif failure == "missing":
        path.unlink()
    else:
        monkeypatch.delenv("GILBIC_OFFICE_REVIEW_EVIDENCE_ROOT")
    before = state(connection)
    with pytest.raises(module.ClientDocumentUnavailable):
        repository.download_for_user(
            user_id=user_id, loan_id=loan_id, document_id=record.document_id
        )
    assert state(connection) == before


def test_release_linked_png_scan_uses_exact_evidence_storage_key_and_media(
    connection, monkeypatch
):
    repository, office, _, loan_id, user_id, args = released_case(
        connection, monkeypatch, release=False
    )
    png = b"\x89PNG\r\n\x1a\nSYNTHETIC PNG\x00IEND\xaeB`\x82"
    signed = office.capture(
        **{
            key: args[key]
            for key in (
                "actor_user_id",
                "registered_device_id",
                "loan_id",
                "packet_hash",
            )
        },
        purpose="borrower_contract_signed",
        witnessed_wet_signature=True,
        content=png,
        media_type="image/png",
        request_id=uuid4(),
    )
    args["contract_evidence_reference"] = signed["evidence_reference"]
    office.release(**args)
    records = repository.list_for_user(user_id=user_id, loan_id=loan_id)
    signed_record = next(
        record for record in records if record.kind == "signed_loan_contract"
    )
    assert signed_record.media_type == "image/png"
    assert (
        str(signed_record.document_id) == signed["evidence_reference"].split(":", 1)[1]
    )
    assert (
        repository.download_for_user(
            user_id=user_id, loan_id=loan_id, document_id=signed_record.document_id
        ).content
        == png
    )
