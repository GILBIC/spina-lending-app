"""Real independent-session request races in an owned disposable database.

Reuse the existing isolated-database fixture; never commit fixtures into the
caller's rollback-only database. Only connection acquisition is substituted.
Business guards, row/advisory locks, private storage and writes remain real.
"""

import base64
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from threading import Event
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


def _wait_until_blocked(connection, names, deadline, *, blocker_pid=None):
    """Observe actual SQL waiters; elapsed sleep never establishes a race."""
    if blocker_pid is None:
        blocker_pid = connection.info.backend_pid
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
            and blocker_pid in seen[names[0]]["blockers"]
        ):
            return
        time.sleep(0.01)
    raise AssertionError("Both independent R1 sessions must reach real SQL locks")


def _race(connection, calls, gate_sql, gate_arguments=(), *, while_blocked=None):
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
            if while_blocked is not None:
                while_blocked()
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


@pytest.mark.parametrize("stage", ("approve", "release"))
@pytest.mark.parametrize("kind", ("dst", "grt"))
def test_applicable_rule_successor_committed_while_action_waits_rejects_stale_source(
    seed_connection, isolated_r1_url, monkeypatch, stage, kind
):
    if stage == "approve":
        repository, _, case, _, calculation = binding_proof._setup(
            seed_connection, monkeypatch
        )
        action = repository.approve
        arguments = binding_proof._arguments(case, calculation)
    else:
        context, action, arguments = lifecycle_proof._prepare(
            seed_connection, monkeypatch, "release"
        )
        case = context["case"]
    expected = []

    def supersede_while_blocked():
        # The worker has reached a real SQL lock. Use the existing rule writer
        # in this independent transaction, then commit before it can proceed.
        binding_proof._supersede_rule(seed_connection, case, kind)
        expected.append(binding_proof._state(seed_connection))

    _independent_connections(monkeypatch, isolated_r1_url)
    outcomes = _race(
        seed_connection,
        [(action, arguments)],
        "lock table accounting.v1_tax_rule_evidence in access exclusive mode",
        while_blocked=supersede_while_blocked,
    )
    assert len(expected) == 1
    assert [result for result, _ in outcomes] == ["conflict"]
    # Include the intentional rule/audit update but no stale approval, release,
    # new evidence, review mutation or partial financial effect from the worker.
    assert binding_proof._state(seed_connection) == expected[0]


def test_audit_rejection_rolls_back_review_and_exact_retry_reuses_staged_support(
    seed_connection, isolated_r1_url, monkeypatch
):
    repository, case = review_proof._setup(seed_connection, monkeypatch)
    payload = review_proof._payload(seed_connection, repository, case)
    actor = review_proof._actor(case)
    before = binding_proof._state(seed_connection)
    key = uuid5(UUID(payload["request_id"]), "spina.r1.support.v1")
    staged = {**before[1][2], f"{key.hex}.bin": SUPPORT}
    constraint = sql.Identifier(f"r1_test_audit_rejection_{uuid4().hex}")
    seed_connection.commit()
    _independent_connections(monkeypatch, isolated_r1_url)
    # Add a test-only restriction in the separately generated disposable DB.
    # Existing constraints/triggers are never disabled or weakened.
    with seed_connection.transaction():
        seed_connection.execute(
            sql.SQL(
                "alter table core.audit_logs add constraint {} "
                "check (actor_user_id <> {}::uuid or action <> {}) not valid"
            ).format(
                constraint,
                sql.Literal(str(case["actor"])),
                sql.Literal(reviews.AUDIT_ACTION),
            )
        )
    try:
        with pytest.raises(owner.FirstLoanConflict):
            repository.record(**actor, request=payload)
        failed = binding_proof._state(seed_connection)
        assert failed[0] == before[0]
        assert failed[1][:2] == before[1][:2]
        assert failed[2] == before[2]
        assert failed[1][2] == staged
        with pytest.raises(owner.FirstLoanConflict):
            repository.by_request(**actor, request_id=UUID(payload["request_id"]))
        assert binding_proof._state(seed_connection) == failed
    finally:
        # Release read snapshots before removing only our additional constraint.
        seed_connection.rollback()
        with seed_connection.transaction():
            seed_connection.execute(
                sql.SQL("alter table core.audit_logs drop constraint {}").format(
                    constraint
                )
            )

    different = SUPPORT.replace(b"SUPPORT", b"CHANGED")
    assert different != SUPPORT
    changed = {
        **payload,
        "support_base64": base64.b64encode(different).decode("ascii"),
    }
    with pytest.raises(owner.FirstLoanConflict):
        repository.record(**actor, request=changed)
    assert binding_proof._state(seed_connection) == failed

    result = repository.record(**actor, request=payload)
    assert result["version_number"] == 1
    _assert_one_review(seed_connection, before, result, case, payload)
    stable = binding_proof._state(seed_connection)
    assert repository.record(**actor, request=payload) == result
    assert repository.record(**actor, request=payload) == result
    metadata, content = repository.support(**actor, calculation_id=UUID(result["id"]))
    assert content == SUPPORT
    assert metadata["byte_count"] == len(SUPPORT)
    assert binding_proof._state(seed_connection) == stable


