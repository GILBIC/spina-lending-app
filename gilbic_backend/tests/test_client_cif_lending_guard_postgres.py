"""CIF readiness at existing credit authorities, in the owned disposable DB."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from test_client_cif_active_loan_source_postgres import _seed_active_source
from test_client_cif_review_confirmation_postgres import (
    DATABASE_URL,
    connection as connection,
    runtime_url as runtime_url,
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)
CONSTRAINT = "client_cif_new_credit_ready"


def _seed(connection):
    case = _seed_active_source(connection)
    case["type"] = connection.execute(
        """insert into lending.loan_types(code,name,term_days,calculation_mode)
        values(%s,'Synthetic CIF guard',30,'fixed_daily') returning id""",
        (f"CIF-GUARD-{uuid4().hex}",),
    ).fetchone()["id"]
    case["old_loan"] = _loan(connection, case)
    case["request"] = connection.execute(
        """insert into lending.client_renewal_requests
        (client_id,loan_id,requested_by_user_id,requested_amount)
        values(%s,%s,%s,1000) returning id""",
        (case["client"], case["old_loan"], case["actor"]),
    ).fetchone()["id"]
    return case


def _loan(connection, case, status="active"):
    return connection.execute(
        """insert into lending.loans
        (loan_number,client_id,loan_type_id,principal,daily_amount,
         date_released,due_date,status,created_by_user_id)
        values(%s,%s,%s,1000,40,
          case when %s='active' then current_date else null end,
          case when %s='active' then current_date+30 else null end,%s,%s)
        returning id""",
        (
            uuid4().hex,
            case["client"],
            case["type"],
            status,
            status,
            status,
            case["actor"],
        ),
    ).fetchone()["id"]


def _flag(connection, case):
    connection.execute(
        """update lending.client_cif_versions set reverification_required_at=now(),
        reverification_reason='Synthetic re-verification required' where id=%s""",
        (case["cif"],),
    )


def _approve(connection, case):
    connection.execute(
        """update lending.client_renewal_requests set status='approved',
        approved_principal=1000,reviewed_by_user_id=%s,reviewed_at=now() where id=%s""",
        (case["actor"], case["request"]),
    )


def _release(connection, case, loan_id, kind="new_loan_release"):
    return connection.execute(
        """select accounting.record_loan_disbursement_evidence(
        %s,%s,%s,current_date,current_date + time '12:00' at time zone 'Asia/Manila',
        1000,0,0,'cash_office',%s,'Synthetic CIF guard') as id""",
        (loan_id, case["actor"], kind, str(loan_id)),
    ).fetchone()["id"]


@pytest.mark.parametrize("status", ["approved", "active"])
def test_new_shared_loan_cannot_bypass_required_reverification(connection, status):
    case = _seed(connection)
    _flag(connection, case)
    with pytest.raises(psycopg.errors.CheckViolation) as caught:
        with connection.transaction():
            _loan(connection, case, status)
    assert caught.value.diag.constraint_name == CONSTRAINT


def test_existing_renewal_approval_cannot_bypass_required_reverification(connection):
    case = _seed(connection)
    _flag(connection, case)
    with pytest.raises(psycopg.errors.CheckViolation) as caught:
        with connection.transaction():
            _approve(connection, case)
    assert caught.value.diag.constraint_name == CONSTRAINT
    assert (
        connection.execute(
            "select status from lending.client_renewal_requests where id=%s",
            (case["request"],),
        ).fetchone()["status"]
        == "pending"
    )


@pytest.mark.parametrize("kind", ["new_loan_release", "renewal_release"])
def test_disbursement_rechecks_cif_after_previous_approval(connection, kind):
    case = _seed(connection)
    _approve(connection, case)
    _flag(connection, case)
    with pytest.raises(psycopg.errors.CheckViolation) as caught:
        with connection.transaction():
            _release(connection, case, case["old_loan"], kind)
    assert caught.value.diag.constraint_name == CONSTRAINT
    assert (
        connection.execute(
            "select count(*) as n from lending.loan_disbursement_events where client_id=%s",
            (case["client"],),
        ).fetchone()["n"]
        == 0
    )


def test_routine_servicing_and_existing_release_retry_remain_available(connection):
    case = _seed(connection)
    release = _release(connection, case, case["old_loan"])
    _flag(connection, case)
    assert _release(connection, case, case["old_loan"]) == release
    for status in ("defaulted", "active", "paid", "active"):
        connection.execute(
            "update lending.loans set status=%s where id=%s", (status, case["old_loan"])
        )
    connection.execute(
        """update lending.client_renewal_requests set collector_cash_received_at=now(),
        client_cash_confirmed_at=now(),handover_proof_status='under_review' where id=%s""",
        (case["request"],),
    )
    connection.execute(
        "select accounting.void_loan_disbursement_evidence(%s,%s,'Synthetic correction')",
        (release, case["actor"]),
    )


@pytest.mark.parametrize(
    "state",
    [
        "draft",
        "not_current",
        "expired",
        "blank_baseline",
        "future_activation",
        "inactive_client",
    ],
)
def test_generic_approval_requires_current_valid_cif(connection, state):
    case = _seed(connection)
    changes = {
        "draft": "status='draft'",
        "not_current": "is_current=false",
        "expired": "expires_at=now()-interval '1 day',review_due_at=now()-interval '91 days'",
        "blank_baseline": "baseline_face_scan_evidence_reference=' '",
        "future_activation": "activated_at=now()+interval '1 day'",
    }
    if state == "inactive_client":
        connection.execute(
            "update lending.clients set status='inactive' where id=%s",
            (case["client"],),
        )
    else:
        connection.execute(
            "update lending.client_cif_versions set " + changes[state] + " where id=%s",
            (case["cif"],),
        )
    with pytest.raises(psycopg.errors.CheckViolation) as caught:
        with connection.transaction():
            _loan(connection, case, "approved")
    assert caught.value.diag.constraint_name == CONSTRAINT


@pytest.mark.parametrize("previous", ["draft", "approved", "dated_approval"])
def test_existing_loan_transition_rechecks_after_cif_changes(connection, previous):
    case = _seed(connection)
    loan_id = _loan(connection, case, "draft" if previous == "draft" else "approved")
    if previous == "dated_approval":
        connection.execute(
            "update lending.loans set date_released=current_date,due_date=current_date+30 where id=%s",
            (loan_id,),
        )
    _flag(connection, case)
    with pytest.raises(psycopg.errors.CheckViolation) as caught:
        with connection.transaction():
            connection.execute(
                "update lending.loans set status='active',date_released=current_date,due_date=current_date+30 where id=%s",
                (loan_id,),
            )
    assert caught.value.diag.constraint_name == CONSTRAINT


@pytest.mark.parametrize("status", ["approved", "active"])
def test_cancelled_shared_loan_reapproval_requires_current_cif(connection, status):
    case = _seed(connection)
    connection.execute(
        "update lending.loans set status='cancelled' where id=%s",
        (case["old_loan"],),
    )
    _flag(connection, case)
    with pytest.raises(psycopg.errors.CheckViolation) as caught:
        with connection.transaction():
            connection.execute(
                "update lending.loans set status=%s where id=%s",
                (
                    status,
                    case["old_loan"],
                ),
            )
    assert caught.value.diag.constraint_name == CONSTRAINT


@pytest.mark.parametrize("boundary", ["release_to_collector", "give_cash", "activate"])
def test_renewal_handoff_rechecks_after_previous_approval(connection, boundary):
    case = _seed(connection)
    _approve(connection, case)
    _flag(connection, case)
    changes = {
        "release_to_collector": "cash_released_to_collector_at=now(),amount_locked_at=now()",
        "give_cash": "cash_given_to_client_at=now()",
        "activate": "activation_status='active'",
    }
    before = connection.execute(
        "select * from lending.client_renewal_requests where id=%s", (case["request"],)
    ).fetchone()
    with pytest.raises(psycopg.errors.CheckViolation) as caught:
        with connection.transaction():
            connection.execute(
                "update lending.client_renewal_requests set "
                + changes[boundary]
                + " where id=%s",
                (case["request"],),
            )
    assert caught.value.diag.constraint_name == CONSTRAINT
    assert (
        connection.execute(
            "select * from lending.client_renewal_requests where id=%s",
            (case["request"],),
        ).fetchone()
        == before
    )


def _execute_renewal(connection, case, new_loan, release):
    return connection.execute(
        """select accounting.record_loan_renewal_execution_evidence(
        %s,%s,%s,%s,current_date,current_date+time '13:00' at time zone 'Asia/Manila',
        0,%s,'Synthetic CIF guard',%s) as id""",
        (
            case["old_loan"],
            new_loan,
            release,
            case["actor"],
            str(new_loan),
            case["request"],
        ),
    ).fetchone()["id"]


def test_renewal_execution_rechecks_even_when_disbursement_was_recorded(connection):
    case = _seed(connection)
    _approve(connection, case)
    new_loan = _loan(connection, case)
    release = _release(connection, case, new_loan, "renewal_release")
    _flag(connection, case)
    with pytest.raises(psycopg.errors.CheckViolation) as caught:
        with connection.transaction():
            _execute_renewal(connection, case, new_loan, release)
    assert caught.value.diag.constraint_name == CONSTRAINT
    assert (
        connection.execute(
            "select count(*) as n from lending.loan_renewal_execution_events where client_id=%s",
            (case["client"],),
        ).fetchone()["n"]
        == 0
    )


@pytest.mark.parametrize("kind", ["valid", "expiring", "legacy_no_cif"])
def test_valid_expiring_and_legacy_clients_keep_existing_credit_flow(connection, kind):
    case = _seed(connection)
    if kind == "expiring":
        connection.execute(
            "update lending.client_cif_versions set expires_at=now()+interval '1 day',review_due_at=now()-interval '89 days' where id=%s",
            (case["cif"],),
        )
    elif kind == "legacy_no_cif":
        connection.execute(
            "delete from lending.client_cif_versions where client_id=%s",
            (case["client"],),
        )
    _approve(connection, case)
    new_loan = _loan(connection, case)
    release = _release(connection, case, new_loan, "renewal_release")
    execution = _execute_renewal(connection, case, new_loan, release)
    if kind != "legacy_no_cif":
        _flag(connection, case)
    assert _execute_renewal(connection, case, new_loan, release) == execution
    assert _release(connection, case, new_loan, "renewal_release") == release


@contextmanager
def _committed_case(runtime_url, *, legacy=False):
    with psycopg.connect(runtime_url, row_factory=dict_row) as setup_connection:
        case = _seed(setup_connection)
        if legacy:
            setup_connection.execute(
                "delete from lending.client_cif_versions where client_id=%s",
                (case["client"],),
            )
    try:
        yield case
    finally:
        with psycopg.connect(runtime_url) as cleanup:
            for table in ("client_renewal_requests", "loans", "client_cif_versions"):
                cleanup.execute(
                    sql.SQL("delete from lending.{} where client_id=%s").format(
                        sql.Identifier(table)
                    ),
                    (case["client"],),
                )
            cleanup.execute(
                "delete from lending.client_onboarding_applicants where id=%s",
                (case["applicant"],),
            )
            cleanup.execute(
                "delete from lending.clients where id in (%s,%s)",
                (case["client"], case["other"]),
            )
            cleanup.execute(
                "delete from lending.loan_types where id=%s", (case["type"],)
            )
            cleanup.execute("delete from core.users where id=%s", (case["actor"],))


def test_concurrent_cif_edit_fails_closed_without_deadlock(runtime_url):
    with _committed_case(runtime_url) as case:
        with psycopg.connect(runtime_url, row_factory=dict_row) as changing:
            _flag(changing, case)
            with psycopg.connect(runtime_url, row_factory=dict_row) as credit:
                credit.execute("set local statement_timeout='2s'")
                with pytest.raises(psycopg.errors.CheckViolation) as caught:
                    with credit.transaction():
                        _loan(credit, case, "approved")
                assert caught.value.diag.constraint_name == CONSTRAINT
        with psycopg.connect(runtime_url, row_factory=dict_row) as credit:
            with pytest.raises(psycopg.errors.CheckViolation):
                with credit.transaction():
                    _loan(credit, case, "approved")


def test_credit_holds_cif_readiness_until_its_transaction_finishes(runtime_url):
    with _committed_case(runtime_url) as case:
        with psycopg.connect(runtime_url, row_factory=dict_row) as credit:
            _loan(credit, case, "approved")
            with psycopg.connect(runtime_url, row_factory=dict_row) as changing:
                changing.execute("set local lock_timeout='100ms'")
                with pytest.raises(psycopg.errors.LockNotAvailable):
                    with changing.transaction():
                        _flag(changing, case)


def test_first_cif_creation_cannot_race_legacy_no_cif_exemption(runtime_url):
    with _committed_case(runtime_url, legacy=True) as case:
        ready = Event()
        worker_pid = []

        def approve_after_start():
            with psycopg.connect(runtime_url, row_factory=dict_row) as credit:
                credit.execute("set local statement_timeout='5s'")
                worker_pid.append(credit.info.backend_pid)
                ready.set()
                with pytest.raises(psycopg.errors.CheckViolation) as caught:
                    with credit.transaction():
                        _loan(credit, case, "approved")
                return caught.value.diag.constraint_name

        with psycopg.connect(runtime_url, row_factory=dict_row) as creating:
            creating.execute(
                "select id from lending.clients where id=%s for update",
                (case["client"],),
            )
            creating.execute(
                """insert into lending.client_cif_versions(client_id,version_number,full_name,phone_number,present_address)
                values(%s,1,'Synthetic first CIF','00000000000','Synthetic address')""",
                (case["client"],),
            )
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(approve_after_start)
                assert ready.wait(2)
                deadline = monotonic() + 2
                waiting = False
                while monotonic() < deadline:
                    waiting = creating.execute(
                        "select exists(select 1 from pg_locks where pid=%s and not granted) as blocked",
                        (worker_pid[0],),
                    ).fetchone()["blocked"]
                    if waiting:
                        break
                    sleep(0.01)
                # Release the transaction before joining even when assertion fails.
                creating.commit()
                assert waiting, (
                    "The new-credit writer must wait for initial CIF creation"
                )
                assert future.result(timeout=3) == CONSTRAINT


def test_guard_migration_rerun_preserves_data_and_one_trigger_per_boundary(connection):
    case = _seed(connection)
    migration = (
        Path(__file__).resolve().parents[1]
        / "sql"
        / "0126_guard_new_credit_with_current_cif.sql"
    )
    body = (
        migration.read_text(encoding="utf-8")
        .strip()
        .removeprefix("BEGIN;")
        .removesuffix("COMMIT;")
    )
    connection.execute(body)
    connection.execute(body)
    _flag(connection, case)
    with pytest.raises(psycopg.errors.CheckViolation) as caught:
        with connection.transaction():
            _approve(connection, case)
    assert caught.value.diag.constraint_name == CONSTRAINT
    triggers = connection.execute(
        """select tgname from pg_trigger where tgname in (
        'lending_new_loan_cif_readiness','lending_renewal_cif_readiness',
        'lending_disbursement_cif_readiness','lending_renewal_execution_cif_readiness')"""
    ).fetchall()
    assert len(triggers) == 4


def test_guard_functions_are_private_and_have_fixed_search_path(connection):
    functions = connection.execute(
        """select p.oid,p.proconfig,p.prosecdef,
        exists(select 1 from aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) acl
               where acl.grantee=0 and acl.privilege_type='EXECUTE') as public_execute
        from pg_proc p join pg_namespace n on n.oid=p.pronamespace
        where n.nspname='lending' and p.proname in (
        'require_current_cif_for_new_credit','guard_new_loan_cif_readiness',
        'guard_renewal_cif_readiness','guard_credit_execution_cif_readiness')"""
    ).fetchall()
    assert len(functions) == 4
    assert all(row["proconfig"] == ["search_path=pg_catalog"] for row in functions)
    assert not any(row["prosecdef"] or row["public_execute"] for row in functions)


def test_named_cif_errors_map_to_existing_evidence_conflict_contracts(connection):
    from gilbic_backend.loan_disbursement_evidence_repository import (
        LoanDisbursementEvidenceConflict,
        PostgresLoanDisbursementEvidenceRepository,
    )
    from gilbic_backend.loan_renewal_execution_evidence_repository import (
        LoanRenewalExecutionEvidenceConflict,
        PostgresLoanRenewalExecutionEvidenceRepository,
    )

    case = _seed(connection)
    _flag(connection, case)
    with pytest.raises(psycopg.errors.CheckViolation) as caught:
        with connection.transaction():
            _loan(connection, case, "approved")
    assert isinstance(
        PostgresLoanDisbursementEvidenceRepository._map_error(caught.value),
        LoanDisbursementEvidenceConflict,
    )
    assert isinstance(
        PostgresLoanRenewalExecutionEvidenceRepository._map_error(caught.value),
        LoanRenewalExecutionEvidenceConflict,
    )
