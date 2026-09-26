"""Remaining R1 source-consumption and interrupted-file proofs.

Reuse the owned disposable database and actual owner transactions. Only
connection acquisition, a deliberate file failure, and the synthetic clock seam
are substituted; guards, locks, hashes, record writes and prior tests stay real.
"""

import base64
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
from threading import Event
from uuid import UUID, uuid4, uuid5

import psycopg
import pytest
import test_first_loan_disclosure_binding_postgres as binding_proof
import test_first_loan_disclosure_concurrency_postgres as concurrency_proof
import test_first_loan_disclosure_repository_postgres as review_proof
from first_loan_disclosure_fixtures import SUPPORT
from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore
from psycopg.rows import dict_row

from gilbic_backend import first_loan_disclosure_repository as reviews
from gilbic_backend import first_loan_repository as owner

isolated_database_url = concurrency_proof.isolated_database_url
isolated_r1_url = concurrency_proof.isolated_r1_url
seed_connection = concurrency_proof.seed_connection
private_fixture_configuration = review_proof.private_fixture_configuration
pytestmark = review_proof.pytestmark


def _replacement(connection, case):
    previous = connection.execute(
        "select * from lending.first_loan_disclosure_calculations "
        "where application_id=%s order by version_number desc limit 1",
        (case["app"].application_id,),
    ).fetchone()
    assert previous is not None
    payload = deepcopy(previous["input_snapshot"])
    request = UUID(str(previous["request_id"]))
    key = uuid5(request, "spina.r1.support.v1")
    assert previous["support_storage_key"] == key
    # Reuse the exact validated original support, not a fabricated source URL.
    content = reviews._support_bytes(previous)
    payload.update(
        request_id=str(uuid4()),
        supersedes_calculation_id=str(previous["id"]),
        support_base64=base64.b64encode(content).decode("ascii"),
    )
    return previous, payload


@pytest.mark.parametrize("stage", ("approve", "release"))
def test_waiting_consumer_rejects_newly_committed_calculation_replacement(
    seed_connection, isolated_r1_url, monkeypatch, stage
):
    case, action, arguments = concurrency_proof._source_action(
        seed_connection, monkeypatch, stage
    )
    previous, payload = _replacement(seed_connection, case)
    expected = []

    def replace_while_blocked():
        # The gate connection is the independent writer. Keep the real actor
        # check and record owner inside this same transaction before commit.
        with seed_connection.cursor(row_factory=dict_row) as cursor:
            owner._actor(
                cursor,
                case["actor"],
                case["device"],
                owner.APPROVE_PERMISSION,
                management=True,
            )
            successor = reviews.record_review(
                cursor,
                **review_proof._actor(case),
                request=payload,
            )
        assert successor["version_number"] == previous["version_number"] + 1
        expected.append(binding_proof._state(seed_connection))

    concurrency_proof._independent_connections(monkeypatch, isolated_r1_url)
    outcomes = concurrency_proof._race(
        seed_connection,
        [(action, arguments)],
        "select id from lending.loan_applications where id=%s for update",
        (case["app"].application_id,),
        while_blocked=replace_while_blocked,
    )
    assert len(expected) == 1
    assert outcomes[0][0] == "conflict"
    assert "Obtain a new review" in outcomes[0][1]
    assert review_proof._row(seed_connection, previous["id"]) == previous
    assert binding_proof._state(seed_connection) == expected[0]


def _consume_before_replacement(
    connection, database_url, monkeypatch, action, arguments, case, payload
):
    ready, allow_commit = Event(), Event()
    consumer_name, writer_name = (f"r1-proof-{uuid4().hex}" for _ in range(2))
    consumer_pid = []

    @contextmanager
    def acquire():
        with (
            psycopg.connect(
                database_url,
                row_factory=dict_row,
                application_name=concurrency_proof.SESSION_NAME.get(),
                options="-c statement_timeout=12000 -c lock_timeout=10000",
            ) as consumer_connection,
            consumer_connection.transaction(),
        ):
            yield consumer_connection
            if concurrency_proof.SESSION_NAME.get() == consumer_name:
                consumer_pid.append(consumer_connection.info.backend_pid)
                ready.set()
                if not allow_commit.wait(timeout=8):
                    raise AssertionError(
                        "The bounded calculation commit gate timed out"
                    )

    def invoke(name, operation, values):
        token = concurrency_proof.SESSION_NAME.set(name)
        try:
            return operation(**deepcopy(values))
        finally:
            concurrency_proof.SESSION_NAME.reset(token)

    connection.commit()
    monkeypatch.setattr(owner, "open_connection", acquire)
    monkeypatch.setattr(reviews, "open_connection", acquire)
    with ThreadPoolExecutor(max_workers=2) as pool:
        consumer = pool.submit(invoke, consumer_name, action, arguments)
        try:
            if not ready.wait(timeout=5):
                if consumer.done():
                    consumer.result(timeout=0)
                raise AssertionError("Consumer did not reach its real commit boundary")
            assert len(consumer_pid) == 1
            writer = pool.submit(
                invoke,
                writer_name,
                reviews.PostgresFirstLoanDisclosureRepository().record,
                {**review_proof._actor(case), "request": payload},
            )
            concurrency_proof._wait_until_blocked(
                connection,
                [writer_name],
                time.monotonic() + 1.5,
                blocker_pid=consumer_pid[0],
            )
            assert not consumer.done() and not writer.done()
        finally:
            # Always release the real transaction before executor cleanup.
            allow_commit.set()
        result = consumer.result(timeout=15)
        successor = writer.result(timeout=15)
    concurrency_proof._independent_connections(monkeypatch, database_url)
    return result, successor