def _source_action(connection, monkeypatch, stage):
    """Choose an actual owner after creating its committed-ready prerequisites."""
    if stage == "review":
        repository, case = review_proof._setup(connection, monkeypatch)
        payload = review_proof._payload(connection, repository, case)
        return case, repository.record, {
            **review_proof._actor(case),
            "request": payload,
        }
    if stage == "approve":
        repository, _, case, _, calculation = binding_proof._setup(
            connection, monkeypatch
        )
        return case, repository.approve, binding_proof._arguments(case, calculation)
    assert stage == "release"
    context, action, arguments = lifecycle_proof._prepare(
        connection, monkeypatch, "release"
    )
    return context["case"], action, arguments


def _consume_before_rule_writer(
    connection, database_url, monkeypatch, action, arguments, case, kind
):
    """Hold the real consumer transaction open after its owner has succeeded.

    The owner runs inside a real outer transaction, so its nested transaction
    is a savepoint. No SQL lock or source guard is replaced. A separate observer
    must see the actual rule writer waiting on this consumer's PostgreSQL PID.
    """
    ready, commit_allowed = Event(), Event()
    consumer_name, writer_name = (f"r1-proof-{uuid4().hex}" for _ in range(2))
    consumer_pid = []

    @contextmanager
    def acquire():
        with psycopg.connect(
            database_url,
            row_factory=dict_row,
            application_name=SESSION_NAME.get(),
            options="-c statement_timeout=12000 -c lock_timeout=10000",
        ) as consumer:
            with consumer.transaction():
                yield consumer
                if SESSION_NAME.get() == consumer_name:
                    consumer_pid.append(consumer.info.backend_pid)
                    ready.set()
                    if not commit_allowed.wait(timeout=8):
                        raise AssertionError(
                            "The bounded consumer commit gate timed out"
                        )

    def consume():
        token = SESSION_NAME.set(consumer_name)
        try:
            return action(**deepcopy(arguments))
        finally:
            SESSION_NAME.reset(token)

    def write_rule():
        with psycopg.connect(
            database_url,
            row_factory=dict_row,
            application_name=writer_name,
            options="-c statement_timeout=12000 -c lock_timeout=10000",
        ) as writer:
            binding_proof._supersede_rule(writer, case, kind)
        return True

    connection.commit()
    monkeypatch.setattr(owner, "open_connection", acquire)
    monkeypatch.setattr(reviews, "open_connection", acquire)
    with ThreadPoolExecutor(max_workers=2) as pool:
        consumer = pool.submit(consume)
        try:
            if not ready.wait(timeout=5):
                if consumer.done():
                    consumer.result(timeout=0)
                raise AssertionError(
                    "The real consumer did not reach its commit boundary"
                )
            assert len(consumer_pid) == 1
            writer = pool.submit(write_rule)
            _wait_until_blocked(
                connection,
                [writer_name],
                time.monotonic() + 1.5,
                blocker_pid=consumer_pid[0],
            )
            locks = connection.execute(
                "select a.application_name,l.mode,l.granted from pg_locks l "
                "join pg_stat_activity a on a.pid=l.pid "
                "where l.relation='accounting.v1_tax_rule_evidence'::regclass "
                "and a.application_name=any(%s)",
                ([consumer_name, writer_name],),
            ).fetchall()
            assert any(
                lock["application_name"] == consumer_name
                and lock["mode"] == "ShareLock"
                and lock["granted"]
                for lock in locks
            )
            assert any(
                lock["application_name"] == writer_name and not lock["granted"]
                for lock in locks
            )
            assert not consumer.done() and not writer.done()
        finally:
            # Release before executor cleanup even when an assertion fails.
            commit_allowed.set()
        result = consumer.result(timeout=15)
        assert writer.result(timeout=15) is True
    _independent_connections(monkeypatch, database_url)
    return result


