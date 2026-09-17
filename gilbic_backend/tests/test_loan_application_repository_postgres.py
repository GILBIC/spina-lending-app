"""Real draft persistence/retry tests; no HTTP identity or loan approval is implied.

Reuse the guarded onboarding database. Only connection acquisition is replaced;
SQL, constraints, transactions, saved values and concurrent connections are real.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from importlib import import_module
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from gilbic_backend.loan_application_information import LoanApplicationInformation
from test_client_cif_review_confirmation_postgres import (
    DATABASE_URL,
    _seed_summary_case,
    _summary_state,
    connection as connection,
    runtime_url as runtime_url,
)
from test_loan_application_history_postgres import TABLES, _read, _require_schema


pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)
MODULE = "gilbic_backend.loan_application_repository"
PERMISSION = "client_onboarding.requirement.review"


def _module():
    try:
        return import_module(MODULE)
    except ModuleNotFoundError as error:
        if error.name != MODULE:
            raise
        pytest.fail("Application draft repository is not implemented", pytrace=False)


def _repository(connection, monkeypatch):
    module = _module()

    @contextmanager
    def acquire():
        with connection.transaction():
            yield connection

    monkeypatch.setattr(module, "open_connection", acquire)
    return module.PostgresLoanApplicationRepository()


def _seed(connection, role="employee"):
    case = _seed_summary_case(connection)
    row = connection.execute(
        "insert into core.user_roles (user_id, role_id) "
        "select %s, id from core.roles where code = %s returning role_id",
        (case["actor"], role),
    ).fetchone()
    assert row is not None, "Existing office role is required by the fixture"
    # Explicit fixture permission on the disposable DB, not a production grant.
    connection.execute(
        "insert into core.role_permissions (role_id, permission_code) "
        "values (%s, %s) on conflict do nothing", (row["role_id"], PERMISSION),
    )
    return case


def _information(amount="3000.00"):
    return LoanApplicationInformation(request={"requested_amount": amount})


def _create(repository, case, reference, **changes):
    values = dict(actor_user_id=case["actor"], client_id=case["client"],
                  cif_version_id=case["cif"], application_reference=reference,
                  information=_information())
    values.update(changes)
    return repository.create_draft(**values)


def _append(repository, case, first, **changes):
    values = dict(actor_user_id=case["actor"], client_id=case["client"],
                  application_id=first.application_id, cif_version_id=case["cif"],
                  expected_version_number=1, information=_information("5000.00"))
    values.update(changes)
    return repository.append_draft(**values)


def _read_version(repository, case, first, **changes):
    values = dict(actor_user_id=case["actor"], client_id=case["client"],
                  application_id=first.application_id, version_number=1)
    values.update(changes)
    return repository.get_version(**values)


def _state(connection, case):
    return {
        "source": _summary_state(connection, case),
        **{table: connection.execute(
            sql.SQL("select * from lending.{} order by id").format(sql.Identifier(table))
        ).fetchall() for table in TABLES},
    }


def _source_without_application_counts(connection, case):
    state = _summary_state(connection, case)
    for table in TABLES:
        state["counts"].pop(f"lending.{table}")
    return state


@pytest.mark.parametrize("role", ["employee", "management"])
@pytest.mark.parametrize("stage", ["draft", "active"])
def test_create_saves_exact_draft_and_header_without_other_side_effects(
    connection, monkeypatch, role, stage
):
    repository = _repository(connection, monkeypatch)
    _require_schema(connection)
    case = _seed(connection, role)
    if stage == "active":
        connection.execute("update lending.clients set status='active' where id=%s", (case["client"],))
        connection.execute(
            "update lending.client_cif_versions set status='active', "
            "baseline_liveness_status='passed', baseline_face_scan_evidence_reference='SYNTHETIC-FACE', "
            "activated_at=now(), expires_at=now()+interval '5 years', "
            "review_due_at=now()+interval '5 years'-interval '90 days' where id=%s", (case["cif"],),
        )
    before = _source_without_application_counts(connection, case)
    reference = f"SYN-APP-{uuid4().hex}"
    information = _information()

    first = _create(repository, case, reference, information=information)

    header = _read(connection, TABLES[0], first.application_id)
    stored = _read(connection, TABLES[1], first.id)
    assert first.application_reference == reference == header["application_reference"]
    assert first.client_id == stored["client_id"] == header["client_id"] == case["client"]
    assert first.cif_version_id == stored["cif_version_id"] == case["cif"]
    assert first.version_number == stored["version_number"] == 1
    assert first.information == information
    assert stored["information"] == information.model_dump(mode="json")
    assert first.recorded_by_user_id == stored["recorded_by_user_id"] == case["actor"]
    assert header["created_by_user_id"] == case["actor"]
    now = connection.execute("select now() as now").fetchone()["now"]
    assert first.recorded_at == stored["recorded_at"] == header["created_at"] == now
    assert first.information.missing_fields()  # Incomplete is allowed, not confirmed.
    assert _read_version(repository, case, first) == first
    assert _source_without_application_counts(connection, case) == before


def test_identical_create_retry_retains_original_metadata_and_no_duplicates(connection, monkeypatch):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    reference = f"SYN-APP-{uuid4().hex}"
    first = _create(repository, case, reference)
    before = _state(connection, case)

    assert _create(repository, case, reference, information=_information()) == first
    assert _state(connection, case) == before


@pytest.mark.parametrize("field", ["client_id", "cif_version_id", "actor_user_id", "information"])
def test_conflicting_create_reference_never_reassigns_or_rewrites(connection, monkeypatch, field):
    repository = _repository(connection, monkeypatch)
    case, other = _seed(connection), _seed(connection)
    reference = f"SYN-APP-{uuid4().hex}"
    first = _create(repository, case, reference)
    changes = {
        "client_id": {"client_id": other["client"], "cif_version_id": other["cif"]},
        "cif_version_id": {"cif_version_id": case["next_cif"]},
        "actor_user_id": {"actor_user_id": other["actor"]},
        "information": {"information": _information("5000.00")},
    }[field]
    before = _state(connection, case)

    with pytest.raises(_module().LoanApplicationConflict):
        _create(repository, case, reference, **changes)

    assert _read_version(repository, case, first) == first
    assert _state(connection, case) == before


def test_changed_saves_append_and_exact_retries_never_rewind_history(connection, monkeypatch):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    reference = f"SYN-APP-{uuid4().hex}"
    first = _create(repository, case, reference)
    source = _source_without_application_counts(connection, case)
    second = _append(repository, case, first)
    third = _append(repository, case, first, expected_version_number=2,
                    information=_information("7000.00"))
    before = _state(connection, case)

    assert (first.version_number, second.version_number, third.version_number) == (1, 2, 3)
    assert len({first.id, second.id, third.id}) == 3
    assert _create(repository, case, reference) == first  # Late initial-save retry.
    assert _append(repository, case, first) == second  # Late retry of version 2.
    assert _append(repository, case, first, expected_version_number=3,
                   information=_information("7000.00")) == third  # No-op latest save.
    for record in (first, second, third):
        assert _read_version(repository, case, first,
                             version_number=record.version_number) == record
    assert _state(connection, case) == before
    assert _source_without_application_counts(connection, case) == source


def test_separate_applications_reuse_profile_without_reusing_loan_request(connection, monkeypatch):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    source = _source_without_application_counts(connection, case)
    first = _create(repository, case, f"SYN-APP-{uuid4().hex}")
    second = _create(repository, case, f"SYN-APP-{uuid4().hex}",
                     information=_information("5000.00"))

    assert first.application_id != second.application_id
    assert first.cif_version_id == second.cif_version_id == case["cif"]
    assert first.version_number == second.version_number == 1
    assert _read_version(repository, case, first) == first
    assert _source_without_application_counts(connection, case) == source


@pytest.mark.parametrize("expected,amount", [(1, "3000.00"), (1, "6000.00"), (3, "5000.00")])
def test_stale_or_future_expected_version_is_not_silently_overwritten(
    connection, monkeypatch, expected, amount
):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    first = _create(repository, case, f"SYN-APP-{uuid4().hex}")
    _append(repository, case, first)
    before = _state(connection, case)

    with pytest.raises(_module().LoanApplicationConflict):
        _append(repository, case, first, expected_version_number=expected,
                information=_information(amount))
    assert _state(connection, case) == before


def test_new_current_cif_creates_version_but_old_saved_version_stays_readable(connection, monkeypatch):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    first = _create(repository, case, f"SYN-APP-{uuid4().hex}")
    connection.execute("update lending.client_cif_versions set is_current=false, "
                       "status='superseded' where id=%s", (case["cif"],))
    connection.execute("update lending.client_cif_versions set is_current=true "
                       "where id=%s", (case["next_cif"],))
    second = _append(repository, case, first, cif_version_id=case["next_cif"],
                     information=first.information)
    connection.execute("update lending.clients set status='blocked' where id=%s", (case["client"],))
    before = _state(connection, case)

    assert second.version_number == 2 and second.cif_version_id == case["next_cif"]
    assert _read_version(repository, case, first) == first
    assert _read_version(repository, case, first, version_number=2) == second
    assert _state(connection, case) == before  # Historical read is not new-loan approval.


@pytest.mark.parametrize("operation", ["create", "append"])
@pytest.mark.parametrize("scenario", [
    "unknown_client", "wrong_cif", "unknown_cif", "not_current", "superseded",
    "blocked", "closed", "ineligible", "missing_applicant",
])
def test_new_writes_require_exact_eligible_sources_without_advancing_cif_stage(
    connection, monkeypatch, operation, scenario
):
    repository = _repository(connection, monkeypatch)
    case, other = _seed(connection), _seed(connection)
    first = _create(repository, case, f"SYN-APP-{uuid4().hex}")
    changes = {}
    if scenario == "unknown_client":
        changes["client_id"] = uuid4()
    elif scenario in {"wrong_cif", "unknown_cif"}:
        changes["cif_version_id"] = other["cif"] if scenario == "wrong_cif" else uuid4()
    elif scenario == "not_current":
        connection.execute("update lending.client_cif_versions set is_current=false where id=%s",
                           (case["cif"],))
    elif scenario == "superseded":
        connection.execute("update lending.client_cif_versions set status='superseded' where id=%s",
                           (case["cif"],))
    elif scenario in {"blocked", "closed"}:
        connection.execute("update lending.clients set status=%s where id=%s",
                           (scenario, case["client"]))
    elif scenario == "ineligible":
        connection.execute("update lending.client_onboarding_applicants "
                           "set status='requirements_rejected' where id=%s", (case["applicant"],))
    else:
        connection.execute("delete from lending.client_onboarding_applicants where id=%s",
                           (case["applicant"],))
    before = _state(connection, case)

    with pytest.raises(_module().LoanApplicationConflict):
        if operation == "create":
            _create(repository, case, f"SYN-APP-{uuid4().hex}", **changes)
        else:
            _append(repository, case, first, **changes)
    assert _state(connection, case) == before


@pytest.mark.parametrize("scenario", [
    "unknown", "inactive", "locked", "pending", "no_role", "collector", "client", "no_permission",
])
def test_persisted_office_actor_checks_apply_to_writes_reads_and_retries(connection, monkeypatch, scenario):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    reference = f"SYN-APP-{uuid4().hex}"
    first = _create(repository, case, reference)
    actor = case["actor"]
    if scenario == "unknown":
        actor = uuid4()
    elif scenario in {"inactive", "locked", "pending"}:
        connection.execute("update core.users set status=%s where id=%s", (scenario, actor))
    elif scenario == "no_permission":
        connection.execute("delete from core.role_permissions where permission_code=%s "
                           "and role_id in (select role_id from core.user_roles where user_id=%s)",
                           (PERMISSION, actor))
    else:
        connection.execute("delete from core.user_roles where user_id=%s", (actor,))
        if scenario != "no_role":
            row = connection.execute("insert into core.user_roles(user_id, role_id) "
                                     "select %s,id from core.roles where code=%s returning role_id",
                                     (actor, scenario)).fetchone()
            assert row is not None
            connection.execute("insert into core.role_permissions(role_id,permission_code) "
                               "values(%s,%s) on conflict do nothing", (row["role_id"], PERMISSION))
    before = _state(connection, case)

    for action in (
        lambda: _create(repository, case, f"SYN-APP-{uuid4().hex}", actor_user_id=actor),
        lambda: _create(repository, case, reference, actor_user_id=actor),
        lambda: _append(repository, case, first, actor_user_id=actor),
        lambda: _read_version(repository, case, first, actor_user_id=actor),
    ):
        with pytest.raises(_module().LoanApplicationAccessDenied):
            action()
        assert _state(connection, case) == before


@pytest.mark.parametrize("field", ["client_id", "application_id", "version_number"])
def test_exact_read_rejects_other_client_unknown_application_or_version(connection, monkeypatch, field):
    repository = _repository(connection, monkeypatch)
    case, other = _seed(connection), _seed(connection)
    first = _create(repository, case, f"SYN-APP-{uuid4().hex}")
    changes = {field: {"client_id": other["client"], "application_id": uuid4(),
                       "version_number": 2}[field]}
    before = _state(connection, case)

    with pytest.raises(_module().LoanApplicationConflict):
        _read_version(repository, case, first, **changes)
    assert _state(connection, case) == before


@pytest.mark.parametrize("operation", ["create", "append"])
def test_failed_version_insert_rolls_back_the_entire_save(connection, monkeypatch, operation):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    first = _create(repository, case, f"SYN-APP-{uuid4().hex}")
    name = f"synthetic_application_failure_{uuid4().hex}"
    connection.execute(sql.SQL("create function pg_temp.{}() returns trigger language plpgsql "
                               "as $$ begin raise exception 'SYNTHETIC application version failure'; end; $$")
                       .format(sql.Identifier(name)))
    connection.execute(sql.SQL("create trigger {} before insert on lending.loan_application_versions "
                               "for each row execute function pg_temp.{}()")
                       .format(sql.Identifier(name), sql.Identifier(name)))
    before = _state(connection, case)

    with pytest.raises(psycopg.errors.RaiseException, match="SYNTHETIC application version failure"):
        if operation == "create":
            _create(repository, case, f"SYN-APP-{uuid4().hex}")
        else:
            _append(repository, case, first)
    assert _state(connection, case) == before  # No orphan header or partial append.


@pytest.mark.parametrize("operation", ["create", "append"])
def test_concurrent_saves_have_one_winner_without_duplicate_or_overwritten_history(
    runtime_url, monkeypatch, operation
):
    module = _module()
    # runtime_url retains the strict loopback/disposable guard. Committed data
    # survives only until the existing runner drops this entire synthetic DB.
    @contextmanager
    def acquire():
        with psycopg.connect(runtime_url, row_factory=dict_row) as opened:
            opened.execute("set local statement_timeout='10s'")
            opened.execute("set local lock_timeout='10s'")
            yield opened

    monkeypatch.setattr(module, "open_connection", acquire)
    repository = module.PostgresLoanApplicationRepository()
    with psycopg.connect(runtime_url, row_factory=dict_row) as seed:
        _require_schema(seed)
        case = _seed(seed)
    reference = f"SYN-CONCURRENT-{uuid4().hex}"
    first = _create(repository, case, reference) if operation == "append" else None
    barrier = Barrier(2)

    def save(index):
        barrier.wait(timeout=5)
        try:
            if operation == "create":
                return _create(repository, case, reference)
            return _append(repository, case, first, information=_information(f"{5000 + index}.00"))
        except module.LoanApplicationConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [pool.submit(save, index) for index in range(2)]
        results = [future.result(timeout=15) for future in pending]
    with psycopg.connect(runtime_url, row_factory=dict_row) as inspect:
        headers = inspect.execute("select * from lending.loan_applications "
                                  "where application_reference=%s", (reference,)).fetchall()
        assert len(headers) == 1
        versions = inspect.execute("select * from lending.loan_application_versions "
                                   "where application_id=%s order by version_number",
                                   (headers[0]["id"],)).fetchall()
    if operation == "create":
        assert results[0] is not None and results[0] == results[1]
        assert len(versions) == 1 and versions[0]["id"] == results[0].id
    else:
        winners = [result for result in results if result is not None]
        assert len(winners) == 1 and len(versions) == 2
        assert versions[0]["id"] == first.id
        assert versions[0]["information"] == first.information.model_dump(mode="json")
        assert versions[1]["id"] == winners[0].id and winners[0].version_number == 2
        assert versions[1]["information"] == winners[0].information.model_dump(mode="json")