@pytest.mark.parametrize("stage", ("approve", "release"))
def test_calculation_replacement_waits_for_consumer_and_preserves_committed_result(
    seed_connection, isolated_r1_url, monkeypatch, stage
):
    case, action, arguments = concurrency_proof._source_action(
        seed_connection, monkeypatch, stage
    )
    previous, payload = _replacement(seed_connection, case)
    original, successor = _consume_before_replacement(
        seed_connection, isolated_r1_url, monkeypatch, action, arguments, case, payload
    )
    binding = original["packet"]["tax_disclosure"]
    assert binding["calculation_id"] == str(previous["id"])
    assert binding["review_digest"] == previous["review_digest"]
    assert successor["version_number"] == previous["version_number"] + 1
    saved = review_proof._row(seed_connection, successor["id"])
    assert saved["supersedes_calculation_id"] == previous["id"]
    assert review_proof._row(seed_connection, previous["id"]) == previous
    before = binding_proof._state(seed_connection)
    assert action(**arguments) == original
    if stage == "approve":
        with pytest.raises(owner.FirstLoanConflict, match="Obtain a new review"):
            owner.PostgresFirstLoanRepository().register_packet_document(
                **review_proof._actor(case),
                loan_id=UUID(original["loan_id"]),
                packet_hash=original["packet_hash"],
                content=concurrency_proof.lifecycle_proof.PDF,
                expected_pricing_snapshot={},
            )
    else:
        assert action(**arguments) == original
    assert binding_proof._state(seed_connection) == before


def _midnight_clock(actual_clock, crossed):
    """Synthetic boundary only; the actual SQL clock and source data are unchanged."""

    def clock(cursor):
        moment, _day = actual_clock(cursor)
        last = moment.astimezone(reviews.MANILA).replace(
            hour=23, minute=59, second=59, microsecond=999999
        )
        instant = last + timedelta(microseconds=1) if crossed else last
        return instant, instant.date()

    return clock


@pytest.mark.parametrize("failure", ("interrupted_write", "midnight"))
def test_post_persistence_failure_retains_only_staged_bytes_then_exact_retry(
    seed_connection, isolated_r1_url, monkeypatch, failure
):
    repository, case = review_proof._setup(seed_connection, monkeypatch)
    payload = review_proof._payload(seed_connection, repository, case)
    actor = review_proof._actor(case)
    before = binding_proof._state(seed_connection)
    key = uuid5(UUID(payload["request_id"]), "spina.r1.support.v1")
    seed_connection.commit()
    concurrency_proof._independent_connections(monkeypatch, isolated_r1_url)
    actual_put, actual_clock = PrivateEvidenceStore.put, reviews._clock
    persisted = []

    def put_then_interrupt(store, storage_key, content, media_type):
        result = actual_put(store, storage_key, content, media_type)
        assert storage_key == key and content == SUPPORT
        persisted.append(storage_key)
        if failure == "interrupted_write":
            raise RuntimeError(
                "Synthetic interruption after immutable file persistence"
            )
        return result

    with monkeypatch.context() as fault:
        fault.setattr(PrivateEvidenceStore, "put", put_then_interrupt)
        fault.setattr(reviews, "_clock", _midnight_clock(actual_clock, persisted))
        expected = RuntimeError
        if failure == "midnight":
            expected = owner.FirstLoanConflict
        with pytest.raises(expected):
            repository.record(**actor, request=payload)
    assert persisted == [key]
    failed = binding_proof._state(seed_connection)
    assert failed[0] == before[0]
    assert failed[1][:2] == before[1][:2]
    assert failed[2] == before[2]
    assert failed[1][2] == {**before[1][2], f"{key.hex}.bin": SUPPORT}
    with pytest.raises(owner.FirstLoanConflict, match="unavailable"):
        repository.by_request(**actor, request_id=UUID(payload["request_id"]))
    assert binding_proof._state(seed_connection) == failed
    result = repository.record(**actor, request=payload)
    concurrency_proof._assert_one_review(seed_connection, before, result, case, payload)
    stable = binding_proof._state(seed_connection)
    assert repository.record(**actor, request=payload) == result
    assert binding_proof._state(seed_connection) == stable


@pytest.mark.parametrize("stage", ("approve", "release"))
def test_midnight_during_support_read_rolls_back_new_binding_without_rewriting_source(
    seed_connection, isolated_r1_url, monkeypatch, stage
):
    _case, action, arguments = concurrency_proof._source_action(
        seed_connection, monkeypatch, stage
    )
    before = binding_proof._state(seed_connection)
    seed_connection.commit()
    concurrency_proof._independent_connections(monkeypatch, isolated_r1_url)
    actual_support, actual_clock = reviews._support_bytes, reviews._clock
    read_completed = []

    def read_then_cross_midnight(row):
        result = actual_support(row)
        read_completed.append(row["id"])
        return result

    with monkeypatch.context() as clock:
        clock.setattr(reviews, "_support_bytes", read_then_cross_midnight)
        clock.setattr(reviews, "_clock", _midnight_clock(actual_clock, read_completed))
        with pytest.raises(owner.FirstLoanConflict, match="current source and date"):
            action(**arguments)
    assert len(read_completed) == 1
    assert binding_proof._state(seed_connection) == before
    original = action(**arguments)
    after = binding_proof._state(seed_connection)
    assert action(**arguments) == original
    assert binding_proof._state(seed_connection) == after
