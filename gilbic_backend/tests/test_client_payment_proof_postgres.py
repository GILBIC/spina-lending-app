"""Real evidence lifecycle and ownership proof in the guarded disposable DB."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from gilbic_backend import client_payment_proof_repository as module
from test_client_cif_review_confirmation_postgres import (
    DATABASE_URL,
    connection as connection,
    runtime_url as runtime_url,
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)
PDF = b"%PDF-1.4\nSynthetic payment evidence\n%%EOF"
REPLACEMENT = b"%PDF-1.4\nSynthetic corrected evidence\n%%EOF"


@pytest.fixture(autouse=True)
def private_storage(monkeypatch, tmp_path):
    root = tmp_path / "proof-files"
    monkeypatch.setenv("GILBIC_OFFICE_REVIEW_EVIDENCE_ROOT", str(root))
    return root


def _seed(connection):
    case = {}
    for name, role in (
        ("client", "client"),
        ("other", "client"),
        ("manager", "management"),
        ("employee", "employee"),
    ):
        user, device = uuid4(), uuid4()
        connection.execute(
            "insert into core.users(id,username,full_name) values(%s,%s,'Synthetic proof actor')",
            (user, user.hex),
        )
        connection.execute(
            "insert into core.user_roles(user_id,role_id) select %s,id from core.roles where code=%s",
            (user, role),
        )
        connection.execute(
            "insert into core.devices(id,user_id,device_identifier_hash,platform) values(%s,%s,%s,'web')",
            (device, user, device.hex),
        )
        case[name] = {"actor_user_id": user, "registered_device_id": device}
    loan_type = connection.execute(
        "insert into lending.loan_types(code,name,term_days,calculation_mode) values(%s,'Synthetic Regular',30,'fixed_daily') returning id",
        (uuid4().hex,),
    ).fetchone()["id"]
    for name in ("client", "other"):
        client_id = connection.execute(
            "insert into lending.clients(user_id,client_code,full_name) values(%s,%s,'Synthetic proof borrower') returning id",
            (case[name]["actor_user_id"], uuid4().hex),
        ).fetchone()["id"]
        loan_id = connection.execute(
            "insert into lending.loans(loan_number,client_id,loan_type_id,principal,daily_amount,date_released,due_date,status) values(%s,%s,%s,1000,40,current_date,current_date+30,'active') returning id",
            (uuid4().hex, client_id, loan_type),
        ).fetchone()["id"]
        case[name + "_client"] = client_id
        case[name + "_loan"] = loan_id
    return case


def _repository(connection, monkeypatch):
    @contextmanager
    def scoped_connection():
        with connection.transaction():
            yield connection

    monkeypatch.setattr(module, "open_connection", scoped_connection)
    return module.PostgresClientPaymentProofRepository()


def _upload(repository, case, **changes):
    values = {
        **case["client"],
        "loan_id": case["client_loan"],
        "request_id": uuid4(),
        "content": PDF,
        "media_type": "application/pdf",
        "note": "Synthetic note",
    }
    values.update(changes)
    return repository.upload(**values)


def _review(repository, case, proof_id, **changes):
    values = {
        **case["manager"],
        "proof_id": proof_id,
        "request_id": uuid4(),
        "expected_version": 1,
        "expected_review_id": None,
        "decision": "correction_required",
        "reason": "Upload a complete readable image",
    }
    values.update(changes)
    return repository.review(**values)


def _financial_state(connection):
    tables = (
        "auth.users",
        "core.users",
        "lending.loans",
        "lending.loan_collection_state",
        "lending.collection_transactions",
        "lending.loan_disbursement_events",
        "lending.first_loan_releases",
        "accounting.journal_entries",
        "accounting.journal_lines",
    )
    return {
        name: connection.execute(
            sql.SQL("select count(*) as n from {}.{}").format(
                *map(sql.Identifier, name.split("."))
            )
        ).fetchone()["n"]
        for name in tables
    }


def test_real_upload_correction_review_history_and_no_financial_effect(
    connection, monkeypatch
):
    case = _seed(connection)
    repository = _repository(connection, monkeypatch)
    before = _financial_state(connection)
    initial = _upload(repository, case)
    proof_id = UUID(initial["proof"]["proof_id"])
    reviewed = _review(repository, case, proof_id)
    assert reviewed["proof"]["status"] == "correction_required"
    corrected = repository.upload(
        **case["client"],
        proof_id=proof_id,
        expected_version=1,
        request_id=uuid4(),
        content=REPLACEMENT,
        media_type="application/pdf",
        note="Complete file",
    )
    assert corrected["proof"]["status"] == "under_review"
    final = _review(
        repository, case, proof_id, expected_version=2, decision="reviewed", reason=""
    )
    assert final["proof"]["status"] == "reviewed"
    assert final["proof"]["official_payment_posted"] is False
    assert [item["version"]["version_number"] for item in final["history"]] == [2, 1]
    assert (
        final["history"][1]["reviews"][0]["reason"]
        == "Upload a complete readable image"
    )
    for version, content in ((1, PDF), (2, REPLACEMENT)):
        metadata, stored = repository.content(
            **case["client"], proof_id=proof_id, version_number=version
        )
        assert stored == content and metadata["byte_count"] == len(content)
    assert _financial_state(connection) == before
    audit = connection.execute(
        "select action from core.audit_logs where target_id=%s", (proof_id,)
    ).fetchall()
    assert (
        sorted(row["action"] for row in audit)
        == ["client_payment_proof.downloaded"] * 2
        + ["client_payment_proof.reviewed"] * 2
        + ["client_payment_proof.uploaded"] * 2
    )


def test_upload_retry_and_conflicting_reuse_preserve_one_version(
    connection, monkeypatch, private_storage
):
    case = _seed(connection)
    repository = _repository(connection, monkeypatch)
    request_id = uuid4()
    first = _upload(repository, case, request_id=request_id)
    assert _upload(repository, case, request_id=request_id) == first
    for changed in (
        {"content": REPLACEMENT},
        {"note": "Changed"},
        {"loan_id": case["other_loan"]},
    ):
        with pytest.raises(module.PaymentProofConflict):
            _upload(repository, case, request_id=request_id, **changed)
    assert len(list(private_storage.glob("*.bin"))) == 1
    assert len(first["history"]) == 1


@pytest.mark.parametrize("action", ["get", "content", "reupload", "upload"])
def test_cross_borrower_targets_are_hidden(connection, monkeypatch, action):
    case = _seed(connection)
    repository = _repository(connection, monkeypatch)
    proof_id = UUID(_upload(repository, case)["proof"]["proof_id"])
    with pytest.raises(module.PaymentProofNotFound):
        if action == "get":
            repository.get(**case["other"], proof_id=proof_id)
        elif action == "content":
            repository.content(**case["other"], proof_id=proof_id, version_number=1)
        elif action == "reupload":
            repository.upload(
                **case["other"],
                proof_id=proof_id,
                expected_version=1,
                request_id=uuid4(),
                content=PDF,
                media_type="application/pdf",
            )
        else:
            repository.upload(
                **case["other"],
                loan_id=case["client_loan"],
                request_id=uuid4(),
                content=PDF,
                media_type="application/pdf",
            )
    assert repository.list_proofs(**case["other"])["proofs"] == []


@pytest.mark.parametrize(
    "scenario",
    [
        "disabled_user",
        "revoked_device",
        "wrong_device",
        "missing_role",
        "unlinked_client",
    ],
)
def test_persisted_client_identity_is_rechecked_for_each_operation(
    connection, monkeypatch, scenario
):
    case = _seed(connection)
    repository = _repository(connection, monkeypatch)
    proof_id = UUID(_upload(repository, case)["proof"]["proof_id"])
    expected = module.PaymentProofAccessDenied
    if scenario == "disabled_user":
        connection.execute(
            "update core.users set status='inactive' where id=%s",
            (case["client"]["actor_user_id"],),
        )
    elif scenario == "revoked_device":
        connection.execute(
            "update core.devices set status='revoked' where id=%s",
            (case["client"]["registered_device_id"],),
        )
    elif scenario == "wrong_device":
        case["client"]["registered_device_id"] = case["other"]["registered_device_id"]
    elif scenario == "missing_role":
        connection.execute(
            "delete from core.user_roles where user_id=%s",
            (case["client"]["actor_user_id"],),
        )
    else:
        connection.execute(
            "update lending.clients set user_id=null where id=%s",
            (case["client_client"],),
        )
        expected = module.PaymentProofNotFound
    with pytest.raises(expected):
        repository.content(**case["client"], proof_id=proof_id, version_number=1)


@pytest.mark.parametrize(
    "scenario", ["client", "employee", "permission_removed", "device_revoked"]
)
def test_only_persisted_authorized_management_can_review(
    connection, monkeypatch, scenario
):
    case = _seed(connection)
    repository = _repository(connection, monkeypatch)
    proof_id = UUID(_upload(repository, case)["proof"]["proof_id"])
    changes = {}
    if scenario in ("client", "employee"):
        changes.update(case[scenario])
    elif scenario == "permission_removed":
        connection.execute(
            "delete from core.role_permissions where permission_code='client_payment_proof.review'"
        )
    else:
        connection.execute(
            "update core.devices set status='revoked' where id=%s",
            (case["manager"]["registered_device_id"],),
        )
    with pytest.raises(module.PaymentProofAccessDenied):
        _review(repository, case, proof_id, **changes)


def test_stale_version_and_concurrent_review_identity_are_rejected(
    connection, monkeypatch
):
    case = _seed(connection)
    repository = _repository(connection, monkeypatch)
    proof_id = UUID(_upload(repository, case)["proof"]["proof_id"])
    request_id = uuid4()
    first = _review(repository, case, proof_id, request_id=request_id)
    assert _review(repository, case, proof_id, request_id=request_id) == first
    with pytest.raises(module.PaymentProofConflict):
        _review(repository, case, proof_id, decision="reviewed", reason="")
    updated = _review(
        repository,
        case,
        proof_id,
        expected_review_id=UUID(first["proof"]["latest_review"]["review_id"]),
        decision="reviewed",
        reason="",
    )
    assert len(updated["history"][0]["reviews"]) == 2
    revised = repository.upload(
        **case["client"],
        proof_id=proof_id,
        expected_version=1,
        request_id=uuid4(),
        content=REPLACEMENT,
        media_type="application/pdf",
    )
    assert revised["proof"]["status"] == "under_review"
    with pytest.raises(module.PaymentProofConflict):
        _review(repository, case, proof_id)
    with pytest.raises(module.PaymentProofConflict):
        repository.upload(
            **case["client"],
            proof_id=proof_id,
            expected_version=1,
            request_id=uuid4(),
            content=PDF,
            media_type="application/pdf",
        )


@pytest.mark.parametrize(
    "table",
    [
        "client_payment_proofs",
        "client_payment_proof_versions",
        "client_payment_proof_reviews",
    ],
)
@pytest.mark.parametrize("operation", ["update", "delete", "truncate"])
def test_evidence_and_review_history_are_immutable(
    connection, monkeypatch, table, operation
):
    case = _seed(connection)
    repository = _repository(connection, monkeypatch)
    proof_id = UUID(_upload(repository, case)["proof"]["proof_id"])
    _review(repository, case, proof_id)
    query = {
        "update": "update lending.{} set id=id",
        "delete": "delete from lending.{}",
        "truncate": "truncate lending.{} cascade",
    }[operation]
    with pytest.raises(psycopg.Error, match="immutable"):
        with connection.transaction():
            connection.execute(sql.SQL(query).format(sql.Identifier(table)))


@pytest.mark.parametrize("action", ["review", "download", "retry"])
def test_missing_or_tampered_file_never_becomes_reviewed(
    connection, monkeypatch, private_storage, action
):
    case = _seed(connection)
    repository = _repository(connection, monkeypatch)
    request_id = uuid4()
    proof = _upload(repository, case, request_id=request_id)
    proof_id = UUID(proof["proof"]["proof_id"])
    next(private_storage.glob("*.bin")).write_bytes(b"tampered")
    with pytest.raises(module.EvidenceFileError):
        if action == "review":
            _review(repository, case, proof_id, decision="reviewed", reason="")
        elif action == "download":
            repository.content(**case["client"], proof_id=proof_id, version_number=1)
        else:
            _upload(repository, case, request_id=request_id)
    assert (
        repository.get(**case["client"], proof_id=proof_id)["proof"]["status"]
        == "under_review"
    )


@pytest.mark.parametrize(
    "changes",
    [{"note": "x" * 1001}, {"note": "nul\x00byte"}, {"content": b"not an image"}],
)
def test_invalid_upload_metadata_or_content_is_rejected_before_file_write(
    connection, monkeypatch, private_storage, changes
):
    case = _seed(connection)
    repository = _repository(connection, monkeypatch)
    with pytest.raises(module.PaymentProofInvalid):
        _upload(repository, case, **changes)
    assert not list(private_storage.glob("*.bin"))


def test_schema_rerun_preserves_history_and_private_permissions(
    connection, monkeypatch
):
    case = _seed(connection)
    repository = _repository(connection, monkeypatch)
    proof = _upload(repository, case)
    source = (
        (
            Path(__file__).resolve().parents[1]
            / "sql"
            / "0127_add_client_payment_proof_evidence.sql"
        )
        .read_text(encoding="utf-8")
        .strip()
    )
    body = source.removeprefix("BEGIN;").removesuffix("COMMIT;")
    connection.execute(body)
    connection.execute(body)
    assert (
        repository.get(**case["client"], proof_id=UUID(proof["proof"]["proof_id"]))
        == proof
    )
    roles = connection.execute(
        "select r.code from core.role_permissions rp join core.roles r on r.id=rp.role_id where rp.permission_code='client_payment_proof.review'"
    ).fetchall()
    assert roles == [{"code": "management"}]
    privileges = connection.execute("""select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace,
        lateral aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a
        where n.nspname='lending' and c.relname in ('client_payment_proofs','client_payment_proof_versions','client_payment_proof_reviews') and a.grantee=0""").fetchall()
    assert privileges == []


@pytest.mark.parametrize("operation", ["upload", "review", "cross_actor_upload"])
def test_concurrent_retries_and_reviews_are_serialized(
    runtime_url, monkeypatch, operation
):
    # Committed synthetic rows intentionally live only until the runner drops
    # its strictly guarded disposable DB; immutable history is never disabled.
    with psycopg.connect(runtime_url, row_factory=dict_row) as seed_connection:
        case = _seed(seed_connection)

    @contextmanager
    def new_connection():
        with psycopg.connect(runtime_url, row_factory=dict_row) as conn:
            conn.execute("set local statement_timeout='5s'")
            yield conn

    monkeypatch.setattr(module, "open_connection", new_connection)
    repository = module.PostgresClientPaymentProofRepository()
    barrier = Barrier(2)
    request_id = uuid4()
    proof_id = (
        UUID(_upload(repository, case)["proof"]["proof_id"])
        if operation == "review"
        else None
    )

    def worker(index):
        barrier.wait(timeout=3)
        try:
            if operation == "upload":
                return _upload(repository, case, request_id=request_id)
            if operation == "cross_actor_upload":
                owner = "client" if index == 0 else "other"
                return repository.upload(
                    **case[owner],
                    loan_id=case[owner + "_loan"],
                    request_id=request_id,
                    content=PDF,
                    media_type="application/pdf",
                )
            return _review(repository, case, proof_id, request_id=uuid4())
        except module.PaymentProofConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, range(2)))
    if operation == "upload":
        assert results[0] == results[1]
        assert len(results[0]["history"]) == 1
    elif operation == "review":
        assert sum(result == "conflict" for result in results) == 1
        assert (
            len(
                repository.get(**case["client"], proof_id=proof_id)["history"][0][
                    "reviews"
                ]
            )
            == 1
        )
    else:
        assert sum(result == "conflict" for result in results) == 1
        result = next(result for result in results if result != "conflict")
        assert len(result["history"]) == 1
