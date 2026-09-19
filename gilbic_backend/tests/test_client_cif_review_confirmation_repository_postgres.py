"""Real repository proof for immutable CIF information-review confirmation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from importlib import import_module
from queue import Queue
from threading import Event, get_ident
from time import monotonic
from typing import Any
import psycopg
import pytest
from office_review_evidence_test_support import (
    private_evidence_root as private_evidence_root,
)
from psycopg import sql
from psycopg.rows import dict_row

from test_client_cif_review_confirmation_postgres import (
    DATABASE_URL,
    _insert,
    _summary_state,
    connection as connection,
    runtime_url as runtime_url,
)
from test_loan_application_repository_postgres import PERMISSION, _seed
from office_review_evidence_test_support import capture_cif


pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)
MODULE = "gilbic_backend.client_cif_repository"
FIELDS = ("full_name", "phone_number", "email", "present_address")
EVIDENCE = "SYNTHETIC-CIF-APPLICANT-ACK"


def _module():
    return import_module(MODULE)


def _repository(connection, monkeypatch):
    module = _module()

    @contextmanager
    def acquire():
        with connection.transaction():
            yield connection

    monkeypatch.setattr(module, "open_connection", acquire)
    return module.PostgresClientCifRepository()


def _method(repository):
    method = getattr(repository, "confirm_review", None)
    if method is None:
        pytest.fail(
            "CIF review confirmation repository is not implemented", pytrace=False
        )
    return method


def _error(repository, name):
    _method(repository)
    return getattr(_module(), name)


def _information(connection, case):
    row = connection.execute(
        "select full_name, phone_number, email, present_address "
        "from lending.client_cif_versions where id = %s",
        (case["cif"],),
    ).fetchone()
    assert row is not None
    return dict(row)


def _payload(connection, case, **changes: Any):
    key = (case["cif"], case["actor"])
    captures = case.setdefault("protected_captures", {})
    if key not in captures:
        captures[key] = capture_cif(connection, case)
    values = {
        "actor_user_id": case["actor"],
        "client_id": case["client"],
        "cif_version_id": case["cif"],
        "expected_information": _information(connection, case),
        "applicant_confirmation_evidence_reference": captures[key],
    }
    values.update(changes)
    return values


def _confirm(repository, connection, case, **changes: Any):
    return _method(repository)(**_payload(connection, case, **changes))


def _rows(connection, client_id):
    return connection.execute(
        "select * from lending.client_cif_review_confirmations "
        "where client_id = %s order by review_cycle_number",
        (client_id,),
    ).fetchall()


def _activate(connection, case):
    connection.execute(
        "update lending.clients set status = 'active' where id = %s",
        (case["client"],),
    )
    connection.execute(
        "update lending.client_cif_versions set status = 'active', "
        "baseline_liveness_status = 'passed', "
        "baseline_face_scan_evidence_reference = 'SYNTHETIC-FACE', "
        "activated_at = now(), expires_at = now() + interval '5 years', "
        "review_due_at = now() + interval '5 years' - interval '90 days' "
        "where id = %s",
        (case["cif"],),
    )


@pytest.mark.parametrize("role", ["employee", "management"])
@pytest.mark.parametrize("stage", ["draft", "active"])
def test_confirmation_persists_exact_snapshot_server_witness_and_time_without_side_effects(
    connection, monkeypatch, role, stage
):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection, role)
    if stage == "active":
        _activate(connection, case)
    connection.execute(
        "update lending.client_cif_versions set "
        "full_name='  Synthetic   CIF Borrower  ', "
        "phone_number='0917-111-1111', email=' MiXeD@Example.COM ', "
        "present_address='  Synthetic   office address  ' where id=%s",
        (case["cif"],),
    )
    expected = _information(connection, case)
    evidence = _payload(connection, case)["applicant_confirmation_evidence_reference"]
    before = _summary_state(connection, case)
    server_time = connection.execute("select now() as value").fetchone()["value"]

    record = _confirm(
        repository,
        connection,
        case,
        expected_information=expected,
        applicant_confirmation_evidence_reference=f"  {evidence}  ",
    )

    stored = _rows(connection, case["client"])
    assert len(stored) == 1
    row = stored[0]
    assert record.id == row["id"]
    assert record.client_id == row["client_id"] == case["client"]
    assert record.cif_version_id == row["cif_version_id"] == case["cif"]
    assert record.review_cycle_number == row["review_cycle_number"] == 1
    assert record.review_snapshot == row["review_snapshot"] == expected
    assert (
        record.applicant_confirmation_evidence_reference
        == row["applicant_confirmation_evidence_reference"]
        == evidence
    )
    assert record.witnessed_by_user_id == row["witnessed_by_user_id"] == case["actor"]
    assert record.confirmed_at == row["confirmed_at"] == server_time
    after = _summary_state(connection, case)
    before["confirmations"] = sorted(
        [*before["confirmations"], row], key=lambda confirmation: confirmation["id"]
    )
    assert after == before


def test_identical_retry_returns_original_even_after_source_becomes_ineligible(
    connection, monkeypatch
):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    payload = _payload(connection, case)
    first = _method(repository)(**payload)
    connection.execute(
        "update lending.client_cif_versions set is_current=false,status='superseded' where id=%s",
        (case["cif"],),
    )
    connection.execute(
        "update lending.client_cif_versions set is_current=true where id=%s",
        (case["next_cif"],),
    )
    connection.execute(
        "update lending.clients set status='blocked' where id=%s", (case["client"],)
    )

    assert _method(repository)(**payload) == first
    assert _rows(connection, case["client"])[0]["id"] == first.id


@pytest.mark.parametrize("difference", ["evidence", "witness", "snapshot"])
def test_conflicting_retry_is_rejected_without_rewrite(
    connection, monkeypatch, difference
):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    first = _confirm(repository, connection, case)
    changes: dict[str, Any] = {}
    if difference == "evidence":
        changes["applicant_confirmation_evidence_reference"] = "DIFFERENT-ACK"
    elif difference == "witness":
        changes["actor_user_id"] = _seed(connection, "management")["actor"]
    else:
        stale = _information(connection, case)
        stale["present_address"] = "Different reviewed snapshot"
        changes["expected_information"] = stale
    before = _rows(connection, case["client"])

    with pytest.raises(_error(repository, "ClientCifConflict")):
        _confirm(repository, connection, case, **changes)
    assert _rows(connection, case["client"]) == before
    assert before[0]["id"] == first.id


@pytest.mark.parametrize("field", FIELDS)
def test_stale_expected_information_is_rejected(connection, monkeypatch, field):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    expected = _information(connection, case)
    expected[field] = "stale@example.com" if field == "email" else "Stale value"
    with pytest.raises(
        _error(repository, "ClientCifConflict"), match="refresh|changed"
    ):
        _confirm(repository, connection, case, expected_information=expected)
    assert _rows(connection, case["client"]) == []


@pytest.mark.parametrize(
    "expected",
    [
        {},
        {"full_name": "Only one field"},
        {
            "full_name": "Name",
            "phone_number": "1234567",
            "email": None,
            "present_address": "Address",
            "extra": "forbidden",
        },
        {
            "full_name": 42,
            "phone_number": "1234567",
            "email": None,
            "present_address": "Address",
        },
    ],
)
def test_malformed_snapshot_is_rejected_without_writes(
    connection, monkeypatch, expected
):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    with pytest.raises(ValueError):
        _confirm(repository, connection, case, expected_information=expected)
    assert _rows(connection, case["client"]) == []


@pytest.mark.parametrize("reference", ["", "   ", None, 123])
def test_evidence_reference_must_be_nonblank_text(connection, monkeypatch, reference):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    with pytest.raises(ValueError):
        _confirm(
            repository,
            connection,
            case,
            applicant_confirmation_evidence_reference=reference,
        )
    assert _rows(connection, case["client"]) == []


@pytest.mark.parametrize(
    "role,state",
    [
        ("collector", "active"),
        ("client", "active"),
        ("employee", "inactive"),
        ("employee", "missing_permission"),
    ],
)
def test_persisted_office_authorization_is_required(
    connection, monkeypatch, role, state
):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection, role)
    if state == "inactive":
        connection.execute(
            "update core.users set status='inactive' where id=%s", (case["actor"],)
        )
    elif state == "missing_permission":
        connection.execute(
            "delete from core.role_permissions where permission_code=%s and role_id in "
            "(select role_id from core.user_roles where user_id=%s)",
            (PERMISSION, case["actor"]),
        )
    with pytest.raises(_error(repository, "ClientCifAccessDenied")):
        _confirm(repository, connection, case)
    assert _rows(connection, case["client"]) == []


def test_retry_rechecks_authorization(connection, monkeypatch):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    _confirm(repository, connection, case)
    connection.execute(
        "update core.users set status='inactive' where id=%s", (case["actor"],)
    )
    with pytest.raises(_error(repository, "ClientCifAccessDenied")):
        _confirm(repository, connection, case)
    assert len(_rows(connection, case["client"])) == 1


@pytest.mark.parametrize(
    "scenario",
    [
        "wrong_client",
        "wrong_cif",
        "noncurrent",
        "superseded",
        "blocked",
        "closed",
        "requirements_incomplete",
        "under_verification",
        "wrong_link",
        "mismatched_stage",
    ],
)
def test_new_confirmation_requires_fresh_paired_eligible_source(
    connection, monkeypatch, scenario
):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    changes = {}
    if scenario == "wrong_client":
        changes["client_id"] = case["other"]
    elif scenario == "wrong_cif":
        changes["cif_version_id"] = case["next_cif"]
    elif scenario == "noncurrent":
        connection.execute(
            "update lending.client_cif_versions set is_current=false where id=%s",
            (case["cif"],),
        )
    elif scenario == "superseded":
        connection.execute(
            "update lending.client_cif_versions set status='superseded' where id=%s",
            (case["cif"],),
        )
    elif scenario in {"blocked", "closed"}:
        connection.execute(
            "update lending.clients set status=%s where id=%s",
            (scenario, case["client"]),
        )
    elif scenario in {"requirements_incomplete", "under_verification"}:
        connection.execute(
            "update lending.client_onboarding_applicants set status=%s where id=%s",
            (scenario, case["applicant"]),
        )
    elif scenario == "wrong_link":
        connection.execute(
            "update lending.client_onboarding_applicants set promoted_client_id=%s where id=%s",
            (case["other"], case["applicant"]),
        )
    elif scenario == "mismatched_stage":
        _activate(connection, case)
        connection.execute(
            "update lending.clients set status='inactive' where id=%s",
            (case["client"],),
        )
    with pytest.raises(_error(repository, "ClientCifConflict")):
        _confirm(repository, connection, case, **changes)
    assert _rows(connection, case["client"]) == []


@pytest.mark.parametrize(
    "field,value",
    [("full_name", "x"), ("phone_number", "123"), ("present_address", "x")],
)
def test_incomplete_stored_information_cannot_be_confirmed(
    connection, monkeypatch, field, value
):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    connection.execute(
        sql.SQL("update lending.client_cif_versions set {}=%s where id=%s").format(
            sql.Identifier(field)
        ),
        (value, case["cif"]),
    )
    with pytest.raises(
        _error(repository, "ClientCifConflict"), match="incomplete|invalid"
    ):
        _confirm(repository, connection, case)
    assert _rows(connection, case["client"]) == []


def test_cycle_number_uses_client_history_not_cif_version_number(
    connection, monkeypatch
):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    first = _insert(connection, case, review_cycle_number=7)
    connection.execute(
        "update lending.client_cif_versions set is_current=false,status='superseded' where id=%s",
        (case["cif"],),
    )
    connection.execute(
        "update lending.client_cif_versions set is_current=true where id=%s",
        (case["next_cif"],),
    )
    case["cif"] = case["next_cif"]
    second = _confirm(repository, connection, case)
    assert second.review_cycle_number == 8
    assert _rows(connection, case["client"])[0]["id"] == first["id"]


def test_insert_failure_rolls_back_without_partial_effects(connection, monkeypatch):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    trigger = f"fail_cif_confirmation_{case['cif'].hex}"
    connection.execute(
        sql.SQL(
            "create function pg_temp.{}() returns trigger language plpgsql as $$ "
            "begin raise exception 'SYNTHETIC CIF confirmation failure' using errcode='23514'; end; $$"
        ).format(sql.Identifier(trigger))
    )
    connection.execute(
        sql.SQL(
            "create trigger {} before insert on lending.client_cif_review_confirmations "
            "for each row when (NEW.cif_version_id = {}::uuid) execute function pg_temp.{}()"
        ).format(
            sql.Identifier(trigger),
            sql.Literal(str(case["cif"])),
            sql.Identifier(trigger),
        )
    )
    _payload(
        connection, case
    )  # Capture precedes the confirmation transaction under test.
    before = _summary_state(connection, case)
    with pytest.raises(
        psycopg.errors.CheckViolation, match="SYNTHETIC CIF confirmation failure"
    ):
        _confirm(repository, connection, case)
    assert _summary_state(connection, case) == before


@pytest.mark.parametrize(
    "winner",
    ["correction", "confirmation", "same_confirmation", "different_confirmation"],
)
def test_confirmation_and_correction_serialize_and_recheck(
    runtime_url, monkeypatch, winner
):
    module = _module()
    repository_probe = module.PostgresClientCifRepository()
    _method(repository_probe)
    options = "-c lock_timeout=10000 -c statement_timeout=15000"
    with psycopg.connect(
        runtime_url, autocommit=True, row_factory=dict_row
    ) as observer:
        with observer.transaction():
            case = _seed(observer)
        payload = _payload(observer, case)
        corrected = {**payload["expected_information"], "phone_number": "09172222222"}
        owner = psycopg.connect(
            runtime_url, row_factory=dict_row, options=options, connect_timeout=5
        )
        owner_thread = get_ident()
        contender_pid = Queue()

        @contextmanager
        def acquire():
            if get_ident() == owner_thread:
                with owner.transaction():
                    yield owner
            else:
                with psycopg.connect(
                    runtime_url,
                    row_factory=dict_row,
                    options=options,
                    connect_timeout=5,
                ) as contender:
                    contender_pid.put(contender.info.backend_pid)
                    yield contender

        monkeypatch.setattr(module, "open_connection", acquire)
        repository = module.PostgresClientCifRepository()
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            owner.execute(
                "select cif.id from lending.client_cif_versions cif "
                "join lending.client_onboarding_applicants applicant on applicant.promoted_client_id=cif.client_id "
                "join lending.clients client on client.id=cif.client_id "
                "where cif.id=%s for update of cif, applicant, client",
                (case["cif"],),
            )
            if winner in {"correction", "same_confirmation", "different_confirmation"}:
                waiting_payload = dict(payload)
                if winner == "different_confirmation":
                    waiting_payload["applicant_confirmation_evidence_reference"] = (
                        "SYNTHETIC-DIFFERENT-ACK"
                    )
                future = executor.submit(_method(repository), **waiting_payload)
            else:
                future = executor.submit(
                    repository.correct_draft_information,
                    actor_user_id=case["actor"],
                    client_id=case["client"],
                    cif_version_id=case["cif"],
                    expected_information=payload["expected_information"],
                    corrected_information=corrected,
                    reason="Synthetic concurrent correction",
                )
            pid = contender_pid.get(timeout=5)
            deadline = monotonic() + 5
            while (
                owner.info.backend_pid
                not in observer.execute(
                    "select pg_blocking_pids(%s) as blockers", (pid,)
                ).fetchone()["blockers"]
            ):
                assert monotonic() < deadline, (
                    "Confirmation did not wait on the CIF review lock"
                )
                Event().wait(0.02)
            owner_confirmation = None
            if winner == "correction":
                repository.correct_draft_information(
                    actor_user_id=case["actor"],
                    client_id=case["client"],
                    cif_version_id=case["cif"],
                    expected_information=payload["expected_information"],
                    corrected_information=corrected,
                    reason="Synthetic concurrent correction",
                )
            else:
                owner_confirmation = _method(repository)(**payload)
            owner.commit()
            if winner == "same_confirmation":
                waited = future.result(timeout=15)
                assert waited == owner_confirmation
            else:
                with pytest.raises(module.ClientCifConflict):
                    future.result(timeout=15)
            rows = _rows(observer, case["client"])
            if winner == "correction":
                assert rows == []
                assert _information(observer, case) == corrected
            else:
                assert len(rows) == 1
                assert rows[0]["review_snapshot"] == payload["expected_information"]
                assert _information(observer, case) == payload["expected_information"]
                assert rows[0]["id"] == owner_confirmation.id
                assert (
                    rows[0]["review_cycle_number"]
                    == owner_confirmation.review_cycle_number
                )
                assert rows[0]["confirmed_at"] == owner_confirmation.confirmed_at
        finally:
            owner.rollback()
            owner.close()
            executor.shutdown(wait=True, cancel_futures=True)
