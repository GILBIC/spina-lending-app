"""Task 3 service proofs on the existing explicitly disposable database.

Only connection acquisition and deliberate file-failure injection are replaced.
Source guards, SQL, transactions, private bytes and immutable rows stay real.
"""

from __future__ import annotations

import base64
import hashlib
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, timedelta
from importlib import import_module
from uuid import uuid4

import psycopg
import pytest
import test_first_loan_disclosure_register_postgres as register_proof
from first_loan_disclosure_fixtures import SUPPORT
from gilbic_backend.first_loan_disclosure import (
    DisclosureReviewRequest,
    public_financial_snapshot,
)
from gilbic_backend.first_loan_repository import (
    FirstLoanAccessDenied,
    FirstLoanConflict,
)
from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore
from psycopg import sql

runtime_url = register_proof.runtime_url
connection = register_proof.connection
private_fixture_configuration = register_proof.private_fixture_configuration
pytestmark = register_proof.pytestmark
MODULE = "gilbic_backend.first_loan_disclosure_repository"


def _setup(connection, monkeypatch):
    try:
        module = import_module(MODULE)
    except ModuleNotFoundError as error:
        if error.name != MODULE:
            raise
        pytest.fail(
            "R1 Task 3: protected disclosure repository is not implemented",
            pytrace=False,
        )
    _, case = register_proof._case(connection, monkeypatch)

    @contextmanager
    def acquire():
        with connection.transaction():
            yield connection

    monkeypatch.setattr(module, "open_connection", acquire)
    return module.PostgresFirstLoanDisclosureRepository(), case


def _actor(case):
    return {
        "actor_user_id": case["actor"],
        "registered_device_id": case["device"],
    }


def _context(repository, case, payload):
    return repository.context(
        **_actor(case),
        **{
            name: payload[name]
            for name in (
                "application_version_id",
                "cif_version_id",
                "dst_rule_id",
                "grt_rule_id",
                "terms",
            )
        },
    )


def _payload(connection, repository, case):
    payload = register_proof._values(connection, case)["input_snapshot"].obj
    payload["support_base64"] = base64.b64encode(SUPPORT).decode("ascii")
    payload["expected_context_digest"] = _context(repository, case, payload)[
        "context_digest"
    ]
    return payload


def _record(repository, case, payload):
    return repository.record(**_actor(case), request=payload)


def _row(connection, calculation_id):
    return connection.execute(
        "select * from lending.first_loan_disclosure_calculations where id = %s",
        (calculation_id,),
    ).fetchone()


def _state(connection):
    rows = connection.execute(
        "select * from lending.first_loan_disclosure_calculations order by id"
    ).fetchall()
    files = {
        path.name: path.read_bytes()
        for path in PrivateEvidenceStore().root.glob("*.bin")
    }
    return rows, register_proof._counts(connection), files


def _business_rows(connection):
    """Preserve complete rows, including zero-sum financial updates."""
    tables = connection.execute(
        "select schemaname, tablename from pg_tables "
        "where schemaname in ('core', 'lending', 'accounting', 'mobile', 'auth') "
        "and not (schemaname = 'lending' "
        "and tablename = 'first_loan_disclosure_calculations') "
        "and not (schemaname = 'core' and tablename = 'audit_logs') "
        "order by schemaname, tablename"
    ).fetchall()
    return {
        (row["schemaname"], row["tablename"]): connection.execute(
            sql.SQL(
                "select to_jsonb(t) as value from {}.{} t "
                "order by to_jsonb(t)::text"
            ).format(
                sql.Identifier(row["schemaname"]), sql.Identifier(row["tablename"])
            )
        ).fetchall()
        for row in tables
    }


def _immutable_result(record):
    return {
        key: value
        for key, value in record.items()
        if key not in {"approval_ready", "blockers"}
    }


def _employee(connection, case):
    connection.execute(
        "delete from core.user_roles where user_id = %s", (case["actor"],)
    )
    role = connection.execute(
        "insert into core.user_roles (user_id, role_id) "
        "select %s, id from core.roles where code = 'employee' returning role_id",
        (case["actor"],),
    ).fetchone()
    assert role is not None
    # Explicit disposable fixture permission, never a production role change.
    connection.execute(
        "insert into core.role_permissions (role_id, permission_code) "
        "values (%s, 'client_onboarding.requirement.review') "
        "on conflict do nothing",
        (role["role_id"],),
    )


