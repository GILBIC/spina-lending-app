"""Real independent-session request races in an owned disposable database.

Reuse the existing isolated-database fixture; never commit fixtures into the
caller's rollback-only database. Only connection acquisition is substituted.
Business guards, row/advisory locks, private storage and writes remain real.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from uuid import UUID, uuid4, uuid5

import psycopg
import pytest
import test_employee_operations_concurrency_postgres as isolated_proof
import test_first_loan_disclosure_binding_postgres as binding_proof
import test_first_loan_disclosure_lifecycle_postgres as lifecycle_proof
import test_first_loan_disclosure_register_postgres as register_proof
import test_first_loan_disclosure_repository_postgres as review_proof
from first_loan_disclosure_fixtures import SUPPORT
from psycopg import sql
from psycopg.rows import dict_row

from gilbic_backend import first_loan_disclosure_repository as reviews
from gilbic_backend import first_loan_repository as owner

isolated_database_url = isolated_proof.isolated_database_url
private_fixture_configuration = review_proof.private_fixture_configuration
pytestmark = review_proof.pytestmark
SESSION_NAME = ContextVar("r1_proof_session", default="r1-proof-readback")


@pytest.fixture(scope="module")
def isolated_r1_url(isolated_database_url):
    # The reused fixture creates a separate generated DB through migration128
    # and drops only that exact DB. Apply129 here, never to its caller's DB.
    with psycopg.connect(isolated_database_url, autocommit=True) as connection:
        connection.execute(register_proof.MIGRATION.read_text(encoding="utf-8"))
    return isolated_database_url


@pytest.fixture
def seed_connection(isolated_r1_url):
    with psycopg.connect(isolated_r1_url, row_factory=dict_row) as connection:
        try:
            yield connection
        finally:
            connection.rollback()


def _independent_connections(monkeypatch, database_url):
    @contextmanager
    def acquire():
        with psycopg.connect(
            database_url,
            row_factory=dict_row,
            application_name=SESSION_NAME.get(),
            options="-c statement_timeout=12000 -c lock_timeout=10000",
        ) as connection:
            yield connection

    monkeypatch.setattr(owner, "open_connection", acquire)
    monkeypatch.setattr(reviews, "open_connection", acquire)


def _wait_until_blocked(connection, names, deadline):
    """Observe actual SQL waiters; elapsed sleep never establishes a race."""
    while time.monotonic() < deadline:
        connection.execute("select pg_stat_clear_snapshot()")
        rows = connection.execute(
            "select application_name,pid,wait_event_type,"
            "pg_blocking_pids(pid) as blockers from pg_stat_activity "
            "where datname=current_database() and application_name=any(%s)",
            (names,),
        ).fetchall()
        seen = {row["application_name"]: row for row in rows}
        if (
            set(seen) == set(names)
            and all(
                row["wait_event_type"] == "Lock" and row["blockers"]
                for row in seen.values()
            )
            and connection.info.backend_pid in seen[names[0]]["blockers"]
        ):
            return
        time.sleep(0.01)
    raise AssertionError("Both independent R1 sessions must reach real SQL locks")


def _race(connection, calls, gate_sql, gate_arguments=()):
    names = [f"r1-proof-{uuid4().hex}" for _ in calls]

    def invoke(name, action, arguments):
        token = SESSION_NAME.set(name)
        try:
            return "success", action(**deepcopy(arguments))
        except owner.FirstLoanConflict as error:
            return "conflict", str(error)
        finally:
            SESSION_NAME.reset(token)

    # Commit synthetic prerequisites before any other session can read them.
    # This connection belongs only to isolated_r1_url, never the caller's DB.
    connection.commit()
    futures = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        # On assertion/error this transaction releases the gate before the
        # executor waits for workers. Runtime review lock_timeout stays at2s.
        with connection.transaction():
            connection.execute(gate_sql, gate_arguments)
            deadline = time.monotonic() + 1.5
            for position, (action, arguments) in enumerate(calls):
                futures.append(pool.submit(invoke, names[position], action, arguments))
                _wait_until_blocked(connection, names[: position + 1], deadline)
        return [future.result(timeout=15) for future in futures]


def _assert_one_review(connection, before, result, case, payload):
    after = binding_proof._state(connection)
    assert after[0] == before[0]
    saved = review_proof._row(connection, result["id"])
    assert saved["request_id"] == UUID(payload["request_id"])
    assert saved["reviewed_by_user_id"] == case["actor"]
    assert [row for row in after[1][0] if row["id"] != saved["id"]] == before[1][0]
    assert len(after[1][0]) == len(before[1][0]) + 1
    added_audits = [row for row in after[2] if row not in before[2]]
    assert len(added_audits) == 1
    assert added_audits[0]["action"] == reviews.AUDIT_ACTION
    assert str(added_audits[0]["target_id"]) == str(saved["id"])
    assert added_audits[0]["actor_user_id"] == case["actor"]
    assert [row for row in after[2] if row != added_audits[0]] == before[2]
    counts = dict(before[1][1])
    counts[("core", "audit_logs")] += 1
    assert after[1][1] == counts
    key = uuid5(UUID(payload["request_id"]), "spina.r1.support.v1")
    assert saved["support_storage_key"] == key
    assert after[1][2] == {**before[1][2], f"{key.hex}.bin": SUPPORT}


@pytest.mark.parametrize("conflicting", (False, True))
def test_concurrent_new_review_request_has_one_record_audit_and_support_file(
    seed_connection, isolated_r1_url, monkeypatch, conflicting
):
    repository, case = review_proof._setup(seed_connection, monkeypatch)
    payload = review_proof._payload(seed_connection, repository, case)
    second = deepcopy(payload)
    if conflicting:
        second["review_rationale"] = "Different synthetic review under the same UUID"
    before = binding_proof._state(seed_connection)
    _independent_connections(monkeypatch, isolated_r1_url)
    outcomes = _race(
        seed_connection,
        [
            (repository.record, {**review_proof._actor(case), "request": request})
            for request in (payload, second)
        ],
        "lock table accounting.v1_tax_rule_evidence in access exclusive mode",
    )
    assert [kind for kind, _ in outcomes] == [
        "success",
        "conflict" if conflicting else "success",
    ]
    result = outcomes[0][1]
    assert result["version_number"] == 1
    if not conflicting:
        assert outcomes[1][1] == result
    _assert_one_review(seed_connection, before, result, case, payload)
    stable = binding_proof._state(seed_connection)
    assert repository.record(**review_proof._actor(case), request=payload) == result
    assert binding_proof._state(seed_connection) == stable


def test_competing_successors_can_create_only_one_next_review_version(
    seed_connection, isolated_r1_url, monkeypatch
):
    repository, case = review_proof._setup(seed_connection, monkeypatch)
    payload = review_proof._payload(seed_connection, repository, case)
    original = repository.record(**review_proof._actor(case), request=payload)
    first = {
        **payload,
        "request_id": str(uuid4()),
        "supersedes_calculation_id": original["id"],
    }
    second = {**first, "request_id": str(uuid4())}
    before = binding_proof._state(seed_connection)
    _independent_connections(monkeypatch, isolated_r1_url)
    outcomes = _race(
        seed_connection,
        [
            (repository.record, {**review_proof._actor(case), "request": request})
            for request in (first, second)
        ],
        "lock table accounting.v1_tax_rule_evidence in access exclusive mode",
    )
    assert sorted(kind for kind, _ in outcomes) == ["conflict", "success"]
    winner = next(
        position for position, (kind, _) in enumerate(outcomes) if kind == "success"
    )
    result = outcomes[winner][1]
    assert result["version_number"] == 2
    _assert_one_review(seed_connection, before, result, case, (first, second)[winner])
    saved = review_proof._row(seed_connection, result["id"])
    assert str(saved["supersedes_calculation_id"]) == original["id"]
    stable = binding_proof._state(seed_connection)
    historical = repository.record(**review_proof._actor(case), request=payload)
    assert review_proof._immutable_result(historical) == review_proof._immutable_result(
        original
    )
    assert "calculation_superseded" in historical["blockers"]
    assert binding_proof._state(seed_connection) == stable


@pytest.mark.parametrize("conflicting", (False, True))
def test_concurrent_release_records_one_handoff_and_never_repeats_financial_effects(
    seed_connection, isolated_r1_url, monkeypatch, conflicting
):
    context, release, arguments = lifecycle_proof._prepare(
        seed_connection, monkeypatch, "release"
    )
    second = dict(arguments)
    if conflicting:
        second["request_id"] = uuid4()
    before = binding_proof._state(seed_connection)
    _independent_connections(monkeypatch, isolated_r1_url)
    outcomes = _race(
        seed_connection,
        [(release, arguments), (release, second)],
        "select id from lending.loans where id=%s for update",
        (arguments["loan_id"],),
    )
    assert [kind for kind, _ in outcomes] == [
        "success",
        "conflict" if conflicting else "success",
    ]
    original = outcomes[0][1]
    if not conflicting:
        assert outcomes[1][1] == original
    loan_id = arguments["loan_id"]
    for table in (
        "first_loan_releases",
        "loan_contract_schedules",
        "loan_disbursement_events",
        "loan_collection_state",
        "first_loan_credential_intents",
    ):
        row = seed_connection.execute(
            sql.SQL("select count(*) as n from lending.{} where loan_id=%s").format(
                sql.Identifier(table)
            ),
            (loan_id,),
        ).fetchone()
        assert row["n"] == 1, table
    saved = seed_connection.execute(
        "select * from lending.first_loan_releases where loan_id=%s", (loan_id,)
    ).fetchone()
    assert saved["request_id"] == arguments["request_id"]
    assert saved["released_by_user_id"] == context["case"]["actor"]
    assert saved["packet_hash"] == arguments["packet_hash"]
    after = binding_proof._state(seed_connection)
    assert after[1][0] == before[1][0]
    assert after[1][2] == before[1][2]
    assert release(**arguments) == original
    assert release(**arguments) == original
    assert binding_proof._state(seed_connection) == after