@pytest.mark.parametrize("stage", ("review", "approve", "release"))
@pytest.mark.parametrize("kind", ("dst", "grt"))
def test_rule_writer_waits_for_valid_consumer_commit_then_replay_stays_immutable(
    seed_connection, isolated_r1_url, monkeypatch, stage, kind
):
    case, action, arguments = _source_action(seed_connection, monkeypatch, stage)
    old_rule = seed_connection.execute(
        "select * from accounting.v1_tax_rule_evidence where id=%s",
        (case[f"{kind}_rule"],),
    ).fetchone()
    original = _consume_before_rule_writer(
        seed_connection, isolated_r1_url, monkeypatch, action, arguments, case, kind
    )
    successors = seed_connection.execute(
        "select id from accounting.v1_tax_rule_evidence "
        "where tax_type=%s and rule_key=%s and rule_version>%s",
        (old_rule["tax_type"], old_rule["rule_key"], old_rule["rule_version"]),
    ).fetchall()
    assert len(successors) == 1
    calculation_id = (
        original["id"]
        if stage == "review"
        else original["packet"]["tax_disclosure"]["calculation_id"]
    )
    saved = review_proof._row(seed_connection, calculation_id)
    assert saved[f"{kind}_rule_id"] == case[f"{kind}_rule"]
    assert saved["rule_snapshot"][kind]["id"] == str(case[f"{kind}_rule"])
    before_replay = binding_proof._state(seed_connection)
    replay = action(**arguments)
    if stage == "review":
        assert review_proof._immutable_result(replay) == review_proof._immutable_result(
            original
        )
        assert "source_context_changed" in replay["blockers"]
        changed = deepcopy(arguments)
        changed["request"]["request_id"] = str(uuid4())
        with pytest.raises(owner.FirstLoanConflict):
            action(**changed)
    else:
        assert replay == original
        if stage == "approve":
            with pytest.raises(owner.FirstLoanConflict):
                owner.PostgresFirstLoanRepository().register_packet_document(
                    **review_proof._actor(case),
                    loan_id=UUID(original["loan_id"]),
                    packet_hash=original["packet_hash"],
                    content=lifecycle_proof.PDF,
                    expected_pricing_snapshot={},
                )
        else:
            releases = seed_connection.execute(
                "select id from lending.first_loan_releases where loan_id=%s",
                (arguments["loan_id"],),
            ).fetchall()
            assert len(releases) == 1
    assert binding_proof._state(seed_connection) == before_replay


@pytest.mark.parametrize("stage", ("review", "approve", "release"))
@pytest.mark.parametrize("change", ("client", "cif"))
def test_committed_source_invalidation_blocks_waiting_action_without_partial_state(
    seed_connection, isolated_r1_url, monkeypatch, stage, change
):
    case, action, arguments = _source_action(seed_connection, monkeypatch, stage)
    expected = []

    def invalidate_while_blocked():
        if change == "client":
            seed_connection.execute(
                "update lending.clients set status='inactive' where id=%s",
                (case["client"],),
            )
        else:
            seed_connection.execute(
                "update lending.client_cif_versions "
                "set reverification_required_at=clock_timestamp(), "
                "reverification_reason=%s where id=%s",
                ("Synthetic concurrent source invalidation", case["cif"]),
            )
        expected.append(binding_proof._state(seed_connection))

    _independent_connections(monkeypatch, isolated_r1_url)
    outcomes = _race(
        seed_connection,
        [(action, arguments)],
        "select id from lending.loan_applications where id=%s for update",
        (case["app"].application_id,),
        while_blocked=invalidate_while_blocked,
    )
    assert len(expected) == 1
    assert [kind for kind, _ in outcomes] == ["conflict"]
    assert binding_proof._state(seed_connection) == expected[0]


@pytest.mark.parametrize("stage", ("review", "approve", "release"))
def test_real_rule_lock_timeout_rolls_back_and_same_request_can_retry(
    seed_connection, isolated_r1_url, monkeypatch, stage
):
    case, action, arguments = _source_action(seed_connection, monkeypatch, stage)
    before = binding_proof._state(seed_connection)
    _independent_connections(monkeypatch, isolated_r1_url)
    name = f"r1-proof-{uuid4().hex}"

    def invoke():
        token = SESSION_NAME.set(name)
        try:
            return action(**deepcopy(arguments))
        finally:
            SESSION_NAME.reset(token)

    seed_connection.commit()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with seed_connection.transaction():
            seed_connection.execute(
                "lock table accounting.v1_tax_rule_evidence in access exclusive mode"
            )
            pending = pool.submit(invoke)
            _wait_until_blocked(seed_connection, [name], time.monotonic() + 1.5)
            # Keep the real lock held until the owner's unchanged 2s timeout.
            with pytest.raises(owner.FirstLoanConflict, match="source is changing"):
                pending.result(timeout=5)
    assert binding_proof._state(seed_connection) == before
    original = action(**arguments)
    after = binding_proof._state(seed_connection)
    assert action(**arguments) == original
    assert binding_proof._state(seed_connection) == after