def test_context_is_source_bound_without_recording_a_review(connection, monkeypatch):
    repository, case = _setup(connection, monkeypatch)
    payload = register_proof._values(connection, case)["input_snapshot"].obj
    before = _state(connection)
    context = _context(repository, case, payload)
    assert context["source"]["application_id"] == str(case["app"].application_id)
    assert context["source"]["application_version_id"] == str(case["app"].id)
    assert context["source"]["client_id"] == str(case["client"])
    assert context["source"]["cif_version_id"] == str(case["cif"])
    assert len(context["context_digest"]) == 64
    assert _context(repository, case, payload) == context
    assert _state(connection) == before


def test_record_retains_exact_support_without_financial_or_generic_evidence_writes(
    connection, monkeypatch
):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    before = _state(connection)
    business_before = _business_rows(connection)
    audits_before = connection.execute(
        "select * from core.audit_logs order by id"
    ).fetchall()
    record = _record(repository, case, payload)
    saved = _row(connection, record["id"])
    request = DisclosureReviewRequest.model_validate(payload)
    assert saved["request_id"] == request.request_id
    assert saved["input_snapshot"] == request.model_dump(
        mode="json", exclude={"support_base64"}
    )
    assert saved["support_sha256"] == hashlib.sha256(SUPPORT).hexdigest()
    assert saved["support_byte_count"] == len(SUPPORT)
    assert saved["reviewed_by_user_id"] == case["actor"]
    assert saved["reviewed_device_id"] == case["device"]
    assert record["version_number"] == 1
    assert record["review_digest"] == saved["review_digest"]
    assert record["financial_snapshot"] == public_financial_snapshot(payload)
    assert (
        not {
            "support_storage_key",
            "input_snapshot",
            "source_snapshot",
            "rule_snapshot",
            "support_base64",
            "ready",
            "approved",
        }
        & record.keys()
    )
    assert repository.get(**_actor(case), calculation_id=record["id"]) == record
    metadata, content = repository.support(**_actor(case), calculation_id=record["id"])
    assert content == SUPPORT
    assert metadata["content_sha256"] == saved["support_sha256"]
    assert "storage_key" not in metadata and "path" not in metadata
    after = _state(connection)
    assert len(after[0]) == len(before[0]) + 1
    expected_counts = dict(before[1])
    expected_counts[("core", "audit_logs")] += 1
    assert after[1] == expected_counts
    assert _business_rows(connection) == business_before
    audit = connection.execute(
        "select * from core.audit_logs where target_id = %s "
        "and action = 'lending.first_loan.disclosure_reviewed'",
        (record["id"],),
    ).fetchall()
    assert len(audit) == 1 and audit[0]["actor_user_id"] == case["actor"]
    assert audit[0]["details"]["review_digest"] == record["review_digest"]
    assert connection.execute(
        "select * from core.audit_logs where id <> %s order by id", (audit[0]["id"],)
    ).fetchall() == audits_before
    assert len(after[2]) == len(before[2]) + 1


def test_identical_retry_returns_original_after_successor_without_writes(
    connection, monkeypatch
):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    first = _record(repository, case, payload)
    successor = deepcopy(payload)
    successor.update(request_id=str(uuid4()), supersedes_calculation_id=first["id"])
    second = _record(repository, case, successor)
    assert second["id"] != first["id"] and second["version_number"] == 2
    before = _state(connection)
    replay = _record(repository, case, payload)
    assert _immutable_result(replay) == _immutable_result(first)
    assert replay["approval_ready"] is False
    assert "calculation_superseded" in replay["blockers"]
    assert _state(connection) == before


@pytest.mark.parametrize("change", ["rationale", "support", "context", "predecessor"])
def test_changed_request_reuse_never_creates_a_second_record(
    connection, monkeypatch, change
):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    _record(repository, case, payload)
    before = _state(connection)
    changed = deepcopy(payload)
    if change == "rationale":
        changed["review_rationale"] = "Different synthetic Management review."
    elif change == "support":
        changed["support_base64"] = base64.b64encode(
            SUPPORT.replace(b"SUPPORT", b"REVISED")
        ).decode("ascii")
    elif change == "context":
        changed["expected_context_digest"] = "c" * 64
    else:
        changed["supersedes_calculation_id"] = str(uuid4())
    with pytest.raises(FirstLoanConflict):
        _record(repository, case, changed)
    assert _state(connection) == before


@pytest.mark.parametrize("change", ["digest", "application", "cif"])
def test_stale_or_foreign_context_has_no_file_or_database_side_effects(
    connection, monkeypatch, change
):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    if change == "digest":
        payload["expected_context_digest"] = "c" * 64
    elif change == "application":
        payload["application_version_id"] = str(uuid4())
    else:
        payload["cif_version_id"] = str(uuid4())
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        _record(repository, case, payload)
    assert _state(connection) == before


@pytest.mark.parametrize("change", ["employee", "permission", "device"])
def test_only_authorized_management_can_record(connection, monkeypatch, change):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    if change == "employee":
        _employee(connection, case)
    elif change == "permission":
        connection.execute(
            "delete from core.role_permissions "
            "where permission_code = 'lending.first_loan.approve'"
        )
    else:
        case["device"] = uuid4()
    before = _state(connection)
    with pytest.raises(FirstLoanAccessDenied):
        _record(repository, case, payload)
    assert _state(connection) == before


def test_office_can_read_financial_values_but_not_calculation_file(
    connection, monkeypatch
):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    record = _record(repository, case, payload)
    _employee(connection, case)
    before = _state(connection)
    assert repository.get(**_actor(case), calculation_id=record["id"]) == record
    with pytest.raises(FirstLoanAccessDenied):
        repository.support(**_actor(case), calculation_id=record["id"])
    assert _state(connection) == before


@pytest.mark.parametrize("change", ["missing", "corrupt"])
def test_private_support_read_checks_actual_retained_bytes(
    connection, monkeypatch, change
):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    record = _record(repository, case, payload)
    saved = _row(connection, record["id"])
    path = PrivateEvidenceStore().root / f"{saved['support_storage_key'].hex}.bin"
    if change == "missing":
        path.unlink()
    else:
        content = path.read_bytes()
        path.write_bytes(content.replace(b"SUPPORT", b"CORRUPT"))
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        repository.support(**_actor(case), calculation_id=record["id"])
    assert _state(connection) == before


def test_next_review_requires_explicit_current_predecessor(connection, monkeypatch):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    _record(repository, case, payload)
    payload["request_id"] = str(uuid4())
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        _record(repository, case, payload)
    assert _state(connection) == before


def test_invalid_file_bytes_cannot_become_a_retained_review(connection, monkeypatch):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    payload["support_base64"] = base64.b64encode(b"not a PDF").decode("ascii")
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        _record(repository, case, payload)
    assert _state(connection) == before


def test_stale_source_remains_readable_but_cannot_record_a_new_review(
    connection, monkeypatch
):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    first = _record(repository, case, payload)
    connection.execute(
        "update lending.clients set status = 'inactive' where id = %s",
        (case["client"],),
    )
    before = _state(connection)
    replay = _record(repository, case, payload)
    assert _immutable_result(replay) == _immutable_result(first)
    assert replay["approval_ready"] is False
    assert "source_context_changed" in replay["blockers"]
    assert repository.get(**_actor(case), calculation_id=first["id"]) == replay
    recovered = repository.by_request(
        **_actor(case), request_id=payload["request_id"]
    )
    assert recovered == replay
    payload["request_id"] = str(uuid4())
    with pytest.raises(FirstLoanConflict):
        _record(repository, case, payload)
    assert _state(connection) == before


@pytest.mark.parametrize("operation", ["get", "support"])
def test_explicit_application_binding_cannot_be_crossed(
    connection, monkeypatch, operation
):
    repository, case = _setup(connection, monkeypatch)
    record = _record(repository, case, _payload(connection, repository, case))
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        getattr(repository, operation)(
            **_actor(case),
            calculation_id=record["id"],
            application_version_id=uuid4(),
        )
    assert _state(connection) == before


def test_different_management_actor_cannot_reuse_request_identity(
    connection, monkeypatch
):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    _record(repository, case, payload)
    _, other = _setup(connection, monkeypatch)
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        _record(repository, other, payload)
    with pytest.raises(FirstLoanConflict):
        repository.by_request(**_actor(other), request_id=payload["request_id"])
    assert _state(connection) == before


def test_missing_values_and_unsupported_grt_never_become_ready(
    connection, monkeypatch
):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    payload["components"].update(
        contractual_interest="195.00", grt_in_repayments="5.00"
    )
    payload["charge_items"] = [
        {
            "item_id": "grt",
            "kind": "grt_recovery",
            "timing": "repayments",
            "amount": "5.00",
            "support_section_reference": "SYNTHETIC blocked split",
        }
    ]
    payload["borrower_charge_basis"]["grt_zero_reason"] = None
    business_before = _business_rows(connection)
    record = _record(repository, case, payload)
    assert record["approval_ready"] is False
    assert "component_integration_required" in record["blockers"]
    assert "missing_amount_financed" in record["blockers"]
    assert "missing_effective_interest_rate" in record["blockers"]
    assert _business_rows(connection) == business_before
    assert _row(connection, record["id"])["input_snapshot"]["terms"] == payload["terms"]


@pytest.mark.parametrize("change", ["wrong_type", "future", "maturity", "superseded"])
def test_rule_applicability_is_rechecked_before_private_file_write(
    connection, monkeypatch, change
):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    if change == "wrong_type":
        payload["dst_rule_id"] = payload["grt_rule_id"]
    else:
        current = connection.execute(
            "select * from accounting.v1_tax_rule_evidence where id = %s",
            (case["dst_rule"],),
        ).fetchone()
        effective = current["effective_from"]
        if change == "future":
            planned = date.fromisoformat(payload["terms"]["schedule_basis_date"])
            effective = planned + timedelta(days=1)
        key = current["rule_key"] if change == "superseded" else f"SYN-R1-{uuid4().hex}"
        replacement = connection.execute(
            "select accounting.record_v1_tax_rule_evidence("
            "%s, %s, 'documentary_stamp_tax', %s, %s, null, 'exempt', 0, %s, "
            "'SYNTHETIC ONLY', 'SYNTHETIC ONLY', 'SYNTHETIC ONLY', %s, "
            "'Synthetic applicability proof; no live tax authority.', %s) as id",
            (
                case["actor"],
                uuid4(),
                key,
                effective,
                1 if change == "maturity" else None,
                "b" * 64,
                current["id"] if change == "superseded" else None,
            ),
        ).fetchone()["id"]
        if change != "superseded":
            payload["dst_rule_id"] = str(replacement)
    before = _state(connection)
    with pytest.raises(FirstLoanConflict):
        _context(repository, case, payload)
    with pytest.raises(FirstLoanConflict):
        _record(repository, case, payload)
    assert _state(connection) == before


def test_failed_audit_rolls_back_review_and_exact_retry_reuses_staged_file(
    connection, monkeypatch
):
    repository, case = _setup(connection, monkeypatch)
    payload = _payload(connection, repository, case)
    before = _state(connection)
    business_before = _business_rows(connection)
    name = f"r1_audit_failure_{uuid4().hex}"
    connection.execute(
        sql.SQL(
            "create function pg_temp.{}() returns trigger language plpgsql "
            "as $$ begin if NEW.action = 'lending.first_loan.disclosure_reviewed' "
            "then raise exception 'SYNTHETIC R1 audit failure'; "
            "end if; return NEW; end; $$"
        ).format(sql.Identifier(name))
    )
    connection.execute(
        sql.SQL(
            "create trigger {} before insert on core.audit_logs "
            "for each row execute function pg_temp.{}()"
        ).format(sql.Identifier(name), sql.Identifier(name))
    )
    with pytest.raises(psycopg.Error, match="SYNTHETIC R1 audit failure"):
        _record(repository, case, payload)
    after = _state(connection)
    assert after[:2] == before[:2]
    assert _business_rows(connection) == business_before
    assert len(after[2]) == len(before[2]) + 1
    connection.execute(
        sql.SQL("drop trigger {} on core.audit_logs").format(sql.Identifier(name))
    )
    record = _record(repository, case, payload)
    assert _state(connection)[2] == after[2]
    assert _record(repository, case, payload) == record
